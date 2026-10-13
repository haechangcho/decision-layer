"""Exact governed query fixtures, reusable from Python, pytest and Jupyter."""
import asyncio
from decision_layer.core.models import DatasetSpec, SemanticCatalog, SemanticObject, TimeScope
from decision_layer.dev import MethodSession
from decision_layer.methods import Scope, Filter
from decision_layer.testing import FixtureProvider, QueryFixture
from .experiment import data
from .methods import categorical_dml, continuous_dml

ROOT = "cube://review/units/"
Y, T, W, UNIT, DATE, GROUP = [ROOT + name for name in ("outcome", "treatment", "baseline", "id", "date", "cohort")]
PERIOD = ("2026-01-01", "2026-01-31")



async def run_case(kind="categorical", *, same_contrast=False):
    frame = data(kind)
    catalog = SemanticCatalog(provider="cube", instance="review", objects=[
        SemanticObject(ref=Y, kind="measure", data_type="number", title="Outcome", entity=UNIT,
                       dimension_refs=[T, W, DATE, GROUP], time_dimension=DATE, metric_kind="additive"),
        *[SemanticObject(ref=ref, kind="dimension", data_type=dtype, title=name) for ref, dtype, name in
          [(T, "string" if kind == "categorical" else "number", "Treatment"), (W, "number", "Baseline"),
           (UNIT, "string", "Unit"), (GROUP, "string", "Cohort")]],
        SemanticObject(ref=DATE, kind="time_dimension", data_type="time", title="Date")])
    selection = Filter(member=GROUP, operator="equals", values=["eligible"])
    # Independent expected query: aliases cannot hide missing scope or filters.
    spec = DatasetSpec(grain="entity", entity=UNIT, measures=[Y], dimensions=[T, W],
                       filters=[selection], time=TimeScope(dimension=DATE, date_range=PERIOD), limit_rows=50001)
    rows = frame[["outcome", "treatment", "w", "unit"]].values.tolist()
    provider = FixtureProvider(catalog, [QueryFixture(spec, rows)] if not same_contrast else [])
    session = await MethodSession.fixture(provider)
    implementation = categorical_dml if kind == "categorical" else continuous_dml
    session.register(implementation)
    try:
        trial = await session.run(implementation, measures={"outcome": Y},
            dimensions={"treatment": T, "confounder": W}, entity=UNIT,
            scope=Scope(PERIOD, DATE), filters=[selection], params={"control": "basic" if kind == "categorical" else .5,
                "treated": ("basic" if kind == "categorical" else .5) if same_contrast else ("plus" if kind == "categorical" else 1.5)})
        provider.assert_consumed()
        return trial
    finally:
        session.close()


if __name__ == "__main__":
    for kind in ("categorical", "continuous"):
        trial = asyncio.run(run_case(kind))
        print(kind, trial.result.status, trial.result.primary.data, trial.queries)
