import pytest
from decision_layer.core.models import (
    Result,
    SelectionOutput,
    SelectionCandidate,
    SelectionCondition,
    Filter,
)
from decision_layer.runs.expressions import (
    resolve,
    AmbiguousSelection,
    UnresolvedExpression,
)
from tests.support.semantic import CAT


def result(scores=(9, 7, 4, 1)):
    common = Filter(member=CAT, operator="equals", values=["parent"])
    candidates = [
        SelectionCandidate(
            path=[SelectionCondition(member=CAT, value=str(i))],
            filters=[common, Filter(member=CAT, operator="equals", values=[str(i)])],
            score=s,
        )
        for i, s in enumerate(scores)
    ]
    return Result(
        status="success",
        selections={
            "ranked_groups": SelectionOutput(
                complete=True, rank_by="value", direction="desc", candidates=candidates
            )
        },
    )


def test_current_top_three_become_filters_and_keep_parent_context():
    evidence = []
    source = {
        "source": "step",
        "step_id": "rank",
        "output": "ranked_groups",
        "select": "top",
        "count": 3,
        "project": "filters",
    }
    value = resolve(source, None, {"rank": result()}, evidence=evidence)
    assert value == [
        {"member": CAT, "operator": "equals", "values": ["parent"]},
        {"member": CAT, "operator": "equals", "values": ["0", "1", "2"]},
    ]
    assert evidence[0]["selection"]["selected_count"] == 3
    assert resolve({**source, "select": "first", "count": 1}, None, {"rank": result()})[
        -1
    ]["values"] == ["0"]
    with pytest.raises(AmbiguousSelection):
        resolve(source, None, {"rank": result((9, 7, 4, 4))})
    mixed = result()
    mixed.selections["ranked_groups"].candidates[1].filters[0] = Filter(
        member=CAT, operator="equals", values=["different"]
    )
    with pytest.raises(UnresolvedExpression):
        resolve(source, None, {"rank": mixed})
