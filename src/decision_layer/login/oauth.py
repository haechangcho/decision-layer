"""MCP OAuth broker using the existing OIDC login and canonical identity (ADR-131).

The SDK handles OAuth client authentication, exact redirect matching and S256
PKCE. A browser must explicitly approve each connection after a fresh IdP login.
DL issues a short-lived, resource-bound opaque token; Cube credentials stay on
the server and are independently issued by Login.credentials_for.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import asdict
from html import escape
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from cryptography.fernet import Fernet, InvalidToken
from mcp.server.auth.provider import (AccessToken, AuthorizationCode, AuthorizationParams,
                                     AuthorizeError, OAuthAuthorizationServerProvider,
                                     RegistrationError, TokenError)
from mcp.server.auth.routes import create_auth_routes
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route

from ..i18n import _, negotiate, set_locale
from .oauth_store import OAuthStore
from .routes import _page
from .sessions import Person

SCOPE = "decision-layer"
COOKIE = "dl_mcp_flow"
FLOW_SECONDS = 600


class OAuthProvider(OAuthAuthorizationServerProvider):
    def __init__(self, login):
        self.login = login
        self.base = login.config.public_url
        self.resource = self.base + "/mcp"
        self.store = OAuthStore(login.settings.database_url)
        key = hmac.new(login.config.session_secret.encode(), b"decision-layer:oauth-state:v1", hashlib.sha256).digest()
        self.cipher = Fernet(base64.urlsafe_b64encode(key))

    def _key(self, kind, key):
        return kind + ":" + (key if kind == "client" else hashlib.sha256(key.encode()).hexdigest())

    async def save(self, kind, key, doc, expires=None):
        payload = self.cipher.encrypt(json.dumps(doc).encode()).decode()
        await self.store.put(self._key(kind, key), payload, expires)

    async def read(self, kind, key, *, consume=False):
        payload = await self.store.read(self._key(kind, key), consume=consume)
        if payload is None:
            return None
        try:
            return json.loads(self.cipher.decrypt(payload.encode()))
        except (InvalidToken, ValueError):
            return None

    async def get_client(self, client_id):
        doc = await self.read("client", client_id)
        return OAuthClientInformationFull.model_validate(doc) if doc else None

    async def register_client(self, client_info):
        for uri in client_info.redirect_uris or []:
            parsed = urlsplit(str(uri))
            local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
            if (parsed.hostname not in self.login.config.mcp_redirect_hosts or parsed.fragment
                    or parsed.username is not None or parsed.password is not None or parsed.scheme not in ("http", "https")
                    or (parsed.scheme != "https" and not local)):
                raise RegistrationError("invalid_redirect_uri", "Redirect host is not approved for this deployment")
        if await self.store.count_clients() >= 1000:
            raise RegistrationError("invalid_client_metadata", "Client registration capacity reached")
        client_info.grant_types = ["authorization_code"]
        client_info.response_types = ["code"]
        await self.save("client", client_info.client_id, client_info.model_dump(mode="json"))

    async def authorize(self, client, params):
        if params.resource not in (None, self.resource):
            raise AuthorizeError("invalid_request", "Unknown MCP resource")
        if set(params.scopes or []) - {SCOPE}:
            raise AuthorizeError("invalid_scope", "Unknown scope")
        request_id = secrets.token_urlsafe(32)
        expires = time.time() + FLOW_SECONDS
        await self.save("flow", request_id, {"client_id": client.client_id,
                        "params": params.model_dump(mode="json"), "csrf": secrets.token_urlsafe(32),
                        "expires_at": expires}, expires)
        return self.base + "/oauth/start?" + urlencode({"request": request_id})

    async def load_authorization_code(self, client, authorization_code):
        doc = await self.read("code", authorization_code)
        if not doc or doc["client_id"] != client.client_id:
            return None
        return AuthorizationCode(code=authorization_code, **doc["authorization"])

    async def exchange_authorization_code(self, client, authorization_code):
        # The SDK has checked client authentication, redirect URI and S256 PKCE.
        doc = await self.read("code", authorization_code.code, consume=True)
        if not doc or doc["client_id"] != client.client_id:
            raise TokenError("invalid_grant", "Code expired or already used")
        token, record = await self.login.tokens.create(Person(**doc["person"]),
            "OAuth: " + (client.client_name or client.client_id), 0,
            seconds=self.login.config.mcp_access_token_seconds,
            client_id=client.client_id, resource=self.resource)
        return OAuthToken(access_token=token, token_type="Bearer",
                          expires_in=record.expires_at - record.created_at, scope=SCOPE)

    async def load_refresh_token(self, client, refresh_token):
        return None

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        raise TokenError("unsupported_grant_type", "Sign in again after the access token expires")

    async def load_access_token(self, token):
        record = await self.login.tokens.verify(token, resource=self.resource)
        if not record or record.resource != self.resource or not record.client_id:
            return None
        return AccessToken(token=token, client_id=record.client_id, scopes=[SCOPE],
                           expires_at=record.expires_at, resource=self.resource, subject=record.subject)

    async def revoke_token(self, token):
        record = await self.login.tokens.verify(token.token, resource=self.resource)
        if record:
            await self.login.tokens.revoke(record.subject, record.id)

    def bound(self, request, request_id):
        value = request.cookies.get(COOKIE, "")
        return bool(value and request_id and secrets.compare_digest(value, request_id))

    async def start(self, request: Request):
        set_locale(negotiate(request.headers.get("accept-language"), self.login.settings.locale))
        request_id = request.query_params.get("request", "")
        if not await self.read("flow", request_id):
            return _page(_("Connection expired"), _("Start the MCP connection again."), 400)
        next_path = "/oauth/consent?" + urlencode({"request": request_id})
        response = RedirectResponse("/auth/login?" + urlencode({"next": next_path}), 302)
        response.set_cookie(COOKIE, request_id, max_age=FLOW_SECONDS, path="/oauth",
                            httponly=True, secure=self.login.config.secure_cookies, samesite="lax")
        return response

    async def consent(self, request: Request):
        set_locale(negotiate(request.headers.get("accept-language"), self.login.settings.locale))
        request_id = request.query_params.get("request", "")
        doc = await self.read("flow", request_id) if self.bound(request, request_id) else None
        person = self.login.session_person(request)
        if not doc or not person:
            return _page(_("Connection expired"), _("Start the MCP connection again."), 400)
        client = await self.get_client(doc["client_id"])
        if client is None:
            return _page(_("Connection expired"), _("The client is no longer registered."), 400)
        if request.method == "GET":
            if doc.get("person") and doc["person"]["subject"] != person.subject:
                return _page(_("Account changed"), _("Start the MCP connection again."), 400)
            doc["person"] = asdict(person)
            await self.save("flow", request_id, doc, doc["expires_at"])
            redirect = doc["params"]["redirect_uri"]
            identity = _("Allow {client} to act as {person} ({role})?", client=client.client_name or client.client_id,
                         person=person.name or person.subject, role=person.role)
            body = (f"<h1>{escape(_('Connect to Decision Layer'))}</h1><p>{escape(identity)}</p>"
                    f"<p>{escape(_('The client can use your available analysis tools and data. Recipe changes follow your role.'))}</p>"
                    f"<p>{escape(_('Connection lasts {minutes} minutes. Revoke it from Access tokens.', minutes=self.login.config.mcp_access_token_seconds // 60))}</p>"
                    f"<p>{escape(_('Return address'))}: <code>{escape(redirect)}</code></p>"
                    f"<form method='post'><input type='hidden' name='csrf' value='{escape(doc['csrf'])}'>"
                    f"<button name='decision' value='allow'>{escape(_('Connect'))}</button> "
                    f"<button name='decision' value='deny'>{escape(_('Cancel'))}</button></form>")
            return _page(_("Connect MCP"), body)
        if request.headers.get("origin", "").rstrip("/") != self.base:
            return _page("Access denied", "Invalid origin.", 403)
        body = await request.body()
        if len(body) > 4096:
            return _page("Access denied", "Invalid form.", 400)
        form = parse_qs(body.decode(errors="replace"))
        if (not secrets.compare_digest(form.get("csrf", [""])[0], doc["csrf"])
                or doc.get("person") != asdict(person)):
            return _page("Access denied", "Invalid consent request.", 403)
        doc = await self.read("flow", request_id, consume=True)
        if not doc:
            return _page("Connection expired", "This request was already used.", 400)
        params = AuthorizationParams.model_validate(doc["params"])
        query = dict(parse_qs(urlsplit(str(params.redirect_uri)).query, keep_blank_values=True))
        query.update(iss=[self.base])
        if params.state is not None:
            query["state"] = [params.state]
        if form.get("decision") != ["allow"]:
            query["error"] = ["access_denied"]
        else:
            code = secrets.token_urlsafe(32)
            authorization = AuthorizationCode(code=code, client_id=client.client_id, scopes=[SCOPE],
                expires_at=time.time() + 120, code_challenge=params.code_challenge,
                redirect_uri=params.redirect_uri, redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
                resource=self.resource, subject=person.subject).model_dump(mode="json", exclude={"code"})
            await self.save("code", code, {"client_id": client.client_id, "person": asdict(person),
                                          "authorization": authorization}, authorization["expires_at"])
            query["code"] = [code]
        parsed = urlsplit(str(params.redirect_uri))
        response = RedirectResponse(urlunsplit(parsed._replace(query=urlencode(query, doseq=True))), 302,
                                    headers={"Cache-Control": "no-store"})
        response.delete_cookie(COOKIE, path="/oauth")
        return response


class ResourceGuard:
    """Bind /token requests to the one approved resource, retaining SDK body limits."""
    def __init__(self, app, resource, *, revocation=False):
        self.app, self.resource, self.revocation = app, resource, revocation

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body += message.get("body", b"")
            if len(body) > 16384:
                return await JSONResponse({"error": "invalid_request"}, 413)(scope, receive, send)
            if not message.get("more_body"):
                break
        resources = parse_qs(body.decode(errors="replace")).get("resource", [])
        if resources and resources != [self.resource]:
            response = JSONResponse({"error": "invalid_target"}, 400, headers={"Cache-Control": "no-store", "Access-Control-Allow-Origin": "*"})
            return await response(scope, receive, send)
        # RFC 6749 Basic clients may send client_id only in Authorization. The
        # SDK expects it in the form too; copy the identifier, never the secret.
        headers = dict(scope.get("headers", []))
        authorization = headers.get(b"authorization", b"").decode(errors="replace")
        form = parse_qs(body.decode(errors="replace"), keep_blank_values=True)
        if authorization.startswith("Basic ") and "client_id" not in form:
            from urllib.parse import unquote
            try:
                basic_id, secret = base64.b64decode(authorization[6:], validate=True).decode().split(":", 1)
                body += b"&" + urlencode({"client_id": unquote(basic_id)}).encode()
            except (ValueError, UnicodeError):
                pass  # The SDK returns the client-authentication failure.
        # SDK RevocationRequest currently declares nullable client_secret without
        # a default. Supply an empty optional field for public/Basic clients;
        # the SDK still authenticates the registered client method independently.
        if self.revocation and "client_secret" not in parse_qs(body.decode(errors="replace"), keep_blank_values=True):
            body += b"&client_secret="
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def oauth_routes(login):
    provider = OAuthProvider(login)
    options = ClientRegistrationOptions(enabled=True, valid_scopes=[SCOPE], default_scopes=[SCOPE])
    routes = create_auth_routes(provider, AnyHttpUrl(provider.base),
                                client_registration_options=options, revocation_options=RevocationOptions(enabled=True))

    async def metadata(request):
        return JSONResponse({"issuer": provider.base, "authorization_endpoint": provider.base + "/authorize",
            "token_endpoint": provider.base + "/token", "registration_endpoint": provider.base + "/register",
            "revocation_endpoint": provider.base + "/revoke", "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"], "scopes_supported": [SCOPE],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"]},
            headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-store"})

    async def resource_metadata(request):
        return JSONResponse({"resource": provider.resource, "authorization_servers": [provider.base],
                             "scopes_supported": [SCOPE], "bearer_methods_supported": ["header"]},
                            headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-store"})

    for route in routes:
        if route.path == "/token":
            route.app = ResourceGuard(route.app, provider.resource)
        elif route.path == "/revoke":
            route.app = ResourceGuard(route.app, provider.resource, revocation=True)
    routes = [r for r in routes if r.path != "/.well-known/oauth-authorization-server"]
    result = [*routes, Route("/.well-known/oauth-authorization-server", metadata),
            Route("/.well-known/oauth-protected-resource", resource_metadata),
            Route("/.well-known/oauth-protected-resource/mcp", resource_metadata),
            Route("/oauth/start", provider.start), Route("/oauth/consent", provider.consent, methods=["GET", "POST"])]
    for route in result:
        if route.path == "/oauth/consent":
            route.app = ResourceGuard(route.app, provider.resource)
    return result
