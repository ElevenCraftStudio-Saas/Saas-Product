# Per-User Event Limits — Design

**Date:** 2026-06-24
**Goal:** Let an admin cap how many events each studio user can create, so the project can be opened to real-time test users without unbounded event creation.

## Decisions (from brainstorming)

- **Limit model:** per-user cap, admin-settable, with a global default for new users.
- **Default:** `2` events per new user.
- **Unlimited:** not a distinct concept. Every user has a numeric cap. "Unlimited" = admin sets a large number.
- **Admin identity:** any `studio`-role user (reuses existing `get_current_studio` gate — matches current admin-panel behavior).
- **Enforcement:** block event creation with `HTTP 403` and a message telling the user to contact the admin.

## Data model

`User` ([backend/app/models/models.py](../../../backend/app/models/models.py)) gains:

```python
max_events = Column(Integer, nullable=True)  # null = use DEFAULT_EVENT_LIMIT; int = explicit cap
```

- `null` → fall back to global default (lets new users inherit the default without a backfill).
- Alembic migration adds the nullable column. No backfill required.

## Global default

- Env var `DEFAULT_EVENT_LIMIT` (default `2`) read via settings/`os.getenv`.
- Effective limit helper:

```python
def effective_event_limit(user) -> int:
    return user.max_events if user.max_events is not None else DEFAULT_EVENT_LIMIT
```

## Enforcement — event create

In `create_event` ([backend/app/routers/events.py](../../../backend/app/routers/events.py)), before building the event:

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

## Admin API ([backend/app/routers/admin.py](../../../backend/app/routers/admin.py))

- **`PATCH /api/admin/users/{user_id}/limit`** — body `{ "max_events": int | null }`, gated by `get_current_studio`.
  - Validate `max_events` is `null` or `>= 0`.
  - Returns updated `UserResponse`.
- **`GET /api/admin/users`** response gains:
  - `max_events: int | null` (raw stored value)
  - `event_count: int` (current owned-event count, for "2/3"-style display)
  - `effective_limit: int` (computed, so the UI need not know the default)

Schema changes in [backend/app/schemas/schemas.py](../../../backend/app/schemas/schemas.py): extend `UserResponse`; add `EventLimitUpdate { max_events: Optional[int] }`.

## Frontend (admin panel + create flow)

- **User-management table** (admin panel): add a column showing `event_count / effective_limit` and an editable number input for `max_events` (blank = inherit default). Save calls the new PATCH endpoint and refreshes via React Query.
- **Event-create handler**: catch `403` from `POST /api/events/`, surface `error.response.data.detail` as a `sonner` toast (the contact-admin message).

## Testing

Backend pytest additions:
- create allowed under limit; blocked at/over limit (403 with message).
- `null` `max_events` falls back to `DEFAULT_EVENT_LIMIT`.
- `PATCH /limit` updates value; validates `>= 0`; rejects non-studio.
- `GET /users` returns `event_count` + `effective_limit`.

## Out of scope

- True role separation (super-admin vs studio) — intentionally deferred; any studio is admin for now.
- Per-event-type or time-windowed quotas.
- Photo/storage quotas.
