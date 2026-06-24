# Security Review — Admin Route Authorization

**Date:** 2026-06-24
**Scope:** Verify every admin-only route enforces `require_admin` (role == "admin") server-side, independent of UI hiding, and that studio/pending users receive HTTP 403.

## Authorization model

- `deps.get_current_user` — resolves a Firebase ID token OR an `X-API-Key` to a `User`.
- `deps.require_user` → 403 `Studio access required` unless `role == "user"`.
- `deps.require_admin` → 403 `Admin access required` unless `role == "admin"`.
- New signups default to `role == "pending"` (no access). Admin is minted only by `scripts/make_admin.py`. No request path can escalate a role to `admin`.

## Admin-only routes (gated by `require_admin`)

| Method | Path | Source |
|--------|------|--------|
| GET | `/api/admin/users` | admin.py `list_users` |
| PATCH | `/api/admin/users/{id}/role` | admin.py `set_user_role` (rejects changing an `admin` row) |
| PATCH | `/api/admin/users/{id}/limit` | admin.py `set_user_limit` |
| PATCH | `/api/admin/users/{id}/storage` | admin.py `set_user_storage` |
| GET | `/api/admin/activity` | admin.py `list_activity` (global) |
| GET | `/api/admin/analytics` | admin.py `analytics` (global) |
| POST | `/api/auth/promote` | auth.py `promote_user` (roles user/pending; rejects admin) |
| POST | `/api/auth/tokens` | auth.py `create_api_token` (assigns to a target `user`) |
| GET | `/api/auth/tokens` | auth.py `list_api_tokens` |
| DELETE | `/api/auth/tokens/{id}` | auth.py `revoke_api_token` |
| POST | `/api/events/{id}/watch-folders` | events.py `add_watch_folder` |
| GET | `/api/events/{id}/watch-folders` | events.py `list_watch_folders` |
| DELETE | `/api/events/{id}/watch-folders/{wid}` | events.py `remove_watch_folder` |
| POST | `/api/events/{id}/watch-folders/{wid}/rescan` | events.py `rescan_watch_folder` |
| POST | `/api/events/{id}/rescan-all` | events.py `rescan_all_folders` |
| GET | `/api/events/{id}/privacy` | events.py `get_privacy` |
| PATCH | `/api/events/{id}/retention` | events.py `set_retention` |
| GET | `/api/events/{id}/consents` | events.py `list_consents` |
| GET | `/api/events/{id}/consents/export` | events.py `export_consents` |

## Studio-user routes (gated by `require_user`)

| Method | Path | Notes |
|--------|------|-------|
| POST/GET | `/api/events/` | own events (`photographer_id == current_user.id`); create enforces event quota |
| GET/DELETE | `/api/events/{id}` | ownership-filtered |
| POST | `/api/photos/upload/{id}` | ownership-filtered; also accepts `X-API-Key` (token assigned to a user); enforces storage quota |
| GET | `/api/photos/event/{id}` | ownership-filtered |

## Public routes (unauthenticated)
`/api/guest/*`, `/healthz`, `/`. `/api/auth/me` is any authenticated user (incl. pending) — returns role for client routing only; grants no management capability.

## Test evidence
Non-admin → 403 is asserted by automated tests:
- `tests/test_gating.py` — user/pending blocked from tokens, watch-folders, event create.
- `tests/test_admin.py` — `test_user_blocked_from_admin`, `test_pending_blocked_from_admin`.
- `tests/test_admin_limits.py::test_quota_endpoints_reject_user`.
- `tests/test_auth.py::test_user_cannot_promote`.
- `tests/test_roles.py` — `require_admin`/`require_user` unit-level 403s with exact detail strings.
- `tests/test_tokens.py` — token assigned to a target user; non-user target rejected (400).

Full backend suite: **65 tests pass**.

## Residual notes (for follow-up, not blocking this change)
- The old studio `/settings` API-keys page was **removed** (token management is admin-only now); agent-token UI for the admin area is a follow-up.
- Server-side folder-watch reads the backend host filesystem (admin-gated, but cloud deploys should rely on the desktop agent).
- The Alembic `upgrade()` (column adds + Postgres `CHECK ck_users_role` + `remap_roles`) is not run by the SQLite test harness — run `alembic upgrade head` once against a Postgres copy before deploy. The remap logic itself is unit-tested in `test_role_remap.py`.
