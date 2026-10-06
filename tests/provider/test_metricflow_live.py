"""Same governed sample and Method implementations, two real semantic engines."""
import os

import pytest

from decision_layer.methods import registry
from decision_layer.methods.context import ExecutionContext, Scope
from decision_layer.semantic.credentials import AnonymousServiceCredentials, ServiceCredentials
from decision_layer.semantic.providers.cube.client import CubeClient
from decision_layer.semantic.providers.cube.provider import CubeProvider
from decision_layer.semantic.providers.metricflow.provider import MetricFlowProvider

pytestmark = pytest.mark.skipif(not os.environ.get("DL_METRICFLOW_TEST_URL"), reason="Opt-in live provider parity")


@pytest.mark.parametrize("method", ["query.drilldown", "query.trend", "query.peer_comparison", "causal.cem"])
async def test_same_methods_against_cube_and_metricflow(method):
    providers = [
        (CubeProvider(CubeClient(os.environ.get("DL_CUBE_TEST_URL", "http://127.0.0.1:4000/cubejs-api/v1")), "journey"),
         ServiceCredentials(os.environ.get("DL_CUBE_TEST_SECRET", "local-example-secret-change-me-0123456789"), ()),
         {"metric": "transaction/receipts", "rate": "transaction/coupon_line_rate", "department": "product/department", "brand": "product/brand", "store": "transaction/store"}),
        (MetricFlowProvider(os.environ["DL_METRICFLOW_TEST_URL"], "journey"), AnonymousServiceCredentials(),
         {"metric": "metrics/receipts", "rate": "metrics/coupon_line_rate", "department": "dimensions/product__department", "brand": "dimensions/product__brand", "store": "dimensions/transaction__store"}),
    ]
    values = []
    for provider, credentials, names in providers:
        r = {key: f"{provider.name}://journey/{value}" for key, value in names.items()}
        scope = Scope()
        params = {}
        if method == "query.drilldown":
            bindings = {"metric": r["metric"], "dimensions": [r["department"]]}
        elif method == "query.trend":
            bindings = {"metric": r["metric"]}
            scope = Scope(date_range=("2001-01-01", "2001-06-30"))
        elif method == "query.peer_comparison":
            bindings = {"metric": r["rate"]}
            params = {"subject": [{"member": r["store"], "value": "364"}],
                      "peers": [{"member": r["department"], "value": "GROCERY"}]}
        else:
            bindings = {"metric": r["rate"], "treatment": r["brand"], "conditions": [r["department"], r["store"]]}
            params = {"target": ["Private"], "comparison": ["National"]}
        catalog = await provider.discover(credentials)
        result = await registry.run(method, ExecutionContext(provider, credentials, catalog, scope), bindings, params)
        if method == "causal.cem":
            assert catalog.get(r["rate"]).ratio_parts is None
            assert result.status == "refused", result
            assert not result.provenance.queries
            continue
        assert result.status == "success", result
        assert all(p.provider == provider.name for p in result.provenance.queries)
        data = result.primary.data
        if method == "query.drilldown":
            assert data["rows"][0]["value"] == "GROCERY"
            values.append([data["rows"][0]["metric"]])
        elif method == "query.peer_comparison":
            values.append([row["metric"] for row in data["rows"]])
        elif method == "query.trend":
            values.append([row[r["metric"]] for row in data["rows"]])
        else:
            values.append([data["matched"]["difference"]])
    if method != "causal.cem":
        assert values[0] == pytest.approx(values[1], abs=0.0001)


@pytest.mark.parametrize("cube_metric,mf_metric,cube_dimension,mf_dimension,period", [
    ("campaign/count", "campaign_count", "campaign/kind", "campaign__kind", None),
    ("campaign_contact/count", "campaign_contact_count", "campaign/kind", "campaign__kind", None),
    ("redemption/count", "redemption_count", "campaign/kind", "campaign__kind", None),
    ("redemption/count", "redemption_count", "household/age_code", "household__age_code", ("2001-01-01", "2001-06-30")),
])
async def test_campaign_models_have_the_same_counts_and_joins(cube_metric, mf_metric, cube_dimension, mf_dimension, period):
    from decision_layer.core.models import DatasetSpec, TimeScope
    cube = CubeProvider(CubeClient(os.environ.get("DL_CUBE_TEST_URL", "http://127.0.0.1:4000/cubejs-api/v1")), "journey")
    mf = MetricFlowProvider(os.environ["DL_METRICFLOW_TEST_URL"], "journey")
    counts = []
    for provider, credentials, metric, dimension, date_ref in [
        (cube, ServiceCredentials(os.environ.get("DL_CUBE_TEST_SECRET", "local-example-secret-change-me-0123456789"), ()),
         f"cube://journey/{cube_metric}", f"cube://journey/{cube_dimension}", "cube://journey/redemption/analysis_date"),
        (mf, AnonymousServiceCredentials(), f"metricflow://journey/metrics/{mf_metric}",
         f"metricflow://journey/dimensions/{mf_dimension}", "metricflow://journey/dimensions/metric_time"),
    ]:
        spec = DatasetSpec(grain="aggregate", measures=[metric], dimensions=[dimension],
                           time=TimeScope(dimension=date_ref, date_range=period) if period else None)
        dataset = await provider.execute(spec, credentials, with_sql=True)
        counts.append({str(row[0]): row[1] for row in dataset.rows})
    assert counts[0] == counts[1]
