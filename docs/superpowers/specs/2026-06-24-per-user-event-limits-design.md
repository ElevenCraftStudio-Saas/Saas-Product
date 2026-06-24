# Admin/Studio Separation + Per-User Event Limits — Design

**Date:** 2026-06-24
**Goal:** Open the app to real-time test users. Add a real admin role with its own page (manage users, set event limits, view analytics/audit), separate from the studio user page. Cap how many events each studio can create.

## Decisions (from brainstorming)

- **Roles:** `admin`, `studio`, `guest`.
- **Bootstrap:** the **first user becomes `admin`** (was `studio`). Everyone after = `guest` (least privilege). Admin promotes guests → studio.
- **Separate pages:** admin-only `/admin` area; studio-only `/dashboard` area. Role-gated, not just auth-gated.
- **Event limit:** per-user cap on studios, admin-settable, with a global default.
- **Default limit:** `2` events per new studio. No "unlimited" concept — admin sets a big number if needed.
- **Enforcement:** block event creation with `HTTP 403` + message telling the user to contact the admin.
- **Deployment:** deferred. User will host on a subdomain once ready; a deploy guide is delivered at the end (not built now).

## Roles & auth (backend)

`deps.py`:
- `_find_or_create_user`: first user (`count() == 0`) → `role="admin"`, else `role="guest"`.
- New dependency `get_current_admin`: requires `role == "admin"`, else `403 "Admin access required"`.
- `get_current_studio` unchanged (`role == "studio"`).

`User` model gains:
```python
max_events = Column(Integer, nullable=True)  # null = DEFAULT_EVENT_LIMIT; int = explicit cap
```
Alembic migration adds the nullable column. No backfill.

## Global default

- Env var `DEFAULT_EVENT_LIMIT` (default `2`).
- Helper: `effective_event_limit(user) -> int = user.max_events if user.max_events is not None else DEFAULT_EVENT_LIMIT`.

## Event-create enforcement (studio)

In `create_event` ([events.py](../../../backend/app/routers/events.py)), before creating:
```python
count = db.query(models.Event.id).filter(models.Event.photographer_id == current_user.id).count()
limit = effective_event_limit(current_user)
if count >= limit:
    raise HTTPException(403, f"Event limit reached ({count}/{limit}). Contact your admin to raise it.")
```

## Admin API ([admin.py](../../../backend/app/routers/admin.py)) — re-gated to `get_current_admin`

- `GET /api/admin/users` → each user includes `role`, `max_events`, `event_count`, `effective_limit`.
- `PATCH /api/admin/users/{id}/role` → promote/demote between `studio` and `guest`. Cannot demote self; cannot change an `admin` row (guard).
- `PATCH /api/admin/users/{id}/limit` → body `{max_events: int|null}`, validate null or `>= 0`.
- `GET /api/admin/activity` and `GET /api/admin/analytics` → **global** (all events), since admin owns none. (Previously scoped to caller's own events.)

Schemas ([schemas.py](../../../backend/app/schemas/schemas.py)): extend `UserResponse` (role, max_events, event_count, effective_limit); add `EventLimitUpdate { max_events: Optional[int] }`.

## Frontend — role-gated separate areas

- **Expose role:** add `useMe()` React Query hook hitting `GET /api/auth/me`; returns backend user incl. `role`. Used by layouts + login redirect.
- **Route groups:**
  - `app/(admin)/admin/...` — own layout, guard `role === "admin"` (else redirect). Moves the existing admin page out of `(dashboard)`.
  - `app/(dashboard)/...` — studio area, guard `role === "studio"` (currently auth-only). Remove the Admin nav link from the studio sidebar.
- **Login redirect** ([login/page.tsx](../../../frontend/app/(auth)/login/page.tsx)): after sign-in, fetch me → `admin` → `/admin`, `studio` → `/dashboard`, `guest` → a "pending access — contact admin" screen.
- **Admin page:** user table with role badge, promote/demote, editable `max_events` (blank = default), usage `event_count / effective_limit`; plus analytics + audit log (already built, now admin-only).
- **Studio dashboard:** events list + create (catch `403` → `sonner` toast with the contact-admin message), settings/API keys.

## Testing (pytest)

- Bootstrap: first user = admin; second = guest.
- `get_current_admin` gate: admin passes; studio/guest → 403.
- Event create: allowed under limit; 403 at/over limit (message); `null` → default 2.
- `PATCH /limit`: updates; validates `>= 0`; admin-only.
- `PATCH /role`: promote guest→studio; can't demote self/admin.
- `GET /users`: returns role, event_count, effective_limit.
- Admin analytics/activity: global across events.

## Deployment guide (delivered at end, not built)

- **Frontend → Vercel** (Next 16, auto-HTTPS for selfie camera). Point subdomain (e.g. `app.<domain>`) via CNAME.
- **Backend → AWS Lightsail/EC2 in us-east-1** (same VPC as RDS → private DB access, no public exposure; ≥2GB RAM for InsightFace). Subdomain `api.<domain>` via A record + HTTPS (Caddy/Nginx). Set `NEXT_PUBLIC_API_URL=https://api.<domain>/api`, `FRONTEND_URL=https://app.<domain>` for CORS.
- Alt backend: Railway/Fly.io (2GB) — faster, RDS stays public (keep SG rule).

## Out of scope

- Multi-tenant org structures, billing.
- Photo/storage quotas.
- Self-service guest→studio signup (admin promotes manually).
