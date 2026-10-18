"""HTTP surface for projects, approved Markdown, relationships and proposals."""
from fastapi import APIRouter, Depends, Query, Request, Response
from backend.api import models, service as s
from backend.api.markdown import HEADINGS, TEMPLATE, sections
from backend.domain import Problem


def create_router(workspace_endpoint, demo_mode=False):
    router = APIRouter(dependencies=[Depends(workspace_endpoint)])

    def read(request):
        wid, actor, role = request.state.identity_info
        return request.app.state.project_store.read(wid)

    def mutate(request, operation):
        wid, actor, role = request.state.identity_info
        return request.app.state.project_store.mutate(wid, lambda state: operation(state, actor, role))

    def markdown_content(request, item, doc):
        return request.app.state.project_store.content(item['id'], doc)

    def get_project(request, project_id):
        return s.project(read(request), project_id)

    def get_context(request, project_id, context_id, include_deleted=False):
        project = get_project(request, project_id)
        return project, s.context(project, context_id, include_deleted)

    @router.get('/template')
    def template():
        return {'headings': HEADINGS, 'content': TEMPLATE}

    @router.get('/projects')
    def projects(request: Request, include_archived: bool = False):
        return [s.metadata(item) for item in s.projects(read(request)).values() if include_archived or not item['archived']]

    @router.post('/projects', status_code=201)
    def create_project(body: models.NewProject, request: Request):
        return mutate(request, lambda state, actor, role: s.create_project(state, actor, body.model_dump()))

    @router.post('/projects/samples')
    def sample_projects(request: Request):
        if not demo_mode:
            raise Problem('Sample projects are available only in demo mode.', 403)
        raise Problem('Sample project creation is disabled. Create a project explicitly.', 409)

    @router.get('/projects/{project_id}')
    def project(project_id: str, request: Request):
        item = get_project(request, project_id)
        graph = s.graph(item)
        return {'project': s.metadata(item), 'contexts': graph['nodes'], 'relationships': graph['edges'],
                'actor': request.state.identity_info[1], 'role': request.state.identity_info[2]}

    @router.put('/projects/{project_id}')
    def update_project(project_id: str, body: models.ProjectUpdate, request: Request):
        return mutate(request, lambda state, actor, role: s.update_project(s.project(state, project_id), actor, body.model_dump()))

    @router.delete('/projects/{project_id}')
    def archive_project(project_id: str, body: models.Delete, request: Request):
        return mutate(request, lambda state, actor, role: s.update_project(s.project(state, project_id), actor, {'expected_version': body.expected_version, 'archived': True}))

    @router.get('/projects/{project_id}/contexts')
    def contexts(project_id: str, request: Request, q: str = Query(default='', max_length=500),
                 offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=100)):
        item = get_project(request, project_id)
        terms = q.casefold().split()
        rows = [s.context_metadata(item, doc) for doc in item['contexts'].values()
                if not doc['deleted'] and all(term in (s.context_name(doc) + ' ' + doc['filename'] + ' ' + doc['content'] + ' ' + doc['owner']).casefold() for term in terms)]
        return {'items': rows[offset:offset + limit], 'total': len(rows)}

    router.add_api_route('/projects/{project_id}/search', contexts, methods=['GET'])

    @router.post('/projects/{project_id}/contexts', status_code=201)
    def create_context(project_id: str, body: models.NewContext, request: Request):
        return mutate(request, lambda state, actor, role: s.propose(s.project(state, project_id), actor, 'create', body.model_dump()))

    @router.get('/projects/{project_id}/contexts/{context_id}')
    def context(project_id: str, context_id: str, request: Request, max_chars: int = Query(default=12000, ge=1, le=12000)):
        item, doc = get_context(request, project_id, context_id)
        content = markdown_content(request, item, doc)
        return {**s.context_metadata(item, doc), 'content': content[:max_chars], 'truncated': len(content) > max_chars}

    @router.put('/projects/{project_id}/contexts/{context_id}')
    def update_context(project_id: str, context_id: str, body: models.Update, request: Request):
        return mutate(request, lambda state, actor, role: s.propose(s.project(state, project_id), actor, 'update', body.model_dump(), context_id))

    @router.delete('/projects/{project_id}/contexts/{context_id}')
    def delete_context(project_id: str, context_id: str, body: models.Delete, request: Request):
        return mutate(request, lambda state, actor, role: s.propose(s.project(state, project_id), actor, 'delete', body.model_dump(), context_id))

    @router.get('/projects/{project_id}/contexts/{context_id}/markdown')
    def markdown(project_id: str, context_id: str, request: Request):
        item, doc = get_context(request, project_id, context_id)
        return Response(content=markdown_content(request, item, doc), media_type='text/markdown',
                        headers={'Content-Disposition': f'attachment; filename="{doc["filename"]}"'})

    @router.get('/projects/{project_id}/contexts/{context_id}/sections')
    def context_sections(project_id: str, context_id: str, request: Request):
        item, doc = get_context(request, project_id, context_id)
        return {**s.status(item, doc), 'sections': sections(markdown_content(request, item, doc))}

    @router.post('/projects/{project_id}/contexts/{context_id}/extract')
    def extract(project_id: str, context_id: str, body: models.Extract, request: Request):
        item, doc = get_context(request, project_id, context_id)
        parts = sections(markdown_content(request, item, doc))
        if set(body.section_keys) - {part['key'] for part in parts}:
            raise Problem('Unknown section key; read the sections endpoint first.', 422)
        selected = [part for part in parts if (not body.section_keys or part['key'] in body.section_keys)
                    and (not body.query or body.query.casefold() in part['body'].casefold())]
        text = '\n\n'.join(f"## {part['heading']}\n\n{part['body']}" for part in selected)
        return {**s.status(item, doc), 'content': text[:body.max_chars], 'truncated': len(text) > body.max_chars}

    @router.get('/projects/{project_id}/contexts/{context_id}/status')
    def status(project_id: str, context_id: str, request: Request, known_version: int | None = Query(default=None, ge=1)):
        item, doc = get_context(request, project_id, context_id, True)
        return s.status(item, doc, known_version)

    @router.get('/projects/{project_id}/contexts/{context_id}/versions')
    def versions(project_id: str, context_id: str, request: Request):
        item, doc = get_context(request, project_id, context_id, True)
        return [{**{key: value for key, value in version.items() if key != 'content'}, 'name': s.context_name(version)} for version in reversed(doc['history'])]

    @router.get('/projects/{project_id}/contexts/{context_id}/versions/{version}')
    def version(project_id: str, context_id: str, version: int, request: Request):
        item, doc = get_context(request, project_id, context_id, True)
        found = next((entry for entry in doc['history'] if entry['version'] == version), None)
        if found is None:
            raise Problem('Version not found.', 404)
        return {**found, 'name': s.context_name(found), 'content': markdown_content(request, item, found)}

    @router.get('/projects/{project_id}/graph')
    def graph(project_id: str, request: Request):
        return s.graph(get_project(request, project_id))

    @router.get('/projects/{project_id}/impact/{context_id}')
    def impact(project_id: str, context_id: str, request: Request):
        item, doc = get_context(request, project_id, context_id)
        nodes = s.graph(item)['nodes']
        affected = {context_id}
        while True:
            expanded = affected | {node['id'] for node in nodes if any(link['target_id'] in affected for link in node['relationships'])}
            if expanded == affected:
                break
            affected = expanded
        return {'context_id': context_id, 'contexts': [node for node in nodes if node['id'] in affected - {context_id}]}

    @router.get('/projects/{project_id}/proposals')
    def proposals(project_id: str, request: Request):
        item = get_project(request, project_id)
        # Lists contain metadata; read one proposal before deciding its exact hash.
        return [{**{key: value for key, value in proposal.items() if key != 'candidate'}, 'name': s.context_name(proposal['candidate']), 'filename': proposal['candidate']['filename']}
                for proposal in reversed(list(item['proposals'].values()))]

    @router.get('/projects/{project_id}/proposals/{proposal_id}')
    def proposal(project_id: str, proposal_id: str, request: Request):
        item = get_project(request, project_id)
        found = item['proposals'].get(proposal_id)
        if not found:
            raise Problem('Proposal not found or unavailable.', 404)
        old = item['contexts'].get(found['context_id'])
        before = next((version for version in old['history'] if version['version'] == found['base_version']), None) if old else None
        content = request.app.state.project_store.candidate(item['id'], found)
        return {**found, 'candidate': {**found['candidate'], 'content': content},
                'before': {**before, 'content': markdown_content(request, item, before)} if before else None}

    @router.post('/projects/{project_id}/proposals/{proposal_id}/review')
    def review(project_id: str, proposal_id: str, body: models.Review, request: Request):
        return mutate(request, lambda state, actor, role: s.review(s.project(state, project_id), actor, role, proposal_id, body.model_dump()))

    @router.get('/projects/{project_id}/activity')
    def activity(project_id: str, request: Request, limit: int = Query(default=30, ge=1, le=100)):
        return list(reversed(get_project(request, project_id)['events']))[:limit]

    return router
