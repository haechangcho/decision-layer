"""MCP OAuth uses the same OIDC identity, permissions and Run ownership as Web."""
import asyncio
import hashlib
import json
import re
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient

from decision_layer.api.app import create_app
from decision_layer.console import create_console
from decision_layer.login.oidc import challenge, new_secret
from decision_layer.login.oauth import OAuthProvider
from decision_layer.login.oauth_store import OAuthStore
from decision_layer.login.sessions import Person
from decision_layer.settings import Settings
from tests.support.semantic import FakeProvider, RR, Q3
from tests.unit.test_shared_login import FakeIdP, shared_settings

BASE = "https://dl.example"
RESOURCE = BASE + "/mcp"
REDIRECT = "http://localhost:1455/callback"


@pytest.fixture
def oauth(tmp_path, monkeypatch, cube_meta):
    import decision_layer.console as console
    settings = shared_settings(tmp_path / "recipes")
    monkeypatch.setattr(console, "create_app", lambda s: create_app(s, FakeProvider(cube_meta)))
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html>")
    app = create_console(settings, static)
    api = next(r.app for r in app.routes if getattr(r, "path", None) == "/api")
    idp = FakeIdP()
    api.state.login.oidc.transport = httpx.MockTransport(idp.handler)
    with TestClient(app, base_url=BASE) as client:
        yield client, idp, api.state.login


def register(client, **extra):
    response = client.post("/register", json={"client_name": "Test analyst", "redirect_uris": [REDIRECT],
        "token_endpoint_auth_method": "none", "grant_types": ["authorization_code"], **extra})
    assert response.status_code == 201, response.text
    return response.json()


def authorize(client, idp, registered, *, group="dl-poc-admin", sub="alice"):
    verifier = new_secret()
    params = {"response_type": "code", "client_id": registered["client_id"], "redirect_uri": REDIRECT,
              "code_challenge": challenge(verifier), "code_challenge_method": "S256",
              "state": "client-state", "resource": RESOURCE, "scope": "decision-layer"}
    start = client.get("/authorize", params=params, follow_redirects=False)
    assert start.status_code == 302, start.text
    start = client.get(start.headers["location"], follow_redirects=False)
    assert start.headers["location"].startswith("/auth/login?")
    upstream = client.get(start.headers["location"], follow_redirects=False)
    callback = idp.authorize(upstream.headers["location"], [group], sub=sub)
    logged_in = client.get(callback, follow_redirects=False)
    if logged_in.status_code != 302:
        return verifier, logged_in, None
    consent_url = logged_in.headers["location"]
    page = client.get(consent_url)
    assert page.status_code == 200 and "Test analyst" in page.text
    csrf = re.search("name='csrf' value='([^']+)'", page.text)[1]
    return verifier, page, (consent_url, csrf)


def approve(client, consent, *, decision="allow", origin=BASE):
    url, csrf = consent
    return client.post(url, data={"csrf": csrf, "decision": decision},
                       headers={"Origin": origin}, follow_redirects=False)


def redeem(client, registered, redirect, verifier, **extra):
    query = parse_qs(urlsplit(redirect).query)
    return client.post("/token", data={"grant_type": "authorization_code", "client_id": registered["client_id"],
        "code": query["code"][0], "code_verifier": verifier, "redirect_uri": REDIRECT, "resource": RESOURCE, **extra})


def test_discovery_and_missing_token_advertise_oauth(oauth):
    client, _, _ = oauth
    denied = client.post("/mcp", json={})
    assert denied.status_code == 401
    assert 'resource_metadata="' + BASE + '/.well-known/oauth-protected-resource"' in denied.headers["www-authenticate"]
    resource = client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert resource["resource"] == RESOURCE and resource["authorization_servers"] == [BASE]
    metadata = client.get("/.well-known/oauth-authorization-server").json()
    assert metadata["code_challenge_methods_supported"] == ["S256"]
    assert metadata["grant_types_supported"] == ["authorization_code"]
    assert "none" in metadata["token_endpoint_auth_methods_supported"]
    assert client.get("/.well-known/oauth-authorization-server", headers={"Host": "evil.example"}).status_code == 400


def test_oauth_authentik_consent_code_and_resource_bound_token(oauth):
    client, idp, login = oauth
    registered = register(client)
    verifier, page, consent = authorize(client, idp, registered)
    assert "admin" in page.text
    done = approve(client, consent)
    query = parse_qs(urlsplit(done.headers["location"]).query)
    assert query["state"] == ["client-state"] and query["iss"] == [BASE]
    response = redeem(client, registered, done.headers["location"], verifier)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["expires_in"] == 3600 and "refresh_token" not in payload
    token = payload["access_token"]
    record = asyncio.run(login.tokens.verify(token, resource=RESOURCE))
    assert record.subject == "oidc:alice" and record.role == "admin"
    assert record.client_id == registered["client_id"] and record.resource == RESOURCE
    assert asyncio.run(login.tokens.verify(token, resource="https://cube.example")) is None
    assert asyncio.run(login.tokens.verify(token)) is None
    client.cookies.clear()
    me = client.get("/me", headers={"Authorization": "Bearer " + token})
    assert me.status_code == 200 and me.json()["subject"] == "oidc:alice"
    replay = redeem(client, registered, done.headers["location"], verifier)
    assert replay.status_code == 400 and replay.json()["error"] == "invalid_grant"
    revoked = client.post("/revoke", data={"client_id": registered["client_id"], "token": token})
    assert revoked.status_code == 200, revoked.text
    assert client.get("/me", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_wrong_pkce_client_redirect_and_resource_cannot_redeem(oauth):
    client, idp, _ = oauth
    registered = register(client)
    other = register(client)
    verifier, _, consent = authorize(client, idp, registered)
    location = approve(client, consent).headers["location"]
    for kwargs in ({"code_verifier": new_secret()}, {"redirect_uri": "http://localhost:1455/other"},
                   {"resource": "https://cube.example/mcp"}, {"resource": RESOURCE + "/other"}):
        assert redeem(client, registered, location, verifier, **kwargs).status_code == 400
    assert redeem(client, other, location, verifier).status_code == 400
    assert redeem(client, registered, location, verifier).status_code == 200


@pytest.mark.parametrize("method", ["client_secret_post", "client_secret_basic"])
def test_confidential_clients_must_authenticate_and_only_revoke_their_own_token(oauth, method):
    client, idp, _ = oauth
    registered = register(client, token_endpoint_auth_method=method)
    other = register(client)
    verifier, _, consent = authorize(client, idp, registered)
    location = approve(client, consent).headers["location"]
    assert redeem(client, registered, location, verifier).status_code == 401
    code = parse_qs(urlsplit(location).query)["code"][0]
    form = {"grant_type": "authorization_code", "code": code, "code_verifier": verifier,
            "redirect_uri": REDIRECT, "resource": RESOURCE}
    auth = None
    if method == "client_secret_post":
        form.update(client_id=registered["client_id"], client_secret=registered["client_secret"])
    else:
        auth = (registered["client_id"], registered["client_secret"])
    response = client.post("/token", data=form, auth=auth)
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    assert client.post("/revoke", data={"client_id": other["client_id"], "token": token}).status_code == 200
    assert client.get("/me", headers={"Authorization": "Bearer " + token}).status_code == 200
    revoke = {"token": token}
    if method == "client_secret_post":
        revoke.update(client_id=registered["client_id"], client_secret=registered["client_secret"])
    response = client.post("/revoke", data=revoke, auth=auth)
    assert response.status_code == 200, response.text
    assert client.get("/me", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_consent_is_explicit_browser_bound_and_csrf_protected(oauth):
    client, idp, _ = oauth
    registered = register(client)
    verifier, _, consent = authorize(client, idp, registered)
    assert approve(client, consent, origin="https://evil.example").status_code == 403
    assert client.post(consent[0], data={"csrf": "wrong", "decision": "allow"},
                       headers={"Origin": BASE}).status_code == 403
    cookies = dict(client.cookies)
    client.cookies.delete("dl_mcp_flow")
    assert client.get(consent[0]).status_code == 400
    for name, value in cookies.items():
        client.cookies.set(name, value)
    denied = approve(client, consent, decision="deny")
    assert parse_qs(urlsplit(denied.headers["location"]).query)["error"] == ["access_denied"]
    assert "code=" not in denied.headers["location"]
    assert approve(client, consent).status_code == 400


def test_unapproved_redirects_scopes_and_unauthorized_users_are_denied(oauth):
    client, idp, _ = oauth
    for uri in ("https://evil.example/callback", "http://claude.ai/callback", "javascript:alert(1)",
                "https://claude.ai.evil.example/callback", "http://localhost:1455/callback#fragment"):
        assert client.post("/register", json={"redirect_uris": [uri]}).status_code == 400
    registered = register(client)
    base = {"client_id": registered["client_id"], "response_type": "code", "redirect_uri": REDIRECT,
            "code_challenge": challenge(new_secret()), "code_challenge_method": "S256"}
    for extra in ({"resource": "https://evil.example"}, {"scope": "admin"},
                  {"redirect_uri": "http://localhost:1455/not-registered"}, {"code_challenge_method": "plain"}):
        response = client.get("/authorize", params={**base, **extra}, follow_redirects=False)
        assert response.status_code == 400 or "error=" in response.headers.get("location", "")
    _, denied, _ = authorize(client, idp, registered, group="unrelated")
    assert denied.status_code == 403


def test_expired_code_and_oversized_token_request_are_rejected(oauth, monkeypatch):
    client, idp, _ = oauth
    registered = register(client)
    verifier, _, consent = authorize(client, idp, registered)
    location = approve(client, consent).headers["location"]
    now = time.time()
    monkeypatch.setattr("decision_layer.login.oauth_store.time.time", lambda: now + 121)
    assert redeem(client, registered, location, verifier).status_code == 400
    assert client.post("/token", content="x=" + "a" * 17000).status_code == 413


def test_oauth_user_uses_canonical_run_ownership_and_recipe_permissions(oauth):
    client, idp, _ = oauth
    registered = register(client)
    verifier, _, consent = authorize(client, idp, registered, group="dl-poc-guest")
    location = approve(client, consent).headers["location"]
    token = redeem(client, registered, location, verifier).json()["access_token"]
    # Browser and OAuth are the same person, so a token-created Run is visible in Web.
    auth = {"Authorization": "Bearer " + token}
    run = client.post("/methods/test.series:run", headers=auth,
                      json={"bindings": {"metric": RR}, "scope": {"date_range": list(Q3)}})
    assert run.status_code == 200, run.text
    assert client.get("/runs/" + run.json()["run_id"]).status_code == 200
    assert client.post("/recipes/x/publish", json={"base_version": "1.0.0"}, headers=auth).status_code == 403


def test_sqlite_oauth_clients_and_tokens_survive_restart_with_encrypted_secrets(tmp_path):
    from decision_layer.login import Login
    from mcp.shared.auth import OAuthClientInformationFull
    settings = shared_settings(tmp_path)
    settings = Settings(**{**settings.__dict__, "database_url": "sqlite:///" + str(tmp_path / "state.db")})
    provider = OAuthProvider(Login(settings))
    client = OAuthClientInformationFull(client_id="persistent-client", client_secret="never-plaintext-secret",
        redirect_uris=[REDIRECT], client_name="Analyst", token_endpoint_auth_method="client_secret_post")
    asyncio.run(provider.register_client(client))
    restarted = OAuthProvider(Login(settings))
    assert asyncio.run(restarted.get_client("persistent-client")).client_secret == client.client_secret
    payload = restarted.store.db.execute("SELECT payload FROM oauth_state").fetchone()[0]
    assert "never-plaintext-secret" not in payload
    token, record = asyncio.run(provider.login.tokens.create(Person("oidc:alice", "user"),
        "OAuth", 0, seconds=3600, client_id=client.client_id, resource=RESOURCE))
    assert asyncio.run(restarted.login.tokens.verify(token, resource=RESOURCE)).subject == record.subject
    raw = json.loads(restarted.login.tokens.db.execute("SELECT doc FROM access_tokens").fetchone()[0])
    assert "client_id" not in raw and "resource" not in raw  # previous image can still read the JSON


def test_existing_sqlite_pat_and_legacy_writer_survive_additive_migration(tmp_path):
    from decision_layer.login.tokens import open_token_store
    path = tmp_path / "legacy.db"
    old_token = "dlp_legacy-test-fixture"
    now = int(time.time())
    doc = {"id": "legacy", "subject": "oidc:alice", "role": "user", "label": "Legacy",
           "created_at": now, "expires_at": now + 3600, "name": "Alice", "revoked_at": None}
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE access_tokens (id TEXT PRIMARY KEY, digest TEXT UNIQUE, subject TEXT, doc TEXT)")
        db.execute("INSERT INTO access_tokens VALUES (?, ?, ?, ?)",
                   ("legacy", hashlib.sha256(old_token.encode()).hexdigest(), "oidc:alice", json.dumps(doc)))
    store = open_token_store("sqlite:///" + str(path))
    assert asyncio.run(store.verify(old_token)).subject == "oidc:alice"
    assert json.loads(store.db.execute("SELECT doc FROM access_tokens").fetchone()[0]) == doc
    token, record = asyncio.run(store.create(Person("oidc:alice", "user"), "OAuth", 0,
        seconds=3600, client_id="fixture", resource=RESOURCE))
    raw = store.db.execute("SELECT doc FROM access_tokens WHERE id=?", (record.id,)).fetchone()[0]
    assert set(json.loads(raw)) == set(doc)
    assert asyncio.run(store.verify(token, resource=RESOURCE)).client_id == "fixture"


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_authorization_state_consume_is_single_use(tmp_path, backend):
    store = OAuthStore("memory" if backend == "memory" else "sqlite:///" + str(tmp_path / "state.db"))

    async def race():
        await store.put("code:key", "payload", time.time() + 30)
        return await asyncio.gather(store.read("code:key", consume=True), store.read("code:key", consume=True))
    assert sorted(str(v) for v in asyncio.run(race())) == ["None", "payload"]


pytestmark = pytest.mark.usefixtures("query_methods")
