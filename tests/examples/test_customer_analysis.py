"""The customer tutorial shows the actual Cube query and function inputs."""

import json
from pathlib import Path

import pytest

from decision_layer.methods import Scope
from examples.methods.authoring.customer_analysis import (
    customer_session,
)
from examples.methods.project.methods.ols.method import METHOD


def inputs():
    return {
        "entity_id": "cube://shop/customers/id",
        "outcome": "cube://shop/customers/purchase_amount",
        "treatment": "cube://shop/customers/ad_exposures",
        "confounders": [
            "cube://shop/customers/age",
            "cube://shop/customers/prior_purchase_amount",
        ],
    }


async def test_customer_tutorial_query_matches_documentation_and_known_slopes():
    session = await customer_session()
    assert session.list_methods() == []
    session.register(METHOD)
    trial = await session.run(
        METHOD,
        bindings=inputs(),
        scope=Scope(
            date_range=("2026-02-01", "2026-02-28"),
            time_dimension="cube://shop/customers/date",
        ),
    )
    assert trial.result.status == "success"
    data = trial.result.primary.data
    assert data["value"] == pytest.approx(50)
    assert data["n_observations"] == 200
    assert data["coefficients"]["confounders_0"] == pytest.approx(10)
    assert data["coefficients"]["confounders_1"] == pytest.approx(0.2)
    assert data["causal_claim"] == "not_established"
    mapping = json.loads(trial.result.provenance.runtime["python.resolved_inputs"])[
        "data"
    ]
    assert mapping["semantic_refs"] == {
        "entity_id": "cube://shop/customers/id",
        "outcome": "cube://shop/customers/purchase_amount",
        "treatment": "cube://shop/customers/ad_exposures",
        "confounders_0": "cube://shop/customers/age",
        "confounders_1": "cube://shop/customers/prior_purchase_amount",
    }
    assert mapping["column_args"] == {
        "outcome": "outcome",
        "treatment": "treatment",
        "confounders": ["confounders_0", "confounders_1"],
    }
    notebook = (
        Path(__file__).resolve().parents[2]
        / "docs/tutorials/methods/write_your_method.ko.ipynb"
    )
    cells = json.loads(notebook.read_text())["cells"]
    explanation = next(
        "".join(c["source"])
        for c in cells
        if "".join(c["source"]).startswith("### 선택한 입력이 함수에 전달되기까지")
    )
    documented_request = json.loads(
        explanation.split("```json\n", 1)[1].split("```", 1)[0]
    )
    assert session.provider.client.requests[0] == {
        "path": "/load",
        "body": documented_request,
    }
    assert trial.queries[0].native_query == {
        key: value
        for key, value in documented_request["query"].items()
        if key not in ("limit", "offset")
    }


async def test_customer_fixture_does_not_answer_unprepared_periods():
    session = await customer_session()
    session.register(METHOD)
    with pytest.raises(AssertionError, match="Unexpected customer fixture query"):
        await session.run(
            METHOD,
            bindings=inputs(),
            scope=Scope(
                date_range=("2026-03-01", "2026-03-31"),
                time_dimension="cube://shop/customers/date",
            ),
        )
    assert session.provider.client.requests == []


async def test_rank_and_ols_share_one_session_and_can_be_rerun():
    from examples.methods.authoring.customer_analysis import practice_session
    from examples.methods.project.methods.rank.method import (
        METHOD as RANK,
    )

    session = await practice_session()
    session.register(RANK)
    assert [m.name for m in session.list_methods()] == ["workshop_project.rank"]
    rank_inputs = {
        "bindings": {
            "value": "cube://shop/sales/revenue",
            "group": "cube://shop/sales/product",
        },
        "scope": Scope(
            date_range=("2026-09-01", "2026-09-30"),
            time_dimension="cube://shop/sales/date",
        ),
    }
    first = await session.run(RANK, **rank_inputs)
    session.register(METHOD)
    assert [m.name for m in session.list_methods()] == [
        "workshop_project.rank",
        "workshop_project.ols",
    ]
    ols = await session.run(
        METHOD,
        bindings=inputs(),
        scope=Scope(
            date_range=("2026-02-01", "2026-02-28"),
            time_dimension="cube://shop/customers/date",
        ),
    )
    again = await session.run(RANK, **rank_inputs)
    assert first.result.status == again.result.status == ols.result.status == "success"
    assert first.result.primary.data == again.result.primary.data
    assert [row["rank"] for row in first.result.primary.data] == [1, 2, 2]
    assert ols.result.primary.data["value"] == pytest.approx(50)
