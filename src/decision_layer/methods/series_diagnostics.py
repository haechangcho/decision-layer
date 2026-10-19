"""An ordinary calculation; its registered adapter owns querying/checks/evidence."""
from decision_layer.methods.time_analysis import SeriesDiagnostics


def largest_moves(data):
    """Find the largest adjacent changes in period/metric/value rows, retaining ties."""
    previous = data.groupby("metric", sort=False).shift()
    changes = data.assign(
        before=previous["value"],
        after=data["value"],
        change=data["value"] - previous["value"],
    )
    changes["from"] = previous["period"]
    changes["to"] = data["period"]
    maximum = changes.groupby("metric")["change"].transform(lambda s: s.abs().max())
    selected = changes.loc[changes["change"].abs().eq(maximum)]
    return selected[["metric", "from", "to", "before", "after", "change"]].round({"change": 4})


METHODS = [SeriesDiagnostics(largest_moves, version="1.1.0")]
