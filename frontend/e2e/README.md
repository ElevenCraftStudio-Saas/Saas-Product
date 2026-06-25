# WedFind E2E (Playwright)

Browser validation against the **real** stack — Firebase, FastAPI, Postgres,
Redis, Celery, S3, InsightFace. Nothing is mocked. This is release validation,
not unit testing (that lives in `test/` via Vitest).

## Prerequisites

1. The full stack is running and reachable (backend, worker, db, redis, S3).
2. A real Firebase **studio** account exists (role `user`).
3. Frontend is built + served (`npm run build && npm run start`) or `dev`.

## Setup

```bash
cd frontend
npm ci
npm run e2e:install          # downloads the Chromium browser
cp e2e/.env.e2e.example .env.e2e   # then fill in real values
```

`.env.e2e` keys (see `.env.e2e.example`):

| key | purpose |
|-----|---------|
| `E2E_BASE_URL` | frontend origin (default `http://localhost:3000`) |
| `E2E_STUDIO_EMAIL` / `E2E_STUDIO_PASSWORD` | real Firebase studio login |
| `E2E_EVENT_SLUG` | a live public event for guest tests |
| `E2E_EXPIRED_SLUG` | a past/closed event (expired-route test) |
| `E2E_REAL_FACES` | `1` to enable face-matching happy paths |
| `E2E_ALL_BROWSERS` | `1` to also run Firefox + WebKit |

## Face assets (for real matching)

Face matching only succeeds with real faces. Tests that need them **skip**
unless `E2E_REAL_FACES=1` and these exist in `e2e/assets/` (gitignored):

| file | content |
|------|---------|
| `studio-photo.jpg` | a photo of person A (the studio uploads it) |
| `selfie.jpg` | a selfie of the **same** person A (the guest) |
| `selfie-noface.jpg` | an image with no detectable face |
| `selfie-multi.jpg` | an image with 2+ faces |

Without real assets, the suite synthesizes throwaway images so the
upload / validation / error flows still execute end-to-end; only the
match-and-download happy paths are gated.

To seed a matchable event: log in as the studio account, create an event,
upload `studio-photo.jpg`, wait for the badge to reach **Ready**, then use that
event's slug as `E2E_EVENT_SLUG`.

## Run

```bash
npm run e2e            # headless, Chromium
npm run e2e:headed     # watch it drive a real browser
npm run e2e:ui         # Playwright UI mode (pick/debug tests)
npm run e2e:report     # open the last HTML report
```

Run one lane:

```bash
npm run e2e -- --project=guest
npm run e2e -- --project=chromium
```

## Layout

```
e2e/
  auth.setup.ts          one-time real Firebase login → e2e/.auth/studio.json
  pages/                 page objects (studio, guest)
  fixtures/assets.ts     real-or-synthesized image resolution
  studio.spec.ts         login→dashboard→create→upload→process→verify→QR
  guest.spec.ts          landing→consent→selfie→AI→gallery→download
  upload.spec.ts         progress / cancel / retry / badges
  errors.spec.ts         not-found, expired, invalid file, no/multi face, no match, session expiry
  a11y.spec.ts           keyboard nav, focus, dialogs, mobile viewport
  screenshots-*.spec.ts  release-artifact screenshots → e2e/screenshots/
```

## Notes

- The Firebase Web SDK keeps its session in **IndexedDB**, so the auth state is
  saved with `storageState({ indexedDB: true })` (Playwright ≥ 1.51).
- The selfie step uses the page's **file-upload fallback** (a hidden
  `input[type=file]`) instead of a live camera — deterministic in CI.
- `workers: 1`, `fullyParallel: false` — these mutate real DB/S3 state, so they
  run serially to avoid races.
- CI: `.github/workflows/e2e.yml` — manual (`workflow_dispatch`) + `v*-rc*`
  tags only. Never on regular PRs.
```
