from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event

import pytest
from fastapi.testclient import TestClient

from backend import domain as d
from backend.ai import AI
from backend.app import create_app
from backend.conversations import HISTORY_BYTES, OUTPUT_BYTES
from backend.store import SQLiteStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTH_MODE', 'demo')
    return TestClient(create_app(SQLiteStore(tmp_path / 'chat.db'), AI(mode='offline')),
                      headers={'x-contextos-client': 'workspace'})


def create(client, request_id='create-0001', title='Implement payment retries'):
    response = client.post('/api/conversations', json={'title': title, 'request_id': request_id})
    assert response.status_code == 200, response.text
    return response.json()


def reply(client, cid, request_id='reply-0001', query='Implement payment retries', **extra):
    return client.post(f'/api/conversations/{cid}/turns', json={
        'query': query, 'budget': 6000, 'request_id': request_id, **extra})


def publish_architecture(store, workspace):
    def update(state):
        proposal = d.propose(state, 'developer', 'developer', {'context_id': 'ARC-001',
            'base_revision': 1, 'body': 'Limit retries to two with the original idempotency key.',
            'reason': 'New accepted design', 'sources': []})
        d.review(state, 'designer', 'architect', proposal['id'], proposal['hash'], 'approve')
    store.mutate(workspace, update)


def test_reopen_persists_turns_and_exact_working_history(client, monkeypatch):
    chat = create(client)
    first = reply(client, chat['id']).json()
    assert first['status'] == 'succeeded' and first['usage']['provider'] == 'offline'
    assert first['manifest']['history_turn_ids'] == []
    before = deepcopy(first['manifest'])
    reopened = TestClient(create_app(client.app.state.store, AI(mode='offline')),
                          cookies=client.cookies, headers=client.headers)
    calls = []
    original = reopened.app.state.ai.conversation
    def capture(role, query, manifest, history):
        calls.append((manifest, history))
        return original(role, query, manifest, history)
    monkeypatch.setattr(reopened.app.state.ai, 'conversation', capture)
    second = reply(reopened, chat['id'], 'reply-0002', 'What should I test next?').json()
    assert second['manifest']['history_turn_ids'] == [first['id']]
    assert calls[0][1] == [{'turn_id': first['id'], 'query': first['query'], 'output': first['output']}]
    assert 'ARC-001' in {s['id'] for s in calls[0][0]['sources']}
    persisted = reopened.get(f"/api/conversations/{chat['id']}").json()
    assert persisted['turns'][0]['manifest'] == before
    assert persisted['turn_ids'] == [first['id'], second['id']]
    exported = reopened.get('/api/export').json()
    assert exported['conversations'][0]['turns'] == persisted['turns']
    assert client.get('/api/conversations').json()['conversations'][0]['id'] == chat['id']


def test_idempotent_creation_and_turns_do_not_repeat_usage(client):
    chat = create(client)
    assert create(client)['id'] == chat['id']
    assert client.post('/api/conversations', json={'title': 'Another task', 'request_id': 'create-0001'}).status_code == 409
    first = reply(client, chat['id']).json()
    assert reply(client, chat['id']).json() == first
    assert len(client.get('/api/workspace').json()['usage']) == 1
    for extra in ({'query': 'Changed request'}, {'budget': 7000}, {'refresh_context': True}):
        assert reply(client, chat['id'], **extra).status_code == 409


def test_failed_turn_retry_keeps_identity_snapshot_and_known_usage(client, monkeypatch):
    chat = create(client)
    ai = client.app.state.ai
    original = ai.conversation
    def fail(*args):
        raise d.Problem('The model is unavailable.', 502, usage={'provider': 'vertex', 'total_tokens': 31})
    monkeypatch.setattr(ai, 'conversation', fail)
    assert reply(client, chat['id']).status_code == 502
    failed = client.get(f"/api/conversations/{chat['id']}").json()['turns'][0]
    assert failed['status'] == 'failed' and failed['output'] == ''
    assert reply(client, chat['id'], 'reply-0002').status_code == 409
    view = client.get('/api/workspace').json()
    assert not view['tasks'] and view['usage'][0]['total_tokens'] == 31
    publish_architecture(client.app.state.store, client.cookies.get('contextos_session'))
    monkeypatch.setattr(ai, 'conversation', original)
    retried = reply(client, chat['id']).json()
    assert retried['id'] == failed['id'] and retried['attempts'] == 2 and retried['stale']
    assert retried['manifest'] == failed['manifest']  # Retries retain the original snapshot.
    assert [u['status'] for u in client.get('/api/workspace').json()['usage']] == ['failed', 'completed']


def test_unexpected_provider_error_is_redacted(client, monkeypatch):
    chat = create(client)
    def fail(*args):
        raise RuntimeError('credential-secret-in-provider-error')
    monkeypatch.setattr(client.app.state.ai, 'conversation', fail)
    response = reply(client, chat['id'])
    assert response.status_code == 502
    assert 'credential-secret' not in response.text + client.get('/api/export').text
    assert client.get(f"/api/conversations/{chat['id']}").json()['turns'][0]['status'] == 'failed'


def test_pending_duplicates_do_not_run_models_or_block_transactions(client, monkeypatch):
    chat = create(client)
    service = client.app.state.conversations
    workspace = client.cookies.get('contextos_session')
    started, release = Event(), Event()
    original = service.ai.conversation
    def slow(*args):
        started.set()
        assert release.wait(5)
        return original(*args)
    monkeypatch.setattr(service.ai, 'conversation', slow)
    with ThreadPoolExecutor(max_workers=1) as executor:
        running = executor.submit(service.reply, workspace, chat['id'], 'demo-developer', 'developer',
                                  'Implement payment retries', 6000, 'reply-0001')
        try:
            assert started.wait(5)
            duplicate = reply(client, chat['id'])
            assert duplicate.status_code == 202 and duplicate.json()['status'] == 'pending'
            assert reply(client, chat['id'], 'reply-0002').status_code == 409
            view = client.get('/api/workspace').json()
            assert not view['tasks'] and len(view['usage']) == 1
        finally:
            release.set()
        assert running.result(timeout=5)['status'] == 'succeeded'


def test_expired_attempt_cannot_overwrite_its_replacement(client, monkeypatch):
    chat = create(client)
    service = client.app.state.conversations
    workspace = client.cookies.get('contextos_session')
    started, release = Event(), Event()
    def slow_then_retry(*args):
        if not started.is_set():
            started.set()
            assert release.wait(5)
            return 'Late result', {'provider': 'test', 'total_tokens': 9}
        return 'Winning result', {'provider': 'test', 'total_tokens': 12}
    monkeypatch.setattr(service.ai, 'conversation', slow_then_retry)
    with ThreadPoolExecutor(max_workers=1) as executor:
        running = executor.submit(service.reply, workspace, chat['id'], 'demo-developer', 'developer',
                                  'Implement payment retries', 6000, 'reply-0001')
        try:
            assert started.wait(5)
            def expire(state):
                state['tasks'][state['conversations'][chat['id']]['turn_ids'][0]]['lease_expires_at'] = '2000-01-01T00:00:00+00:00'
            service.store.mutate(workspace, expire)
            replacement = reply(client, chat['id']).json()
            assert replacement['status'] == 'succeeded' and replacement['attempts'] == 2
        finally:
            release.set()
        assert running.result(timeout=5)['output'] == 'Winning result'
    view = client.get('/api/workspace').json()
    assert len(view['tasks']) == 1 and view['tasks'][0]['output'] == 'Winning result'
    assert [(u['status'], u['total_tokens']) for u in view['usage']] == [('failed', 9), ('completed', 12)]


def test_context_refresh_explicitly_resets_history_preserving_earlier_turns(client):
    chat = create(client)
    first = reply(client, chat['id']).json()
    publish_architecture(client.app.state.store, client.cookies.get('contextos_session'))
    assert reply(client, chat['id'], 'reply-0002', 'What should I test next?').status_code == 409
    second = reply(client, chat['id'], 'reply-0002', 'Test payment retries', refresh_context=True).json()
    assert second['manifest']['history_turn_ids'] == []
    assert next(s['revision'] for s in second['manifest']['sources'] if s['id'] == 'ARC-001') == 2
    third = reply(client, chat['id'], 'reply-0003', 'What else?').json()
    assert third['manifest']['history_turn_ids'] == [second['id']]
    persisted = client.get(f"/api/conversations/{chat['id']}").json()['turns']
    assert persisted[0]['manifest'] == first['manifest'] and persisted[0]['stale']


def test_context_change_during_reply_marks_exact_snapshot_stale(client, monkeypatch):
    chat = create(client)
    original = client.app.state.ai.conversation
    def update_during_call(*args):
        publish_architecture(client.app.state.store, client.cookies.get('contextos_session'))
        return original(*args)
    monkeypatch.setattr(client.app.state.ai, 'conversation', update_during_call)
    turn = reply(client, chat['id']).json()
    assert turn['stale']
    assert next(s['revision'] for s in turn['manifest']['sources'] if s['id'] == 'ARC-001') == 1


def test_revoked_source_hides_entire_conversation_and_derived_views(client, monkeypatch):
    chat = create(client)
    turn = reply(client, chat['id']).json()
    assert client.post('/api/activity', json={'action': 'manifest_inspected', 'target_id': turn['id']}).status_code == 200
    def restrict(state):
        state['contexts']['ARC-001']['policy'] = 'Restricted'
    client.app.state.store.mutate(client.cookies.get('contextos_session'), restrict)
    def unexpected(*args):
        pytest.fail('Restricted history must never reach the model')
    monkeypatch.setattr(client.app.state.ai, 'conversation', unexpected)
    assert client.get(f"/api/conversations/{chat['id']}").status_code == 404
    assert client.get('/api/conversations').json()['conversations'] == []
    assert reply(client, chat['id'], 'reply-0002', refresh_context=True).status_code == 404
    assert client.post('/api/activity', json={'action': 'manifest_inspected', 'target_id': turn['id']}).status_code == 404
    for path in ('/api/workspace', '/api/export'):
        response = client.get(path)
        assert chat['id'] not in response.text and turn['id'] not in response.text
        assert not response.json()['conversations'] and not response.json()['tasks'] and not response.json()['usage']


def test_different_members_roles_and_workspaces_cannot_read_private_history(tmp_path, monkeypatch):
    import firebase_admin
    from firebase_admin import auth
    monkeypatch.setenv('AUTH_MODE', 'firebase')
    monkeypatch.setattr(firebase_admin, '_apps', {'test': object()})
    identities = {'alice': ('team', 'alice', 'developer'), 'bob': ('team', 'bob', 'developer'),
                  'alice-role': ('team', 'alice', 'architect'), 'alice-tenant': ('other', 'alice', 'developer')}
    def verify(token, check_revoked):
        assert check_revoked
        workspace, actor, role = identities[token]
        return {'uid': actor, 'contextos_workspace': workspace, 'contextos_role': role}
    monkeypatch.setattr(auth, 'verify_id_token', verify)
    client = TestClient(create_app(SQLiteStore(tmp_path / 'members.db'), AI(mode='offline')),
                        headers={'x-contextos-client': 'workspace', 'Authorization': 'Bearer alice'})
    chat = create(client, title='Private working notes')
    turn = reply(client, chat['id']).json()
    assert client.post('/api/activity', json={'action': 'manifest_inspected', 'target_id': turn['id']}).status_code == 200
    for token in ('bob', 'alice-role', 'alice-tenant'):
        client.headers['Authorization'] = f'Bearer {token}'
        assert client.get(f"/api/conversations/{chat['id']}").status_code == 404
        assert reply(client, chat['id'], 'reply-0002').status_code == 404
        assert client.post('/api/activity', json={'action': 'manifest_inspected', 'target_id': turn['id']}).status_code == 404
        for path in ('/api/workspace', '/api/export', '/api/conversations'):
            text = client.get(path).text
            assert chat['id'] not in text and turn['id'] not in text and 'Private working notes' not in text
    client.headers['Authorization'] = 'Bearer alice'
    assert client.get(f"/api/conversations/{chat['id']}").status_code == 200


@pytest.mark.parametrize('output', ['', 'x' * (OUTPUT_BYTES + 1)])
def test_invalid_model_output_records_failure_and_usage(client, monkeypatch, output):
    chat = create(client)
    monkeypatch.setattr(client.app.state.ai, 'conversation', lambda *args: (output, {'total_tokens': 100}))
    assert reply(client, chat['id']).status_code == 502
    persisted = client.get(f"/api/conversations/{chat['id']}").json()['turns'][0]
    assert persisted['status'] == 'failed' and persisted['output'] == ''
    assert client.get('/api/workspace').json()['usage'][0]['total_tokens'] == 100


def test_bounded_history_requires_explicit_reset(client, monkeypatch):
    chat = create(client)
    monkeypatch.setattr(client.app.state.ai, 'conversation', lambda *args: ('x' * HISTORY_BYTES, {'total_tokens': 100}))
    first = reply(client, chat['id']).json()
    assert first['status'] == 'succeeded'
    response = reply(client, chat['id'], 'reply-0002')
    assert response.status_code == 422 and 'history' in response.json()['detail']
    assert len(client.get('/api/workspace').json()['usage']) == 1
    assert reply(client, chat['id'], 'reply-0002', refresh_context=True).status_code == 200


def test_preflight_and_quota_failures_leave_no_partial_turn(client):
    chat = create(client)
    assert reply(client, chat['id'], budget=200).status_code == 422
    assert client.get(f"/api/conversations/{chat['id']}").json()['turns'] == []
    for _ in range(6):
        assert client.post('/api/tasks', json={'query': 'payment retries'}).status_code == 200
    assert reply(client, chat['id']).status_code == 429
    assert client.get(f"/api/conversations/{chat['id']}").json()['turns'] == []
    assert len(client.get('/api/workspace').json()['usage']) == 6


def test_conversation_limits_and_request_validation(client):
    chat = create(client)
    for i in range(2, 21):
        create(client, f'create-{i:04}')
    assert client.post('/api/conversations', json={'title': 'One too many', 'request_id': 'create-0021'}).status_code == 409
    assert reply(client, chat['id'], request_id='short').status_code == 422
    assert reply(client, chat['id'], role='security').status_code == 422
    assert client.post('/api/conversations', json={'title': 'Bad override', 'request_id': 'create-0021', 'actor': 'admin'}).status_code == 422


def test_turn_limit_is_checked_before_reserving_usage(client):
    chat = create(client)
    first = reply(client, chat['id']).json()
    def fill(state):
        item = state['conversations'][chat['id']]
        for i in range(11):
            turn = deepcopy(first)
            turn.update(id=f'RUN-test-{i}', request_id=f'old-reply-{i}')
            state['tasks'][turn['id']] = turn
            item['turn_ids'].append(turn['id'])
    client.app.state.store.mutate(client.cookies.get('contextos_session'), fill)
    assert reply(client, chat['id'], 'reply-0002', refresh_context=True).status_code == 409
    assert len(client.get('/api/workspace').json()['usage']) == 1


def test_history_sources_propagate_staleness_even_when_not_in_current_retrieval():
    state = d.seed()
    state['tasks']['test'] = {'manifest': {'sources': [], 'history_source_ids': ['ARC-001']}, 'stale': False}
    proposal = d.propose(state, 'dev', 'developer', {'context_id': 'ARC-001', 'base_revision': 1,
        'body': 'Updated architecture.', 'reason': 'Change', 'sources': []})
    d.review(state, 'designer', 'architect', proposal['id'], proposal['hash'], 'approve')
    assert state['tasks']['test']['stale']
