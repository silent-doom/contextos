"""The same verifier runs against real HTTP or independent local API sessions."""
import argparse
import time

import pytest
from fastapi.testclient import TestClient

from backend.ai import AI
from backend.app import create_app
from backend.domain import empty_workspace
from backend.store import SQLiteStore
from backend.data.storage import MarkdownStorage
from scripts import verify_collaboration as verifier


@pytest.fixture
def collaboration(tmp_path, monkeypatch):
    import firebase_admin
    from firebase_admin import auth

    monkeypatch.setenv('AUTH_MODE', 'firebase')
    monkeypatch.setattr(firebase_admin, '_apps', {'test': object()})
    members = {
        'author-token': {'uid': 'developer-user', 'contextos_role': 'developer'},
        'reviewer-token': {'uid': 'architect-user', 'contextos_role': 'architect'},
    }
    for claims in members.values():
        claims.update(contextos_workspace='verification-team', auth_time=int(time.time()))

    def verified(token, check_revoked):
        assert check_revoked is True
        return dict(members[token.removeprefix('session-')])

    monkeypatch.setattr(auth, 'verify_id_token', verified)
    monkeypatch.setattr(auth, 'verify_session_cookie', verified)
    monkeypatch.setattr(auth, 'create_session_cookie', lambda token, expires_in: f'session-{token}')
    store = SQLiteStore(tmp_path / 'collaboration.db', initializer=empty_workspace)
    app = create_app(store, AI(mode='offline'), markdown_storage=MarkdownStorage(tmp_path / 'storage'))
    return lambda: TestClient(app), members, store


def test_two_independent_sessions_share_accepted_context_and_preserve_snapshots(collaboration):
    factory, _, store = collaboration
    evidence = verifier.verify(factory, 'author-token', 'reviewer-token', allow_offline=True)
    state = store.read('verification-team')
    topic = state['contexts'][evidence['context_id']]
    assert topic['revision'] == 2 and len(topic['history']) == 2
    original = state['tasks'][evidence['initial_run_id']]
    refreshed = state['tasks'][evidence['refreshed_run_id']]
    assert original['stale'] and not refreshed['stale']
    assert original['actor'] == refreshed['actor'] == 'architect-user'
    assert verifier.source_from(original, topic['id'])['revision'] == 1
    assert verifier.source_from(refreshed, topic['id'])['revision'] == 2
    assert evidence['offline_rehearsal'] is True
    signed_out = {event['actor'] for event in state['events'] if event['action'] == 'Signed out'}
    assert signed_out == {'developer-user', 'architect-user'}
    assert 'author-token' not in str(evidence) and 'reviewer-token' not in str(evidence)


def test_two_authenticated_members_use_the_same_knowledge_pages_in_private_work(collaboration):
    factory, members, store = collaboration
    author, reviewer = factory(), factory()
    for client, token in ((author, 'author-token'), (reviewer, 'reviewer-token')):
        client.headers.update({'Authorization': f'Bearer {token}', 'X-ContextOS-Client': 'workspace'})
    project = author.post('/api/context/projects', json={'name': 'Team handoff', 'project_type': 'Software'}).json()
    pid = project['id']
    base = f'/api/context/projects/{pid}'
    proposal = author.post(f'{base}/contexts', json={
        'name': 'Retry contract', 'filename': 'retries.md', 'owner': 'Designer', 'owner_type': 'architect',
        'content': '## Overview\n\nPayment retries.\n\n## Details\n\nAt most two attempts; preserve idempotency.\n\n## Next steps\n\nTest retry boundaries.',
        'reason': 'Approved provider agreement.'}).json()
    assert author.get('/api/workspace', params={'project_id': pid}).json()['contexts'] == []
    response = reviewer.post(f"{base}/proposals/{proposal['id']}/review", json={'hash': proposal['hash'], 'decision': 'approve'})
    assert response.status_code == 200, response.text
    chat = author.post('/api/conversations', json={'title': 'Implement retries', 'request_id': 'team-shared-context', 'project_id': pid}).json()
    result = author.post(f"/api/conversations/{chat['id']}/turns", json={'query': 'Implement payment retries', 'budget': 6000, 'request_id': 'team-first-message'}).json()
    assert result['manifest']['sources'][0]['id'] == proposal['context_id']
    assert 'two attempts' in result['output']
    assert reviewer.get(f"/api/conversations/{chat['id']}").status_code == 404
    assert reviewer.get('/api/workspace', params={'project_id': pid}).json()['tasks'] == []
    events = author.get('/api/workspace', params={'project_id': pid}).json()['events']
    publication = next(e for e in events if e['action'] == 'Context revision published')
    assert publication['actor'] == 'architect-user' and 'developer-user' in publication['detail']
    members['author-token']['contextos_workspace'] = 'other-team'
    assert author.get(f'{base}/contexts').status_code == 404
    assert author.get(f"/api/conversations/{chat['id']}").status_code == 404


@pytest.mark.parametrize('field,value,message', [
    ('uid', 'developer-user', 'distinct user'),
    ('contextos_role', 'developer', 'Developer author and Architect reviewer'),
    ('contextos_workspace', 'different-team', 'shared workspace membership'),
])
def test_wrong_accounts_cannot_pass_collaboration_verification(collaboration, field, value, message):
    factory, members, store = collaboration
    members['reviewer-token'][field] = value
    with pytest.raises(verifier.VerificationError, match=message):
        verifier.verify(factory, 'author-token', 'reviewer-token', allow_offline=True)
    state = store.read('verification-team')
    assert not state['contexts'] and not state['tasks']


def test_offline_is_never_accepted_as_live_evidence(collaboration):
    factory, _, store = collaboration
    with pytest.raises(verifier.VerificationError, match='Live AI is required'):
        verifier.verify(factory, 'author-token', 'reviewer-token')
    assert not store.read('verification-team')['usage']


def test_cli_does_not_print_credentials_from_transport_failures(monkeypatch, capsys):
    secret = 'private-verification-token'
    monkeypatch.setenv('CONTEXTOS_AUTHOR_ID_TOKEN', secret)
    monkeypatch.setenv('CONTEXTOS_REVIEWER_ID_TOKEN', secret + '-other')

    def failing_client(**kwargs):
        raise RuntimeError(f'Provider diagnostic containing {secret}')

    monkeypatch.setattr(verifier.httpx, 'Client', failing_client)
    assert verifier.main(['--base-url', 'https://staging.example.invalid']) == 1
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
    assert 'FAIL: Verification could not complete' in captured.err


@pytest.mark.parametrize('url', [
    'http://public.example.invalid', 'https://user:password@example.invalid',
    'https://example.invalid/?token=secret', 'https://example.invalid/#secret',
])
def test_cli_rejects_insecure_or_credential_bearing_origins(url):
    with pytest.raises(argparse.ArgumentTypeError):
        verifier.staging_url(url)
