"""Audit saved Claude protocol events against canonical Run evidence; no network."""
import argparse
import json
from pathlib import Path
from decision_layer.core.models import DatasetSpec


def verify(directory):
    metrics = json.loads((directory / 'metrics.json').read_text())
    events = [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines() if line.strip()]
    calls = [block for event in events if event.get('type') == 'assistant'
             for block in event.get('message', {}).get('content', []) if block.get('type') == 'tool_use']
    init = next(event for event in events if event.get('type') == 'system' and event.get('subtype') == 'init')
    assert metrics['exit_code'] == 0 and metrics['client_success'] and not metrics['timed_out']
    assert len(metrics['runs']) == 1
    run = json.loads((directory / (metrics['runs'][0]['run_id'] + '.json')).read_text())
    assert run['status'] == 'completed' and run['active_skill_step'] is None
    assert [s['step']['method'] for s in run['steps']] == ['analysis.drilldown', 'analysis.peer_comparison', 'example.household_regression']
    assert all(s['result']['status'] == 'success' for s in run['steps'])
    assert run['author']['client_name'] == 'claude-code' and run['author']['client_source'] == 'protocol'
    assert run['conclusion'] and run['conclusion_author']['client_name'] == 'claude-code'
    assert all(c['name'].startswith('mcp__decisionlayer__') for c in calls)
    query_calls = [c['input'] for c in calls if c['name'].endswith('__run_skill_query')]
    failed = []
    for step in run['steps'][:2]:
        skill = step['skill']
        assert skill['status'] == 'completed' and len(skill['guide']['sha256']) == 64
        assert skill['manifest']['agent_executable'] and skill['manifest']['implementation'] == 'skill'
        assert skill['completed_by']['client_name'] == 'claude-code'
        for query in skill['queries']:
            assert query['author']['client_name'] == 'claude-code' and query['author']['client_source'] == 'protocol'
            assert query['started_at'] and query['finished_at']
            matches = [c for c in query_calls if c['step_id'] == step['step']['id'] and c['query_id'] == query['id']]
            assert matches, 'Stored query is missing its actual MCP call'
            assert query['spec'] == DatasetSpec.model_validate(matches[0]['spec']).model_dump(mode='json')
            if query['status'] == 'failed':
                assert query['error']['code'] == 'INVALID_BINDING'
                assert query['spec']['time']['date_range'] == ['2000-01-01', '2000-12-31']
                failed.append(query['id'])
            else:
                assert query['status'] == 'success' and query['result']['primary']['data']
                assert query['result']['provenance']['queries'] and query['result']['validation']
        selected = step['result']['selections']['selected_group']
        assert selected['kind'] == 'selected_group' and selected['reason']
        source = next(q for q in skill['queries'] if q['id'] == selected['evidence']['query_id'])
        assert source['result']['primary']['data'][selected['evidence']['row']][selected['evidence']['dimension']] == selected['candidates'][0]['path'][-1]['value']
    exported = run['steps'][1]['result']['selections']['selected_group']['evidence']['filters']
    assert run['steps'][2]['step']['params']['population_filters'] == exported
    assert any(f['operator'] == 'notEquals' and f['values'] == ['21'] for f in exported)
    assert any(f['operator'] == 'equals' and f['values'] == ['22'] for f in exported)
    assert len(run['query_attempts']) == 4 and all(q['status'] == 'success' for q in run['query_attempts'])
    assert all(q['spec']['time']['date_range'] == ['2001-01-01', '2001-12-31'] for q in run['query_attempts'])
    assert len(failed) == (1 if metrics['failure_case'] else 0)
    python = run['steps'][2]['result']
    assert all(c['status'] == 'pass' for c in python['validation'])
    assert {row['n_observations'] for row in python['primary']['data']} == {2046}
    responses = [str(block.get('content', '')) for event in events for block in event.get('message', {}).get('content', []) if block.get('type') == 'tool_result']
    oversized = sum('<persisted-output>' in value or 'exceeds maximum allowed tokens' in value for value in responses)
    result = {'verified': oversized == 0, 'server_evidence_verified': True, 'oversized_tool_responses': oversized, 'run_id': run['id'], 'model_from_client_log': init.get('model'),
        'client_from_protocol': run['author']['client_name'], 'query_calls': len(query_calls),
        'provider_attempts': len(run['query_attempts']), 'failed_query_ids': failed,
        'checks': ['MCP-only calls', 'query requests match persisted logs', 'Skill text/version/hash persisted',
            'actual query-row selection', 'full filters propagated', 'Python checks passed', '2046 observations',
            'Claude conclusion persisted', 'invalid period never reached provider' if failed else 'all provider reads succeeded']}
    (directory / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    print(json.dumps(verify(parser.parse_args().directory), ensure_ascii=False))
