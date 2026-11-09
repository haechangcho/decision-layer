"""A registered, provider-fed ranking. It never connects to a warehouse directly."""

from typing import Annotated
from pydantic import Field
from decision_layer.methods import Column, DataInput, python_method
from decision_layer.methods.output import Table
from decision_layer.core.models import (
    ArtifactColumn,
    Filter,
    SelectionCandidate,
    SelectionCondition,
    SelectionOutput,
)


def rank_groups(data, value, groups, limit: Annotated[int, Field(ge=1, le=100)] = 10):
    """Rank complete observed groups; no grouping returns the overall metric value.

    Values are already aggregated by Cube. Keep every candidate in the typed
    selection output so a later top-N request can detect a boundary tie.
    """
    refs = data.attrs["semantic_refs"]
    columns = [
        ArtifactColumn(
            name=name, ref=refs[name], role="measure" if name == value else "dimension"
        )
        for name in [*groups, value]
    ]
    if not groups:
        return Table([{value: float(data[value].sum())}], columns=columns)
    ranked = data.sort_values(value, ascending=False, kind="stable")
    rows = ranked.to_dict(orient="records")
    output = Table(rows[:limit], columns=columns)
    inherited = [Filter.model_validate(item) for item in data.attrs.get("filters", [])]
    output.selections = {
        "ranked_groups": SelectionOutput(
            complete=True,
            rank_by="value",
            direction="desc",
            candidates=[
                SelectionCandidate(
                    path=[
                        SelectionCondition(member=refs[name], value=row[name])
                        for name in groups
                    ],
                    filters=[
                        *inherited,
                        *[
                            Filter(
                                member=refs[name], operator="equals", values=[row[name]]
                            )
                            for name in groups
                        ],
                    ],
                    score=float(row[value]),
                )
                for row in rows
            ],
        )
    }
    return output


METHOD = python_method(
    rank_groups,
    name="retail_review.group_rank",
    version="1.0.0",
    label="Group metric ranking",
    inputs={
        "data": DataInput(
            columns={
                "value": Column(source="measure", dtype="number"),
                "groups": Column(source="dimension", multiple=True, required=False),
            },
            filters_parameter="filters",
            require_complete=True,
        )
    },
    selection_outputs=["ranked_groups"],
)

METHOD.manifest.parameters["limit"].ui_group = "basic"
