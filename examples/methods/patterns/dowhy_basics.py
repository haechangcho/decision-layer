"""Two native DoWhy methods on a known synthetic binary contrast."""
import asyncio
import json

from decision_layer.dev import MethodSession
from decision_layer.methods import Scope, register_builtins
from decision_layer.core.models import DatasetSpec, TimeScope
from decision_layer.testing import FixtureProvider, QueryFixture
from .scenarios import catalog, M, TREAT, BASELINE, UNIT, DATE, FEB


def observations():
    import numpy as np
    x = np.tile(np.linspace(-1, 1, 100), 2)
    treated = np.repeat([0, 1], 100)
    # Exactly paired covariates: true contrast is 2 in both populations.
    return [[float(3*v + 2*t), int(t), float(v), str(i)]
            for i, (v, t) in enumerate(zip(x, treated))]


async def demonstrate():
    spec = DatasetSpec(grain="entity", measures=[M], dimensions=[TREAT, BASELINE], entity=UNIT,
        time=TimeScope(dimension=DATE, date_range=FEB), limit_rows=50001)
    session = await MethodSession.fixture(FixtureProvider(catalog(), [
        QueryFixture(spec, observations()), QueryFixture(spec, observations())]))
    register_builtins(session.registry)
    results = []
    for name in ("stats.binary_matching", "stats.regression_adjustment"):
        trial = await session.run(name, outcome=M, treatment=TREAT,
            confounders=[BASELINE], unit=UNIT, scope=Scope(FEB, DATE))
        if trial.result.status != "success":
            raise RuntimeError(trial.result.warnings)
        data = trial.result.primary.data
        results.append({"method": name, "value": data["value"], "target": data["target"],
                        "assumptions_status": data["assumptions_status"]})
    session.provider.assert_consumed()
    session.close()
    return results


if __name__ == "__main__":
    print(json.dumps(asyncio.run(demonstrate()), indent=2))
