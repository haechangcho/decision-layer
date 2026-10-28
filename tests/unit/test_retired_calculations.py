from decision_layer.methods import registry
from decision_layer.methods.loading import configured_registry
from decision_layer.settings import Settings


RETIRED = {'stats.period_change', 'stats.series_diagnostics', 'example.household_regression'}


def test_configured_catalog_retires_calculations_without_losing_pins():
    own = configured_registry(Settings(method_modules=('examples.recipes.skill_chain',)))
    assert RETIRED.isdisjoint(m.name for m in own.manifests())
    for name in RETIRED:
        assert own.get(name, '1.0.0')
    assert own.get('stats.series_diagnostics', '1.1.0')
    for manifest in own.manifests():
        if manifest.implementation == 'skill':
            text = own.get(manifest.name).source_text
            assert not any(name in text for name in RETIRED)
    assert own.get('analysis.drilldown', '1.0.1').guide.version == '1.0.1'
    assert own.get('analysis.trend', '1.0.0').guide.version == '1.0.0'
    assert own.get('analysis.drilldown').guide.version == '2.2.0'
    assert own.get('analysis.drilldown', '1.1.0').guide.version == '1.1.0'


async def test_managed_retired_calculation_stays_hidden_after_publish_and_restart(tmp_path):
    from decision_layer.methods.assets import MethodAssets, DraftRequest, RevisionRequest
    own = configured_registry(Settings(method_modules=('examples.recipes.skill_chain',)))
    store = MethodAssets(tmp_path, own)
    name = 'example.household_regression'
    content = '''from examples.recipes.skill_chain import COMPATIBILITY_METHODS
from copy import copy
METHODS = [copy(method) for method in COMPATIBILITY_METHODS]
'''
    draft = store.save(name, DraftRequest(base_version='1.0.0', version='1.0.1', content=content), 'test')
    checked = await store.check(name, draft['revision'])
    assert checked['validation']['status'] == 'pass'
    store.publish(name, RevisionRequest(revision=draft['revision'], reviewed=True), 'test')
    assert name not in {m.name for m in own.manifests()}
    fresh = configured_registry(Settings(method_modules=('examples.recipes.skill_chain',)))
    MethodAssets(tmp_path, fresh)
    assert name not in {m.name for m in fresh.manifests()}
    assert fresh.get(name, '1.0.0') and fresh.get(name, '1.0.1')


async def test_current_campaign_recipe_finishes_without_retired_python():
    from examples.recipes.skill_chain import campaign_recipe, legacy_campaign_recipe
    from examples.recipes.skill_chain_demo import demonstrate
    assert RETIRED.isdisjoint(s.method for s in campaign_recipe().steps)
    assert legacy_campaign_recipe().steps[-1].method == 'example.household_regression'
    run = await demonstrate()
    assert run.status == 'completed'
    assert [s.step.method for s in run.steps] == ['analysis.drilldown', 'analysis.peer_comparison']
    assert len(run.query_attempts) == 3
    assert all(step.skill for step in run.steps)
