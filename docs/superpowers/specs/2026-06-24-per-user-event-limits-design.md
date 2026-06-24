# Admin/User Role Separation + Quotas — Design

**Date:** 2026-06-24 (revised)
**Goal:** Enforce hard role separation between a single **admin** and **studio users**. Users never see or reach admin functionality (UI or API). Admin controls users, roles, event/storage quotas, tokens, folder-watch, privacy/audit. New signups are invite-only.

## Decisions (locked)

- **Roles:** `admin`, `user`, `pending`.
  - `admin` — full control (one designated admin; minted only by the `make_admin` CLI / migration seed).
  - `user` — studio photographer: create/manage own events, upload photos, view guest matches, download, view own profile.
  - `pending` — logged in but **no access** (invite-only holding state). Sees a "pending approval" screen only.
  - **Anonymous guests** (event-link visitors) keep the login-free public flow — no `User` row.
- **No auto-admin / no privilege escalation.** Remove the "first user becomes studio" bootstrap. New Firebase logins are created as `pending`. Admin is granted **only** by `scripts/make_admin.py` (ops, once) or by an existing admin via the promote/role endpoints.
- **Default new-signup role:** `pending` (invite-only).
- **Event quota:** per-user `max_events`, admin-settable, default `DEFAULT_EVENT_LIMIT=2`.
- **Storage quota:** per-user `storage_limit_mb`, admin-settable, default `DEFAULT_STORAGE_LIMIT_MB=2048`. Enforced at ingest by summing `Photo.size_bytes` for the user's events.
- **Deferred (placeholder admin-only pages, not built):** billing/subscription, studio settings, event-assignment to users. These render an admin-only "coming soon" page; no backend.
- **Role column:** stored as a constrained `String` (values `admin`/`user`/`pending`) validated in app + a DB CHECK constraint — not a native PG ENUM (keeps SQLite tests + Alembic downgrades simple). Functionally equivalent to the requested `Enum`.

## Backend authorization

`deps.py`:
- `_find_or_create_user`: new users → `role="pending"` (was first-user→studio). No count-based bootstrap.
- `require_admin(current_user)` → 403 `{"detail": "Admin access required"}` unless `role == "admin"`.
- `require_user(current_user)` → 403 `{"detail": "Studio access required"}` unless `role == "user"`. (Replaces `get_current_studio`; admins are NOT users — admin manages, doesn't create events.)

**Endpoint gating:**
- `require_admin`: all `/api/admin/*`; `/api/auth/promote`; `/api/auth/tokens` (create/list/revoke); `/api/events/{id}/watch-folders*` + `rescan*`; `/api/events/{id}/privacy` + `retention` + `consents` + `consents/export`.
- `require_user`: `POST/GET /api/events/`, `GET/DELETE /api/events/{id}`, `POST /api/photos/upload/{id}` (also accepts `X-API-Key` agent), `GET /api/photos/event/{id}`.
- Public: `/api/guest/*`, `/healthz`.
- `/api/auth/me`: any authenticated user (incl `pending`) — returns role so the frontend can route.

## Data model

`User`:
```python
role = Column(String, nullable=False, default="pending")  # admin | user | pending (CHECK-constrained)
max_events = Column(Integer, nullable=True)        # null = DEFAULT_EVENT_LIMIT
storage_limit_mb = Column(Integer, nullable=True)  # null = DEFAULT_STORAGE_LIMIT_MB
```
`Photo`:
```python
size_bytes = Column(Integer, nullable=True)  # bytes stored, for storage-quota accounting
```

**Migration (`e4f5a6b7c8d9`):**
1. Add `users.max_events`, `users.storage_limit_mb`, `photos.size_bytes` (all nullable).
2. Add CHECK constraint `role IN ('admin','user','pending')`.
3. **Data remap (safe, deterministic, exactly one admin):**
   - Lowest-`id` user → `admin`.
   - All other rows with old role `studio` → `user`.
   - All other rows with old role `guest` → `pending` (preserves "no access" — guest had none).

## Helpers

`app/core/limits.py`:
- `DEFAULT_EVENT_LIMIT = int(env "DEFAULT_EVENT_LIMIT", 2)`
- `DEFAULT_STORAGE_LIMIT_MB = int(env "DEFAULT_STORAGE_LIMIT_MB", 2048)`
- `effective_event_limit(user) -> int`
- `effective_storage_limit_mb(user) -> int`
- `user_storage_used_bytes(db, user) -> int` (sum `Photo.size_bytes` over the user's events)

## Enforcement

- **Event create** (`events.py create_event`): `count >= effective_event_limit` → 403 `Event limit reached ({count}/{limit}). Contact your admin to raise it.`
- **Photo ingest** (`photo_ingest.ingest_photo_bytes`): set `Photo.size_bytes = len(data)`; if `used + len(data) > limit*1024*1024` → 403 `Storage limit reached. Contact your admin.` (raised before S3 upload to avoid orphan objects).

## Admin API (`admin.py`, all `require_admin`)

- `GET /users` → `AdminUserResponse[]` with `role, max_events, storage_limit_mb, event_count, effective_limit, effective_storage_limit_mb, storage_used_mb`.
- `PATCH /users/{id}/role` → body `{role}` in `{user, pending}`; cannot change an `admin` row (400).
- `PATCH /users/{id}/limit` → `{max_events: int|null}` (null or ≥0).
- `PATCH /users/{id}/storage` → `{storage_limit_mb: int|null}` (null or ≥0).
- `GET /activity`, `GET /analytics` → global (admin sees all).

## Frontend (role-based separation)

- `useMe()` hook → `/auth/me` returns `{id, role, ...}`.
- **Route groups:**
  - `(admin)/admin/...` — guard `role==='admin'`. Nav: Dashboard, Users, Event/Storage limits, API Tokens, Audit, Analytics, Folder-watch, Billing (placeholder), Settings (placeholder).
  - `(dashboard)/...` — guard `role==='user'`. Nav: Dashboard, Events, Photos, Guests, Profile. **No admin items rendered at all** (not hidden via CSS — not rendered).
  - `pending` users → `/pending` screen.
- **Login redirect:** `admin → /admin`, `user → /dashboard`, `pending → /pending`.
- Admin user table: role toggle (user↔pending), event-limit editor, storage-limit editor, usage columns.
- Create-event / upload failures surface the backend 403 detail as a toast.
- API Tokens UI + folder-watch UI move into the admin area (removed from user dashboard).

## Security review (deliverable)

After build, produce a table of every admin route × dependency gate confirming `require_admin`, plus confirmation that no admin data is reachable with a `user`/`pending` token (covered by tests).

## Testing

- Migration remap: lowest-id→admin, studio→user, guest→pending; exactly one admin.
- `require_admin`/`require_user` gates: admin/user/pending matrix → 200/403 with exact detail strings.
- New signup → `pending`; no auto-admin.
- Event quota + storage quota enforcement (under/at/over; storage raises before S3).
- Admin role/limit/storage PATCH; cannot demote admin.
- `GET /users` payload fields.
- Frontend: manual checks — user never sees admin nav; `/admin` as user redirects; pending sees pending screen.

## Out of scope
Billing system, storage usage trends, event-assignment relation, multi-tenant orgs, self-service signup approval flows beyond a manual admin grant.
