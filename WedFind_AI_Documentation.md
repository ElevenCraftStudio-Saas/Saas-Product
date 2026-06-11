# Project Name

WedFind AI

# Product Overview

WedFind AI is a SaaS platform for wedding photographers and studios.

Business Flow:
Studio Login
→ Create Event
→ Generate QR
→ Upload Wedding Photos
→ Guest Scans QR
→ Guest Gives Consent
→ Guest Takes Selfie
→ AI Face Matching
→ Guest Sees Only Their Photos
→ Guest Downloads Photos

Goal:
Automate wedding photo discovery using AI facial recognition.

---

## 1. Executive Summary

WedFind AI is a business-to-business-to-consumer (B2B2C) photo delivery SaaS platform tailored specifically for wedding studios and photographers. Instead of manually distributing thousands of wedding photos or forcing guests to scroll through massive galleries, WedFind AI leverages facial recognition technology to provide an automated, personalized photo discovery experience. 

**Target Customers:** Wedding photography studios, event management companies, and professional photographers.
**Business Value:** Saves photographers dozens of hours in photo sorting and distribution. Enhances the guest experience by instantly delivering their specific photos to their mobile devices, creating an immediate wow-factor.
**Key Differentiators:** Consent-first AI processing, event-isolated galleries (zero cross-event data leakage), automated QR code generation per event, and a seamless guest flow requiring zero app installations or logins.

---

## 2. Complete Technology Stack

### Frontend
* **Framework:** Next.js (App Router)
* **Libraries:** React Hook Form, Zod (Validation), Lucide React (Icons), Sonner (Toasts)
* **State Management:** React Query (`@tanstack/react-query`) for remote state caching and mutation handling.
* **UI Libraries:** Tailwind CSS, shadcn/ui components (Radix UI primitives).
* **Data Fetching:** Axios (configured in `frontend/lib/api.ts`).
* **Routing:** Next.js native App Router with dynamic segments (e.g., `/event/[slug]`).

### Backend
* **Framework:** FastAPI (Python)
* **API Architecture:** RESTful architecture, modularized via APIRouter.
* **Authentication Flow:** Firebase Authentication. The client retrieves an ID token and sends it via Bearer headers. FastAPI validates the token against Google's public x509 certificates.
* **Services:** `face_engine.py` (AI), `s3_service.py` (Storage), `face_processing.py` (Background tasks), `activity.py` (Logging).
* **Dependency Injection:** Used heavily for database sessions (`get_db`) and current user context (`get_current_user`).

### Database
* **Current Database:** SQLite (`wedfind.db`) using SQLAlchemy ORM.
* **Future Database Recommendations:** PostgreSQL (strongly recommended for production to support high concurrency, proper foreign key constraints, and JSON querying).

### Storage
* **Implementation:** AWS S3 (via `boto3`).
* **Usage:** Stores event QR codes, uploaded wedding photos, and serves them via short-lived Presigned URLs to protect underlying assets.

### AI
* **Implementation:** InsightFace (`buffalo_l` model running on `CPUExecutionProvider`).
* **Usage:** Detects faces, extracts 512-dimensional embeddings, and computes cosine similarity to match guest selfies against the event gallery.

### Authentication
* **Implementation:** Firebase Auth.
* **Usage:** Studio logins. Supports Email, Phone OTP, Google Login implicitly via Firebase client SDK. Validated statelessly on the backend.

### Infrastructure
* **Deployment Architecture:** Currently running locally (uvicorn + next dev) but architected for containerization. Stateless backend (mostly) assuming SQLite is swapped for a managed DB.

---

## 3. Complete Folder Structure Analysis

### `backend/`
* **Purpose:** Contains the FastAPI REST API, database models, AI processing logic, and S3 integration.
* **`app/main.py`:** The entry point for the FastAPI application. Wires up routers, CORS, and logging.
* **`app/core/`:** Contains core infrastructure logic (`auth.py` for deps, `firebase.py` for token verification).
* **`app/models/`:** Contains SQLAlchemy ORM definitions (`models.py`).
* **`app/schemas/`:** Contains Pydantic models for request/response validation and serialization.
* **`app/routers/`:** Contains the controller layer. Segregated by domains: `auth.py`, `events.py`, `photos.py`, `match.py`, `guest.py`.
* **`app/services/`:** Contains business logic decoupled from HTTP: `s3_service.py` (AWS wrapper), `face_engine.py` (InsightFace singleton), `face_processing.py` (Background extraction jobs), `activity.py` (Audit logging).
* **`app/utils/`:** Contains utility helpers like QR code generation (`qr.py`).

### `frontend/`
* **Purpose:** Contains the Next.js React application for both Studio Dashboard and Guest UI.
* **`app/(auth)/`:** Contains login pages and authentication flows.
* **`app/(dashboard)/`:** Contains the authenticated studio views (Event list, Event details).
* **`app/event/[slug]/`:** Contains the public-facing guest flow.
* **`components/ui/`:** Contains reusable generic UI components (shadcn/ui).
* **`components/guest/`:** Contains domain-specific components for the guest flow (`SelfieCapture.tsx`, `PhotoGallery.tsx`).
* **`lib/`:** Contains shared utilities: `api.ts` (Axios config), `firebase.ts` (Client init), `auth-context.tsx` (React Context), `hooks/guest.ts` (React Query wrappers).

### `uploads/`
* **Purpose:** Fallback local storage directory for instances where S3 is not configured. Contains temp folders for processing (`temp_processing/`, `temp_selfies/`).

---

## 4. Page-by-Page Documentation

| Route | Purpose | Components Used | API Calls | User Actions | Security |
|-------|---------|-----------------|-----------|--------------|----------|
| `/login` | Studio authentication | Form, Input, Button, Card | Firebase Client SDK | Enter credentials, OAuth click | Public |
| `/dashboard` | Studio event management | Card, Dialog, Form | `GET /api/events/`, `POST /api/events/` | View events, Create event | Studio Auth |
| `/events/[id]` | Event management, photo uploads | Dropzone, Photo Grid | `GET /api/events/[id]`, `GET /api/photos/event/[id]`, `POST /api/photos/upload/[id]` | Upload photos, view processing status | Studio Auth |
| `/event/[slug]` | Guest portal | SelfieCapture, PhotoGallery | `GET /api/guest/[slug]`, `POST /api/guest/[slug]/selfie`, `GET /api/guest/[slug]/photos/[id]/download` | Consent, take selfie, view gallery, download | Public (Consent required) |

---

## 5. API Documentation

### `POST /api/events/`
* **Purpose:** Create a new wedding event.
* **Auth:** Studio Token Required.
* **Request Body:** `{"title": "string", "description": "string", "event_date": "datetime"}`
* **Response:** Event object with auto-generated slug and S3 presigned URL for the generated QR code.
* **Error Cases:** `401 Unauthorized`, `502 Bad Gateway` (S3 upload failure).
* **Files Used:** `backend/app/routers/events.py`, `backend/app/utils/qr.py`, `backend/app/services/s3_service.py`.

### `GET /api/events/`
* **Purpose:** List all events for the logged-in photographer.
* **Auth:** Studio Token Required.
* **Response:** List of Event objects.
* **Files Used:** `backend/app/routers/events.py`.

### `POST /api/photos/upload/{event_id}`
* **Purpose:** Upload raw wedding photos to an event.
* **Auth:** Studio Token Required.
* **Request Body:** `multipart/form-data` with multiple files.
* **Response:** List of Photo objects with status PENDING.
* **Error Cases:** `404 Not Found` (Event missing), `502 Bad Gateway` (Storage failure).
* **Behavior:** Synchronously uploads to S3, writes to DB, and dispatches a FastAPI `BackgroundTasks` job to process face embeddings.
* **Files Used:** `backend/app/routers/photos.py`, `backend/app/services/face_processing.py`.

### `GET /api/guest/{slug}`
* **Purpose:** Retrieve public event details. Logs an `EVENT_VIEWED` activity.
* **Auth:** Public.
* **Response:** Event title, description, date, and URL.
* **Error Cases:** `404 Not Found`.
* **Files Used:** `backend/app/routers/guest.py`.

### `POST /api/guest/{slug}/selfie`
* **Purpose:** Consent to processing, upload selfie, and get matched photos.
* **Auth:** Public.
* **Request Body:** `multipart/form-data` (file: Blob, consent: boolean).
* **Response:** `{"count": int, "photos": [{"id": int, "filename": str, "url": str}]}`
* **Error Cases:** `400 Bad Request` (Missing consent, Invalid mime type, Size exceeds limit, No faces detected, Multiple faces detected).
* **Behavior:** Validates consent, saves consent record to DB, runs InsightFace on selfie, computes cosine similarity against event embeddings, returns matched presigned URLs.
* **Files Used:** `backend/app/routers/guest.py`, `backend/app/services/face_engine.py`.

### `GET /api/guest/{slug}/photos/{photo_id}/download`
* **Purpose:** Get a short-lived download URL for a specific matched photo.
* **Auth:** Public.
* **Response:** `{"url": "string", "expires_in": 3600}`
* **Error Cases:** `404 Not Found` (Event isolation boundary check failed), `500 Internal Server Error` (Presigned URL generation failed).
* **Files Used:** `backend/app/routers/guest.py`.

---

## 6. Authentication System

**Mechanism:** Firebase Authentication.
**Flow:**
1. Studio User inputs credentials in the React frontend (`/login`).
2. Firebase JS SDK authenticates the user directly with Google servers.
3. Firebase returns an ID Token (JWT).
4. Frontend attaches this ID token as a `Bearer` token in the `Authorization` header via an Axios interceptor (`frontend/lib/api.ts`).
5. FastAPI (`backend/app/core/firebase.py`) intercepts the request via `get_current_user` dependency.
6. The backend cryptographically verifies the token signature against Google's public x509 certs.
7. If the user doesn't exist in the local SQLite `users` table, a JIT (Just-In-Time) provisioning occurs, inserting the Firebase UID.

**Roles:** Role column exists (`role = "studio"` or `"guest"`), currently defaulting to studio.
**Files Involved:**
* `frontend/lib/firebase.ts` (Init)
* `frontend/lib/auth-context.tsx` (React Context Provider)
* `backend/app/core/firebase.py` (Validation logic)
* `backend/app/routers/deps.py` (FastAPI dependency)

---

## 7. Event Management System

**Create Event Flow:**
1. Studio submits Event details.
2. Backend generates a unique URL slug (`slugify(title) + uuid[:8]`).
3. Backend generates a QR code image buffer pointing to `FRONTEND_URL/event/{slug}` using the `qrcode` library.
4. The QR image buffer is directly uploaded to AWS S3 (`qr/{slug}_qr.png`).
5. The Event record is stored in the database with references to the S3 key.
6. A presigned URL is returned to the frontend to display the QR code.
**Files Involved:** `backend/app/routers/events.py`

---

## 8. QR Code System

* **Generation:** Generated on-the-fly in memory during Event creation using the Python `qrcode` library.
* **Storage:** Uploaded immediately to the S3 bucket under the `qr/` prefix.
* **Display:** Accessed via short-lived AWS Presigned URLs in the Studio dashboard.
* **Dependencies:** `qrcode`, `Pillow`, `boto3`.

---

## 9. Photo Upload System

**Flow Diagram:**
`Frontend Dropzone` → `POST /upload/{event_id}` → `FastAPI Validates Size/MIME` → `Upload to S3` → `Write to DB (PENDING)` → `Return 200 OK` → `Trigger Background Task`

**Details:**
* **Validation:** Max 10MB per file. Only JPEG/PNG allowed. Rejected files are skipped gracefully.
* **Storage:** Uploaded to S3 under `events/{event_id}/{uuid}.jpg`.
* **Database:** `Photo` row created with S3 key.
* **Background Processing:** A FastAPI `BackgroundTasks` job (`process_photo_faces`) is queued. It downloads the S3 image to a local temp folder, runs InsightFace to extract bounding boxes and 512D embeddings, stores them in the `face_embeddings` table, updates the photo status to `COMPLETED`, and deletes the temp file.

---

## 10. Face Recognition System

**Engine:** `InsightFace` (`buffalo_l` model).
**Photo Processing Flow (Background):**
Extracts all faces from a high-res wedding photo. Saves `[512 floats]` array and `[x1, y1, x2, y2]` bounding box to SQLite as JSON text.
**Selfie Processing Flow (Synchronous):**
Guest uploads a selfie. The backend temporarily saves it, extracts exactly 1 face (rejects if 0 or >1), and gets the guest embedding.
**Matching Logic:**
Numpy computes the cosine similarity between the guest embedding and every embedding attached to the specific event.
**Threshold:** Configurable via `.env` (`MATCH_THRESHOLD`), defaults to `0.6`.
**Event Isolation:** The matching query `db.query(models.FaceEmbedding).filter(models.FaceEmbedding.photo_id.in_(event_photo_ids))` strictly limits the search space to the current event. Zero risk of cross-event face matching.

---

## 11. Guest Flow

1. **Scan QR:** Guest scans physical QR, opening `/event/[slug]`.
2. **Event Details:** `GET /api/guest/{slug}` fetches event metadata and logs `EVENT_VIEWED`.
3. **Consent:** Guest must explicitly check a checkbox acknowledging biometric processing.
4. **Selfie Capture:** Guest takes a selfie using the device camera (`SelfieCapture.tsx`).
5. **Upload & Match:** Selfie is sent to `POST /api/guest/{slug}/selfie`. The backend logs `SELFIE_UPLOADED`, extracts the face, runs matching, logs `FACE_MATCH_COMPLETED`, and returns matched photo IDs and Presigned URLs.
6. **Gallery:** Guest scrolls through a masonry grid of their matched photos (`PhotoGallery.tsx`).
7. **Download:** Guest clicks download. The frontend calls `GET /api/guest/{slug}/photos/{photo_id}/download` to get a fresh presigned URL. The backend logs `PHOTO_DOWNLOADED` and returns the URL.

---

## 12. Database Documentation

**Current DB:** SQLite
**Tables:**

1. **`users`**: Studio photographers.
   * **Columns:** `id`, `firebase_uid`, `name`, `email`, `role`, `created_at`
2. **`events`**: Wedding events.
   * **Columns:** `id`, `title`, `description`, `event_date`, `event_slug`, `qr_code_path`, `storage_provider`, `storage_key`, `created_at`, `photographer_id`
   * **Relationships:** Belongs to `users`. Has many `photos`.
3. **`photos`**: Uploaded gallery photos.
   * **Columns:** `id`, `event_id`, `filename`, `filepath`, `storage_provider`, `storage_key`, `processing_status`, `uploaded_at`
   * **Relationships:** Belongs to `events`. Has many `face_embeddings`.
4. **`face_embeddings`**: AI face vectors.
   * **Columns:** `id`, `photo_id`, `embedding` (JSON), `face_box` (JSON), `created_at`
   * **Relationships:** Belongs to `photos`.
5. **`downloads`**: Tracks photo downloads.
   * **Columns:** `id`, `photo_id`, `ip_address`, `downloaded_at`
6. **`guest_consents`**: Audit log of guest biometric consent.
   * **Columns:** `id`, `event_id`, `ip_address`, `consent_version`, `consent_timestamp`
7. **`activity_logs`**: System audit trail.
   * **Columns:** `id`, `action`, `event_id`, `photo_id`, `ip_address`, `detail` (JSON), `created_at`

---

## 13. AWS Usage

* **S3 Bucket:** Name driven by `AWS_BUCKET_NAME`.
* **Object Structure:**
  * `qr/{slug}_qr.png`
  * `events/{event_id}/{uuid}.jpg`
* **Presigned URLs:** By default, S3 objects are completely private. The backend dynamically generates secure, time-limited (`DOWNLOAD_URL_TTL = 3600`) URLs using `boto3.client('s3').generate_presigned_url`. This guarantees guests cannot scrape the bucket.

---

## 14. Security Audit

* **Authentication:** **Secure (Low Risk)**. Delegating to Firebase eliminates password storage risks. Token verification is standard.
* **Authorization:** **Medium Risk**. Event ownership is checked for studio actions, but direct photo deletion/manipulation endpoints should be double-checked for IDOR (Insecure Direct Object Reference) vulnerabilities.
* **S3 Access:** **Secure (Low Risk)**. Uses Presigned URLs. No public bucket policies required.
* **Guest Isolation:** **Secure (Low Risk)**. The query strictly filters embeddings by `event_id`.
* **Consent Tracking:** **Secure (Low Risk)**. Hard gate on the API (`consent=true` required). IP address and timestamp recorded in `guest_consents`.
* **Audit Logging:** **Secure (Low Risk)**. Robust system logging views, downloads, and processing events.

---

## 15. Logging & Monitoring

* **Activity Logs:** Recorded in SQLite `activity_logs` table (Actions: `EVENT_VIEWED`, `SELFIE_UPLOADED`, `FACE_MATCH_COMPLETED`, `PHOTO_DOWNLOADED`).
* **System Logs:** Python `logging` module configured. Application logs surface S3 failures, background job exceptions, and QR generation metadata.
* **Recommendations:** Currently lacks external aggregators. Needs integration with **Sentry** (for unhandled Python/React exceptions) and **Datadog/CloudWatch** (for structured log aggregation and metrics).

---

## 16. Current Project Status

| Feature | Status | Notes |
|---------|--------|-------|
| Studio Authentication | Implemented | Firebase Integration |
| Event Creation & QR | Implemented | Auto S3 upload |
| Photo Uploads | Implemented | Supports S3 |
| AI Face Embedding | Implemented | Background task, SQLite JSON |
| Guest Consent Gate | Implemented | IP & Version tracking |
| Guest Selfie Match | Implemented | Synchronous matching |
| Guest Photo Gallery | Implemented | Presigned URL serving |
| Download Tracking | Implemented | IP tracking |

**Missing Features:**
* Bulk Photo deletion / Event deletion cascade validation.
* Webhook / WebSocket progress updates to frontend for photo processing status.
* Watermarking functionality.
* Paid tiers/monetization (Stripe integration).

---

## 17. Technical Debt

**High Impact:**
* **SQLite for Vectors:** Storing 512-dimension float arrays as JSON strings in SQLite is terrible for memory and CPU. Comparing arrays requires pulling JSON text into memory and deserializing it on every selfie request.
* **Background Tasks:** Using FastAPI `BackgroundTasks` means jobs run in the same memory space as the web server. InsightFace is CPU/Memory heavy. If the server restarts, pending jobs are lost.

**Medium Impact:**
* **S3 Temp Downloads:** The background worker downloads the S3 image back to disk to run InsightFace, which doubles bandwidth costs.

---

## 18. Scalability Assessment

* **100 Events:** System will perform adequately. Local SQLite will easily handle the JSON deserialization loop.
* **1,000 Events:** Background tasks will begin to choke the FastAPI web workers. Server memory will spike during large batch uploads. SQLite database locks may cause API timeouts.
* **10,000 Events:** System will completely fail. SQLite JSON deserialization for matching across thousands of photos will result in 10-30+ second timeouts on selfie uploads.

**Bottlenecks:** In-memory queue, SQLite DB locks, CPU-bound vector math in Python runtime.

---

## 19. Production Readiness Assessment

| Area | Score | Notes |
|------|-------|-------|
| Authentication | 9/10 | Firebase is production-grade. |
| Database | 3/10 | SQLite + JSON vectors is unscalable. |
| Storage | 8/10 | S3 + Presigned URLs is excellent. |
| Security | 8/10 | Good consent modeling and isolation. |
| Monitoring | 4/10 | Lacks external APM and error tracking. |
| Scalability | 2/10 | Monolithic CPU AI + API, no durable queue. |
| AI Accuracy | 8/10 | InsightFace buffalo_l is highly accurate. |

**Overall Score:** 6.0 / 10
*Status:* Excellent MVP. Ready for Beta testing, but not ready for massive scale.

---

## 20. Recommended Next Roadmap

### 30 Day Plan (Stabilization)
1. **Database Migration:** Replace SQLite with **PostgreSQL**.
2. **Vector DB Support:** Install the **pgvector** extension. Alter `FaceEmbedding` table to use `VECTOR(512)` type. Change Python matching logic to use SQL native cosine distance (`<=>`). This immediately fixes the biggest scaling bottleneck.
3. **Monitoring:** Integrate Sentry on Frontend and Backend.

### 60 Day Plan (Decoupling)
1. **Message Queue:** Implement **Redis + Celery**. Move `process_photo_faces` out of FastAPI `BackgroundTasks` into isolated Celery worker containers. This prevents heavy CPU loads from crashing the API.
2. **WebSocket Integration:** Allow the frontend to subscribe to Redis events so the photographer dashboard shows real-time upload/processing progress bars.
3. **Electron / Desktop Uploader:** Build a lightweight desktop uploader. Web browsers struggle to upload 2,000 high-res raw images without crashing.

### 90 Day Plan (Growth Features)
1. **Watermarking Engine:** Integrate a pipeline to overlay studio logos on gallery images, stripping the watermark only upon paid download.
2. **WhatsApp Bot Integration:** Allow guests to send their selfie to a Twilio/WhatsApp number instead of a web page, receiving their gallery link instantly.
3. **Monetization:** Stripe Connect integration to allow photographers to charge guests per-photo downloads.