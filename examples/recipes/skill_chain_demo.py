"""Deterministic client replay for the notebook; not a live Claude evaluation."""
async def demonstrate():
    from decision_layer.core.models import DatasetSpec,TimeScope,Filter,SemanticCatalog,SemanticObject,CallerInfo
    from decision_layer.methods import registry
    from decision_layer.recipes.loader import RecipeStore
    from decision_layer.runs.engine import RunEngine
    from decision_layer.runs.store import MemoryRunStore
    from decision_layer.runs.skills import SkillQueryRequest,SkillFinishRequest,SkillSelection
    from decision_layer.semantic.credentials import AnonymousServiceCredentials
    from decision_layer.testing import FixtureProvider,QueryFixture
    from examples.recipes.skill_chain import campaign_recipe
    import tempfile
    ref=lambda name:f'cube://fixture/campaign_household_outcomes/{name}'
    metric,campaign,time,unit=map(ref,['post_sales_mean','campaign_id','campaign_start_date','observation_id'])
    before,frequency=ref('pre_sales_mean'),ref('pre_frequency_mean')
    dates=('2001-01-01','2001-12-31')
    dimensions=[campaign,time,unit]
    catalog=SemanticCatalog(provider='cube',instance='fixture',objects=[
        *[SemanticObject(ref=m,kind='measure',data_type='number',title=m,metric_kind='average',entity=unit,dimension_refs=dimensions,time_dimension=time) for m in [metric,before,frequency]],
        SemanticObject(ref=campaign,kind='dimension',data_type='string',title='Campaign'),
        SemanticObject(ref=unit,kind='dimension',data_type='string',title='Observation'),
        SemanticObject(ref=time,kind='time_dimension',data_type='time',title='Campaign start'),
    ])
    grouped=DatasetSpec(grain='aggregate',measures=[metric],dimensions=[campaign],time=TimeScope(dimension=time,date_range=dates),order=[(metric,'desc')],limit_rows=100)
    subject=grouped.model_copy(update={'filters':[Filter(member=campaign,operator='equals',values=['A'])]})
    peers=grouped.model_copy(update={'filters':[Filter(member=campaign,operator='notEquals',values=['A'])]})
    provider=FixtureProvider(catalog,[QueryFixture(grouped,[[250,'A'],[150,'B']]),QueryFixture(subject,[[250,'A']]),QueryFixture(peers,[[150,'B']])])
    assets=registry.copy()
    with tempfile.TemporaryDirectory() as directory:
        recipes=RecipeStore(directory,'cube','fixture',registry=assets)
        recipes.save(campaign_recipe('fixture'),None)
        engine=RunEngine(provider,recipes,MemoryRunStore(),registry=assets)
        creds,caller=AnonymousServiceCredentials(),CallerInfo(subject='notebook')
        try:
            run=await engine.start(creds,caller,recipe='campaign-skill-investigation',question='Inspect campaign differences and peer evidence',scope={'date_range':list(dates),'time_dimension':time})
            assert run.active_skill_step=='campaigns'
            await engine.skill_query(creds,caller,run.id,'campaigns',SkillQueryRequest(id='by_campaign',purpose='Read campaign means',spec=grouped))
            run=await engine.finish_skill(creds,caller,run.id,'campaigns',SkillFinishRequest(reason='Inspect observed campaign A',selection=SkillSelection(query_id='by_campaign',row=0,dimension=campaign,reason='Largest returned campaign mean')))
            assert run.active_skill_step=='peers'
            await engine.skill_query(creds,caller,run.id,'peers',SkillQueryRequest(id='subject',purpose='Read selected campaign A',spec=subject))
            await engine.skill_query(creds,caller,run.id,'peers',SkillQueryRequest(id='peers',purpose='Read accessible campaigns excluding A',spec=peers))
            run=await engine.finish_skill(creds,caller,run.id,'peers',SkillFinishRequest(reason='Record the observed peer campaign B',selection=SkillSelection(query_id='peers',row=0,dimension=campaign,reason='Observed peer campaign B')))
            assert run.steps[-1].result.status=='success'
            assert len(run.steps) == 2
            provider.assert_consumed()
            return run
        finally:
            engine.jobs.shutdown()


if __name__ == "__main__":
    import asyncio

    run = asyncio.run(demonstrate())
    for step in run.steps:
        print(step.step.id, step.result.status)
