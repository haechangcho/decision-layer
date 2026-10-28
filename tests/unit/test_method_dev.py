"""Developer sessions use explicitly registered functions and strict query evidence."""

from dataclasses import replace
import pytest

from decision_layer.core.errors import ProviderError
from decision_layer.core.periods import ExecutionPolicy
from decision_layer.dev import MethodSession
from decision_layer.methods import InvalidBinding, Refused, Scope, registry
from tests.support.methods.functions import group_metric
from tests.support.methods.cases import M, GROUP, DATE, FEB, scenarios


async def session_for(policy=None):
    provider = scenarios()[0].provider()
    session = await MethodSession.fixture(provider, policy=policy)
    session.register(group_metric)
    return session, provider


def arguments():
    return dict(metric=M, group=GROUP, limit=3, scope=Scope(FEB, DATE))


async def test_query_and_source_evidence():
    session, provider = await session_for()
    trial = await session.run(group_metric, **arguments())
    assert trial.result.status == "success"
    assert [row["metric"] for row in trial.result.primary.data] == [30, 20, 10]
    assert trial.result.run_id is None and len(trial.queries) == 1
    assert trial.attempts[0].status == "success"
    provider.assert_consumed()


async def test_registration_is_local_and_replacement_explicit():
    session, _ = await session_for()
    with pytest.raises(InvalidBinding):
        registry.get(group_metric.manifest.name)
    with pytest.raises(InvalidBinding, match="already registered"):
        session.register(group_metric)
    session.register(group_metric, replace=True)
    listed = session.list_methods()
    listed[0].description = "Local edit"
    assert session.list_methods()[0].description != "Local edit"


async def test_catalog_copies_and_private_objects():
    session, _ = await session_for()
    session.object(M).title = "Edited copy"
    assert session.object(M).title != "Edited copy"
    session.catalog.get(M).public = False
    from decision_layer.core.errors import UnknownSemanticObject

    with pytest.raises(UnknownSemanticObject):
        session.object(M)


async def test_failure_retains_attempt():
    session, provider = await session_for()
    provider._queries[0] = replace(
        provider._queries[0], error=ProviderError("Unavailable")
    )
    with pytest.raises(ProviderError):
        await session.run(group_metric, **arguments())
    assert session.last_trial.result is None
    assert session.last_trial.attempts[0].status == "failed"


async def test_no_period_or_missing_binding_never_queries():
    session, provider = await session_for()
    with pytest.raises(Refused):
        await session.run(group_metric, **{**arguments(), "scope": Scope()})
    with pytest.raises(InvalidBinding):
        await session.run(group_metric, metric=M, scope=Scope(FEB, DATE))
    assert provider.calls == []


async def test_timeout_retains_interrupted_evidence():
    import asyncio

    session, provider = await session_for(ExecutionPolicy(deadline_seconds=0.01))

    async def slow(*args, **kwargs):
        await asyncio.sleep(1)

    provider.execute = slow
    with pytest.raises(TimeoutError):
        await session.run(group_metric, **arguments())
    assert session.last_trial.attempts[0].error_code == "QUERY_INTERRUPTED"


async def test_row_bound_refuses_without_capability():
    session, provider = await session_for(ExecutionPolicy(max_result_rows=1))
    trial = await session.run(group_metric, **arguments())
    assert trial.result.status == "refused"
    assert not trial.result.provides
    assert provider.calls == [] and trial.attempts == []
