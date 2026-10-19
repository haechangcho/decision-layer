from copy import deepcopy
import pytest
from decision_layer.mcp import server


def query():
    return {'id': 'q', 'purpose': 'Inspect rows', 'status': 'success', 'spec': {'filters': []},
        'result': {'status': 'success', 'primary': {'data': [{'group': str(i), 'value': i} for i in range(1000)]},
            'artifacts': [], 'validation': [{'code': 'QUERY_SCOPE', 'status': 'pass'}],
            'provenance': {'queries': [{'rows': 1000, 'compiled_sql': 'select governed'}]}}}


def test_skill_run_summary_preserves_evidence_without_repeating_rows():
    original = query()
    frozen = deepcopy(original)
    skill = {'status': 'completed', 'guide': {'markdown': 'long instructions', 'version': '1.0.0', 'sha256': 'a'*64},
             'manifest': {'agent_executable': True}, 'queries': [original]}
    summary = server._compact_skill(skill)
    assert summary['queries'][0]['rows'] == 1000
    assert 'result' not in summary['queries'][0] and 'markdown' not in summary['guide']
    skill['status'] = 'awaiting_agent'
    assert server._compact_skill(skill)['guide']['markdown'] == 'long instructions'
    result = server._skill_result_summary(original['result'])
    assert len(result['primary']['data']) == 0 and result['primary_preview']['total'] == 1000
    assert result['validation'][0]['status'] == 'pass'
    assert original == frozen, 'Compaction must never change persisted evidence'


async def test_skill_query_pagination_reads_stored_evidence_with_access_checks(monkeypatch):
    original = query()
    frozen = deepcopy(original)
    calls = []
    async def api(method, path):
        calls.append((method, path))
        return {'id': 'r', 'steps': [{'step': {'id': 's'}, 'skill': {'queries': [original]}}]}
    monkeypatch.setattr(server, '_call', api)
    page = await server.get_skill_query('r', 's', 'q', offset=25, limit=25)
    assert page['result']['primary']['data'][0]['value'] == 25
    assert page['page']['next_offset'] == 50 and page['page']['total_rows'] == 1000
    assert page['result']['validation'] and page['spec'] == original['spec']
    assert original == frozen and calls == [('GET', '/runs/r')]
    assert (await server.get_skill_query('r','s','q',limit=101))['error']['code'] == 'INVALID_PAGE'
    assert (await server.get_skill_query('r','s','missing'))['error']['code'] == 'SKILL_QUERY_NOT_FOUND'
    async def denied(method, path):
        return {'error': {'code': 'ACCESS_DENIED'}}
    monkeypatch.setattr(server, '_call', denied)
    assert (await server.get_skill_query('r','s','q'))['error']['code'] == 'ACCESS_DENIED'
