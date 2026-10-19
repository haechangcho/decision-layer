"""Ordinary pandas function, reusable without importing Decision Layer."""


def rank_values(frame, descending: bool = True):
    """Rank the supplied group values, preserving equal ranks for ties."""
    result = frame.copy()
    result["rank"] = result["value"].rank(method="min", ascending=not descending).astype(int)
    return result.sort_values(["rank", "group"]).reset_index(drop=True)


def registered_method():
    from decision_layer.methods import InputTable, calculation
    return calculation(rank_values, name="workshop.native_rank", version="1.0.0",
                       table=InputTable(measures={"value": "metric"}, dimensions={"group": "group"},
                                        format="dataframe"), requires_period=True)


async def fixture_session():
    """Scripted contributor test, not a local data-file source."""
    from decision_layer.core.models import DatasetSpec, TimeScope
    from decision_layer.dev import MethodSession
    from decision_layer.testing import FixtureProvider, QueryFixture
    from examples.methods.first_method.fixtures import METRIC, DIMENSION, DATE, DATES, fixture_provider
    spec = DatasetSpec(grain="aggregate", measures=[METRIC], dimensions=[DIMENSION],
                       time=TimeScope(dimension=DATE, date_range=DATES), limit_rows=50001)
    session = await MethodSession.fixture(FixtureProvider(fixture_provider().catalog,
        [QueryFixture(spec, [[30, "A"], [20, "B"], [20, "C"]])]))
    session.register(registered_method())
    return session
