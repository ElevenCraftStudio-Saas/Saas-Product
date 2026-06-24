# Admin Role + Per-User Event Limits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single system admin (first user) with its own role-gated page that manages all users and their per-user event quota, while studio users get a separate page and cannot administer anything.

**Architecture:** Backend adds a third role (`admin`) plus a nullable `User.max_events` column and an `effective_event_limit` helper; event creation is blocked over quota; the admin router is re-gated to admins and gains a quota-setting endpoint. Frontend reads the backend role via a `useMe()` hook, splits `/admin` (admin-only) from `/dashboard` (studio-only) into separate route groups, and redirects by role at login.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, pytest (SQLite + mocks); Next.js 16 (App Router, webpack dev), React 19, TanStack Query, Axios, sonner.

## Global Constraints

- Roles are exactly `admin`, `studio`, `guest`. Exactly one admin; admin role is granted only by bootstrap (first user), never via API.
- Default event quota for new studios: `DEFAULT_EVENT_LIMIT = 2`. `User.max_events = NULL` means "use default".
- Over-quota event creation returns `HTTP 403` with detail exactly: `Event limit reached ({count}/{limit}). Contact your admin to raise it.`
- Schema changes go through Alembic (`alembic upgrade head`), never `create_all`. Current head: `d3e4f5a6b7c8`.
- Backend tests run via `..\.venv\Scripts\python.exe -m pytest` from `backend/` (the venv launcher shims are broken after the drive move — always use `python -m`).
- Frontend has no test runner; frontend tasks verify with `npx tsc --noEmit` + `npx eslint` + a stated manual browser check.
- Do not print or commit real secrets. `.env` stays untracked.

---

### Task 1: Add `User.max_events` column + migration

**Files:**
- Modify: `backend/app/models/models.py:14-25` (User model)
- Create: `backend/alembic/versions/e4f5a6b7c8d9_user_max_events.py`
- Test: `backend/tests/test_limits.py`

**Interfaces:**
- Produces: `models.User.max_events` (`Optional[int]`, nullable, default `None`).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_limits.py`:

```python
from tests.conftest import make_user


def test_new_user_max_events_defaults_to_none():
    u = make_user(role="studio", email="limit1@test.ai", firebase_uid="limit-uid-1")
    assert u.max_events is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_limits.py -v`
Expected: FAIL — `AttributeError: 'User' object has no attribute 'max_events'`.

- [ ] **Step 3: Add the column to the model**

In `backend/app/models/models.py`, inside `class User`, add after the `role` line (line 22):

```python
    role = Column(String, default="studio")  # "admin", "studio", or "guest"
    max_events = Column(Integer, nullable=True)  # null = use DEFAULT_EVENT_LIMIT
```

(`Integer` is already imported at the top of the file.)

- [ ] **Step 4: Run test to verify it passes**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_limits.py -v`
Expected: PASS (SQLite test DB is created fresh from the models each test).

- [ ] **Step 5: Create the Alembic migration**

Create `backend/alembic/versions/e4f5a6b7c8d9_user_max_events.py`:

```python
"""user max_events quota

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-06-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('max_events', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'max_events')
```

- [ ] **Step 6: Verify the migration chains cleanly (offline check)**

Run: `..\.venv\Scripts\python.exe -m alembic history`
Expected: the list ends with `... d3e4f5a6b7c8 -> e4f5a6b7c8d9 (head), user max_events quota`. (No DB connection needed for `history`.)

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/models.py backend/alembic/versions/e4f5a6b7c8d9_user_max_events.py backend/tests/test_limits.py
git commit -m "feat: add User.max_events quota column + migration"
```

---

### Task 2: `DEFAULT_EVENT_LIMIT` + `effective_event_limit` helper

**Files:**
- Create: `backend/app/core/limits.py`
- Test: `backend/tests/test_limits.py` (append)

**Interfaces:**
- Produces:
  - `app.core.limits.DEFAULT_EVENT_LIMIT: int` (read from env `DEFAULT_EVENT_LIMIT`, default `2`).
  - `app.core.limits.effective_event_limit(user: models.User) -> int`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_limits.py`:

```python
from app.core import limits
from app.models import models


def test_effective_limit_uses_default_when_none():
    u = models.User(role="studio", max_events=None)
    assert limits.effective_event_limit(u) == limits.DEFAULT_EVENT_LIMIT


def test_effective_limit_uses_explicit_value():
    u = models.User(role="studio", max_events=5)
    assert limits.effective_event_limit(u) == 5


def test_default_limit_is_two():
    assert limits.DEFAULT_EVENT_LIMIT == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_limits.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.limits'`.

- [ ] **Step 3: Create the helper**

Create `backend/app/core/limits.py`:

```python
"""Per-user event quota helpers."""
import os

# Default number of events a new studio may create. A user's max_events
# column overrides this when set; null falls back here.
DEFAULT_EVENT_LIMIT = int(os.getenv("DEFAULT_EVENT_LIMIT", "2"))


def effective_event_limit(user) -> int:
    """Resolve a user's event cap: explicit max_events, else the default."""
    if getattr(user, "max_events", None) is not None:
        return user.max_events
    return DEFAULT_EVENT_LIMIT
```

- [ ] **Step 4: Run test to verify it passes**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_limits.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/limits.py backend/tests/test_limits.py
git commit -m "feat: add DEFAULT_EVENT_LIMIT and effective_event_limit helper"
```

---

### Task 3: `admin` bootstrap + `get_current_admin` dependency

**Files:**
- Modify: `backend/app/routers/deps.py:35-49` (bootstrap role), append new dependency at end of file
- Modify: `backend/tests/conftest.py` (add `as_admin` fixture)
- Test: `backend/tests/test_admin_role.py`

**Interfaces:**
- Consumes: `deps.get_current_user`.
- Produces:
  - Bootstrap: first user created → `role="admin"`, all later → `role="guest"`.
  - `deps.get_current_admin(current_user) -> models.User` — raises `403 "Admin access required"` unless `role == "admin"`.
  - conftest `as_admin` fixture overriding `get_current_user` + `get_current_admin`.

- [ ] **Step 1: Add the `as_admin` fixture to conftest**

In `backend/tests/conftest.py`, append:

```python
@pytest.fixture
def as_admin():
    """Override auth deps to act as the single admin user; returns the user."""
    user = make_user(role="admin", email="admin@test.ai", firebase_uid="admin-uid")

    def _current():
        db = _db_session()
        try:
            return db.query(models.User).filter(models.User.id == user.id).first()
        finally:
            db.close()

    app_main.app.dependency_overrides[deps.get_current_user] = _current
    app_main.app.dependency_overrides[deps.get_current_admin] = _current
    return user
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_admin_role.py`:

```python
from app.database import SessionLocal
from app.models import models
from app.routers import deps
from app import main as app_main
from fastapi import HTTPException
import pytest
from tests.conftest import make_user


def test_first_user_bootstraps_as_admin():
    decoded = {"uid": "boot-1", "email": "first@test.ai", "name": "First"}
    db = SessionLocal()
    try:
        u = deps._find_or_create_user(decoded, db)
        assert u.role == "admin"
    finally:
        db.close()


def test_second_user_is_guest():
    db = SessionLocal()
    try:
        deps._find_or_create_user({"uid": "boot-1", "email": "a@test.ai"}, db)
        second = deps._find_or_create_user({"uid": "boot-2", "email": "b@test.ai"}, db)
        assert second.role == "guest"
    finally:
        db.close()


def test_get_current_admin_allows_admin():
    admin = make_user(role="admin", email="adm@test.ai", firebase_uid="adm-uid")
    assert deps.get_current_admin(admin) is admin


def test_get_current_admin_rejects_studio():
    studio = make_user(role="studio", email="st@test.ai", firebase_uid="st-uid")
    with pytest.raises(HTTPException) as exc:
        deps.get_current_admin(studio)
    assert exc.value.status_code == 403
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_admin_role.py -v`
Expected: FAIL — `AttributeError: module 'app.routers.deps' has no attribute 'get_current_admin'` and the bootstrap test asserting `"admin"` fails (currently `"studio"`).

- [ ] **Step 4: Change bootstrap role**

In `backend/app/routers/deps.py`, change lines 35-38 from:

```python
    # Bootstrap: the very first user becomes studio (owner). Everyone after
    # defaults to guest (least privilege); promote via /api/auth/promote.
    is_first_user = db.query(models.User).count() == 0
    role = "studio" if is_first_user else "guest"
```

to:

```python
    # Bootstrap: the very first user becomes the single admin (owner). Everyone
    # after defaults to guest (least privilege); admin promotes to studio.
    is_first_user = db.query(models.User).count() == 0
    role = "admin" if is_first_user else "guest"
```

- [ ] **Step 5: Add the `get_current_admin` dependency**

At the end of `backend/app/routers/deps.py`, append:

```python
def get_current_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    """Require the admin account (admin-only management endpoints)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_admin_role.py -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/deps.py backend/tests/conftest.py backend/tests/test_admin_role.py
git commit -m "feat: bootstrap first user as admin + get_current_admin gate"
```

---

### Task 4: Enforce the event quota on create

**Files:**
- Modify: `backend/app/routers/events.py:1-21` (imports), `:63-69` (create_event head)
- Test: `backend/tests/test_limits.py` (append)

**Interfaces:**
- Consumes: `app.core.limits.effective_event_limit`, `as_studio` fixture.
- Produces: `POST /api/events/` returns `403` with the exact quota message when `count >= limit`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_limits.py`:

```python
def _make_event_payload(title):
    return {"title": title, "description": "d", "event_date": "2026-07-01T00:00:00"}


def test_create_event_allowed_under_limit(client, as_studio):
    r = client.post("/api/events/", json=_make_event_payload("E1"))
    assert r.status_code == 200, r.text


def test_create_event_blocked_at_limit(client, as_studio):
    # Default limit is 2; create 2, third must fail.
    assert client.post("/api/events/", json=_make_event_payload("E1")).status_code == 200
    assert client.post("/api/events/", json=_make_event_payload("E2")).status_code == 200
    r = client.post("/api/events/", json=_make_event_payload("E3"))
    assert r.status_code == 403
    assert "Event limit reached (2/2)" in r.json()["detail"]
    assert "Contact your admin" in r.json()["detail"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_limits.py -k "create_event" -v`
Expected: FAIL — the third create returns `200` (no enforcement yet) so `test_create_event_blocked_at_limit` fails.

- [ ] **Step 3: Add the import**

In `backend/app/routers/events.py`, after line 16 (`from ..services import retention`), add:

```python
from ..core.limits import effective_event_limit
```

- [ ] **Step 4: Add the enforcement check**

In `create_event` (`backend/app/routers/events.py`), immediately after the function signature/`def create_event(...)`: insert as the first statements of the body, before `slug = ...`:

```python
    count = db.query(models.Event.id).filter(
        models.Event.photographer_id == current_user.id
    ).count()
    limit = effective_event_limit(current_user)
    if count >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Event limit reached ({count}/{limit}). Contact your admin to raise it.",
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_limits.py -v`
Expected: PASS (all limits tests).

- [ ] **Step 6: Run the full suite (no regressions)**

Run: `..\.venv\Scripts\python.exe -m pytest -q`
Expected: all tests pass (previous 35 + new).

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/events.py backend/tests/test_limits.py
git commit -m "feat: block event creation over per-user quota (403)"
```

---

### Task 5: Re-gate admin router, add quota endpoint + usage payload, global analytics/activity

**Files:**
- Modify: `backend/app/schemas/schemas.py:7-17` (UserResponse), `:159-161` (admin schemas)
- Modify: `backend/app/routers/admin.py` (imports, gates, new endpoint, global scope)
- Test: `backend/tests/test_admin_limits.py`

**Interfaces:**
- Consumes: `deps.get_current_admin`, `app.core.limits.effective_event_limit`, `as_admin`/`as_studio` fixtures.
- Produces:
  - `schemas.UserResponse` gains `max_events: Optional[int]`.
  - `schemas.AdminUserResponse` (UserResponse + `event_count: int`, `effective_limit: int`).
  - `schemas.EventLimitUpdate { max_events: Optional[int] }`.
  - `GET /api/admin/users` → `List[AdminUserResponse]`, admin-gated.
  - `PATCH /api/admin/users/{id}/limit` → `AdminUserResponse`, admin-gated, validates `null` or `>= 0`.
  - `PATCH /api/admin/users/{id}/role` → admin-gated, rejects changing an `admin` row (`400`).
  - `GET /api/admin/activity`, `GET /api/admin/analytics` → global across all events, admin-gated.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_admin_limits.py`:

```python
from tests.conftest import make_user
from app.database import SessionLocal
from app.models import models


def _seed_studio_with_events(email, uid, n_events):
    studio = make_user(role="studio", email=email, firebase_uid=uid)
    db = SessionLocal()
    try:
        for i in range(n_events):
            db.add(models.Event(title=f"E{i}", event_slug=f"{uid}-{i}", photographer_id=studio.id))
        db.commit()
    finally:
        db.close()
    return studio


def test_admin_users_returns_usage(client, as_admin):
    s = _seed_studio_with_events("s1@test.ai", "s1-uid", 1)
    r = client.get("/api/admin/users")
    assert r.status_code == 200, r.text
    row = next(u for u in r.json() if u["id"] == s.id)
    assert row["event_count"] == 1
    assert row["effective_limit"] == 2
    assert row["max_events"] is None


def test_admin_set_limit(client, as_admin):
    s = _seed_studio_with_events("s2@test.ai", "s2-uid", 0)
    r = client.patch(f"/api/admin/users/{s.id}/limit", json={"max_events": 7})
    assert r.status_code == 200, r.text
    assert r.json()["max_events"] == 7
    assert r.json()["effective_limit"] == 7


def test_admin_set_limit_rejects_negative(client, as_admin):
    s = _seed_studio_with_events("s3@test.ai", "s3-uid", 0)
    r = client.patch(f"/api/admin/users/{s.id}/limit", json={"max_events": -1})
    assert r.status_code == 400


def test_admin_endpoints_reject_studio(client, as_studio):
    r = client.get("/api/admin/users")
    assert r.status_code == 403


def test_admin_cannot_demote_admin_row(client, as_admin):
    # as_admin user is itself an admin; trying to change its role must 400.
    db = SessionLocal()
    try:
        admin = db.query(models.User).filter(models.User.role == "admin").first()
        admin_id = admin.id
    finally:
        db.close()
    r = client.patch(f"/api/admin/users/{admin_id}/role", json={"role": "guest"})
    assert r.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_admin_limits.py -v`
Expected: FAIL — `/limit` route is 404/405; `/users` rows lack `event_count`; studio gets 200 not 403 (still studio-gated).

- [ ] **Step 3: Extend schemas**

In `backend/app/schemas/schemas.py`, change `UserResponse` (lines 7-17) to add `max_events`:

```python
class UserResponse(BaseModel):
    id: int
    firebase_uid: Optional[str] = None
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: str
    max_events: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True
```

Then, in the Admin Schemas section (after `class RoleUpdate`, around line 161), add:

```python
class AdminUserResponse(UserResponse):
    event_count: int = 0
    effective_limit: int = 0


class EventLimitUpdate(BaseModel):
    max_events: Optional[int] = None
```

- [ ] **Step 4: Rewrite the admin router head + user endpoints**

In `backend/app/routers/admin.py`, change the import on line 19 from:

```python
from .deps import get_current_studio
```

to:

```python
from .deps import get_current_admin
from ..core.limits import effective_event_limit
```

Replace `list_users` (lines 26-31) with:

```python
@router.get("/users", response_model=List[schemas.AdminUserResponse])
def list_users(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    users = db.query(models.User).order_by(models.User.created_at.desc()).all()
    counts = dict(
        db.query(models.Event.photographer_id, func.count())
        .group_by(models.Event.photographer_id)
        .all()
    )
    out = []
    for u in users:
        ec = counts.get(u.id, 0)
        out.append(schemas.AdminUserResponse(
            id=u.id, firebase_uid=u.firebase_uid, name=u.name, email=u.email,
            phone=u.phone, role=u.role, max_events=u.max_events, created_at=u.created_at,
            event_count=ec, effective_limit=effective_event_limit(u),
        ))
    return out
```

Replace `set_user_role` (lines 34-51) gate + add admin-guard:

```python
@router.patch("/users/{user_id}/role", response_model=schemas.UserResponse)
def set_user_role(
    user_id: int,
    body: schemas.RoleUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    if body.role not in ("studio", "guest"):
        raise HTTPException(status_code=400, detail="role must be 'studio' or 'guest'")
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot change the admin's role")
    target.role = body.role
    db.commit()
    db.refresh(target)
    return target
```

Add the new quota endpoint immediately after `set_user_role`:

```python
@router.patch("/users/{user_id}/limit", response_model=schemas.AdminUserResponse)
def set_user_limit(
    user_id: int,
    body: schemas.EventLimitUpdate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    if body.max_events is not None and body.max_events < 0:
        raise HTTPException(status_code=400, detail="max_events must be null or >= 0")
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.max_events = body.max_events
    db.commit()
    db.refresh(target)
    ec = db.query(models.Event.id).filter(models.Event.photographer_id == target.id).count()
    return schemas.AdminUserResponse(
        id=target.id, firebase_uid=target.firebase_uid, name=target.name, email=target.email,
        phone=target.phone, role=target.role, max_events=target.max_events,
        created_at=target.created_at, event_count=ec, effective_limit=effective_event_limit(target),
    )
```

- [ ] **Step 5: Make activity + analytics admin-gated and global**

In `backend/app/routers/admin.py`, in `list_activity` (lines 56-79): change the dependency `current_user: models.User = Depends(get_current_studio)` to `_admin: models.User = Depends(get_current_admin)`, and replace the owned-id filtering with global scope. Replace the body from line 64 (`# Only events owned...`) through the `q = db.query(...)` setup with:

```python
    q = db.query(models.ActivityLog)
    if event_id is not None:
        q = q.filter(models.ActivityLog.event_id == event_id)
    if action:
        q = q.filter(models.ActivityLog.action == action)
    limit = max(1, min(limit, 500))
    return q.order_by(models.ActivityLog.created_at.desc()).limit(limit).all()
```

In `analytics` (lines 84-95): change `current_user: models.User = Depends(get_current_studio)` to `_admin: models.User = Depends(get_current_admin)`, and change the events query (lines 89-94) to global:

```python
    events = (
        db.query(models.Event)
        .order_by(models.Event.created_at.desc())
        .all()
    )
```

(Leave the rest of `analytics` unchanged — it already derives everything from `events`.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_admin_limits.py -v`
Expected: PASS (5 tests).

- [ ] **Step 7: Run the full suite — fix the now-admin-gated existing admin tests**

Run: `..\.venv\Scripts\python.exe -m pytest -q`
Expected: existing `tests/test_admin.py` may fail because it used `as_studio`. For each failing admin test in `tests/test_admin.py`, change the fixture argument from `as_studio` to `as_admin`. Re-run until green. (If a test asserts owned-only scoping, update it to expect global scope.)

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/schemas.py backend/app/routers/admin.py backend/tests/test_admin_limits.py backend/tests/test_admin.py
git commit -m "feat: admin-gate admin router, add quota endpoint + usage, global analytics"
```

---

### Task 6: One-time `make_admin` bootstrap script (for the existing DB)

**Files:**
- Create: `backend/scripts/make_admin.py`
- Test: `backend/tests/test_make_admin.py`

**Interfaces:**
- Produces: `scripts.make_admin.promote_to_admin(db, email) -> models.User` (sets role to `admin`); CLI entrypoint `python scripts/make_admin.py <email>`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_make_admin.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from scripts.make_admin import promote_to_admin
from tests.conftest import make_user


def test_promote_to_admin_sets_role():
    make_user(role="studio", email="promote@test.ai", firebase_uid="promote-uid")
    db = SessionLocal()
    try:
        u = promote_to_admin(db, "promote@test.ai")
        assert u.role == "admin"
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_make_admin.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts'`.

- [ ] **Step 3: Create the script**

Create `backend/scripts/__init__.py` (empty file) and `backend/scripts/make_admin.py`:

```python
"""Promote an existing user to the single admin role, by email.

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_make_admin.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/__init__.py backend/scripts/make_admin.py backend/tests/test_make_admin.py
git commit -m "feat: add make_admin bootstrap script for existing DB"
```

---

### Task 7: Frontend `useMe()` role hook

**Files:**
- Create: `frontend/lib/hooks/me.ts`

**Interfaces:**
- Produces: `useMe()` → TanStack Query result of `MeUser { id, role, email, name, max_events }`; enabled only when a Firebase user exists.

- [ ] **Step 1: Create the hook**

Create `frontend/lib/hooks/me.ts`:

```ts
'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

export interface MeUser {
  id: number;
  role: 'admin' | 'studio' | 'guest';
  email: string | null;
  name: string | null;
  max_events: number | null;
}

export function useMe() {
  const { user } = useAuth();
  return useQuery<MeUser>({
    queryKey: ['me', user?.uid],
    enabled: !!user,
    queryFn: async () => (await api.get('/auth/me')).data,
  });
}
```

- [ ] **Step 2: Typecheck**

Run (from `frontend/`): `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/hooks/me.ts
git commit -m "feat: add useMe role hook"
```

---

### Task 8: Split `/admin` into its own role-gated route group

**Files:**
- Create: `frontend/app/(admin)/layout.tsx`
- Create: `frontend/app/(admin)/admin/page.tsx` (moved + extended from `(dashboard)/admin/page.tsx`)
- Delete: `frontend/app/(dashboard)/admin/page.tsx`
- Modify: `frontend/app/(dashboard)/layout.tsx` (remove Admin link, add studio role guard)

**Interfaces:**
- Consumes: `useMe()` from Task 7.
- Produces: `/admin` rendered only for `role === 'admin'`; studio area redirects admins to `/admin` and guests to `/login`.

- [ ] **Step 1: Create the admin layout (guard)**

Create `frontend/app/(admin)/layout.tsx`:

```tsx
'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import Link from 'next/link';
import { ShieldCheck, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth-context';
import { useMe } from '@/lib/hooks/me';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, loading, signOut } = useAuth();
  const { data: me, isLoading } = useMe();

  useEffect(() => {
    if (!loading && !user) { router.push('/login'); return; }
    if (me && me.role !== 'admin') {
      router.push(me.role === 'studio' ? '/dashboard' : '/login');
    }
  }, [loading, user, me, router]);

  if (loading || !user || isLoading || !me || me.role !== 'admin') return null;

  return (
    <div className="flex h-screen bg-slate-50">
      <aside className="w-64 bg-white border-r hidden md:flex flex-col">
        <div className="p-6 border-b flex items-center gap-2">
          <ShieldCheck className="w-7 h-7 text-primary" />
          <span className="text-xl font-bold">WedFind Admin</span>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          <Link href="/admin">
            <Button variant="ghost" className="w-full justify-start gap-2">
              <ShieldCheck className="w-5 h-5" /> <span>Admin</span>
            </Button>
          </Link>
        </nav>
        <div className="p-4 border-t">
          <Button variant="ghost"
            className="w-full justify-start gap-2 text-red-500 hover:text-red-600 hover:bg-red-50"
            onClick={async () => { await signOut(); router.push('/login'); }}>
            <LogOut className="w-5 h-5" /> <span>Logout</span>
          </Button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto p-6 md:p-8">{children}</main>
    </div>
  );
}
```

- [ ] **Step 2: Move + extend the admin page**

Create `frontend/app/(admin)/admin/page.tsx` by copying the current `frontend/app/(dashboard)/admin/page.tsx` verbatim, then apply the two changes below.

Change the `AdminUser` interface to add quota fields:

```tsx
interface AdminUser {
  id: number;
  email: string | null;
  name: string | null;
  phone: string | null;
  role: string;
  max_events: number | null;
  event_count: number;
  effective_limit: number;
  created_at: string;
}
```

Replace the whole `UsersTab` function with this quota-aware version:

```tsx
function UsersTab() {
  const qc = useQueryClient();
  const { data: users, isLoading } = useQuery<AdminUser[]>({
    queryKey: ['admin-users'],
    queryFn: async () => (await api.get('/admin/users')).data,
  });
  const setRole = useMutation({
    mutationFn: async ({ id, role }: { id: number; role: string }) =>
      (await api.patch(`/admin/users/${id}/role`, { role })).data,
    onSuccess: () => { toast.success('Role updated'); qc.invalidateQueries({ queryKey: ['admin-users'] }); },
    onError: (e: unknown) =>
      toast.error((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed'),
  });
  const setLimit = useMutation({
    mutationFn: async ({ id, max_events }: { id: number; max_events: number | null }) =>
      (await api.patch(`/admin/users/${id}/limit`, { max_events })).data,
    onSuccess: () => { toast.success('Limit updated'); qc.invalidateQueries({ queryKey: ['admin-users'] }); },
    onError: (e: unknown) =>
      toast.error((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed'),
  });

  if (isLoading) return <Loader2 className="w-6 h-6 animate-spin" />;
  return (
    <Card>
      <CardContent className="pt-6 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b">
              <th className="py-2 pr-4">User</th>
              <th className="py-2 px-2">Role</th>
              <th className="py-2 px-2">Usage</th>
              <th className="py-2 px-2">Event limit</th>
              <th className="py-2 px-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {users?.map((u) => (
              <tr key={u.id} className="border-b last:border-0">
                <td className="py-2 pr-4">
                  <p className="font-medium">{u.name || u.email || u.phone || `#${u.id}`}</p>
                  <p className="text-xs text-slate-400">{u.email || u.phone}</p>
                </td>
                <td className="py-2 px-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    u.role === 'admin' ? 'bg-amber-100 text-amber-700'
                    : u.role === 'studio' ? 'bg-primary/10 text-primary'
                    : 'bg-slate-100 text-slate-600'}`}>{u.role}</span>
                </td>
                <td className="py-2 px-2 whitespace-nowrap">{u.event_count} / {u.effective_limit}</td>
                <td className="py-2 px-2">
                  {u.role === 'admin' ? <span className="text-xs text-slate-400">—</span> : (
                    <LimitEditor
                      value={u.max_events}
                      onSave={(v) => setLimit.mutate({ id: u.id, max_events: v })}
                      disabled={setLimit.isPending}
                    />
                  )}
                </td>
                <td className="py-2 px-2">
                  {u.role === 'admin' ? <span className="text-xs text-slate-400">—</span>
                   : u.role === 'studio' ? (
                    <Button size="sm" variant="outline" onClick={() => setRole.mutate({ id: u.id, role: 'guest' })} disabled={setRole.isPending}>Make guest</Button>
                  ) : (
                    <Button size="sm" onClick={() => setRole.mutate({ id: u.id, role: 'studio' })} disabled={setRole.isPending}>Make studio</Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function LimitEditor({ value, onSave, disabled }: { value: number | null; onSave: (v: number | null) => void; disabled: boolean }) {
  const [v, setV] = useState<string>(value === null ? '' : String(value));
  return (
    <div className="flex items-center gap-2">
      <input
        type="number" min={0} value={v} placeholder="default"
        onChange={(e) => setV(e.target.value)}
        className="h-8 w-20 rounded-md border border-input px-2 text-sm"
      />
      <Button size="sm" variant="outline" disabled={disabled}
        onClick={() => onSave(v.trim() === '' ? null : Math.max(0, parseInt(v, 10) || 0))}>
        Save
      </Button>
    </div>
  );
}
```

Then delete the old page: `git rm frontend/app/(dashboard)/admin/page.tsx`.

- [ ] **Step 3: Remove the Admin link + add studio guard in the dashboard layout**

In `frontend/app/(dashboard)/layout.tsx`:

Remove the Admin nav `<Link href="/admin">…</Link>` block (lines 56-61).

Add the role hook + guard. Add the import near the top:

```tsx
import { useMe } from '@/lib/hooks/me';
```

Replace the `useEffect` redirect (lines 18-22) with a role-aware one, and use `me` in the guard:

```tsx
  const { data: me, isLoading: meLoading } = useMe();

  useEffect(() => {
    if (!loading && !user) { router.push('/login'); return; }
    if (me && me.role !== 'studio') {
      router.push(me.role === 'admin' ? '/admin' : '/login');
    }
  }, [loading, user, me, router]);
```

And change the early-return guard (line 29) to:

```tsx
  if (loading || !user || meLoading || !me || me.role !== 'studio') {
    return null;
  }
```

- [ ] **Step 4: Typecheck + lint**

Run (from `frontend/`): `npx tsc --noEmit && npx eslint app/(admin) app/(dashboard) lib/hooks`
Expected: no errors.

- [ ] **Step 5: Manual verification**

Start frontend (`npm run dev`). With backend reachable (or `/auth/me` mocked): an admin user lands on `/admin` and sees the user table with Usage + Event-limit columns; visiting `/dashboard` as admin redirects to `/admin`; a studio user on `/admin` redirects to `/dashboard`. (If the DB is down, this is testable once it's back — note and proceed.)

- [ ] **Step 6: Commit**

```bash
git add frontend/app/(admin) frontend/app/(dashboard)/layout.tsx
git rm frontend/app/(dashboard)/admin/page.tsx
git commit -m "feat: separate admin route group with role guard + quota editor"
```

---

### Task 9: Redirect by role at login

**Files:**
- Modify: `frontend/app/(auth)/login/page.tsx:28-75`

**Interfaces:**
- Consumes: `api` (`/auth/me`).
- Produces: after sign-in, route `admin → /admin`, `studio → /dashboard`, `guest → /pending`.

- [ ] **Step 1: Add a role-routing helper + use it**

In `frontend/app/(auth)/login/page.tsx`, add an import:

```tsx
import api from '@/lib/api';
```

Add this helper inside the component (after `const [mode, ...]`):

```tsx
  async function routeByRole() {
    try {
      const me = (await api.get('/auth/me')).data as { role: string };
      if (me.role === 'admin') router.push('/admin');
      else if (me.role === 'studio') router.push('/dashboard');
      else router.push('/pending');
    } catch {
      router.push('/dashboard');
    }
  }
```

In `onSubmit`, replace `router.push('/dashboard');` (line 56) with `await routeByRole();`.
In `onGoogle`, replace `router.push('/dashboard');` (line 69) with `await routeByRole();`.

- [ ] **Step 2: Typecheck**

Run (from `frontend/`): `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/(auth)/login/page.tsx
git commit -m "feat: redirect by role after login"
```

---

### Task 10: Guest "pending access" screen

**Files:**
- Create: `frontend/app/pending/page.tsx`

**Interfaces:**
- Produces: `/pending` — static screen telling a guest-role user to contact the admin, with a logout button.

- [ ] **Step 1: Create the page**

Create `frontend/app/pending/page.tsx`:

```tsx
'use client';

import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth-context';
import { Clock } from 'lucide-react';

export default function PendingPage() {
  const router = useRouter();
  const { signOut } = useAuth();
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <div className="max-w-md text-center space-y-4">
        <Clock className="mx-auto h-12 w-12 text-slate-400" />
        <h1 className="text-2xl font-bold">Access pending</h1>
        <p className="text-slate-500">
          Your account doesn&apos;t have studio access yet. Please contact your
          admin to be granted access.
        </p>
        <Button variant="outline" onClick={async () => { await signOut(); router.push('/login'); }}>
          Sign out
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + lint**

Run (from `frontend/`): `npx tsc --noEmit && npx eslint app/pending`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/pending/page.tsx
git commit -m "feat: add guest pending-access screen"
```

---

### Task 11: Surface the quota 403 as a toast on event create

**Files:**
- Modify: `frontend/app/(dashboard)/dashboard/page.tsx:49-61`

**Interfaces:**
- Consumes: `POST /api/events/` 403 detail.
- Produces: create-event failure shows the backend detail message via `sonner`.

- [ ] **Step 1: Replace the create handler's catch**

In `frontend/app/(dashboard)/dashboard/page.tsx`, change `onSubmit` (lines 49-61) so the catch surfaces the backend detail:

```tsx
  async function onSubmit(values: z.infer<typeof eventSchema>) {
    try {
      await api.post('/events/', {
        ...values,
        event_date: new Date(values.event_date).toISOString(),
      });
      toast.success('Event created successfully');
      setOpen(false);
      refetch();
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: string } } })
        .response?.data?.detail;
      toast.error(detail || 'Failed to create event');
    }
  }
```

- [ ] **Step 2: Typecheck**

Run (from `frontend/`): `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Manual verification**

As a studio at its quota (2 events), clicking Create Event shows a toast reading `Event limit reached (2/2). Contact your admin to raise it.`

- [ ] **Step 4: Commit**

```bash
git add frontend/app/(dashboard)/dashboard/page.tsx
git commit -m "feat: show quota-exceeded message on event create"
```

---

### Task 12: Config + docs wrap-up

**Files:**
- Modify: `backend/.env.example`
- Modify: `README.md` (roles + quota note)

**Interfaces:** none (docs/config only).

- [ ] **Step 1: Document the env var**

In `backend/.env.example`, add a line under the existing config block:

```
# Default events a new studio may create (admin can override per user)
DEFAULT_EVENT_LIMIT=2
```

- [ ] **Step 2: Note roles in the README**

In `README.md`, in the Security & Privacy section's bootstrap bullet, replace "First-user-becomes-studio bootstrap" with:

```
- First-user-becomes-**admin** bootstrap (single system admin); everyone else defaults to `guest`. The admin promotes users to `studio` and sets each studio's event quota (`DEFAULT_EVENT_LIMIT`, default 2). Existing DBs: run `python scripts/make_admin.py <email>` once to designate the admin.
```

- [ ] **Step 3: Run the full backend suite once more**

Run (from `backend/`): `..\.venv\Scripts\python.exe -m pytest -q`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add backend/.env.example README.md
git commit -m "docs: document admin role + DEFAULT_EVENT_LIMIT"
```

---

## Deployment (delivered as guidance after implementation — not a build task)

Once merged and the DB is reachable, host so it survives laptop shutdown:

1. **Frontend → Vercel.** Import the repo, root `frontend/`, set `NEXT_PUBLIC_*` env vars (Firebase web config + `NEXT_PUBLIC_API_URL=https://api.<domain>/api`). Add subdomain `app.<domain>` (CNAME → Vercel). HTTPS is automatic (needed for the selfie camera).
2. **Backend → AWS Lightsail/EC2 in us-east-1** (same VPC as RDS → private DB, no public exposure; pick ≥2GB RAM for InsightFace `buffalo_l`). Run `uvicorn` behind Caddy/Nginx with HTTPS on `api.<domain>` (A record). Set `DATABASE_URL` (private RDS endpoint), `FRONTEND_URL=https://app.<domain>`, AWS + Firebase env vars, `DEFAULT_EVENT_LIMIT`. Run `alembic upgrade head`, then `python scripts/make_admin.py <your-email>`.
3. **Alt backend (faster, RDS stays public):** Railway or Fly.io with a 2GB instance; keep the RDS security-group rule for the host's egress IP.
4. **Desktop agent** stays on the studio's own machine (watches local disk) — not hosted.

---

## Self-Review

- **Spec coverage:** roles (T3), max_events column+migration (T1), default+helper (T2), enforcement (T4), admin re-gate + /limit + usage + global analytics (T5), bootstrap script for existing DB (T6), useMe (T7), separate route groups + guards + quota editor (T8), login redirect (T9), pending screen (T10), create toast (T11), env+README+deploy guide (T12). All spec sections mapped.
- **Placeholder scan:** no TBD/“add error handling”; every code step shows full code.
- **Type consistency:** `AdminUserResponse` fields (`event_count`, `effective_limit`, `max_events`) match between schema (T5), frontend `AdminUser` interface (T8) and `MeUser` (T7). `effective_event_limit` named identically in T2/T4/T5. Endpoint paths (`/admin/users/{id}/limit`) consistent across T5 and T8.
