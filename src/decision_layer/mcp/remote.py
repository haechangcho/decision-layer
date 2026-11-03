"""Streamable HTTP MCP for shared deployments (ADR-130).

The same tools as the stdio adapter, mounted at /mcp beside the API. Each request
must carry a verified OAuth or personal access token; it is forwarded unchanged to the REST API,
which verifies it like any other caller. There is no MCP-only execution path.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ..settings import Settings
from ..i18n import _, negotiate, reset_locale, set_locale
from ..login.tokens import PREFIX

PATH = "/mcp"


class _RequireAccessToken:
    def __init__(self, app: ASGIApp, login) -> None:
        self.app, self.login = app, login

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        from .server import REQUEST_TOKEN, REQUEST_LOCALE

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        locale = negotiate(headers.get("accept-language"), self.login.settings.locale)
        context = set_locale(locale)
        language = REQUEST_LOCALE.set(locale)
        reset = None
        try:
            token = headers.get("authorization", "").removeprefix("Bearer ").strip()
            resource = self.login.config.public_url + PATH
            record = await self.login.tokens.verify(token, resource=resource) if token.startswith(PREFIX) else None
            if record is None:
                metadata = self.login.config.public_url + "/.well-known/oauth-protected-resource"
                response = JSONResponse(status_code=401, headers={"WWW-Authenticate":
                                        f'Bearer resource_metadata="{metadata}", scope="decision-layer"'},
                                        content={"error": {"code": "UNAUTHENTICATED",
                                                           "message": _("Connect using OAuth, or supply a personal access token.")}})
                await response(scope, receive, send)
                return
            reset = REQUEST_TOKEN.set(token)
            await self.app(scope, receive, send)
        finally:
            if reset is not None:
                REQUEST_TOKEN.reset(reset)
            REQUEST_LOCALE.reset(language)
            reset_locale(context)



def remote_app(settings: Settings, login):
    """(ASGI app for PATH, its lifespan context)."""
    from mcp.server.transport_security import TransportSecuritySettings

    from .server import mcp

    public = urlsplit(settings.login.public_url)
    origin = f"{public.scheme}://{public.netloc}"
    hosts = [pattern for host in settings.http_allowed_hosts for pattern in (host, f"{host}:*")]
    app = mcp.streamable_http_app(
        streamable_http_path=PATH, stateless_http=True, json_response=True,
        transport_security=TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=[origin]))
    return _RequireAccessToken(app, login), app.router.lifespan_context
