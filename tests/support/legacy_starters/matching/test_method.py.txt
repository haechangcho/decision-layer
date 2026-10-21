"""Check known synthetic group differences and invalid inputs without a server."""

import numpy as np
import pandas as pd
import pytest
from .method import matching
from decision_layer.methods.context import Refused


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


def test_known_difference():
    result = matching(sample(), "outcome", "treatment", ["confounders_0"])
    assert result["value"] == pytest.approx(2)
    assert result["n_unique_matched_controls"] == 100
    assert result["max_distance"] == pytest.approx(0, abs=1e-7)
    assert result["causal_claim"] == "not_established"


@pytest.mark.parametrize(
    "problem", ["duplicate", "missing", "nonbinary", "small", "support", "reuse"]
)
def test_invalid_data(problem):
    frame = sample()
    if problem == "duplicate":
        frame.loc[1, "entity_id"] = frame.loc[0, "entity_id"]
    if problem == "missing":
        frame.loc[0, "outcome"] = np.nan
    if problem == "nonbinary":
        frame.loc[0, "treatment"] = 2
    if problem == "small":
        frame = frame.drop(frame.index[frame.treatment == 1][29:])
    if problem == "support":
        frame["confounders_0"] = frame["treatment"] * 1000
    if problem == "reuse":
        frame.loc[frame.treatment == 1, "confounders_0"] = np.linspace(0, 0.001, 100)
    with pytest.raises((ValueError, Refused)):
        matching(frame, "outcome", "treatment", ["confounders_0"])
