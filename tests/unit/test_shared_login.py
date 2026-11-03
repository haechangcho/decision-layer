"""Shared deployment login (ADR-130): OIDC sessions, access tokens and roles."""
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from decision_layer.api.app import create_app
from decision_layer.settings import LoginSettings, Settings
from tests.support.semantic import FakeProvider, RR, Q3
from tests.unit.test_access import bearer
from tests.unit.test_recipe_authoring import recipe

ISSUER = "https://idp.example/application/o/decision-layer/"
SESSION_SECRET = "s" * 40
CUBE_SECRET = "c" * 40


class FakeIdP:
    """An authentik-like provider: discovery, JWKS and a token endpoint."""

    def __init__(self) -> None:
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.claims: dict = {}
        self.codes: dict[str, dict] = {}
        self.issuer = ISSUER

    def authorize(self, url: str, groups: list[str], sub: str = "alice") -> str:
        query = parse_qs(urlsplit(url).query)
        code = f"code-{len(self.codes)}"
        self.codes[code] = {"nonce": query["nonce"][0], "groups": groups, "sub": sub,
                            "challenge": query["code_challenge"][0]}
        return f"/auth/callback?code={code}&state={query['state'][0]}"

    def handler(self, request: httpx.Request) -> httpx.Response:
        base = ISSUER.rstrip("/")
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(200, json={
                "issuer": self.issuer, "authorization_endpoint": base + "/authorize",
                "token_endpoint": base + "/token", "jwks_uri": base + "/jwks",
                "end_session_endpoint": base + "/end-session/"})
        if request.url.path.endswith("/jwks"):
            jwk = jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key(), as_dict=True)
            return httpx.Response(200, json={"keys": [{**jwk, "kid": "k1", "alg": "RS256", "use": "sig"}]})
        if request.url.path.endswith("/token"):
            form = parse_qs(request.content.decode())
            grant = self.codes.pop(form["code"][0], None)
            if grant is None:
                return httpx.Response(400, json={"error": "invalid_grant"})
            now = int(time.time())
            claims = {"iss": self.issuer, "aud": "dl-client", "sub": grant["sub"], "iat": now, "exp": now + 300,
                      "nonce": grant["nonce"], "name": "Alice", "cube_groups": grant["groups"], **self.claims}
            token = jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "k1"})
            return httpx.Response(200, json={"id_token": token, "access_token": "unused"})
        return httpx.Response(404)


def shared_settings(tmp_path, **login) -> Settings:
    return Settings(
        database_url="memory", recipes_dir=str(tmp_path), deployment_mode="shared",
        http_allowed_hosts=("testserver", "dl.example", "127.0.0.1"),
        login=LoginSettings(issuer=ISSUER, client_id="dl-client", client_secret="client-secret",
                            public_url="https://dl.example", session_secret=SESSION_SECRET,
                            cube_token_secret=CUBE_SECRET, admin_groups=("dl-poc-admin",),
                            user_groups=("dl-poc-guest",), **login))


@pytest.fixture
def idp():
    return FakeIdP()


@pytest.fixture
def client(cube_meta, tmp_path, idp):
    app = create_app(shared_settings(tmp_path), FakeProvider(cube_meta))
    app.state.login.oidc.transport = httpx.MockTransport(idp.handler)
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def sign_in(client, idp, groups, sub="alice", next_path="/ui/runs"):
    start = client.get(f"/auth/login?next={next_path}", follow_redirects=False)
    assert start.status_code == 302 and start.headers["location"].startswith(ISSUER.rstrip("/") + "/authorize")
    query = parse_qs(urlsplit(start.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"] and query["redirect_uri"] == ["https://dl.example/auth/callback"]
    return client.get(idp.authorize(start.headers["location"], groups, sub), follow_redirects=False)


def test_shared_mode_requires_complete_login_configuration(tmp_path):
    with pytest.raises(ValueError, match="DL_OIDC_ISSUER"):
        create_app(Settings(database_url="memory", deployment_mode="shared"))
    for change, message in [({"session_secret": "short"}, "at least 32"),
                            ({"cube_token_secret": SESSION_SECRET}, "must differ"),
                            ({"public_url": "http://dl.example"}, "https"),
                            ({"public_url": "https://other.example"}, "DL_HTTP_ALLOWED_HOSTS")]:
        settings = shared_settings(tmp_path)
        login = LoginSettings(**{**settings.login.__dict__, **change})
        with pytest.raises(ValueError, match=message):
            create_app(Settings(**{**settings.__dict__, "login": login}))


@pytest.mark.parametrize("unsafe", [{"allow_service_credentials": True}, {"allow_method_editing": True},
                                    {"source_admin_token": "admin"}])
def test_shared_mode_refuses_operator_escape_hatches(tmp_path, unsafe):
    settings = shared_settings(tmp_path)
    with pytest.raises(ValueError, match="Shared deployment cannot"):
        create_app(Settings(**{**settings.__dict__, **unsafe}))


def test_requests_without_login_are_refused_and_provider_tokens_are_not_identities(client):
    missing = client.get("/me")
    assert missing.status_code == 401 and missing.json()["error"]["code"] == "LOGIN_REQUIRED"
    assert missing.json()["error"]["details"]["login_url"] == "/auth/login"
    # A Cube-accepted JWT is not an application identity in shared mode.
    assert client.get("/me", headers=bearer("alice")).status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer dlp_unknown"}).status_code == 401
    forged = jwt.encode({"sub": "oidc:alice", "role": "admin", "aud": "decision-layer:session",
                         "exp": int(time.time()) + 60}, "x" * 40, algorithm="HS256")
    client.cookies.set("dl_session", forged)
    assert client.get("/me").status_code == 401


def test_login_creates_session_with_role_and_signed_cube_identity(client, idp):
    done = sign_in(client, idp, ["dl-poc-admin"])
    assert done.status_code == 302 and done.headers["location"] == "/ui/runs"
    cookie = done.headers["set-cookie"]
    assert "dl_session=" in cookie and "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
    me = client.get("/me").json()
    assert me == {"subject": "oidc:alice", "groups": ["admin"], "authentication": "login", "role": "admin", "name": "Alice"}
    creds = client.app.state.login.credentials_for(client.app.state.login.session_person(
        type("R", (), {"cookies": client.cookies})()))
    claims = jwt.decode(creds.bearer(), CUBE_SECRET, algorithms=["HS256"])
    assert claims["sub"] == "oidc:alice" and claims["cubeGroups"] == ["admin"] and claims["exp"] - claims["iat"] <= 300


def test_guest_gets_user_role_and_unknown_groups_are_denied(client, idp):
    assert sign_in(client, idp, ["dl-poc-guest"]).status_code == 302
    assert client.get("/me").json()["role"] == "user" and client.get("/me").json()["groups"] == ["guest"]
    client.cookies.clear()
    denied = sign_in(client, idp, ["admin", "insurance"], sub="mallory")
    assert denied.status_code == 403 and "dl_session" not in denied.headers.get("set-cookie", "")


def test_callback_rejects_wrong_state_issuer_audience_and_replay(client, idp):
    start = client.get("/auth/login", follow_redirects=False)
    callback = idp.authorize(start.headers["location"], ["dl-poc-admin"])
    tampered = callback.rsplit("state=", 1)[0] + "state=other"
    assert client.get(tampered, follow_redirects=False).status_code == 400
    idp.claims = {"aud": "another-client"}
    assert client.get(callback, follow_redirects=False).status_code == 401
    idp.claims = {}
    # Codes are single use at the IdP; a second callback fails closed.
    assert client.get(callback, follow_redirects=False).status_code == 401
    assert client.get("/me").status_code == 401


def test_next_path_cannot_redirect_off_site(client, idp):
    for unsafe in ("https://evil.example", "//evil.example", "/\\evil.example"):
        assert sign_in(client, idp, ["dl-poc-admin"], next_path=unsafe).headers["location"] == "/ui/"
        client.cookies.clear()


def test_access_tokens_act_as_owner_and_can_be_revoked(client, idp):
    sign_in(client, idp, ["dl-poc-guest"])
    assert client.get("/auth/tokens").status_code == 200
    page = client.post("/auth/tokens", content="label=Claude+Code",
                       headers={"Content-Type": "application/x-www-form-urlencoded", "Origin": "https://dl.example"})
    token = page.text.split("<pre>", 1)[1].split("</pre>", 1)[0]
    assert token.startswith("dlp_") and "https://dl.example/mcp" in page.text
    browser_cookies = dict(client.cookies)
    client.cookies.clear()
    auth = {"Authorization": f"Bearer {token}"}
    assert client.get("/me", headers=auth).json()["subject"] == "oidc:alice"
    # A token cannot mint further tokens.
    assert client.get("/auth/tokens", headers=auth, follow_redirects=False).status_code == 302
    run = client.post("/methods/test.series:run", headers=auth,
                      json={"bindings": {"metric": RR}, "scope": {"date_range": list(Q3)}}).json()
    for name, value in browser_cookies.items():
        client.cookies.set(name, value)
    assert client.get(f"/runs/{run['run_id']}").status_code == 200  # same owner in the browser
    token_id = client.app.state.login.tokens._rows and next(iter(client.app.state.login.tokens._rows))
    assert client.post(f"/auth/tokens/{token_id}/revoke", headers={"Origin": "https://dl.example"},
                       follow_redirects=False).status_code == 303
    client.cookies.clear()
    assert client.get("/me", headers=auth).status_code == 401


def test_cross_site_form_posts_are_rejected(client, idp):
    sign_in(client, idp, ["dl-poc-admin"])
    response = client.post("/auth/tokens", content="label=x", headers={
        "Content-Type": "application/x-www-form-urlencoded", "Origin": "https://attacker.example"})
    assert response.status_code == 403


def test_runs_are_private_and_recipe_writes_follow_roles(cube_meta, tmp_path, idp):
    app = create_app(shared_settings(tmp_path), FakeProvider(cube_meta))
    app.state.login.oidc.transport = httpx.MockTransport(idp.handler)
    with TestClient(app, base_url="https://testserver") as admin, TestClient(app, base_url="https://testserver") as guest:
        sign_in(admin, idp, ["dl-poc-admin"], sub="alice")
        sign_in(guest, idp, ["dl-poc-guest"], sub="bob")
        run = admin.post("/methods/test.series:run",
                         json={"bindings": {"metric": RR}, "scope": {"date_range": list(Q3)}}).json()
        assert guest.get(f"/runs/{run['run_id']}").status_code == 404
        body = {"recipe": recipe().model_copy(update={"status": "draft"}).model_dump(mode="json")}
        assert guest.put("/recipes/orders-test", json=body).status_code == 403
        assert admin.put("/recipes/orders-test", json=body).status_code == 200
        published = admin.post("/recipes/orders-test/publish", json={"base_version": "1.0.0"})
        assert published.status_code == 200
        assert guest.get("/recipes/orders-test").status_code == 200
        assert guest.post("/recipes/orders-test/publish", json={"base_version": published.json()["version"]}).status_code == 403


def test_logout_clears_session_and_uses_provider_end_session(client, idp):
    sign_in(client, idp, ["dl-poc-admin"])
    out = client.get("/auth/logout", follow_redirects=False)
    assert out.headers["location"] == ISSUER.rstrip("/") + "/end-session/"
    assert client.get("/me").status_code == 401


pytestmark = pytest.mark.usefixtures("query_methods")


def test_every_api_route_needs_login_except_health(client, idp):
    for path in ("/methods", "/methods/stats.regression_adjustment", "/sources/current", "/execution-policy",
                 "/recipes", "/semantic/catalog", "/runs"):
        assert client.get(path).status_code == 401, path
    for path in ("/docs", "/openapi.json"):
        assert client.get(path).status_code in (401, 404), path
    assert client.get("/health").status_code == 200
    sign_in(client, idp, ["dl-poc-guest"])
    assert client.get("/methods").status_code == 200


def test_shared_source_status_explains_session_auth_without_exposing_secrets(client, idp):
    sign_in(client, idp, ['dl-poc-admin'])
    response = client.get('/sources/current')
    assert response.status_code == 200
    status = response.json()
    assert status['deployment_mode'] == 'shared' and not status['editable']
    assert 'client_secret' not in status and 'cube_token_secret' not in status
    assert client.get('/me').json()['authentication'] == 'login'
