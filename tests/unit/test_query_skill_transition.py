import pytest
from decision_layer.methods import registry
from decision_layer.core.models import Filter
from tests.support.semantic import RR, AMOUNT, CAT, Q2, ctx


def test_query_skills_replace_default_python_lookup_and_trend():
    names = {m.name for m in registry.manifests()}
    assert names == {'analysis.metric_lookup', 'analysis.drilldown',
                     'stats.regression_adjustment', 'stats.binary_matching'}
    assert {'query.aggregate','query.trend','stats.period_change','stats.series_diagnostics'}.isdisjoint(names)
    for name in ['query.aggregate','query.trend']:
        assert registry.get(name).manifest.version == '1.0.0'
    for name in ['analysis.metric_lookup','analysis.trend','analysis.drilldown','analysis.peer_comparison']:
        skill = registry.get(name)
        assert skill.manifest.agent_executable and not skill.manifest.provides
        assert any('가' <= char <= '힣' for char in skill.guide.markdown)


async def test_period_calculation_matches_legacy_trend_and_checks(provider):
    old = await registry.run('query.trend',ctx(provider),{'metric':AMOUNT},{'comparison':list(Q2)})
    new = await registry.run('stats.period_change',ctx(provider),{'metric':AMOUNT},{'comparison':list(Q2)})
    assert new.status == 'success'
    assert new.primary.data == next(a.data for a in old.artifacts if a.type == 'estimate')
    factors = new.primary.data['decomposition']['decompositions'][0]['factors']
    assert sum(f['contribution'] for f in factors) == pytest.approx(new.primary.data['change'],abs=.02)
    assert {'complete_period','comparable_periods','freshness'} <= {v.validator for v in new.validation}


async def test_series_diagnostics_retains_selected_population(provider):
    execution = ctx(provider)
    result = await registry.run('stats.series_diagnostics',execution,{'metric':RR},
        {'filters':[Filter(member=CAT,operator='equals',values=['A']).model_dump()]})
    assert result.status == 'success'
    assert result.provides == ['time_series']
    assert result.provenance.queries
    assert execution.attempts
    assert all(Filter(member=CAT,operator='equals',values=['A']) in attempt.spec.filters for attempt in execution.attempts)
    assert {'complete_period','freshness'} <= {v.validator for v in result.validation}


def test_adjacent_change_preserves_ties_and_missing_values():
    from decision_layer.methods.time_analysis import largest_moves
    rows=[{'period':'a','x':1},{'period':'b','x':3},{'period':'c','x':1},{'period':'d','x':None}]
    result=largest_moves(rows,['x'])
    assert [(r['from'],r['to'],r['change']) for r in result] == [('a','b',2),('b','c',-2)]
