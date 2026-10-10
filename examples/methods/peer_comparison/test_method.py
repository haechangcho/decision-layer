from pathlib import Path
from decision_layer.dev import MethodSession
from decision_layer.methods import Scope
from decision_layer.methods.peer_comparison import PeerComparison
from decision_layer.semantic.credentials import AnonymousServiceCredentials
from tests.support.notebooks import execute_notebook
from .fixtures import fixture_provider, BINDINGS, PARAMS, DATE, DATES


async def test_peer_comparison():
    provider = fixture_provider()
    session = await MethodSession.connect(provider, AnonymousServiceCredentials())
    session.register(PeerComparison())
    trial = await session.run("query.peer_comparison", bindings=BINDINGS, params=PARAMS,
                              scope=Scope(date_range=DATES, time_dimension=DATE))
    assert trial.result.status == "success"
    assert [row["difference_from_subject"] for row in trial.result.primary.data["rows"]] == [0, 4, 6]
    assert len(trial.attempts) == 3
    provider.assert_consumed()


async def test_fixture_notebook_runs_all_cells(monkeypatch):
    path = Path(__file__).with_name("explore.ipynb")
    namespace = await execute_notebook(path, monkeypatch)
    assert len(namespace["trial"].attempts) == 3
    assert namespace["run"].steps[0].result.status == "success"
