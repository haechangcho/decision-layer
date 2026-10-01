"""Who is calling (ADR-024, ADR-029).

Decision Layer does not verify tokens itself: the semantic provider does. A caller's
identity is the subject of a token **the provider has accepted** (discover()
succeeded with it), so a forged `sub` cannot claim someone else's runs — Cube
rejects a token whose signature it can't verify. The claims are then read
without re-verifying the signature.

Service credentials (no Authorization header) are a local/dev fallback, only
when DL_ALLOW_SERVICE_CREDENTIALS is set; they all share one identity.
"""
from __future__ import annotations

import jwt

from .core.errors import DecisionLayerError, ProviderAccessDenied
from .core.models import CallerInfo
from .semantic.credentials import AnonymousServiceCredentials, RequestCredentials, ServiceCredentials
from .semantic.provider import Credentials, SemanticProvider
from .i18n import _

SUBJECT_CLAIMS = ("sub", "email", "user_id", "userId")
GROUP_CLAIMS = ("cube_groups", "cubeGroups", "groups")


class Unauthenticated(DecisionLayerError):
    code = "UNAUTHENTICATED"
    http_status = 401


def credentials(authorization: str | None, *, allow_service: bool, secret: str | None,
                groups: tuple[str, ...], auth_method: str | None = None) -> RequestCredentials | ServiceCredentials | AnonymousServiceCredentials:
    if auth_method == "none":
        if not allow_service:
            raise Unauthenticated("Unauthenticated Cube access is disabled on this deployment")
        return AnonymousServiceCredentials()
    token = (authorization or "").removeprefix("Bearer ").strip()
    if token:
        return RequestCredentials(token)
    if auth_method != "token" and allow_service and secret:
        return ServiceCredentials(secret, groups)
    raise Unauthenticated(_("An Authorization: Bearer <token> header is required"))


async def identify(provider: SemanticProvider, creds: Credentials) -> CallerInfo:
    """The caller behind creds, after the provider has accepted them."""
    if isinstance(creds, (ServiceCredentials, AnonymousServiceCredentials)):
        return CallerInfo(subject=f"service:{creds.subject}", groups=list(creds.groups))
    await provider.discover(creds)  # raises ProviderAccessDenied for tokens the provider rejects
    try:
        claims = jwt.decode(creds.token, options={"verify_signature": False})
    except jwt.PyJWTError:
        claims = {}
    subject = next((str(claims[c]) for c in SUBJECT_CLAIMS if claims.get(c)), None)
    if not subject:
        raise ProviderAccessDenied(_("The token has no subject (sub), so runs can't be stored or read for it"))
    groups = next((claims[c] for c in GROUP_CLAIMS if claims.get(c)), [])
    return CallerInfo(subject=subject, groups=groups if isinstance(groups, list) else [str(groups)])
