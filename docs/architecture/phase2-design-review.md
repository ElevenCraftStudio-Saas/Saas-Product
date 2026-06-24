# Phase 2 — Scalability Design Review (Celery / HNSW / Thumbnails)

> Review BEFORE code. Goal: move heavy work off the web tier, make matching index-backed, add thumbnails — without changing business logic or the public API shape (except the documented guest-match async option).

## Current state (what we're changing)
- `face_processing.process_photo_faces(photo_id)` runs via **FastAPI BackgroundTasks** (`photos.py`) and a **raw daemon thread** (`folder_watcher.py`) — in the web process. (`app/services/face_processing.py`)
- Guest selfie: `face_engine.get_faces()` runs **inline in an `async def` handler** → blocks the event loop. (`routers/guest.py`)
- Matching: `WHERE (1 - (embedding_vec <=> q)) >= threshold` — a **range scan**, HNSW index unused, no `LIMIT`. (`services/matching.py`)
- Retention sweep: `asyncio` loop **inside every web worker** (`main.py` lifespan) → duplicate work under >1 worker.
- Embedding stored **twice** (JSON `embedding` + `vector(512)`); no `event_id` on `face_embeddings`; no thumbnails.
- Phase 1 already added `REDIS_URL` + readiness ping, so Redis is a known dependency.

---

## 1. Celery Architecture
```
app/workers/
  celery_app.py     # Celery() factory: broker+backend = settings.REDIS_URL
  face_tasks.py     # process_photo(photo_id), match_selfie(event_id, bytes)  [optional]
  thumb_tasks.py    # make_thumbnail(photo_id), backfill_thumbnails()
  maintenance.py    # retention_sweep(), reset_stuck_processing()   (beat-scheduled)
```
- **Factory pattern:** `celery_app = Celery("wedfind", broker=REDIS_URL, backend=REDIS_URL)`; `task_acks_late=True`, `worker_prefetch_multiplier=1` (fair dispatch for long CPU tasks), `task_reject_on_worker_lost=True`.
- Tasks call existing **services** (`face_processing`, `s3_service`, `retention`) — no logic rewrite. Each task opens its own `SessionLocal` (already the pattern in `process_photo_faces`).
- Web tier **enqueues** (`process_photo.delay(id)`); never runs inference. `face_engine` (buffalo_l) loads in the **worker** process, not the API.
- **Feature flag** `USE_CELERY` (default true in prod): when false, fall back to the current BackgroundTasks path — zero-risk rollback (item 10).

## 2. Redis Queues
Separate queues so a flood of heavy face jobs doesn't starve quick ones:

| Queue | Tasks | Why |
|---|---|---|
| `face` | `process_photo`, `match_selfie` | CPU-heavy InsightFace; isolated |
| `thumbs` | `make_thumbnail`, `backfill_thumbnails` | light, must stay responsive |
| `maintenance` | `retention_sweep`, `reset_stuck_processing` | beat-driven, low priority |

Routing via `task_routes`. Redis DB index per env (`/0` app cache + broker is fine; or `/1` broker, `/2` result to separate). Result backend TTL `result_expires=3600`.

## 3. Worker Count Strategy
- **face worker:** `--pool=prefork --concurrency=$(nproc)` (CPU-bound; 1 task per core). Each prefork child loads its own model copy → size the box for `cores × ~1.5 GB`. Scale **replicas** on Redis `face` queue depth (KEDA/ASG on `llen`).
- **thumbs worker:** `--pool=threads --concurrency=4` (I/O-bound: S3 + Pillow). Can share a container or be separate.
- **beat:** exactly **1 replica** (owns schedules; no duplication). Retention loop **removed from web lifespan**.
- Local/dev: one worker consuming all queues (`-Q face,thumbs,maintenance`).

## 4. Retry Strategy
- **Transient** (S3 `ClientError`/timeout, DB `OperationalError`): `autoretry_for=(BotoCoreError, OperationalError)`, `retry_backoff=True` (exponential), `retry_backoff_max=300`, `retry_jitter=True`, `max_retries=5`.
- **Permanent** (corrupt image, unsupported type): no retry → mark `status='failed'`, log, return. "No face found" is **not** an error → `status='completed'` with 0 embeddings.
- `acks_late=True` so a crash mid-task re-delivers (at-least-once). Tasks are **idempotent**: `process_photo` deletes any existing embeddings for the photo before inserting (safe re-run); `make_thumbnail` overwrites the same S3 key.

## 5. Dead-Letter Handling
Celery has no native DLQ. Strategy:
- On final failure (`max_retries` exhausted) → `on_failure` hook sets `Photo.status='failed'`, writes an `ActivityLog` `PHOTO_PROCESS_FAILED` with the error, and reports to **Sentry** (Phase 3 wires the DSN; hook is ready now).
- **`reset_stuck_processing` beat job** (every 15 min): photos `status='processing'` older than N minutes → reset to `pending` and re-enqueue (covers worker-killed jobs). Bounded re-enqueue count via an attempt counter to avoid infinite loops.
- A lightweight `failed` query powers an admin "reprocess" action (future). No separate DLQ table in Phase 2 — `status='failed'` + activity log is the dead-letter record.

## 6. Thumbnail Generation Pipeline
```
ingest_photo_bytes  → photo row (+ enqueue make_thumbnail.delay(id))
make_thumbnail(id)  → S3 get original → Pillow: fit within 400px, EXIF-transpose,
                      strip metadata → encode WebP q80 → S3 put thumb_key
                      → photos.thumb_key = key
```
- New column `photos.thumb_key TEXT NULL` (migration B/D).
- S3 layout: `events/{eid}/thumbs/{uuid}.webp` alongside originals.
- Gallery/admin list responses return **thumb presigned URL** (fallback to original if `thumb_key` null); originals only on explicit download. Frontend switches grids to `next/image` + `remotePatterns` (CDN host).
- **Backfill** existing photos: `backfill_thumbnails()` enqueues `make_thumbnail` for every `thumb_key IS NULL` photo, in batches.

## 7. Face Embedding Pipeline
- `process_photo` task = current `process_photo_faces` logic, unchanged, called from Celery instead of BackgroundTasks/daemon thread. Ingest paths (`photos.py`, `folder_watcher.py`) switch `add_task(...)` / `Thread(...)` → `process_photo.delay(id)`.
- **Idempotency:** task first deletes existing `FaceEmbedding` rows for the photo (re-run safe under `acks_late`).
- **Guest selfie matching** — two options (decision needed):
  - **(A) Celery task + poll (recommended):** `POST /selfie` records consent, enqueues `match_selfie`, returns `job_id`; new `GET /guest/{slug}/matches/{job_id}` polls result. True isolation; needs a small frontend polling change. Matches the v2 blueprint.
  - **(B) Threadpool inline (minimal):** keep one request/response; wrap inference in `await run_in_threadpool(face_engine.get_faces, ...)` so the event loop isn't blocked. No frontend change, but inference still runs on the web container.
  - **Recommendation:** ship **(B) in Phase 2-B** (unblocks the event loop immediately, zero API/frontend change) and treat **(A)** as a fast-follow once thumbnails/queues are proven. Flag for your call.

## 8. Migration Strategy for Existing Photos
- Existing photos **already have embeddings** (JSON + `vector(512)`) from the old pipeline → **no re-embedding required**.
- They lack thumbnails → `backfill_thumbnails()` one-off (idempotent, batched, rate-limited so it doesn't saturate S3/CPU). Triggered via a management command / one-off Celery task post-deploy.
- Photos stuck in `pending`/`processing` from the old path → `reset_stuck_processing` picks them up and routes through Celery.
- No data is destroyed; backfill only **adds** `thumb_key`.

## 9. HNSW Index Migration Plan
The index exists but is unused because the **query shape** is wrong, and matching must stay **event-scoped**.
- **Schema (migration C):** add `face_embeddings.event_id BIGINT` (denormalized) + backfill from the `photo→event` join + btree `ix_face_event(event_id)`. Needed so KNN can pre-filter by event without a join that defeats the index.
- **Rebuild HNSW** with tuned params: `m=16, ef_construction=64` (current uses defaults). Build `CONCURRENTLY`-equivalent care: creating an HNSW index locks writes; do it in a low-traffic window or build new index then swap. On a small/medium table a brief lock is acceptable; document the window.
- **Query change (code, ships with C):**
  ```sql
  SET LOCAL hnsw.ef_search = 100;
  SELECT photo_id
  FROM face_embeddings
  WHERE event_id = :eid
  ORDER BY embedding_vec <=> :q
  LIMIT 100;
  -- then keep ids whose (1 - cosine_distance) >= :threshold, in app
  ```
  Index-backed KNN, event-scoped, no full scan. SQLite/legacy-NULL fallback (pure-Python cosine) stays for dev + un-backfilled rows.
- **Validation:** `EXPLAIN (ANALYZE)` in a PG integration test asserts an **Index Scan using ix_face_hnsw** (not Seq Scan), and that results match the old range-scan output on a seeded set.

## 10. Rollback Plan
- **`USE_CELERY` flag:** off → ingest reverts to BackgroundTasks/daemon-thread + the retention loop re-enables in web. Instant, no redeploy of code.
- **Workers:** scale `face`/`thumbs`/`beat` replicas → 0 to disable async tier; web keeps serving.
- **Migrations reversible:** `thumb_key` and `face_embeddings.event_id` each have `downgrade()` dropping the column; HNSW rebuild keeps the old index until the new one is verified (swap, don't drop-first).
- **Matching query** behind the same revertable commit; if KNN misbehaves, revert C's code hunk to the range-scan while keeping the columns (no data change).
- Each step (A–D) is an isolated commit/PR → revert any one without touching the others.

---

## Implementation order (small commits, tests + deploy notes each)
- **A. Celery infrastructure** — `celery_app.py`, queues, config, worker/beat compose services, `USE_CELERY` flag, a trivial `ping` task. *Tests:* task registered, eager-mode unit test. *Deploy:* add worker+beat containers; Redis already present.
- **B. Face-processing migration** — move `process_photo` to Celery; ingest paths enqueue; remove retention loop from web → beat; guest selfie → threadpool (option B). *Tests:* enqueue called on upload; idempotent reprocess; selfie no longer blocks (threadpool). *Deploy:* set `USE_CELERY=true`; scale face worker.
- **C. HNSW migration** — add `event_id` + backfill + tuned index; rewrite matching to KNN. *Tests:* PG integration: EXPLAIN uses index, KNN == range-scan results at threshold, event isolation. *Deploy:* run migration in low-write window; verify EXPLAIN in prod.
- **D. Thumbnail generation** — `thumb_key` column, `make_thumbnail` task, ingest enqueues, list endpoints return thumbs, `backfill_thumbnails`; frontend `next/image`. *Tests:* thumb created + key stored; list returns thumb URL; backfill enqueues null-key photos. *Deploy:* run backfill one-off; set CDN `remotePatterns`.

## Open decisions for reviewer
1. **Guest matching:** option **(B) threadpool now** (recommended) vs **(A) Celery+poll now** (more work, needs frontend change)?
2. **HNSW rebuild window:** brief write-lock acceptable, or build-new-then-swap (more careful, more steps)?
3. **Drop the duplicate JSON `embedding`** column once KNN is proven (saves ~50% table size), or keep as SQLite-dev fallback? (Recommend: keep for now, drop in Phase 3.)
