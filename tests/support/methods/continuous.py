"""A known numeric-treatment slope on the same governed fixture execution path."""

from decision_layer.dev import MethodSession
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
    return session
