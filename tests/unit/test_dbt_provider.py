"""Official GraphQL contract tests; these do not replace an authenticated live test."""
import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from decision_layer.api.app import create_app
from decision_layer.core.errors import CapabilityMissing, DatasetTooLarge, ProviderAccessDenied, ProviderError, UnknownSemanticObject
from decision_layer.core.models import DatasetSpec, Filter, TimeScope
from decision_layer.semantic.credentials import RequestCredentials
from decision_layer.semantic.providers.dbt.provider import DbtSemanticLayerProvider
from decision_layer.settings import Settings
from decision_layer.sources.config import SourceConfigInput, SourceConfigManager, SourceConfigError
from decision_layer.sources.provider import ConfiguredSemanticProvider
from decision_layer.sources.store import MemorySourceStore

URL = "https://semantic-layer.cloud.getdbt.com/api/graphql"
CREDS = RequestCredentials("dbt-test-token")
METRIC = "dbt://company/metrics/revenue"
REGION = "dbt://company/dimensions/customer__region"
TIME = "dbt://company/dimensions/metric_time"


def catalog(name="revenue", pages=1):
    return {"metricsPaginated": {"totalPages": pages, "items": [{"name": name,
        "type": "SIMPLE", "typeParams": {}, "description": "Governed revenue",
        "queryableGranularities": ["DAY", "MONTH"],
        "dimensions": [{"name": "customer__region", "type": "CATEGORICAL", "description": "Region"}]}]}}


def result(rows, *, pages=1):
    names = list(rows[0]) if rows else ["revenue"]
    return {"query": {"status": "SUCCESSFUL", "totalPages": pages, "sql": "select governed_revenue",
                      "jsonResult": json.dumps({"schema": {"fields": [{"name": n} for n in names]}, "data": rows})}}


def response(data):
    return httpx.Response(200, json={"data": data})


@respx.mock
async def test_catalog_pagination_native_metadata_and_token():
    def serve(request):
        body = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer dbt-test-token"
        assert body["variables"]["environmentId"] == 123
        return response(catalog("revenue" if body["variables"]["pageNum"] == 1 else "margin", pages=2))
    route = respx.post(URL).mock(side_effect=serve)
    provider = DbtSemanticLayerProvider(URL.removesuffix("/api/graphql"), "company", 123)
    data = await provider.discover(CREDS)
    assert route.call_count == 2
    assert data.get(METRIC).description == "Governed revenue"
    assert data.get(METRIC).time_dimension == TIME
    assert data.get(METRIC).count_measure is None
    assert data.get(METRIC).metric_kind == "other"  # SIMPLE does not declare an aggregation.
    assert REGION in data.get(METRIC).dimension_refs


@respx.mock
async def test_query_polling_pagination_filters_time_order_and_provenance():
    calls = []
    def serve(request):
        body = json.loads(request.content)
        calls.append(body)
        if "Catalog(" in body["query"]:
            return response(catalog())
        if "mutation" in body["query"]:
            return response({"createQuery": {"queryId": "query-123"}})
        polls = [c for c in calls if "query Result" in c["query"]]
        if len(polls) == 1:
            return response({"query": {"status": "RUNNING"}})
        page = body["variables"]["pageNum"]
        return response(result([{"CUSTOMER__REGION": "O'Reilly", "METRIC_TIME__MONTH": f"2026-0{page}-01T00:00:00", "REVENUE": page * 100}], pages=2))
    respx.post(URL).mock(side_effect=serve)
    spec = DatasetSpec(grain="aggregate", measures=[METRIC], dimensions=[REGION],
        time=TimeScope(dimension=TIME, date_range=("2026-01-01", "2026-02-28"), granularity="month"),
        filters=[Filter(member=REGION, operator="equals", values=["O'Reilly"])], order=[(TIME, "asc")])
    dataset = await DbtSemanticLayerProvider(URL, "company", 123, poll_interval=0).execute(spec, CREDS, with_sql=True)
    submitted = next(c["variables"] for c in calls if "mutation" in c["query"])
    assert submitted["groupBy"] == [{"name": "customer__region"}, {"name": "metric_time", "grain": "MONTH"}]
    assert submitted["orderBy"] == [{"groupBy": {"name": "metric_time", "grain": "MONTH"}, "descending": False}]
    assert "'2026-03-01'" in submitted["where"][0]["sql"]
    assert "'O''Reilly'" in submitted["where"][1]["sql"]
    assert dataset.rows[1] == ["O'Reilly", "2026-02-01T00:00:00", 200]
    evidence = dataset.provenance[0]
    assert evidence.pages == 2 and evidence.native_query["queryId"] == "query-123"
    assert evidence.compiled_sql == "select governed_revenue"
    assert "dbt-test-token" not in dataset.model_dump_json()


@pytest.mark.parametrize("status,payload,error", [
    (401, {}, ProviderAccessDenied), (403, {}, ProviderAccessDenied),
    (429, {}, ProviderError), (500, {}, ProviderError),
    (200, {"errors": [{"extensions": {"code": "FORBIDDEN"}}]}, ProviderAccessDenied),
    (200, {"data": {}, "errors": [{"message": "sensitive warehouse details"}]}, ProviderError),
])
@respx.mock
async def test_http_and_graphql_errors_fail_closed(status, payload, error):
    respx.post(URL).mock(return_value=httpx.Response(status, json=payload))
    with pytest.raises(error) as exc:
        await DbtSemanticLayerProvider(URL, "company", 123).discover(CREDS)
    assert "sensitive warehouse details" not in str(exc.value)


@pytest.mark.parametrize("state", ["FAILED", "CANCELLED", "UNRECOGNIZED"])
@respx.mock
async def test_query_failure_retains_query_id(state):
    respx.post(URL).mock(side_effect=[response(catalog()), response({"createQuery": {"queryId": "q-failed"}}),
                                      response({"query": {"status": state}})])
    with pytest.raises(ProviderError) as exc:
        await DbtSemanticLayerProvider(URL, "company", 123).execute(DatasetSpec(grain="aggregate", measures=[METRIC]), CREDS)
    assert exc.value.details["query_id"] == "q-failed"


@respx.mock
async def test_timeout_does_not_resubmit_query():
    def serve(request):
        query = json.loads(request.content)["query"]
        return response(catalog() if "Catalog(" in query else {"createQuery": {"queryId": "pending"}} if "mutation" in query else {"query": {"status": "RUNNING"}})
    route = respx.post(URL).mock(side_effect=serve)
    with pytest.raises(ProviderError, match="wait limit"):
        await DbtSemanticLayerProvider(URL, "company", 123, timeout=.02).execute(DatasetSpec(grain="aggregate", measures=[METRIC]), CREDS)
    assert sum("mutation" in json.loads(c.request.content)["query"] for c in route.calls) == 1


@pytest.mark.parametrize("value", ["{{ run_query('select 1') }}", "{% import 'x' %}", "a\\'b", float("inf")])
@respx.mock
async def test_unsupported_filter_values_never_submit_query(value):
    route = respx.post(URL).mock(return_value=response(catalog()))
    from decision_layer.core.errors import InvalidDatasetSpec
    with pytest.raises((CapabilityMissing, InvalidDatasetSpec)):
        await DbtSemanticLayerProvider(URL, "company", 123).execute(DatasetSpec(grain="aggregate", measures=[METRIC],
            filters=[Filter(member=REGION, operator="equals", values=[value])]), CREDS)
    assert route.call_count == 1


@respx.mock
async def test_cross_environment_refs_are_not_resolved():
    respx.post(URL).mock(return_value=response(catalog()))
    with pytest.raises(UnknownSemanticObject):
        await DbtSemanticLayerProvider(URL, "other", 456).resolve([METRIC], CREDS)


@respx.mock
async def test_oversized_results_are_not_silently_truncated(monkeypatch):
    monkeypatch.setattr("decision_layer.semantic.providers.dbt.provider.MAX_ROWS", 1)
    respx.post(URL).mock(side_effect=[response(catalog()), response({"createQuery": {"queryId": "large"}}),
        response(result([{"revenue": 1}, {"revenue": 2}]))])
    with pytest.raises(DatasetTooLarge):
        await DbtSemanticLayerProvider(URL, "company", 123).execute(DatasetSpec(grain="aggregate", measures=[METRIC]), CREDS)


async def test_saved_environment_and_in_flight_provider_are_isolated(monkeypatch):
    manager = SourceConfigManager(MemorySourceStore(), Settings(database_url="memory"))
    await manager.save(SourceConfigInput(provider="dbt", api_url=URL, environment_id=123, instance="company"))
    bound = ConfiguredSemanticProvider(manager)
    bound.bind(await manager.effective())
    await manager.save(SourceConfigInput(provider="dbt", api_url=URL, environment_id=456, instance="company"))
    assert (await bound._provider()).environment_id == 123
    assert (await ConfiguredSemanticProvider(manager)._provider()).environment_id == 456
    monkeypatch.setenv("DBT_ENVIRONMENT_ID", "789")
    assert (await manager.view())["environment_id"] == 789
    with pytest.raises(SourceConfigError):
        await manager.save(SourceConfigInput(provider="dbt", api_url=URL, environment_id=456))


@respx.mock
def test_sources_and_canonical_preview_use_official_api():
    def serve(request):
        body = json.loads(request.content)
        assert body["variables"]["environmentId"] == 123
        assert request.headers["authorization"] == "Bearer dbt-test-token"
        if "Catalog(" in body["query"]:
            return response(catalog())
        if "mutation" in body["query"]:
            return response({"createQuery": {"queryId": "api-query"}})
        return response(result([{"revenue": 100}]))
    respx.post(URL).mock(side_effect=serve)
    with TestClient(create_app(Settings(database_url="memory"))) as client:
        body = {"provider": "dbt", "api_url": URL, "environment_id": 123, "instance": "company", "auth_method": "token"}
        headers = {"Authorization": "Bearer dbt-test-token"}
        assert client.post("/sources/current:test", json=body, headers=headers).json()["measures"] == 1
        assert client.put("/sources/current", json=body).status_code == 200
        assert client.get("/sources/current").json()["environment_id"] == 123
        preview = client.post("/datasets/preview", json={"grain": "aggregate", "measures": [METRIC]}, headers=headers)
        assert preview.status_code == 200, preview.text
        assert preview.json()["rows"] == [[100]]
        assert client.get("/semantic/catalog").status_code == 401


@respx.mock
def test_method_run_and_recipe_preserve_dbt_bindings_and_evidence():
    queries = {}
    def serve(request):
        body = json.loads(request.content)
        if "Catalog(" in body["query"]:
            return response(catalog())
        if "mutation" in body["query"]:
            query_id = f"q-{len(queries)}"
            queries[query_id] = body["variables"]
            return response({"createQuery": {"queryId": query_id}})
        native = queries[body["variables"]["queryId"]]
        rows = ([{"customer__region": "North", "revenue": 100}, {"customer__region": "South", "revenue": 50}]
                if native["groupBy"] else [{"revenue": 150}])
        return response(result(rows))
    respx.post(URL).mock(side_effect=serve)
    with TestClient(create_app(Settings(database_url="memory"))) as client:
        headers = {"Authorization": "Bearer dbt-test-token", "X-Decision-Layer-Client": "mcp"}
        client.put("/sources/current", json={"provider": "dbt", "api_url": URL, "environment_id": 123, "instance": "company"})
        started = client.post("/runs", headers=headers, json={"question": "Which region has the highest revenue?", "scope": {"date_range": ["2026-07-01", "2026-09-30"]}})
        assert started.status_code == 200, started.text
        run_id = started.json()["id"]
        executed = client.post(f"/runs/{run_id}/steps", headers=headers, json={
            "method": "query.drilldown", "purpose": "Find the leading region", "bindings": {"metric": METRIC, "dimensions": [REGION]}})
        assert executed.status_code == 200, executed.text
        data = executed.json()
        assert data["status"] == "success"
        assert data["primary"]["data"]["rows"][0]["value"] == "North"
        run_id = data["run_id"]
        run = client.get(f"/runs/{run_id}", headers=headers).json()
        assert run["plan"]["question"] == "Which region has the highest revenue?"
        assert run["origin"] == "mcp"
        assert run["status"] == "open"
        assert data["provenance"]["queries"][0]["native_query"]["queryId"] == "q-0"
        candidate = client.get(f"/runs/{run_id}/recipe-candidate", headers=headers, params={"indices": 0})
        assert candidate.status_code == 200, candidate.text
        assert candidate.json()["recipe"]["semantic_scope"]["primary_metric"] == METRIC
        assert candidate.json()["recipe"]["steps"][0]["bindings"]["dimensions"] == [REGION]
