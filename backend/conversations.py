"""Application service for private task conversations over the workspace store."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

from backend import domain as d
from backend import project_context as pc
from backend.api import service as pages

MAX_CONVERSATIONS = 20
MAX_TURNS = 12
HISTORY_BYTES = 16000
OUTPUT_BYTES = 24000
ATTEMPT_SECONDS = 120


def conversation(state, cid, actor, role):
    item = state.get('conversations', {}).get(cid)
    if not item or not d.conversation_visible(state, item, role, actor):
        raise d.Problem('Conversation not found or unavailable.', 404)
    return item


def stale(state, turn):
    return pc.stale(state, turn)


class ConversationService:
    """Coordinate transactions and model calls without giving the model authority."""

    def __init__(self, store, ai):
        self.store, self.ai = store, ai

    def create(self, workspace, actor, role, title, request_id, project_id=None):
        def save(state):
            if project_id:
                pages.project(state, project_id, active=True)
            items = state.setdefault('conversations', {})
            existing = next((c for c in items.values() if c['actor'] == actor and c['role'] == role
                             and c['request_id'] == request_id), None)
            if existing:
                if existing['title'] != title or existing.get('project_id') != project_id:
                    raise d.Problem('This request ID was already used with a different title.', 409)
                return deepcopy(conversation(state, existing['id'], actor, role))
            if len(items) >= MAX_CONVERSATIONS:
                raise d.Problem('This workspace has reached its 20-conversation limit.', 409)
            item = {'id': d.uid('CHAT'), 'project_id': project_id, 'actor': actor, 'role': role, 'title': title,
                    'request_id': request_id, 'turn_ids': [], 'created_at': d.now(), 'updated_at': d.now()}
            items[item['id']] = item
            d.audit(state, actor, 'Conversation created', None, item['id'], role=role,
                    private_role=role, private_actor=actor, conversation_id=item['id'], project_id=project_id)
            return deepcopy(item)
        return self.store.mutate(workspace, save)

    def get(self, workspace, cid, actor, role):
        state = self.store.read(workspace)
        item = deepcopy(conversation(state, cid, actor, role))
        item['turns'] = [deepcopy(state['tasks'][tid]) for tid in item['turn_ids']]
        return item

    def list(self, workspace, actor, role):
        state = self.store.read(workspace)
        return [deepcopy(c) for c in state.get('conversations', {}).values()
                if d.conversation_visible(state, c, role, actor)]

    def _begin(self, state, cid, actor, role, query, budget, request_id, refresh_context, project_id=None):
        item = conversation(state, cid, actor, role)
        if item.get('project_id'):
            pages.project(state, item['project_id'], active=True)
        if project_id is not None and project_id != item.get('project_id'):
            raise d.Problem('This conversation belongs to a different project.', 409)
        turns = [state['tasks'][tid] for tid in item['turn_ids']]
        existing = next((turn for turn in turns if turn['request_id'] == request_id), None)
        if existing:
            if (existing['query'], existing['manifest']['budget'], existing['refresh_context']) != (query, budget, refresh_context):
                raise d.Problem('This request ID was already used with different turn input.', 409)
            if existing['status'] == 'succeeded':
                return deepcopy(existing), False
            if (existing['status'] == 'pending'
                    and datetime.fromisoformat(existing['lease_expires_at']) > datetime.now(timezone.utc)):
                return deepcopy(existing), False
            if existing['id'] != item['turn_ids'][-1]:
                raise d.Problem('Only the latest unfinished turn can be retried.', 409)
            if existing['status'] == 'pending':
                d.finish_usage(state, existing['attempt_id'], failed=True)
            turn = existing
        else:
            if turns and turns[-1]['status'] != 'succeeded':
                raise d.Problem('Wait for the pending turn or retry the failed turn with the same request ID.', 409)
            if len(turns) >= MAX_TURNS:
                raise d.Problem('This conversation has reached its 12-turn limit. Start a new task.', 409)
            history = []
            for previous in turns:
                if previous['refresh_context']:
                    history = []
                history.append(previous)
            if not refresh_context and any(stale(state, previous) for previous in history):
                raise d.Problem('Accepted context changed. Confirm refresh_context to continue with current sources and reset working history.', 409)
            if refresh_context:
                history = []
            working = [{'turn_id': t['id'], 'query': t['query'], 'output': t['output']} for t in history]
            history_bytes = d.estimate(json.dumps(working, ensure_ascii=False, separators=(',', ':')))
            if history_bytes > HISTORY_BYTES:
                raise d.Problem('Working history exceeds 16,000 UTF-8 bytes. Explicitly refresh context to start a new working segment.', 422)
            retrieval_query = ' '.join([t['query'] for t in history] + [query])
            manifest = pc.assemble(state, role, retrieval_query, budget, item.get('project_id'))
            manifest.update(history_turn_ids=[t['id'] for t in history], history_estimated_tokens=history_bytes,
                            history_budget=HISTORY_BYTES,
                            history_source_ids=sorted({s['id'] for t in history for s in t['manifest']['sources']}))
            turn = {'id': d.uid('RUN'), 'project_id': item.get('project_id'), 'conversation_id': cid, 'request_id': request_id,
                    'actor': actor, 'role': role, 'query': query, 'manifest': manifest,
                    'refresh_context': refresh_context, 'output': '', 'usage': {},
                    'created_at': d.now(), 'stale': False, 'attempts': 0}
            state['tasks'][turn['id']] = turn
            item['turn_ids'].append(turn['id'])
        source_ids = sorted({s['id'] for s in turn['manifest']['sources']}
                            | set(turn['manifest']['history_source_ids']))
        turn['attempt_id'] = d.reserve_usage(state, role, source_ids, 'conversation',
                                            private_actor=actor, conversation_id=cid, project_id=item.get('project_id'))
        turn.update(status='pending', error=None, attempts=turn['attempts'] + 1,
                    lease_expires_at=(datetime.now(timezone.utc) + timedelta(seconds=ATTEMPT_SECONDS)).isoformat())
        item['updated_at'] = d.now()
        d.audit(state, actor, 'Conversation turn started', None, turn['id'], role=role,
                source_ids=source_ids, private_role=role, private_actor=actor, conversation_id=cid, project_id=item.get('project_id'))
        return deepcopy(turn), True

    def _finish(self, state, turn, output, usage, failed):
        current = state['tasks'][turn['id']]
        superseded = current['attempt_id'] != turn['attempt_id']
        d.finish_usage(state, turn['attempt_id'], usage, failed=failed or superseded)
        if superseded:
            return  # An expired attempt cannot overwrite a newer attempt's result.
        current.update(status='failed' if failed else 'succeeded', output='' if failed else output,
                       usage=usage or {}, error='The reply could not complete. Retry this turn.' if failed else None,
                       lease_expires_at=None, stale=stale(state, current))
        state['conversations'][turn['conversation_id']]['updated_at'] = d.now()
        d.audit(state, turn['actor'], 'Conversation turn failed' if failed else 'Conversation turn completed',
                None, turn['id'], role=turn['role'], outcome='failed' if failed else 'completed',
                source_ids=[s['id'] for s in turn['manifest']['sources']] + turn['manifest']['history_source_ids'],
                private_role=turn['role'], private_actor=turn['actor'], conversation_id=turn['conversation_id'], project_id=turn.get('project_id'))

    def reply(self, workspace, cid, actor, role, query, budget, request_id, refresh_context=False, project_id=None):
        turn, execute = self.store.mutate(workspace, lambda state: self._begin(
            state, cid, actor, role, query, budget, request_id, refresh_context, project_id))
        if execute:
            usage = None
            try:
                state = self.store.read(workspace)
                conversation(state, cid, actor, role)  # Recheck access before sending history to the model.
                history = [{'turn_id': tid, 'query': state['tasks'][tid]['query'], 'output': state['tasks'][tid]['output']}
                           for tid in turn['manifest']['history_turn_ids']]
                output, usage = self.ai.conversation(role, query, turn['manifest'], history)
                if not isinstance(output, str) or not output.strip() or d.estimate(output) > OUTPUT_BYTES:
                    raise d.Problem('The reply was empty or exceeded the stored-output limit.', 502)
                self.store.mutate(workspace, lambda state: self._finish(state, turn, output, usage, False))
            except Exception as exc:
                self.store.mutate(workspace, lambda state: self._finish(
                    state, turn, '', usage or getattr(exc, 'usage', None), True))
                if isinstance(exc, d.Problem):
                    raise
                raise d.Problem('The reply could not complete. Retry this turn.', 502) from exc
        current = self.get(workspace, cid, actor, role)
        return next(t for t in current['turns'] if t['id'] == turn['id'])
