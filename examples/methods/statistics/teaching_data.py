"""Small fixed data helpers used by the first-Method notebooks."""
from dataclasses import replace

import pandas as pd

from decision_layer.core.models import DatasetSpec, TimeScope
from decision_layer.dev import MethodSession
from decision_layer.testing import FixtureProvider, QueryFixture
from examples.methods.scenarios.scenarios import BEFORE, DATE, FEB, GROUP, M, SUBJECT, catalog, scenarios


def _example(name):
    available = {case.name: case for case in scenarios()}
    # An open notebook may still have the previous scenario name in memory.
    previous_name = {"by_group": "drilldown", "drilldown": "by_group"}.get(name)
    case = available.get(name) or available.get(previous_name)
    if case is None:
        raise ValueError(
            f"Unknown practice example {name!r}. Choose: {', '.join(available)}"
        )
    return case


async def example_session(name):
    """Create a local session that returns fixed data for a named example."""
    if name == "multi_group":
        spec = DatasetSpec(grain="aggregate", measures=[M, BEFORE], dimensions=[GROUP, SUBJECT],
            time=TimeScope(dimension=DATE, date_range=FEB), order=[(M, "desc")], limit_rows=3)
        rows = [[30, 25, "A", "X"], [20, 15, "B", "Y"], [10, 5, "C", "Z"]]
        return await MethodSession.fixture(FixtureProvider(catalog(), [QueryFixture(spec, rows)]))
    return await MethodSession.fixture(_example(name).provider())


def binary_regression_frame():
    query = _example("dowhy").queries[0]
    return pd.DataFrame(query.rows, columns=["outcome", "treatment", "baseline", "unit"])


async def duplicate_unit_session():
    """Create the binary-regression example with one duplicated unit."""
    query = _example("dowhy").queries[0]
    rows = [list(row) for row in query.rows]
    rows[1][-1] = rows[0][-1]
    provider = FixtureProvider(catalog(), [replace(query, rows=rows)])
    return await MethodSession.fixture(provider)
