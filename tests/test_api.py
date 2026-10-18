import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.ai import AI
from backend.store import SQLiteStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTH_MODE', 'demo'); monkeypatch.setenv('AI_MODE', 'offline')
    return TestClient(create_app(SQLiteStore(tmp_path / 'test.db'), AI()), headers={'x-contextos-client': 'workspace'})


def test_full_cross_role_workflow(client):
    state = client.get('/api/workspace').json()
    assert state['role'] == 'developer'
    run = client.post('/api/tasks', json={'query': 'Implement payment retries', 'budget': 6000}).json()
    assert run['usage']['provider'] == 'offline'
    assert run['manifest']['sources']
    p = client.post('/api/proposals', json={'context_id': 'ARC-001', 'base_revision': 1, 'body': 'Retry at most two times, using the original idempotency key.', 'reason': 'Limit latency'}).json()
    assert client.post(f"/api/proposals/{p['id']}/review", json={'hash': p['hash'], 'decision': 'approve'}).status_code == 403
    client.post('/api/persona', json={'role': 'architect'})
    assert client.post(f"/api/proposals/{p['id']}/review", json={'hash': p['hash'], 'decision': 'approve'}).status_code == 200
    state = client.get('/api/workspace').json()
    assert state['tasks'][0]['stale']
    rerun = client.post('/api/tasks', json={'query': 'Implement payment retries', 'budget': 6000}).json()
    assert not rerun['stale']
    assert next(x for x in rerun['manifest']['sources'] if x['id'] == 'ARC-001')['revision'] == 2


def test_sessions_isolated_and_requests_validated(client):
    client.get('/api/workspace')
    client.post('/api/persona', json={'role': 'security'})
    assert 'RES-001' in client.get('/api/workspace').text
    client.cookies.clear()
    assert 'RES-001' not in client.get('/api/workspace').text
    assert client.post('/api/tasks', json={'query': '', 'role': 'security'}).status_code == 422
    assert client.post('/api/persona', json={'role': 'admin'}).status_code == 422
    assert client.post('/api/persona', json={'role': 'pm'}, headers={'origin': 'https://evil.example'}).status_code == 403


def test_ingest_candidate_requires_independent_review(client):
    p = client.post('/api/ingest', json={'notes': 'Customers need clear error messages after a declined card.', 'source': 'Workshop'}).json()
    assert p['status'] == 'pending'
    # Seven seeded items exist; Developer cannot see restricted RES-001.
    assert len(client.get('/api/workspace').json()['contexts']) == 6
    client.post('/api/persona', json={'role': 'pm'})
    assert client.post(f"/api/proposals/{p['id']}/review", json={'hash': p['hash'], 'decision': 'approve'}).status_code == 200
    assert len(client.get('/api/workspace').json()['contexts']) == 7


def test_restricted_task_output_hidden_after_switch(client):
    client.post('/api/persona', json={'role': 'security'})
    response = client.post('/api/tasks', json={'query': 'Internal security finding diagnostic endpoint', 'budget': 10000})
    assert 'INTERNAL-SEC-42' in response.text
    client.post('/api/persona', json={'role': 'developer'})
    state = client.get('/api/workspace')
    assert 'INTERNAL-SEC-42' not in state.text
    assert not state.json()['tasks']


def test_budget_overflow_and_model_error_visible(client, monkeypatch):
    assert client.post('/api/tasks', json={'query': 'payment', 'budget': 200}).status_code == 422
    from backend.domain import Problem
    def fail(*args):
        raise Problem('Model unavailable', 502)
    monkeypatch.setattr(client.app.state.ai, 'task', fail)
    result = client.post('/api/tasks', json={'query': 'payment', 'budget': 6000})
    assert result.status_code == 502
    assert client.get('/api/workspace').json()['usage'][0]['status'] == 'failed'


def test_rate_limit(client):
    for _ in range(6):
        assert client.post('/api/tasks', json={'query': 'payment', 'budget': 6000}).status_code == 200
    assert client.post('/api/tasks', json={'query': 'payment', 'budget': 6000}).status_code == 429


def test_invalid_extraction_records_known_usage(client, monkeypatch):
    from backend.domain import Problem
    def invalid(notes):
        raise Problem('Invalid extraction', 502, usage={'provider': 'vertex', 'total_tokens': 230})
    monkeypatch.setattr(client.app.state.ai, 'extract', invalid)
    response = client.post('/api/ingest', json={'notes': 'A sufficiently long note.', 'source': 'Test'})
    assert response.status_code == 502
    state = client.get('/api/workspace').json()
    assert state['usage'][0]['total_tokens'] == 230
    assert state['usage'][0]['status'] == 'failed'
    assert not state['proposals']


def test_source_change_during_model_call_marks_new_run_stale(client, monkeypatch):
    from backend.domain import propose, review
    client.get('/api/workspace')
    workspace = client.cookies.get('contextos_session')
    original = client.app.state.ai.task
    def concurrent_change(role, query, manifest):
        def mutation(s):
            p = propose(s, 'dev', 'developer', {'context_id': 'ARC-001', 'base_revision': 1, 'body': 'A concurrent reviewed design.', 'reason': 'Concurrent update', 'sources': []})
            review(s, 'architect', 'architect', p['id'], p['hash'], 'approve')
        client.app.state.store.mutate(workspace, mutation)
        return original(role, query, manifest)
    monkeypatch.setattr(client.app.state.ai, 'task', concurrent_change)
    response = client.post('/api/tasks', json={'query': 'payment retry architecture', 'budget': 6000})
    assert response.status_code == 200
    run = response.json()
    assert run['stale']
    assert next(s for s in run['manifest']['sources'] if s['id'] == 'ARC-001')['revision'] == 1


def test_firebase_claims_are_authoritative_and_isolate_workspaces(tmp_path, monkeypatch):
    import firebase_admin
    from firebase_admin import auth
    monkeypatch.setenv('AUTH_MODE', 'firebase')
    monkeypatch.setenv('AI_MODE', 'offline')
    monkeypatch.setattr(firebase_admin, '_apps', {'test': object()})
    verified = []
    def verify(token, check_revoked):
        verified.append(check_revoked)
        identities = {
            'dev-token': {'uid':'dev-a','contextos_workspace':'team-a','contextos_role':'developer'},
            'arch-token': {'uid':'arch-a','contextos_workspace':'team-a','contextos_role':'architect'},
            'other-token': {'uid':'other','contextos_workspace':'team-b','contextos_role':'architect'},
        }
        if token not in identities:
            raise ValueError('Invalid signature')
        return identities[token]
    monkeypatch.setattr(auth, 'verify_id_token', verify)
    app = create_app(SQLiteStore(tmp_path / 'auth.db'), AI())
    c = TestClient(app, headers={'x-contextos-client':'workspace'})
    assert c.get('/api/workspace').status_code == 401
    c.headers['Authorization'] = 'Bearer dev-token'
    assert c.get('/api/demo/scenarios').status_code == 403
    assert c.post('/api/demo/scenarios/restricted', json={}).status_code == 403
    assert c.post('/api/persona', json={'role':'security'}).status_code == 403
    p = c.post('/api/proposals', json={'context_id':'ARC-001','base_revision':1,'body':'A reviewed design','reason':'New evidence'}).json()
    c.headers['Authorization'] = 'Bearer other-token'
    assert not c.get('/api/workspace').json()['proposals']
    assert c.post(f"/api/proposals/{p['id']}/review", json={'hash':p['hash'],'decision':'approve'}).status_code == 404
    c.headers['Authorization'] = 'Bearer arch-token'
    assert c.post(f"/api/proposals/{p['id']}/review", json={'hash':p['hash'],'decision':'approve'}).status_code == 200
    assert all(verified)


def test_static_assets_security_headers_and_missing_client_header(client):
    for path in ('/', '/favicon.ico', '/assets/app.js', '/assets/style.css', '/assets/favicon.svg'):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers['x-content-type-options'] == 'nosniff'
    assert client.get('/api/workspace').headers['cache-control'] == 'no-store'
    client.headers.pop('x-contextos-client')
    assert client.post('/api/persona', json={'role':'security'}).status_code == 403


def test_persona_actions_are_attributed_and_recommendations_obey_ownership(client):
    for role in ('pm','architect','developer','qa','security'):
        client.post('/api/persona', json={'role':role})
        state = client.get('/api/workspace').json()
        task = next(a for a in state['next_actions'] if a['kind']=='task')
        assert task['query']
        assert not any(a['kind']=='review' for a in state['next_actions'])
        run = client.post('/api/tasks',json={'query':task['query'],'budget':6000}).json()
        assert client.post('/api/activity',json={'action':'manifest_inspected','target_id':run['id']}).status_code == 200
        state = client.get('/api/workspace').json()
        event = next(e for e in state['events'] if e['action']=='Task completed' and e['role']==role)
        assert event['actor']==f'demo-{role}' and event['outcome']=='completed'
    client.post('/api/persona',json={'role':'developer'})
    proposal = client.post('/api/proposals',json={'context_id':'ARC-001','base_revision':1,'body':'Use idempotency for safe retries.','reason':'Clarify the contract'}).json()
    assert not any(a['kind']=='review' for a in client.get('/api/workspace').json()['next_actions'])
    client.post('/api/proposals/'+proposal['id']+'/review',json={'hash':proposal['hash'],'decision':'approve'})
    blocked = next(e for e in client.get('/api/workspace').json()['events'] if e['outcome']=='blocked')
    assert blocked['actor']=='demo-developer' and blocked['role']=='developer'
    client.post('/api/persona',json={'role':'architect'})
    action = client.get('/api/workspace').json()['next_actions'][0]
    assert action['kind']=='review' and action['id']==proposal['id']


def test_inspection_logs_enforce_visibility_and_do_not_leak_restricted_work(client):
    client.post('/api/persona',json={'role':'security'})
    assert client.post('/api/activity',json={'action':'context_viewed','target_id':'RES-001'}).status_code==200
    run = client.post('/api/tasks',json={'query':'Internal security finding','budget':10000}).json()
    client.post('/api/persona',json={'role':'developer'})
    assert client.post('/api/activity',json={'action':'manifest_inspected','target_id':run['id']}).status_code==404
    assert client.post('/api/activity',json={'action':'context_viewed','target_id':'RES-001'}).status_code==404
    view = client.get('/api/workspace').json()
    assert 'Internal security finding' not in str(view['events'])
    assert not any(e['action']=='Task completed' for e in view['events'])
    assert client.post('/api/activity',json={'action':'approved_anything','target_id':'ARC-001'}).status_code==422
    exported = client.get('/api/export').json()
    assert exported['events'][0]['action']=='Evidence exported'


def test_public_origin_supports_https_proxy_without_trusting_forwarded_headers(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTH_MODE', 'demo')
    monkeypatch.setenv('PUBLIC_ORIGIN', 'https://contextos.example')
    c = TestClient(create_app(SQLiteStore(tmp_path / 'proxy.db'), AI(mode='offline')),
                   headers={'x-contextos-client': 'workspace'})
    assert c.post('/api/persona', json={'role': 'qa'},
                  headers={'origin': 'https://contextos.example'}).status_code == 200
    for origin in ('https://evil.example', 'http://contextos.example', 'http://testserver', 'null'):
        assert c.post('/api/persona', json={'role': 'pm'}, headers={
            'origin': origin, 'x-forwarded-host': 'evil.example',
            'x-forwarded-proto': 'https'}).status_code == 403


@pytest.mark.parametrize('origin', ['https://example.com/path', 'https://user@example.com', 'https://example.com?x=1', 'null'])
def test_invalid_public_origin_fails_at_startup(tmp_path, monkeypatch, origin):
    monkeypatch.setenv('PUBLIC_ORIGIN', origin)
    with pytest.raises(RuntimeError, match='PUBLIC_ORIGIN'):
        create_app(SQLiteStore(tmp_path / 'invalid-origin.db'), AI(mode='offline'))
