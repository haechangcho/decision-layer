"""Reproduce ordinary Python -> existing sample Cube -> canonical Run evidence.

Requires the complete-journey Cube/API and CUBE_API_SECRET for its local sample.
Does not publish Methods/Recipes, change semantic definitions or edit saved drafts.
"""
import argparse
import asyncio
import json
import math
import os
from pathlib import Path
import time
import urllib.error
import urllib.request


def call(base, path, body=None):
    request = urllib.request.Request(base + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def saved_run(base, version, bindings, scope):
    result = call(base, '/methods/stats.regression_adjustment:run', {
        'method_version': version, 'question': 'Compare ordinary Python registration with its pinned prior version.',
        'bindings': bindings, 'scope': scope,
        'author': {'client_name': 'Python contract integration trial', 'client_source': 'runner'},
    })
    run_id = result['run_id']
    for attempt in range(60):
        run = call(base, '/runs/' + run_id)
        if not run.get('running'):
            return run
        time.sleep(1)
    raise TimeoutError(f'Run {run_id} did not finish; inspect it before retrying')


async def rank_run(args, metric, group, time_ref):
    from decision_layer.core.models import PlanStep, Recipe, SemanticScope
    from decision_layer.dev import MethodSession
    from decision_layer.semantic.credentials import ServiceCredentials
    from examples.methods.authoring.plain_python import METHODS, rank_groups
    import pandas as pd

    session = await MethodSession.cube(args.cube, ServiceCredentials(os.environ['CUBE_API_SECRET'], ()),
                                       instance=args.instance)
    try:
        session.register(METHODS[0])
        recipe = Recipe(name='ordinary-function-trial', version='1.0.0', description='Rank actual observed campaign means.',
            mode='pipeline', semantic_scope=SemanticScope(primary_metric=metric, preferred_dimensions=[group]),
            steps=[PlanStep(id='rank', method='workshop.rank', method_version='1.0.0',
                purpose='Rank observed campaign means; no causal claim.', bindings={'value': metric, 'group': group})])
        run = await session.preview(recipe, step_index=0, scope={
            'date_range': ['2001-01-01','2001-12-31'], 'time_dimension':time_ref})
        result = run.steps[0].result
        assert result.status == 'success', result
        rows = result.primary.data
        assert rows and rank_groups(pd.DataFrame(rows).drop(columns=['rank'])).to_dict('records') == rows
        assert result.provenance.queries and run.steps[0].code.available
        assert all(check.status == 'pass' for check in result.validation)
        return run.model_dump(mode='json')
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api', default='http://localhost:8000')
    parser.add_argument('--cube', default='http://localhost:4000/cubejs-api/v1')
    parser.add_argument('--instance', default='journey')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    ref = lambda member: f'cube://{args.instance}/campaign_household_outcomes/{member}'
    bindings = {'outcome':ref('post_sales_mean'), 'treatment':ref('pre_sales_mean'),
                'confounders':[ref('pre_frequency_mean')], 'unit':ref('observation_id')}
    group, time_ref = ref('campaign_id'), ref('campaign_start_date')
    catalog = call(args.api, '/semantic/catalog')
    refs = {obj['ref']:obj for obj in catalog['objects']}
    required = {group,time_ref,*[v for value in bindings.values() for v in (value if isinstance(value,list) else [value])]}
    assert required <= refs.keys(), 'Existing sample model is unavailable; do not invent replacement members'
    (args.output/'observed-model.json').write_text(json.dumps({k:refs[k] for k in sorted(required)},indent=2)+'\n')
    scope = {'date_range':['2001-01-01','2001-12-31'], 'time_dimension':time_ref,
             'filters':[{'member':group,'operator':'equals','values':['22']}]}
    runs = []
    for version in ('1.1.0','1.0.0'):
        run = saved_run(args.api, version, bindings, scope)
        (args.output/f'regression-{version}.json').write_text(json.dumps(run,ensure_ascii=False,indent=2)+'\n')
        assert run['steps'][0]['result']['status'] == 'success', run['steps'][0]['result']
        assert run['steps'][0]['method'].endswith('@'+version)
        assert run['steps'][0]['code']['version'] == version
        assert run['query_attempts']
        runs.append(run)
    new, old = (run['steps'][0]['result'] for run in runs)
    assert math.isclose(new['primary']['data']['value'], old['primary']['data']['value'], rel_tol=1e-10)
    assert new['primary']['data'] == {key:value for key,value in old['primary']['data'].items() if key != 'backend_warnings'}
    assert all(warning in new['warnings'] for warning in old['primary']['data'].get('backend_warnings', []))
    assert [a['spec'] for a in runs[0]['query_attempts']] == [a['spec'] for a in runs[1]['query_attempts']]
    assert json.loads(new['provenance']['runtime']['python.resolved_inputs'])['data']['semantic_refs']['confounders_0'] == bindings['confounders'][0]
    rank = asyncio.run(rank_run(args,bindings['outcome'],group,time_ref))
    (args.output/'rank-cube-run.json').write_text(json.dumps(rank,ensure_ascii=False,indent=2)+'\n')
    metrics = {'mode':'Real Cube; scripted REST and local canonical Recipe preview; no Claude trial',
        'new_run':runs[0]['id'], 'pinned_run':runs[1]['id'], 'regression_values_equal':True,
        'query_specs_equal':True, 'observations':new['primary']['data']['n_units'],
        'value':new['primary']['data']['value'], 'rank_observed_groups':len(rank['steps'][0]['result']['primary']['data']),
        'rank_storage':'local in-memory Run exported as JSON; not saved in the running API database',
        'causal_claim':new['primary']['data']['causal_claim']}
    (args.output/'live-metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(metrics,ensure_ascii=False))


if __name__ == '__main__':
    main()
