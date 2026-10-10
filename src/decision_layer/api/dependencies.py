"""Authentication and shared HTTP response helpers."""
from __future__ import annotations
from typing import Annotated, Literal
from fastapi import Depends, Header, Request
from fastapi.responses import JSONResponse
from ..auth import credentials, identify
from ..i18n import _
from ..core.errors import DecisionLayerError
from ..core.models import CallerInfo, MethodManifest, Run
from ..semantic.credentials import AnonymousServiceCredentials, RequestCredentials, ServiceCredentials
from ..sources.config import EffectiveSource
from ..sources.provider import ConfiguredSemanticProvider
from ..settings import Settings
from ..i18n import _

PREVIEW_ROWS = 1000
MAX_WAIT_SECONDS = 300


def run_origin(request: Request) -> Literal["api", "web", "mcp"]:
    hint = request.headers.get("X-Decision-Layer-Client")
    return hint if hint in ("web", "mcp") else "api"


class JobFailed(DecisionLayerError):
    """The run's last background job raised; code/message are the recorded ones."""
    http_status = 422

    def __init__(self, error: dict) -> None:
        super().__init__(error.get("message", ""))
        self.code = error.get("code", "JOB_FAILED")


class NoResult(DecisionLayerError):
    code = "NO_RESULT"
    http_status = 404


class SourceAdminRequired(DecisionLayerError):
    code = "SOURCE_ADMIN_REQUIRED"
    http_status = 403


async def get_credentials(request: Request, authorization: Annotated[str | None, Header()] = None):
    """The caller's bearer token is passed through to the provider (ADR-024); service credentials
    are a local/dev fallback that must be switched on explicitly (ADR-029)."""
    settings: Settings = request.app.state.settings
    source: EffectiveSource = await request.app.state.source_manager.effective(resolve_secret=False)
    if source.auth_method == "api_secret" and not authorization:
        source = await request.app.state.source_manager.effective()
    if isinstance(request.app.state.provider, ConfiguredSemanticProvider):
        request.app.state.provider.bind(source)
    return credentials(authorization, allow_service=settings.allow_service_credentials,
                       secret=source.api_secret, groups=source.service_groups, auth_method=source.auth_method)


Creds = Annotated[RequestCredentials | ServiceCredentials | AnonymousServiceCredentials, Depends(get_credentials)]


async def get_caller(request: Request, creds: Creds) -> CallerInfo:
    return await identify(request.app.state.provider, creds)


Caller = Annotated[CallerInfo, Depends(get_caller)]


def localized(m: MethodManifest) -> MethodManifest:
    """Manifest texts are English in code; serve them in the request's language."""
    return m.model_copy(update={
        "description": _(m.description),
        "label": _(m.label),
        "roles": {k: r.model_copy(update={"description": _(r.description), "label": _(r.label)}) for k, r in m.roles.items()},
        "parameters": {k: p.model_copy(update={"description": _(p.description), "label": _(p.label)}) for k, p in m.parameters.items()},
    })


def waited(settings: Settings, wait: float | None) -> float:
    return max(0.0, min(settings.request_wait_seconds if wait is None else wait, MAX_WAIT_SECONDS))

def accepted(run: Run) -> JSONResponse:
    return JSONResponse(status_code=202, content={
        "run_id": run.id, "status": "running", "running": run.running.model_dump(mode="json") if run.running else None,
        "poll": f"/runs/{run.id}/result"})
