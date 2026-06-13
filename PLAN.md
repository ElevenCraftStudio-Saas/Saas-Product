# WedFind AI — Differentiation Plan

Goal: stop being "another face-match app." Win on two moats competitors structurally lack — **DPDP privacy compliance** and **zero-touch ingest** — then fill table-stakes gaps (WhatsApp, billing, branding).

Positioning: *"DPDP-compliant, zero-touch wedding photo delivery — editing folder to guest's WhatsApp, automatically. Faces deleted on schedule. Audit-ready."*

---

## Phase 1 — Privacy / DPDP moat (START HERE)

Why first: closest to done (consent already logged), no new infra, the hardest moat to copy. India DPDP Act 2023 makes biometric processing a studio liability — we make compliance a product.

### 1a. Data model
- `Event.retention_days` (Integer, nullable; null = keep forever) — when set, photos+faces auto-purge N days after `event_date`.
- `Event.consent_text` (String, nullable) — custom consent wording per studio (snapshot for proof).
- `GuestConsent.consent_text` (String) — exact text the guest agreed to (immutable proof).
- `GuestConsent.user_agent` (String, nullable) — extra evidence.
- (Erasure needs no new table — guest data = consent + downloads + activity rows keyed by `ip_address`+`event_id`.)
- Alembic migration for the above.

### 1b. Studio endpoints (auth: studio, event-owned)
- `GET  /api/events/{id}/consents` — consent ledger (paginated): ip, version, text, timestamp, user_agent.
- `GET  /api/events/{id}/consents/export?format=csv|pdf` — downloadable proof-of-consent (CSV always; PDF via reportlab).
- `PATCH /api/events/{id}/retention` — set/clear `retention_days`; returns computed purge date.
- `GET  /api/events/{id}/privacy` — summary: consent count, retention_days, scheduled_purge_at, photos_count.

### 1c. Guest endpoint (public)
- `POST /api/guest/{slug}/erase` — right-to-erasure. Deletes consent + downloads + activity logs for caller IP within that event. Returns counts. Logs `DATA_ERASED`.

### 1d. Retention sweeper (background)
- `services/retention.py` — `purge_expired(db)`: find events where `retention_days` set and `now > event_date + retention_days` and photos still present → delete S3 objects (reuse `s3_service.delete_file`), FaceEmbedding rows, Photo rows; log `RETENTION_PURGE` with counts.
- Wire into `main.py` lifespan: run on startup + every 24h (asyncio task loop). Idempotent.

### 1e. Frontend
- Studio `events/[id]` → **Privacy** panel: consent count, retention dropdown (Off / 30 / 90 / 180 / 365 days), "Export consent log" (CSV/PDF), scheduled purge date.
- Guest `event/[slug]` → small "Delete my data" link → confirm → calls erase.

### 1f. Tests
- consent export returns rows (CSV headers, row count).
- retention sweeper deletes expired event photos+embeddings, skips non-expired, skips null retention.
- erase removes only caller-IP rows scoped to event.

### 1g. Deliverable
README "Privacy & Compliance" section upgraded to a selling feature. Commit as blackcommando5.

---

## Phase 2 — WhatsApp delivery (table-stakes gap)
- Meta WhatsApp Cloud API integration (`services/whatsapp.py`).
- Guest enters phone on event page → receives gallery link + matched count via WhatsApp.
- Studio toggle per event. Opt-in consent reused.
- Config: `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`.

## Phase 3 — Desktop ingest agent (zero-touch moat)
- Standalone Python tray app (PyInstaller) — studio installs once.
- Watches a local folder, pushes new images to `POST /api/photos/upload/{event_id}` with a studio API token.
- Survives restart, retries on failure, shows synced count.
- Replaces cloud-side watchdog (which can't see studio's laptop).
- New: per-studio API token auth (not just Firebase) for the agent.

## Phase 4 — Billing + branding (make it sellable)
- Razorpay subscription (tiers by events/storage/photos).
- Studio branding: logo + accent color on guest page (`Event` or `Studio` profile fields).
- Studio analytics dashboard: scans, match rate, downloads per event (from ActivityLog).

---

## Sequencing & effort
| Phase | What | Type | Effort |
|------|------|------|:---:|
| 1 | DPDP consent ledger + retention + erasure | moat | S |
| 2 | WhatsApp delivery | gap | M |
| 3 | Desktop ingest agent | moat | L |
| 4 | Razorpay billing + branding + analytics | gap | M |

## Open security (blocks launch — do alongside Phase 1)
- Rotate RDS password (current value leaked).
- Rotate the exposed IAM access key (see ops notes, not committed).
- S3 lifecycle policy (ties into retention).
