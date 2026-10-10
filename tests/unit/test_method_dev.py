"""Public developer helpers exercise the canonical registry and dataset boundary."""
from dataclasses import replace

import pytest

from decision_layer.core.errors import ProviderError
from decision_layer.core.models import Artifact, MethodManifest, Recipe, PlanStep, SemanticScope
from decision_layer.core.periods import ExecutionPolicy
from decision_layer.dev import MethodSession
from decision_layer.methods import registry as global_registry
from decision_layer.methods import InvalidBinding, Method, MethodOutput
from decision_layer.methods.context import Refused, Scope
from decision_layer.methods.peer_comparison import PeerComparison
from decision_layer.semantic.credentials import AnonymousServiceCredentials
from decision_layer.testing import FixtureProvider, QueryFixture

from examples.methods.peer_comparison import fixtures
from examples.methods.peer_comparison.fixtures import METRIC, DATE, DATES, BINDINGS, PARAMS


async def session_for(provider=None, policy=None):
    provider = provider or fixtures.fixture_provider()
    session = await MethodSession.connect(provider, AnonymousServiceCredentials(), policy=policy)
    session.register(PeerComparison())
    return session, provider


def scope():
    return Scope(date_range=DATES, time_dimension=DATE)


async def test_peer_queries_and_independent_expected_result():
    session, provider = await session_for()
    trial = await session.run("query.peer_comparison", bindings=BINDINGS, params=PARAMS, scope=scope())
    assert trial.result.status == "success"
    assert [row["difference_from_subject"] for row in trial.result.primary.data["rows"]] == [0, 4, 6]
    assert [attempt.status for attempt in trial.attempts] == ["success"] * 3
    assert len(trial.queries) == 3 and trial.result.run_id is None
    assert trial.result.interpretation == "descriptive"
    assert trial.result.primary.data["statistical_judgement"] == "not_tested"
    provider.assert_consumed()


async def test_registry_is_local_and_replacement_explicit():
    original = global_registry.get("query.peer_comparison")
    session, _ = await session_for()
    with pytest.raises(InvalidBinding, match="already registered"):
        session.register(PeerComparison())
    edited = PeerComparison()
    session.register(edited, replace=True)
    assert session.registry.get("query.peer_comparison") is edited
    assert global_registry.get("query.peer_comparison") is original


async def test_catalog_helpers_only_return_visible_objects():
    session, _ = await session_for()
    assert session.metrics()[0].ref == METRIC
    assert DATE in [obj.ref for obj in session.dimensions(METRIC)]
    session.metrics()[0].title = "Modified copy"
    assert session.object(METRIC).title == "Return rate"
    session.catalog.objects[0].public = False
    assert METRIC not in [obj.ref for obj in session.metrics()]
    from decision_layer.core.errors import UnknownSemanticObject
    with pytest.raises(UnknownSemanticObject):
        session.object(METRIC)


async def test_provider_failure_retains_partial_evidence_and_raises():
    provider = fixtures.fixture_provider()
    responses = provider._queries
    responses[1] = replace(responses[1], error=ProviderError("Fixture provider unavailable"))
    session, _ = await session_for(provider)
    with pytest.raises(ProviderError):
        await session.run("query.peer_comparison", bindings=BINDINGS, params=PARAMS, scope=scope())
    assert session.last_trial.result is None
    assert [attempt.status for attempt in session.last_trial.attempts] == ["success", "failed"]
    assert len(session.last_trial.queries) == 1
    assert len(provider.calls) == 2


async def test_wrong_population_filter_is_not_accepted_as_fixture_success():
    session, _ = await session_for()
    params = {**PARAMS, "peers": []}
    with pytest.raises(AssertionError, match="Query #1 differs"):
        await session.run("query.peer_comparison", bindings=BINDINGS, params=params, scope=scope())
    assert session.last_trial.attempts[0].status == "failed"


async def test_scope_and_budget_checks_still_apply():
    session, provider = await session_for(policy=ExecutionPolicy(max_queries=1))
    with pytest.raises(Refused):
        await session.run("query.peer_comparison", bindings=BINDINGS, params=PARAMS, scope=Scope())
    assert provider.calls == []
    trial = await session.run("query.peer_comparison", bindings=BINDINGS, params=PARAMS, scope=scope())
    assert trial.result.status == "refused" and trial.result.provides == []
    assert len(trial.attempts) == 1


async def test_missing_population_refuses_comparison():
    provider = fixtures.fixture_provider()
    provider._queries[1] = replace(provider._queries[1], rows=[])
    session, _ = await session_for(provider)
    trial = await session.run("query.peer_comparison", bindings=BINDINGS, params=PARAMS, scope=scope())
    assert trial.result.status == "refused" and trial.result.provides == []
    provider.assert_consumed()


async def test_unused_queries_and_bad_rows_are_detected():
    provider = fixtures.fixture_provider()
    with pytest.raises(AssertionError, match="Used 0 of 3"):
        provider.assert_consumed()
    first = provider._queries[0]
    bad = FixtureProvider(provider.catalog, [QueryFixture(first.spec, [[12]])])
    session, _ = await session_for(bad)
    with pytest.raises(AssertionError, match="row width"):
        await session.run("query.peer_comparison", bindings=BINDINGS, params=PARAMS, scope=scope())


async def test_output_contract_is_enforced_in_shared_registry():
    class Broken(Method):
        manifest = MethodManifest(name="example.broken", version="1.0.0", kind="query",
                                  description="Invalid output", roles={}, outputs=["table"],
                                  execution="semantic_pushdown", interpretation="descriptive")
        async def run(self, ctx, bindings, params):
            return MethodOutput(primary=Artifact(type="estimate", data={"value": 1}))
    session, _ = await session_for()
    session.register(Broken())
    with pytest.raises(InvalidBinding, match="undeclared artifact"):
        await session.run("example.broken", bindings={}, scope=scope())


async def test_recipe_preview_uses_run_engine_and_local_method():
    session, provider = await session_for()
    recipe = Recipe(name="peer-example", version="1.0.0", mode="pipeline", description="Peer comparison",
                    semantic_scope=SemanticScope(primary_metric=METRIC),
                    steps=[PlanStep(id="compare", method="query.peer_comparison", bindings=BINDINGS, params=PARAMS)])
    run = await session.preview(recipe, step_index=0,
                                scope={"date_range": list(DATES), "time_dimension": DATE})
    assert run.preview and run.status == "completed"
    assert run.steps[0].result.status == "success"
    assert len(run.query_attempts) == 3
    assert run.steps[0].result.run_id == run.id
    provider.assert_consumed()
    session.close()


@pytest.mark.parametrize("bindings,params", [({}, PARAMS), (BINDINGS, {**PARAMS, "min_count": 0})])
async def test_session_invalid_inputs_issue_no_queries(bindings, params):
    session, provider = await session_for()
    with pytest.raises(InvalidBinding):
        await session.run("query.peer_comparison", bindings=bindings, params=params, scope=scope())
    assert provider.calls == [] and session.last_trial.attempts == []


async def test_timeout_retains_failed_query_evidence():
    import asyncio
    session, provider = await session_for(policy=ExecutionPolicy(deadline_seconds=0.01))
    async def slow(*args, **kwargs):
        await asyncio.sleep(1)
    provider.execute = slow
    with pytest.raises(TimeoutError):
        await session.run("query.peer_comparison", bindings=BINDINGS, params=PARAMS, scope=scope())
    assert session.last_trial.result is None
    assert session.last_trial.attempts[0].error_code == "QUERY_INTERRUPTED"


async def test_row_bound_refuses_without_providing_capability():
    provider = fixtures.fixture_provider()
    provider._queries[0] = replace(provider._queries[0], rows=[[12, 100], [12, 100]])
    session, _ = await session_for(provider, ExecutionPolicy(max_result_rows=1))
    trial = await session.run("query.peer_comparison", bindings=BINDINGS, params=PARAMS, scope=scope())
    assert trial.result.status == "refused" and trial.result.provides == []
    assert len(trial.attempts) == 1 and trial.attempts[0].status == "failed"


