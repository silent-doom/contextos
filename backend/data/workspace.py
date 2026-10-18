"""Join authorized project knowledge to private task state without copying it.

Firestore already stores both in one transaction. The single-process local
provider reads the shared registry for each operation and persists only task
state in SQLite; freshness is derived from canonical revisions on every read.
"""
from backend.data.projects import FirestoreProjects


class ProjectWorkspaceStore:
    def __init__(self, store, projects):
        self.store = store
        self.projects = projects
        self.unified = isinstance(projects, FirestoreProjects) and projects.store is store

    def _projects(self, identity):
        state = self.projects.read(identity)
        for project in state['context_projects'].values():
            for doc in project['contexts'].values():
                if not doc['deleted']:
                    # Retrieval must enforce the same immutable-file checks as
                    # the Knowledge API, rather than trusting a cached body.
                    doc['content'] = self.projects.content(project['id'], doc)
        return state['context_projects']

    def read(self, identity):
        state = self.store.read(identity)
        if not self.unified:
            state['context_projects'] = self._projects(identity)
        return state

    def mutate(self, identity, operation):
        if self.unified:
            return self.store.mutate(identity, operation)

        def joined(state):
            previous = state.pop('context_projects', None)
            state['context_projects'] = self._projects(identity)
            try:
                return operation(state)
            finally:
                state.pop('context_projects', None)
                if previous is not None:
                    state['context_projects'] = previous

        return self.store.mutate(identity, joined)
