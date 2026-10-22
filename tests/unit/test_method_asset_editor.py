import json
import pytest
from fastapi.testclient import TestClient
from decision_layer.api.app import create_app
from decision_layer.settings import Settings
from decision_layer.methods import registry
from tests.support.semantic import RR, Q3, DT


def app(tmp_path, provider, enabled=True):
    settings=Settings(database_url='memory',recipes_dir=str(tmp_path/'recipes'),
        allow_service_credentials=True,cube_api_secret='test-secret-at-least-32-characters',
        cube_service_groups=('ecommerce',),method_assets_dir=str(tmp_path/'assets'),allow_method_editing=enabled)
    return create_app(settings,provider)


def skill_source(client):
    value=client.get('/methods/analysis.drilldown/source').json()
    content=value['content'].replace('version: 2.1.0','version: 2.1.1')+'\n검토한 새 한국어 지침입니다.\n'
    return {'base_version':'2.1.0','version':'2.1.1','content':content,'revision':None}


def test_skill_draft_conflict_review_publication_restart_and_old_versions(tmp_path,provider):
    application=app(tmp_path,provider)
    with TestClient(application) as client:
        req=skill_source(client)
        draft=client.put('/methods/analysis.drilldown/draft',json=req).json()
        assert client.get('/methods/analysis.drilldown').json()['version']=='2.1.0'
        assert client.put('/methods/analysis.drilldown/draft',json=req).status_code==409
        args={'revision':draft['revision'],'reviewed':True}
        assert client.post('/methods/analysis.drilldown/draft:publish',json=args).status_code==400
        check=client.post('/methods/analysis.drilldown/draft:check',json=args)
        assert check.json()['validation']['status']=='pass'
        assert not check.json()['validation']['analytical_quality_verified']
        assert client.post('/methods/analysis.drilldown/draft:publish',json={**args,'reviewed':False}).status_code==400
        assert client.post('/methods/analysis.drilldown/draft:publish',json=args).status_code==200
        assert client.get('/methods/analysis.drilldown').json()['version']=='2.1.1'
        # Old pinned Recipe still resolves; active Skill snapshots survive publication.
        run=client.post('/runs',json={'question':'Old pinned Skill','scope':{'date_range':list(Q3),'time_dimension':DT}}).json()
        result=client.post(f"/runs/{run['id']}/steps",json={'method':'analysis.drilldown','method_version':'1.0.1','bindings':{'metric':RR}})
        assert result.status_code==200 and result.json()['status']=='needs_input'
        recorded=client.get(f"/runs/{run['id']}").json()['steps'][0]
        assert recorded['skill']['guide']['version']=='1.0.1'
    with TestClient(app(tmp_path,provider)) as client:
        assert client.get('/methods/analysis.drilldown').json()['version']=='2.1.1'
        assert client.get('/methods/analysis.drilldown/source').json()['draft'] is None
        assert len(client.get('/methods/analysis.drilldown/source').json()['history'])==1


PYTHON='''from decision_layer.methods import DataInput, python_method

def adjusted(data):
    return data.assign(value=data.value * 2)

METHODS = [python_method(adjusted, name="query.aggregate", version="1.0.0",
    inputs={"data":DataInput(measures=["value"])})]
'''


def test_python_publish_runs_new_code_preserves_pinned_old_and_source(tmp_path,provider):
    with TestClient(app(tmp_path,provider)) as client:
        old=client.get('/methods/query.aggregate/source').json()
        assert old['code']['available'] and 'class Aggregate' in old['code']['files'][0]['content']
        saved=client.put('/methods/query.aggregate/draft',json={'base_version':'1.0.0','version':'1.0.1','content':PYTHON}).json()
        args={'revision':saved['revision'],'reviewed':True}
        assert client.post('/methods/query.aggregate/draft:check',json={**args,'reviewed':False}).status_code==400
        checked=client.post('/methods/query.aggregate/draft:check',json=args)
        assert checked.json()['validation']['status']=='pass',checked.text
        assert client.post('/methods/query.aggregate/draft:publish',json=args).status_code==200
        current=client.get('/methods/query.aggregate/source').json()
        assert current['code']['origin']=='managed' and 'def adjusted' in current['code']['files'][0]['content']
        assert 'version="1.0.1"' in current['code']['authoring_content']
        assert '_dl_registered_method' not in current['content']
        response=client.post('/methods/query.aggregate:run',json={'bindings':{'value':RR},'scope':{'date_range':list(Q3),'time_dimension':DT}})
        assert response.status_code==200 and response.json()['status']=='success',response.text
        record=client.get('/runs/'+response.json()['run_id']).json()['steps'][0]
        assert record['code']['version']=='1.0.1' and record['method'].endswith('@1.0.1')
        source=record['code']['files'][0]['content']
        assert 'data.value * 2' in source and record['result']['primary']['data']
        run=client.post('/runs',json={'question':'Pinned old aggregate','scope':{'date_range':list(Q3),'time_dimension':DT}}).json()
        old_result=client.post('/runs/'+run['id']+'/steps',json={'method':'query.aggregate','method_version':'1.0.0','bindings':{'metric':RR}})
        assert old_result.status_code==200 and old_result.json()['provenance']['method'].endswith('@1.0.0')
        assert response.json()['primary']['data'][0]['value'] == pytest.approx(2 * old_result.json()['primary']['data'][0][RR])
    with TestClient(app(tmp_path,provider)) as client:
        assert client.get('/methods/query.aggregate').json()['version']=='1.0.1'
        assert client.get('/methods/query.aggregate?version=1.0.0').json()['roles'].get('metric')


def test_editing_disabled_and_invalid_python_not_published(tmp_path,provider):
    with TestClient(app(tmp_path,provider,enabled=False)) as client:
        assert not client.get('/methods/query.aggregate/source').json()['permissions']['edit']
        assert client.put('/methods/query.aggregate/draft',json={'base_version':'1.0.0','version':'1.0.1','content':PYTHON}).status_code==400
    with TestClient(app(tmp_path,provider)) as client:
        saved=client.put('/methods/query.aggregate/draft',json={'base_version':'1.0.0','version':'1.0.1','content':'def bad('}).json()
        req={'revision':saved['revision'],'reviewed':True}
        checked=client.post('/methods/query.aggregate/draft:check',json=req).json()
        assert checked['validation']['status']=='fail'
        assert client.post('/methods/query.aggregate/draft:publish',json=req).status_code==400
        assert client.get('/methods/query.aggregate').json()['version']=='1.0.0'


def test_recipe_publisher_does_not_gain_python_publication_permission():
    from decision_layer.api.dependencies import require_method_permission,MethodPermissionRequired
    from decision_layer.core.models import CallerInfo
    settings=Settings(recipe_publishers=('alice',),method_editors=('editor',),method_publishers=('operator',))
    with pytest.raises(MethodPermissionRequired):require_method_permission(settings,CallerInfo(subject='alice'),publish=True)
    require_method_permission(settings,CallerInfo(subject='editor'))
    with pytest.raises(MethodPermissionRequired):require_method_permission(settings,CallerInfo(subject='editor'),publish=True)
    require_method_permission(settings,CallerInfo(subject='operator'),publish=True)


async def test_python_import_timeout_keeps_current_version(tmp_path):
    from decision_layer.methods.assets import MethodAssets,DraftRequest
    own=registry.copy();store=MethodAssets(tmp_path/'slow',own)
    draft=store.save('query.aggregate',DraftRequest(base_version='1.0.0',version='1.0.1',content='while True:\n    pass\n'), 'operator')
    result=await store.check('query.aggregate',draft['revision'])
    assert result['validation']['status']=='fail' and '15 second' in result['validation']['message']
    assert own.get('query.aggregate').manifest.version=='1.0.0' and not store.history()


def test_installed_and_managed_same_version_collision_is_not_silently_replaced(tmp_path,provider):
    from decision_layer.methods.assets import MethodAssets,AssetConflict
    from decision_layer.methods.skills import SkillMethod
    with TestClient(app(tmp_path,provider)) as client:
        req=skill_source(client)
        draft=client.put('/methods/analysis.drilldown/draft',json=req).json()
        args={'revision':draft['revision'],'reviewed':True}
        client.post('/methods/analysis.drilldown/draft:check',json=args)
        assert client.post('/methods/analysis.drilldown/draft:publish',json=args).status_code==200
    upgraded=registry.copy()
    upgraded.register(SkillMethod(req['content'].replace('검토한 새 한국어 지침입니다.','패키지에서 별도로 변경했습니다.')))
    with pytest.raises(AssetConflict):MethodAssets(tmp_path/'assets',upgraded)


def test_historical_uninstalled_recipe_pin_does_not_block_storage_startup(tmp_path):
    import yaml
    from decision_layer.recipes.loader import RecipeStore
    from decision_layer.core.models import Recipe,SemanticScope,PlanStep
    from decision_layer.methods import InvalidBinding
    recipe=Recipe(name='historical',version='1.0.0',description='Archived procedure',mode='pipeline',
        semantic_scope=SemanticScope(primary_metric=RR),steps=[PlanStep(method='query.aggregate',method_version='0.0.0',bindings={'metric':RR})])
    (tmp_path/'historical@1.0.0.yaml').write_text(yaml.safe_dump(recipe.model_dump(mode='json')))
    store=RecipeStore(tmp_path,'cube','local')
    assert store.get('historical').steps[0].method_version=='0.0.0'
    with pytest.raises(InvalidBinding):registry.get('query.aggregate','0.0.0')
