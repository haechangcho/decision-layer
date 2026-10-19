"""Deterministic discovery scenarios; these do not measure an LLM's understanding."""
import pytest
from fastapi.testclient import TestClient

from decision_layer.core.models import AnalysisGoal
from decision_layer.core.errors import UnknownSemanticObject
from decision_layer.dev import MethodSession
from decision_layer.methods import Measure, Table, method, register_builtins, MethodRegistry
from decision_layer.methods.context import ExecutionContext
from decision_layer.methods.discovery import MethodSearchRequest, find_methods
from examples.methods.authoring.sample_data import fixture_provider, METRIC, DIMENSION


def goal(capabilities=(), interpretation="association", refs=()):
    return AnalysisGoal(id="answer", description="Compare the requested values",
        required_capabilities=list(capabilities), interpretation=interpretation, semantic_refs=list(refs))


async def test_normal_ambiguous_multiple_and_unsupported_questions():
    session = await MethodSession.fixture(fixture_provider())
    register_builtins(session.registry)
    # Human-resolved intent: "Show this measure". No natural-language parsing is claimed.
    lookup = session.find_methods(goal=goal(refs=[METRIC, DIMENSION]), names=["analysis.metric_lookup"])
    assert [c["manifest"]["name"] for c in lookup["candidates"]] == ["analysis.metric_lookup"]
    assert lookup["candidates"][0]["input_candidates"]["metric"] == [METRIC]
    # "Analyze this": the system cannot infer a purpose from a valid measure.
    ambiguous = session.find_methods(goal=goal(refs=[METRIC]))
    assert len(ambiguous["candidates"]) > 1
    assert ambiguous["semantic_meaning_verified"] is False
    # Several candidates remain valid; no score silently chooses one.
    unfiltered = session.find_methods()
    assert len(unfiltered["candidates"]) > len(lookup["candidates"])
    unsupported = session.find_methods(goal=goal(["future_sales_forecast"]))
    assert unsupported["status"] == "no_available_candidate"
    assert unsupported["unknown_capabilities"] == ["future_sales_forecast"]
    assert not session.provider.calls


async def test_custom_method_needs_no_tags_but_does_not_inherit_capabilities():
    @method("test.lookup", version="1.0.0", interpretation="association")
    async def lookup(ctx, *, value: Measure) -> Table:
        """Return one governed measure; no forecast or effect estimation."""
        return Table([])
    session = await MethodSession.fixture(fixture_provider())
    session.register(lookup)
    found = session.find_methods(goal=goal(refs=[METRIC]))
    assert found["candidates"][0]["manifest"]["description"] == lookup.__doc__
    assert found["candidates"][0]["required_inputs"] == ["value"]
    assert not session.find_methods(goal=goal(["metric_lookup"]))["candidates"]
    assert not session.find_methods(goal=goal(interpretation="causal_conditional"))["candidates"]


async def test_same_private_and_unknown_boundary_as_execution():
    session = await MethodSession.fixture(fixture_provider())
    register_builtins(session.registry)
    session.catalog.get(METRIC).public = False
    with pytest.raises(UnknownSemanticObject):
        session.find_methods(goal=goal(refs=[METRIC]))
    report = session.find_methods()
    assert all(METRIC not in str(candidate["input_candidates"]) for candidate in report["candidates"])
    assert not session.provider.calls


async def test_missing_requirements_are_explained_without_querying(monkeypatch):
    session = await MethodSession.fixture(fixture_provider())
    register_builtins(session.registry)
    caps = session.provider.capabilities().model_copy(update={"entity_grain_queries": False})
    monkeypatch.setattr(session.provider, "capabilities", lambda: caps)
    from decision_layer.methods.advanced import binary_regression
    session.register(binary_regression, replace=True)
    report = session.find_methods(names=["stats.binary_regression"])
    assert not report["candidates"]
    assert "PROVIDER_CAPABILITY_UNAVAILABLE" in [r["code"] for r in report["excluded"][0]["reasons"]]
    assert not session.provider.calls


async def test_conditional_capabilities_are_not_promised_by_default():
    session = await MethodSession.fixture(fixture_provider())
    register_builtins(session.registry)
    from decision_layer.methods.time_analysis import PeriodChange
    session.register(PeriodChange(), replace=True)
    report = session.find_methods(goal=goal(["period_change"]), names=["stats.period_change"])
    candidate = report["candidates"][0]
    assert "comparison" in candidate["required_inputs"]
    assert not candidate["conditional_capabilities"]
    assert not session.find_methods(names=["query.trend"])["candidates"]


def test_rest_and_python_share_results_and_caller_visibility(cube_meta, tmp_path):
    from decision_layer.api.app import create_app
    from decision_layer.settings import Settings
    from tests.support.semantic import FakeProvider, CREDS, AMOUNT
    from decision_layer.methods import registry
    provider = FakeProvider(cube_meta)
    app = create_app(Settings(database_url="sqlite:///:memory:", recipes_dir=tmp_path), provider=provider)
    request = MethodSearchRequest(goal=goal(["metric_lookup"], refs=[AMOUNT]))
    expected = find_methods(registry, ExecutionContext(provider, CREDS, provider.catalog), request)
    import jwt
    token = jwt.encode({"sub": "alice"}, "test-secret-at-least-thirty-two-characters", algorithm="HS256")
    with TestClient(app) as client:
        response = client.post("/methods:search", headers={"Authorization": f"Bearer {token}", "Accept-Language": "en"}, json=request.model_dump(mode="json"))
        assert response.status_code == 200, response.text
        assert response.json() == expected
        denied = client.post("/methods:search", headers={"Authorization": "Bearer bad"}, json={})
        assert denied.status_code in (401, 403)
    assert provider.calls == 0


@pytest.mark.parametrize("provides", ["metric_lookup", [""], ["metric lookup"], ["a", "a"]])
def test_ambiguous_capability_declarations_fail_early(provides):
    with pytest.raises(ValueError, match="provides"):
        @method("test.bad", version="1.0.0", interpretation="association", provides=provides)
        async def bad(ctx) -> Table:
            return Table([])


def test_invalid_dependency_and_ambiguous_optional_type_fail_early():
    with pytest.raises(ValueError):
        @method("test.bad", version="1.0.0", interpretation="association", requires_packages={"pandas": "=>2"})
        async def bad(ctx) -> Table:
            return Table([])
    with pytest.raises(ValueError, match="one non-null"):
        @method("test.bad", version="1.0.0", interpretation="association")
        async def bad_union(ctx, *, value: str | int | None = None) -> Table:
            return Table([])


async def test_executable_developer_flow_preserves_query_and_provenance():
    from tests.support.methods.discovery import demonstrate
    report = await demonstrate()
    assert report["lookup_candidates"] == ["analysis.metric_lookup"]
    assert [row["metric"] for row in report["rows"]] == [30, 20, 10]
    assert report["query_attempts"] == 1
    assert report["method_version"] == "method://example/group_metric@1.0.0"
    from tests.support.methods.cases import M, GROUP, DATE
    assert set(report["semantic_refs"]) == {M, GROUP, DATE}
    from tests.support.methods.functions import group_metric
    assert group_metric.manifest.interpretation == "association"


async def test_private_input_is_also_refused_at_execution_without_queries():
    from examples.methods.authoring.sample_data import DATE, DATES
    from decision_layer.methods import Scope
    from tests.unit.test_method_authoring import grouped
    session = await MethodSession.fixture(fixture_provider())
    session.register(grouped)
    session.catalog.get(METRIC).public = False
    with pytest.raises(UnknownSemanticObject):
        await session.run(grouped, metric=METRIC, group=DIMENSION, scope=Scope(DATES, DATE))
    assert not session.provider.calls


async def test_absent_package_and_missing_description_are_visible():
    @method("test.missing_package", version="1.0.0",
            requires_packages={"decision-layer-nonexistent-test-package": ">=1"})
    async def missing(ctx) -> Table:
        return Table([])
    @method("test.no_description", version="1.0.0")
    async def undocumented(ctx) -> Table:
        return Table([])
    session = await MethodSession.fixture(fixture_provider())
    session.register(missing)
    session.register(undocumented)
    report = session.find_methods()
    assert report["excluded"][0]["reasons"][0]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert report["candidates"][0]["description_available"] is False
    assert not session.provider.calls


async def test_compatibility_methods_are_resolvable_but_not_new_candidates():
    session = await MethodSession.fixture(fixture_provider())
    register_builtins(session.registry)
    retired = {"stats.adjusted_difference", "stats.dml", "stats.did"}
    assert len([m for m in session.registry.manifests() if m.implementation == "python"]) == 2
    assert len([m for m in session.registry.manifests(include_compatibility=True) if m.implementation == "python"]) == 18
    assert retired.isdisjoint(m.name for m in session.registry.manifests())
    for name in retired:
        legacy = session.registry.get(name)
        assert legacy.manifest.version == "1.0.0"
        assert "design" in legacy.manifest.parameters
    assert not session.find_methods(names=list(retired))["candidates"]
    assert not session.provider.calls


async def test_cem_is_compatibility_only():
    session = await MethodSession.fixture(fixture_provider())
    register_builtins(session.registry)
    assert "causal.cem" not in {m.name for m in session.registry.manifests() if m.implementation == "python"}
    assert session.registry.get("causal.cem").manifest.version == "1.1.1"
    assert session.find_methods(names=["causal.cem"])["candidates"] == []


async def test_optional_method_can_be_enabled_with_existing_registration():
    from decision_layer.methods.peer_comparison import PeerComparison
    session = await MethodSession.fixture(fixture_provider())
    register_builtins(session.registry)
    assert {m.name for m in session.registry.manifests() if m.implementation == "python"} == {
        "stats.regression_adjustment", "stats.binary_matching",
    }
    assert session.find_methods(names=["query.peer_comparison"])["candidates"] == []
    # replace=True acknowledges an existing compatibility registration locally.
    session.register(PeerComparison(), replace=True)
    assert session.find_methods(names=["query.peer_comparison"])["candidates"]
    assert len([m for m in session.registry.manifests() if m.implementation == "python"]) == 3
    assert not session.provider.calls
