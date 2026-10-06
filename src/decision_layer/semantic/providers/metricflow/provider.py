"""HTTP adapter for the Decision Layer MetricFlow gateway (not dbt Cloud's API)."""
from __future__ import annotations

import httpx

from ....core.errors import ProviderAccessDenied, ProviderError, UnknownSemanticObject
from ....core.models import Dataset, DatasetSpec, ProviderCapabilities, SemanticCatalog


def capabilities() -> ProviderCapabilities:
    return ProviderCapabilities(aggregate_queries=True, entity_grain_queries=False, time_dimensions=True,
                                compiled_sql=True, hierarchies=False, max_rows_per_query=50000)


class MetricFlowProvider:
    name = "metricflow"
    identity_mode = "credential"

    def __init__(self, api_url: str, instance: str):
        self.api_url, self.instance = api_url.rstrip("/"), instance

    def capabilities(self):
        return capabilities()

    async def _request(self, method, path, credentials, body=None):
        token = credentials.bearer()
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                response = await client.request(method, self.api_url + path, json=body,
                                                headers={"Authorization": f"Bearer {token}"} if token else {})
        except httpx.RequestError as exc:
            raise ProviderError("The MetricFlow gateway could not be reached. Check its URL and service status.") from exc
        if response.status_code in (401, 403):
            raise ProviderAccessDenied("MetricFlow rejected the access token.")
        if not response.is_success:
            try:
                error = response.json().get("error", {})
            except ValueError:
                error = {}
            exc = ProviderError(error.get("message") or "MetricFlow could not execute this request. Check the gateway logs.")
            if error.get("code"):
                exc.code = error["code"]
            if response.status_code in (400, 404, 422):
                exc.http_status = response.status_code
            raise exc
        return response.json()

    async def discover(self, credentials):
        catalog = SemanticCatalog.model_validate(await self._request("GET", "/catalog", credentials))
        if catalog.provider != self.name or catalog.instance != self.instance:
            raise ProviderError("The gateway provider or instance differs from the connection settings.")
        return catalog

    async def resolve(self, refs, credentials):
        catalog = await self.discover(credentials)
        result = []
        for ref in refs:
            obj = catalog.get(ref)
            if obj is None:
                raise UnknownSemanticObject("This semantic object is not available on the current connection.", ref=ref)
            result.append(obj)
        return result

    async def validate_dataset(self, spec, credentials):
        await self._request("POST", "/datasets/validate", credentials, spec.model_dump(mode="json"))

    async def execute(self, spec: DatasetSpec, credentials, *, with_sql=False):
        return Dataset.model_validate(await self._request("POST", "/datasets/query", credentials,
                                                        {"spec": spec.model_dump(mode="json"), "with_sql": with_sql}))
