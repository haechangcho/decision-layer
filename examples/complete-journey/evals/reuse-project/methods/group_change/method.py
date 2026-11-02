"""Benchmark calculation over two complete, provider-aggregated group tables."""

from collections import defaultdict
from math import isfinite

from decision_layer.methods import Column, DataInput, python_method


def group_change(current, previous):
    """Rank group changes and inspect the largest group's subgroups; preserve ties."""
    def collect(rows):
        result = {}
        for row in rows:
            key = (row["group"], row["subgroup"])
            value, units = row["metric"], row["units"]
            if None in key or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) for v in (value, units)) or key in result:
                raise ValueError("Groups and finite values must be unique and non-null")
            result[key] = (value, units)
        if not result:
            raise ValueError("Both periods must have observations")
        return result

    now, before = collect(current), collect(previous)
    grouped = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    for (group, subgroup), (value, units) in before.items():
        grouped[group][0] += value
        grouped[group][2] += units
    for (group, subgroup), (value, units) in now.items():
        grouped[group][1] += value
        grouped[group][3] += units
    ranked = sorted(((g, v[0], v[1], v[1] - v[0]) for g, v in grouped.items()),
                    key=lambda row: (-abs(row[3]), row[0]))
    top = abs(ranked[0][3])
    winners = [row[0] for row in ranked if abs(row[3]) == top]
    rows = [{"kind": "overall", "previous": sum(v[0] for v in grouped.values()),
             "current": sum(v[1] for v in grouped.values()),
             "units_previous": sum(v[2] for v in grouped.values()), "units_current": sum(v[3] for v in grouped.values())}]
    rows += [{"kind": "group", "group": g, "previous": a, "current": b, "change": c,
              "units_previous": grouped[g][2], "units_current": grouped[g][3],
              "selected": len(winners) == 1 and g == winners[0], "tie": len(winners) > 1 and g in winners}
             for g, a, b, c in ranked]
    if len(winners) == 1:
        winner = winners[0]
        keys = sorted({key for key in before.keys() | now.keys() if key[0] == winner})
        rows += [{"kind": "subgroup", "group": group, "subgroup": subgroup,
                  "previous": before.get((group, subgroup), (0.0, 0.0))[0], "current": now.get((group, subgroup), (0.0, 0.0))[0],
                  "units_previous": before.get((group, subgroup), (0.0, 0.0))[1], "units_current": now.get((group, subgroup), (0.0, 0.0))[1]}
                 for group, subgroup in keys]
    return rows


columns = {
    "metric": Column(source="measure", dtype="number"),
    "units": Column(source="measure", dtype="number"),
    "group": Column(source="dimension"),
    "subgroup": Column(source="dimension"),
}
METHOD = python_method(
    group_change, name="benchmark.group_change", version="1.1.0", output="table",
    inputs={
        "current": DataInput(columns=columns, format="records", require_complete=True),
        "previous": DataInput(columns=columns, format="records", require_complete=True, period_parameter="comparison", period_role="comparison"),
    },
)
