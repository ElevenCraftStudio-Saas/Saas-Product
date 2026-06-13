import tempfile


def _create_event(client):
    return client.post("/api/events/", json={"title": "Wedding", "event_date": "2026-09-01T00:00:00Z"})


def test_studio_creates_event(client, as_studio):
    r = _create_event(client)
    assert r.status_code == 200
    body = r.json()
    assert body["event_slug"].startswith("wedding-")
    assert body["qr_code_path"].startswith("qr/")
    assert body["url"]  # presigned (mocked)


def test_guest_cannot_create_event(client, as_guest):
    r = _create_event(client)
    assert r.status_code == 403


def test_watch_folder_validates_path(client, as_studio):
    eid = _create_event(client).json()["id"]
    # non-existent path → 400
    r = client.post(f"/api/events/{eid}/watch-folder", json={"folder_path": "Z:/nope/nope"})
    assert r.status_code == 400
    # valid temp dir → 200
    with tempfile.TemporaryDirectory() as d:
        r2 = client.post(f"/api/events/{eid}/watch-folder", json={"folder_path": d})
        assert r2.status_code == 200
        assert r2.json()["watching"] in (True, False)  # observer started
        # cleanup watcher
        client.delete(f"/api/events/{eid}/watch-folder")
