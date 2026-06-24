import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from scripts.make_admin import promote_to_admin
from tests.conftest import make_user


def test_promote_to_admin():
    make_user(role="user", email="promote@test.ai", firebase_uid="promote-uid")
    db = SessionLocal()
    try:
        u = promote_to_admin(db, "promote@test.ai")
        assert u.role == "admin"
    finally:
        db.close()
