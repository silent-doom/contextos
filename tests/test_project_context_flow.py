"""Project context integration through ordinary create, review and task APIs."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.ai import AI
from backend.app import create_app
from backend.store import SQLiteStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTH_MODE', 'demo')
    return TestClient(create_app(SQLiteStore(tmp_path / 'handoff.db'), AI(mode='offline')),
                      headers={'x-contextos-client': 'workspace'})


def setup(client):
    response = client.post('/api/context/projects', json={'name': 'Test project', 'project_type': 'Software'})
    assert response.status_code == 201, response.text
    pid = response.json()['id']
    base = f'/api/context/projects/{pid}'
    ids = {}
    fixtures = [
        ('requirements', 'pm', 'Retry transient failures without duplicate charges.', []),
        ('security', 'security', 'Never log card numbers or credentials.', []),
        ('architecture', 'architect', 'Use at most three attempts with the same idempotency key.', ['requirements', 'security']),
        ('quality', 'qa', 'Check payment retry limits and duplicate submissions.', ['architecture']),
    ]
    for name, role, body, dependencies in fixtures:
        proposal = client.post(f'{base}/contexts', json={
            'name': name.title(), 'filename': f'{name}.md', 'owner': role, 'owner_type': role,
            'content': f'## Overview\n\n{name.title()}.\n\n## Details\n\n{body}\n\n## Next steps\n\nVerify the contract.',
            'relationships': [{'target_id': ids[dep], 'kind': 'depends_on'} for dep in dependencies],
            'reason': 'Test fixture.'}).json()
        assert approve(client, base, proposal, role).status_code == 200
        ids[name] = proposal['context_id']
        client.post('/api/persona', json={'role': 'developer'})
    return pid, base


def snapshot(client, pid):
    response = client.get('/api/workspace', params={'project_id': pid})
    assert response.status_code == 200, response.text
    return response.json()


def propose_change(client, base, cid, text='Allow at most two attempts; reuse the original idempotency key.'):
    doc = client.get(f'{base}/contexts/{cid}').json()
    data = {key: doc[key] for key in ('name', 'filename', 'owner', 'owner_type', 'relationships')}
    data.update(content=f'## Overview\n\nUpdated decision.\n\n## Details\n\n{text}\n\n## Next steps\n\nReview dependent work.',
                expected_version=doc['version'], reason='Provider reliability agreement changed.')
    response = client.put(f'{base}/contexts/{cid}', json=data)
    assert response.status_code == 200, response.text
    return response.json()


def approve(client, base, proposal, role='architect'):
    client.post('/api/persona', json={'role': role})
    return client.post(f"{base}/proposals/{proposal['id']}/review",
                       json={'hash': proposal['hash'], 'decision': 'approve'})


def test_knowledge_is_the_exact_project_source_for_work_and_inbox(client):
    pid, base = setup(client)
    workspace = snapshot(client, pid)
    architecture = next(c for c in workspace['contexts'] if c['domain'] == 'Architecture')
    proposal = propose_change(client, base, architecture['id'])
    # Drafts are visible in Inbox but cannot reach an agent's accepted payload.
    pending = snapshot(client, pid)
    assert pending['proposals'][-1]['status'] == 'pending'
    assert next(c for c in pending['contexts'] if c['id'] == architecture['id'])['revision'] == 1
    assert approve(client, base, proposal, 'developer').status_code == 403
    assert approve(client, base, proposal).status_code == 200
    client.post('/api/persona', json={'role': 'qa'})
    response = client.post('/api/tasks', json={'query': 'Derive payment retry acceptance tests', 'budget': 6000, 'project_id': pid})
    assert response.status_code == 200, response.text
    run = response.json()
    source = next(s for s in run['manifest']['sources'] if s['id'] == architecture['id'])
    assert source['revision'] == 2 and 'two attempts' in source['body']
    assert source['body'] == client.get(f"{base}/contexts/{source['id']}").json()['content']
    assert 'two attempts' in run['output']
    refreshed = snapshot(client, pid)
    assert refreshed['tasks'][0]['id'] == run['id']
    event = next(e for e in refreshed['events'] if e['action'] == 'Context revision published' and 'v2' in e['detail'])
    assert event['actor'] == 'demo-architect' and 'demo-developer' in event['detail']
    assert any('changed dependencies' in w for w in run['manifest']['context_warnings'])


def test_projects_do_not_mix_sources_runs_usage_or_exports(client):
    pid, base = setup(client)
    other = client.post('/api/context/projects', json={'name': 'Other team', 'project_type': 'Test'}).json()['id']
    run = client.post('/api/tasks', json={'query': 'Implement payment retries', 'project_id': pid}).json()
    assert run['manifest']['sources']
    for selected in (other, None):
        data = client.get('/api/export', params={'project_id': selected} if selected else {}).json()
        assert run['id'] not in str(data)
        assert not data['usage']
    assert client.post('/api/tasks', json={'query': 'Payment retries', 'project_id': 'missing'}).status_code == 404
    assert client.get('/api/workspace?project_id=missing').status_code == 404
    # Another isolated workspace cannot address a known project ID.
    stranger = TestClient(client.app, headers=client.headers)
    assert stranger.get(f'{base}/contexts').status_code == 404


def test_new_security_constraint_flags_prior_work_and_requires_explicit_refresh(client):
    pid, base = setup(client)
    chat = client.post('/api/conversations', json={'title': 'Build payment retries', 'request_id': 'create-project-chat', 'project_id': pid}).json()
    path = f"/api/conversations/{chat['id']}/turns"
    first = client.post(path, json={'query': 'Implement payment retries', 'budget': 6000, 'request_id': 'turn-project-first'}).json()
    original = deepcopy(first['manifest'])
    security = next(c for c in snapshot(client, pid)['contexts'] if c['domain'] == 'Security')
    proposal = propose_change(client, base, security['id'], 'Redact provider trace IDs from customer-visible errors and logs.')
    assert approve(client, base, proposal, 'security').status_code == 200
    client.post('/api/persona', json={'role': 'developer'})
    changed = snapshot(client, pid)['tasks'][0]
    assert changed['stale'] and changed['context_changes'][0]['mandatory']
    assert changed['manifest'] == original
    assert client.post(path, json={'query': 'Which tests change?', 'budget': 6000, 'request_id': 'turn-project-second'}).status_code == 409
    refreshed = client.post(path, json={'query': 'Which tests change?', 'budget': 6000, 'request_id': 'turn-project-second', 'refresh_context': True}).json()
    assert refreshed['status'] == 'succeeded' and not refreshed['stale']
    assert refreshed['manifest']['history_turn_ids'] == []
    assert any(s['id'] == security['id'] and s['revision'] == 2 for s in refreshed['manifest']['sources'])
    reopened = TestClient(create_app(client.app.state.store, AI(mode='offline')), headers=client.headers, cookies=client.cookies)
    assert reopened.get(f"/api/conversations/{chat['id']}").json()['turns'][0]['manifest'] == original
    assert client.post(path, json={'query': 'Different project?', 'budget': 6000, 'request_id': 'turn-project-third', 'project_id': 'wrong'}).status_code == 409


def test_new_mandatory_rule_during_inference_is_detected(client, monkeypatch):
    pid, base = setup(client)
    original = client.app.state.ai.task
    def publish_during_call(role, query, manifest):
        data = {'name': 'Additional security constraint', 'filename': 'extra-security.md',
                'content': '## Overview\n\nLogging.\n\n## Details\n\nRedact provider trace IDs.\n\n## Next steps\n\nReview logs.',
                'owner': 'Security', 'owner_type': 'security', 'reason': 'Additional provider requirement.'}
        proposal = client.post(f'{base}/contexts', json=data).json()
        assert approve(client, base, proposal, 'security').status_code == 200
        return original(role, query, manifest)
    monkeypatch.setattr(client.app.state.ai, 'task', publish_during_call)
    response = client.post('/api/tasks', json={'query': 'Implement payment retries', 'project_id': pid})
    assert response.status_code == 200, response.text
    assert response.json()['stale']


def test_project_mandatory_budget_and_independent_exact_review(client):
    pid, base = setup(client)
    assert client.post('/api/assemble', json={'query': 'Payments', 'budget': 200, 'project_id': pid}).status_code == 422
    arc = next(c for c in snapshot(client, pid)['contexts'] if c['domain'] == 'Architecture')
    first, second = propose_change(client, base, arc['id']), propose_change(client, base, arc['id'], 'At most one attempt.')
    client.post('/api/persona', json={'role': 'architect'})
    assert client.post(f"{base}/proposals/{first['id']}/review", json={'hash': '0' * 64, 'decision': 'approve'}).status_code == 409
    def publish(proposal):
        return client.post(f"{base}/proposals/{proposal['id']}/review", json={'hash': proposal['hash'], 'decision': 'approve'}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(publish, (first, second)))
    assert sorted(outcomes) == [200, 409]
    versions = client.get(f"{base}/contexts/{arc['id']}/versions").json()
    assert [v['version'] for v in versions] == [2, 1]


def test_mandatory_project_rule_keeps_its_dependency_even_without_query_overlap(client):
    pid, base = setup(client)
    contexts = snapshot(client, pid)['contexts']
    arc = next(c for c in contexts if c['domain'] == 'Architecture')
    data = {'name': 'Operational safety rule', 'filename': 'safety.md', 'owner': 'Security', 'owner_type': 'security',
            'content': '## Overview\n\nSafety.\n\n## Details\n\nFollow the linked contract.\n\n## Next steps\n\nVerify conformance.',
            'relationships': [{'target_id': arc['id'], 'kind': 'depends_on'}], 'reason': 'Required prerequisite.'}
    proposal = client.post(f'{base}/contexts', json=data).json()
    assert approve(client, base, proposal, 'security').status_code == 200
    result = client.post('/api/assemble', json={'query': 'Unrelated question', 'budget': 6000, 'project_id': pid})
    assert result.status_code == 200, result.text
    assert arc['id'] in {s['id'] for s in result.json()['sources']}
