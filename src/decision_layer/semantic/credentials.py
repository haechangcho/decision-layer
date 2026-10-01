"""Who is asking the semantic provider.

- RequestCredentials: the caller's own bearer token, passed through unchanged, so
  Cube applies that caller's access rules (ADR-024).
- ServiceCredentials: local/dev fallback — a short-lived JWT signed with the
  Cube API secret (Cube OSS default checkAuth), carrying configured groups.
- AnonymousServiceCredentials: local/dev fallback for Cube instances running
  without API authentication; it deliberately sends no Authorization header.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import jwt


@dataclass(frozen=True)
class RequestCredentials:
    token: str

    def bearer(self) -> str | None:
        return self.token


@dataclass(frozen=True)
class ServiceCredentials:
    secret: str
    groups: tuple[str, ...]
    subject: str = "decision-layer"
    ttl_seconds: int = 300

    def bearer(self) -> str | None:
        now = int(time.time())
        # both spellings: Cube deployments read either `cube_groups` or `cubeGroups`
        claims = {"sub": self.subject, "cube_groups": list(self.groups), "cubeGroups": list(self.groups),
                  "iat": now, "exp": now + self.ttl_seconds}
        return jwt.encode(claims, self.secret, algorithm="HS256")


@dataclass(frozen=True)
class AnonymousServiceCredentials:
    groups: tuple[str, ...] = ()
    subject: str = "local-development"

    def bearer(self) -> str | None:
        return None
