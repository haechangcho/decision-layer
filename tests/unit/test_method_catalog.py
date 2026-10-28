"""List installed contracts; enforce requirements when the selected Method executes."""

import pytest
from fastapi.testclient import TestClient

from decision_layer.core.errors import UnknownSemanticObject
from decision_layer.dev import MethodSession
from decision_layer.methods import (
    DataInput,
    Measure,
    Scope,
    Table,
    method,
    python_method,
    register_builtins,
)
from decision_layer.testing import FixtureProvider
from examples.methods.authoring.sample_data import (
    fixture_provider,
    METRIC,
    DIMENSION,
    DATE,
    DATES,
)


async def test_listing_preserves_descriptions_without_querying():
    from tests.unit.test_method_authoring import grouped

    session = await MethodSession.fixture(fixture_provider())
    session.register(grouped)
    manifests = session.list_methods()
    assert [item.name for item in manifests] == [grouped.manifest.name]
    assert manifests[0].description == grouped.__doc__
    assert manifests[0].roles["metric"].required
    assert not session.provider.calls
    assert not hasattr(session, "find_methods")


def test_api_lists_and_describes_methods_without_a_source_query(
    cube_meta, tmp_path, monkeypatch
):
    from decision_layer.api.app import create_app
    from decision_layer.settings import Settings
    from tests.support.semantic import FakeProvider

    provider = FakeProvider(cube_meta)

    async def unavailable(*args, **kwargs):
        raise AssertionError("Listing should not discover or query the semantic source")

    monkeypatch.setattr(provider, "discover", unavailable)
    app = create_app(
        Settings(database_url="memory", recipes_dir=str(tmp_path)), provider
    )
    with TestClient(app) as client:
        response = client.get("/methods")
        assert response.status_code == 200
        listed = response.json()
        assert listed
        detail = client.get(f"/methods/{listed[0]['name']}")
        assert detail.status_code == 200
        assert detail.json() == listed[0]
        assert client.post("/methods:search", json={}).status_code == 404
    assert provider.calls == 0


@pytest.mark.parametrize("requirement", ["package", "provider"])
async def test_listed_method_still_refuses_missing_requirements_before_query(
    requirement, monkeypatch
):
    def calculate(data):
        raise AssertionError("Unavailable Method must not reach calculation")

    provider = FixtureProvider(fixture_provider().catalog, [])
    if requirement == "provider":
        capabilities = provider.capabilities().model_copy(
            update={"aggregate_queries": False}
        )
        monkeypatch.setattr(provider, "capabilities", lambda: capabilities)
    registered = python_method(
        calculate,
        name="test.requirements",
        version="1.0.0",
        inputs={"data": DataInput(measures=["value"], format="records")},
        requires_packages={"decision-layer-nonexistent-test-package": ">=1"}
        if requirement == "package"
        else {},
    )
    session = await MethodSession.fixture(provider)
    session.register(registered)
    assert [m.name for m in session.list_methods()] == [registered.manifest.name]
    trial = await session.run(registered, value=METRIC, scope=Scope(DATES, DATE))
    assert trial.result.status == "refused"
    assert trial.result.primary is None
    assert trial.result.warnings
    assert provider.calls == []


@pytest.mark.parametrize(
    "provides", ["metric_lookup", [""], ["metric lookup"], ["a", "a"]]
)
def test_ambiguous_capability_declarations_fail_early(provides):
    with pytest.raises(ValueError, match="provides"):

        @method(
            "test.bad", version="1.0.0", interpretation="association", provides=provides
        )
        async def bad(ctx) -> Table:
            return Table([])


def test_invalid_dependency_and_ambiguous_optional_type_fail_early():
    with pytest.raises(ValueError):

        @method(
            "test.bad",
            version="1.0.0",
            interpretation="association",
            requires_packages={"pandas": "=>2"},
        )
        async def bad(ctx) -> Table:
            return Table([])

    with pytest.raises(ValueError, match="one non-null"):

        @method("test.bad", version="1.0.0", interpretation="association")
        async def bad_union(ctx, *, value: str | int | None = None) -> Table:
            return Table([])


async def test_private_input_is_also_refused_at_execution_without_queries():
    from examples.methods.authoring.sample_data import DATE, DATES
    from decision_layer.methods import Scope
    from tests.unit.test_method_authoring import grouped

    session = await MethodSession.fixture(fixture_provider())
    session.register(grouped)
    session.catalog.get(METRIC).public = False
    with pytest.raises(UnknownSemanticObject):
        await session.run(
            grouped, metric=METRIC, group=DIMENSION, scope=Scope(DATES, DATE)
        )
    assert not session.provider.calls


def test_current_builtins_share_exact_project_starters():
    from importlib.resources import files
    from decision_layer.methods import MethodRegistry
    from decision_layer.methods.skills import SkillMethod

    target = register_builtins(MethodRegistry())
    assert len(target.manifests()) == len(target._versions) == 4
    for directory, name in [("metric_lookup", "analysis.metric_lookup"), ("drilldown", "analysis.drilldown")]:
        path = files("decision_layer") / "starters" / "methods" / directory / "SKILL.md"
        starter = SkillMethod.from_file(path)
        current = target.get(name)
        assert current.manifest.version == "2.2.0"
        assert current.source_text == starter.source_text
        assert current.guide.sha256 == starter.guide.sha256
    from decision_layer.starters.methods.ols.method import METHOD as regression
    from decision_layer.starters.methods.matching.method import METHOD as matching
    assert target.get(regression.manifest.name) is regression
    assert target.get(matching.manifest.name) is matching
