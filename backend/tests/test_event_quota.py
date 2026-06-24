"""Per-user event quota enforcement on create."""


def _payload(t):
    return {"title": t, "description": "d", "event_date": "2026-07-01T00:00:00"}


def test_event_create_allowed_under_limit(client, as_user):
    assert client.post("/api/events/", json=_payload("E1")).status_code == 200


def test_event_create_blocked_at_limit(client, as_user):
    assert client.post("/api/events/", json=_payload("E1")).status_code == 200
    assert client.post("/api/events/", json=_payload("E2")).status_code == 200
    r = client.post("/api/events/", json=_payload("E3"))
    assert r.status_code == 403
    assert r.json()["detail"] == "Event limit reached (2/2). Contact your admin to raise it."
