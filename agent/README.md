# WedFind Desktop Ingest Agent

Zero-touch photo upload. Install on the studio's editing machine, point it at a
folder, and every new photo is pushed to WedFind automatically — no browser,
no manual upload. The cloud backend can't see the studio's local disk; this
agent bridges that gap.

> Finish editing → photos are already delivered.

## How it works
- Authenticates with a **studio API key** (`X-API-Key`) — no Firebase login on the desktop.
- Watches a folder (recursively) with `watchdog` + does an initial scan on start.
- Waits for each file to finish copying (size-stable) before upload.
- De-duplicates by file **content hash** — renames/moves don't re-upload.
- Persists synced state to `~/.wedfind_agent/` → survives restarts.
- Retries with backoff on network/server errors.

## 1. Get an API key
In the WedFind web dashboard: **Settings → API Keys → Create** (or `POST /api/auth/tokens`).
Copy the `wfa_...` token — it is shown only once.

## 2. Install
```bash
cd agent
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## 3. Configure
```bash
copy config.example.json config.json   # then edit values
```
Set `api_url`, `api_key`, `event_id`, and `folders` (a list — one per
photographer/cameraman). A single `"folder": "..."` string still works too.

## 4. Run
```bash
python wedfind_agent.py --config config.json
```
Or all-CLI (no file) — repeat `--folder` for multiple:
```bash
python wedfind_agent.py --api-url https://api.yourhost.com/api ^
  --api-key wfa_xxx --event-id 12 ^
  --folder "D:/Wedding/Cam1" --folder "D:/Wedding/Cam2"
```

## 5. Build a standalone .exe (optional)
```bash
pip install pyinstaller
pyinstaller --onefile --name WedFindAgent wedfind_agent.py
# → dist/WedFindAgent.exe
WedFindAgent.exe --config config.json
```

## Auto-start on boot (Windows)
Create a shortcut to `WedFindAgent.exe --config C:\path\config.json` in:
`shell:startup` (Win+R → `shell:startup`).

## Notes
- One agent process per event/folder. Run multiple for multiple events.
- State files live in `~/.wedfind_agent/state_<hash>.json` (one per api_url+event+folder).
- Revoke a key anytime from the dashboard; the agent will get 401 and stop.
