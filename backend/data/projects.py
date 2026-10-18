"""Project persistence: local storage files, or the configured Firestore store."""
from copy import deepcopy
import json
import os
from threading import RLock
from uuid import uuid4
from backend.domain import Problem


class LocalProjects:
    _locks = {}

    def __init__(self, markdown):
        self.markdown = markdown
        self.path = markdown.root / 'projects.json'
        self.lock = self._locks.setdefault(str(markdown.root).casefold(), RLock())
        self.shared_demo = os.getenv('AUTH_MODE', 'demo') == 'demo'

    def _read_all(self):
        """Read existing files only. Sessions never create or seed projects."""
        with self.lock:
            try:
                state = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'context_projects': {}}
                records = state['context_projects']
                if not isinstance(records, dict):
                    raise ValueError('Invalid project registry')
                for project_id, item in records.items():
                    self.markdown.project_path(project_id)
                    if item['id'] != project_id or not all(isinstance(item[key], dict) for key in ('contexts', 'proposals')) or not isinstance(item['events'], list):
                        raise ValueError('Invalid project metadata')
                directory = self.markdown.root / 'projects'
                for folder in sorted(directory.iterdir()) if directory.exists() else []:
                    if not folder.is_dir():
                        continue
                    self.markdown.project_path(folder.name)
                    if folder.name not in records:
                        records[folder.name] = {
                            'id': folder.name, 'name': folder.name + ' (metadata missing)',
                            'project_type': 'Metadata missing', 'admin': '', 'version': 1, 'archived': False,
                            'created_at': None, 'updated_at': None, 'metadata_missing': True,
                            'description': 'Markdown files exist, but saved names, owners, relationships and approvals are missing. Restore the original project metadata before making changes.',
                            'stored_markdown_files': sum(1 for _ in folder.rglob('*.md')),
                            'contexts': {}, 'proposals': {}, 'events': [],
                        }
                return deepcopy(state)
            except OSError as exc:
                raise Problem('Local project storage is unavailable.', 503) from exc
            except (ValueError, KeyError, TypeError) as exc:
                raise Problem('Local projects.json is invalid. Restore its saved metadata before continuing.', 409) from exc

    def _visible(self, state, identity):
        if not self.shared_demo:
            state['context_projects'] = {key: item for key, item in state['context_projects'].items()
                                         if identity is not None and item.get('_access_scope') == identity}
        return state

    def read(self, identity=None):
        return self._visible(self._read_all(), identity)

    def mutate(self, identity, operation):
        with self.lock:
            complete = self._read_all()
            state = self._visible(deepcopy(complete), identity)
            result = deepcopy(operation(state))
            if not self.shared_demo:
                if identity is None:
                    raise Problem('Verified project access is required.', 403)
                for item in state['context_projects'].values():
                    item['_access_scope'] = identity
            complete['context_projects'].update(state['context_projects'])
            saved = {'context_projects': {key: item for key, item in complete['context_projects'].items() if not item.get('metadata_missing')}}
            raw = json.dumps(saved, ensure_ascii=False, indent=2)
            temporary = self.path.with_name('.projects-' + uuid4().hex + '.tmp')
            try:
                self.markdown.sync(saved)
                for project_id in saved['context_projects']:
                    self.markdown.project_path(project_id).mkdir(parents=True, exist_ok=True)
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary.write_text(raw, encoding='utf-8', newline='\n')
                temporary.replace(self.path)
                return result
            except OSError as exc:
                raise Problem('Local project storage could not be saved.', 503) from exc
            finally:
                temporary.unlink(missing_ok=True)

    def content(self, project_id, doc):
        return self.markdown.revision(project_id, doc)

    def candidate(self, project_id, proposal):
        return self.markdown.proposal(project_id, proposal)


class FirestoreProjects:
    """Keep authorized metadata and Markdown in Firestore; never use local files."""
    def __init__(self, store):
        self.store = store

    def read(self, identity):
        return self.store.read(identity)

    def mutate(self, identity, operation):
        return self.store.mutate(identity, operation)

    def content(self, project_id, doc):
        return doc['content']

    def candidate(self, project_id, proposal):
        return proposal['candidate']['content']


def make_project_store(store, markdown):
    if os.getenv('K_SERVICE') or os.getenv('STORE_BACKEND') == 'firestore':
        return FirestoreProjects(store)
    return LocalProjects(markdown)
