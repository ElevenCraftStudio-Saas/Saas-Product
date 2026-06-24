"""Route authorization matrix: admin-only vs user-only vs pending (no access)."""


def test_user_cannot_list_tokens(client, as_user):
    assert client.get("/api/auth/tokens").status_code == 403


def test_admin_can_list_tokens(client, as_admin):
    assert client.get("/api/auth/tokens").status_code == 200


def test_user_cannot_start_watch_folder(client, as_user):
    r = client.post("/api/events/1/watch-folders", json={"folder_path": "/x"})
    assert r.status_code == 403


def test_user_cannot_create_token(client, as_user):
    r = client.post("/api/auth/tokens", json={"user_id": 1, "name": "agent"})
    assert r.status_code == 403


def test_pending_cannot_create_event(client, as_pending):
    r = client.post("/api/events/", json={"title": "E", "description": "d", "event_date": "2026-07-01T00:00:00"})
    assert r.status_code == 403
    assert r.json()["detail"] == "Studio access required"


# Admin-gated event sub-routes must 403 for a studio user (these lost their
# ownership filter when re-gated to require_admin — confirm no user access).
def test_user_blocked_from_event_privacy(client, as_user):
    assert client.get("/api/events/1/privacy").status_code == 403


def test_user_blocked_from_retention(client, as_user):
    assert client.patch("/api/events/1/retention", json={"retention_days": 5}).status_code == 403


def test_user_blocked_from_consents(client, as_user):
    assert client.get("/api/events/1/consents").status_code == 403


def test_user_blocked_from_rescan_all(client, as_user):
    assert client.post("/api/events/1/rescan-all").status_code == 403


def test_pending_blocked_from_admin_analytics(client, as_pending):
    assert client.get("/api/admin/analytics").status_code == 403
