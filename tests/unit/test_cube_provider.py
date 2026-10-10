import pytest

from decision_layer.core.errors import (
    CapabilityMissing, DatasetTooLarge, InvalidDatasetSpec, ProviderError, UnknownSemanticObject,
)
from decision_layer.core.models import DatasetSpec, Filter, TimeScope
from decision_layer.semantic.credentials import RequestCredentials
from decision_layer.semantic.providers.cube import provider as provider_mod
from decision_layer.semantic.providers.cube.catalog_mapper import map_meta
from decision_layer.semantic.providers.cube.compiler import compile_spec
from decision_layer.semantic.providers.cube.provider import CubeProvider
from tests.support.semantic import ref

CREDS = RequestCredentials("t")


def test_catalog_uses_base_refs_and_merges_view_meta(cube_meta):
    cat, views = map_meta(cube_meta, "local")
    rr = cat.get(ref("ecom_order.return_rate"))
    assert rr.kind == "measure" and rr.metric_kind == "other"          # ratio only when declared
    assert rr.metadata["preAggregation"]["timeDimension"] == "order_dt"  # came from the view, camelCase kept
    assert rr.entity == ref("ecom_order.order_id")
    assert cat.get(ref("ecom_order.count")).metric_kind == "count"
    assert cat.get(ref("ecom_order.total_order_amount")).metric_kind == "additive"
    assert cat.get(ref("ecom_order.avg_order_value")).metric_kind == "average"
    assert cat.get(ref("ecom_order.is_free_shipping")).data_type == "boolean"
    assert cat.get(ref("ecom_order.order_dt")).kind == "time_dimension"
    assert cat.get("cube://local/ecommerce_kpi/return_rate") is None     # views never become refs
    assert cat.hierarchies[ref("ecom_order.seller_org")] == [ref("ecom_order.md_team_nm"), ref("ecom_order.seller_id")]
    assert views.views["ecommerce_kpi"]["ecom_order.count"] == "ecommerce_kpi.order_count"  # alias kept


def test_custom_metadata_does_not_define_ratio_semantics(cube_meta):
    for c in cube_meta["cubes"]:
        for m in c["measures"]:
            if m["name"] == "ecom_order.return_rate":
                m["meta"] = {"numerator": "ecom_return.count", "denominator": "count"}
    cat, _ = map_meta(cube_meta, "local")
    rr = cat.get(ref("ecom_order.return_rate"))
    assert rr.metric_kind == "other"
    assert rr.ratio_parts is None
    assert rr.count_measure is None
    assert cat.get(ref("ecom_order.total_order_amount")).count_measure is None
    assert cat.get(ref("ecom_order.count")).count_measure == ref("ecom_order.count")


def test_hierarchies_are_optional(cube_meta):
    for c in cube_meta["cubes"]:
        c.pop("hierarchies", None)
    cat, _ = map_meta(cube_meta, "local")
    assert cat.hierarchies == {} and cat.get(ref("ecom_order.seller_id")) is not None


def test_compile_routes_through_view_and_maps_back(cube_meta):
    cat, views = map_meta(cube_meta, "local")
    spec = DatasetSpec(grain="aggregate", measures=[ref("ecom_order.return_rate"), ref("ecom_order.count")],
                       dimensions=[ref("ecom_product.category_nm")],
                       time=TimeScope(dimension=ref("ecom_order.order_dt"), date_range=("2026-01-01", "2026-09-30")),
                       filters=[Filter(member=ref("ecom_order.is_free_shipping"), operator="equals", values=[True])],
                       order=[(ref("ecom_order.return_rate"), "desc")])
    c = compile_spec(spec, cat, views)
    assert c.view == "ecommerce_kpi"
    assert c.query["measures"] == ["ecommerce_kpi.return_rate", "ecommerce_kpi.order_count"]
    assert c.query["dimensions"] == ["ecommerce_kpi.category_nm"]
    assert c.query["filters"] == [{"member": "ecommerce_kpi.is_free_shipping", "operator": "equals", "values": ["true"]}]
    assert c.query["timeDimensions"] == [{"dimension": "ecommerce_kpi.order_dt", "dateRange": ["2026-01-01", "2026-09-30"]}]
    assert [col.ref for col in c.columns] == [ref("ecom_product.category_nm"), ref("ecom_order.return_rate"), ref("ecom_order.count")]


def test_compile_falls_back_to_base_cubes(cube_meta):
    cat, views = map_meta(cube_meta, "local")
    c = compile_spec(DatasetSpec(grain="aggregate", measures=[ref("ecom_order.count")],
                                 dimensions=[ref("ecom_seller.join_dt")]), cat, views)
    assert c.view is None and c.query["dimensions"] == ["ecom_seller.join_dt"]


from tests.support.cube import FakeClient


async def test_entity_grain_pages_in_order(cube_meta, monkeypatch):
    monkeypatch.setattr(provider_mod, "PAGE_SIZE", 10)
    client = FakeClient(cube_meta, rows_total=25)
    p = CubeProvider(client, "local")
    spec = DatasetSpec(grain="entity", entity=ref("ecom_order.order_id"), measures=[ref("ecom_order.return_rate")],
                       dimensions=[ref("ecom_order.channel")])
    ds = await p.execute(spec, CREDS, with_sql=True)
    assert len(ds.rows) == 25 and ds.provenance[0].pages == 3
    assert [q["offset"] for q in client.loads] == [0, 10, 20]
    # the view doesn't expose order_id, so the query falls back to base cube names
    assert client.loads[0]["order"] == [["ecom_order.order_id", "asc"]]
    assert ds.rows[0][2] == 0.0 and ds.columns[0].role == "entity"       # measures converted to numbers
    assert ds.provenance[0].compiled_sql == "SELECT 1"


async def test_aggregate_overflow_fails_closed(cube_meta, monkeypatch):
    monkeypatch.setattr(provider_mod, "PAGE_SIZE", 10)
    p = CubeProvider(FakeClient(cube_meta, rows_total=50), "local")
    with pytest.raises(DatasetTooLarge):
        await p.execute(DatasetSpec(grain="aggregate", measures=[ref("ecom_order.count")],
                                    dimensions=[ref("ecom_order.seller_id")]), CREDS)


async def test_validation_errors(cube_meta):
    p = CubeProvider(FakeClient(cube_meta), "local")
    with pytest.raises(UnknownSemanticObject):
        await p.validate_dataset(DatasetSpec(grain="aggregate", measures=[ref("ecom_order.nope")]), CREDS)
    with pytest.raises(InvalidDatasetSpec):
        await p.validate_dataset(DatasetSpec(grain="aggregate", measures=[ref("ecom_order.channel")]), CREDS)
    # a delivery measure at order grain is allowed: Cube aggregates it per order before joining
    await p.validate_dataset(DatasetSpec(grain="entity", entity=ref("ecom_order.order_id"),
                                         measures=[ref("ecom_delivery.avg_delivery_days")]), CREDS)


async def test_missing_join_path_is_capability_missing(cube_meta):
    class NoJoin(FakeClient):
        async def load(self, query, token):
            raise ProviderError("Cube 오류: Can't find join path to join 'a', 'b'")

    with pytest.raises(CapabilityMissing):
        await CubeProvider(NoJoin(cube_meta), "local").execute(
            DatasetSpec(grain="aggregate", measures=[ref("ecom_order.count")]), CREDS)


@pytest.mark.parametrize("detail", ["JWT is missing groups", "Authorization header is required",
                                     "Invalid token", "Token has expired"])
def test_auth_failures_are_access_denied_without_traceback(detail):
    import httpx

    from decision_layer.core.errors import ProviderAccessDenied
    from decision_layer.semantic.providers.cube.client import CubeClient

    resp = httpx.Response(500, json={"error": f"Error: Python error: Exception: {detail}\nTraceback (most recent call last):\n  File ..."})
    with pytest.raises(ProviderAccessDenied) as e:
        CubeClient._body(resp, "/meta")
    assert "Traceback" not in e.value.message and detail in e.value.message
    with pytest.raises(ProviderError) as e:
        CubeClient._body(httpx.Response(500, json={"error": "Query failed\nstack"}), "/load")
    assert e.value.message == "Cube error: Query failed"


@pytest.mark.parametrize("message", ["Unexpected token SELECT", "Unknown member token_count"])
def test_query_errors_are_not_auth_errors(message):
    import httpx
    from decision_layer.core.errors import ProviderAccessDenied
    from decision_layer.semantic.providers.cube.client import CubeClient

    with pytest.raises(ProviderError) as exc:
        CubeClient._body(httpx.Response(500, json={"error": message}), "/load")
    assert not isinstance(exc.value, ProviderAccessDenied)


@pytest.mark.parametrize("body", [[], None, "proxy response"])
def test_non_object_response_is_provider_error(body):
    import json
    import httpx
    from decision_layer.semantic.providers.cube.client import CubeClient

    with pytest.raises(ProviderError):
        CubeClient._body(httpx.Response(200, content=json.dumps(body)), "/meta")
