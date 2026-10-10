"""Sources HTTP routes; analytical work stays in the canonical engine."""
from __future__ import annotations
import hmac
from typing import Annotated
from fastapi import Depends, Header, Request
from ..auth import credentials
from ..i18n import _
from ..core.errors import ProviderAccessDenied, ProviderError
from ..core.models import ProviderCapabilities
from ..semantic.providers.cube.client import CubeConnectionError
from ..sources.config import SourceConfigError, SourceConfigInput
from ..sources.provider import ConfiguredSemanticProvider, make_provider
from ..i18n import _
from fastapi import APIRouter
from .dependencies import Creds, SourceAdminRequired

def create_router(settings, provider, source_manager):
    router = APIRouter()
    @router.get("/sources/current/capabilities", response_model=ProviderCapabilities)
    async def capabilities() -> ProviderCapabilities:
        await source_manager.effective(resolve_secret=False)
        return provider.capabilities()

    @router.get("/execution-policy")
    async def execution_policy() -> dict:
        return {**settings.execution_policy.model_dump(mode="json"), "revision": settings.execution_policy.revision,
                "cost_estimation": "unsupported", "query_cancellation": "not_guaranteed"}


    def require_source_admin(request: Request, admin_key: Annotated[str | None, Header(alias="X-Decision-Layer-Admin-Key")] = None) -> None:
        """Editing the shared connection is gated only where DL_SOURCE_ADMIN_TOKEN is set (a shared
        deployment). Without it this is a single-user/local install and editing is open (ADR-033)."""
        expected = request.app.state.settings.source_admin_token
        if not expected:
            return
        if not admin_key or not hmac.compare_digest(admin_key, expected):
            raise SourceAdminRequired(_("Enter the source administrator key configured by the server."))

    @router.get("/sources/current")
    async def source_current() -> dict:
        return await source_manager.view()

    @router.get("/sources/providers")
    async def source_providers() -> list[dict]:
        entries = []
        for name, title in (("cube", "Cube"), ("dbt", "dbt Semantic Layer")):
            config = await source_manager.effective(resolve_secret=False, provider=name)
            entries.append({"provider": name, "title": title, "api_url": config.api_url,
                            "instance": config.instance, "auth_method": config.auth_method,
                            "environment_id": config.environment_id,
                            "service_groups": list(config.service_groups),
                            "environment_overrides": config.environment_overrides})
        return entries

    @router.put("/sources/current")
    async def source_save(value: SourceConfigInput, _admin: None = Depends(require_source_admin)) -> dict:
        await source_manager.save(value)
        return await source_manager.view()

    @router.post("/sources/current:test")
    async def source_test(value: SourceConfigInput, _admin: None = Depends(require_source_admin),
                          authorization: Annotated[str | None, Header()] = None) -> dict:
        try:
            config = value
            effective = await source_manager.effective(resolve_secret=False, provider=config.provider)
            if config.provider != "cube" and config.auth_method == "api_secret":
                raise SourceConfigError("SOURCE_AUTH_METHOD_INVALID", "API secrets apply only to Cube development connections.")
            environment_id = effective.environment_id if effective.environment_overrides["environment_id"] else config.environment_id
            if config.provider == "dbt" and (not environment_id or config.auth_method != "token"):
                raise SourceConfigError("SOURCE_ENVIRONMENT_REQUIRED", "Enter the dbt environment ID and use access-token authentication.")
            api_url = effective.api_url if effective.environment_overrides["api_url"] else config.api_url
            auth_method = effective.auth_method if effective.environment_overrides["auth_method"] else config.auth_method
            groups = (effective.service_groups if effective.environment_overrides["service_groups"]
                      else tuple(config.service_groups or effective.service_groups))
            if auth_method != "token" and not settings.allow_service_credentials:
                raise SourceConfigError("SOURCE_DEV_AUTH_DISABLED", "Development authentication is disabled on this deployment.", 403)
            secret = None
            if auth_method == "api_secret":
                supplied = config.api_secret.get_secret_value() if config.api_secret else None
                current = await source_manager.effective(provider=config.provider)
                secret = current.api_secret if effective.environment_overrides["api_secret"] else supplied or current.api_secret
                if not secret:
                    raise SourceConfigError("SOURCE_SECRET_REQUIRED", "Enter the Cube API secret to test this connection.", 400)
            creds = credentials(authorization, allow_service=settings.allow_service_credentials,
                                secret=secret, groups=groups, auth_method=auth_method)
            test_provider = (provider if not isinstance(provider, ConfiguredSemanticProvider)
                             else make_provider(config.provider, api_url, config.instance or effective.instance, environment_id))
            catalog = await test_provider.discover(creds)
        except ProviderAccessDenied as exc:
            raise SourceConfigError("SOURCE_AUTH_FAILED", "The semantic provider rejected these credentials. Check its authentication configuration.", 401) from exc
        except CubeConnectionError as exc:
            raise SourceConfigError("SOURCE_UNREACHABLE", "The semantic provider could not be reached. Check the URL, port, network and TLS certificate.", 502) from exc
        except ProviderError as exc:
            raise SourceConfigError("SOURCE_PROVIDER_ERROR", "The semantic provider returned an error. Check its API URL, service logs and model compilation.", 502) from exc
        public = [obj for obj in catalog.objects if obj.public]
        if not public:
            raise SourceConfigError("SOURCE_NO_CUBES", "The provider responded but no semantic objects are visible. Deploy semantic models and grant access.", 422)
        return {"status": "connected", "provider": catalog.provider, "instance": catalog.instance,
                "objects": len(public), "measures": sum(o.kind == "measure" for o in public),
                "dimensions": sum(o.kind == "dimension" for o in public),
                "time_dimensions": sum(o.kind == "time_dimension" for o in public)}

    @router.get("/sources/current/readiness")
    async def source_readiness(creds: Creds) -> dict:
        catalog = await provider.discover(creds)
        public = [obj for obj in catalog.objects if obj.public]
        items = []
        for metric in (obj for obj in public if obj.kind == "measure"):
            entity_ref = metric.entity
            related = [obj for obj in public if obj.ref in metric.dimension_refs or (entity_ref and obj.entity == entity_ref)]
            times = [obj for obj in related if obj.kind == "time_dimension"]
            any_times = any(obj.kind == "time_dimension" for obj in public)
            has_key = bool(entity_ref and any(obj.ref == entity_ref for obj in public))
            ratio_parts = metric.ratio_parts
            ratio_ok = bool(ratio_parts and all(any(obj.ref == ref and obj.kind == "measure" for obj in public)
                                                for ref in ratio_parts))
            checks = {
                "decomposition": {"status": "ready" if ratio_ok else ("missing" if metric.metric_kind == "ratio" else "not_applicable"),
                                  "parts": list(ratio_parts) if ratio_parts else [],
                                  "impact": None if ratio_ok or metric.metric_kind != "ratio" else "This ratio cannot be decomposed into its declared numerator and denominator."},
                "time": {"status": "ready" if times else ("unknown" if any_times else "missing"),
                         "dimensions": [o.ref for o in times],
                         "impact": None if times else ("A related time dimension could not be confirmed from metadata. Select and verify one when running."
                                                       if any_times else "Time-series analysis is unavailable: no time dimension is visible.")},
                "entity_key": {"status": "ready" if has_key else "missing", "ref": entity_ref,
                               "impact": None},
            }
            items.append({"metric": metric.model_dump(mode="json"), "checks": checks})
        return {"provider": catalog.provider, "instance": catalog.instance, "metrics": items,
                "note": "Readiness reflects declarations visible in the semantic catalog; preview queries are still required to confirm joinability and access."}

    return router
