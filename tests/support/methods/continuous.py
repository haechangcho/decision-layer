"""A known numeric-treatment slope on the same governed fixture execution path."""

from decision_layer.dev import MethodSession
from decision_layer.methods import Scope, register_builtins
from decision_layer.core.models import DatasetSpec, TimeScope
from decision_layer.testing import FixtureProvider, QueryFixture
from tests.support.methods.cases import catalog, M, RATE, BASELINE, UNIT, DATE, FEB


def sample():
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(7)
    dose = np.linspace(0.05, 0.30, 200)
    baseline = rng.normal(size=200)
    return pd.DataFrame(
        {
            "unit": [str(i) for i in range(200)],
            "treatment": dose,
            "baseline": baseline,
            "outcome": 100 + 50 * dose + 3 * baseline,
        }
    )


async def example_session():
    frame = sample()
    spec = DatasetSpec(
        grain="entity",
        measures=[M, RATE],
        dimensions=[BASELINE],
        entity=UNIT,
        time=TimeScope(dimension=DATE, date_range=FEB),
        limit_rows=50001,
    )
    rows = frame[["outcome", "treatment", "baseline", "unit"]].values.tolist()
    session = await MethodSession.fixture(
        FixtureProvider(catalog(), [QueryFixture(spec, rows)])
    )
    register_builtins(session.registry)
    return session


async def demonstrate():
    results = []
    for label, params in (
        ("per stored treatment unit", {}),
        ("0.10 to 0.20", {"control_value": 0.10, "treatment_value": 0.20}),
    ):
        session = await example_session()
        trial = await session.run(
            "stats.regression_adjustment",
            outcome=M,
            treatment=RATE,
            confounders=[BASELINE],
            unit=UNIT,
            scope=Scope(FEB, DATE),
            **params,
        )
        session.provider.assert_consumed()
        results.append({"result": label, "value": trial.result.primary.data["value"]})
        session.close()
    return results
