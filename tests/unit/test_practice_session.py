"""Interactive examples stay repeatable without relaxing strict query fixtures."""
import pytest

from decision_layer.methods import Scope
from examples.methods.authoring.sample_data import DATE, DATES, DIMENSION, METRIC
from examples.methods.authoring.plain_python import METHODS, practice_session


async def test_practice_queries_repeat_after_comparison_and_option_changes():
    session = await practice_session()
    assert session.list_methods() == []
    for method in METHODS[:2]:
        session.register(method)
    inputs = dict(value=METRIC, group=DIMENSION, scope=Scope(DATES, DATE))
    first = await session.run('workshop.rank', **inputs)
    comparison = await session.run('workshop.compare', baseline=['2026-08-01', '2026-08-31'], **inputs)
    again = await session.run('workshop.rank', **inputs)
    ascending = await session.run('workshop.rank', descending=False, **inputs)
    assert first.result.primary.data == again.result.primary.data
    assert [row['rank'] for row in ascending.result.primary.data] == [3, 1, 1]
    assert [row['change'] for row in comparison.result.primary.data] == [20, -5, 0]
    assert len(session.provider.calls) == 5


async def test_practice_still_rejects_queries_without_exact_fixture():
    session = await practice_session()
    assert session.list_methods() == []
    for method in METHODS[:2]:
        session.register(method)
    with pytest.raises(AssertionError, match='Unexpected practice query'):
        await session.run('workshop.rank', value=METRIC, group=DIMENSION,
                          scope=Scope(('2026-07-01', '2026-07-31'), DATE))
