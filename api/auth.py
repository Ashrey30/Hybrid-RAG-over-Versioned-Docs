from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from common.config import ROOT
from email_validator import EmailNotValidError, validate_email

SESSION_TTL_SECONDS = 12 * 60 * 60
_PASSWORD_SPECIALS = "!@#$%^&*"
_SCRYPT_N = 1 << 14
_DUMMY_SALT = b"hybrid-rag-auth-dummy"
_DUMMY_HASH = hashlib.scrypt(b"not-a-password", salt=_DUMMY_SALT, n=_SCRYPT_N, r=8, p=1)


@dataclass(frozen=True)
class User:
    id: int
    email: str
    role: str

    @property
    def access_group(self) -> str:
        return "restricted" if self.role == "admin" else "public"


class AuthStore:
    def __init__(self, path: Path | None = None):
        configured_path = os.getenv("AUTH_DB_PATH")
        self.path = Path(configured_path) if configured_path else (path or ROOT / "data" / "auth.sqlite")

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        con = self._connect()
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def initialize(self) -> None:
        with self._connection() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'admin')),
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
                """
            )

    @staticmethod
    def normalize_email(email: str) -> str:
        if not isinstance(email, str):
            raise ValueError("Enter a valid email address.")
        try:
            normalized = validate_email(email.strip(), check_deliverability=False).normalized.casefold()
        except EmailNotValidError as exc:
            raise ValueError("Enter a valid email address.") from exc
        if len(normalized) > 254:
            raise ValueError("Enter a valid email address.")
        return normalized

    @staticmethod
    def _password_bytes(password: str) -> bytes:
        if not isinstance(password, str) or len(password) > 1024:
            raise ValueError("Password must be at most 1024 characters.")
        return password.encode("utf-8")

    @staticmethod
    def validate_password(password: str) -> None:
        if not isinstance(password, str) or len(password) < 9:
            raise ValueError("Password must be at least 9 characters.")
        if len(password) > 1024:
            raise ValueError("Password must be at most 1024 characters.")
        if not re.search(r"[A-Z]", password):
            raise ValueError("Password must include an uppercase letter.")
        if not re.search(r"[a-z]", password):
            raise ValueError("Password must include a lowercase letter.")
        if not re.search(r"[0-9]", password):
            raise ValueError("Password must include a number.")
        if not any(char in _PASSWORD_SPECIALS for char in password):
            raise ValueError(f"Password must include one of these special characters: {_PASSWORD_SPECIALS}")

    @staticmethod
    def _password_hash(password: bytes, salt: bytes) -> bytes:
        return hashlib.scrypt(password, salt=salt, n=_SCRYPT_N, r=8, p=1)

    @staticmethod
    def _user(row: sqlite3.Row) -> User:
        return User(id=row["id"], email=row["email"], role=row["role"])

    def create_user(self, email: str, password: str, role: str = "user") -> User:
        self.initialize()
        normalized_email = self.normalize_email(email)
        self.validate_password(password)
        password_bytes = self._password_bytes(password)
        if role not in {"user", "admin"}:
            raise ValueError("Role must be user or admin.")
        salt = secrets.token_bytes(16)
        password_hash = self._password_hash(password_bytes, salt)
        with self._connection() as con:
            cursor = con.execute(
                "INSERT INTO users (email, password_salt, password_hash, role, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (normalized_email, salt, password_hash, role, int(time.time())),
            )
            row = con.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._user(row)

    def authenticate(self, email: str, password: str) -> User | None:
        self.initialize()
        try:
            normalized_email = self.normalize_email(email)
            password_bytes = self._password_bytes(password)
        except ValueError:
            normalized_email = ""
            password_bytes = b"invalid"
        with self._connection() as con:
            row = con.execute("SELECT * FROM users WHERE email = ?", (normalized_email,)).fetchone()
        if row is None:
            hmac.compare_digest(self._password_hash(password_bytes[:1024], _DUMMY_SALT), _DUMMY_HASH)
            return None
        computed = self._password_hash(password_bytes, row["password_salt"])
        if not hmac.compare_digest(computed, row["password_hash"]):
            return None
        return self._user(row)

    def create_session(self, user_id: int, ttl_seconds: int = SESSION_TTL_SECONDS) -> str:
        self.initialize()
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        with self._connection() as con:
            con.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            con.execute(
                "INSERT INTO sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (hashlib.sha256(token.encode()).hexdigest(), user_id, now + ttl_seconds, now),
            )
        return token

    def user_for_session(self, token: str | None) -> User | None:
        if not token or len(token) > 256:
            return None
        self.initialize()
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self._connection() as con:
            row = con.execute(
                "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id "
                "WHERE sessions.token_hash = ? AND sessions.expires_at > ?",
                (token_hash, int(time.time())),
            ).fetchone()
        return self._user(row) if row else None

    def revoke_session(self, token: str | None) -> None:
        if not token or len(token) > 256:
            return
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self._connection() as con:
            con.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
