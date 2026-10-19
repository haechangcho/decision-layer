"""Registration and worker checks retain their execution order and failure semantics."""

import pytest

from decision_layer.dev import MethodSession
from decision_layer.methods import DataInput, Scope, python_method
from decision_layer.testing import FixtureProvider
from examples.methods.first_method.fixtures import DATE, DATES, METRIC, fixture_provider


@pytest.mark.parametrize("failure", ["false", "value_error", "assertion"])
async def test_option_failure_stops_before_query_and_later_checks(failure):
    calls = []

    def first(enabled):
        calls.append("first")
        if failure == "value_error":
            raise ValueError("Invalid option")
        if failure == "assertion":
            raise AssertionError("Invalid option")
        return False

    def later(enabled):
        calls.append("later")

    def calculate(data, enabled=True):
        calls.append("calculation")
        return data

    provider = FixtureProvider(fixture_provider().catalog, [])
    session = await MethodSession.fixture(provider)
    method = python_method(
        calculate,
        name="test.option_order",
        version="1.0.0",
        inputs={"data": DataInput(measures=["value"], format="records")},
        option_checks=[first, later],
    )
    session.register(method)
    trial = await session.run(method, value=METRIC, scope=Scope(DATES, DATE))
    assert trial.result.status == "refused"
    assert trial.result.primary is None
    assert calls == ["first"]
    assert provider.calls == []
    assert [(item.code, item.status) for item in trial.result.validation] == [
        ("PYTHON_OPTION_CHECK", "fail")
    ]


@pytest.mark.parametrize("option_check", [False, True])
def test_invalid_check_return_is_a_programming_error(option_check):
    # A truthy object must not silently pass a reviewed bool/None contract.
    from decision_layer.methods.function.execution import run_checks

    with pytest.raises(TypeError, match="return None/bool"):
        run_checks([lambda: {"valid": True}], {}, option_checks=option_check)


@pytest.mark.parametrize("option_check", [False, True])
def test_only_expected_validation_exceptions_become_refusals(option_check):
    from decision_layer.methods.function.execution import run_checks

    def broken():
        raise RuntimeError("Calculation implementation failed")

    with pytest.raises(RuntimeError, match="implementation failed"):
        run_checks([broken], {}, option_checks=option_check)
