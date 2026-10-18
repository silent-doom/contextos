"""Real HTTP and MCP workflow checks against an isolated transactional memory store."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import pytest
import uvicorn
from fastapi.testclient import TestClient
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from backend import domain as d
from backend.app import create_app
from backend.ai import AI
from backend.data.storage import MarkdownStorage


class MemoryStore:
    def __init__(self):
        self.states = {}

    def mutate(self, workspace, operation):
        state = deepcopy(self.states.get(workspace)) or d.seed()
        result = deepcopy(operation(state))
        self.states[workspace] = state
        return result

    def read(self, workspace):
        return self.mutate(workspace, lambda state: state)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTH_MODE', 'demo')
    with TestClient(create_app(store=MemoryStore(), ai=AI(mode='offline'), markdown_storage=MarkdownStorage(tmp_path / 'storage')), headers={'X-ContextOS-Client': 'workspace'}) as client:
        yield client


def create_project(client, name='Prototype'):
    response = client.post('/api/context/projects', json={'name': name, 'project_type': 'software', 'description': 'Project metadata'})
    assert response.status_code == 201, response.text
    return response.json()


def base(project):
    return '/api/context/projects/' + project['id']


def candidate(client, filename='architecture.md', **overrides):
    return {'filename': filename, 'content': client.get('/api/context/template').json()['content'].replace('## Overview', '## Overview\n\n**Approved knowledge** and evidence'),
            'owner': 'Architecture team', 'owner_type': 'architect', 'relationships': [], 'reason': 'Capture shared knowledge', **overrides}


def approve(client, project, proposal, role='architect'):
    client.post('/api/persona', json={'role': role})
    response = client.post(base(project) + '/proposals/' + proposal['id'] + '/review', json={'hash': proposal['hash'], 'decision': 'approve'})
    client.post('/api/persona', json={'role': 'developer'})
    assert response.status_code == 200, response.text
    return response.json()


def publish(client, project, filename='architecture.md', **overrides):
    response = client.post(base(project) + '/contexts', json=candidate(client, filename, **overrides))
    assert response.status_code == 201, response.text
    proposal = response.json()
    approve(client, project, proposal)
    return client.get(base(project) + '/contexts/' + proposal['context_id']).json()


def replacement(doc, **overrides):
    return {**{key: doc[key] for key in ('filename', 'content', 'owner', 'owner_type', 'relationships')},
            'expected_version': doc['version'], 'reason': 'New evidence', **overrides}


def test_context_names_are_separate_reviewed_searchable_and_versioned(client):
    project = create_project(client)
    doc = publish(client, project, 'internal-001.md', name='System Architecture')
    path = base(project) + '/contexts/' + doc['id']
    assert doc['name'] == 'System Architecture'
    assert client.get(base(project) + '/graph').json()['nodes'][0]['name'] == doc['name']
    assert client.get(base(project) + '/search?q=System+Architecture').json()['total'] == 1
    proposal = client.put(path, json=replacement(doc, name='Platform Design')).json()
    assert client.get(path).json()['name'] == 'System Architecture'
    assert client.get(base(project) + '/proposals').json()[0]['name'] == 'Platform Design'
    approve(client, project, proposal)
    assert client.get(path).json()['name'] == 'Platform Design'
    assert client.get(path + '/versions/1').json()['name'] == 'System Architecture'
    assert [row['name'] for row in client.get(path + '/versions').json()] == ['Platform Design', 'System Architecture']
    assert 'internal-001.md' in client.get(path + '/markdown').headers['content-disposition']
    current = client.get(path).json()
    # Older clients omitting name must not erase an accepted display name.
    next_proposal = client.put(path, json=replacement(current)).json()
    assert next_proposal['candidate']['name'] == 'Platform Design'
    for invalid in ('', '   ', 'x' * 121):
        assert client.put(path, json=replacement(current, name=invalid)).status_code == 422


def test_pre_name_records_and_pending_proposals_need_no_migration(client):
    from backend.api import service as s
    state = {}
    project = s.create_project(state, 'author', {'name': 'Legacy', 'project_type': 'software'})
    item = s.project(state, project['id'])
    proposal = s.propose(item, 'author', 'create', candidate(client, 'system-architecture.md'))
    # Simulate an immutable proposal written before display names existed.
    proposal['candidate'].pop('name')
    proposal['hash'] = s.proposal_hash(proposal)
    original = deepcopy(proposal)
    assert s.context_name(proposal['candidate']) == 'System architecture'
    assert proposal == original
    s.review(item, 'reviewer', 'architect', proposal['id'], {'hash': proposal['hash'], 'decision': 'approve'})
    doc = s.context(item, proposal['context_id'])
    original_history = deepcopy(doc['history'])
    assert s.context_metadata(item, doc)['name'] == 'System architecture'
    update = s.propose(item, 'author', 'update', replacement(doc, name='System Architecture'), doc['id'])
    s.review(item, 'reviewer', 'architect', update['id'], {'hash': update['hash'], 'decision': 'approve'})
    assert item['contexts'][doc['id']]['history'][0] == original_history[0]


def test_projects_start_empty_have_metadata_and_admin_crud(client):
    assert client.get('/api/context/projects').json() == []
    project = create_project(client)
    assert project['admin'] == 'demo-developer' and project['created_at'] and project['version'] == 1
    assert client.get(base(project)).json()['contexts'] == []
    change = {**{key: project[key] for key in ('name', 'project_type', 'description', 'admin')}, 'expected_version': 1}
    client.post('/api/persona', json={'role': 'pm'})
    assert client.put(base(project), json=change).status_code == 403
    client.post('/api/persona', json={'role': 'developer'})
    changed = client.put(base(project), json={**change, 'name': 'Renamed'}).json()
    assert changed['version'] == 2 and changed['name'] == 'Renamed'
    assert client.put(base(project), json=change).status_code == 409
    assert client.request('DELETE', base(project), json={'expected_version': 2, 'reason': 'Archive'}).status_code == 200
    assert client.get('/api/context/projects').json() == []
    archived = client.get('/api/context/projects?include_archived=true').json()[0]
    assert archived['archived']
    assert client.post(base(project) + '/contexts', json=candidate(client)).status_code == 409
    restore = {**change, 'expected_version': 3, 'archived': False}
    assert client.put(base(project), json=restore).json()['archived'] is False


def test_context_create_is_proposal_independent_role_approves_exact_hash(client):
    project = create_project(client)
    proposal = client.post(base(project) + '/contexts', json=candidate(client)).json()
    path = base(project) + '/proposals/' + proposal['id']
    assert proposal['status'] == 'pending'
    assert client.get(base(project)).json()['contexts'] == []
    assert client.post(path + '/review', json={'hash': proposal['hash'], 'decision': 'approve'}).status_code == 403
    client.post('/api/persona', json={'role': 'architect'})
    assert client.post(path + '/review', json={'hash': '0' * 64, 'decision': 'approve'}).status_code == 409
    assert client.post(path + '/review', json={'hash': proposal['hash'], 'decision': 'approve'}).status_code == 200
    assert client.post(path + '/review', json={'hash': proposal['hash'], 'decision': 'approve'}).status_code == 409
    doc = client.get(base(project) + '/contexts/' + proposal['context_id']).json()
    assert doc['filename'] == 'architecture.md' and doc['owner_type'] == 'architect' and doc['version'] == 1
    assert client.get(base(project) + '/proposals').json()[0]['filename'] == doc['filename']
    assert 'candidate' not in client.get(base(project) + '/proposals').json()[0]


def test_author_cannot_review_even_when_their_role_matches(client):
    project = create_project(client)
    content = candidate(client, owner_type='developer')['content']
    content = content.replace('## Details', '## Details\n\n```markdown\n## A heading inside code\n```')
    response = client.post(base(project) + '/contexts', json=candidate(client, content=content, owner_type='developer'))
    assert response.status_code == 201
    proposal = response.json()
    path = base(project) + '/proposals/' + proposal['id'] + '/review'
    for decision in ('approve', 'reject'):
        assert client.post(path, json={'hash': proposal['hash'], 'decision': decision}).status_code == 403


def test_owner_role_transfer_requires_current_owner_role_and_independence(client):
    project = create_project(client)
    doc = publish(client, project)
    proposal = client.put(base(project) + '/contexts/' + doc['id'], json=replacement(doc, owner='Security team', owner_type='security')).json()
    assert proposal['reviewer_type'] == 'architect'
    client.post('/api/persona', json={'role': 'security'})
    path = base(project) + '/proposals/' + proposal['id'] + '/review'
    assert client.post(path, json={'hash': proposal['hash'], 'decision': 'approve'}).status_code == 403
    approve(client, project, proposal)
    assert client.get(base(project) + '/contexts/' + doc['id']).json()['owner_type'] == 'security'


def test_stale_proposals_conflict_and_history_preserves_every_field(client):
    project = create_project(client)
    doc = publish(client, project)
    path = base(project) + '/contexts/' + doc['id']
    one = client.put(path, json=replacement(doc, owner='First owner')).json()
    two = client.put(path, json=replacement(doc, filename='renamed.md')).json()
    assert client.get(path).json()['owner'] == doc['owner']
    approve(client, project, one)
    client.post('/api/persona', json={'role': 'architect'})
    assert client.post(base(project) + '/proposals/' + two['id'] + '/review', json={'hash': two['hash'], 'decision': 'approve'}).status_code == 409
    assert client.get(path + '/versions/1').json()['owner'] == doc['owner']
    assert client.get(path + '/versions/2').json()['owner'] == 'First owner'
    assert client.get(path + '/versions/1').json()['content'] == doc['content']
    assert 'content' not in client.get(path + '/versions').json()[0]
    assert client.get(path + '/status?known_version=1').json()['known_version_current'] is False


def test_context_deletion_requires_approval_retains_history_and_can_be_rejected(client):
    project = create_project(client)
    doc = publish(client, project)
    path = base(project) + '/contexts/' + doc['id']
    proposal = client.request('DELETE', path, json={'expected_version': 1, 'reason': 'No longer needed'}).json()
    assert client.get(path).status_code == 200
    client.post('/api/persona', json={'role': 'architect'})
    assert client.post(base(project) + '/proposals/' + proposal['id'] + '/review', json={'hash': proposal['hash'], 'decision': 'reject'}).json()['status'] == 'rejected'
    client.post('/api/persona', json={'role': 'developer'})
    proposal = client.request('DELETE', path, json={'expected_version': 1, 'reason': 'Confirmed removal'}).json()
    approve(client, project, proposal)
    assert client.get(path).status_code == 404
    assert client.get(path + '/status').json()['status'] == 'deleted'
    assert client.get(path + '/versions/1').json()['content'] == doc['content']
    assert client.get(path + '/versions/2').json()['deleted']


def test_relationship_freshness_propagates_and_refresh_is_reviewed(client):
    project = create_project(client)
    first = publish(client, project, 'requirements.md')
    second = publish(client, project, 'design.md', relationships=[{'target_id': first['id'], 'kind': 'depends_on'}])
    third = publish(client, project, 'implementation.md', relationships=[{'target_id': second['id'], 'kind': 'depends_on'}])
    reference = publish(client, project, 'notes.md', relationships=[{'target_id': first['id'], 'kind': 'references'}])
    unrelated = publish(client, project, 'unrelated.md')
    root = base(project)
    proposal = client.put(root + '/contexts/' + first['id'], json=replacement(first, content=first['content'].replace('evidence', 'new evidence'))).json()
    assert client.get(root + '/contexts/' + reference['id'] + '/status').json()['requires_review'] is False
    approve(client, project, proposal)
    assert client.get(root + '/contexts/' + second['id'] + '/status').json()['status'] == 'stale'
    assert client.get(root + '/contexts/' + third['id'] + '/status').json()['status'] == 'stale'
    state = client.get(root + '/contexts/' + reference['id'] + '/status').json()
    assert state['requires_review'] and not state['up_to_date'] and state['status_label'] == 'Requires review'
    assert state['changed_relationships'] == [{'source_id': reference['id'], 'source_name': reference['name'],
        'target_id': first['id'], 'target_name': first['name'], 'kind': 'references',
        'reviewed_version': 1, 'current_version': 2, 'reason': 'version_changed'}]
    assert client.get(root + '/contexts/' + unrelated['id'] + '/status').json()['status_label'] == 'Up to date'
    assert {node['id'] for node in client.get(root + '/impact/' + first['id']).json()['contexts']} == {second['id'], third['id'], reference['id']}
    # Every current-context JSON surface exposes the same review data.
    path = root + '/contexts/' + reference['id']
    rows = [client.get(path).json(), client.get(path + '/sections').json(),
            client.post(path + '/extract', json={}).json(),
            next(row for row in client.get(root).json()['contexts'] if row['id'] == reference['id']),
            next(row for row in client.get(root + '/contexts').json()['items'] if row['id'] == reference['id']),
            client.get(root + '/search?q=notes').json()['items'][0],
            next(row for row in client.get(root + '/graph').json()['nodes'] if row['id'] == reference['id'])]
    for row in rows:
        for field in ('status', 'status_label', 'up_to_date', 'requires_review', 'changed_relationships'):
            assert row[field] == state[field]
    refresh = client.put(root + '/contexts/' + second['id'], json=replacement(second)).json()
    assert client.get(root + '/contexts/' + second['id'] + '/status').json()['requires_review']
    approve(client, project, refresh)
    assert client.get(root + '/contexts/' + second['id'] + '/status').json()['up_to_date']
    assert not client.get(root + '/contexts/' + third['id'] + '/status').json()['up_to_date']
    assert client.get(root + '/contexts/' + second['id'] + '/status').json()['changed_relationships'] == []
    rejected = client.put(path, json=replacement(reference)).json()
    client.post('/api/persona', json={'role': 'architect'})
    assert client.post(root + '/proposals/' + rejected['id'] + '/review', json={'hash': rejected['hash'], 'decision': 'reject'}).status_code == 200
    assert client.get(path + '/status').json()['requires_review']


@pytest.mark.parametrize('kind', ['depends_on', 'references'])
def test_changed_dependency_blocks_publication_and_linked_deletion(client, kind):
    project = create_project(client)
    source = publish(client, project, 'source.md')
    pending = client.post(base(project) + '/contexts', json=candidate(client, 'consumer.md', relationships=[{'target_id': source['id'], 'kind': kind}])).json()
    update = client.put(base(project) + '/contexts/' + source['id'], json=replacement(source)).json()
    approve(client, project, update)
    client.post('/api/persona', json={'role': 'architect'})
    assert client.post(base(project) + '/proposals/' + pending['id'] + '/review', json={'hash': pending['hash'], 'decision': 'approve'}).status_code == 409
    client.post('/api/persona', json={'role': 'developer'})
    publish(client, project, 'linked.md', relationships=[{'target_id': source['id'], 'kind': 'references'}])
    deletion = client.request('DELETE', base(project) + '/contexts/' + source['id'], json={'expected_version': 2, 'reason': 'Remove source'}).json()
    client.post('/api/persona', json={'role': 'architect'})
    assert client.post(base(project) + '/proposals/' + deletion['id'] + '/review', json={'hash': deletion['hash'], 'decision': 'approve'}).status_code == 409


def test_legacy_reference_baselines_use_history_without_changing_old_records(client):
    from backend.api import service as s
    state = {}
    item = s.project(state, s.create_project(state, 'author', {'name': 'Legacy', 'project_type': 'software'})['id'])
    def accepted(filename, **overrides):
        proposal = s.propose(item, 'author', 'create', candidate(client, filename, **overrides))
        proposal.pop('relationship_versions')
        proposal['hash'] = s.proposal_hash(proposal)
        s.review(item, 'reviewer', 'architect', proposal['id'], {'hash': proposal['hash'], 'decision': 'approve'})
        doc = item['contexts'][proposal['context_id']]
        doc.pop('relationship_versions')
        doc['history'][0].pop('relationship_versions')
        return doc
    source = accepted('source.md')
    linked = accepted('notes.md', relationships=[{'target_id': source['id'], 'kind': 'references'}])
    before = deepcopy(item)
    assert not s.status(item, linked)['requires_review']
    assert item == before
    pending = s.propose(item, 'author', 'update', replacement(linked), linked['id'])
    pending.pop('relationship_versions')
    pending['hash'] = s.proposal_hash(pending)
    change = s.propose(item, 'author', 'update', replacement(source), source['id'])
    s.review(item, 'reviewer', 'architect', change['id'], {'hash': change['hash'], 'decision': 'approve'})
    assert s.status(item, linked)['changed_relationships'][0]['reviewed_version'] == 1
    assert s.status(item, linked)['requires_review']
    with pytest.raises(d.Problem):
        s.review(item, 'reviewer', 'architect', pending['id'], {'hash': pending['hash'], 'decision': 'approve'})
    assert item['contexts'][linked['id']]['history'] == before['contexts'][linked['id']]['history']


def test_reference_cycles_terminate_and_missing_baselines_require_review(client):
    from backend.api import service as s
    project = create_project(client)
    first = publish(client, project, 'first.md')
    second = publish(client, project, 'second.md', relationships=[{'target_id': first['id'], 'kind': 'references'}])
    change = client.put(base(project) + '/contexts/' + first['id'], json=replacement(first, relationships=[{'target_id': second['id'], 'kind': 'references'}])).json()
    approve(client, project, change)
    assert not client.get(base(project) + '/contexts/' + first['id'] + '/status').json()['requires_review']
    assert client.get(base(project) + '/contexts/' + second['id'] + '/status').json()['requires_review']
    item = next(iter(client.app.state.store.states.values()))['context_projects'][project['id']]
    doc = deepcopy(item['contexts'][second['id']])
    doc['relationship_versions'] = {}
    result = s.status(item, doc)
    assert result['requires_review'] and result['changed_relationships'][0]['reason'] == 'untracked'
    missing = deepcopy(item)
    missing['contexts'].pop(first['id'])
    assert s.status(missing, doc)['changed_relationships'][0]['reason'] == 'missing'


def test_structure_safe_filenames_relationship_boundaries_and_cycles(client):
    project = create_project(client)
    for filename in ('../escape.md', 'C:\\escape.md', 'a.md\r\nHeader.md', 'CON.md'):
        assert client.post(base(project) + '/contexts', json=candidate(client, filename)).status_code == 422
    assert client.post(base(project) + '/contexts', json=candidate(client, content='# Unstructured')).status_code == 422
    assert client.post(base(project) + '/contexts', json=candidate(client, content='## Overview\nx\n## Next steps\nx\n## Details\nx')).status_code == 422
    first = publish(client, project, 'first.md')
    assert client.post(base(project) + '/contexts', json=candidate(client, 'FIRST.md')).status_code == 409
    second = publish(client, project, 'second.md', relationships=[{'target_id': first['id'], 'kind': 'depends_on'}])
    assert client.put(base(project) + '/contexts/' + first['id'], json=replacement(first, relationships=[{'target_id': second['id'], 'kind': 'depends_on'}])).status_code == 422
    another = create_project(client, 'Other')
    assert client.post(base(another) + '/contexts', json=candidate(client, relationships=[{'target_id': first['id']}])).status_code == 404
    assert client.get(base(another) + '/contexts/' + first['id']).status_code == 404


def test_extract_search_download_graph_and_audit_are_versioned(client):
    project = create_project(client)
    doc = publish(client, project)
    path = base(project) + '/contexts/' + doc['id']
    assert client.get(base(project) + '/search?q=approved+knowledge&limit=1').json()['total'] == 1
    parts = client.get(path + '/sections').json()['sections']
    result = client.post(path + '/extract', json={'section_keys': [parts[0]['key']], 'query': 'knowledge', 'max_chars': 25}).json()
    assert result['version'] == 1 and len(result['content']) == 25 and result['truncated']
    assert client.post(path + '/extract', json={'section_keys': ['bad']}).status_code == 422
    assert len(client.get(path + '?max_chars=4').json()['content']) == 4
    assert client.get(path + '/markdown').text == doc['content']
    assert 'attachment;' in client.get(path + '/markdown').headers['content-disposition']
    assert client.get(base(project) + '/graph').json()['nodes'][0]['status'] == 'up_to_date'
    assert client.get(base(project) + '/activity').json()[0]['action'] == 'proposal_approved'
    assert client.get(base(project) + '/contexts?offset=-1').status_code == 422
    assert client.post(base(project) + '/contexts', json=candidate(client, 'another.md'), headers={'Origin': 'https://other.invalid'}).status_code == 403


def test_proposal_hash_binds_owner_filename_relationships_and_content(client):
    from backend.api.service import proposal_hash
    project = create_project(client)
    proposal = client.post(base(project) + '/contexts', json=candidate(client)).json()
    for key, value in [('name', 'Other Display Name'), ('filename', 'other.md'), ('content', 'tampered'), ('owner', 'other'), ('owner_type', 'security'), ('relationships', [{'target_id': 'other', 'kind': 'references'}])]:
        altered = deepcopy(proposal)
        altered['candidate'][key] = value
        assert proposal_hash(altered) != proposal['hash']
    altered = deepcopy(proposal)
    altered['relationship_versions']['other'] = 2
    assert proposal_hash(altered) != proposal['hash']


def test_workspace_isolation_and_firebase_trusted_identity(monkeypatch, tmp_path):
    import firebase_admin
    from firebase_admin import auth
    monkeypatch.setenv('AUTH_MODE', 'firebase')
    monkeypatch.setattr(firebase_admin, '_apps', {'test': object()})
    def verify(token, check_revoked):
        assert check_revoked
        if token not in ('one', 'two', 'reviewer'):
            raise ValueError('Bad signature')
        return {'uid': token, 'contextos_workspace': 'other' if token == 'two' else 'team',
                'contextos_role': 'architect' if token == 'reviewer' else 'developer'}
    monkeypatch.setattr(auth, 'verify_id_token', verify)
    with TestClient(create_app(store=MemoryStore(), ai=AI(mode='offline'), markdown_storage=MarkdownStorage(tmp_path / 'storage')), headers={'X-ContextOS-Client': 'workspace'}) as client:
        assert client.get('/api/context/projects').status_code == 401
        client.headers['Authorization'] = 'Bearer one'
        assert client.post('/api/context/projects/samples', json={}).status_code == 403
        project = create_project(client)
        proposal = client.post(base(project) + '/contexts', json=candidate(client)).json()
        client.headers['Authorization'] = 'Bearer two'
        assert client.get('/api/context/projects').json() == []
        for suffix in ('', '/graph', '/proposals', '/activity'):
            assert client.get(base(project) + suffix).status_code == 404
        assert client.post(base(project) + '/proposals/' + proposal['id'] + '/review', json={'hash': proposal['hash'], 'decision': 'approve'}).status_code == 404
        client.headers['Authorization'] = 'Bearer reviewer'
        assert client.post(base(project) + '/proposals/' + proposal['id'] + '/review', json={'hash': proposal['hash'], 'decision': 'approve'}).status_code == 200


def test_markdown_files_are_saved_for_proposals_and_approved_versions(client):
    project = create_project(client)
    storage = client.app.state.markdown_storage.root
    assert list(storage.rglob('*.md')) == []
    proposal = client.post(base(project) + '/contexts', json=candidate(client)).json()
    assert len(list(storage.rglob('candidate.md'))) == 1
    assert (storage / 'projects' / project['id'] / 'proposals' / proposal['id'] / 'candidate.md').is_file()
    assert not (storage / 'workspaces').exists()
    assert list(storage.rglob('v*.md')) == []
    assert client.get(base(project) + '/contexts').json()['total'] == 0
    approve(client, project, proposal)
    path = base(project) + '/contexts/' + proposal['context_id']
    original = client.get(path).json()
    first = next(storage.rglob('v000001-*.md'))
    assert first.read_text(encoding='utf-8') == original['content']
    change = client.put(path, json=replacement(original, content=original['content'] + '\nNew evidence.')).json()
    assert not list(storage.rglob('v000002-*.md'))
    approve(client, project, change)
    assert first.read_text(encoding='utf-8') == original['content']
    assert len(list(storage.rglob('v000002-*.md'))) == 1
    assert client.get(path + '/versions/1').json()['content'] == original['content']
    first.write_text('Unreviewed disk change', encoding='utf-8')
    assert client.get(path + '/versions/1').status_code == 409


def test_storage_failure_does_not_commit_a_proposal(client, monkeypatch):
    from backend.domain import Problem
    project = create_project(client)
    def fail(*args):
        raise Problem('Markdown storage is unavailable.', 503)
    monkeypatch.setattr(client.app.state.markdown_storage, 'sync', fail)
    assert client.post(base(project) + '/contexts', json=candidate(client)).status_code == 503
    assert client.get(base(project) + '/proposals').json() == []


def test_two_sample_projects_are_idempotent_and_workspace_isolated(client):
    first = client.post('/api/context/projects/samples', json={})
    assert first.status_code == 200
    projects = first.json()
    assert [item['name'] for item in projects] == ['Checkout Reliability', 'Research Assistant']
    assert client.post('/api/context/projects/samples', json={}).json() == projects
    assert len(client.get('/api/context/projects').json()) == 2
    context_ids = []
    for project in projects:
        details = client.get(base(project)).json()
        assert len(details['contexts']) == 4 and details['relationships']
        context_ids.extend(doc['id'] for doc in details['contexts'])
    assert len(set(context_ids)) == 8
    storage = client.app.state.markdown_storage.root
    assert len(list(storage.rglob('v*.md'))) == 8
    client.cookies.clear()
    assert client.get('/api/context/projects').json() == []
    assert client.get(base(projects[0])).status_code == 404
    other = client.post('/api/context/projects/samples', json={}).json()
    assert {item['id'] for item in other}.isdisjoint(item['id'] for item in projects)
    assert {path.name for path in (storage / 'projects').iterdir()} == {item['id'] for item in projects + other}
    assert not (storage / 'workspaces').exists()


def test_real_mcp_stdio_creates_empty_project_and_proposes_context(client):
    with socket.socket() as port_socket:
        port_socket.bind(('127.0.0.1', 0))
        port = port_socket.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(client.app, host='127.0.0.1', port=port, log_level='error'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(.02)
        assert server.started
        async def run():
            params = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).resolve().parents[2] / 'mcp' / 'server.py')],
                env={**os.environ, 'CONTEXT_API_URL': f'http://127.0.0.1:{port}', 'CONTEXT_API_TOKEN': ''})
            async with stdio_client(params) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    tools = {tool.name for tool in (await session.list_tools()).tools}
                    assert len(tools) == 22 and 'delete_context' in tools and 'approve_proposal' not in tools
                    async def call(name, arguments):
                        result = await session.call_tool(name, arguments)
                        assert not result.isError, result
                        return result.structuredContent or json.loads(result.content[0].text)
                    result = await call('create_project', {'project': {'name': 'MCP project', 'project_type': 'research'}})
                    project_id = result['id']
                    assert (await call('read_project', {'project_id': project_id}))['contexts'] == []
                    template = await call('get_context_template', {})
                    proposal = await call('create_context', {'project_id': project_id, 'context': {'name': 'Research Findings', 'filename': 'research.md', 'content': template['content'], 'owner': 'Research team', 'owner_type': 'architect', 'reason': 'Agent evidence'}})
                    assert proposal['status'] == 'pending'
                    proposed_context = (await call('read_context_proposal', {'project_id': project_id, 'proposal_id': proposal['id']}))['candidate']
                    assert proposed_context['filename'] == 'research.md'
                    assert proposed_context['name'] == 'Research Findings'
                    assert (await call('discover_context', {'project_id': project_id}))['total'] == 0
                    # Publish test fixtures with an independent reviewer; agents have no approval tool.
                    from backend.api import service as s
                    store = client.app.state.store
                    workspace = next(wid for wid, state in store.states.items() if project_id in s.projects(state))
                    def accept(proposal):
                        store.mutate(workspace, lambda state: s.review(s.project(state, project_id), 'test-reviewer', 'architect',
                            proposal['id'], {'hash': proposal['hash'], 'decision': 'approve'}))
                    accept(proposal)
                    source_id = proposal['context_id']
                    reference = await call('create_context', {'project_id': project_id, 'context': {
                        **proposed_context, 'name': 'Research Summary', 'filename': 'summary.md',
                        'relationships': [{'target_id': source_id, 'kind': 'references'}], 'reason': 'Summarize findings'}})
                    accept(reference)
                    linked_id = reference['context_id']
                    args = {'project_id': project_id, 'context_id': linked_id}
                    assert (await call('get_context_status', args))['status_label'] == 'Up to date'
                    update = await call('update_context', {'project_id': project_id, 'context_id': source_id,
                        'changes': {**proposed_context, 'expected_version': 1, 'reason': 'New findings',
                                    'content': template['content'].replace('## Details', '## Details\n\nNew evidence.')}})
                    accept(update)
                    state = await call('get_context_status', args)
                    assert state['requires_review'] and state['status_label'] == 'Requires review'
                    assert state['changed_relationships'][0]['target_id'] == source_id
                    assert state['changed_relationships'][0]['current_version'] == 2
                    rows = [await call('read_context', args), await call('read_context_sections', args),
                            await call('extract_context', {**args, 'selection': {}})]
                    for name, arguments, field in [
                        ('read_project', {'project_id': project_id}, 'contexts'),
                        ('discover_context', {'project_id': project_id}, 'items'),
                        ('search_context', {'project_id': project_id, 'query': 'summary'}, 'items'),
                        ('read_context_graph', {'project_id': project_id}, 'nodes'),
                        ('inspect_context_impact', {'project_id': project_id, 'context_id': source_id}, 'contexts')]:
                        rows.append(next(row for row in (await call(name, arguments))[field] if row['id'] == linked_id))
                    for row in rows:
                        assert row['requires_review'] and row['status_label'] == state['status_label']
                        assert row['changed_relationships'] == state['changed_relationships']
        asyncio.run(run())
    finally:
        server.should_exit = True
        thread.join(timeout=10)
