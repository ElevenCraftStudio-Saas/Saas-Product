# Phase 3 — Reliability Design Review (Observability / Metrics / DB hardening / Tests)

> Review BEFORE code. Goal: make failures visible (Sentry, structured logs, metrics), make the schema safe (FK cascades + indexes), and raise confidence (pgvector + Celery integration tests, ≥80% coverage). No business-logic changes.

## Current state
- Logging = `logging.basicConfig` plain text, loggers `wedfind.*`. No JSON, no request id. (`app/main.py`)
- No Sentry (DSN field already exists in `config.py`, unused). No metrics endpoint.
- **Every FK has no `ON DELETE`** — cascades are ORM-only → raw/bulk deletes orphan rows. (`alembic/versions/8a80caa549c7…`)
- Missing indexes: `downloads.photo_id`, `activity_logs(event_id, created_at)`, `guest_consents(event_id, ip_address)`. (`photos.event_id`, `face_embeddings.event_id` already indexed.)
- Tests run SQLite only; **pgvector KNN + Celery + migration `upgrade()` paths unexercised**. Coverage **72%** (Phase 1 CI gate = 70%).

---

## 1. Sentry Architecture
- `sentry-sdk[fastapi]` + Celery integration. Init **once per process**: web in `main.py`, workers in `celery_app.py` — both gated on `settings.SENTRY_DSN` (no-op when unset, so dev/test untouched).
- `traces_sample_rate=0.1` (tunable env), `profiles_sample_rate=0`, `environment=settings.ENV`, `release=<git sha>` (build arg).
- Captures: unhandled exceptions (auto), plus an explicit `capture_exception` in the Phase-2 task `on_failure` dead-letter hook and in `process_photo_faces`/`make_thumbnail` failure branches.
- PII scrubbing: `send_default_pii=False`; strip Authorization/X-API-Key via `before_send`.

## 2. Logging Format
- **structlog → JSON** (one line per event). Replace `basicConfig` with a `logging.config.dictConfig` that routes stdlib `wedfind.*` + uvicorn loggers through a structlog `ProcessorFormatter`.
- Fields: `timestamp` (ISO8601 UTC), `level`, `logger`, `event` (message), `request_id`, plus any bound context (`event_id`, `photo_id`, `task_id`). Exceptions rendered with traceback.
- Toggle: `LOG_JSON` (default true in prod, false/plain in dev for readability). Keeps every existing `logger.info(...)` call working unchanged.
- `python-json-logger` is the lighter alternative; **recommend structlog** for the contextvar-based correlation id (item 3).

## 3. Correlation ID Strategy
- Middleware `RequestIDMiddleware`: read inbound `X-Request-ID` (or generate `uuid4`), bind into a `contextvars` var, set on the response header. structlog merges the contextvar into every log line within the request.
- **Across Celery:** enqueue helpers attach the current request id as a task header (`process_photo.apply_async(..., headers={"request_id": rid})`); a worker `task_prerun` signal binds it into the worker's structlog context → web→worker log correlation for one upload.
- Sentry: set `scope.set_tag("request_id", rid)` so errors are joinable with logs.

## 4. Metrics Architecture
- HTTP: `prometheus-fastapi-instrumentator` exposes `/metrics`. **Exposure: internal network only** (ECS security group / k8s ClusterIP) — not behind app auth, never public. Optional `ENABLE_METRICS` flag (default true).
- Celery: `task_prerun`/`task_postrun`/`task_failure` signals increment custom counters + a duration histogram (no extra exporter container needed). Queue depth scraped from Redis by an external `celery-exporter` (deploy-time, optional) OR a gauge updated by beat.
- Domain counters live in `core/metrics.py` (a registry module), incremented from services.

## 5. Prometheus Metric List
| Metric | Type | Labels | Source |
|---|---|---|---|
| `http_requests_total` | counter | method, handler, status | instrumentator |
| `http_request_duration_seconds` | histogram | method, handler | instrumentator |
| `http_requests_inprogress` | gauge | method, handler | instrumentator |
| `wedfind_celery_tasks_total` | counter | task, state(success/failure/retry) | celery signals |
| `wedfind_celery_task_duration_seconds` | histogram | task | celery signals |
| `wedfind_photos_processed_total` | counter | result(completed/failed) | face_processing |
| `wedfind_faces_detected_total` | counter | — | face_processing |
| `wedfind_thumbnails_total` | counter | result(ok/fail) | thumbnails |
| `wedfind_selfie_matches_total` | counter | matched(yes/no) | guest match |
| `wedfind_quota_rejections_total` | counter | kind(event/storage) | quota enforcement |
| `wedfind_dependency_up` | gauge | dep(db/redis/s3) | readyz |

## 6. FK Cascade Migration Plan
Add `ON DELETE` to every FK so DB-level deletes are safe (not just ORM):

| Table.column → parent | Action |
|---|---|
| `events.photographer_id → users.id` | CASCADE |
| `photos.event_id → events.id` | CASCADE |
| `face_embeddings.photo_id → photos.id` | CASCADE |
| `face_embeddings.event_id → events.id` | CASCADE |
| `downloads.photo_id → photos.id` | CASCADE |
| `guest_consents.event_id → events.id` | CASCADE |
| `folder_watches.event_id → events.id` | CASCADE |
| `api_tokens.assigned_user_id → users.id` | CASCADE |
| `activity_logs.event_id → events.id` | **SET NULL** (keep audit row) |
| `activity_logs.photo_id → photos.id` | **SET NULL** |

**Lock-safe technique (Postgres):** for each FK — `ALTER TABLE … DROP CONSTRAINT <name>; ALTER TABLE … ADD CONSTRAINT <name> FOREIGN KEY(...) REFERENCES ... ON DELETE … NOT VALID;` then `ALTER TABLE … VALIDATE CONSTRAINT <name>;`.
- `ADD … NOT VALID` = metadata-only, **brief ACCESS EXCLUSIVE** (sub-second).
- `VALIDATE CONSTRAINT` = scans the table but takes only **SHARE UPDATE EXCLUSIVE** → reads + writes continue.
- Adding `ON DELETE` does **not rewrite** the table.
- **SQLite:** cannot `ALTER` FKs → migration guards Postgres-only; SQLite relies on ORM cascade (unchanged). Tests assert ORM cascade.
- Existing constraint names: discover via `information_schema` at migration time (names were auto-generated) rather than hard-coding.

## 7. Index Migration Plan
Add the missing indexes **`CONCURRENTLY`** (no write lock):
- `ix_downloads_photo_id` on `downloads(photo_id)`
- `ix_activity_event_created` on `activity_logs(event_id, created_at DESC)`
- `ix_consents_event_ip` on `guest_consents(event_id, ip_address)`

- `CREATE INDEX CONCURRENTLY` **cannot run in a transaction** → use Alembic `with op.get_context().autocommit_block():`. Postgres-only; SQLite path uses plain `CREATE INDEX` (no CONCURRENTLY keyword).
- **No lock, no maintenance window** (build runs longer but reads/writes continue).

## 8. pgvector Test Strategy
- `@pytest.mark.pg` tests, skipped unless `WEDFIND_TEST_PG_URL` is set (CI provides the pgvector service). A session-scoped fixture builds a PG engine, `CREATE EXTENSION IF NOT EXISTS vector`, runs `alembic upgrade head` (also covers item 9's migration test), seeds embeddings.
- Assertions: (a) `EXPLAIN` of the match query shows **Index Scan using ix_face_embeddings_vec** (not Seq Scan); (b) KNN returns the same ids as the SQLite reference at a given threshold; (c) event isolation (a face in event B never matches event A); (d) FK cascade actually fires (`DELETE FROM events` removes child rows).
- This is the first real coverage of the production matching path.

## 9. Celery Integration Test Strategy
- **Layer 1 (have):** eager-mode unit tests for task logic.
- **Layer 2 (new):** `@pytest.mark.celery`, skipped without `REDIS_URL` reachable. Use `pytest-celery` (or a `celery_worker` fixture) + the CI Redis service. Enqueue `process_photo` / `make_thumbnail` for real and assert DB side-effects; test `reset_stuck_processing` re-enqueues a wedged photo; test retry on a forced transient error.
- Migration test: `alembic upgrade head` then `alembic downgrade -1` round-trips for the new migrations (CI, real PG).

## 10. Coverage Plan (72% → 80%)
New tests: `process_photo_faces` happy + S3-download-fail (status FAILED) + reset_stuck; `make_thumbnail` error branch; `folder_watcher.handle_file` (temp FS, mocked engine/S3); activity logging; retention tz-boundary; pgvector (item 8); migration round-trip (item 9).
- `.coveragerc` `omit`: `app/services/face_engine.py` (loads the 300MB model — not unit-testable), `alembic/*`, `app/workers/celery_app.py` boot. This removes untestable lines from the denominator so 80% reflects real logic.
- Raise CI gate `--cov-fail-under` **70 → 80** in the same commit that lands the new tests.

## 11. Rollback Plan
- **Observability/metrics are additive + env-gated:** unset `SENTRY_DSN` / set `LOG_JSON=false` / `ENABLE_METRICS=false` → revert behavior with **no redeploy**. Each is an isolated commit → `git revert` cleanly.
- **DB migrations** have `downgrade()`: FK migration restores the prior (no-`ON DELETE`) constraints; index migration `DROP INDEX CONCURRENTLY`. `NOT VALID`/`VALIDATE` and `CONCURRENTLY` are all reversible and non-destructive (no data change, no table rewrite).
- Coverage gate raise is a CI-config revert only.

## 12. Production Deployment Plan (ordered)
1. **A Observability** — deploy (no schema). Set `SENTRY_DSN`, `LOG_JSON=true`. Confirm structured logs + a test error in Sentry + `X-Request-ID` echoed.
2. **B Metrics** — deploy; wire Prometheus scrape of `/metrics` on the internal network; import a Grafana dashboard. No schema.
3. **C-indexes** — `alembic upgrade` (CONCURRENTLY) — **no window**.
4. **C-FK cascades** — `alembic upgrade` — **brief sub-second exclusive lock per table** on `DROP/ADD … NOT VALID`; `VALIDATE` runs online. Schedule in a **low-traffic window** to be safe, but no long outage.
5. **D Tests** — CI gate to 80%; no runtime change.
6. Alarms: Sentry issue spikes, `http_request_duration_seconds` p95, `wedfind_celery_tasks_total{state="failure"}`, queue depth, `wedfind_dependency_up==0`.

---

## ⚠️ Migrations that lock / need a window
| Migration | Lock | Window? |
|---|---|---|
| **Indexes (CONCURRENTLY)** | none (online build) | **No window** |
| **FK cascades** | brief **ACCESS EXCLUSIVE** per table on DROP/ADD-NOT-VALID (sub-second); VALIDATE is online (SHARE UPDATE EXCLUSIVE) | **Low-traffic window recommended** (short, no rewrite). Avoid during a bulk-delete/heavy-write job. |

No table rewrites. No long-held locks if the NOT VALID + VALIDATE technique is used (vs. a plain validating ADD CONSTRAINT, which would hold the lock through the scan — **rejected** for that reason).

---

## Decisions (approved 2026-06-24)
1. **Logging:** **structlog** → JSON + contextvar correlation id.
2. **`/metrics`:** **internal-network only, no auth.**
3. **FK migration:** **`NOT VALID` + `VALIDATE`** (minimal lock).
4. **Coverage gate:** **75% now**, raise to 80% once the pg/celery marked suites are stable in CI.
