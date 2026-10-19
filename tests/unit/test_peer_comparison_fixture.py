from decision_layer.dev import MethodSession
from decision_layer.methods import Scope
from decision_layer.methods.peer_comparison import PeerComparison
from decision_layer.semantic.credentials import AnonymousServiceCredentials
from tests.support.methods.peer_data import (
    fixture_provider,
    BINDINGS,
    PARAMS,
    DATE,
    DATES,
)


async def test_peer_comparison():
    provider = fixture_provider()
    session = await MethodSession.connect(provider, AnonymousServiceCredentials())
    session.register(PeerComparison())
    trial = await session.run(
        "query.peer_comparison",
        bindings=BINDINGS,
        params=PARAMS,
        scope=Scope(date_range=DATES, time_dimension=DATE),
    )
    assert trial.result.status == "success"
    assert [
        row["difference_from_subject"] for row in trial.result.primary.data["rows"]
    ] == [0, 4, 6]
    assert len(trial.attempts) == 3
    provider.assert_consumed()
