import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("benchmark_change_method", Path(__file__).parents[2] / "examples/complete-journey/evals/reuse-project/methods/group_change/method.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
group_change = module.group_change


def row(group, subgroup, metric):
    return {"group": group, "subgroup": subgroup, "metric": metric, "units": 1}


def test_new_and_missing_groups_and_selected_subgroups():
    result = group_change([row("A", "x", 4), row("C", "z", 8)], [row("A", "x", 10), row("B", "y", 2)])
    assert result[0] == {"kind": "overall", "previous": 12.0, "current": 12.0, "units_previous": 2.0, "units_current": 2.0}
    assert result[1]["group"] == "C" and result[1]["change"] == 8 and result[1]["selected"]
    assert result[-1] == {"kind": "subgroup", "group": "C", "subgroup": "z", "previous": 0.0, "current": 8, "units_previous": 0.0, "units_current": 1}


def test_tie_never_selects_a_subgroup():
    result = group_change([row("A", "x", 0), row("B", "x", 10)], [row("A", "x", 5), row("B", "x", 5)])
    assert all(item["tie"] and not item["selected"] for item in result[1:])
    assert not any(item["kind"] == "subgroup" for item in result)


@pytest.mark.parametrize("bad", [[], [row("A", "x", float("nan"))], [row("A", "x", 1), row("A", "x", 2)]])
def test_bad_data_is_rejected(bad):
    with pytest.raises(ValueError):
        group_change(bad, [row("A", "x", 1)])
