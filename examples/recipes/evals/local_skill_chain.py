"""Scripted REST/Cube integration check. No Claude/model or external data transfer."""
import argparse
import json
import sys
import time
from pathlib import Path

from claude_skill_chain import ROOT, call
sys.path.insert(0, str(ROOT))
from examples.recipes.skill_chain import legacy_campaign_recipe as campaign_recipe


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--api', default='http://localhost:8000')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tie-break', choices=['refuse', 'smallest-campaign-id'], default='refuse')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    recipe = campaign_recipe().model_dump(mode='json')
    call(args.api, '/recipes:validate?live=true', recipe)
    existing = next((r for r in call(args.api, '/recipes') if r['name'] == recipe['name']), None)
    if existing is None:
        call(args.api, '/recipes/' + recipe['name'], {'recipe': recipe, 'base_version': None}, 'PUT')
    elif existing != recipe:
        raise RuntimeError('Existing Recipe differs; do not overwrite')
    ref = lambda member: 'cube://journey/campaign_household_outcomes/' + member
    metric, dimension, time_ref = map(ref, ['post_sales_mean', 'campaign_id', 'campaign_start_date'])
    dates = ['2001-01-01', '2001-12-31']
    author = {'client_name': 'Scripted REST integration (not Claude)', 'client_source': 'runner'}
    run = call(args.api, '/runs', {'recipe': recipe['name'], 'question': '로컬 실연결 검사: Skill 드릴다운 → peer 조회 → Python 회귀 (Claude 실험 아님)',
        'scope': {'date_range': dates, 'time_dimension': time_ref}, 'author': author})
    run_id = run['id']
    (args.output / 'run-id.txt').write_text(run_id + '\n')

    def refresh():
        for _ in range(90):
            current = call(args.api, '/runs/' + run_id)
            if not current.get('running'):
                return current
            time.sleep(1)
        raise TimeoutError('Run job did not finish')

    def query(step, query_id, filters=None, period=None):
        spec = {'grain': 'aggregate', 'measures': [metric], 'dimensions': [dimension],
            'time': {'dimension': time_ref, 'date_range': period or dates},
            'filters': filters or [], 'order': [[metric, 'desc']], 'limit_rows': 100}
        response = call(args.api, f'/runs/{run_id}/steps/{step}/queries',
            {'id': query_id, 'purpose': 'Scripted integration read: ' + query_id, 'spec': spec, 'author': author})
        if 'status' not in response or response.get('status') == 'running':
            current = refresh()
            response = next(q for r in current['steps'] if r['step']['id'] == step for q in r['skill']['queries'] if q['id'] == query_id)
        return response

    def finish(step, evidence):
        assert evidence['status'] == 'success', evidence
        rows = evidence['result']['primary']['data']
        assert rows, 'No evidence rows'
        tied = [i for i, row in enumerate(rows) if row[metric] == rows[0][metric]]
        if len(tied) > 1 and args.tie_break == 'refuse':
            call(args.api, f'/runs/{run_id}/steps/{step}:finish', {'status': 'refused', 'reason': 'Highest returned mean is tied; no selection rule supplied.', 'author': author})
            raise ValueError('No unique highest returned row; Skill refused')
        chosen = min(tied, key=lambda i: int(rows[i][dimension])) if len(tied) > 1 else 0
        reason = 'Largest returned mean; ties use smallest numeric campaign ID per explicit experiment rule. Not an anomaly or peer-validity claim.'
        call(args.api, f'/runs/{run_id}/steps/{step}:finish', {'reason': 'Scripted selection of largest returned mean; not causal or a verified anomaly.',
            'selection': {'query_id': evidence['id'], 'row': chosen, 'dimension': dimension, 'reason': reason}, 'author': author})
        return rows[chosen][dimension]

    try:
        refresh()
        failed = query('campaigns', 'wrong_period', period=['2000-01-01', '2000-12-31'])
        assert failed['status'] == 'failed'
        assert len(refresh()['query_attempts']) == 0, 'Rejected dates reached the provider'
        subject = finish('campaigns', query('campaigns', 'by_campaign'))
        assert refresh()['active_skill_step'] == 'peers'
        subject_filter = {'member': dimension, 'operator': 'equals', 'values': [subject]}
        excluded = {'member': dimension, 'operator': 'notEquals', 'values': [subject]}
        assert query('peers', 'subject', [subject_filter])['status'] == 'success'
        peer = finish('peers', query('peers', 'other_campaigns', [excluded]))
        run = refresh()
        assert [r['result']['status'] for r in run['steps']] == ['success'] * 3
        assert run['steps'][-1]['step']['params']['population_filters'] == [excluded, {'member': dimension, 'operator': 'equals', 'values': [peer]}]
        if run['status'] == 'open':
            run = call(args.api, f'/runs/{run_id}:complete', {'summary': '로컬 scripted 검증 완료. Skill 조회 3건과 Python 조회·회귀 1건 성공. 잘못된 기간 요청은 Cube 조회 전에 거부되어 Skill 로그에 보존됨. 동료 집단 적절성·인과성은 검증하지 않음. Claude 실험 아님.', 'author': author})
    finally:
        run = call(args.api, '/runs/' + run_id)
        (args.output / 'run.json').write_text(json.dumps(run, ensure_ascii=False, indent=2) + '\n')
    metrics = {'mode': 'scripted REST -> existing Cube, not Claude', 'tie_break': args.tie_break, 'run_id': run_id,
        'status': run['status'], 'methods': [r['step']['method'] for r in run['steps']],
        'step_statuses': [r['result']['status'] for r in run['steps']],
        'skill_query_statuses': [[q['status'] for q in r['skill']['queries']] for r in run['steps'] if r.get('skill')],
        'provider_attempts': len(run['query_attempts']), 'subject': subject, 'selected_peer': peer,
        'python_filters': run['steps'][-1]['step']['params']['population_filters']}
    (args.output / 'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(metrics, ensure_ascii=False))


if __name__ == '__main__':
    main()
