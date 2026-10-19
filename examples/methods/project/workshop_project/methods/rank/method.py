from decision_layer.methods import Column, DataInput, python_method


def analyze(data, descending=True):
    """Rank observed groups by a selected metric, retaining ties."""
    return data.assign(rank=data["value"].rank(method="min", ascending=not descending))


METHOD = python_method(
    analyze,
    name="workshop_project.rank",
    version="1.0.0",
    inputs={
        "data": DataInput(
            columns={
                "value": Column(source="measure"),
                "group": Column(source="dimension"),
            }
        ),
    },
)
