import pytest
from decision_layer.core.models import (DatasetSpec,TimeScope,PlanStep,Recipe,SemanticScope,CallerInfo,Filter)
from decision_layer.methods import registry, InvalidBinding
from decision_layer.recipes.loader import RecipeStore
from decision_layer.runs.engine import RunEngine, RunBusy
from decision_layer.runs.store import MemoryRunStore, UnknownRun
from decision_layer.runs.skills import SkillQueryRequest, SkillFinishRequest, SkillSelection
from decision_layer.semantic.credentials import AnonymousServiceCredentials
from decision_layer.testing import FixtureProvider, QueryFixture
from examples.methods.first_method.fixtures import METRIC,DIMENSION,DATE,DATES,fixture_provider

CREDS=AnonymousServiceCredentials()
ME=CallerInfo(subject='alice')
SCOPE={'date_range':list(DATES),'time_dimension':DATE}
SPEC=DatasetSpec(grain='aggregate',measures=[METRIC],dimensions=[DIMENSION],
                time=TimeScope(dimension=DATE,date_range=DATES),limit_rows=100)


def engine(tmp_path):
    provider=FixtureProvider(fixture_provider().catalog,[QueryFixture(SPEC,[[30,'A'],[20,'B']])])
    return RunEngine(provider,RecipeStore(tmp_path,'cube','fixture'),MemoryRunStore())


async def start(e):
    run=await e.start(CREDS,ME,recipe=None,question='Inspect groups',scope=SCOPE)
    run,result=await e.step(CREDS,ME,run.id,PlanStep(id='split',method='analysis.drilldown',bindings={'metric':METRIC,'dimensions':[DIMENSION]}))
    assert result.status=='needs_input' and result.needs_input['reason_code']=='AGENT_EXECUTION_REQUIRED'
    return run


async def test_skill_query_logs_exports_and_closes_without_invented_values(tmp_path):
    e=engine(tmp_path);run=await start(e)
    assert run.active_skill_step=='split' and run.steps[0].skill.guide.sha256
    assert not run.steps[0].result.validation
    req=SkillQueryRequest(id='groups',purpose='Inspect observed groups',spec=SPEC)
    run,q=await e.skill_query(CREDS,ME,run.id,'split',req)
    assert q.status=='success' and q.result.primary.data[0][DIMENSION]=='A'
    _,duplicate=await e.skill_query(CREDS,ME,run.id,'split',req)
    assert duplicate==q and len(e.provider.calls)==1
    with pytest.raises(InvalidBinding):
        await e.finish_skill(CREDS,ME,run.id,'split',SkillFinishRequest(reason='inspect',selection=SkillSelection(query_id='groups',row=99,dimension=DIMENSION,reason='invented')))
    run=await e.finish_skill(CREDS,ME,run.id,'split',SkillFinishRequest(reason='Inspect A',selection=SkillSelection(query_id='groups',row=0,dimension=DIMENSION,reason='largest returned value')))
    result=run.steps[0].result
    assert result.status=='success' and len(result.provenance.queries)==1
    selection=result.selections['selected_group']
    assert selection.kind=='selected_group' and selection.candidates[0].path[-1].value=='A'
    assert selection.evidence['filters'][-1]['values']==['A']
    assert not run.active_skill_step and not result.provides
    assert (await e.complete(ME,run.id,summary='Observed groups')).status=='completed'
    e.jobs.shutdown()


async def test_pending_skill_blocks_other_steps_completion_and_shared_mutation(tmp_path):
    e=engine(tmp_path);run=await start(e)
    with pytest.raises(RunBusy):await e.complete(ME,run.id,summary='pretend done')
    with pytest.raises(RunBusy):await e.step(CREDS,ME,run.id,PlanStep(method='query.aggregate',bindings={'metric':METRIC}))
    with pytest.raises(UnknownRun):await e.skill_query(CREDS,CallerInfo(subject='bob'),run.id,'split',SkillQueryRequest(id='q',purpose='q',spec=SPEC))
    with pytest.raises(InvalidBinding):await e.finish_skill(CREDS,ME,run.id,'split',SkillFinishRequest(reason='No evidence'))
    run=await e.finish_skill(CREDS,ME,run.id,'split',SkillFinishRequest(status='refused',reason='Data not available'))
    assert run.steps[0].result.status=='refused'
    e.jobs.shutdown()


async def test_invalid_period_is_logged_without_query_and_can_be_recovered(tmp_path):
    e=engine(tmp_path);run=await start(e)
    invalid=SPEC.model_copy(update={'time':TimeScope(dimension=DATE,date_range=('2025-01-01','2025-01-31'))})
    run,q=await e.skill_query(CREDS,ME,run.id,'split',SkillQueryRequest(id='wrong_period',purpose='Bad dates',spec=invalid))
    assert q.status=='failed' and q.error['code']=='INVALID_BINDING' and not e.provider.calls
    run,q=await e.skill_query(CREDS,ME,run.id,'split',SkillQueryRequest(id='corrected',purpose='Right dates',spec=SPEC))
    assert q.status=='success' and len(run.steps[0].skill.queries)==2
    e.jobs.shutdown()


async def test_mixed_pipeline_pauses_then_resumes_and_retains_selection(tmp_path):
    e=engine(tmp_path)
    from examples.methods.authoring.plain_python import rank_groups
    from decision_layer.methods import python_method,DataInput
    own=registry.copy()
    own.register(python_method(rank_groups,name='test.rank',version='1.0.0',inputs={'data':DataInput(measures=['value'],dimensions=['group'],filters_parameter='selected_filters')}))
    e.registry=own;e.recipes.registry=own
    filtered=DatasetSpec(grain='aggregate',measures=[METRIC],dimensions=[DIMENSION],time=SPEC.time,
        filters=[Filter(member=DIMENSION,operator='equals',values=['A'])],limit_rows=50001)
    e.provider=FixtureProvider(fixture_provider().catalog,[QueryFixture(SPEC,[[30,'A'],[20,'B']]),QueryFixture(filtered,[[30,'A']])])
    recipe=Recipe(name='mixed',version='1.0.0',description='Skill followed by Python',mode='pipeline',semantic_scope=SemanticScope(primary_metric=METRIC),steps=[
        PlanStep(id='split',method='analysis.drilldown',bindings={'metric':METRIC,'dimensions':[DIMENSION]}),
        PlanStep(id='python',method='test.rank',bindings={'value':METRIC,'group':DIMENSION},params={'selected_filters':'$steps.split.selections.selected_group.evidence.filters'})])
    e.recipes.save(recipe,None)
    run=await e.start(CREDS,ME,recipe='mixed',question='Inspect then calculate',scope=SCOPE)
    assert len(run.steps)==1 and run.active_skill_step=='split'
    await e.skill_query(CREDS,ME,run.id,'split',SkillQueryRequest(id='groups',purpose='Read groups',spec=SPEC))
    run=await e.finish_skill(CREDS,ME,run.id,'split',SkillFinishRequest(reason='Choose A',selection=SkillSelection(query_id='groups',row=0,dimension=DIMENSION,reason='Largest returned value')))
    assert run.status=='completed' and len(run.steps)==2
    assert run.steps[1].result.status=='success' and run.steps[1].result.primary.data[0]['rank']==1
    assert run.steps[1].step.params['selected_filters'][0]['values']==['A']
    assert len(run.query_attempts)==2
    e.jobs.shutdown()


async def test_skill_snapshot_and_inherited_filters_survive_restart(tmp_path):
    from decision_layer.runs.store import SqliteRunStore
    e=engine(tmp_path)
    e.store=SqliteRunStore(str(tmp_path/'runs.db'))
    run=await e.start(CREDS,ME,recipe=None,question='Inspect subset',scope=SCOPE)
    inherited=Filter(member=DIMENSION,operator='notEquals',values=['X'])
    run,_result=await e.step(CREDS,ME,run.id,PlanStep(id='split',method='analysis.drilldown',bindings={'metric':METRIC},params={'filters':[inherited.model_dump()]}))
    _,q=await e.skill_query(CREDS,ME,run.id,'split',SkillQueryRequest(id='omitted',purpose='Bad scope',spec=SPEC))
    assert q.status=='failed' and not e.provider.calls
    frozen=run.steps[0].skill.guide.sha256
    reloaded=await e.store.get(run.id)
    assert reloaded.active_skill_step=='split' and reloaded.steps[0].skill.guide.sha256==frozen
    assert reloaded.steps[0].skill.queries[0].error
    e.jobs.shutdown()


async def test_skill_query_api_is_canonical_and_attributes_mcp_author(provider, tmp_path):
    from fastapi.testclient import TestClient
    from decision_layer.api.app import create_app
    from decision_layer.settings import Settings
    from tests.support.runs import SCOPE as API_SCOPE
    from tests.support.semantic import RR, CAT
    settings=Settings(database_url='memory',allow_service_credentials=True,cube_api_secret='test-secret-at-least-32-characters',cube_service_groups=('ecommerce',))
    with TestClient(create_app(settings,provider)) as client:
        run=client.post('/runs',json={'question':'Inspect', 'scope':API_SCOPE}).json()
        start=client.post(f"/runs/{run['id']}/steps",json={'id':'split','method':'analysis.drilldown','bindings':{'metric':RR,'dimensions':[CAT]}})
        assert start.status_code==200 and start.json()['needs_input']['reason_code']=='AGENT_EXECUTION_REQUIRED'
        saved=client.get(f"/runs/{run['id']}").json()
        period=saved['plan']['scope']
        query=client.post(f"/runs/{run['id']}/steps/split/queries",json={'id':'read','purpose':'Inspect','author':{'client_name':'test-agent'},
            'spec':{'grain':'aggregate','measures':[RR],'dimensions':[CAT],'time':{'dimension':period['time_dimension'],'date_range':period['date_range']},'limit_rows':10}})
        assert query.status_code==200 and query.json()['status']=='success',query.text
        assert query.json()['author']['client_name']=='test-agent'
        finished=client.post(f"/runs/{run['id']}/steps/split:finish",json={'reason':'Observed groups'})
        assert finished.status_code==200 and finished.json()['steps'][0]['result']['status']=='success'
