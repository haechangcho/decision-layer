import importlib.util
import pytest

pytestmark = pytest.mark.skipif(importlib.util.find_spec("dowhy") is None, reason="Install DoWhy extra")


@pytest.fixture(params=["legacy", "ordinary"])
def estimate_regression_adjustment(request):
    from decision_layer.methods.regression_adjustment import estimate_regression_adjustment as legacy
    from decision_layer.methods.native_regression import analyze

    if request.param == "legacy":
        return legacy

    def ordinary(frame, columns, *args, **kwargs):
        data = frame.rename(columns={name: f"confounders_{i}" for i, name in enumerate(columns)})
        return analyze(data, *args, **kwargs)

    return ordinary


def test_known_slope_specific_contrast_and_source_scale(estimate_regression_adjustment):
    from examples.methods.statistics.continuous_regression import sample
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


def test_binary_still_returns_zero_to_one_change(estimate_regression_adjustment):
    from tests.unit.test_dowhy_matching import sample
    payload = estimate_regression_adjustment(sample(), ["baseline"])
    assert payload["value"] == pytest.approx(2)
    assert payload["treatment_type"] == "binary"
    from decision_layer.methods import Refused
    with pytest.raises(Refused):
        estimate_regression_adjustment(sample(), ["baseline"], .2, .8)


@pytest.mark.parametrize("problem", ["half_pair", "same_values", "outside", "missing", "duplicate", "categorical", "constant", "collinear", "infinite", "few_values"])
def test_invalid_data_and_contrasts_refuse(problem, estimate_regression_adjustment):
    import numpy as np
    from decision_layer.methods import Refused
    from examples.methods.statistics.continuous_regression import sample
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
    from examples.methods.statistics.continuous_regression import demonstrate
    results = await demonstrate()
    assert results[0]["value"] == pytest.approx(50)
    assert results[1]["value"] == pytest.approx(5)


async def test_incomplete_contrast_refuses_without_query():
    from examples.methods.statistics.continuous_regression import example_session, M, RATE, BASELINE, UNIT, FEB, DATE
    from decision_layer.methods import Scope
    session = await example_session()
    result = (await session.run("stats.regression_adjustment", outcome=M, treatment=RATE,
        confounders=[BASELINE], unit=UNIT, scope=Scope(FEB, DATE), control_value=.1)).result
    assert result.status == "refused"
    assert not session.provider.calls


@pytest.mark.parametrize("binary", [False, True])
@pytest.mark.parametrize("contrast", ["default", "forward", "reverse"])
def test_refactored_and_editable_source_preserve_complete_payload(binary, contrast, tmp_path):
    import numpy as np
    from pandas.testing import assert_frame_equal
    from decision_layer.methods import registry
    from decision_layer.methods.native_regression import analyze
    from decision_layer.methods.regression_adjustment import estimate_regression_adjustment
    from decision_layer.methods.source import capture_source
    from tests.unit.test_authoring_source import import_source
    from tests.unit.test_dowhy_matching import sample as binary_sample
    from examples.methods.statistics.continuous_regression import sample as continuous_sample

    data = (binary_sample() if binary else continuous_sample()).rename(
        columns={"baseline": "confounders_0"}
    )
    # Exercise categorical encoding and positional alignment with a non-default index.
    data["confounders_1"] = np.tile(["east", "west", "north", "south"], len(data) // 4)
    data.index = np.arange(len(data)) * 3 + 10
    data.attrs["semantic_refs"] = {"treatment": "cube://test/observations/treatment"}
    before = data.copy(deep=True)
    values = (0, 1) if binary else (.1, .2)
    args = () if contrast == "default" else values if contrast == "forward" else values[::-1]

    expected = estimate_regression_adjustment(data, ["confounders_0", "confounders_1"], *args)
    expected.update(
        treatment_ref=data.attrs["semantic_refs"]["treatment"],
        treatment_scale="as_stored_in_semantic_source",
    )
    source = capture_source(registry.get("stats.regression_adjustment"))
    editable = import_source(tmp_path / "editable_regression.py", source.editor_content)
    assert analyze(data, *args) == expected
    assert editable.fn(data, *args) == expected
    assert_frame_equal(data, before)
    assert data.attrs == before.attrs
