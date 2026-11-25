from __future__ import annotations

from getpass import getpass
import sqlite3

from api.auth import AuthStore


def main() -> None:
    store = AuthStore()
    email = input("Admin email: ").strip()
    password = getpass("Admin password (9+ chars, upper/lowercase, number, and !@#$%^&*): ")
    confirmation = getpass("Confirm admin password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    try:
        user = store.create_user(email, password, role="admin")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        if "users.email" in str(exc):
            raise SystemExit("That email already has an account; no role was changed.") from exc
        raise
    print(f"Admin account created for {user.email}.")


if __name__ == "__main__":
    main()
