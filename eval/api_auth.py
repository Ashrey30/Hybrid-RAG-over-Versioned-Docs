from __future__ import annotations

import os


def authenticate_api(client, base_url: str, *, require_admin: bool = False) -> dict:
    email = os.getenv("RAG_TEST_EMAIL")
    password = os.getenv("RAG_TEST_PASSWORD")
    if not email or not password:
        raise RuntimeError("Set RAG_TEST_EMAIL and RAG_TEST_PASSWORD for API evaluation.")
    response = client.post(
        f"{base_url.rstrip('/')}/auth/login",
        json={"email": email, "password": password},
    )
    response.raise_for_status()
    user = response.json()
    if require_admin and user.get("role") != "admin":
        raise RuntimeError("This evaluation needs an admin account to read request metrics.")
    return user
