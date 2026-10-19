"""Ordinary functions plus separate, operator-reviewed registration."""

from decision_layer.methods import DataInput, python_method


def rank_groups(data, descending=True):
    """Rank observed values, retaining tied ranks."""
    return data.assign(
        rank=data["value"].rank(method="min", ascending=not descending).astype(int)
    )


def compare_periods(current, previous):
    """Compare the same observed groups across two explicitly selected periods."""
    joined = current.merge(
        previous, on="group", suffixes=("_current", "_previous"), validate="one_to_one"
    )
    return joined.assign(change=joined.value_current - joined.value_previous)


def same_groups(current, previous):
    if set(current.group) != set(previous.group):
        raise ValueError("Both periods must contain the same observed groups")


METHODS = [
    python_method(
        rank_groups,
        name="workshop.rank",
        version="1.0.0",
        inputs={"data": DataInput(measures=["value"], dimensions=["group"])},
    ),
    python_method(
        compare_periods,
        name="workshop.compare",
        version="1.0.0",
        inputs={
            "current": DataInput(measures=["value"], dimensions=["group"]),
            "previous": DataInput(
                measures=["value"],
                dimensions=["group"],
                period_parameter="baseline",
                period_role="comparison",
            ),
        },
        checks=[same_groups],
    ),
]


async def practice_session(prior=None):
    """Prepare repeatable fixture data with no Methods registered."""
    from decision_layer.core.models import DatasetSpec, TimeScope
    from decision_layer.dev import MethodSession
    from decision_layer.testing import FixtureProvider, QueryFixture
    from examples.methods.authoring.sample_data import (
        METRIC,
        DIMENSION,
        DATE,
        DATES,
        fixture_provider,
    )

    current = DatasetSpec(
        grain="aggregate",
        measures=[METRIC],
        dimensions=[DIMENSION],
        time=TimeScope(dimension=DATE, date_range=DATES),
        limit_rows=50001,
    )
    before = current.model_copy(
        update={
            "time": TimeScope(dimension=DATE, date_range=("2026-08-01", "2026-08-31"))
        }
    )

    class PracticeProvider(FixtureProvider):
        async def execute(self, spec, credentials, *, with_sql=False):
            # Notebook cells can be rerun in any order. Match the entire query,
            # while keeping the shared FixtureProvider's one-shot script strict.
            fixture = next((item for item in self._queries if item.spec == spec), None)
            self.calls.append(spec.model_copy(deep=True))
            if fixture is None:
                raise AssertionError(f"Unexpected practice query: {spec.model_dump()}")
            response = FixtureProvider(self.catalog, [fixture])
            return await response.execute(spec, credentials, with_sql=with_sql)

    provider = PracticeProvider(
        fixture_provider().catalog,
        [
            QueryFixture(current, [[30, "A"], [20, "B"], [20, "C"]]),
            QueryFixture(
                before,
                prior if prior is not None else [[10, "A"], [25, "B"], [20, "C"]],
            ),
        ],
    )
    return await MethodSession.fixture(provider)
