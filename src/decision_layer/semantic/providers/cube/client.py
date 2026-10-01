"""Thin async client for the Cube REST API (/meta, /load, /sql) — standard Cube OSS endpoints only."""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any

import httpx

from ....core.errors import ProviderAccessDenied, ProviderError
from ....i18n import _

_CONTINUE_WAIT = "Continue wait"
# Cube reports failures raised in checkAuth (bad/expired token, missing claims) as a generic error
# when the auth hook itself throws; recognise them so callers get 403, not 502.
_AUTH_ERROR = re.compile(r"check_?auth|\bjwt\b|unauthori[sz]ed|authorization|forbidden|access denied|"
                         r"\b(?:invalid|expired|missing) (?:access |bearer )?token\b|"
                         r"\btoken (?:(?:is|has) )?(?:invalid|expired|missing)\b", re.IGNORECASE)


class CubeConnectionError(ProviderError):
    """The transport failed before Cube returned an HTTP response."""


class CubeClient:
    def __init__(self, base_url: str, timeout: float = 60.0, wait_seconds: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.wait_seconds = wait_seconds

    async def meta(self, token: str | None) -> dict[str, Any]:
        return await self._get("/meta", token)

    async def load(self, query: dict[str, Any], token: str | None) -> dict[str, Any]:
        return await self._post("/load", {"query": query}, token)

    async def sql(self, query: dict[str, Any], token: str | None) -> dict[str, Any]:
        return await self._post("/sql", {"query": query}, token)

    # ── transport ─────────────────────────────────────────────────────────
    def _headers(self, token: str | None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _get(self, path: str, token: str | None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(self.base_url + path, headers=self._headers(token))
            except httpx.RequestError as e:
                raise CubeConnectionError(_("Cube connection error: {error}", error=e)) from e
        return self._body(resp, path)

    async def _post(self, path: str, payload: dict[str, Any], token: str | None) -> dict[str, Any]:
        deadline = time.monotonic() + self.wait_seconds
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while True:
                try:
                    resp = await client.post(self.base_url + path, json=payload, headers=self._headers(token))
                except httpx.RequestError as e:
                    raise CubeConnectionError(_("Cube connection error: {error}", error=e)) from e
                body = self._body(resp, path)
                if body.get("error") != _CONTINUE_WAIT:   # pre-aggregation still building → poll
                    return body
                if time.monotonic() > deadline:
                    raise ProviderError(_("The Cube query did not finish in time"), path=path)
                await asyncio.sleep(1)

    @staticmethod
    def _body(resp: httpx.Response, path: str) -> dict[str, Any]:
        try:
            body = resp.json() if resp.content else {}
        except ValueError:
            body = {"error": resp.text[:500]}
        if not isinstance(body, dict):
            raise ProviderError("Cube returned an invalid response. Check the Cube API URL.", path=path)
        error = body.get("error")
        if resp.status_code < 400 and (error is None or error == _CONTINUE_WAIT):
            return body
        # first line only: provider stack traces are not for API callers
        detail = str(error or resp.status_code).strip().splitlines()[0][:300]
        if resp.status_code in (401, 403) or _AUTH_ERROR.search(str(error or "")):
            raise ProviderAccessDenied(_("Cube access error: {detail}", detail=detail), path=path)
        raise ProviderError(_("Cube error: {detail}", detail=detail), path=path)
