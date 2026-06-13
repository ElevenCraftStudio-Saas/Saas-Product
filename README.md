# WedFind AI — Saas-Product

AI-powered wedding photo delivery. A studio uploads (or auto-syncs) event photos; each guest scans a QR code, gives consent, takes a selfie, and instantly gets **only their own** photos via face recognition — then downloads them.

> Studio Login → Create Event → Generate QR → Upload / Auto-watch folder → Guest scans QR → Consent → Selfie → AI face matching → Guest sees only their photos → Downloads

Privacy-first, built for Indian wedding studios (DPDP-aware).

---

## ✨ Features

- **Studio dashboard** — Firebase auth (Email/Google), event creation, QR generation, photo upload to S3
- **Auto folder upload** — point an event at a local folder; new photos are detected (watchdog) and uploaded + processed automatically, surviving backend restarts
- **Desktop ingest agent** — standalone app the studio installs on its editing machine; watches a local folder and pushes new photos via a studio **API key** (zero browser, zero manual upload). Works when the backend runs in the cloud and can't see the studio's disk. See [agent/](agent/)
- **API keys** — studio-managed long-lived keys (`X-API-Key`) for the agent; create/revoke from the dashboard, sha256-hashed at rest, shown once
- **AI face matching** — InsightFace `buffalo_l` 512-dim embeddings + cosine similarity (0.60), strictly event-scoped, single-face enforced
- **pgvector vector search** — HNSW cosine index on a `vector(512)` column; dual-path matcher (Postgres `<=>` operator, with a pure-Python cosine fallback for SQLite / un-backfilled rows)
- **Guest flow (no login)** — consent-gated, live selfie capture (`getUserMedia`), matched gallery, signed-URL downloads
- **Bulk download** — guests can grab all matched photos as a single event-isolated ZIP (rate-limited, streamed)
- **Role-based access** — first user bootstraps as `studio`; everyone else `guest`; studio-only admin promotion endpoint
- **Privacy/compliance** — biometric consent (IP + version + timestamp) recorded before processing; selfies not stored permanently
- **Audit logging** — `EVENT_VIEWED`, `SELFIE_UPLOADED`, `FACE_MATCH_COMPLETED`, `PHOTO_DOWNLOADED`, upload/watch events
- **Hardening** — per-IP rate limiting (SlowAPI) on public endpoints (selfie 10/min, ZIP 5/min), S3 cleanup on event delete, `/healthz`
- **Tested** — 17-test pytest suite (auth, events, ingest, guest match, ZIP) on a SQLite test DB with S3 + face-engine mocks

---

## 🧱 Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind v4, ShadCN UI, TanStack Query, Axios, React Hook Form, Zod |
| Backend | FastAPI, Uvicorn, SQLAlchemy, Pydantic v2 |
| Database | PostgreSQL (AWS RDS) + pgvector (HNSW), Alembic migrations, psycopg v3 — SQLite fallback for local |
| Auth | Firebase (Email/Google/Phone); backend verifies ID tokens via Google public certs (PyJWT + cryptography) |
| Face AI | InsightFace `buffalo_l`, ONNXRuntime, OpenCV, NumPy |
| Storage | AWS S3 (boto3), presigned URLs |
| Folder watch | watchdog |
| Rate limit | SlowAPI |
| QR | qrcode + Pillow |
| Tests | pytest, httpx, TestClient (SQLite + mocks) |

---

## 🏗️ Architecture

```
 Studio ─► Next.js UI ─► FastAPI ─► AWS S3 (photos, QR)
 Guest  ─►            Axios       └► PostgreSQL/RDS (events, embeddings, consents, audit, folder_watches)
            ▲                         │
      Firebase Auth          InsightFace (embeddings + cosine match)
                             watchdog (auto folder upload, resumes on startup)
```

Upload pipeline is single-source (`services/photo_ingest.py`) — both the manual upload route and the folder watcher reuse it.

---

## 📁 Structure

```
backend/
  alembic/                 # migrations (schema source of truth)
  app/
    core/                  # firebase token verify, limiter
    routers/               # auth, events (+watch endpoints), photos, guest
    services/              # face_engine, face_processing, s3_service, matching,
                           #   activity, photo_ingest, folder_watcher
    models/ schemas/ utils/
  tests/                   # pytest suite (conftest + auth/events/ingest/guest/zip)
  pytest.ini
  test_db.py               # RDS connectivity check
frontend/
  app/(dashboard)/         # studio: dashboard, events (+folder watch)
  app/event/[slug]/        # guest: consent → selfie → gallery
  components/guest/        # selfie-capture, photo-gallery
  components/dashboard/    # folder-watch, privacy-panel
  app/(dashboard)/settings # API key management
  lib/                     # api, firebase, auth-context, hooks
agent/                     # desktop ingest agent (watchdog + API key push)
  wedfind_agent.py  config.example.json  requirements.txt  README.md
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+, Node.js 18+
- AWS S3 bucket + IAM credentials
- A Firebase project (enable Email/Password, Google, Phone)
- PostgreSQL (AWS RDS) — or use the SQLite fallback locally

### 1. Backend
```bash
cd backend
python -m venv ../.venv
../.venv/Scripts/activate          # Windows  (source ../.venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
cp .env.example .env               # fill in real values
alembic upgrade head               # apply DB schema
uvicorn app.main:app --port 8000
```
> First run downloads the InsightFace `buffalo_l` model (~300 MB), ~20s to load.
> Restart fully after backend edits (don't rely on `--reload` during model load).
> Verify the DB connection any time: `python test_db.py`.

### 2. Frontend
```bash
cd frontend
npm install
cp .env.example .env.local         # fill in Firebase web config
npm run dev
```
App: http://localhost:3000 · API: http://localhost:8000 · Docs: http://localhost:8000/docs · Health: http://localhost:8000/healthz

> **Selfie camera** needs HTTPS on real phones (localhost is fine on desktop; use a tunnel for mobile).

---

## ⚙️ Configuration

Secrets live in untracked env files (templates: `.env.example`).

| Backend (`backend/.env`) | Frontend (`frontend/.env.local`) |
|--------------------------|----------------------------------|
| `DATABASE_URL` (postgresql+psycopg://… or sqlite) | `NEXT_PUBLIC_FIREBASE_API_KEY` |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | `NEXT_PUBLIC_FIREBASE_APP_ID` |
| `AWS_BUCKET_NAME`, `AWS_REGION` | `NEXT_PUBLIC_FIREBASE_*` |
| `FIREBASE_PROJECT_ID`, `MATCH_THRESHOLD`, `CONSENT_VERSION` | `NEXT_PUBLIC_API_URL` |

---

## 📡 Key API Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/healthz` | – | DB + S3 health |
| GET | `/api/auth/me` | Firebase | Current user (auto-provisioned; first = studio) |
| POST | `/api/auth/promote` | Studio | Grant/revoke studio role |
| POST | `/api/auth/tokens` | Studio | Create desktop-agent API key (returned once) |
| GET | `/api/auth/tokens` | Studio | List API keys |
| DELETE | `/api/auth/tokens/{id}` | Studio | Revoke API key |
| POST | `/api/events/` | Studio | Create event + QR |
| POST | `/api/photos/upload/{event_id}` | Studio (Firebase **or** API key) | Manual / agent photo upload |
| POST | `/api/events/{id}/watch-folder` | Studio | Start auto folder upload |
| GET | `/api/events/{id}/watch-folder` | Studio | Watch status + photo count |
| DELETE | `/api/events/{id}/watch-folder` | Studio | Stop watching |
| POST | `/api/events/{id}/rescan` | Studio | Manual folder rescan |
| GET | `/api/guest/{slug}` | Public | Event details |
| POST | `/api/guest/{slug}/selfie` | Consent (10/min) | Face match (event-scoped, pgvector) |
| GET | `/api/guest/{slug}/photos/{photo_id}/download` | Public | Signed download URL |
| POST | `/api/guest/{slug}/download-zip` | Public (5/min) | Bulk ZIP of matched photos (event-isolated) |
| POST | `/api/guest/{slug}/erase` | Public (5/min) | DPDP right-to-erasure (delete caller's data) |
| GET | `/api/events/{id}/privacy` | Studio | Consent count, retention, scheduled purge date |
| PATCH | `/api/events/{id}/retention` | Studio | Set/clear auto-delete window (days) |
| GET | `/api/events/{id}/consents` | Studio | Consent ledger |
| GET | `/api/events/{id}/consents/export?format=csv\|pdf` | Studio | Proof-of-consent export |

---

## 🗄️ Migrations (Alembic)

Schema is managed by Alembic, not `create_all`.
```bash
alembic upgrade head                                   # apply
alembic revision --autogenerate -m "describe change"   # create after model edits
```
The pgvector migration (`CREATE EXTENSION vector`, `embedding_vec` column, HNSW index) is Postgres-only and self-skips on SQLite.

---

## 🧪 Testing

```bash
cd backend
../.venv/Scripts/pytest            # 17 tests
```
Runs against an isolated SQLite DB (`DATABASE_URL` set in `conftest.py` before import) with S3 and the face engine mocked — no AWS/RDS/model needed. Covers auth role gating, event CRUD, the ingest pipeline, guest selfie match, and bulk ZIP isolation.

---

## 🔒 Security & Privacy

- No secrets in git — credentials gitignored; use `.env.example`.
- First-user-becomes-studio bootstrap; least-privilege `guest` default.
- **DPDP compliance suite:**
  - Biometric consent (text + version + IP + user-agent + timestamp) recorded before any face processing.
  - **Consent ledger + CSV/PDF export** — audit-ready proof per event.
  - **Configurable retention** — photos + face embeddings auto-purged N days after the event (daily background sweeper); consent records retained as legal proof.
  - **Right-to-erasure** — guest deletes their own data (consent + downloads + activity) in one click.
  - Selfies never persisted (matched in memory, temp file deleted).
- Event isolation — matching/downloads constrained to one event.
- Folder paths validated (absolute, exists, no traversal).
- **Production:** rotate AWS/RDS credentials regularly; restrict RDS security group; consider a desktop agent for folder watching when the backend runs in the cloud (watchdog only sees the backend host's filesystem); prefer an S3 region near your users (e.g. `ap-south-1`).

---

## 🗺️ Roadmap

WhatsApp delivery · Celery + Redis async pipeline · Razorpay billing + studio branding · S3 lifecycle retention (DPDP) · `ap-south-1` region · private RDS subnet · regional languages · multi-region.

---

## 📄 License

Proprietary — all rights reserved.
