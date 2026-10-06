import pytest
import httpx
import respx

from decision_layer.core.errors import InvalidDatasetSpec, ProviderAccessDenied, ProviderError
from decision_layer.semantic.credentials import RequestCredentials
from decision_layer.semantic.providers.metricflow.gateway import _literal
from decision_layer.semantic.providers.metricflow.provider import MetricFlowProvider
from decision_layer.sources.config import SourceConfigInput, SourceConfigManager, SourceConfigError
from decision_layer.sources.store import MemorySourceStore
from decision_layer.settings import Settings
from decision_layer.sources.provider import ConfiguredSemanticProvider


async def test_switch_preserves_each_provider_and_isolates_cube_secret(monkeypatch):
    monkeypatch.setenv("CUBE_API_SECRET", "cube-secret-only")
    manager = SourceConfigManager(MemorySourceStore(), Settings(allow_service_credentials=True))
    await manager.save(SourceConfigInput(provider="cube", api_url="http://cube/cubejs-api/v1", auth_method="api_secret"))
    await manager.save(SourceConfigInput(provider="metricflow", instance="warehouse", api_url="http://mf", auth_method="none"))
    current = await manager.effective()
    assert current.provider == "metricflow" and current.instance == "warehouse"
    assert current.api_secret is None and current.auth_method == "none"
    cube = await manager.effective(provider="cube")
    assert cube.api_url == "http://cube/cubejs-api/v1" and cube.api_secret == "cube-secret-only"
    with pytest.raises(SourceConfigError):
        await manager.save(SourceConfigInput(provider="metricflow", api_url="http://mf", auth_method="api_secret"))


async def test_inflight_request_keeps_its_original_provider():
    manager = SourceConfigManager(MemorySourceStore(), Settings(allow_service_credentials=True))
    await manager.save(SourceConfigInput(provider="cube", api_url="http://cube", auth_method="none"))
    provider = ConfiguredSemanticProvider(manager)
    provider.bind(await manager.effective())
    original = await provider._provider()
    await manager.save(SourceConfigInput(provider="metricflow", api_url="http://mf", auth_method="none"))
    assert await provider._provider() is original
    assert provider.name == "cube"
    assert (await ConfiguredSemanticProvider(manager)._provider()).name == "metricflow"


@respx.mock
async def test_remote_catalog_is_scoped_and_bearer_is_passed_through():
    route = respx.get("http://mf/catalog").mock(return_value=httpx.Response(200, json={
        "provider": "metricflow", "instance": "prod", "objects": []}))
    provider = MetricFlowProvider("http://mf", "prod")
    await provider.discover(RequestCredentials("opaque-token"))
    assert route.calls.last.request.headers["authorization"] == "Bearer opaque-token"
    with pytest.raises(ProviderError):
        await MetricFlowProvider("http://mf", "other").discover(RequestCredentials("opaque-token"))
    route.mock(return_value=httpx.Response(401))
    with pytest.raises(ProviderAccessDenied):
        await provider.discover(RequestCredentials("bad"))


def test_filter_values_cannot_inject_sql_or_jinja():
    assert _literal("O'Reilly") == "E'O''Reilly'"
    assert _literal("a\\b") == "E'a\\\\b'"
    for value in ("{{ run_query('select 1') }}", "{% import 'x' %}", "{# comment", float("nan")):
        with pytest.raises(InvalidDatasetSpec):
            _literal(value)


async def test_example_provider_default_does_not_override_saved_selection(monkeypatch):
    monkeypatch.setenv("DL_DEFAULT_SOURCE_PROVIDER", "metricflow")
    monkeypatch.setenv("METRICFLOW_AUTH_METHOD", "none")
    manager = SourceConfigManager(MemorySourceStore(), Settings(allow_service_credentials=True))
    assert (await manager.effective()).provider == "metricflow"
    await manager.save(SourceConfigInput(provider="cube", api_url="http://cube", auth_method="none"))
    assert (await manager.effective()).provider == "cube"


@pytest.mark.parametrize("kind,aggregation,hints,expected_kind,expected_count", [
    ("simple", "count", {}, "count", "lines"),
    ("simple", "count_distinct", {}, "count", None),
    ("simple", "sum", {}, "additive", None),
    ("ratio", "sum", {}, "ratio", "lines"),
    ("derived", "sum", {"numerator": "coupons", "denominator": "lines"}, "other", None),
    ("simple", "sum", {"count_measure": "lines", "metric_kind": "count"}, "additive", None),
])
def test_catalog_uses_native_semantics_without_guessing_samples(kind, aggregation, hints, expected_kind, expected_count):
    from types import SimpleNamespace as NS
    from decision_layer.semantic.providers.metricflow.gateway import MetricFlowRuntime
    definition = NS(name="lines", type=NS(value=kind),
                    type_params=NS(measure=NS(name="value") if kind == "simple" else None,
                                   numerator=NS(name="coupons"), denominator=NS(name="lines")),
                    dict=lambda: {"config": {"meta": {"decision_layer": hints}}})
    runtime = MetricFlowRuntime.__new__(MetricFlowRuntime)
    runtime.instance = "generic"
    runtime.config = NS(semantic_manifest=NS(metrics=[definition], semantic_models=[NS(
        measures=[NS(name="value", agg=NS(value=aggregation))], dimensions=[])]))
    runtime.engine = NS(list_metrics=lambda: [NS(name="lines", dimensions=[])])
    metric = runtime._catalog().objects[0]
    assert metric.metric_kind == expected_kind
    assert metric.count_measure == (f"metricflow://generic/metrics/{expected_count}" if expected_count else None)
