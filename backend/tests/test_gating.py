"""Route authorization matrix: admin-only vs user-only vs pending (no access)."""


def test_user_cannot_list_tokens(client, as_user):
    assert client.get("/api/auth/tokens").status_code == 403


def test_admin_can_list_tokens(client, as_admin):
    assert client.get("/api/auth/tokens").status_code == 200


def test_watch_folder_on_missing_event_404s(client, as_user):
    # Watch folders are owner-operable now (see test_watch_ownership.py for
    # the full matrix); a nonexistent event is a plain 404.
    r = client.post("/api/events/1/watch-folders", json={"folder_path": "/x"})
    assert r.status_code == 404


def test_user_cannot_create_token(client, as_user):
    r = client.post("/api/auth/tokens", json={"user_id": 1, "name": "agent"})
    assert r.status_code == 403


def test_admin_cannot_create_event_role(client, as_admin):
    # Admin is not a studio user: require_user must 403 an admin token.
    # (as_admin overrides require_user in tests, so assert the dep directly.)
    from app.routers import deps
    from fastapi import HTTPException
    import pytest
    admin_user = type("U", (), {"role": "admin"})()
    with pytest.raises(HTTPException) as e:
        deps.require_user(admin_user)
    assert e.value.status_code == 403


# Admin-gated event sub-routes must 403 for a studio user (these lost their
# ownership filter when re-gated to require_admin — confirm no user access).
def test_user_blocked_from_event_privacy(client, as_user):
    assert client.get("/api/events/1/privacy").status_code == 403


def test_user_blocked_from_retention(client, as_user):
    assert client.patch("/api/events/1/retention", json={"retention_days": 5}).status_code == 403


def test_user_blocked_from_consents(client, as_user):
    assert client.get("/api/events/1/consents").status_code == 403


def test_rescan_all_on_missing_event_404s(client, as_user):
    # Owner-operable now — nonexistent event is 404, other-owner is 403
    # (covered in test_watch_ownership.py).
    assert client.post("/api/events/1/rescan-all").status_code == 404


def test_user_blocked_from_admin_analytics(client, as_user):
    assert client.get("/api/admin/analytics").status_code == 403
