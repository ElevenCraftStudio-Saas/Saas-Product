"""API token (desktop agent auth) — create/list/revoke + X-API-Key auth."""


def test_create_and_list_token(client, as_studio):
    r = client.post("/api/auth/tokens", json={"name": "Studio laptop"})
    assert r.status_code == 200
    body = r.json()
    assert body["token"].startswith("wfa_")
    assert body["token_prefix"].startswith("wfa_")
    assert body["name"] == "Studio laptop"

    lst = client.get("/api/auth/tokens")
    assert lst.status_code == 200
    assert len(lst.json()) == 1
    # plaintext is never returned by the list endpoint
    assert "token" not in lst.json()[0]


def test_revoke_token(client, as_studio):
    tid = client.post("/api/auth/tokens", json={"name": "temp"}).json()["id"]
    r = client.delete(f"/api/auth/tokens/{tid}")
    assert r.status_code == 204
    assert client.get("/api/auth/tokens").json()[0]["revoked"] is True


def test_api_key_authenticates_as_studio(client, as_studio):
    # Mint a token while authed as studio…
    token = client.post("/api/auth/tokens", json={"name": "agent"}).json()["token"]
    # …then drop the auth override and authenticate purely via X-API-Key.
    client.app.dependency_overrides.clear()
    r = client.get("/api/events/", headers={"X-API-Key": token})
    assert r.status_code == 200  # resolved to the studio user


def test_revoked_key_rejected(client, as_studio):
    created = client.post("/api/auth/tokens", json={"name": "agent"}).json()
    client.delete(f"/api/auth/tokens/{created['id']}")
    client.app.dependency_overrides.clear()
    r = client.get("/api/events/", headers={"X-API-Key": created["token"]})
    assert r.status_code == 401


def test_bad_key_rejected(client):
    client.app.dependency_overrides.clear()
    r = client.get("/api/events/", headers={"X-API-Key": "wfa_not_a_real_token"})
    assert r.status_code == 401
