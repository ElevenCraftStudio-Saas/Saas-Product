"""API token (desktop agent auth) — admin-created, assigned to a target user."""
from tests.conftest import make_user


def _agent_user_id():
    return make_user(role="user", email="agentowner@test.ai", firebase_uid="agentowner").id


def test_create_and_list_token(client, as_admin):
    uid = _agent_user_id()
    r = client.post("/api/auth/tokens", json={"user_id": uid, "name": "Studio laptop"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token"].startswith("wfa_")
    assert body["token_prefix"].startswith("wfa_")
    assert body["name"] == "Studio laptop"

    lst = client.get("/api/auth/tokens")
    assert lst.status_code == 200
    assert len(lst.json()) == 1
    assert "token" not in lst.json()[0]  # plaintext never returned by list


def test_revoke_token(client, as_admin):
    uid = _agent_user_id()
    tid = client.post("/api/auth/tokens", json={"user_id": uid, "name": "temp"}).json()["id"]
    r = client.delete(f"/api/auth/tokens/{tid}")
    assert r.status_code == 204
    assert client.get("/api/auth/tokens").json()[0]["revoked"] is True


def test_api_key_authenticates_as_user(client, as_admin):
    uid = _agent_user_id()
    token = client.post("/api/auth/tokens", json={"user_id": uid, "name": "agent"}).json()["token"]
    # Drop the auth override and authenticate purely via X-API-Key.
    client.app.dependency_overrides.clear()
    r = client.get("/api/events/", headers={"X-API-Key": token})
    assert r.status_code == 200  # resolved to the assigned studio user


def test_revoked_key_rejected(client, as_admin):
    uid = _agent_user_id()
    created = client.post("/api/auth/tokens", json={"user_id": uid, "name": "agent"}).json()
    client.delete(f"/api/auth/tokens/{created['id']}")
    client.app.dependency_overrides.clear()
    r = client.get("/api/events/", headers={"X-API-Key": created["token"]})
    assert r.status_code == 401


def test_token_target_must_be_user_role(client, as_admin):
    p = make_user(role="pending", email="p2@test.ai", firebase_uid="p2")
    r = client.post("/api/auth/tokens", json={"user_id": p.id, "name": "x"})
    assert r.status_code == 400


def test_bad_key_rejected(client):
    client.app.dependency_overrides.clear()
    r = client.get("/api/events/", headers={"X-API-Key": "wfa_not_a_real_token"})
    assert r.status_code == 401
