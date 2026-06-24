# Admin/User Role Separation + Quotas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hard role separation — a single `admin` controls users/quotas/tokens/folder-watch/privacy/audit; `user` (studio photographer) only manages own events/photos; `pending` (invite-only) has no access. No admin UI or API is reachable by non-admins.

**Architecture:** Three role values (`admin`/`user`/`pending`) on `User` (constrained string, default `pending`, no auto-admin). `require_admin`/`require_user` dependencies gate every route. Per-user event + storage quotas (admin-settable). Frontend splits into `(admin)` and `(dashboard)` route groups, each role-guarded; non-admin nav never renders admin items.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, pytest (SQLite + mocks); Next.js 16 (webpack dev), React 19, TanStack Query, Axios, sonner.

## Global Constraints

- Role values exactly `admin`, `user`, `pending`. New signups default to `pending`. Admin minted only by `scripts/make_admin.py` or by an existing admin via PATCH/promote. No count-based auto-admin.
- Admin-required 403 detail exactly: `Admin access required`. Studio-required 403 detail exactly: `Studio access required`.
- Event over-quota 403 detail exactly: `Event limit reached ({count}/{limit}). Contact your admin to raise it.`
- Storage over-quota 403 detail exactly: `Storage limit reached. Contact your admin to raise it.`
- `DEFAULT_EVENT_LIMIT=2`, `DEFAULT_STORAGE_LIMIT_MB=2048` (env-overridable). `NULL` column = use default.
- Schema via Alembic only. Current head: `d3e4f5a6b7c8`. New migration: `e4f5a6b7c8d9`.
- Backend tests: `..\.venv\Scripts\python.exe -m pytest` from `backend/` (venv launchers broken after drive move — always `python -m`).
- Frontend: no test runner; verify with `npx tsc --noEmit` + `npx eslint` + stated manual check.
- Non-admin nav items must NOT render (not CSS-hidden). Authorization is enforced server-side regardless of UI.

---

### Task 1: Model + migration (roles, quotas, photo size, data remap)

**Files:**
- Modify: `backend/app/models/models.py` (User role default + max_events + storage_limit_mb; Photo size_bytes)
- Create: `backend/alembic/versions/e4f5a6b7c8d9_roles_quotas.py`
- Test: `backend/tests/test_limits.py`

**Interfaces:**
- Produces: `User.role` (default `"pending"`), `User.max_events: Optional[int]`, `User.storage_limit_mb: Optional[int]`, `Photo.size_bytes: Optional[int]`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_limits.py`:

```python
from tests.conftest import make_user


def test_new_user_quota_fields_default_none():
    u = make_user(role="user", email="limit1@test.ai", firebase_uid="limit-uid-1")
    assert u.max_events is None
    assert u.storage_limit_mb is None
```

- [ ] **Step 2: Run test — expect fail**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_limits.py -v`
Expected: FAIL — `AttributeError: 'User' object has no attribute 'max_events'`.

- [ ] **Step 3: Edit the models**

In `backend/app/models/models.py`, replace the User `role` line (line 22) and add fields:

```python
    role = Column(String, nullable=False, default="pending")  # admin | user | pending
    max_events = Column(Integer, nullable=True)        # null = DEFAULT_EVENT_LIMIT
    storage_limit_mb = Column(Integer, nullable=True)  # null = DEFAULT_STORAGE_LIMIT_MB
```

In `class Photo`, add after `uploaded_at` (line 57):

```python
    size_bytes = Column(Integer, nullable=True)  # bytes stored, for storage-quota accounting
```

- [ ] **Step 4: Run test — expect pass**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_limits.py -v`
Expected: PASS.

- [ ] **Step 5: Create the migration**

Create `backend/alembic/versions/e4f5a6b7c8d9_roles_quotas.py`:

```python
"""roles + quotas + photo size, with role data remap

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
    op.add_column('users', sa.Column('storage_limit_mb', sa.Integer(), nullable=True))
    op.add_column('photos', sa.Column('size_bytes', sa.Integer(), nullable=True))

    conn = op.get_bind()
    # Deterministic remap: lowest-id user -> admin; old 'studio' -> 'user'; old 'guest' -> 'pending'.
    row = conn.execute(sa.text("SELECT id FROM users ORDER BY id ASC LIMIT 1")).fetchone()
    conn.execute(sa.text("UPDATE users SET role='user' WHERE role='studio'"))
    conn.execute(sa.text("UPDATE users SET role='pending' WHERE role='guest'"))
    if row is not None:
        conn.execute(sa.text("UPDATE users SET role='admin' WHERE id=:i"), {"i": row[0]})

    # CHECK constraint (Postgres; SQLite ignores named CHECK add via batch — guarded).
    if conn.dialect.name == "postgresql":
        op.create_check_constraint(
            "ck_users_role", "users", "role IN ('admin','user','pending')"
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column('photos', 'size_bytes')
    op.drop_column('users', 'storage_limit_mb')
    op.drop_column('users', 'max_events')
```

- [ ] **Step 6: Verify chain**

Run: `..\.venv\Scripts\python.exe -m alembic history`
Expected: ends `... d3e4f5a6b7c8 -> e4f5a6b7c8d9 (head), roles + quotas ...`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/models.py backend/alembic/versions/e4f5a6b7c8d9_roles_quotas.py backend/tests/test_limits.py
git commit -m "feat: roles+quotas columns, photo size, role-remap migration"
```

---

### Task 2: Quota helpers (`app/core/limits.py`)

**Files:**
- Create: `backend/app/core/limits.py`
- Test: `backend/tests/test_limits.py` (append)

**Interfaces:**
- Produces: `DEFAULT_EVENT_LIMIT:int`, `DEFAULT_STORAGE_LIMIT_MB:int`, `effective_event_limit(user)->int`, `effective_storage_limit_mb(user)->int`, `user_storage_used_bytes(db, user)->int`.

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_limits.py`:

```python
from app.core import limits
from app.models import models


def test_default_event_limit_is_two():
    assert limits.DEFAULT_EVENT_LIMIT == 2


def test_default_storage_limit_is_2048():
    assert limits.DEFAULT_STORAGE_LIMIT_MB == 2048


def test_effective_event_limit():
    assert limits.effective_event_limit(models.User(max_events=None)) == 2
    assert limits.effective_event_limit(models.User(max_events=9)) == 9


def test_effective_storage_limit():
    assert limits.effective_storage_limit_mb(models.User(storage_limit_mb=None)) == 2048
    assert limits.effective_storage_limit_mb(models.User(storage_limit_mb=500)) == 500
```

- [ ] **Step 2: Run — expect fail**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_limits.py -k "limit" -v`
Expected: FAIL — `ModuleNotFoundError: app.core.limits`.

- [ ] **Step 3: Create the helper**

Create `backend/app/core/limits.py`:

```python
"""Per-user event + storage quota helpers."""
import os

from sqlalchemy import func

from ..models import models

DEFAULT_EVENT_LIMIT = int(os.getenv("DEFAULT_EVENT_LIMIT", "2"))
DEFAULT_STORAGE_LIMIT_MB = int(os.getenv("DEFAULT_STORAGE_LIMIT_MB", "2048"))


def effective_event_limit(user) -> int:
    if getattr(user, "max_events", None) is not None:
        return user.max_events
    return DEFAULT_EVENT_LIMIT


def effective_storage_limit_mb(user) -> int:
    if getattr(user, "storage_limit_mb", None) is not None:
        return user.storage_limit_mb
    return DEFAULT_STORAGE_LIMIT_MB


def user_storage_used_bytes(db, user) -> int:
    """Sum of stored photo bytes across all events owned by the user."""
    total = (
        db.query(func.coalesce(func.sum(models.Photo.size_bytes), 0))
        .join(models.Event, models.Photo.event_id == models.Event.id)
        .filter(models.Event.photographer_id == user.id)
        .scalar()
    )
    return int(total or 0)
```

- [ ] **Step 4: Run — expect pass**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_limits.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/limits.py backend/tests/test_limits.py
git commit -m "feat: event + storage quota helpers"
```

---

### Task 3: `pending` bootstrap + `require_admin`/`require_user` + conftest fixtures

**Files:**
- Modify: `backend/app/routers/deps.py:35-49` (bootstrap), append two dependencies; keep `get_current_studio` as an alias of `require_user` for back-compat during migration
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_roles.py`

**Interfaces:**
- Produces:
  - new users → `role="pending"`.
  - `deps.require_admin(user)->User` (403 `Admin access required` unless admin).
  - `deps.require_user(user)->User` (403 `Studio access required` unless `role=="user"`).
  - `deps.get_current_studio = require_user` (alias).
  - conftest fixtures `as_admin`, `as_user`, `as_pending`.

- [ ] **Step 1: Update conftest fixtures**

In `backend/tests/conftest.py`, replace the `as_studio` and `as_guest` fixtures (lines 63-94) with:

```python
def _override_current(user):
    def _current():
        db = _db_session()
        try:
            return db.query(models.User).filter(models.User.id == user.id).first()
        finally:
            db.close()
    return _current


@pytest.fixture
def as_admin():
    user = make_user(role="admin", email="admin@test.ai", firebase_uid="admin-uid")
    cur = _override_current(user)
    app_main.app.dependency_overrides[deps.get_current_user] = cur
    app_main.app.dependency_overrides[deps.require_admin] = cur
    app_main.app.dependency_overrides[deps.require_user] = cur  # admin tests that hit user routes
    return user


@pytest.fixture
def as_user():
    user = make_user(role="user", email="user@test.ai", firebase_uid="user-uid")
    cur = _override_current(user)
    app_main.app.dependency_overrides[deps.get_current_user] = cur
    app_main.app.dependency_overrides[deps.require_user] = cur
    return user


@pytest.fixture
def as_pending():
    user = make_user(role="pending", email="pending@test.ai", firebase_uid="pending-uid")
    cur = _override_current(user)
    app_main.app.dependency_overrides[deps.get_current_user] = cur
    return user
```

Also change the default in `make_user` (line 51) from `role="studio"` to `role="user"`.

- [ ] **Step 2: Write failing tests**

Create `backend/tests/test_roles.py`:

```python
import pytest
from fastapi import HTTPException
from app.database import SessionLocal
from app.routers import deps
from tests.conftest import make_user


def test_new_user_is_pending():
    db = SessionLocal()
    try:
        u = deps._find_or_create_user({"uid": "x1", "email": "x1@test.ai"}, db)
        assert u.role == "pending"
    finally:
        db.close()


def test_no_auto_admin_even_for_first_user():
    db = SessionLocal()
    try:
        first = deps._find_or_create_user({"uid": "f1", "email": "f1@test.ai"}, db)
        assert first.role == "pending"
    finally:
        db.close()


def test_require_admin_allows_admin():
    a = make_user(role="admin", email="a@test.ai", firebase_uid="a-uid")
    assert deps.require_admin(a) is a


def test_require_admin_rejects_user():
    u = make_user(role="user", email="u@test.ai", firebase_uid="u-uid")
    with pytest.raises(HTTPException) as e:
        deps.require_admin(u)
    assert e.value.status_code == 403
    assert e.value.detail == "Admin access required"


def test_require_user_rejects_pending():
    p = make_user(role="pending", email="p@test.ai", firebase_uid="p-uid")
    with pytest.raises(HTTPException) as e:
        deps.require_user(p)
    assert e.value.status_code == 403
    assert e.value.detail == "Studio access required"
```

- [ ] **Step 3: Run — expect fail**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_roles.py -v`
Expected: FAIL — `require_admin` missing; bootstrap returns `studio`.

- [ ] **Step 4: Edit deps.py bootstrap**

In `backend/app/routers/deps.py`, replace lines 35-44 (the bootstrap block creating the user) with:

```python
    email = decoded.get("email")
    phone = decoded.get("phone_number")
    # Invite-only: every new login starts as 'pending' (no access). An admin
    # grants 'user'. Admin itself is minted only by scripts/make_admin.py.
    user = models.User(
        firebase_uid=uid,
        email=email,
        phone=phone,
        name=decoded.get("name") or email or phone or "User",
        role="pending",
    )
```

- [ ] **Step 5: Replace `get_current_studio` + add `require_admin`**

In `backend/app/routers/deps.py`, replace the `get_current_studio` function (lines 83-87) with:

```python
def require_user(current_user: models.User = Depends(get_current_user)) -> models.User:
    """Require a studio user account (event/photo endpoints)."""
    if current_user.role != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Studio access required")
    return current_user


def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    """Require the admin account (all management endpoints)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


# Back-compat alias (callers migrated to require_user/require_admin in this change).
get_current_studio = require_user
```

- [ ] **Step 6: Run — expect pass**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_roles.py -v`
Expected: PASS (5 tests).

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/deps.py backend/tests/conftest.py backend/tests/test_roles.py
git commit -m "feat: pending bootstrap + require_admin/require_user dependencies"
```

---

### Task 4: Re-gate routers (admin vs user)

**Files:**
- Modify: `backend/app/routers/auth.py` (promote + tokens → require_admin)
- Modify: `backend/app/routers/events.py` (watch-folders + rescan + privacy/retention/consents → require_admin; events CRUD + photos stay require_user)
- Modify: `backend/app/routers/photos.py` (require_user)
- Modify: existing tests that used `as_studio` → `as_user` / `as_admin` as appropriate
- Test: `backend/tests/test_gating.py`

**Interfaces:**
- Consumes: `deps.require_admin`, `deps.require_user`.
- Produces: gating per the spec's endpoint table.

- [ ] **Step 1: Write failing gating tests**

Create `backend/tests/test_gating.py`:

```python
def test_user_cannot_list_tokens(client, as_user):
    assert client.get("/api/auth/tokens").status_code == 403


def test_admin_can_list_tokens(client, as_admin):
    assert client.get("/api/auth/tokens").status_code == 200


def test_user_cannot_start_watch_folder(client, as_user):
    # event need not exist; gate runs before handler body
    r = client.post("/api/events/1/watch-folders", json={"folder_path": "/x"})
    assert r.status_code in (403,)


def test_pending_cannot_create_event(client, as_pending):
    r = client.post("/api/events/", json={"title": "E", "description": "d", "event_date": "2026-07-01T00:00:00"})
    assert r.status_code == 403
    assert r.json()["detail"] == "Studio access required"
```

- [ ] **Step 2: Run — expect fail**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_gating.py -v`
Expected: FAIL — tokens/watch currently allow `user` (was studio==user alias), pending create returns wrong gate.

- [ ] **Step 3: Re-gate `auth.py`**

In `backend/app/routers/auth.py`, change the import on line 14 to:

```python
from .deps import get_current_user, require_admin, require_user
```

In `promote_user` (line 34) change `_admin: models.User = Depends(get_current_studio)` → `_admin: models.User = Depends(require_admin)`, and restrict allowed roles to `("user", "pending")`:

```python
    if body.role not in ("user", "pending"):
        raise HTTPException(status_code=400, detail="role must be 'user' or 'pending'")
```

In `create_api_token`, `list_api_tokens`, `revoke_api_token` (lines 54, 68, 82) change `Depends(get_current_studio)` → `Depends(require_admin)`.

- [ ] **Step 4: Re-gate `events.py`**

In `backend/app/routers/events.py` change the import (line 7) to:

```python
from .deps import require_admin, require_user
```

For each route, set the dependency:
- `create_event` (63), `list_events` (112), `get_event` (125), `delete_event` (145): `Depends(require_user)`.
- `watch-folders` create/list/delete (200, 229, 245), `rescan` (261), `rescan-all` (276): `Depends(require_admin)`.
- `privacy` (310), `retention` (320), `consents` (337), `consents/export` (352): `Depends(require_admin)`.

(Replace each `current_user: models.User = Depends(get_current_studio)` with the mapped dependency. Where a handler needs the user object, keep the param name `current_user`.)

NOTE: admin-gated event sub-routes still call `_owned_event_or_404(event_id, current_user, ...)` which filters by `photographer_id == current_user.id`. Since the admin owns no events, change those admin-gated handlers to look the event up by id WITHOUT the owner filter. Add a helper in `events.py`:

```python
def _event_or_404(event_id: int, db: Session) -> models.Event:
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
```

In the admin-gated handlers (watch-folders, rescan, privacy, retention, consents, export) replace `_owned_event_or_404(event_id, current_user, db)` with `_event_or_404(event_id, db)`.

- [ ] **Step 5: Re-gate `photos.py`**

In `backend/app/routers/photos.py`, change its auth import to `require_user` and set both routes (`upload/{event_id}` line 16, `event/{event_id}` line 65) to `Depends(require_user)`. (The upload route also accepts `X-API-Key` via `get_current_user` internally — keep that path; the agent token resolves to its owning user which must be role `user`.)

- [ ] **Step 6: Fix existing tests' fixtures**

Run the full suite: `..\.venv\Scripts\python.exe -m pytest -q`. For every failure in `tests/test_events.py`, `tests/test_ingest.py`, `tests/test_tokens.py`, `tests/test_guest.py`, `tests/test_admin.py`: change the fixture argument from `as_studio` to `as_user` (event/photo/guest tests) or `as_admin` (token tests, admin tests, watch-folder tests, privacy tests). Re-run until green.

- [ ] **Step 7: Run gating tests — expect pass**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_gating.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/auth.py backend/app/routers/events.py backend/app/routers/photos.py backend/tests/
git commit -m "feat: re-gate routes to require_admin/require_user"
```

---

### Task 5: Event quota enforcement

**Files:**
- Modify: `backend/app/routers/events.py` (imports + create_event head)
- Test: `backend/tests/test_limits.py` (append)

**Interfaces:**
- Consumes: `effective_event_limit`, `as_user`.
- Produces: `POST /api/events/` 403 over quota.

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_limits.py`:

```python
def _payload(t):
    return {"title": t, "description": "d", "event_date": "2026-07-01T00:00:00"}


def test_event_create_allowed_under_limit(client, as_user):
    assert client.post("/api/events/", json=_payload("E1")).status_code == 200


def test_event_create_blocked_at_limit(client, as_user):
    assert client.post("/api/events/", json=_payload("E1")).status_code == 200
    assert client.post("/api/events/", json=_payload("E2")).status_code == 200
    r = client.post("/api/events/", json=_payload("E3"))
    assert r.status_code == 403
    assert r.json()["detail"] == "Event limit reached (2/2). Contact your admin to raise it."
```

- [ ] **Step 2: Run — expect fail**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_limits.py -k "event_create" -v`
Expected: FAIL — third create returns 200.

- [ ] **Step 3: Add import + check**

In `backend/app/routers/events.py` add after line 16:

```python
from ..core.limits import effective_event_limit
```

As the first statements in `create_event` body (before `slug = ...`):

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

- [ ] **Step 4: Run — expect pass**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_limits.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/events.py backend/tests/test_limits.py
git commit -m "feat: enforce event quota on create"
```

---

### Task 6: Storage quota + `Photo.size_bytes` at ingest

**Files:**
- Modify: `backend/app/services/photo_ingest.py` (set size_bytes; enforce storage before S3)
- Test: `backend/tests/test_storage.py`

**Interfaces:**
- Consumes: `effective_storage_limit_mb`, `user_storage_used_bytes`.
- Produces: ingest sets `Photo.size_bytes = len(data)`; raises `HTTPException(403, "Storage limit reached. Contact your admin to raise it.")` when over quota, BEFORE the S3 upload.

- [ ] **Step 1: Read the ingest signature**

Open `backend/app/services/photo_ingest.py`. Identify `ingest_photo_bytes(...)` — its params include the `db` session, the owning event (or event_id), the raw `data: bytes`, filename, content_type. Confirm where the S3 upload and `Photo(...)` creation happen (around lines 53-77).

- [ ] **Step 2: Write failing tests**

Create `backend/tests/test_storage.py`:

```python
from app.database import SessionLocal
from app.models import models
from app.services import photo_ingest
from tests.conftest import make_user


def _make_event(owner):
    db = SessionLocal()
    try:
        e = models.Event(title="E", event_slug=f"slug-{owner.id}", photographer_id=owner.id)
        db.add(e); db.commit(); db.refresh(e)
        return e.id
    finally:
        db.close()


def test_ingest_records_size_bytes():
    owner = make_user(role="user", email="st1@test.ai", firebase_uid="st1")
    eid = _make_event(owner)
    db = SessionLocal()
    try:
        event = db.query(models.Event).get(eid)
        photo = photo_ingest.ingest_photo_bytes(db, event, b"X" * 1234, "a.jpg", "image/jpeg")
        assert photo is not None
        assert photo.size_bytes == 1234
    finally:
        db.close()


def test_ingest_blocks_over_storage_limit():
    import pytest
    from fastapi import HTTPException
    owner = make_user(role="user", email="st2@test.ai", firebase_uid="st2")
    # 0 MB limit -> any upload exceeds.
    db = SessionLocal()
    try:
        u = db.query(models.User).get(owner.id)
        u.storage_limit_mb = 0
        db.commit()
    finally:
        db.close()
    eid = _make_event(owner)
    db = SessionLocal()
    try:
        event = db.query(models.Event).get(eid)
        with pytest.raises(HTTPException) as e:
            photo_ingest.ingest_photo_bytes(db, event, b"X" * 10, "a.jpg", "image/jpeg")
        assert e.value.status_code == 403
        assert e.value.detail == "Storage limit reached. Contact your admin to raise it."
    finally:
        db.close()
```

(If `ingest_photo_bytes` has a different parameter order/shape, adjust these calls to match what Step 1 found — keep the assertions.)

- [ ] **Step 3: Run — expect fail**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_storage.py -v`
Expected: FAIL — `size_bytes` not set / no storage enforcement.

- [ ] **Step 4: Implement**

In `backend/app/services/photo_ingest.py`, add near the top:

```python
from fastapi import HTTPException
from ..core.limits import effective_storage_limit_mb, user_storage_used_bytes
```

In `ingest_photo_bytes`, BEFORE the S3 upload, add a quota check (the event's owner is `event.photographer_id`):

```python
    owner = db.query(models.User).filter(models.User.id == event.photographer_id).first()
    if owner is not None:
        limit_bytes = effective_storage_limit_mb(owner) * 1024 * 1024
        used = user_storage_used_bytes(db, owner)
        if used + len(data) > limit_bytes:
            raise HTTPException(
                status_code=403,
                detail="Storage limit reached. Contact your admin to raise it.",
            )
```

When constructing the `Photo(...)` row, add `size_bytes=len(data)` to its kwargs.

- [ ] **Step 5: Run — expect pass**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_storage.py -v`
Expected: PASS.

- [ ] **Step 6: Full suite**

Run: `..\.venv\Scripts\python.exe -m pytest -q`
Expected: green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/photo_ingest.py backend/tests/test_storage.py
git commit -m "feat: record photo size + enforce storage quota at ingest"
```

---

### Task 7: Admin schemas + endpoints (users payload, /limit, /storage, /role, global)

**Files:**
- Modify: `backend/app/schemas/schemas.py` (UserResponse + AdminUserResponse + EventLimitUpdate + StorageLimitUpdate + RoleUpdate values)
- Modify: `backend/app/routers/admin.py`
- Test: `backend/tests/test_admin_limits.py`

**Interfaces:**
- Produces:
  - `UserResponse` gains `max_events`, `storage_limit_mb`.
  - `AdminUserResponse` = UserResponse + `event_count, effective_limit, effective_storage_limit_mb, storage_used_mb`.
  - `EventLimitUpdate{max_events:Optional[int]}`, `StorageLimitUpdate{storage_limit_mb:Optional[int]}`.
  - `GET /api/admin/users` (require_admin) → `AdminUserResponse[]`.
  - `PATCH /api/admin/users/{id}/role` (`user`/`pending`, reject admin row).
  - `PATCH /api/admin/users/{id}/limit`, `PATCH /api/admin/users/{id}/storage`.
  - `/activity`, `/analytics` require_admin + global.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_admin_limits.py`:

```python
from tests.conftest import make_user
from app.database import SessionLocal
from app.models import models


def _seed_user_events(email, uid, n):
    u = make_user(role="user", email=email, firebase_uid=uid)
    db = SessionLocal()
    try:
        for i in range(n):
            db.add(models.Event(title=f"E{i}", event_slug=f"{uid}-{i}", photographer_id=u.id))
        db.commit()
    finally:
        db.close()
    return u


def test_users_payload(client, as_admin):
    s = _seed_user_events("s1@test.ai", "s1", 1)
    r = client.get("/api/admin/users")
    assert r.status_code == 200
    row = next(x for x in r.json() if x["id"] == s.id)
    assert row["event_count"] == 1
    assert row["effective_limit"] == 2
    assert row["effective_storage_limit_mb"] == 2048
    assert row["storage_used_mb"] == 0
    assert row["max_events"] is None


def test_set_limit(client, as_admin):
    s = _seed_user_events("s2@test.ai", "s2", 0)
    r = client.patch(f"/api/admin/users/{s.id}/limit", json={"max_events": 7})
    assert r.status_code == 200
    assert r.json()["effective_limit"] == 7


def test_set_storage(client, as_admin):
    s = _seed_user_events("s3@test.ai", "s3", 0)
    r = client.patch(f"/api/admin/users/{s.id}/storage", json={"storage_limit_mb": 500})
    assert r.status_code == 200
    assert r.json()["effective_storage_limit_mb"] == 500


def test_users_rejects_user_role(client, as_user):
    assert client.get("/api/admin/users").status_code == 403


def test_role_change_to_user(client, as_admin):
    s = _seed_user_events("s4@test.ai", "s4", 0)
    db = SessionLocal()
    try:
        db.query(models.User).filter(models.User.id == s.id).update({"role": "pending"})
        db.commit()
    finally:
        db.close()
    r = client.patch(f"/api/admin/users/{s.id}/role", json={"role": "user"})
    assert r.status_code == 200
    assert r.json()["role"] == "user"


def test_cannot_change_admin_role(client, as_admin):
    db = SessionLocal()
    try:
        admin_id = db.query(models.User).filter(models.User.role == "admin").first().id
    finally:
        db.close()
    r = client.patch(f"/api/admin/users/{admin_id}/role", json={"role": "pending"})
    assert r.status_code == 400
```

- [ ] **Step 2: Run — expect fail**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_admin_limits.py -v`
Expected: FAIL — routes missing / studio-gated.

- [ ] **Step 3: Extend schemas**

In `backend/app/schemas/schemas.py`, set `UserResponse` to include quota fields:

```python
class UserResponse(BaseModel):
    id: int
    firebase_uid: Optional[str] = None
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: str
    max_events: Optional[int] = None
    storage_limit_mb: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True
```

Change `RoleUpdate` (line 160) comment + add admin schemas after it:

```python
class RoleUpdate(BaseModel):
    role: str  # "user" or "pending"


class AdminUserResponse(UserResponse):
    event_count: int = 0
    effective_limit: int = 0
    effective_storage_limit_mb: int = 0
    storage_used_mb: int = 0


class EventLimitUpdate(BaseModel):
    max_events: Optional[int] = None


class StorageLimitUpdate(BaseModel):
    storage_limit_mb: Optional[int] = None
```

- [ ] **Step 4: Rewrite admin.py user endpoints + gates**

In `backend/app/routers/admin.py`, change line 19 import to:

```python
from .deps import require_admin
from ..core.limits import (
    effective_event_limit, effective_storage_limit_mb, user_storage_used_bytes,
)
```

Add a builder helper near the top:

```python
def _admin_user(db, u) -> schemas.AdminUserResponse:
    ec = db.query(models.Event.id).filter(models.Event.photographer_id == u.id).count()
    used_mb = user_storage_used_bytes(db, u) // (1024 * 1024)
    return schemas.AdminUserResponse(
        id=u.id, firebase_uid=u.firebase_uid, name=u.name, email=u.email, phone=u.phone,
        role=u.role, max_events=u.max_events, storage_limit_mb=u.storage_limit_mb,
        created_at=u.created_at, event_count=ec,
        effective_limit=effective_event_limit(u),
        effective_storage_limit_mb=effective_storage_limit_mb(u),
        storage_used_mb=used_mb,
    )
```

Replace `list_users` (26-31):

```python
@router.get("/users", response_model=List[schemas.AdminUserResponse])
def list_users(db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    users = db.query(models.User).order_by(models.User.created_at.desc()).all()
    return [_admin_user(db, u) for u in users]
```

Replace `set_user_role` (34-51):

```python
@router.patch("/users/{user_id}/role", response_model=schemas.AdminUserResponse)
def set_user_role(user_id: int, body: schemas.RoleUpdate,
                  db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    if body.role not in ("user", "pending"):
        raise HTTPException(status_code=400, detail="role must be 'user' or 'pending'")
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot change the admin's role")
    target.role = body.role
    db.commit(); db.refresh(target)
    return _admin_user(db, target)
```

Add the two quota endpoints after it:

```python
@router.patch("/users/{user_id}/limit", response_model=schemas.AdminUserResponse)
def set_user_limit(user_id: int, body: schemas.EventLimitUpdate,
                   db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    if body.max_events is not None and body.max_events < 0:
        raise HTTPException(status_code=400, detail="max_events must be null or >= 0")
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.max_events = body.max_events
    db.commit(); db.refresh(target)
    return _admin_user(db, target)


@router.patch("/users/{user_id}/storage", response_model=schemas.AdminUserResponse)
def set_user_storage(user_id: int, body: schemas.StorageLimitUpdate,
                     db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    if body.storage_limit_mb is not None and body.storage_limit_mb < 0:
        raise HTTPException(status_code=400, detail="storage_limit_mb must be null or >= 0")
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.storage_limit_mb = body.storage_limit_mb
    db.commit(); db.refresh(target)
    return _admin_user(db, target)
```

- [ ] **Step 5: Make activity + analytics admin + global**

In `list_activity` (56-79): change dep to `Depends(require_admin)`, drop the owned-ids filtering — query `ActivityLog` globally (keep `event_id`/`action`/`limit` filters). In `analytics` (84-95): change dep to `Depends(require_admin)`, query all events (`db.query(models.Event).order_by(models.Event.created_at.desc()).all()`).

- [ ] **Step 6: Run — expect pass**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_admin_limits.py -v`
Expected: PASS (6 tests).

- [ ] **Step 7: Full suite (fix lingering fixtures)**

Run: `..\.venv\Scripts\python.exe -m pytest -q`. Fix any remaining `as_studio`→`as_admin`/`as_user` in `tests/test_admin.py` and assert global (not owned) scope. Green before commit.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/schemas.py backend/app/routers/admin.py backend/tests/test_admin_limits.py backend/tests/test_admin.py
git commit -m "feat: admin user payload + quota endpoints + global analytics"
```

---

### Task 8: `make_admin` script (deterministic admin minting)

**Files:**
- Create: `backend/scripts/__init__.py`, `backend/scripts/make_admin.py`
- Test: `backend/tests/test_make_admin.py`

**Interfaces:**
- Produces: `scripts.make_admin.promote_to_admin(db, email)->User`; CLI `python scripts/make_admin.py <email>`.

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_make_admin.py`:

```python
import sys, os
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
```

- [ ] **Step 2: Run — expect fail**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_make_admin.py -v`
Expected: FAIL — `No module named 'scripts'`.

- [ ] **Step 3: Create script**

Create `backend/scripts/__init__.py` (empty) and `backend/scripts/make_admin.py`:

```python
"""Promote an existing user to admin, by email.

Usage (from backend/):  python scripts/make_admin.py user@example.com
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal  # noqa: E402
from app.models import models  # noqa: E402


def promote_to_admin(db, email: str):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise SystemExit(f"No user with email {email!r} (must sign in once first).")
    user.role = "admin"
    db.commit(); db.refresh(user)
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

- [ ] **Step 4: Run — expect pass**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_make_admin.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/__init__.py backend/scripts/make_admin.py backend/tests/test_make_admin.py
git commit -m "feat: make_admin CLI for deterministic admin minting"
```

---

### Task 9: Frontend `useMe()` hook

**Files:** Create `frontend/lib/hooks/me.ts`

- [ ] **Step 1: Create**

```ts
'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

export interface MeUser {
  id: number;
  role: 'admin' | 'user' | 'pending';
  email: string | null;
  name: string | null;
  max_events: number | null;
  storage_limit_mb: number | null;
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

- [ ] **Step 2: Typecheck** — `npx tsc --noEmit` (no errors).
- [ ] **Step 3: Commit** — `git add frontend/lib/hooks/me.ts && git commit -m "feat: useMe role hook"`

---

### Task 10: Admin route group (guard + page + quota/storage editors + tokens/watch nav)

**Files:**
- Create: `frontend/app/(admin)/layout.tsx`, `frontend/app/(admin)/admin/page.tsx` (moved + extended)
- Delete: `frontend/app/(dashboard)/admin/page.tsx`

- [ ] **Step 1: Create the admin layout (role guard + full admin nav)**

Create `frontend/app/(admin)/layout.tsx`:

```tsx
'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import Link from 'next/link';
import { ShieldCheck, Users, KeyRound, ScrollText, LogOut, CreditCard, Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth-context';
import { useMe } from '@/lib/hooks/me';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, loading, signOut } = useAuth();
  const { data: me, isLoading } = useMe();

  useEffect(() => {
    if (!loading && !user) { router.push('/login'); return; }
    if (me && me.role !== 'admin') router.push(me.role === 'user' ? '/dashboard' : '/pending');
  }, [loading, user, me, router]);

  if (loading || !user || isLoading || !me || me.role !== 'admin') return null;

  const items = [
    { href: '/admin', icon: ShieldCheck, label: 'Admin' },
    { href: '/admin/billing', icon: CreditCard, label: 'Billing' },
    { href: '/admin/settings', icon: Settings, label: 'Studio Settings' },
  ];
  return (
    <div className="flex h-screen bg-slate-50">
      <aside className="w-64 bg-white border-r hidden md:flex flex-col">
        <div className="p-6 border-b flex items-center gap-2">
          <ShieldCheck className="w-7 h-7 text-primary" /><span className="text-xl font-bold">WedFind Admin</span>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          {items.map((it) => (
            <Link key={it.href} href={it.href}>
              <Button variant="ghost" className="w-full justify-start gap-2">
                <it.icon className="w-5 h-5" /> <span>{it.label}</span>
              </Button>
            </Link>
          ))}
        </nav>
        <div className="p-4 border-t">
          <Button variant="ghost" className="w-full justify-start gap-2 text-red-500 hover:bg-red-50"
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

Copy `frontend/app/(dashboard)/admin/page.tsx` to `frontend/app/(admin)/admin/page.tsx`. Apply: replace the `AdminUser` interface and `UsersTab` with the quota+storage-aware versions below (and add the `Tokens` tab linking to the existing token UI logic — keep `analytics`/`activity` tabs unchanged):

```tsx
interface AdminUser {
  id: number; email: string | null; name: string | null; phone: string | null;
  role: string; max_events: number | null; storage_limit_mb: number | null;
  event_count: number; effective_limit: number; effective_storage_limit_mb: number;
  storage_used_mb: number; created_at: string;
}
```

```tsx
function UsersTab() {
  const qc = useQueryClient();
  const { data: users, isLoading } = useQuery<AdminUser[]>({
    queryKey: ['admin-users'], queryFn: async () => (await api.get('/admin/users')).data,
  });
  const onErr = (e: unknown) => toast.error((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed');
  const setRole = useMutation({
    mutationFn: async ({ id, role }: { id: number; role: string }) => (await api.patch(`/admin/users/${id}/role`, { role })).data,
    onSuccess: () => { toast.success('Role updated'); qc.invalidateQueries({ queryKey: ['admin-users'] }); }, onError: onErr,
  });
  const setLimit = useMutation({
    mutationFn: async ({ id, max_events }: { id: number; max_events: number | null }) => (await api.patch(`/admin/users/${id}/limit`, { max_events })).data,
    onSuccess: () => { toast.success('Event limit updated'); qc.invalidateQueries({ queryKey: ['admin-users'] }); }, onError: onErr,
  });
  const setStorage = useMutation({
    mutationFn: async ({ id, storage_limit_mb }: { id: number; storage_limit_mb: number | null }) => (await api.patch(`/admin/users/${id}/storage`, { storage_limit_mb })).data,
    onSuccess: () => { toast.success('Storage limit updated'); qc.invalidateQueries({ queryKey: ['admin-users'] }); }, onError: onErr,
  });
  if (isLoading) return <Loader2 className="w-6 h-6 animate-spin" />;
  return (
    <Card><CardContent className="pt-6 overflow-x-auto">
      <table className="w-full text-sm">
        <thead><tr className="text-left text-slate-500 border-b">
          <th className="py-2 pr-4">User</th><th className="py-2 px-2">Role</th>
          <th className="py-2 px-2">Events</th><th className="py-2 px-2">Event limit</th>
          <th className="py-2 px-2">Storage</th><th className="py-2 px-2">Storage limit (MB)</th>
          <th className="py-2 px-2">Action</th>
        </tr></thead>
        <tbody>
          {users?.map((u) => (
            <tr key={u.id} className="border-b last:border-0">
              <td className="py-2 pr-4"><p className="font-medium">{u.name || u.email || `#${u.id}`}</p><p className="text-xs text-slate-400">{u.email}</p></td>
              <td className="py-2 px-2"><span className={`text-xs px-2 py-0.5 rounded-full ${u.role==='admin'?'bg-amber-100 text-amber-700':u.role==='user'?'bg-primary/10 text-primary':'bg-slate-100 text-slate-600'}`}>{u.role}</span></td>
              <td className="py-2 px-2 whitespace-nowrap">{u.event_count} / {u.effective_limit}</td>
              <td className="py-2 px-2">{u.role==='admin'?'—':<NumEditor value={u.max_events} onSave={(v)=>setLimit.mutate({id:u.id,max_events:v})} disabled={setLimit.isPending} />}</td>
              <td className="py-2 px-2 whitespace-nowrap">{u.storage_used_mb} / {u.effective_storage_limit_mb} MB</td>
              <td className="py-2 px-2">{u.role==='admin'?'—':<NumEditor value={u.storage_limit_mb} onSave={(v)=>setStorage.mutate({id:u.id,storage_limit_mb:v})} disabled={setStorage.isPending} />}</td>
              <td className="py-2 px-2">
                {u.role==='admin'?'—':u.role==='user'
                  ? <Button size="sm" variant="outline" onClick={()=>setRole.mutate({id:u.id,role:'pending'})} disabled={setRole.isPending}>Revoke</Button>
                  : <Button size="sm" onClick={()=>setRole.mutate({id:u.id,role:'user'})} disabled={setRole.isPending}>Grant user</Button>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </CardContent></Card>
  );
}

function NumEditor({ value, onSave, disabled }: { value: number | null; onSave: (v: number | null) => void; disabled: boolean }) {
  const [v, setV] = useState<string>(value === null ? '' : String(value));
  return (
    <div className="flex items-center gap-2">
      <input type="number" min={0} value={v} placeholder="default" onChange={(e)=>setV(e.target.value)} className="h-8 w-24 rounded-md border border-input px-2 text-sm" />
      <Button size="sm" variant="outline" disabled={disabled} onClick={()=>onSave(v.trim()===''?null:Math.max(0,parseInt(v,10)||0))}>Save</Button>
    </div>
  );
}
```

Delete old page: `git rm "frontend/app/(dashboard)/admin/page.tsx"`.

- [ ] **Step 3: Typecheck + lint** — `npx tsc --noEmit` (no errors).
- [ ] **Step 4: Commit**

```bash
git add "frontend/app/(admin)"
git rm "frontend/app/(dashboard)/admin/page.tsx"
git commit -m "feat: admin route group with role guard + quota/storage editors"
```

---

### Task 11: Studio dashboard — role guard + admin nav removed

**Files:** Modify `frontend/app/(dashboard)/layout.tsx`

- [ ] **Step 1: Guard + strip admin nav**

In `frontend/app/(dashboard)/layout.tsx`:
- Add import `import { useMe } from '@/lib/hooks/me';`.
- Remove the `Admin` nav `<Link href="/admin">` block (lines 56-61) AND the `API Keys` `<Link href="/settings">` block (lines 62-67) — tokens are admin-only now. Keep Dashboard + Events; add Photos/Guests/Profile links if those routes exist, else keep Dashboard + Events.
- Replace the redirect effect (18-22) and guard (29):

```tsx
  const { data: me, isLoading: meLoading } = useMe();
  useEffect(() => {
    if (!loading && !user) { router.push('/login'); return; }
    if (me && me.role !== 'user') router.push(me.role === 'admin' ? '/admin' : '/pending');
  }, [loading, user, me, router]);
```
```tsx
  if (loading || !user || meLoading || !me || me.role !== 'user') return null;
```

- [ ] **Step 2: Typecheck** — `npx tsc --noEmit`.
- [ ] **Step 3: Manual check** — a `user` sees only non-admin nav; visiting `/admin` as `user` redirects to `/dashboard`.
- [ ] **Step 4: Commit** — `git add "frontend/app/(dashboard)/layout.tsx" && git commit -m "feat: studio dashboard role guard, admin nav removed"`

---

### Task 12: Login redirect by role + pending page

**Files:** Modify `frontend/app/(auth)/login/page.tsx`; Create `frontend/app/pending/page.tsx`

- [ ] **Step 1: Role routing at login**

In `frontend/app/(auth)/login/page.tsx` add `import api from '@/lib/api';`, add helper inside component:

```tsx
  async function routeByRole() {
    try {
      const me = (await api.get('/auth/me')).data as { role: string };
      router.push(me.role === 'admin' ? '/admin' : me.role === 'user' ? '/dashboard' : '/pending');
    } catch { router.push('/pending'); }
  }
```
Replace both `router.push('/dashboard')` (lines 56, 69) with `await routeByRole();`.

- [ ] **Step 2: Pending page**

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
        <p className="text-slate-500">Your account isn&apos;t active yet. Please contact your admin to be granted studio access.</p>
        <Button variant="outline" onClick={async () => { await signOut(); router.push('/login'); }}>Sign out</Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Typecheck** — `npx tsc --noEmit`.
- [ ] **Step 4: Commit** — `git add "frontend/app/(auth)/login/page.tsx" frontend/app/pending/page.tsx && git commit -m "feat: role-based login redirect + pending screen"`

---

### Task 13: Quota 403 toasts on create + upload

**Files:** Modify `frontend/app/(dashboard)/dashboard/page.tsx`

- [ ] **Step 1: Surface backend detail**

In `onSubmit` (lines 49-61) replace the catch:

```tsx
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      toast.error(detail || 'Failed to create event');
    }
```

(If an upload handler exists in the events detail page, apply the same catch pattern so the storage-limit 403 surfaces.)

- [ ] **Step 2: Typecheck** — `npx tsc --noEmit`.
- [ ] **Step 3: Commit** — `git add "frontend/app/(dashboard)/dashboard/page.tsx" && git commit -m "feat: show quota 403 detail on create"`

---

### Task 14: Placeholder admin pages (billing, studio settings)

**Files:** Create `frontend/app/(admin)/admin/billing/page.tsx`, `frontend/app/(admin)/admin/settings/page.tsx`

- [ ] **Step 1: Create placeholders**

`frontend/app/(admin)/admin/billing/page.tsx`:

```tsx
'use client';
import { CreditCard } from 'lucide-react';
export default function BillingPage() {
  return (
    <div className="space-y-2">
      <h1 className="text-3xl font-bold flex items-center gap-2"><CreditCard className="w-7 h-7 text-primary" /> Billing</h1>
      <p className="text-slate-500">Subscription &amp; billing management is coming soon.</p>
    </div>
  );
}
```

`frontend/app/(admin)/admin/settings/page.tsx`:

```tsx
'use client';
import { Settings } from 'lucide-react';
export default function StudioSettingsPage() {
  return (
    <div className="space-y-2">
      <h1 className="text-3xl font-bold flex items-center gap-2"><Settings className="w-7 h-7 text-primary" /> Studio Settings</h1>
      <p className="text-slate-500">Studio-wide settings are coming soon.</p>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + lint** — `npx tsc --noEmit && npx eslint "app/(admin)"`.
- [ ] **Step 3: Commit** — `git add "frontend/app/(admin)/admin/billing" "frontend/app/(admin)/admin/settings" && git commit -m "feat: admin-only billing + settings placeholders"`

---

### Task 15: Config, README, security-review doc

**Files:** Modify `backend/.env.example`, `README.md`; Create `docs/superpowers/security-review-admin-routes.md`

- [ ] **Step 1: Env vars**

In `backend/.env.example` add:

```
# Per-user quotas (admin can override each user)
DEFAULT_EVENT_LIMIT=2
DEFAULT_STORAGE_LIMIT_MB=2048
```

- [ ] **Step 2: README roles note**

In `README.md` Security & Privacy section, replace the first-user bootstrap bullet with:

```
- Roles: `admin` (single, minted only via `python scripts/make_admin.py <email>`), `user` (studio photographer), `pending` (invite-only, no access until an admin grants `user`). New logins default to `pending`; no auto-admin. Admin sets each user's event + storage quota.
```

- [ ] **Step 3: Security-review deliverable**

Create `docs/superpowers/security-review-admin-routes.md` with a table of every admin route → gating dependency → confirmed 403-for-non-admin (filled from the final code), plus a statement that `tests/test_gating.py` + `tests/test_admin_limits.py` assert non-admin tokens receive 403.

- [ ] **Step 4: Full suite + frontend build**

Run (backend): `..\.venv\Scripts\python.exe -m pytest -q` — all green.
Run (frontend): `npx tsc --noEmit && npm run build` — succeeds.

- [ ] **Step 5: Commit**

```bash
git add backend/.env.example README.md docs/superpowers/security-review-admin-routes.md
git commit -m "docs: roles, quotas env, admin-route security review"
```

---

## Deliverables checklist (from the request)

1. **DB migration** — Task 1 (`e4f5a6b7c8d9`, columns + role remap).
2. **Backend authorization deps** — Task 3 (`require_admin`/`require_user`) + Task 4 (re-gate).
3. **Frontend role-based navigation** — Tasks 10, 11 (separate groups, admin nav not rendered for users).
4. **Admin/User UI separation** — Tasks 10–14.
5. **Permission tests** — Tasks 3, 4, 7 (`test_roles`, `test_gating`, `test_admin_limits`).
6. **Summary of changed files** — produced at the end of execution.
7. **Security review of admin routes** — Task 15 doc.

## Self-Review

- **Spec coverage:** roles+migration+remap (T1), helpers (T2), pending bootstrap + deps (T3), re-gate all routes (T4), event quota (T5), storage quota+size (T6), admin payload+endpoints+global (T7), make_admin (T8), useMe (T9), admin group+editors (T10), dashboard guard+nav strip (T11), login redirect+pending (T12), quota toasts (T13), placeholders (T14), config+README+security review (T15). All spec sections mapped.
- **Placeholder scan:** none; all code shown.
- **Type/name consistency:** `AdminUserResponse` fields (`event_count`, `effective_limit`, `effective_storage_limit_mb`, `storage_used_mb`, `max_events`, `storage_limit_mb`) consistent across schema (T7), frontend `AdminUser` (T10), `MeUser` (T9). `require_admin`/`require_user` named identically T3→T4→T7. Detail strings match the Global Constraints verbatim. Endpoints `/admin/users/{id}/{role,limit,storage}` consistent T7↔T10.
