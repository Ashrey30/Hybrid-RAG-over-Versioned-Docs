from fastapi.testclient import TestClient
import pytest

from api import main
from api.auth import AuthStore


def test_user_registration_login_logout_and_role_enforcement(tmp_path, monkeypatch):
    store = AuthStore(tmp_path / "auth.sqlite")
    monkeypatch.setattr(main, "_auth_store", store)
    calls = []

    class FakePipeline:
        def ask(self, question, group):
            calls.append((question, group))
            return {
                "answer": "grounded answer",
                "status": "answered",
                "citations": [],
                "trace": {"timings_ms": {"total": 1}},
                "_debug": {},
            }

        def suggestions(self, group, exclude):
            calls.append(("suggestions", group, exclude))
            return [{"key": "topic-a", "question": "What is topic A?", "source": "Document A"}]

    monkeypatch.setattr(main, "pipe", lambda: FakePipeline())
    with TestClient(main.app) as client:
        assert client.get("/suggestions").status_code == 401
        response = client.post(
            "/auth/register",
            json={"email": "Person@Example.com", "password": "A sufficiently long password1!", "role": "admin"},
        )
        assert response.status_code == 201
        assert response.json()["role"] == "user"
        assert response.json()["access_group"] == "public"
        assert client.get("/auth/me").json()["email"] == "person@example.com"

        suggestions = client.get("/suggestions", params=[("exclude", "topic-x")])
        assert suggestions.status_code == 200
        assert suggestions.json()["suggestions"][0]["source"] == "Document A"
        assert calls[-1] == ("suggestions", "public", ["topic-x"])

        answer = client.post("/ask", json={"question": "hello"})
        assert answer.status_code == 200
        assert "trace" not in answer.json()
        assert calls[-1] == ("hello", "public")

        assert client.post("/auth/logout", json={}).status_code == 200
        assert client.get("/auth/me").status_code == 401
        assert client.post("/ask", json={"question": "hello"}).status_code == 401

        assert client.post(
            "/auth/register",
            json={"email": "PERSON@example.com", "password": "Another sufficiently long password2@"},
        ).status_code == 409
        assert client.post(
            "/auth/register",
            json={"email": "weak@example.com", "password": "all lowercase1!"},
        ).status_code == 422
        assert client.post(
            "/auth/login",
            json={"email": "person@example.com", "password": "IncorrectPassword1!"},
        ).status_code == 401
        assert client.post(
            "/auth/login",
            json={"email": "person@example.com", "password": "' OR 1=1 --"},
        ).status_code == 401
        assert client.post(
            "/auth/login",
            json={"email": "person@example.com' OR '1'='1", "password": "A sufficiently long password1!"},
        ).status_code == 422
        assert client.post(
            "/auth/register",
            json={"email": "' OR 1=1 --@example.com", "password": "A sufficiently long password1!"},
        ).status_code == 422

        admin = store.create_user("admin@example.com", "An admin password long enough1!", role="admin")
        admin_client = TestClient(main.app)
        login = admin_client.post(
            "/auth/login",
            json={"email": admin.email, "password": "An admin password long enough1!"},
        )
        assert login.status_code == 200
        assert login.json()["access_group"] == "restricted"
        assert admin_client.get("/suggestions").status_code == 200
        assert calls[-1] == ("suggestions", "restricted", [])
        admin_answer = admin_client.post("/ask", json={"question": "restricted question"})
        assert "trace" in admin_answer.json()
        assert calls[-1] == ("restricted question", "restricted")


def test_session_expiration_and_revocation(tmp_path):
    store = AuthStore(tmp_path / "auth.sqlite")
    user = store.create_user("user@example.com", "A sufficiently long password1!")

    expired = store.create_session(user.id, ttl_seconds=-1)
    assert store.user_for_session(expired) is None

    session = store.create_session(user.id)
    assert store.user_for_session(session) == user
    store.revoke_session(session)
    assert store.user_for_session(session) is None


def test_password_policy_requires_length_case_number_and_supported_symbol():
    for password in (
        "Ab1!",
        "lowercase123!",
        "UPPERCASE123!",
        "MixedCase!!",
        "MixedCase123",
        "MixedCase123?",
    ):
        with pytest.raises(ValueError):
            AuthStore.validate_password(password)

    for symbol in "!@#$%^&*":
        AuthStore.validate_password(f"Abcdefgh1{symbol}")


def test_email_validation_rejects_malformed_and_sql_injection_shaped_addresses(tmp_path):
    store = AuthStore(tmp_path / "auth.sqlite")
    for email in ("missing-at.example.com", "person@@example.com", "person@example", "' OR 1=1 --@example.com"):
        with pytest.raises(ValueError, match="valid email"):
            store.normalize_email(email)

    assert store.normalize_email("  Person@Example.com ") == "person@example.com"


def test_legacy_demo_token_endpoint_is_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_auth_store", AuthStore(tmp_path / "auth.sqlite"))
    monkeypatch.setattr(main, "pipe", lambda: None)

    with TestClient(main.app) as client:
        assert client.get("/demo-token?group=restricted").status_code == 404
