"""OpenID Connect authorization-code login with PKCE (ADR-130).

The provider (authentik first) verifies the person. Decision Layer verifies the
returned id_token's signature, issuer, audience, expiry and nonce, then reads the
subject, display name and groups. Access and refresh tokens are not kept.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from urllib.parse import urlencode

import httpx
import jwt

from ..core.errors import DecisionLayerError
from ..i18n import _
from ..settings import LoginSettings

_ASYMMETRIC = ("RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256")
METADATA_SECONDS = 3600


class LoginFailed(DecisionLayerError):
    code = "LOGIN_FAILED"
    http_status = 401


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


class OIDCClient:
    def __init__(self, login: LoginSettings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.login = login
        self.transport = transport
        self._metadata: tuple[float, dict] | None = None
        self._keys: dict[str, jwt.PyJWK] = {}

    def _http(self) -> httpx.AsyncClient:
        # The IdP is operator-configured; redirects are not followed with credentials.
        return httpx.AsyncClient(transport=self.transport, timeout=10, follow_redirects=False)

    async def metadata(self) -> dict:
        if self._metadata and time.monotonic() - self._metadata[0] < METADATA_SECONDS:
            return self._metadata[1]
        url = self.login.issuer.rstrip("/") + "/.well-known/openid-configuration"
        async with self._http() as http:
            response = await http.get(url)
        if response.status_code != 200:
            raise LoginFailed(_("The identity provider's configuration is unavailable"))
        doc = response.json()
        if str(doc.get("issuer", "")).rstrip("/") != self.login.issuer.rstrip("/"):
            raise LoginFailed(_("The identity provider reported a different issuer"))
        for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            if not str(doc.get(key, "")).startswith("https://"):
                raise LoginFailed(_("The identity provider's configuration is incomplete"))
        self._metadata = (time.monotonic(), doc)
        return doc

    async def authorize_url(self, *, state: str, nonce: str, verifier: str) -> str:
        doc = await self.metadata()
        query = urlencode({"response_type": "code", "client_id": self.login.client_id,
                           "redirect_uri": self.login.redirect_uri, "scope": self.login.scopes,
                           "state": state, "nonce": nonce, "code_challenge": challenge(verifier),
                           "code_challenge_method": "S256"})
        return f"{doc['authorization_endpoint']}?{query}"

    async def logout_url(self) -> str | None:
        try:
            endpoint = (await self.metadata()).get("end_session_endpoint")
        except LoginFailed:
            return None
        return endpoint if isinstance(endpoint, str) and endpoint.startswith("https://") else None

    async def exchange(self, *, code: str, verifier: str, nonce: str) -> dict:
        """The verified id_token claims for an authorization code."""
        doc = await self.metadata()
        async with self._http() as http:
            response = await http.post(doc["token_endpoint"], data={
                "grant_type": "authorization_code", "code": code, "redirect_uri": self.login.redirect_uri,
                "code_verifier": verifier}, auth=(self.login.client_id, self.login.client_secret))
        if response.status_code != 200:
            raise LoginFailed(_("The identity provider rejected the login"))
        id_token = response.json().get("id_token")
        if not isinstance(id_token, str):
            raise LoginFailed(_("The identity provider returned no id_token"))
        claims = await self._verify(id_token, doc)
        if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
            raise LoginFailed(_("The login response does not match this browser"))
        return claims

    async def _verify(self, id_token: str, doc: dict) -> dict:
        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.PyJWTError as exc:
            raise LoginFailed(_("The id_token is malformed")) from exc
        alg = header.get("alg")
        if alg in _ASYMMETRIC:
            key = await self._key(header.get("kid"), doc)
        elif alg == "HS256":
            # authentik signs with the client secret when the provider has no signing key.
            key = self.login.client_secret
        else:
            raise LoginFailed(_("The id_token uses an unsupported algorithm"))
        try:
            return jwt.decode(id_token, key, algorithms=[alg], audience=self.login.client_id,
                              issuer=doc["issuer"], leeway=30,
                              options={"require": ["sub", "iss", "aud", "exp", "iat"]})
        except jwt.PyJWTError as exc:
            raise LoginFailed(_("The id_token could not be verified")) from exc

    async def _key(self, kid: str | None, doc: dict) -> jwt.PyJWK:
        if kid not in self._keys:
            async with self._http() as http:
                response = await http.get(doc["jwks_uri"])
            if response.status_code != 200:
                raise LoginFailed(_("The identity provider's signing keys are unavailable"))
            keys = {}
            for item in response.json().get("keys", []):
                try:
                    keys[item.get("kid")] = jwt.PyJWK(item)
                except (jwt.PyJWTError, ValueError, KeyError):
                    continue
            self._keys = keys
        if kid not in self._keys:
            raise LoginFailed(_("The id_token was signed with an unknown key"))
        return self._keys[kid]


def groups(claims: dict, claim: str) -> list[str]:
    value = claims.get(claim)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            value = [value]
    return [str(v) for v in value] if isinstance(value, list) else []
