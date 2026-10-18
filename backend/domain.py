"""Pure governed-memory domain. No HTTP or model authority here."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
import re
from uuid import uuid4

ROLES = ('pm', 'architect', 'developer', 'qa', 'security')
OWNERS = {'Requirements': 'pm', 'Architecture': 'architect', 'Implementation': 'developer', 'Quality': 'qa', 'Security': 'security'}


class Problem(Exception):
    def __init__(self, message, status=400, usage=None):
        self.message, self.status, self.usage = message, status, usage


def now():
    return datetime.now(timezone.utc).isoformat()


def uid(prefix):
    return f'{prefix}-{uuid4().hex[:10]}'


def estimate(text):
    # One UTF-8 byte per estimated token is intentionally conservative.
    return len(text.encode('utf-8'))


def visible(item, role):
    return item['policy'] != 'Restricted' or role == 'security'


def context(state, cid, role):
    item = state['contexts'].get(cid)
    if not item or not visible(item, role):
        raise Problem('Context not found or unavailable to this persona.', 404)
    return item


def audit(state, actor, action, cid, detail, *, role=None, outcome='completed', source_ids=None, private_role=None, private_actor=None, conversation_id=None):
    state['events'].append({'id': uid('EVT'), 'at': now(), 'actor': actor,
                            'role': role, 'action': action, 'context_id': cid,
                            'detail': detail, 'outcome': outcome,
                            'source_ids': list(source_ids or []), 'private_role': private_role,
                            'private_actor': private_actor, 'conversation_id': conversation_id})


def reserve_usage(state, role, sources, kind, *, private_actor=None, conversation_id=None):
    """Reserve every model attempt inside the caller's business transaction."""
    if len(state['usage']) >= 50:
        raise Problem('This workspace has reached its 50-call demo allowance. Export and start a new sandbox.', 429)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
    if sum(datetime.fromisoformat(u['at']) > cutoff for u in state['usage']) >= 6:
        raise Problem('Please wait a minute before making more model requests.', 429)
    call_id = uid('CALL')
    state['usage'].append({'id': call_id, 'at': now(), 'kind': kind, 'status': 'pending',
                           'source_ids': list(sources), 'private_role': role if kind in ('extraction', 'conversation') else None,
                           'private_actor': private_actor, 'conversation_id': conversation_id})
    return call_id


def finish_usage(state, call_id, usage=None, failed=False):
    entry = next(u for u in state['usage'] if u['id'] == call_id)
    entry.update(usage or {})
    entry['status'] = 'completed' if usage is not None and not failed else 'failed'


def seed():
    docs = [
        ('REQ-001', 'Safe payment retries', 'Requirements', 'Customers must never be charged twice when retrying a failed payment. Retry only transient failures. Declined cards are not retryable. Return the original result for repeated idempotency keys.', True, [], 'Reviewed'),
        ('ARC-001', 'Payment retry architecture', 'Architecture', 'Use one idempotency key per payment intent. Persist the result before responding. Retry transient provider failures up to 3 times with exponential backoff. A unique database constraint on the key prevents concurrent duplicate charges.', False, ['REQ-001', 'SEC-001'], 'Reviewed'),
        ('QA-001', 'Checkout acceptance scenarios', 'Quality', 'Test a provider timeout followed by success; concurrent requests with the same key; duplicate callback delivery; declined cards with no retry; exhausted retry attempts. Assert exactly one charge and stable response semantics.', False, ['REQ-001', 'ARC-001'], 'Reviewed'),
        ('SEC-001', 'Payment data guardrails', 'Security', 'Never log card numbers, credentials, or full payment tokens. Use synthetic fixtures in demonstrations. Enforce authorization before retrieval and before any mutation.', True, [], 'Reviewed'),
        ('IMP-001', 'Checkout API contract', 'Implementation', 'POST /payments accepts payment_intent_id and an Idempotency-Key header. Return the existing payment result when the key already exists. Trace every attempt using a correlation ID without sensitive data.', False, ['ARC-001'], 'Reviewed'),
        ('OPS-001', 'Release readiness', 'Implementation', 'Before rollout: confirm health probes, request timeouts, error-rate monitoring, and rollback documentation. Release checkout changes gradually and monitor duplicate-charge reports.', False, [], 'Reviewed'),
        ('RES-001', 'Internal security finding', 'Security', 'Synthetic restricted finding: a legacy diagnostic endpoint exposes test transaction metadata. Remove the endpoint before production rollout. Tracking reference INTERNAL-SEC-42.', False, ['SEC-001'], 'Restricted'),
    ]
    state = {'contexts': {}, 'proposals': {}, 'tasks': {}, 'events': [], 'usage': [], 'role': 'developer', 'project': {'name': 'Checkout reliability', 'description': 'One payment. One charge. A shared understanding.', 'id': 'checkout'}}
    for cid, title, domain, body, mandatory, deps, policy in docs:
        state['contexts'][cid] = {'id': cid, 'title': title, 'domain': domain, 'body': body, 'owner': OWNERS[domain], 'policy': policy, 'mandatory': mandatory, 'dependencies': deps, 'revision': 1, 'status': 'accepted', 'sources': ['Synthetic product workshop'], 'updated_at': now(), 'history': [{'revision': 1, 'body': body, 'actor': 'seed', 'at': now(), 'reason': 'Synthetic accepted demo baseline'}]}
    audit(state, 'system', 'Workspace created', 'REQ-001', 'Synthetic checkout project initialized.')
    return state


def empty_workspace():
    """Real accounts start with no synthetic project knowledge."""
    state = {'contexts': {}, 'proposals': {}, 'tasks': {}, 'events': [], 'usage': [],
             'role': 'developer', 'project': {'name': 'Your workspace', 'description': '', 'id': 'workspace'}}
    audit(state, 'system', 'Workspace created', None, 'Empty authenticated workspace initialized.')
    return state


def digest(proposal):
    return sha256(json.dumps({k: proposal[k] for k in ('context_id', 'base_revision', 'title', 'domain', 'body', 'reason', 'sources')}, sort_keys=True).encode()).hexdigest()


def propose(state, actor, role, data):
    cid = data.get('context_id')
    if cid:
        item = context(state, cid, role)
        if data['base_revision'] != item['revision']:
            raise Problem('The accepted version changed. Reload it and review your proposal again.', 409)
        title, domain = item['title'], item['domain']
    else:
        if len(state['contexts']) >= 30:
            raise Problem('The demo has reached its 30-context limit. Consolidate an existing topic.', 409)
        title, domain = data['title'], data['domain']
        if any(x['title'].casefold() == title.casefold() for x in state['contexts'].values()):
            raise Problem('That topic already exists. Propose an update to it instead.', 409)
    body = data['body'].strip()
    if not body or estimate(body) > 10000:
        raise Problem('Context must contain text and fit within 10,000 UTF-8 bytes.')
    if len([p for p in state['proposals'].values() if p['status'] == 'pending']) >= 50:
        raise Problem('Review pending proposals before creating more.', 409)
    proposal = {'id': uid('PRP'), 'context_id': cid, 'base_revision': data.get('base_revision', 0), 'title': title, 'domain': domain, 'body': body, 'reason': data['reason'], 'sources': data.get('sources', []), 'author': actor, 'author_role': role, 'status': 'pending', 'created_at': now()}
    proposal['hash'] = digest(proposal)
    state['proposals'][proposal['id']] = proposal
    audit(state, actor, 'Change proposed', cid, title, role=role)
    return deepcopy(proposal)


def affected_contexts(state, cid):
    affected = {cid}
    while True:
        expanded = affected | {k for k, v in state['contexts'].items() if set(v['dependencies']) & affected}
        if expanded == affected:
            return affected
        affected = expanded


def review(state, actor, role, pid, expected_hash, decision):
    p = state['proposals'].get(pid)
    if not p:
        raise Problem('Proposal not found.', 404)
    if p['context_id']:
        context(state, p['context_id'], role)
    if role != OWNERS[p['domain']]:
        raise Problem(f"Only the {OWNERS[p['domain']]} reviewer can decide this change.", 403)
    if p['author'] == actor:
        raise Problem('An independent reviewer must approve or reject this change.', 403)
    if p['hash'] != expected_hash or digest(p) != expected_hash:
        raise Problem('Proposal content does not match the reviewed version.', 409)
    if p['status'] != 'pending':
        raise Problem('This proposal has already been reviewed.', 409)
    if decision == 'reject':
        p.update(status='rejected', reviewer=actor, reviewed_at=now())
        audit(state, actor, 'Change rejected', p['context_id'], p['title'], role=role)
        return deepcopy(p)
    cid = p['context_id']
    if cid:
        item = context(state, cid, role)
        if item['revision'] != p['base_revision']:
            raise Problem('Stale proposal: another revision was published. Create a new proposal against the current version.', 409)
    else:
        if len(state['contexts']) >= 30 or any(x['title'].casefold() == p['title'].casefold() for x in state['contexts'].values()):
            raise Problem('Topic limit reached or this topic now exists. Reconcile before publishing.', 409)
        cid = uid('CTX')
        item = {'id': cid, 'title': p['title'], 'domain': p['domain'], 'owner': OWNERS[p['domain']], 'policy': 'Reviewed', 'mandatory': False, 'dependencies': [], 'revision': 0, 'history': [], 'status': 'accepted'}
        state['contexts'][cid] = item
        p['published_context_id'] = cid
    item.update(body=p['body'], revision=item['revision'] + 1, sources=p['sources'], updated_at=now())
    item['history'].append({'revision': item['revision'], 'body': item['body'], 'actor': actor, 'at': now(), 'reason': p['reason'], 'proposal_id': pid})
    p.update(status='published', reviewer=actor, reviewed_at=now())
    affected = affected_contexts(state, cid)
    for task in state['tasks'].values():
        source_ids = {s['id'] for s in task['manifest']['sources']} | set(task['manifest'].get('history_source_ids', []))
        if source_ids & affected:
            task['stale'] = True
    audit(state, actor, 'Revision published', cid, f"{item['title']} → v{item['revision']}", role=role)
    return deepcopy(p)


def source_payload(items):
    return json.dumps([{'id': x['id'], 'revision': x['revision'], 'title': x['title'], 'body': x['body']} for x in items], ensure_ascii=False, separators=(',', ':'))


def assemble(state, role, query, budget):
    allowed = [x for x in state['contexts'].values() if visible(x, role) and x['status'] == 'accepted']
    mandatory = [x for x in allowed if x['mandatory']]
    if estimate(source_payload(mandatory)) > budget:
        raise Problem('Mandatory constraints exceed this context budget. Increase the budget; no constraints were dropped.', 422)
    terms = set(re.findall(r'\w+', query.lower())) - {'the', 'a', 'to', 'and', 'for', 'of', 'with', 'what', 'how'}
    scored = [(len(terms & set(re.findall(r'\w+', (x['title'] + ' ' + x['body']).lower()))), x) for x in allowed if not x['mandatory']]
    scored.sort(key=lambda pair: (-pair[0], pair[1]['id']))
    selected = list(mandatory)
    for score, item in scored:
        if not score:
            continue
        closure = {item['id']}
        while True:
            more = closure | {dep for x in allowed if x['id'] in closure for dep in x['dependencies']}
            if more == closure:
                break
            closure = more
        # Do not include a document if any dependency is inaccessible.
        if not closure.issubset({x['id'] for x in allowed}):
            continue
        addition = [x for x in allowed if x['id'] in closure and x not in selected]
        if estimate(source_payload(selected + addition)) <= budget:
            selected.extend(addition)
    payload = source_payload(selected)
    return {'sources': json.loads(payload), 'context_payload': payload, 'estimated_tokens': estimate(payload), 'baseline_estimated_tokens': estimate(source_payload(allowed)), 'budget': budget, 'estimator': 'UTF-8 bytes (conservative upper-bound estimate, not model tokenization)', 'created_at': now()}


def task_visible(state, task, role, actor=None):
    if task.get('conversation_id') and (task['actor'] != actor or task['role'] != role):
        return False
    sources = {s['id'] for s in task['manifest']['sources']} | set(task['manifest'].get('history_source_ids', []))
    return all(cid in state['contexts'] and visible(state['contexts'][cid], role) for cid in sources)


def conversation_visible(state, conversation, role, actor):
    return bool(conversation and conversation['actor'] == actor and conversation['role'] == role
            and all(tid in state['tasks'] and task_visible(state, state['tasks'][tid], role, actor)
                    for tid in conversation['turn_ids']))


def snapshot(state, role, actor=None):
    allowed = {k: deepcopy(v) for k, v in state['contexts'].items() if visible(v, role)}
    proposals = [deepcopy(p) for p in state['proposals'].values() if not p['context_id'] or p['context_id'] in allowed]
    for p in proposals:
        item = allowed.get(p['context_id'])
        p['before'] = next((h['body'] for h in item['history'] if h['revision'] == p['base_revision']), '') if item else ''
    conversations = [deepcopy(c) for c in state.get('conversations', {}).values()
                     if conversation_visible(state, c, role, actor)]
    conversation_ids = {c['id'] for c in conversations}
    tasks = [deepcopy(t) for t in state['tasks'].values() if task_visible(state, t, role, actor)
             and t.get('status', 'succeeded') == 'succeeded'
             and (not t.get('conversation_id') or t['conversation_id'] in conversation_ids)]
    events = [deepcopy(e) for e in state['events']
              if (not e['context_id'] or e['context_id'] in allowed)
              and all(cid in allowed for cid in e.get('source_ids', []))
              and (not e.get('private_role') or e['private_role'] == role)
              and (not e.get('private_actor') or e['private_actor'] == actor)
              and (not e.get('conversation_id') or e['conversation_id'] in conversation_ids)]
    for event in events:
        legacy_role = event['actor'].removeprefix('demo-')
        if not event.get('role') and legacy_role in ROLES:
            event['role'] = legacy_role
    usage = [u for u in state['usage'] if all(cid in allowed for cid in u.get('source_ids', []))
             and (not u.get('private_role') or u['private_role'] == role)
             and (not u.get('private_actor') or u['private_actor'] == actor)
             and (not u.get('conversation_id') or u['conversation_id'] in conversation_ids)]
    return {'project': state['project'], 'role': role, 'contexts': list(allowed.values()), 'proposals': proposals,
            'tasks': tasks, 'conversations': conversations, 'events': events[-100:][::-1], 'usage': usage}


TASK_GOALS = {
    'pm': 'Define acceptance criteria for safe payment retries and declined-card messages',
    'architect': 'Review payment retry architecture and idempotency tradeoffs',
    'developer': 'Implement payment retries using the accepted API contract',
    'qa': 'Create tests for payment retries, duplicate requests and declined cards',
    'security': 'Review payment data guardrails and internal security findings',
}


def next_actions(state, role, actor):
    """Permission-scoped suggestions only; every execution keeps its normal gate."""
    view = snapshot(state, role, actor)
    actions = []
    owned = [p for p in view['proposals'] if p['status'] == 'pending'
             and OWNERS[p['domain']] == role and p['author'] != actor]
    if owned:
        actions.append({'kind': 'review', 'id': owned[0]['id'], 'label': 'Review proposal',
                        'title': owned[0]['title'], 'reason': 'You own this domain and can independently review it.'})
    stale = [t for t in view['tasks'] if t['role'] == role and t['stale']]
    if stale:
        actions.append({'kind': 'rerun', 'id': stale[-1]['id'], 'label': 'Review & refresh run',
                        'title': stale[-1]['query'], 'reason': 'Accepted sources changed. Inspect the old run before refreshing it.'})
    actions.append({'kind': 'task', 'label': 'Start task', 'title': TASK_GOALS[role],
                    'query': TASK_GOALS[role], 'reason': 'Use the latest accepted knowledge available to your persona.'})
    actions.append({'kind': 'create', 'label': 'Propose knowledge', 'title': 'Capture a decision',
                    'reason': 'Create a candidate for independent owner review.'})
    return actions
