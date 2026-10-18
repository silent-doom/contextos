from copy import deepcopy
import os
from pathlib import Path
import re
import secrets
from typing import Literal
from urllib.parse import urlsplit
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from backend import domain as d
from backend.ai import AI
from backend.store import make_store
from backend.conversations import ConversationService

ROOT = Path(__file__).resolve().parent.parent


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class ProposalInput(Input):
    context_id: str | None = None
    base_revision: int = Field(default=0, ge=0)
    title: str = Field(default='New requirement', min_length=1, max_length=120)
    domain: Literal['Requirements', 'Architecture', 'Implementation', 'Quality', 'Security'] = 'Requirements'
    body: str = Field(min_length=1, max_length=10000)
    reason: str = Field(min_length=1, max_length=1500)
    sources: list[str] = Field(default_factory=list, max_length=10)


class ReviewInput(Input):
    hash: str = Field(min_length=64, max_length=64)
    decision: Literal['approve', 'reject']


class TaskInput(Input):
    query: str = Field(min_length=3, max_length=2000)
    budget: int = Field(default=6000, ge=200, le=16000)


class ConversationInput(Input):
    title: str = Field(min_length=3, max_length=120)
    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{8,80}$')


class TurnInput(TaskInput):
    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{8,80}$')
    refresh_context: bool = False


class IngestInput(Input):
    notes: str = Field(min_length=10, max_length=8000)
    source: str = Field(min_length=1, max_length=200)


class ActivityInput(Input):
    action: Literal['context_viewed', 'manifest_inspected']
    target_id: str = Field(min_length=1, max_length=80)


class RoleInput(Input):
    role: Literal['pm', 'architect', 'developer', 'qa', 'security']


def create_app(store=None, ai=None):
    public_origin = os.getenv('PUBLIC_ORIGIN', '').rstrip('/')
    if public_origin:
        parsed = urlsplit(public_origin)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username
                or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise RuntimeError('PUBLIC_ORIGIN must be an absolute HTTP(S) origin without a path or credentials.')
    app = FastAPI(title='ContextOS', docs_url='/api/docs', redoc_url=None)
    app.state.store = store or make_store()
    app.state.ai = ai or AI()
    app.state.conversations = ConversationService(app.state.store, app.state.ai)
    auth_mode = os.getenv('AUTH_MODE', 'demo')
    if auth_mode not in ('demo', 'firebase'):
        raise RuntimeError('AUTH_MODE must be demo or firebase.')
    if auth_mode == 'firebase':
        import firebase_admin
        if not firebase_admin._apps:
            firebase_admin.initialize_app()

    @app.exception_handler(d.Problem)
    async def problem_handler(request, exc):
        identity_info = getattr(request.state, 'identity_info', None)
        # Rejected domain operations roll back their business transaction. Persist
        # the attributed failure separately, without request content or hidden IDs.
        if identity_info and request.method == 'POST' and not request.url.path.startswith('/api/demo/'):
            wid, actor, role = identity_info
            operation = request.url.path.split('/')[2]
            outcome = 'blocked' if exc.status in (403, 404, 409, 422, 429) else 'failed'
            try:
                app.state.store.mutate(wid, lambda s: d.audit(
                    s, actor, f'{operation.title()} {outcome}', None,
                    f'HTTP {exc.status}. The request did not complete.',
                    role=role, outcome=outcome, private_role=role,
                    private_actor=actor if operation == 'conversations' else None))
            except d.Problem:
                import logging
                logging.getLogger(__name__).warning('Audit append unavailable at workspace capacity.')
        return JSONResponse({'detail': exc.message}, status_code=exc.status)

    @app.middleware('http')
    async def boundary(request: Request, call_next):
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            if request.headers.get('x-contextos-client') != 'workspace':
                return JSONResponse({'detail': 'Missing same-origin client header.'}, status_code=403)
            origin = request.headers.get('origin')
            if origin and origin.rstrip('/') != (public_origin or str(request.base_url).rstrip('/')):
                return JSONResponse({'detail': 'Cross-origin writes are not allowed.'}, status_code=403)
            try:
                length = int(request.headers.get('content-length', '0'))
            except ValueError:
                return JSONResponse({'detail': 'Invalid request size.'}, status_code=400)
            if length > 40000:
                return JSONResponse({'detail': 'Request too large.'}, status_code=413)
            # Enforce the same cap when Content-Length is absent or inaccurate.
            body = await request.body()
            if len(body) > 40000:
                return JSONResponse({'detail': 'Request too large.'}, status_code=413)
        response = await call_next(request)
        if getattr(request.state, 'new_session', None):
            response.set_cookie('contextos_session', request.state.new_session, httponly=True, samesite='strict', secure=bool(os.getenv('K_SERVICE')), max_age=604800)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' https://identitytoolkit.googleapis.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.url.path.startswith('/api/') or request.url.path in ('/', '/knowledge') or request.url.path.startswith('/assets/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    def identity(request, response):
        if auth_mode == 'firebase':
            from backend.identity import verified_identity
            request.state.identity_info = verified_identity(request)
            return request.state.identity_info
        workspace = request.cookies.get('contextos_session', '')
        if not re.fullmatch(r'[a-f0-9]{64}', workspace):
            workspace = secrets.token_hex(32)
            request.state.new_session = workspace
        state = app.state.store.read(workspace)
        role = state['role']
        request.state.identity_info = (workspace, f'demo-{role}', role)
        return request.state.identity_info

    def reserve(workspace, role, sources, kind):
        return app.state.store.mutate(workspace, lambda state: d.reserve_usage(state, role, sources, kind))

    from backend.identity import register_auth_routes
    register_auth_routes(app, auth_mode)

    @app.get('/api/demo/scenarios')
    def demo_scenarios(request: Request, response: Response):
        identity(request, response)
        if auth_mode != 'demo':
            raise d.Problem('Synthetic scenarios are available only in demo mode.', 403)
        from backend.demo import SCENARIOS
        return {'scenarios': SCENARIOS}

    @app.post('/api/demo/scenarios/{scenario_id}')
    def demo_scenario(scenario_id: str, request: Request, response: Response):
        identity(request, response)
        if auth_mode != 'demo':
            raise d.Problem('Synthetic scenarios are available only in demo mode.', 403)
        from backend.demo import run_scenario
        return run_scenario(scenario_id)

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'ai_mode': app.state.ai.mode, 'auth_mode': auth_mode}

    @app.get('/api/workspace')
    def workspace(request: Request, response: Response):
        wid, actor, role = identity(request, response)
        current = app.state.store.read(wid)
        result = d.snapshot(current, role, actor)
        result.update(actor=actor, ai_mode=app.state.ai.mode, auth_mode=auth_mode,
                      next_actions=d.next_actions(current, role, actor), context_pages_enabled=True)
        return result

    @app.post('/api/persona')
    def persona(data: RoleInput, request: Request, response: Response):
        wid, actor, previous_role = identity(request, response)
        if auth_mode != 'demo':
            raise d.Problem('Persona switching is only available in the synthetic demo.', 403)
        def switch(s):
            s.update(role=data.role)
            d.audit(s, actor, 'Persona switched', None, f'{previous_role} → {data.role}', role=previous_role)
        app.state.store.mutate(wid, switch)
        return {'role': data.role}

    @app.post('/api/proposals')
    def proposals(data: ProposalInput, request: Request, response: Response):
        wid, actor, role = identity(request, response)
        if any(len(source) > 300 for source in data.sources):
            raise d.Problem('Source labels must be at most 300 characters.')
        return app.state.store.mutate(wid, lambda s: d.propose(s, actor, role, data.model_dump()))

    @app.post('/api/proposals/{pid}/review')
    def review(pid: str, data: ReviewInput, request: Request, response: Response):
        wid, actor, role = identity(request, response)
        return app.state.store.mutate(wid, lambda s: d.review(s, actor, role, pid, data.hash, data.decision))

    @app.post('/api/assemble')
    def assemble(data: TaskInput, request: Request, response: Response):
        wid, actor, role = identity(request, response)
        def assemble_context(s):
            result = d.assemble(s, role, data.query, data.budget)
            d.audit(s, actor, 'Context assembled', None, f"{len(result['sources'])} accepted sources selected.",
                    role=role, source_ids=[x['id'] for x in result['sources']])
            return result
        return app.state.store.mutate(wid, assemble_context)

    @app.post('/api/conversations')
    def create_conversation(data: ConversationInput, request: Request, response: Response):
        wid, actor, role = identity(request, response)
        return app.state.conversations.create(wid, actor, role, data.title, data.request_id)

    @app.get('/api/conversations')
    def list_conversations(request: Request, response: Response):
        wid, actor, role = identity(request, response)
        return {'conversations': app.state.conversations.list(wid, actor, role)}

    @app.get('/api/conversations/{cid}')
    def get_conversation(cid: str, request: Request, response: Response):
        wid, actor, role = identity(request, response)
        return app.state.conversations.get(wid, cid, actor, role)

    @app.post('/api/conversations/{cid}/turns')
    def conversation_turn(cid: str, data: TurnInput, request: Request, response: Response):
        wid, actor, role = identity(request, response)
        turn = app.state.conversations.reply(wid, cid, actor, role, **data.model_dump())
        response.status_code = 202 if turn['status'] == 'pending' else 200
        return turn

    @app.post('/api/tasks')
    def task(data: TaskInput, request: Request, response: Response):
        wid, actor, role = identity(request, response)
        manifest = d.assemble(app.state.store.read(wid), role, data.query, data.budget)
        call_id = reserve(wid, role, [x['id'] for x in manifest['sources']], 'task')
        usage = None
        try:
            output, usage = app.state.ai.task(role, data.query, manifest)
            run = {'id': d.uid('RUN'), 'query': data.query, 'role': role, 'actor': actor, 'output': output, 'manifest': manifest, 'usage': usage, 'created_at': d.now(), 'stale': False}
            def save(s):
                run['stale'] = any(s['contexts'][x['id']]['revision'] != x['revision'] for x in manifest['sources'])
                s['tasks'][run['id']] = deepcopy(run)
                d.finish_usage(s, call_id, usage)
                d.audit(s, actor, 'Task completed', None, f"Run {run['id']} · {len(manifest['sources'])} sources",
                        role=role, source_ids=[x['id'] for x in manifest['sources']])
            app.state.store.mutate(wid, save)
            return run
        except Exception as exc:
            def failed(s):
                d.finish_usage(s, call_id, usage or getattr(exc, 'usage', None), failed=True)
                d.audit(s, actor, 'Model processing failed', None, 'Inspect usage and retry when available.',
                        role=role, outcome='failed', private_role=role)
            app.state.store.mutate(wid, failed)
            raise

    @app.post('/api/ingest')
    def ingest(data: IngestInput, request: Request, response: Response):
        wid, actor, role = identity(request, response)
        call_id = reserve(wid, role, [], 'extraction')
        usage = None
        try:
            candidate, usage = app.state.ai.extract(data.notes)
            # Domain validation remains independent of the model's structured output.
            validated = ProposalInput(**candidate, sources=[data.source])
            def save(s):
                result = d.propose(s, actor, role, validated.model_dump())
                d.finish_usage(s, call_id, usage)
                d.audit(s, actor, 'Notes extracted', result.get('context_id'), 'Candidate sent for independent review.',
                        role=role, private_role=role)
                return result
            return app.state.store.mutate(wid, save)
        except Exception as exc:
            def failed(s):
                d.finish_usage(s, call_id, usage or getattr(exc, 'usage', None), failed=True)
                d.audit(s, actor, 'Model processing failed', None, 'Inspect usage and retry when available.',
                        role=role, outcome='failed', private_role=role)
            app.state.store.mutate(wid, failed)
            raise

    @app.get('/api/export')
    def export(request: Request, response: Response):
        wid, actor, role = identity(request, response)
        def export_visible(s):
            d.audit(s, actor, 'Evidence exported', None, 'Exported the persona-visible workspace.', role=role, private_role=role)
            result = d.snapshot(s, role, actor)
            for item in result['conversations']:
                item['turns'] = [deepcopy(s['tasks'][tid]) for tid in item['turn_ids']]
            return result
        return app.state.store.mutate(wid, export_visible)

    @app.post('/api/activity')
    def activity(data: ActivityInput, request: Request, response: Response):
        wid, actor, role = identity(request, response)
        def record(s):
            if data.action == 'context_viewed':
                item = d.context(s, data.target_id, role)
                d.audit(s, actor, 'Context inspected', item['id'], f"{item['title']} · v{item['revision']}", role=role)
            else:
                task = s['tasks'].get(data.target_id)
                if (not task or not d.task_visible(s, task, role, actor)
                        or task.get('conversation_id') and not d.conversation_visible(
                            s, s.get('conversations', {}).get(task['conversation_id'], {}), role, actor)):
                    raise d.Problem('Run not found or unavailable.', 404)
                d.audit(s, actor, 'Manifest inspected', None, f"Run {data.target_id}", role=role,
                        source_ids=[x['id'] for x in task['manifest']['sources']] + task['manifest'].get('history_source_ids', []),
                        private_role=role if task.get('conversation_id') else None,
                        private_actor=actor if task.get('conversation_id') else None,
                        conversation_id=task.get('conversation_id'))
            return {'recorded': True}
        return app.state.store.mutate(wid, record)

    from backend.api.main import create_router
    app.include_router(create_router(workspace), prefix='/api/context', tags=['Shared knowledge'])

    @app.get('/favicon.ico', include_in_schema=False)
    def favicon():
        return FileResponse(ROOT / 'web' / 'favicon.svg', media_type='image/svg+xml')

    @app.get('/knowledge', include_in_schema=False)
    @app.get('/')
    def index():
        return FileResponse(ROOT / 'web' / 'index.html')

    app.mount('/assets', StaticFiles(directory=ROOT / 'web'), name='assets')
    return app


app = create_app()
