"""Legacy adapter regression tests (not a supported product connector); these do not replace an authenticated live test."""
import json

import httpx
import pytest
import respx

from decision_layer.core.errors import CapabilityMissing, DatasetTooLarge, ProviderAccessDenied, ProviderError, UnknownSemanticObject
from decision_layer.core.models import DatasetSpec, Filter, TimeScope
from decision_layer.semantic.credentials import RequestCredentials
from decision_layer.semantic.providers.dbt.provider import DbtSemanticLayerProvider

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


@pytest.mark.parametrize("intermediate", ["RUNNING", "COMPILED"])
@respx.mock
async def test_query_polling_pagination_filters_time_order_and_provenance(intermediate):
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
            return response({"query": {"status": intermediate}})
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
    assert sum("mutation" in call["query"] for call in calls) == 1
    assert all(call["variables"]["queryId"] == "query-123" for call in calls if "query Result" in call["query"])


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


@pytest.mark.parametrize("state", ["RUNNING", "COMPILED"])
@respx.mock
async def test_timeout_does_not_resubmit_query(state):
    def serve(request):
        query = json.loads(request.content)["query"]
        return response(catalog() if "Catalog(" in query else {"createQuery": {"queryId": "pending"}} if "mutation" in query else {"query": {"status": state}})
    route = respx.post(URL).mock(side_effect=serve)
    with pytest.raises(ProviderError, match="wait limit"):
        await DbtSemanticLayerProvider(URL, "company", 123, timeout=.02).execute(DatasetSpec(grain="aggregate", measures=[METRIC]), CREDS)
    assert sum("mutation" in json.loads(c.request.content)["query"] for c in route.calls) == 1


@pytest.mark.parametrize("state", [None, "secret-token-with-sensitive-data", {"token": "secret"}])
@respx.mock
async def test_invalid_query_status_is_redacted(state, caplog):
    respx.post(URL).mock(side_effect=[response(catalog()), response({"createQuery": {"queryId": "q-invalid"}}),
                                      response({"query": {"status": state}})])
    with pytest.raises(ProviderError) as exc:
        await DbtSemanticLayerProvider(URL, "company", 123).execute(DatasetSpec(grain="aggregate", measures=[METRIC]), CREDS)
    assert exc.value.details["query_status"] == "INVALID_RESPONSE"
    assert "secret" not in str(exc.value) + caplog.text


@pytest.mark.parametrize("value", ["{{ run_query('select 1') }}", "{% import 'x' %}", "a\\'b", float("inf")])
@respx.mock
async def test_unsupported_filter_values_never_submit_query(value):
    route = respx.post(URL).mock(return_value=response(catalog()))
    from decision_layer.core.errors import InvalidDatasetSpec
    from pydantic import ValidationError
    with pytest.raises((CapabilityMissing, InvalidDatasetSpec, ValidationError)):
        await DbtSemanticLayerProvider(URL, "company", 123).execute(DatasetSpec(grain="aggregate", measures=[METRIC],
            filters=[Filter(member=REGION, operator="equals", values=[value])]), CREDS)
    assert route.call_count == (0 if value == float("inf") else 1)


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
