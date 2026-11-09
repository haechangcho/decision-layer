"""Known-answer examples for complete ranking handoffs and daily concentration."""

from pathlib import Path
import importlib.util
import pandas as pd
import pytest

ROOT = Path(__file__).parents[2] / "examples/complete-journey/retail-review/methods"


def load(name):
    spec = importlib.util.spec_from_file_location(
        "example_" + name, ROOT / name / "method.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rank_keeps_unshown_candidates_and_inherited_filters():
    module = load("rank_groups")
    frame = pd.DataFrame(
        [
            {"value": 9.0, "group": "A"},
            {"value": 7.0, "group": "B"},
            {"value": 7.0, "group": "C"},
        ]
    )
    frame.attrs = {
        "semantic_refs": {
            "value": "cube://local/sales/amount",
            "group": "cube://local/product/category",
        },
        "filters": [
            {
                "member": "cube://local/product/department",
                "operator": "equals",
                "values": ["D"],
            }
        ],
    }
    table = module.rank_groups(frame, "value", ["group"], limit=2)
    assert len(table.primary.data) == 2
    candidates = table.selections["ranked_groups"].candidates
    assert len(candidates) == 3 and candidates[-1].score == 7
    assert candidates[0].filters[0].values == ["D"]
    assert candidates[0].filters[-1].values == ["A"]


def test_daily_concentration_keeps_observed_days_and_earliest_tied_peak():
    module = load("daily_profile")
    frame = pd.DataFrame(
        [
            {"time": "2000-01-03", "value": 20.0, "group": "A"},
            {"time": "2000-01-01", "value": 20.0, "group": "A"},
            {"time": "2000-01-07", "value": 10.0, "group": "A"},
        ]
    )
    module.valid_input(frame, "value", ["group"])
    result = module.daily_profile(frame, "value", ["group"])
    assert result.primary.data[0]["total"] == 50
    assert result.primary.data[0]["peak_share"] == 0.4
    assert result.primary.data[0]["peak_date"] == "2000-01-01"
    assert result.primary.data[0]["observed_days"] == 3
    assert len(result.artifacts[0].data["rows"]) == 3


@pytest.mark.parametrize("values", [[0, 0], [-1, 3], [float("nan"), 2]])
def test_invalid_concentration_values_do_not_produce_a_claim(values):
    module = load("daily_profile")
    frame = pd.DataFrame({"value": values, "group": ["A", "A"]})
    with pytest.raises(ValueError):
        module.valid_input(frame, "value", ["group"])
