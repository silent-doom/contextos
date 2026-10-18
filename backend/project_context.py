"""Project-scoped read models over the canonical approved Markdown records.

No content is copied into the older workspace collection. HTTP, tasks and
conversations all resolve the same project revisions through this boundary.
"""
from copy import deepcopy

from backend import domain as d
from backend.api import service as pages

DOMAINS = {role: domain for domain, role in d.OWNERS.items()}


def contexts(state, project_id=None):
    if not project_id:
        return state['contexts']
    project = pages.project(state, project_id)
    return {doc['id']: {
        'id': doc['id'], 'project_id': project_id, 'title': pages.context_name(doc),
        'domain': DOMAINS[doc['owner_type']], 'body': doc['content'],
        'owner': doc['owner_type'], 'policy': 'Reviewed',
        # Project-wide requirements and security guardrails are deterministic,
        # rather than depending on a similarity score to reach the model.
        'mandatory': doc['owner_type'] in ('pm', 'security'),
        'dependencies': list(doc['dependency_versions']), 'revision': doc['version'],
        'status': 'accepted', 'freshness': pages.status(project, doc)['status'],
        'sources': [doc['filename']], 'updated_at': doc['updated_at'],
        'history': [{'revision': h['version'], 'body': h['content'],
                     'actor': h['approved_by'], 'at': h['updated_at'],
                     'reason': h['reason'], 'proposal_id': h['proposal_id']}
                    for h in doc['history']],
    } for doc in project['contexts'].values() if not doc['deleted']}


def view(state, project_id=None):
    """Read-only projection; mutations must use the canonical page service."""
    if not project_id:
        # Older workspaces remain isolated from newly created projects.
        return {**state,
                'tasks': {k: v for k, v in state['tasks'].items() if not v.get('project_id')},
                'conversations': {k: v for k, v in state.get('conversations', {}).items() if not v.get('project_id')},
                'events': [e for e in state['events'] if not e.get('project_id')],
                'usage': [u for u in state['usage'] if not u.get('project_id')]}
    project = pages.project(state, project_id)
    proposals = {}
    for p in project['proposals'].values():
        proposals[p['id']] = {
            **deepcopy(p), 'title': pages.context_name(p['candidate']),
            'domain': DOMAINS[p['reviewer_type']], 'review_role': p['reviewer_type'],
            'body': p['candidate']['content'], 'base_revision': p['base_version'],
            'status': 'published' if p['status'] == 'approved' else p['status'],
            'sources': [p['candidate']['filename']],
            'reviewer': p.get('reviewed_by'),
        }
    return {**state, 'project': pages.metadata(project),
            'contexts': contexts(state, project_id), 'proposals': proposals,
            'tasks': {k: v for k, v in state['tasks'].items() if v.get('project_id') == project_id},
            'conversations': {k: v for k, v in state.get('conversations', {}).items() if v.get('project_id') == project_id},
            'events': [e for e in state['events'] if e.get('project_id') == project_id],
            'usage': [u for u in state['usage'] if u.get('project_id') == project_id]}


def assemble(state, role, query, budget, project_id=None):
    if project_id:
        pages.project(state, project_id, active=True)
    selected = view(state, project_id)
    manifest = d.assemble(selected, role, query, budget)
    if project_id:
        manifest['project_id'] = project_id
        manifest['mandatory_revisions'] = {c['id']: c['revision'] for c in selected['contexts'].values() if c['mandatory']}
        manifest['context_warnings'] = [
            f"{source['id']} v{source['revision']} has changed dependencies; verify this decision before implementation."
            for source in manifest['sources'] if selected['contexts'][source['id']]['freshness'] == 'stale']
    return manifest


def stale(state, run):
    current = contexts(state, run.get('project_id'))
    mandatory_changed = ('mandatory_revisions' in run['manifest'] and
                         run['manifest']['mandatory_revisions'] != {
                             c['id']: c['revision'] for c in current.values() if c['mandatory']})
    return run.get('stale', False) or mandatory_changed or any(
        s['id'] not in current or current[s['id']]['revision'] != s['revision']
        for s in run['manifest']['sources'])


def propose(state, project_id, actor, role, action, data, context_id=None):
    result = pages.propose(pages.project(state, project_id), actor, action, data, context_id)
    d.audit(state, actor, 'Context change proposed', None,
            f"{pages.context_name(result['candidate'])} · {result['reason']}",
            role=role, project_id=project_id)
    return result


def review(state, project_id, actor, role, proposal_id, data):
    project = pages.project(state, project_id)
    result = pages.review(project, actor, role, proposal_id, data)
    if result['status'] == 'approved':
        accepted = contexts(state, project_id)
        affected = d.affected_contexts({'contexts': accepted}, result['context_id'])
        # A newly added/changed mandatory rule can affect work that did not
        # previously know it existed. Warn conservatively within this project.
        mandatory = result['candidate']['owner_type'] in ('pm', 'security')
        for run in state['tasks'].values():
            if run.get('project_id') != project_id:
                continue
            used = {s['id'] for s in run['manifest']['sources']} | set(run['manifest'].get('history_source_ids', []))
            if mandatory or used & affected:
                run['stale'] = True
                run.setdefault('context_changes', []).append({
                    'context_id': result['context_id'], 'title': pages.context_name(result['candidate']),
                    'revision': result['published_version'], 'reason': result['reason'],
                    'mandatory': mandatory, 'action': result['action']})
    d.audit(state, actor, 'Context revision published' if result['status'] == 'approved' else 'Proposal rejected',
            None, f"{pages.context_name(result['candidate'])} · proposed by {result['author']} · "
                  + (f"v{result['published_version']} · " if result['status'] == 'approved' else '') + result['reason'],
            role=role, project_id=project_id)
    return result
