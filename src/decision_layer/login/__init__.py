"""Application login for shared deployments (ADR-130).

Every Web, REST and MCP request in shared mode resolves to one verified person —
from the browser session cookie or a personal access token — before any Cube query.
Provider tokens sent by callers are not accepted: Decision Layer signs each Cube
token itself so Cube access policies still decide what the person can see.
"""
from __future__ import annotations

from fastapi import Request

from ..auth import Unauthenticated
from ..i18n import _
from ..semantic.credentials import LoginCredentials
from ..settings import Settings
from .oidc import OIDCClient
from .sessions import SESSION_COOKIE, Person, read_session
from .tokens import PREFIX, AccessTokenStore, open_token_store


class LoginRequired(Unauthenticated):
    code = "LOGIN_REQUIRED"


class Login:
    def __init__(self, settings: Settings, tokens: AccessTokenStore | None = None,
                 oidc: OIDCClient | None = None) -> None:
        self.settings = settings
        self.config = settings.login
        self.tokens = tokens or open_token_store(settings.database_url)
        self.oidc = oidc or OIDCClient(self.config)

    def role(self, idp_groups: list[str]) -> str | None:
        if set(idp_groups) & set(self.config.admin_groups):
            return "admin"
        if set(idp_groups) & set(self.config.user_groups):
            return "user"
        return None

    def credentials_for(self, person: Person) -> LoginCredentials:
        cube_groups = self.config.cube_admin_groups if person.role == "admin" else self.config.cube_user_groups
        return LoginCredentials(secret=self.config.cube_token_secret, groups=tuple(cube_groups),
                                subject=person.subject, role=person.role, name=person.name)

    def session_person(self, request: Request) -> Person | None:
        return read_session(self.config.session_secret, request.cookies.get(SESSION_COOKIE))

    async def person(self, request: Request) -> Person:
        cached = getattr(request.state, "dl_person", None)
        if cached is not None:
            return cached
        person = await self._person(request)
        request.state.dl_person = person
        return person

    async def _person(self, request: Request) -> Person:
        authorization = request.headers.get("authorization", "")
        if authorization:
            token = authorization.removeprefix("Bearer ").strip()
            if not token.startswith(PREFIX):
                raise Unauthenticated(_("This deployment accepts only Decision Layer access tokens"))
            record = await self.tokens.verify(token, resource=self.config.public_url + "/mcp")
            if record is None:
                raise Unauthenticated(_("The access token is invalid, expired or revoked"))
            return record.person()
        person = self.session_person(request)
        if person is None:
            raise LoginRequired(_("Sign in to continue"), login_url="/auth/login")
        return person

    async def credentials(self, request: Request) -> LoginCredentials:
        return self.credentials_for(await self.person(request))


PUBLIC_PATHS = ("/health",)


async def require_login(request: Request) -> None:
    """Every shared-mode API route needs a signed-in person, catalog reads included."""
    path = getattr(request.scope.get("route"), "path", "")
    if path in PUBLIC_PATHS or path.startswith("/auth/"):
        return
    await request.app.state.login.person(request)
