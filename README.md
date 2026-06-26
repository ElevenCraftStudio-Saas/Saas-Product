# WedFind AI

> AI-powered wedding photo delivery. A studio uploads event photos; each guest scans a QR code, gives consent, takes a selfie, and instantly receives **only their own** photos via face recognition — then downloads them.

**Live:** frontend → `https://wedfind.elevencraftstudio.com` · API → `https://api.wedfind.elevencraftstudio.com`

```
Studio: login → create event → QR → upload photos (or auto-watch folder)
Guest:  scan QR → consent → selfie → AI face match → see only your photos → download
```

Privacy-first, built for Indian wedding studios (DPDP-aware).

---

## Table of Contents
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Architecture](#-architecture)
- [Repository Layout](#-repository-layout)
- [Access Model (public vs protected)](#-access-model)
- [Local Development](#-local-development)
- [Configuration](#-configuration)
- [Testing](#-testing)
- [Production Deployment (AWS + Vercel)](#-production-deployment-aws--vercel)
- [Key API Endpoints](#-key-api-endpoints)
- [Security & Privacy](#-security--privacy)
- [Operations](#-operations)
- [Roadmap](#-roadmap)

---

## ✨ Features

- **Studio dashboard** — Firebase auth (Email/Google), event creation, QR generation, photo upload to S3, per-event stats.
- **Admin console** — single system admin manages all users, sets per-user **event + storage quotas**, views global analytics, audit log, and agent API tokens. Admin and studio are separate, role-gated areas (enforced server-side).
- **AI face matching** — InsightFace `buffalo_l` 512-dim embeddings + cosine similarity (threshold 0.60), strictly event-scoped, single-face enforced.
- **pgvector vector search** — HNSW cosine index on a `vector(512)` column with `event_id` denormalized for fast event-scoped KNN.
- **Async processing** — Celery + Redis run the heavy work (face embeddings, thumbnails, maintenance) off the request path; FastAPI stays responsive.
- **Guest flow (no login)** — consent-gated, live selfie capture (`getUserMedia`) with file-upload fallback, matched gallery, signed-URL downloads, bulk ZIP.
- **Desktop ingest agent** — optional app the studio runs on its editing machine; watches a folder and pushes new photos via a studio **API key** (works when the backend is in the cloud and can't see the studio's disk). See [agent/](agent/).
- **Privacy / DPDP** — biometric consent (text + version + IP + timestamp) recorded before processing; configurable retention with auto-purge; right-to-erasure; selfies never persisted.
- **Observability** — structured JSON logs with request IDs, Prometheus `/metrics`, Sentry hooks, health probes (`/livez`, `/readyz`, `/healthz`).
- **Hardening** — per-IP rate limiting (SlowAPI), security headers, HTTPS redirect in production, S3 cleanup on event delete.

---

## 🧱 Tech Stack

| Layer | Tech |
|-------|------|
| **Frontend** | Next.js 16 (App Router), React 19, TypeScript, Tailwind v4, Base UI, TanStack Query, Axios, React Hook Form, Zod |
| **Backend** | FastAPI, Gunicorn/Uvicorn, SQLAlchemy, Pydantic v2 (fail-fast settings) |
| **Async** | Celery + Redis (broker + result backend); queues: `default, face, thumbs, maintenance` |
| **Database** | PostgreSQL 16 + **pgvector** (HNSW), Alembic migrations, psycopg v3 |
| **Auth / RBAC** | Firebase ID tokens (verified via Google public certs — PyJWT + cryptography); roles in **Firestore** (admin / user) |
| **Face AI** | InsightFace `buffalo_l`, ONNXRuntime, OpenCV, NumPy |
| **Storage** | AWS S3 (boto3), presigned URLs, thumbnails |
| **Frontend tests** | Vitest, React Testing Library, MSW, jsdom |
| **E2E** | Playwright (Chromium) against the real stack |
| **Backend tests** | pytest, httpx (SQLite + S3/face mocks) |
| **Infra** | Terraform (AWS), Docker / Docker Compose, Caddy (auto-HTTPS), Vercel (frontend) |

---

## 🏗️ Architecture

```
                       ┌─────────────────────────────┐
   Browser  ──HTTPS──► │ Vercel (Next.js frontend)   │
   (studio/guest)      └──────────────┬──────────────┘
                                      │  api.* (HTTPS)
                                      ▼
                       ┌─────────────────────────────┐        ┌──────────────┐
                       │ EC2 host (Docker)           │        │ Firebase     │
                       │  Caddy ─► gunicorn/FastAPI ─┼──auth──► (tokens+roles)│
                       │          Celery worker      │        └──────────────┘
                       │          Celery beat        │
                       └───┬─────────┬──────────┬────┘
                           │         │          │
                     ┌─────▼───┐ ┌───▼────┐ ┌───▼──────┐
                     │ RDS     │ │ Redis  │ │ S3       │
                     │ pgvector│ │ Elasti │ │ (photos) │
                     └─────────┘ └────────┘ └──────────┘
                      (private)   (private)   (private + presigned)
```

- The upload pipeline is single-source — manual upload and the folder watcher reuse the same ingest service.
- Face embedding + thumbnailing run as Celery tasks; the API only enqueues.
- RDS, Redis, and S3 are not internet-reachable; only the app host talks to them. Secrets come from AWS Secrets Manager via the EC2 instance role (no static AWS keys).

---

## 📁 Repository Layout

```
backend/
  alembic/                 migrations (schema source of truth)
  app/
    core/                  firebase token verify/init, limiter, request-id, security headers
    routers/               auth, events, photos, guest, admin
    services/              face_processing, s3_service, matching, firestore_service, ...
    workers/               celery_app + tasks
    models/ schemas/ utils/
  tests/                   pytest suite (auth, events, ingest, guest, zip, privacy, admin, reliability)
frontend/
  app/                     (dashboard), (admin), (auth), event/[slug] guest flow
  components/              dashboard, events, guest, photos, layout, common, ui
  lib/ services/ types/    typed API client, TanStack Query hooks, domain services
  test/                    Vitest unit/integration (MSW)
  e2e/                     Playwright specs + page objects
agent/                     desktop ingest agent (watchdog + API key push)
deploy/
  terraform/               VPC, subnets, SGs, EC2, RDS(pgvector), ElastiCache, S3, IAM, Secrets, CloudWatch
  compose/                 docker-compose.staging.yml + Caddyfile
  scripts/                 fetch-secrets, deploy, rollback, rotate-firebase-key
  runbooks/                deployment, secrets, monitoring, rollback, validation, firebase-key-rotation
```

---

## 🔐 Access Model

| Tier | Who | Surface |
|------|-----|---------|
| **Public** | anyone, no login | Login/signup page; guest flow (`/event/<slug>` → consent → selfie → gallery → download); health endpoints; `GET /api/guest/*`, selfie match, guest downloads |
| **Authenticated** | any signed-in user (Firebase token) | `/api/auth/me`, `/api/events`, `/api/photos`; frontend `/dashboard`, `/events`, `/profile`, `/settings` |
| **Admin** | role = `admin` | `/api/admin/*` (analytics, users, role/quota changes, tokens); frontend `/admin/*` |
| **Never public** | — | Postgres, Redis, S3 (direct), `/metrics`, Secrets Manager, server shell (SSM-only), Celery worker/beat |

The app is open to the internet (as a SaaS must be); data and infrastructure are sealed behind the authenticated API.

---

## 🚀 Local Development

### Prerequisites
- Python 3.11+, Node.js 20+, Docker (for the all-in-one stack)
- A Firebase project (Email/Google enabled)
- An AWS S3 bucket (for real photo storage) — optional for pure UI work

### Option A — Docker (full stack, recommended)
Brings up Postgres + Redis + API + Celery worker + beat.
```bash
cp backend/.env.example backend/.env          # fill values
# place your Firebase service-account JSON at backend/firebase-service-account.json
docker compose up -d --build                  # API on http://localhost:8002
```
Frontend:
```bash
cd frontend
cp .env.example .env.local                    # set NEXT_PUBLIC_API_URL=http://localhost:8002/api + Firebase web config
npm install
npm run dev                                    # http://localhost:3000
```

### Option B — Hybrid (db+redis in Docker, API local on :8000)
```bash
docker compose up -d db redis
cd backend && python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
# separate terminal — worker:
celery -A app.workers.celery_app worker -Q default,face,thumbs,maintenance -c 2 --loglevel=info
```

> First backend start downloads the InsightFace `buffalo_l` model (~300 MB).
> The selfie camera needs HTTPS on real phones (localhost is fine on desktop).

### Bootstrap an admin
```bash
# in the api container:  docker compose exec api python scripts/make_admin_firestore.py you@email.com
```

---

## ⚙️ Configuration

Secrets live in untracked env files (templates: `.env.example`). Required backend vars are validated at startup (the process refuses to boot if any is missing).

| Backend (`backend/.env`) | Frontend (`frontend/.env.local`) |
|--------------------------|----------------------------------|
| `DATABASE_URL`, `REDIS_URL` | `NEXT_PUBLIC_API_URL` |
| `AWS_REGION`, `S3_BUCKET` (or `AWS_BUCKET_NAME`) | `NEXT_PUBLIC_FIREBASE_API_KEY`, `…_APP_ID` |
| `FIREBASE_PROJECT_ID` | `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`, `…_PROJECT_ID` |
| `FIREBASE_SERVICE_ACCOUNT_B64` *or* a key file | `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET`, `…_MESSAGING_SENDER_ID` |
| `ENV`, `FRONTEND_URL`, `SENTRY_DSN`, `MATCH_THRESHOLD`, quotas | `NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID` |

On AWS, the backend reads these from **Secrets Manager** (rendered to a `600` `.env` on the host); S3 access uses the **EC2 instance role** — no static AWS keys.

---

## 🧪 Testing

**Backend** (SQLite + S3/face mocks — no AWS/RDS needed):
```bash
cd backend && .venv/Scripts/python -m pytest -q     # 117 passed, 2 skipped
```

**Frontend unit/integration** (Vitest + MSW, no live backend):
```bash
cd frontend
npm test                 # 62 passed
npm run test:coverage    # coverage with thresholds
```

**End-to-end** (Playwright, Chromium, real stack — needs a running deployment):
```bash
cd frontend
cp e2e/.env.e2e.example .env.e2e     # set E2E_BASE_URL + a real studio account + event slug
npm run e2e
```

CI: `.github/workflows/ci.yml` runs backend pytest + migrations, frontend lint + Vitest + build, and a Docker build on every push/PR. Playwright runs separately (`.github/workflows/e2e.yml`) — manual or release-candidate only.

---

## ☁️ Production Deployment (AWS + Vercel)

Infrastructure is Terraform (in [`deploy/terraform/`](deploy/terraform)); the backend runs in Docker on EC2 behind Caddy (auto-HTTPS); the frontend is hosted on Vercel.

**High level:**
1. Build + push the backend image to ECR.
2. `terraform apply` → VPC, private subnets, EC2, **RDS (pgvector, automated backups)**, **ElastiCache Redis**, **S3**, IAM instance role, Secrets Manager, CloudWatch alarms.
3. Inject the Firebase service-account key into the secret ([rotate-firebase-key.sh](deploy/scripts/rotate-firebase-key.sh)).
4. Deploy on the host (`deploy/scripts/deploy.sh <image>` over SSM): fetch secrets → pull → `compose up` (api + worker + beat + Caddy) → migrate → `/readyz` gate.
5. Point DNS at the host's Elastic IP; Caddy issues the Let's Encrypt cert.
6. Deploy the frontend to Vercel (`NEXT_PUBLIC_API_URL=https://<api-domain>/api` + Firebase config), point the web domain at Vercel.

Full step-by-step + rollback + validation are in [`deploy/runbooks/`](deploy/runbooks). Promote to production by parameter (`-var environment=production -var db_multi_az=true`).

**Security model:** no static AWS keys (instance role); secrets in Secrets Manager; private subnets for DB/Redis; S3 private + encrypted + versioned; IMDSv2; SSM-only host access; Firestore/Storage rules deny-all (client never touches them directly).

---

## 📡 Key API Endpoints

Base path: `/api`.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/livez`, `/readyz`, `/healthz` | – | Liveness / readiness (DB+Redis+S3) / health |
| GET | `/metrics` | internal | Prometheus metrics (not internet-routed) |
| GET | `/api/auth/me` | Firebase | Current user + role (auto-provisioned) |
| GET/POST/DELETE | `/api/auth/tokens` | Admin | Manage desktop-agent API keys |
| GET | `/api/admin/users` · PATCH `…/role` `…/limit` `…/storage` | Admin | Users + per-user quotas |
| GET | `/api/admin/analytics`, `/api/admin/activity` | Admin | Global analytics + audit log |
| GET/POST/DELETE | `/api/events/` | Firebase | Event CRUD + QR |
| POST | `/api/photos/upload/{event_id}` | Firebase **or** API key | Manual / agent upload |
| GET | `/api/photos/event/{id}` | Firebase | Event photos + processing status |
| GET | `/api/guest/{slug}` | Public | Public event details |
| POST | `/api/guest/{slug}/selfie` | Public (rate-limited) | Face match (event-scoped, pgvector) |
| GET | `/api/guest/{slug}/photos/{id}/download` | Public | Signed download URL |
| POST | `/api/guest/{slug}/download-zip` | Public (rate-limited) | Bulk ZIP of matched photos |

Interactive docs at `/docs` (when not disabled in production).

---

## 🔒 Security & Privacy

- **No secrets in git** — env files, service-account keys, Terraform state, venvs, and `node_modules` are gitignored.
- **RBAC** — `admin` (single system admin, minted via `scripts/make_admin_firestore.py`) and `user` (studio). Admin routes verify `role == "admin"` server-side. Roles stored in Firestore; the Firebase Admin SDK bypasses the deny-all Firestore/Storage rules, so no client can read/write them directly.
- **DPDP** — biometric consent (text + version + IP + timestamp) recorded before any face processing; configurable retention with a daily auto-purge sweeper; guest right-to-erasure; selfies matched in memory and never persisted.
- **Network** — RDS + Redis in private subnets; S3 private with presigned access; the host has no open SSH port (SSM only); IMDSv2 enforced.
- **Credentials** — AWS access via EC2 instance role (no static keys); all sensitive config in Secrets Manager; the Firebase service-account key is rotatable without code changes ([runbook](deploy/runbooks/firebase-key-rotation.md)).

---

## 🛠️ Operations

- **Deploy / rollback** — [`deploy/scripts/`](deploy/scripts) + [`deploy/runbooks/`](deploy/runbooks). The host is driven via AWS SSM (no SSH).
- **Monitoring** — CloudWatch logs (`/wedfind/<env>/app`) + alarms (EC2/RDS/Redis) → SNS; Sentry for errors; Prometheus `/metrics`. See [monitoring runbook](deploy/runbooks/monitoring.md).
- **Backups** — RDS automated backups (7-day retention) + point-in-time restore; S3 versioning.
- **Validation** — after any deploy or credential change, run the [validation checklist](deploy/runbooks/validation-checklist.md).

---

## 🗺️ Roadmap

WhatsApp delivery · Razorpay billing + studio branding · multi-AZ / multi-region HA · regional languages · CDN for thumbnails · remote Terraform state (S3 + DynamoDB lock).

---

## 📄 License

Proprietary — all rights reserved.
