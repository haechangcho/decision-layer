"""Streamable HTTP MCP for shared deployments (ADR-130).

The same tools as the stdio adapter, mounted at /mcp beside the API. Each request
must carry a personal access token; it is forwarded unchanged to the REST API,
which verifies it like any other caller. There is no MCP-only execution path.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ..settings import Settings
from ..login.tokens import PREFIX

PATH = "/mcp"


class _RequireAccessToken:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        from .server import REQUEST_TOKEN

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        token = headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not token.startswith(PREFIX):
            response = JSONResponse(status_code=401, headers={"WWW-Authenticate": 'Bearer realm="decision-layer"'},
                                    content={"error": {"code": "UNAUTHENTICATED",
                                                       "message": "Create an access token at /auth/tokens."}})
            await response(scope, receive, send)
            return
        reset = REQUEST_TOKEN.set(token)
        try:
            await self.app(scope, receive, send)
        finally:
            REQUEST_TOKEN.reset(reset)


def remote_app(settings: Settings):
    """(ASGI app for PATH, its lifespan context)."""
    from mcp.server.transport_security import TransportSecuritySettings

    from .server import mcp

    public = urlsplit(settings.login.public_url)
    origin = f"{public.scheme}://{public.netloc}"
    hosts = [pattern for host in settings.http_allowed_hosts for pattern in (host, f"{host}:*")]
    app = mcp.streamable_http_app(
        streamable_http_path=PATH, stateless_http=True, json_response=True,
        transport_security=TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=[origin]))
    return _RequireAccessToken(app), app.router.lifespan_context
