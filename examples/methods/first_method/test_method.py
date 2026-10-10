from pathlib import Path
from decision_layer.dev import MethodSession
from decision_layer.methods import Scope
from decision_layer.semantic.credentials import AnonymousServiceCredentials
from tests.support.notebooks import execute_notebook
from .method import GroupMetric
from .fixtures import fixture_provider, METRIC, DIMENSION, DATE, DATES


async def test_first_method():
    provider = fixture_provider()
    session = await MethodSession.connect(provider, AnonymousServiceCredentials())
    session.register(GroupMetric())
    trial = await session.run("example.group_metric", bindings={"metric": METRIC, "dimension": DIMENSION},
                              params={"limit": 3}, scope=Scope(date_range=DATES, time_dimension=DATE))
    assert trial.result.status == "success"
    assert [row[METRIC] for row in trial.result.primary.data] == [30, 20, 10]
    provider.assert_consumed()
