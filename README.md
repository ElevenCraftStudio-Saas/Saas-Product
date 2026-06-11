# WedFind AI — Saas-Product

AI-powered wedding photo delivery. A studio uploads event photos; each guest scans a QR code, takes a selfie, and instantly gets **only their own** photos via face recognition — then downloads them.

> Studio Login → Create Event → Generate QR → Guest scans QR → Guest gives consent → Takes selfie → AI face matching → Guest sees only their photos → Downloads

---

## ✨ Features

- **Studio dashboard** — Firebase auth (Email/Password, Google), event creation, QR generation, photo upload to S3
- **AI face matching** — InsightFace (`buffalo_l`) embeddings + cosine similarity, scoped strictly per-event
- **Guest flow (no login)** — consent-gated, live selfie capture (`getUserMedia`), matched gallery, signed-URL downloads
- **Privacy-first** — explicit biometric consent recorded (IP + version) before processing; selfies not stored permanently
- **Audit logging** — `EVENT_VIEWED`, `SELFIE_UPLOADED`, `FACE_MATCH_COMPLETED`, `PHOTO_DOWNLOADED`
- **Security** — event isolation (no cross-event photo access), file validation (type + 10 MB), expiring presigned URLs

---

## 🧱 Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 16, React 19, TypeScript, ShadCN UI, TanStack Query, Axios |
| Backend | FastAPI, SQLAlchemy, Pydantic |
| Auth | Firebase Authentication (ID-token verification via Google public certs) |
| Storage | AWS S3 (boto3) |
| Face Recognition | InsightFace `buffalo_l`, OpenCV, ONNXRuntime |
| Database | SQLite (dev) → PostgreSQL (planned) |

---

## 🏗️ Architecture

```
                ┌──────────────┐         ┌──────────────┐
 Studio  ─────► │  Next.js UI  │ ──────► │   FastAPI    │ ──► AWS S3 (photos, QR)
 Guest   ─────► │  (frontend)  │  Axios  │  (backend)   │ ──► SQLite (events, embeddings,
                └──────────────┘         └──────┬───────┘       consents, audit logs)
                       ▲                        │
                Firebase Auth            InsightFace (embeddings + cosine match)
```

**Guest match flow:** QR → `/event/{slug}` → consent → selfie → `POST /api/guest/{slug}/selfie` → one-face check → embedding → cosine match within event → gallery → `GET /api/guest/{slug}/photos/{id}/download`.

---

## 📁 Project Structure

```
.
├── backend
│   ├── app
│   │   ├── core         # Firebase token verification
│   │   ├── models       # SQLAlchemy models
│   │   ├── routers      # auth, events, photos, guest, match
│   │   ├── schemas      # Pydantic schemas
│   │   ├── services     # face engine, S3, activity logging
│   │   └── utils        # QR generation
│   ├── requirements.txt
│   └── .env.example
├── frontend
│   ├── app              # Next.js routes (dashboard, login, guest /event/[slug])
│   ├── components       # UI + guest (selfie-capture, photo-gallery)
│   ├── lib              # api, firebase, auth-context, hooks
│   └── .env.example
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+, Node.js 18+
- An AWS S3 bucket + IAM credentials
- A Firebase project (enable Email/Password, Google, Phone in Authentication)

### 1. Backend
```bash
cd backend
python -m venv ../.venv
../.venv/Scripts/activate        # Windows  (source ../.venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
cp .env.example .env             # then fill in real values
uvicorn app.main:app --port 8000
```
> First run downloads the InsightFace `buffalo_l` model (~300 MB) and takes ~20s to load.
> After backend code edits, do a **full restart** (avoid `--reload` — it can miss changes during model load).

### 2. Frontend
```bash
cd frontend
npm install
cp .env.example .env.local       # then fill in Firebase web config
npm run dev
```
App: http://localhost:3000 · API: http://localhost:8000 · API docs: http://localhost:8000/docs

> **Phone testing note:** `getUserMedia` (selfie camera) requires HTTPS on real devices. Use localhost on desktop, or a tunnel (ngrok / `next dev --experimental-https`) for phones.

---

## ⚙️ Configuration

All secrets live in untracked env files (see `.env.example` in each folder):

| Backend (`backend/.env`) | Frontend (`frontend/.env.local`) |
|--------------------------|----------------------------------|
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | `NEXT_PUBLIC_FIREBASE_API_KEY` |
| `AWS_BUCKET_NAME`, `AWS_REGION` | `NEXT_PUBLIC_FIREBASE_APP_ID` |
| `FIREBASE_PROJECT_ID` | `NEXT_PUBLIC_FIREBASE_*` (authDomain, projectId, …) |
| `SECRET_KEY`, `MATCH_THRESHOLD`, `CONSENT_VERSION` | `NEXT_PUBLIC_API_URL` |

---

## 📡 Key API Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/auth/me` | Firebase | Current user (auto-provisioned) |
| POST | `/api/events/` | Studio | Create event + QR |
| GET | `/api/events/` | Studio | List events |
| POST | `/api/photos/upload/{event_id}` | Studio | Upload photos to S3 |
| GET | `/api/guest/{slug}` | Public | Event details (logs view) |
| POST | `/api/guest/{slug}/selfie` | Consent | Face match (event-scoped) |
| GET | `/api/guest/{slug}/photos/{photo_id}/download` | Public | Signed download URL |

---

## 🔒 Security & Privacy

- **No secrets in git** — all credentials are gitignored; use `.env.example` as the template.
- **Biometric consent (DPDP)** recorded before any face processing.
- **Event isolation** — matching and downloads are constrained to a single event.
- **Recommended for production:** store data in an India region (S3 `ap-south-1`), rotate keys regularly, move SQLite → PostgreSQL (with `pgvector` for embedding search).

---

## 🗺️ Roadmap

WhatsApp-native delivery · Electron auto-uploader · PostgreSQL + pgvector · Celery + Redis async pipeline · real-time gallery · studio CRM · AI culling · regional languages.

---

## 📄 License

Proprietary — all rights reserved.
