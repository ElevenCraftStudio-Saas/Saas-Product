# Folder-Watch UI — Design Spec (2026-07-05)

## Goal
Studios manage auto-import folders on their own events from the event
workspace. Backend endpoints already exist and were made owner-operable in
`0e60ca8` (`/api/events/{id}/watch-folders` CRUD + rescan + rescan-all); no UI
exposes them.

## Where
New **"Auto-import folders"** card in `app/(dashboard)/events/[id]/page.tsx`,
rendered below the upload dropzone. No new route.

## Card
- Rows per watch: folder path (truncated, full on title), watching-status dot
  (green watching / gray stopped), photo count, last-scan time, per-row
  **Rescan** and **Remove** buttons.
- Add form: text input for an absolute server path + **Add** button.
- **Rescan all** in the card header (visible only when ≥1 watch).
- Hint: "Folders are watched on the server running WedFind. For folders on
  your own computer, use the desktop agent."
- Empty state text; toasts for errors (409 duplicate, 400 bad path, 403).
- Mobile-first: rows stack, buttons wrap; no horizontal scroll.

## Data layer
- `types/models.ts`: `FolderWatch` (id, event_id, folder_path, enabled,
  created_at, last_scan_at, watching, photo_count) + `RescanResult {uploaded}`.
- `services/events.ts`: `getWatchFolders(eventId)`, `addWatchFolder(eventId,
  path)`, `removeWatchFolder(eventId, watchId)`, `rescanFolder(eventId,
  watchId)`, `rescanAllFolders(eventId)` — thin typed wrappers over lib/api.
- `lib/hooks/watch-folders.ts`: `useWatchFolders(eventId)` query
  (`['watch-folders', eventId]`) + add/remove/rescan mutations invalidating it.
  Rescan success toasts "N photos imported".
- New component `components/events/watch-folders-card.tsx`.

## Testing
MSW handlers for the five endpoints; component test: renders rows, add fires
mutation, duplicate-path 409 surfaces a toast; hook test via renderHook.

## Out of scope
Per-folder enable/disable toggle (no API), server folder browser, admin panel
changes, e2e.
