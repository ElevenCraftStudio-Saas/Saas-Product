# WedFind AI — Production SaaS Blueprint (v2)

> Clean-architecture rebuild blueprint. Existing repo is a **feature reference** only.
> Roles: `admin`, `user` (guest = anonymous, not a role). No pending/approval state.
> Every secret comes from the environment. No SQLite fallback. Jobs never run in web workers.

---

## 1. Complete Architecture

```
                          ┌──────────────────────────┐
        Browser  ───────► │  Next.js 16 (Vercel)     │  app.<domain>
        (studio/guest)    │  App Router, TS, Tailwind│
                          └─────────────┬────────────┘
                                        │ HTTPS (Firebase ID token / public)
                                        ▼
                          ┌──────────────────────────┐
   Desktop Agent ───X-API-Key──────────►            │  api.<domain>
   (Windows, watchdog)    │  FastAPI (uvicorn/gunicorn)│
                          │  routers→services→repos    │
                          └───┬───────────┬────────┬───┘
                              │           │        │
                  ┌───────────▼──┐  ┌─────▼────┐ ┌─▼─────────┐
                  │ PostgreSQL   │  │  Redis   │ │  AWS S3   │
                  │ + pgvector   │  │ (broker  │ │ originals │
                  │ (RDS)        │  │  + cache)│ │ +thumbs   │
                  └──────────────┘  └────┬─────┘ └───────────┘
                                         │ broker
                              ┌──────────▼───────────┐
                              │  Celery workers       │  (separate containers)
                              │  face / thumbs /      │
                              │  cleanup / retention  │
                              │  InsightFace buffalo_l│
                              └──────────┬────────────┘
                                         │ beat (scheduler)
                                         ▼
                              retention sweep, orphan cleanup
        Sentry ◄── all services (errors)      Prometheus ◄── /metrics
```

**Principles**
- **Layered backend:** `routers` (HTTP/DTO/RBAC) → `services` (business logic) → `repositories` (DB access) → `models`. Workers reuse `services`/`repositories`, never `routers`.
- **No work in request path:** face detection, embedding, thumbnails, ZIP packaging, retention → Celery. Web stays I/O-bound and fast.
- **Stateless web tier:** horizontally scalable; all state in Postgres/Redis/S3. Single Celery-beat replica owns schedules (no duplicate sweeps).
- **Fail-fast config:** pydantic `Settings` validates at import; missing required var → process refuses to boot.

---

## 2. Folder Structure

```
wedfind/
├─ backend/
│  ├─ app/
│  │  ├─ main.py                 # app factory, middleware, lifespan, /livez /readyz
│  │  ├─ config.py               # pydantic Settings (fail-fast)
│  │  ├─ db.py                   # engine, SessionLocal, get_db
│  │  ├─ core/
│  │  │  ├─ firebase.py          # ID-token verify (leeway, aud/iss/RS256)
│  │  │  ├─ security.py          # security-headers middleware, CORS builder
│  │  │  ├─ limiter.py           # SlowAPI + Redis storage
│  │  │  ├─ rbac.py              # require_user / require_admin / get_current_user
│  │  │  ├─ logging.py           # structlog JSON config
│  │  │  └─ metrics.py           # Prometheus instrumentator
│  │  ├─ models/                 # SQLAlchemy ORM (one file per aggregate or models.py)
│  │  ├─ schemas/                # Pydantic DTOs (request/response), pagination
│  │  ├─ repositories/           # query objects: user_repo, event_repo, photo_repo …
│  │  ├─ services/               # event_service, photo_service, match_service,
│  │  │                          #   quota_service, token_service, admin_service
│  │  ├─ routers/
│  │  │  ├─ public.py            # /api/guest/*  (anonymous)
│  │  │  ├─ auth.py              # /api/auth/me
│  │  │  ├─ events.py photos.py  # /api/events, /api/photos  (require_user)
│  │  │  └─ admin.py             # /api/admin/*  (require_admin)
│  │  ├─ workers/
│  │  │  ├─ celery_app.py        # Celery factory (Redis broker/result)
│  │  │  ├─ face_tasks.py        # detect+embed → pgvector
│  │  │  ├─ thumb_tasks.py       # thumbnail generation
│  │  │  └─ maintenance.py       # retention sweep, orphan cleanup (beat)
│  │  └─ utils/                  # qr, s3, hashing, image validation
│  ├─ alembic/versions/          # migrations (DDL incl. cascades, HNSW)
│  ├─ tests/                     # unit / integration / pg / migration / rbac / match
│  ├─ pyproject.toml             # deps, ruff, pytest, coverage config
│  └─ Dockerfile
├─ frontend/                     # Next.js 16 (see §5)
│  ├─ app/  components/  lib/
│  └─ Dockerfile
├─ agent/                        # Windows desktop uploader
├─ docker-compose.yml            # local full stack
├─ .github/workflows/ci.yml      # test → build → migrate → deploy
└─ docs/
```

---

## 3. Database Schema (ERD + DDL)

```
users ─1──<┐ events ─1──<┐ photos ─1──<┐ face_embeddings (vector(512), HNSW)
  │        │   │         │   │         ├──< downloads
  │        │   │         │   └─────────┘
  │        │   ├──< guest_consents
  │        │   ├──< folder_watches
  │        │   └──< activity_logs (event_id nullable, SET NULL)
  └──< api_tokens (assigned_user_id)
```

All FKs have explicit `ON DELETE` behavior. Deleting an event cascades to its photos → embeddings/downloads, consents, folder_watches; nulls activity_logs.event_id.

```sql
CREATE TABLE users (
  id            BIGSERIAL PRIMARY KEY,
  firebase_uid  TEXT NOT NULL UNIQUE,
  email         CITEXT UNIQUE,
  name          TEXT,
  role          TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin','user')),
  max_events       INT,            -- NULL => DEFAULT_EVENT_LIMIT
  storage_limit_mb INT,            -- NULL => DEFAULT_STORAGE_LIMIT_MB
  storage_used_bytes BIGINT NOT NULL DEFAULT 0,  -- denormalized counter
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE events (
  id           BIGSERIAL PRIMARY KEY,
  owner_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name         TEXT NOT NULL,
  slug         TEXT NOT NULL UNIQUE,
  event_date   TIMESTAMPTZ NOT NULL,
  retention_days INT,
  consent_text TEXT,
  qr_key       TEXT,            -- S3 key for QR png
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_events_owner ON events(owner_id);

CREATE TABLE photos (
  id            BIGSERIAL PRIMARY KEY,
  event_id      BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  filename      TEXT NOT NULL,
  s3_key        TEXT NOT NULL,
  thumb_key     TEXT,
  size_bytes    BIGINT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','processing','completed','failed')),
  uploaded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (event_id, filename)               -- server-side dedup
);
CREATE INDEX ix_photos_event_status ON photos(event_id, status);

CREATE TABLE face_embeddings (
  id         BIGSERIAL PRIMARY KEY,
  photo_id   BIGINT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
  event_id   BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,  -- denormalized for event-scoped KNN
  embedding  vector(512) NOT NULL,
  face_box   JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_face_event ON face_embeddings(event_id);
CREATE INDEX ix_face_hnsw ON face_embeddings
  USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);

CREATE TABLE api_tokens (
  id            BIGSERIAL PRIMARY KEY,
  assigned_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_by    BIGINT REFERENCES users(id) ON DELETE SET NULL,  -- the admin
  name          TEXT,
  token_prefix  TEXT NOT NULL,
  token_hash    TEXT NOT NULL UNIQUE,    -- HMAC-SHA256(pepper, token)
  revoked       BOOLEAN NOT NULL DEFAULT false,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at  TIMESTAMPTZ
);
CREATE INDEX ix_tokens_user ON api_tokens(assigned_user_id);

CREATE TABLE guest_consents (
  id           BIGSERIAL PRIMARY KEY,
  event_id     BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  ip_hash      TEXT,                 -- hashed, not raw IP
  consent_version TEXT NOT NULL,
  consent_text TEXT,
  user_agent   TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_consents_event ON guest_consents(event_id);

CREATE TABLE downloads (
  id          BIGSERIAL PRIMARY KEY,
  photo_id    BIGINT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
  ip_hash     TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_downloads_photo ON downloads(photo_id);

CREATE TABLE folder_watches (
  id          BIGSERIAL PRIMARY KEY,
  event_id    BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  folder_path TEXT NOT NULL,
  enabled     BOOLEAN NOT NULL DEFAULT true,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_scan_at TIMESTAMPTZ
);
CREATE INDEX ix_watches_event ON folder_watches(event_id);

CREATE TABLE activity_logs (
  id         BIGSERIAL PRIMARY KEY,
  action     TEXT NOT NULL,
  event_id   BIGINT REFERENCES events(id) ON DELETE SET NULL,
  actor      TEXT,                  -- user id or 'guest'
  ip_hash    TEXT,
  detail     JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_activity_event_created ON activity_logs(event_id, created_at DESC);
CREATE INDEX ix_activity_action ON activity_logs(action);
```

**vs current repo (fixes):** single `vector(512)` (no duplicate JSON) · `event_id` denormalized onto `face_embeddings` for event-scoped HNSW KNN · real `ON DELETE CASCADE`/`SET NULL` everywhere · `storage_used_bytes` counter (no per-upload SUM) · IPs hashed (DPDP) · `(event_id, created_at)` + `downloads.photo_id` indexes.

---

## 4. API Specification

DTOs via Pydantic; all list endpoints paginated `?limit=&cursor=` (keyset). OpenAPI auto-served at `/docs` (gated behind admin in prod).

### Public (anonymous, rate-limited, Redis-backed)
| Method | Path | Limit | Purpose |
|---|---|---|---|
| GET | `/api/guest/{slug}` | 30/min | event meta |
| POST | `/api/guest/{slug}/selfie` | 10/min | consent + enqueue match → returns job id |
| GET | `/api/guest/{slug}/matches/{job}` | 30/min | poll match result (photo ids + thumb urls) |
| GET | `/api/guest/{slug}/photos/{id}/download` | 30/min | presigned original url |
| POST | `/api/guest/{slug}/download-zip` | 5/min | enqueue ZIP build → job id |
| GET | `/api/guest/{slug}/zip/{job}` | 30/min | presigned zip url when ready |
| POST | `/api/guest/{slug}/erase` | 5/min | DPDP erasure |

### Auth (any authenticated)
| GET | `/api/auth/me` | current user + role (admin-allowlist applied) |

### User (`require_user`, owner-scoped)
| POST/GET | `/api/events` | create (quota) / list own (paginated) |
| GET/PATCH/DELETE | `/api/events/{id}` | own event |
| POST | `/api/events/{id}/upload` | browser upload (quota) → enqueue face+thumb |
| GET | `/api/events/{id}/photos` | paginated, page-signed thumbs only |
| GET | `/api/events/{id}/analytics` | own-event analytics |
| GET/PATCH | `/api/events/{id}/privacy` | retention/consent text |
| POST/GET/DELETE | `/api/events/{id}/watch-folders` | folder watch (local-deploy) |

### Admin (`require_admin`, global)
| GET | `/api/admin/users` | paginated; name/email/role/events/limits/storage |
| PATCH | `/api/admin/users/{id}/role` | user↔admin, **last-admin lock** |
| PATCH | `/api/admin/users/{id}/limit` · `/storage` | quotas |
| POST/GET/DELETE | `/api/admin/tokens` | create (assigned_user_id) / list / revoke |
| GET | `/api/admin/audit` | global audit (paginated) |
| GET | `/api/admin/analytics` | global analytics |

### Health/ops
`GET /livez` (process up, no deps) · `GET /readyz` (DB+Redis+S3+model loaded → **503 when degraded**) · `GET /metrics` (Prometheus, internal).

---

## 5. Frontend Routes (Next.js 16 App Router)

```
app/
  page.tsx                       /            → redirect /login
  (auth)/login/page.tsx          /login       Firebase Google + email; redirect by role
  event/[slug]/page.tsx          /event/[slug] PUBLIC guest flow (consent→selfie→gallery→zip)
  (dashboard)/layout.tsx                       guard role==='user' (admin→/admin/users)
    dashboard/page.tsx           /dashboard    events list, create, quota+storage usage
    events/[id]/page.tsx         /events/[id]  upload, folder-watch, privacy, activity, downloads
  (admin)/layout.tsx                           guard role==='admin' (user→/dashboard)
    admin/users/page.tsx         /admin/users  table + promote/demote + edit limits + create token
    admin/tokens/page.tsx        /admin/tokens create(pick user)/list/revoke
    admin/audit/page.tsx         /admin/audit  global log (paginated)
    admin/analytics/page.tsx     /admin/analytics totals + per-event
```
- `useMe()` → `/api/auth/me`; layouts role-gate (non-matching role redirected, never rendered).
- Images via `next/image` + `remotePatterns` for the CDN; gallery uses **thumbnails**, originals only on download.
- Polling replaced by job-id polling with backoff that stops when status terminal.

---

## 6. Admin Workflows
1. **Bootstrap:** run `python scripts/make_admin_firestore.py owner@email.com` after the user's first login; or find the user's Firestore doc in the console and set `role: "admin"`.
2. **Manage user:** edit `max_events` / `storage_limit_mb` inline; **Promote to Admin** / **Demote to User** (blocked if it would remove the last admin → 400).
3. **Agent token:** `/admin/tokens` → pick a `user` → create → plaintext shown **once** → hand to studio for the desktop agent. Revoke anytime.
4. **Oversight:** global audit log + analytics across all studios.

## 7. User Workflows
Login → `/dashboard` (auto `role=user`). Create event (quota-checked) → QR + guest link generated. Upload photos (browser or agent) → async face+thumb. Configure privacy/retention. Watch event activity + downloads. Cannot reach `/admin/*` (frontend guard + backend `require_admin` 403).

## 8. Guest Workflows
Open `/event/[slug]` (QR) → consent (recorded, IP hashed) → selfie → **enqueued** match job → poll → gallery of matched **thumbnails** → download originals (presigned) or request ZIP (enqueued). No account. Selfie + its embedding never persisted. One-click DPDP erasure.

---

## 9. Face-Recognition Architecture

```
upload (web/agent) → photo row (status=pending) → S3 put
        └─► Celery: face_tasks.process(photo_id)
               status=processing → S3 get → InsightFace buffalo_l (worker, CPU/GPU)
               → vector(512) per face → INSERT face_embeddings(embedding, event_id)
               → status=completed   (failed path → status=failed, retried w/ backoff)
        └─► Celery: thumb_tasks.make(photo_id) → 400px WebP → S3 thumb_key

guest selfie → Celery: face_tasks.match(event_id, selfie_bytes)
               detect 1 face → embedding → KNN:
```
```sql
SELECT photo_id
FROM face_embeddings
WHERE event_id = :eid
ORDER BY embedding <=> :q          -- HNSW cosine, index-backed
LIMIT 100;
-- then filter (1 - cosine_distance) >= :threshold in app (default 0.6)
```
- **HNSW index used** (KNN `ORDER BY <=> LIMIT`), event-scoped via `WHERE event_id` + `ix_face_event`. `SET LOCAL hnsw.ef_search = 100` per query.
- **Never in request handler** — all inference in Celery workers (own model copy; scale worker replicas independently of web).
- Idempotent tasks; orphaned `processing` rows reset by a beat job.

---

## 10. Security Architecture
- **Transport:** TLS at LB; `HTTPSRedirectMiddleware` + HSTS (`max-age=63072000; includeSubDomains; preload`).
- **Headers middleware:** `Content-Security-Policy` (locked to self + CDN + Firebase), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`.
- **AuthN:** Firebase ID token verified server-side — RS256, `aud=PROJECT_ID`, `iss=securetoken.google.com/<proj>`, `leeway=30s` (fixes clock-skew 401s), `sub` required.
- **AuthZ (RBAC):** `require_user` / `require_admin` deps; role from DB synced from Firestore (source of truth); last-admin-lock on demotion.
- **Rate limiting:** SlowAPI with **Redis** storage (shared across replicas); trusted-proxy `X-Forwarded-For` only behind known hops.
- **Uploads:** extension + MIME + **magic-byte** sniff (Pillow verify) + size cap; folder-watch confined to `WATCH_BASE_DIR` allowlist.
- **S3:** Block Public Access ON; objects private; **presigned** GET (≤1h) / PUT; CloudFront with signed URLs in front.
- **Secrets:** all from env via `Settings`; production injects via AWS Secrets Manager / SSM; **no static IAM keys** — task role / instance profile. API tokens stored as `HMAC-SHA256(pepper, token)`, plaintext shown once.
- **PII/DPDP:** IPs hashed; consent ledger; retention auto-purge; right-to-erasure; selfies never stored.
- **Cookies:** Firebase session handled client-side; any server cookie `Secure; HttpOnly; SameSite=Lax`.

### config.py (fail-fast)
```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    DATABASE_URL: str                      # postgresql+psycopg://…  (no sqlite fallback)
    REDIS_URL: str
    AWS_REGION: str
    AWS_ACCESS_KEY_ID: str | None = None    # None when using task role
    AWS_SECRET_ACCESS_KEY: str | None = None
    S3_BUCKET: str
    FIREBASE_PROJECT_ID: str
    FIREBASE_CLIENT_EMAIL: str
    FIREBASE_PRIVATE_KEY: str
    FRONTEND_URL: str
    SENTRY_DSN: str | None = None
    DEFAULT_EVENT_LIMIT: int = 2
    DEFAULT_STORAGE_LIMIT_MB: int = 2048
    WATCH_BASE_DIR: str | None = None
    ENV: str = "production"

    # Roles are managed in Firestore (see services/firestore_service.py).
    # The ADMIN_EMAILS env-var approach has been removed.

settings = Settings()   # raises at import if a required var is missing → process won't boot
```

---

## 11. Docker Setup

**backend/Dockerfile** (bakes the model; no cold-start download):
```dockerfile
FROM python:3.11-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/pyproject.toml backend/poetry.lock* ./
RUN pip install -e .
# Pre-download InsightFace buffalo_l into the image (~300MB)
RUN python -c "from insightface.app import FaceAnalysis; FaceAnalysis(name='buffalo_l').prepare(ctx_id=-1)"
COPY backend/ .
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fsS http://localhost:8000/livez || exit 1
CMD ["gunicorn","app.main:app","-k","uvicorn.workers.UvicornWorker","-w","4","-b","0.0.0.0:8000"]
```
Worker image reuses the same base: `CMD ["celery","-A","app.workers.celery_app","worker","-c","2"]`; beat: `… beat`.
**frontend/Dockerfile:** `node:20-alpine`, `next build`, `output: "standalone"`, `next start` (or deploy to Vercel).

**docker-compose.yml** (local full stack):
```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment: { POSTGRES_PASSWORD: dev, POSTGRES_DB: wedfind }
    ports: ["5432:5432"]
    volumes: [pg:/var/lib/postgresql/data]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
  api:
    build: { context: ., dockerfile: backend/Dockerfile }
    env_file: [backend/.env]
    depends_on: [db, redis]
    ports: ["8000:8000"]
    command: ["sh","-c","alembic upgrade head && gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000"]
  worker:
    build: { context: ., dockerfile: backend/Dockerfile }
    env_file: [backend/.env]
    depends_on: [db, redis]
    command: ["celery","-A","app.workers.celery_app","worker","-c","2"]
  beat:
    build: { context: ., dockerfile: backend/Dockerfile }
    env_file: [backend/.env]
    depends_on: [db, redis]
    command: ["celery","-A","app.workers.celery_app","beat"]
volumes: { pg: {} }
```

---

## 12. CI/CD Setup

**.github/workflows/ci.yml**
```yaml
name: ci
on: { push: { branches: [main] }, pull_request: {} }
jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env: { POSTGRES_PASSWORD: test, POSTGRES_DB: test }
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U postgres" --health-interval 5s --health-timeout 5s --health-retries 10
      redis: { image: redis:7, ports: ["6379:6379"] }
    env:
      DATABASE_URL: postgresql+psycopg://postgres:test@localhost:5432/test
      REDIS_URL: redis://localhost:6379/0
      # …minimal required env for Settings to boot…
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e "backend[dev]"
      - run: ruff check backend
      - run: alembic -c backend/alembic.ini upgrade head     # migration test (real PG)
      - run: pytest backend --cov=app --cov-fail-under=80
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd frontend && npm ci && npm run lint && npm run build
  deploy:
    needs: [backend, frontend]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "build+push images, then run 'alembic upgrade head' as a one-off release task before traffic shift"
```
Pipeline: **lint → migrate-on-real-Postgres → pytest (≥80%) → frontend build → (main) build/push images + migrate + deploy.**

---

## 13. Testing Plan (target ≥80%)

| Layer | Scope |
|---|---|
| **Unit** | quota math, RBAC deps (`require_user`/`require_admin`), cosine/threshold, token HMAC, magic-byte validation, slug gen |
| **Integration (FastAPI TestClient)** | event CRUD owner-scoping, photo upload→enqueue, admin user/limit/role + last-admin lock, token create/assign/resolve/revoke, guest consent→match→download, erasure |
| **PostgreSQL (real pgvector, CI service)** | KNN `ORDER BY <=> LIMIT` returns correct ids at threshold; HNSW used (`EXPLAIN` shows index scan); event isolation |
| **Migration** | `alembic upgrade head` on clean PG matches `Base.metadata`; `downgrade` reversible; cascade behavior (delete event → rows gone) |
| **RBAC/security** | user→admin route = 403; guest→user route = 403; promote-to-admin; cross-tenant IDOR on every user route; spoofed XFF doesn't bypass; magic-byte rejects disguised file |
| **Face matching** | seeded embeddings straddling threshold; `process_photo_faces` happy + failure (status transitions); thumbnail task |
| **Worker** | Celery task idempotency; orphan-`processing` reset; retention purge + S3 delete |

Coverage gate enforced in CI (`--cov-fail-under=80`). Postgres-backed tests run as a CI service (the current SQLite-only harness is the #1 coverage gap).

---

## 14. Production Deployment Guide
1. **Provision:** RDS Postgres + `CREATE EXTENSION vector;` (private subnet) · ElastiCache Redis · S3 bucket (Block Public Access ON) + CloudFront (signed URLs) · ECR repos · Secrets Manager entries for every `Settings` var.
2. **DNS/TLS:** `app.<domain>` → Vercel (or frontend container behind ALB) · `api.<domain>` → ALB→ECS, ACM cert, HSTS.
3. **Deploy:** CI builds images → ECS services: `api` (web), `worker` (Celery, scale on queue depth), `beat` (replicas=1). Run `alembic upgrade head` as a one-off task **before** shifting traffic.
4. **Bootstrap admin:** run `python scripts/make_admin_firestore.py owner@email.com` after the owner signs in once; or set `role: "admin"` on the user's Firestore doc manually.
5. **Probes:** ALB target group health = `/readyz` (503 when degraded); ECS container health = `/livez`.
6. **Observability:** Sentry DSN set; structured JSON logs → CloudWatch; `/metrics` scraped by Prometheus/Grafana; alarms on 5xx, queue depth, RDS conns, worker failures.
7. **Backups:** RDS automated snapshots + PITR; S3 versioning + lifecycle (retention).
8. **Scale:** web on CPU/RPS; workers on Redis queue depth; one beat. DB pool tuned (`pool_size`, `max_overflow`, `pool_recycle=1800`, `pool_pre_ping`).

---

## 15. Production Readiness Checklist
**Config/secrets** ☐ pydantic Settings fail-fast ☐ no SQLite fallback ☐ all secrets in Secrets Manager ☐ no static IAM key (task role) ☐ `API_TOKEN_PEPPER` set
**Security** ☐ HTTPS+HSTS+CSP+headers ☐ Firebase `leeway=30` ☐ RBAC + last-admin lock ☐ Redis rate limit ☐ magic-byte upload check ☐ folder-watch base-dir confine ☐ S3 Block-Public-Access + presigned/CloudFront ☐ IPs hashed
**Scale/perf** ☐ Celery workers (no inference in web) ☐ HNSW KNN query (index-backed) ☐ thumbnails + next/image + CDN ☐ pagination on all lists ☐ storage counter (no per-upload SUM) ☐ DB pool tuned ☐ job-id polling stops when terminal
**Data** ☐ FK `ON DELETE CASCADE`/`SET NULL` ☐ indexes (event_id, created_at; downloads.photo_id) ☐ single `vector(512)` (no dup JSON) ☐ migrations reversible
**Ops** ☐ Dockerfile bakes model ☐ docker-compose ☐ CI (lint+migrate+pytest≥80%+build) ☐ `/livez`+`/readyz` (503 degraded) ☐ Sentry ☐ structured logs ☐ `/metrics` ☐ RDS backups+PITR ☐ S3 versioning
**Product** ☐ Firestore admin bootstrap (scripts/make_admin_firestore.py) ☐ no pending state ☐ guest anonymous ☐ desktop agent token=assigned user ☐ OpenAPI gated in prod

---

### Migration path from the current repo (since most logic exists)
Reuse as services: face_processing, matching (rewrite to KNN), photo_ingest, s3, qr, retention, activity, api_tokens, folder_watcher, the whole guest/admin/event router logic, and the Next.js pages (already roles admin/user, admin split into routes). **Net-new for v2:** `config.py` Settings, Celery `workers/`, security-headers middleware, `/livez`+`/readyz`, Sentry, thumbnails, the cascade+HNSW+counter migration, `repositories/` layer, Redis rate-limit storage, Dockerfiles, compose, CI. This is the smallest path to the blueprint without discarding tested code.
```
