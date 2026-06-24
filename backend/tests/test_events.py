import tempfile


def _create_event(client):
    return client.post("/api/events/", json={"title": "Wedding", "event_date": "2026-09-01T00:00:00Z"})


def test_user_creates_event(client, as_user):
    r = _create_event(client)
    assert r.status_code == 200
    body = r.json()
    assert body["event_slug"].startswith("wedding-")
    assert body["qr_code_path"].startswith("qr/")
    assert body["url"]  # presigned (mocked)


def test_pending_cannot_create_event(client, as_pending):
    r = _create_event(client)
    assert r.status_code == 403


# Folder-watch is admin-gated. as_admin also overrides require_user, so the
# admin can create the event (owns it) and then manage its watch folders.
def test_watch_folder_validates_path(client, as_admin):
    eid = _create_event(client).json()["id"]
    r = client.post(f"/api/events/{eid}/watch-folders", json={"folder_path": "Z:/nope/nope"})
    assert r.status_code == 400
    with tempfile.TemporaryDirectory() as d:
        r2 = client.post(f"/api/events/{eid}/watch-folders", json={"folder_path": d})
        assert r2.status_code == 200
        wid = r2.json()["id"]
        assert r2.json()["watching"] in (True, False)
        assert client.post(f"/api/events/{eid}/watch-folders", json={"folder_path": d}).status_code == 409
        client.delete(f"/api/events/{eid}/watch-folders/{wid}")


def test_multiple_watch_folders(client, as_admin):
    eid = _create_event(client).json()["id"]
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        client.post(f"/api/events/{eid}/watch-folders", json={"folder_path": d1})
        client.post(f"/api/events/{eid}/watch-folders", json={"folder_path": d2})
        lst = client.get(f"/api/events/{eid}/watch-folders")
        assert lst.status_code == 200
        assert len(lst.json()) == 2
        for w in lst.json():
            client.delete(f"/api/events/{eid}/watch-folders/{w['id']}")
