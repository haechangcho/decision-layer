"""Descriptive daily concentration; no missing-day imputation or significance test."""

import math
from decision_layer.methods import Column, DataInput, python_method
from decision_layer.methods.output import Table
from decision_layer.core.models import Artifact, RoleSpec


def valid_input(data, value, groups):
    if not all(math.isfinite(float(v)) and v >= 0 for v in data[value]):
        raise ValueError("Daily concentration requires finite, non-negative values")
    if (data.groupby(groups, dropna=False)[value].sum() <= 0).any():
        raise ValueError("Each group must have a positive period total")


def daily_profile(data, value, groups):
    """Show each group's largest observed day and its share of the period sum."""
    rows = []
    artifacts = []
    for key, frame in data.groupby(groups, dropna=False, sort=False):
        keys = key if isinstance(key, tuple) else (key,)
        total = float(frame[value].sum())
        peak = frame.sort_values([value, "time"], ascending=[False, True]).iloc[0]
        rows.append(
            {
                **dict(zip(groups, keys)),
                "total": total,
                "peak_date": str(peak["time"])[:10],
                "peak_value": float(peak[value]),
                "peak_share": float(peak[value]) / total,
                "observed_days": len(frame),
            }
        )
        values = frame.sort_values("time")[["time", value]].to_dict(orient="records")
        artifacts.append(
            Artifact(
                type="time_series",
                title=" · ".join(map(str, keys)),
                data={
                    "rows": [
                        {"time": str(row["time"]), "value": float(row[value])}
                        for row in values
                    ],
                    "time_key": "time",
                    "metric": "value",
                    "granularity": "day",
                },
            )
        )
    output = Table(sorted(rows, key=lambda row: row["peak_share"], reverse=True))
    output.artifacts = artifacts
    output.warnings = [
        "Concentration describes observed days only. Missing days are not filled with zero; no significance or causal conclusion is established."
    ]
    return output


METHOD = python_method(
    daily_profile,
    name="retail_review.daily_profile",
    version="1.0.0",
    label="Daily concentration",
    inputs={
        "data": DataInput(
            columns={
                "value": RoleSpec(
                    kind="measure", data_type="number", metric_kinds=["additive"]
                ),
                "groups": Column(source="dimension", multiple=True),
            },
            column_args=["value"],
            time_granularity="day",
            filters_parameter="filters",
            require_complete=True,
        )
    },
    checks=(valid_input,),
)

# Declare the additional per-group chart artifacts in the same Method contract.
METHOD.manifest.outputs.append("time_series")
