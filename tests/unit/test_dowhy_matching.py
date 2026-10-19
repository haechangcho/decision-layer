"""Known synthetic contrasts and refusal cases; data do not prove identification."""
import importlib.util
import pytest

pytestmark = pytest.mark.skipif(importlib.util.find_spec("dowhy") is None, reason="Install DoWhy extra")


def sample(n=100):
    import numpy as np
    import pandas as pd
    x = np.tile(np.linspace(-1, 1, n), 2)
    treatment = np.repeat([0, 1], n)
    return pd.DataFrame({"unit": np.arange(2*n), "outcome": 3*x + 2*treatment,
                         "treatment": treatment, "baseline": x})


def test_known_att_and_regression_ate_use_native_dowhy():
    from decision_layer.methods.binary_matching import estimate_binary_matching
    from decision_layer.methods.statistics import estimate_binary_regression
    frame = sample()
    matched = estimate_binary_matching(frame, ["baseline"])
    adjusted = estimate_binary_regression(frame, ["baseline"])
    assert matched["value"] == pytest.approx(2)
    assert adjusted["value"] == pytest.approx(2)
    assert matched["target"] == "att" and adjusted["target"] == "ate"
    assert matched["n_unique_matched_controls"] == 100
    assert matched["max_distance"] == pytest.approx(0)
    assert matched["balance"][0]["smd_after"] == pytest.approx(0)
    assert matched["causal_claim"] == "not_established"
    assert matched["uncertainty"] == "not_reported"


@pytest.mark.parametrize("issue", ["duplicate", "missing", "nonbinary", "small", "support", "reuse"])
def test_matching_refuses_unsupported_data(issue):
    import numpy as np
    from decision_layer.methods import Refused
    from decision_layer.methods.binary_matching import estimate_binary_matching
    frame = sample(29 if issue == "small" else 100)
    if issue == "duplicate": frame.loc[1, "unit"] = frame.loc[0, "unit"]
    if issue == "missing": frame.loc[0, "baseline"] = np.nan
    if issue == "nonbinary": frame.loc[0, "treatment"] = 2
    if issue == "support": frame["baseline"] = frame["treatment"] * 1000
    if issue == "reuse": frame.loc[frame.treatment == 1, "baseline"] = np.linspace(0, .001, 100)
    with pytest.raises(Refused):
        estimate_binary_matching(frame, ["baseline"])


async def test_matching_uses_the_shared_entity_query_and_provenance():
    from decision_layer.dev import MethodSession
    from decision_layer.methods import Scope, register_builtins
    from decision_layer.core.models import DatasetSpec, TimeScope
    from decision_layer.testing import FixtureProvider, QueryFixture
    from examples.methods.scenarios.scenarios import catalog, M, TREAT, BASELINE, UNIT, DATE, FEB
    frame = sample()
    spec = DatasetSpec(grain="entity", measures=[M], dimensions=[TREAT, BASELINE], entity=UNIT,
        time=TimeScope(dimension=DATE, date_range=FEB), limit_rows=50001)
    rows = frame[["outcome", "treatment", "baseline", "unit"]].values.tolist()
    session = await MethodSession.fixture(FixtureProvider(catalog(), [QueryFixture(spec, rows)]))
    register_builtins(session.registry)
    trial = await session.run("stats.binary_matching", outcome=M, treatment=TREAT,
        confounders=[BASELINE], unit=UNIT, scope=Scope(FEB, DATE))
    assert trial.result.status == "success"
    assert trial.result.primary.data["value"] == pytest.approx(2)
    assert trial.result.interpretation == "association"
    assert trial.result.provides == ["matched_comparison"]
    assert trial.result.provenance.runtime["dowhy"] == "0.13"
    assert len(trial.attempts) == 1
    session.provider.assert_consumed()
