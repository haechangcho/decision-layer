import importlib.util
import pytest

pytestmark = pytest.mark.skipif(importlib.util.find_spec("dowhy") is None, reason="Install DoWhy extra")


def test_known_slope_specific_contrast_and_source_scale():
    from decision_layer.methods.regression_adjustment import estimate_regression_adjustment
    from examples.methods.patterns.continuous_regression import sample
    frame = sample()
    slope = estimate_regression_adjustment(frame, ["baseline"])
    contrast = estimate_regression_adjustment(frame, ["baseline"], .10, .20)
    assert slope["value"] == pytest.approx(50)
    assert slope["result_scale"] == "per_treatment_unit" and slope["contrast"] is None
    assert slope["estimation_contrast"] == [.05, .30]
    assert contrast["value"] == pytest.approx(5)
    assert contrast["contrast"] == [.10, .20]
    frame["treatment"] *= 100
    percent = estimate_regression_adjustment(frame, ["baseline"])
    assert percent["value"] == pytest.approx(.5)
    assert slope["support"]["joint_support"] == "not_verified"
    assert slope["assumptions_status"] == "not_verified"


def test_binary_still_returns_zero_to_one_change():
    from decision_layer.methods.regression_adjustment import estimate_regression_adjustment
    from tests.unit.test_dowhy_matching import sample
    payload = estimate_regression_adjustment(sample(), ["baseline"])
    assert payload["value"] == pytest.approx(2)
    assert payload["treatment_type"] == "binary"
    from decision_layer.methods import Refused
    with pytest.raises(Refused):
        estimate_regression_adjustment(sample(), ["baseline"], .2, .8)


@pytest.mark.parametrize("problem", ["half_pair", "same_values", "outside", "missing", "duplicate", "categorical", "constant", "collinear", "infinite", "few_values"])
def test_invalid_data_and_contrasts_refuse(problem):
    import numpy as np
    from decision_layer.methods import Refused
    from decision_layer.methods.regression_adjustment import estimate_regression_adjustment
    from examples.methods.patterns.continuous_regression import sample
    frame = sample()
    params = {}
    if problem == "half_pair": params = {"control_value": .1}
    if problem == "same_values": params = {"control_value": .1, "treatment_value": .1}
    if problem == "outside": params = {"control_value": .1, "treatment_value": .8}
    if problem == "missing": frame.loc[0, "treatment"] = np.nan
    if problem == "duplicate": frame.loc[1, "unit"] = frame.loc[0, "unit"]
    if problem == "categorical": frame["treatment"] = ["a", "b"] * 100
    if problem == "constant": frame["treatment"] = .1
    if problem == "collinear": frame["treatment"] = 2*frame["baseline"]
    if problem == "infinite": frame.loc[0, "treatment"] = np.inf
    if problem == "few_values": frame["treatment"] = np.arange(200) % 3
    with pytest.raises(Refused):
        estimate_regression_adjustment(frame, ["baseline"], **params)


async def test_shared_session_query_result_and_provenance():
    from examples.methods.patterns.continuous_regression import demonstrate
    results = await demonstrate()
    assert results[0]["value"] == pytest.approx(50)
    assert results[1]["value"] == pytest.approx(5)


async def test_incomplete_contrast_refuses_without_query():
    from examples.methods.patterns.continuous_regression import example_session, M, RATE, BASELINE, UNIT, FEB, DATE
    from decision_layer.methods import Scope
    session = await example_session()
    result = (await session.run("stats.regression_adjustment", outcome=M, treatment=RATE,
        confounders=[BASELINE], unit=UNIT, scope=Scope(FEB, DATE), control_value=.1)).result
    assert result.status == "refused"
    assert not session.provider.calls
