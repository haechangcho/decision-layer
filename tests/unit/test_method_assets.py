from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from decision_layer.api.app import create_app
from decision_layer.dev import MethodSession
from decision_layer.methods import DataInput, InvalidBinding, Scope, python_method, registry, SkillMethod
from decision_layer.methods.loading import configured_registry
from decision_layer.settings import Settings
from decision_layer.core.models import DatasetSpec, TimeScope
from decision_layer.testing import FixtureProvider, QueryFixture
from examples.methods.first_method.fixtures import METRIC, DIMENSION, DATE, DATES, fixture_provider
from examples.methods.authoring.plain_python import METHODS, rank_groups
from tests.support.runs import SCOPE

BASELINE = ("2026-08-01", "2026-08-31")


def data_provider(rows=None, prior=None):
    def spec(dates):
        return DatasetSpec(grain="aggregate", measures=[METRIC], dimensions=[DIMENSION],
            time=TimeScope(dimension=DATE, date_range=dates), limit_rows=50001)
    return FixtureProvider(fixture_provider().catalog, [
        QueryFixture(spec(DATES), rows if rows is not None else [[30, "A"], [20, "B"], [20, "C"]]),
        QueryFixture(spec(BASELINE), prior if prior is not None else [[10, "A"], [25, "B"], [20, "C"]])])


async def trial(method, provider=None, **params):
    session = await MethodSession.fixture(provider or data_provider())
    session.register(method)
    return (await session.run(method, value=METRIC, group=DIMENSION, scope=Scope(DATES, DATE), **params)).result


async def test_plain_function_matches_direct_pandas_and_records_implementation():
    import pandas as pd
    result = await trial(METHODS[0])
    assert result.status == "success"
    assert result.primary.data == rank_groups(pd.DataFrame({"value": [30,20,20], "group": ["A","B","C"]})).to_dict(orient="records")
    assert result.provenance.runtime['python.function_sha256'] != 'unavailable'
    assert result.provenance.queries and all(v.status == "pass" for v in result.validation)
    assert result.interpretation == "association"


async def test_multiple_inputs_use_explicit_periods_and_executable_cross_input_check():
    result = await trial(METHODS[1], baseline=BASELINE)
    assert [row['change'] for row in result.primary.data] == [20, -5, 0]
    assert len(result.provenance.queries) == 2
    assert result.validation[-1].code == 'PYTHON_CHECK'
    refused = await trial(METHODS[1], data_provider(prior=[[1,"X"]]), baseline=BASELINE)
    assert refused.status == 'refused' and refused.primary is None
    assert refused.validation[-1].status == 'fail'


@pytest.mark.parametrize('rows,code', [([], 'MINIMUM_ROWS'), ([[None,'A']], 'FINITE_MEASURES'), ([[1,'A'],[2,'A']], 'UNIQUE_GRAIN')])
async def test_bad_data_stops_before_python(rows, code):
    def never(data):
        raise AssertionError('Calculation must not execute')
    result = await trial(python_method(never, name='test.stop', version='1.0.0',
        inputs={'data': DataInput(measures=['value'], dimensions=['group'])}), data_provider(rows))
    assert result.status == 'refused' and result.primary is None
    assert any(v.code == code and v.status == 'fail' for v in result.validation)


async def test_python_runs_in_server_worker():
    import time
    from decision_layer.methods.context import ExecutionContext
    from decision_layer.methods.python import _execute_python
    from decision_layer.core.periods import ExecutionPolicy
    from decision_layer.semantic.credentials import AnonymousServiceCredentials
    async def persist(): pass
    ctx = ExecutionContext(data_provider(), AnonymousServiceCredentials(), data_provider().catalog,
        execution_policy=ExecutionPolicy(), persist_attempts=persist)
    ctx._started = time.monotonic()
    method = METHODS[0]
    out = await ctx.compute(_execute_python, method.fn, {'data':[{'value':3,'group':'A'}]}, method.inputs,
        {'descending':True}, method.checks, method.output, method.adapt)
    assert out.primary.data[0]['rank'] == 1


def test_skill_discovery_snapshots_and_non_execution(provider):
    settings = Settings(database_url='memory', allow_service_credentials=True, cube_api_secret='test-secret-at-least-32-characters', cube_service_groups=('ecommerce',))
    with TestClient(create_app(settings, provider)) as client:
        guide = client.get('/methods/guide.breakdown/guide').json()
        assert guide['enforcement'] == 'advisory' and len(guide['sha256']) == 64
        assert client.get('/method-guides/cube-query').json()['package_version']
        assert client.get('/methods/query.aggregate/guide').status_code == 400
        run = client.post('/runs', json={'question':'Inspect values', 'scope':SCOPE,'guide':'guide.breakdown'}).json()
        assert run['method_guides'] == [guide] and run['steps'] == []
        assert not run['validation']
        refused = client.post(f"/runs/{run['id']}/steps", json={'method':'guide.breakdown'})
        assert refused.status_code == 400
        assert client.get(f"/runs/{run['id']}").json()['steps'] == []
        direct = client.post('/methods/guide.breakdown:run', json={'scope':SCOPE})
        assert direct.status_code == 400


def test_operator_modules_and_skills_are_isolated_and_duplicates_fail(tmp_path):
    text='---\nname: team.lookup\nversion: 1.0.0\ndescription: Read values\nsuggested_methods: [query.aggregate]\n---\nUse the registered tool.\n'
    (tmp_path/'SKILL.md').write_text(text)
    settings=Settings(method_modules=('examples.methods.authoring.plain_python',), skills_dir=str(tmp_path))
    own=configured_registry(settings)
    assert own.get('workshop.rank') and own.get('team.lookup')
    with pytest.raises(InvalidBinding): registry.get('workshop.rank')
    (tmp_path/'duplicate.md').write_text(text)
    with pytest.raises(ValueError, match='Duplicate'): configured_registry(settings)


async def test_mcp_loads_guide_and_forwards_snapshot_selection(monkeypatch):
    from decision_layer.mcp import server
    calls=[]
    async def call(method,path,**kwargs):
        calls.append((path,kwargs))
        return {'implementation':'skill'} if path == '/methods/guide.breakdown' else {'markdown':'guide'}
    monkeypatch.setattr(server, '_call', call)
    monkeypatch.setattr(server, 'METHODS', set())
    assert (await server.describe_method('guide.breakdown'))['guide']['markdown'] == 'guide'
    await server.start_analysis('Question', goals=[], guide='guide.breakdown')
    assert calls[-1][1]['json']['guide'] == 'guide.breakdown'


async def test_existing_dowhy_function_uses_new_adapter_unchanged():
    pytest.importorskip('dowhy')
    from examples.methods.authoring.plain_python import DOWHY_METHOD, adjusted_difference
    from examples.methods.statistics.teaching_data import example_session, binary_regression_frame
    from examples.methods.scenarios.scenarios import M, UNIT, TREAT, BASELINE as COVARIATE, FEB, DATE as TIME
    session = await example_session('dowhy')
    session.register(DOWHY_METHOD)
    result = (await session.run(DOWHY_METHOD, outcome=M, treatment=TREAT, baseline=COVARIATE,
        unit_id=UNIT, scope=Scope(FEB,TIME))).result
    assert result.status == 'success'
    assert result.primary.data['value'] == pytest.approx(adjusted_difference(binary_regression_frame())['value'])
    assert result.primary.data['causal_claim'] == 'not_established'
    assert result.interpretation == 'association'


def test_custom_python_method_api_and_recipe_ownership(provider, tmp_path):
    from tests.support.semantic import RR
    settings=Settings(database_url='memory', allow_service_credentials=True,
        cube_api_secret='test-secret-at-least-32-characters', cube_service_groups=('ecommerce',),
        method_modules=('examples.methods.authoring.plain_python',), recipes_dir=str(tmp_path))
    with TestClient(create_app(settings, provider)) as client:
        assert client.get('/methods/workshop.rank').status_code == 200
        # The native alias 'value' can become a reusable Recipe primary metric.
        from tests.support.semantic import CAT
        run=client.post('/runs',json={'question':'Rank groups','scope':SCOPE}).json()
        response=client.post(f"/runs/{run['id']}/steps",json={
            'method':'workshop.rank','bindings':{'value':RR,'group':CAT}})
        assert response.status_code == 200, response.text
        assert response.json()['status'] == 'success', response.text
        assert client.post(f"/runs/{run['id']}:complete", json={"summary":"Ranked observed groups"}).status_code == 200
        draft=client.post(f"/runs/{run['id']}/recipe",json={})
        assert draft.status_code == 200, draft.text
        assert draft.json()['semantic_scope']['primary_metric'] == RR
        assert client.post('/recipes:validate',json=draft.json()).status_code == 200
        assert client.get(f"/recipes/{draft.json()['name']}/edit").status_code == 200
    with TestClient(create_app(Settings(database_url='memory'), provider)) as other:
        assert other.get('/methods/workshop.rank').status_code == 400



def test_skill_cannot_be_saved_as_executable_recipe():
    from decision_layer.core.models import Recipe, SemanticScope, PlanStep
    from decision_layer.recipes.authoring import validate_recipe, RecipeEditError
    recipe = Recipe(name='test',version='1.0.0',description='test',semantic_scope=SemanticScope(primary_metric=METRIC),
        mode='pipeline', steps=[PlanStep(method='guide.breakdown')])
    with pytest.raises(RecipeEditError, match='advisory'):
        validate_recipe(recipe)


def test_skill_directory_rejects_outside_symlinks_and_non_executable_suggestions(tmp_path):
    from decision_layer.methods.skills import load_skill_directory
    assets=tmp_path/'skills';assets.mkdir()
    external=tmp_path/'outside.md'; external.write_text('outside')
    (assets/'escape.md').symlink_to(external)
    with pytest.raises(ValueError, match='symlinks'):load_skill_directory(registry.copy(),assets)
    (assets/'escape.md').unlink()
    (assets/'skill.md').write_text('---\nname: test.skill\nversion: 1.0.0\ndescription: test\nsuggested_methods: [guide.breakdown]\n---\nInstructions')
    with pytest.raises(ValueError, match='executable'):load_skill_directory(registry.copy(),assets)
