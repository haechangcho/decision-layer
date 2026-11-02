"""Signed browser cookies for the login flow and the signed-in session (ADR-130).

Both are HS256 JWTs under DL_SESSION_SECRET with distinct audiences, so a flow
cookie can never be replayed as a session. Sessions are stateless: logout clears
the cookie, and a copied cookie stays valid until it expires (DL_SESSION_HOURS).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

import jwt

SESSION_COOKIE = "dl_session"
FLOW_COOKIE = "dl_login"
_SESSION_AUDIENCE = "decision-layer:session"
_FLOW_AUDIENCE = "decision-layer:login-flow"
FLOW_SECONDS = 600


@dataclass(frozen=True)
class Person:
    """A person the OIDC provider verified, with the role their groups grant."""
    subject: str
    role: Literal["admin", "user"]
    name: str | None = None


def sign_session(secret: str, person: Person, hours: float) -> str:
    now = int(time.time())
    return jwt.encode({"sub": person.subject, "role": person.role, "name": person.name,
                       "aud": _SESSION_AUDIENCE, "iat": now, "exp": now + int(hours * 3600)},
                      secret, algorithm="HS256")


def read_session(secret: str, cookie: str | None) -> Person | None:
    if not cookie:
        return None
    try:
        claims = jwt.decode(cookie, secret, algorithms=["HS256"], audience=_SESSION_AUDIENCE,
                            options={"require": ["sub", "exp", "aud"]})
    except jwt.PyJWTError:
        return None
    if claims.get("role") not in ("admin", "user"):
        return None
    return Person(subject=claims["sub"], role=claims["role"], name=claims.get("name"))


def sign_flow(secret: str, *, state: str, nonce: str, verifier: str, next_path: str) -> str:
    now = int(time.time())
    return jwt.encode({"state": state, "nonce": nonce, "verifier": verifier, "next": next_path,
                       "aud": _FLOW_AUDIENCE, "iat": now, "exp": now + FLOW_SECONDS},
                      secret, algorithm="HS256")


def read_flow(secret: str, cookie: str | None) -> dict | None:
    if not cookie:
        return None
    try:
        return jwt.decode(cookie, secret, algorithms=["HS256"], audience=_FLOW_AUDIENCE,
                          options={"require": ["state", "nonce", "verifier", "exp", "aud"]})
    except jwt.PyJWTError:
        return None


def safe_next(value: str | None) -> str:
    """Only same-origin paths; never an absolute or protocol-relative URL."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/ui/"
    return value
