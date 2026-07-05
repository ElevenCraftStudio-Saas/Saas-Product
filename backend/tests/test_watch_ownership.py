"""Folder-watch ownership: studios operate watch folders on their OWN events;
admins retain access to any event. Other studios are locked out."""
from app import main as app_main
from app.routers import deps
from tests.conftest import make_user, _override_current


def _create_event(client, title="Wedding"):
    return client.post(
        "/api/events/", json={"title": title, "event_date": "2026-09-01T00:00:00Z"}
    ).json()


def test_studio_manages_own_watch_folders(client, as_user, tmp_path):
    ev = _create_event(client)
    folder = str(tmp_path)

    # add
    r = client.post(f"/api/events/{ev['id']}/watch-folders", json={"folder_path": folder})
    assert r.status_code == 200, r.text
    watch_id = r.json()["id"]

    # list
    r = client.get(f"/api/events/{ev['id']}/watch-folders")
    assert r.status_code == 200
    assert len(r.json()) == 1

    # rescan one + all
    assert client.post(
        f"/api/events/{ev['id']}/watch-folders/{watch_id}/rescan"
    ).status_code == 200
    assert client.post(f"/api/events/{ev['id']}/rescan-all").status_code == 200

    # remove
    assert client.delete(
        f"/api/events/{ev['id']}/watch-folders/{watch_id}"
    ).status_code == 204


def test_other_studio_locked_out_of_watch_folders(client, as_user, tmp_path):
    ev = _create_event(client)

    # Switch identity to a different studio user.
    other = make_user(role="user", email="other@test.ai", firebase_uid="other-uid")
    cur = _override_current(other)
    app_main.app.dependency_overrides[deps.get_current_user] = cur
    app_main.app.dependency_overrides[deps.require_user] = cur

    assert client.post(
        f"/api/events/{ev['id']}/watch-folders", json={"folder_path": str(tmp_path)}
    ).status_code == 403
    assert client.get(f"/api/events/{ev['id']}/watch-folders").status_code == 403
    assert client.post(f"/api/events/{ev['id']}/rescan-all").status_code == 403


def test_admin_still_manages_any_events_watch_folders(client, as_user, tmp_path):
    ev = _create_event(client)  # owned by the studio user

    admin = make_user(role="admin", email="boss@test.ai", firebase_uid="boss-uid")
    cur = _override_current(admin)
    app_main.app.dependency_overrides[deps.get_current_user] = cur

    r = client.post(
        f"/api/events/{ev['id']}/watch-folders", json={"folder_path": str(tmp_path)}
    )
    assert r.status_code == 200, r.text
    assert client.get(f"/api/events/{ev['id']}/watch-folders").status_code == 200
