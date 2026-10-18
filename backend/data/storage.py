"""Markdown access for local files or canonical Firestore workspace records.

Project metadata and review hashes stay in the existing transactional store.
Only authorized records supplied by the API are written or read here.
"""
import hashlib
import os
from pathlib import Path
import re
from threading import RLock
from uuid import uuid4
from backend.domain import Problem


class MarkdownStorage:
    def __init__(self, root):
        self.root = Path(root).resolve()
        # Versioned paths can exceed Windows' legacy 260-character limit.
        if os.name == 'nt' and not str(self.root).startswith('\\\\?\\'):
            path = str(self.root)
            self.root = Path('\\\\?\\UNC\\' + path[2:] if path.startswith('\\\\') else '\\\\?\\' + path)
        self.lock = RLock()

    def project_path(self, project_id):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', project_id):
            raise Problem('Invalid storage project ID.', 422)
        return self.root / 'projects' / project_id

    def _file(self, project_id, kind, record_id, filename):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', record_id):
            raise Problem('Invalid storage record ID.', 422)
        path = self.project_path(project_id) / kind / record_id / filename
        if not path.resolve().is_relative_to(self.root):
            raise Problem('Invalid storage path.', 422)
        return path

    def _content(self, path, expected):
        """Create missing files atomically; never overwrite approved/reviewed content."""
        try:
            with self.lock:
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = path.with_name('.' + uuid4().hex + '.tmp')
                    try:
                        temporary.write_text(expected, encoding='utf-8', newline='\n')
                        temporary.replace(path)
                    finally:
                        temporary.unlink(missing_ok=True)
                content = path.read_bytes().decode('utf-8')
                if content != expected:
                    raise Problem('Stored Markdown differs from its reviewed version. Restore the file before continuing.', 409)
                return content
        except OSError as exc:
            raise Problem('Markdown storage is unavailable. Check the local storage folder.', 503) from exc
        except UnicodeError as exc:
            raise Problem('Stored Markdown is not valid UTF-8.', 409) from exc

    def revision(self, project_id, doc):
        version = doc['version']
        if not isinstance(version, int) or version < 1:
            raise Problem('Invalid Markdown version.', 422)
        digest = hashlib.sha256(doc['content'].encode()).hexdigest()[:32]
        path = self._file(project_id, 'contexts', doc['id'], f'versions/v{version:06d}-{digest}.md')
        return self._content(path, doc['content'])

    def proposal(self, project_id, proposal):
        path = self._file(project_id, 'proposals', proposal['id'], 'candidate.md')
        return self._content(path, proposal['candidate']['content'])

    def sync(self, state):
        """Write files before the metadata transaction commits; retries are idempotent."""
        for project in state.get('context_projects', {}).values():
            for doc in project['contexts'].values():
                for revision in doc['history']:
                    self.revision(project['id'], revision)
            for proposal in project['proposals'].values():
                self.proposal(project['id'], proposal)


class WorkspaceMarkdownStorage:
    """Read the authorized content already committed in the workspace database.

    Firestore transactions persist bodies, revisions and proposal hashes together.
    Keeping a second filesystem copy would add an ephemeral Cloud Run dependency.
    """
    def revision(self, project_id, doc):
        return doc['content']

    def proposal(self, project_id, proposal):
        return proposal['candidate']['content']

    def sync(self, state):
        # The enclosing workspace transaction persists all of these records.
        pass


def make_markdown_storage(store, root):
    from backend.store import FirestoreStore
    return WorkspaceMarkdownStorage() if isinstance(store, FirestoreStore) else MarkdownStorage(root)
