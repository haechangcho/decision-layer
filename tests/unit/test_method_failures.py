"""Required input, data and budget failures stop governed execution."""

import pytest
from dataclasses import replace
from decision_layer.core.errors import ProviderError
from decision_layer.core.periods import ExecutionPolicy
from decision_layer.dev import MethodSession
from decision_layer.methods import InvalidBinding, Refused, Scope, register_builtins
from decision_layer.methods.dependencies import dependency_issue
from tests.support.methods.functions import AUTHORED
from tests.support.methods.cases import GROUP, M, scenarios

FAILURES = (
    "wrong-kind",
    "wrong-query",
    "no-period",
    "query-budget",
    "provider-failure",
    "row-overflow",
    "non-primary-unit",
    "missing-data",
    "duplicate-unit",
    "missing-cohort",
    "unsupported-option",
    "duplicate-panel",
    "overlapping-windows",
)


async def failure(name):
    parent = {
        "query-budget": "peer",
        "provider-failure": "peer",
        "non-primary-unit": "ols",
        "missing-data": "ols",
        "duplicate-unit": "ols",
        "missing-cohort": "unit-change",
        "unsupported-option": "did",
        "duplicate-panel": "did",
        "overlapping-windows": "did",
    }.get(name, "by_group")
    scenario = next(item for item in scenarios() if item.name == parent)
    policy = (
        ExecutionPolicy(max_queries=1)
        if name == "query-budget"
        else ExecutionPolicy(max_result_rows=3)
        if name == "row-overflow"
        else ExecutionPolicy()
    )
    arguments = scenario.arguments
    expected_error, queries = None, 1
    if name == "wrong-kind":
        arguments["measures"] = {"group": M}
        expected_error, queries = InvalidBinding, 0
    elif name == "wrong-query":
        arguments["params"]["limit"] = 2
        expected_error = AssertionError
    elif name == "no-period":
        arguments["scope"] = Scope()
        expected_error, queries = Refused, 0
    elif name == "provider-failure":
        scenario.queries[1] = replace(
            scenario.queries[1], error=ProviderError("Fixture provider unavailable")
        )
        expected_error, queries = ProviderError, 2
    elif name == "row-overflow":
        scenario.queries[0] = replace(
            scenario.queries[0], rows=[*scenario.queries[0].rows, [5, "D"]]
        )
    elif name == "non-primary-unit":
        arguments["entity"] = GROUP
        expected_error, queries = InvalidBinding, 0
    elif name in ("missing-data", "duplicate-unit"):
        query = scenario.queries[0]
        rows = [list(row) for row in query.rows]
        if name == "missing-data":
            rows[0][0] = None
        else:
            rows[1][-1] = rows[0][-1]
        scenario.queries[0] = replace(query, rows=rows)
    elif name == "missing-cohort":
        scenario.queries[1] = replace(
            scenario.queries[1], rows=scenario.queries[1].rows[:1]
        )
        queries = 2
    elif name == "unsupported-option":
        arguments.setdefault("params", {})["causal_claim"] = True
        expected_error, queries = InvalidBinding, 0
    elif name == "duplicate-panel":
        query = scenario.queries[0]
        scenario.queries[0] = replace(query, rows=[*query.rows, query.rows[0]])
    elif name == "overlapping-windows":
        from tests.support.methods.cases import FEB

        arguments.setdefault("params", {})["windows"] = [FEB, FEB]
        queries = 0
    provider = scenario.provider()
    session = await MethodSession.fixture(provider, policy=policy)
    register_builtins(session.registry)
    for implementation in AUTHORED:
        session.register(implementation)
    if issue := dependency_issue(
        session.registry.get(scenario.method).manifest.requires_packages
    ):
        pytest.skip(issue)
    try:
        trial = await session.run(scenario.method, **arguments)
    except (InvalidBinding, ProviderError, Refused, AssertionError) as exc:
        if not expected_error or not isinstance(exc, expected_error):
            raise
        outcome, message = type(exc).__name__, str(exc)
    else:
        if expected_error or trial.result.status != "refused":
            raise AssertionError("Expected a refusal or the documented exception")
        outcome, message = "refused", trial.result.warnings
    trial = session.last_trial
    attempts = trial.attempts if trial else []
    assert len(provider.calls) == queries
    return {
        "case": name,
        "verified": True,
        "outcome": outcome,
        "queries": len(provider.calls),
        "attempts": [item.status for item in attempts],
        "message": message,
    }


@pytest.mark.parametrize("name", FAILURES)
async def test_contract_refusals(name):
    report = await failure(name)
    assert report["verified"]
