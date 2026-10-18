"""Simple project/context rules over the host's transactional workspace store.

The context_projects key holds this prototype's records. The database provider,
schema, authentication and legacy task workflows stay with the host application.
"""
from copy import deepcopy
import hashlib
import json
import re
from backend.domain import Problem, now, uid
from backend.api.markdown import validate


def projects(state):
    return state.get('context_projects', {})


def project(state, project_id, active=False):
    item = projects(state).get(project_id)
    if item is None:
        raise Problem('Project not found or unavailable.', 404)
    if active and item['archived']:
        raise Problem('Restore this archived project before making changes.', 409)
    return item


def context(item, context_id, include_deleted=False):
    doc = item['contexts'].get(context_id)
    if doc is None or (doc['deleted'] and not include_deleted):
        raise Problem('Context not found or unavailable.', 404)
    return doc


def metadata(item):
    return {key: value for key, value in item.items() if key not in ('contexts', 'proposals', 'events', '_access_scope')}


def log(item, actor, action, target):
    item['events'].append({'at': now(), 'actor': actor, 'action': action, 'target_id': target})


def create_project(state, actor, data):
    records = state.setdefault('context_projects', {})
    if sum(not item.get('metadata_missing') for item in records.values()) >= 10:
        raise Problem('Prototype limit: 10 registered projects.', 409)
    item = {'id': uid('PRJ'), **data, 'admin': actor, 'version': 1, 'archived': False,
            'created_at': now(), 'updated_at': now(), 'contexts': {}, 'proposals': {}, 'events': []}
    records[item['id']] = item
    log(item, actor, 'project_created', item['id'])
    return metadata(item)


def update_project(item, actor, data):
    if item.get('metadata_missing'):
        raise Problem('Restore this project\'s missing metadata before making changes.', 409)
    if actor != item['admin']:
        raise Problem('Only the project admin can edit or archive this project.', 403)
    if data.pop('expected_version') != item['version']:
        raise Problem('Project changed. Reload before editing.', 409)
    item.update(data, version=item['version'] + 1, updated_at=now())
    log(item, actor, 'project_updated', item['id'])
    return metadata(item)


def dependency_versions(item, relationships):
    return {link['target_id']: context(item, link['target_id'])['version'] for link in relationships if link['kind'] == 'depends_on'}


def relationship_versions(item, relationships):
    return {link['target_id']: context(item, link['target_id'])['version'] for link in relationships}


def reviewed_versions(item, record):
    """Read old baselines without changing approved history or proposal hashes."""
    if 'relationship_versions' in record:
        return record['relationship_versions']
    versions = dict(record.get('dependency_versions', {}))
    source = record.get('candidate', record)
    stamp = record.get('updated_at', record['created_at'])
    for link in source['relationships']:
        target_id = link['target_id']
        if target_id not in versions:
            target = item['contexts'].get(target_id, {})
            accepted = [entry['version'] for entry in target.get('history', []) if entry['updated_at'] <= stamp]
            versions[target_id] = max(accepted, default=None)
    return versions


def context_name(doc):
    if doc.get('name'):
        return doc['name']
    label = re.sub(r'[_-]+', ' ', doc['filename'][:-3]).strip()
    return label[:1].upper() + label[1:]


def validate_candidate(item, candidate, context_id):
    name = candidate['filename']
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *[f'COM{i}' for i in range(1, 10)], *[f'LPT{i}' for i in range(1, 10)]}
    if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_. -]*\.md', name, re.I)
            or '..' in name or name.split('.')[0].upper() in reserved):
        raise Problem('Use a plain .md filename with letters, numbers, spaces, underscores or hyphens; no paths.', 422)
    if any(doc['id'] != context_id and not doc['deleted'] and doc['filename'].casefold() == name.casefold() for doc in item['contexts'].values()):
        raise Problem('A context with this filename already exists in this project.', 409)
    validate(candidate['content'])
    links = candidate['relationships']
    if len({link['target_id'] for link in links}) != len(links):
        raise Problem('Choose one relationship per target context.', 422)
    for link in links:
        if link['target_id'] == context_id:
            raise Problem('A context cannot relate to itself.', 422)
        context(item, link['target_id'])
    graph = {doc['id']: [link['target_id'] for link in doc['relationships'] if link['kind'] == 'depends_on'] for doc in item['contexts'].values() if not doc['deleted']}
    graph[context_id] = [link['target_id'] for link in links if link['kind'] == 'depends_on']
    visited = set()
    def visit(node, path):
        if node in path:
            raise Problem('Dependency relationships cannot form a cycle.', 422)
        if node in visited:
            return
        for target in graph.get(node, []):
            visit(target, path | {node})
        visited.add(node)
    visit(context_id, set())


def proposal_hash(proposal):
    keys = ('id', 'project_id', 'action', 'context_id', 'base_version', 'candidate', 'dependency_versions', 'reason', 'author', 'reviewer_type')
    if 'relationship_versions' in proposal:
        keys += ('relationship_versions',)
    return hashlib.sha256(json.dumps({key: proposal[key] for key in keys}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def propose(item, actor, action, data, context_id=None):
    if item.get('metadata_missing'):
        raise Problem('Restore this project\'s missing metadata before making changes.', 409)
    if item['archived']:
        raise Problem('Restore this archived project before proposing changes.', 409)
    if sum(p['status'] == 'pending' for p in item['proposals'].values()) >= 50:
        raise Problem('Review pending proposals before adding more.', 409)
    previous = context(item, context_id) if context_id else None
    base_version = data.get('expected_version', 0)
    if previous and base_version != previous['version']:
        raise Problem('Accepted version changed. Reload before proposing.', 409)
    if action == 'create' and len(item['contexts']) >= 30:
        raise Problem('Prototype limit: 30 contexts per project, including deleted history.', 409)
    context_id = context_id or uid('CTX')
    source = previous if action == 'delete' else data
    candidate = {key: deepcopy(source[key]) for key in ('filename', 'content', 'owner', 'owner_type', 'relationships')}
    candidate['name'] = source.get('name') or context_name(previous or candidate)
    validate_candidate(item, candidate, context_id)
    proposal = {'id': uid('PROP'), 'project_id': item['id'], 'action': action, 'context_id': context_id,
                'base_version': base_version, 'candidate': candidate, 'reason': data['reason'], 'author': actor,
                'reviewer_type': previous['owner_type'] if previous else candidate['owner_type'],
                'dependency_versions': dependency_versions(item, candidate['relationships']),
                'relationship_versions': relationship_versions(item, candidate['relationships']),
                'created_at': now(), 'status': 'pending'}
    proposal['hash'] = proposal_hash(proposal)
    item['proposals'][proposal['id']] = proposal
    log(item, actor, f'context_{action}_proposed', context_id)
    return proposal


def review(item, actor, role, proposal_id, data):
    proposal = item['proposals'].get(proposal_id)
    if not proposal:
        raise Problem('Proposal not found or unavailable.', 404)
    if actor == proposal['author'] or role != proposal['reviewer_type']:
        raise Problem(f"An independent {proposal['reviewer_type']} reviewer must decide this proposal.", 403)
    if proposal['status'] != 'pending':
        raise Problem('This proposal has already been decided.', 409)
    if proposal['hash'] != data['hash'] or proposal_hash(proposal) != data['hash']:
        raise Problem('Proposal does not match the content reviewed. Reload it.', 409)
    if data['decision'] == 'approve':
        if item['archived']:
            raise Problem('Restore this project before publishing.', 409)
        old = item['contexts'].get(proposal['context_id'])
        if (old and (old['deleted'] or old['version'] != proposal['base_version'])) or (not old and proposal['base_version'] != 0):
            raise Problem('Stale proposal. Create a new proposal against the accepted version.', 409)
        if not old and len(item['contexts']) >= 30:
            raise Problem('Prototype context limit reached.', 409)
        validate_candidate(item, proposal['candidate'], proposal['context_id'])
        baseline = reviewed_versions(item, proposal)
        if relationship_versions(item, proposal['candidate']['relationships']) != baseline:
            raise Problem('A related context changed since this proposal. Create a fresh proposal.', 409)
        if proposal['action'] == 'delete' and any(link['target_id'] == proposal['context_id'] for doc in item['contexts'].values() if not doc['deleted'] for link in doc['relationships']):
            raise Problem('Other contexts still link here. Approve removal of those relationships first.', 409)
        stamp = now()
        doc = {'id': proposal['context_id'], 'project_id': item['id'], **deepcopy(proposal['candidate']),
               'version': proposal['base_version'] + 1, 'deleted': proposal['action'] == 'delete',
               'created_at': old['created_at'] if old else stamp, 'updated_at': stamp,
               'dependency_versions': deepcopy(proposal['dependency_versions']),
               'relationship_versions': deepcopy(baseline), 'history': deepcopy(old['history']) if old else []}
        revision = {key: deepcopy(value) for key, value in doc.items() if key != 'history'}
        revision.update(approved_by=actor, proposal_id=proposal['id'], reason=proposal['reason'])
        doc['history'].append(revision)
        item['contexts'][doc['id']] = doc
        proposal['published_version'] = doc['version']
    proposal.update(status='approved' if data['decision'] == 'approve' else 'rejected', reviewed_by=actor, reviewed_at=now())
    item['updated_at'] = now()
    log(item, actor, f"proposal_{proposal['status']}", proposal_id)
    return proposal


def status(item, doc, known_version=None):
    changed, visited = [], {doc['id']}
    def walk(current):
        baseline = reviewed_versions(item, current)
        for link in current['relationships']:
            target_id = link['target_id']
            # Reference cycles are allowed; a page's own revision is not an upstream change.
            if target_id == doc['id']:
                continue
            version = baseline.get(target_id)
            target = item['contexts'].get(target_id)
            reason = ('missing' if not target else 'deleted' if target['deleted'] else
                      'untracked' if version is None else 'version_changed' if target['version'] != version else None)
            if reason:
                changed.append({'source_id': current['id'], 'source_name': context_name(current),
                                'target_id': target_id, 'target_name': context_name(target) if target else target_id,
                                'kind': link['kind'], 'reviewed_version': version,
                                'current_version': target['version'] if target else None, 'reason': reason})
            if target and not target['deleted'] and target_id not in visited:
                visited.add(target_id)
                walk(target)
    walk(doc)
    freshness = 'deleted' if doc['deleted'] else 'stale' if changed else 'up_to_date'
    return {'id': doc['id'], 'version': doc['version'], 'status': freshness, 'up_to_date': freshness == 'up_to_date',
            'requires_review': freshness == 'stale',
            'status_label': {'up_to_date': 'Up to date', 'stale': 'Requires review', 'deleted': 'Deleted'}[freshness],
            'changed_relationships': changed, 'changed_dependencies': sorted({link['target_id'] for link in changed}),
            'known_version': known_version,
            'known_version_current': None if known_version is None else known_version == doc['version'],
            'pending_proposals': sum(p['context_id'] == doc['id'] and p['status'] == 'pending' for p in item['proposals'].values())}


def context_metadata(item, doc):
    return {**{key: value for key, value in doc.items() if key not in ('content', 'history')},
            'name': context_name(doc), **status(item, doc)}


def graph(item):
    nodes = [context_metadata(item, doc) for doc in item['contexts'].values() if not doc['deleted']]
    return {'nodes': nodes, 'edges': [{'source_id': doc['id'], **link} for doc in nodes for link in doc['relationships']]}
