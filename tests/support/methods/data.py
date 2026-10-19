"""Fixed observations shared by Method runtime tests."""

import pandas as pd

from decision_layer.dev import MethodSession
from tests.support.methods.cases import scenarios


def _example(name):
    available = {case.name: case for case in scenarios()}
    case = available.get(name)
    if case is None:
        raise ValueError(
            f"Unknown practice example {name!r}. Choose: {', '.join(available)}"
        )
    return case


async def example_session(name):
    """Create a local session that returns fixed data for a named example."""
    return await MethodSession.fixture(_example(name).provider())


def binary_regression_frame():
    query = _example("dowhy").queries[0]
    return pd.DataFrame(
        query.rows, columns=["outcome", "treatment", "baseline", "unit"]
    )
