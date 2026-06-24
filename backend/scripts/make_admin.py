"""Promote an existing user to the single admin role, by email.

This is the ONLY way to mint an admin (no auto-admin on signup). Run once,
after the intended admin has signed in at least once.

Usage (from backend/):  python scripts/make_admin.py user@example.com
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal  # noqa: E402
from app.models import models  # noqa: E402


def promote_to_admin(db, email: str):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise SystemExit(f"No user with email {email!r} (must sign in once first).")
    user.role = "admin"
    db.commit()
    db.refresh(user)
    return user


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/make_admin.py <email>")
    db = SessionLocal()
    try:
        u = promote_to_admin(db, sys.argv[1])
        print(f"OK: {u.email} is now {u.role}")
    finally:
        db.close()
