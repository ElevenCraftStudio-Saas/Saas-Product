from tests.conftest import make_user
from app.core import limits
from app.models import models


# ---- Task 1: model columns ----

def test_new_user_quota_fields_default_none():
    u = make_user(role="user", email="limit1@test.ai", firebase_uid="limit-uid-1")
    assert u.max_events is None
    assert u.storage_limit_mb is None


# ---- Task 2: helpers ----

def test_default_event_limit_is_two():
    assert limits.DEFAULT_EVENT_LIMIT == 2


def test_default_storage_limit_is_50gb():
    assert limits.DEFAULT_STORAGE_LIMIT_MB == 51200  # 50 GB


def test_effective_event_limit():
    assert limits.effective_event_limit(models.User(max_events=None)) == 2
    assert limits.effective_event_limit(models.User(max_events=9)) == 9


def test_effective_storage_limit():
    assert limits.effective_storage_limit_mb(models.User(storage_limit_mb=None)) == 51200
    assert limits.effective_storage_limit_mb(models.User(storage_limit_mb=500)) == 500


# (event-create quota enforcement tests live in test_event_quota.py, added in Task 5)
