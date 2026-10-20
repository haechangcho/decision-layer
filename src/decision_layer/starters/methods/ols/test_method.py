"""Check known synthetic coefficients and invalid inputs without a server."""

import numpy as np
import pandas as pd
import pytest
from .method import ols


def sample():
    baseline = np.tile(np.linspace(-1, 1, 100), 2)
    treatment = np.repeat([0, 1], 100)
    return pd.DataFrame(
        {
            "entity_id": np.arange(200),
            "outcome": 3 * baseline + 2 * treatment,
            "treatment": treatment,
            "confounders_0": baseline,
        }
    )


def test_known_coefficient():
    result = ols(sample(), "outcome", "treatment", ["confounders_0"])
    assert result["value"] == pytest.approx(2)
    assert result["n_observations"] == 200
    assert result["causal_claim"] == "not_established"


def test_continuous_treatment_keeps_its_scale():
    frame = sample()
    frame["treatment"] = np.tile(np.linspace(0.05, 0.30, 100), 2)
    frame["confounders_0"] = np.repeat([0.0, 1.0], 100)
    frame["outcome"] = 50 * frame["treatment"] + 3 * frame["confounders_0"]
    assert ols(frame, "outcome", "treatment", ["confounders_0"])[
        "value"
    ] == pytest.approx(50)


@pytest.mark.parametrize("problem", ["duplicate", "missing", "constant", "collinear"])
def test_invalid_data(problem):
    frame = sample()
    if problem == "duplicate":
        frame.loc[1, "entity_id"] = frame.loc[0, "entity_id"]
    if problem == "missing":
        frame.loc[0, "outcome"] = np.nan
    if problem == "constant":
        frame["outcome"] = 1
    if problem == "collinear":
        frame["confounders_0"] = frame["treatment"]
    with pytest.raises(ValueError):
        ols(frame, "outcome", "treatment", ["confounders_0"])
