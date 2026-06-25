# WedFind AI — Frontend Progress

Next.js 16 (App Router) · React 19 · TypeScript (strict) · Tailwind v4 · TanStack Query · Firebase Auth · React Hook Form + Zod. Enhances the existing app — does not replace working auth/RBAC.

Status: **MVP feature-complete** (Increments 1–5) + **production polish** (Increment 6). `tsc --noEmit` clean, `next build` clean.

---

## Completed features
| Area | Status |
|---|---|
| Auth + role routing (admin/user), session-expiry handling | ✅ |
| Reusable **AppShell** (sidebar, mobile drawer, breadcrumbs, user menu, dark mode, role-aware nav) | ✅ |
| **Admin** dashboard + users/tokens/audit/analytics | ✅ |
| **Studio** dashboard + Event Management (search/sort/filter/paginate, create, delete, QR) | ✅ |
| **Event workspace** (`/events/[id]`) — overview cards, production upload, recent uploads, QR sharing | ✅ |
| **Upload UX** — drag/drop, folder, queue, concurrency, progress/speed/ETA, retry, cancel, dedupe | ✅ |
| **Guest flow** — landing → consent → camera/upload → AI matching → gallery → download | ✅ |
| Dark mode, skeletons, empty/error states, toasts, 404/500/global error boundaries | ✅ |

---

## Shared UI primitives (`components/`)
- **ui/**: `button, card, dialog, form, input, label, progress, sonner, table, tabs, skeleton, mode-toggle`
- **feedback/states.tsx**: `Spinner, PageSpinner, EmptyState, ErrorState`
- **common/**: `search-toolbar, pagination-bar`
- **layout/**: `app-shell, sidebar-nav, user-menu, breadcrumbs, page-header, nav-config`
- **dashboard/**: `metric-card (+skeleton), stat-grid, dashboard-section, activity-list, quick-action-card`
- **events/**: `event-status-badge, event-action-menu, qr-card, event-form, event-form-dialog, event-table, event-card, event-stats-grid, event-workspace-header`
- **photos/**: `processing-badge, upload-dropzone, upload-queue, upload-queue-item, upload-toolbar`
- **guest/**: `guest-flow-provider, guest-header, consent-card, camera-view, selfie-preview, matching-timeline, gallery-grid, gallery-photo, fullscreen-viewer, empty-gallery`
- **providers/**: `theme-provider, query-provider, session-guard`

All presentation components are typed, prop-driven, and free of business logic (IO lives in hooks/services).

## Shared hooks (`lib/hooks/`)
`useMe` · `useEvents/useEvent/useCreateEvent/useDeleteEvent` · `useStudioMetrics` · `useEventPhotos` (adaptive polling) · `useUploadQueue` · `useAnalytics/useAdminUsers/useActivity/useDashboardMetrics` · `useGuestFlow` · `useClickOutside`

## Shared services (`services/`) + lib
`services/{auth,events,admin,photos,guest}.ts` — thin typed endpoint wrappers.
`lib/api.ts` — axios instance + typed `httpGet/Post/Patch/Delete<T>`, Firebase token attach, **401 refresh-and-retry → session-expired event**.
`lib/errors.ts` — `ApiError` (normalizes FastAPI `detail`). `lib/format.ts`, `lib/event-status.ts`, `lib/firebase.ts`, `lib/utils.ts`. `types/models.ts` mirrors backend DTOs.

---

## Route map
**Public:** `/` · `/login` · `/session-expired` · `/unauthorized` · `/event/[slug]` `/consent` `/selfie` `/processing` `/gallery` `/expired` `/not-found`
**Studio (role `user`):** `/dashboard` · `/events` · `/events/[id]` · `/profile` · `/settings`
**Admin (role `admin`):** `/admin` · `/admin/users` · `/admin/tokens` · `/admin/audit` · `/admin/analytics`
Route groups `(admin)` / `(dashboard)` guard by role with a loading screen (no unauthorized flash).

## Backend endpoints consumed (no backend changes made)
`GET /auth/me` · `GET/POST /events/` · `GET/DELETE /events/{id}` · `POST /photos/upload/{id}` · `GET /photos/event/{id}` · `GET /admin/{analytics,users,activity}` · `PATCH /admin/users/{id}/{role,limit,storage}` · `GET/POST/DELETE /auth/tokens` · `GET /guest/{slug}` · `POST /guest/{slug}/selfie` · `GET /guest/{slug}/photos/{id}/download` · `POST /guest/{slug}/download-zip`

---

## Remaining TODOs (frontend, UI-ready when backend lands)
- **Edit event** — disabled gracefully; needs `PATCH /events/{id}`.
- **Per-event counts** (Photos/Guests/Downloads `—` columns) + **studio aggregate KPIs** (dashboard placeholders) — need count/summary endpoints; swap one hook each.
- **Confidence badges** (dev-only) — need a per-photo score in the selfie match response.
- **`/expired`** page exists but isn't auto-triggered — needs an expiry flag on `GET /guest/{slug}`.

## Technical debt
- **`<img>` (not `next/image`)** for presigned S3 urls (rotating query strings aren't optimizer-friendly) → possible CLS; revisit with CloudFront stable paths.
- **Firebase SDK bundles into public guest routes** (`api.ts` imports `auth`); guests never authenticate. Could code-split auth out of the guest bundle.
- **No frontend test runner** (no jest/vitest/playwright).
- Folder-watch + privacy panels removed from studio UI (admin-gated by backend RBAC) — product decision, not debt, but noted.

## Future enhancements
Progressive/full-res gallery loading + virtualization for large galleries · native share sheet · PWA/offline selfie retry · i18n · Suspense-based route streaming · Sentry on the frontend.
