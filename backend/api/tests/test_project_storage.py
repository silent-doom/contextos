"""Persistence boundaries without a real database or cloud credentials."""
from copy import deepcopy
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest
from backend.api import service as s
from backend.data.projects import LocalProjects, FirestoreProjects, make_project_store
from backend.data.storage import MarkdownStorage
from backend.domain import Problem


def test_local_registry_reads_are_empty_and_side_effect_free(tmp_path):
    root = tmp_path / 'storage'
    assert LocalProjects(MarkdownStorage(root)).read('session-one') == {'context_projects': {}}
    assert not root.exists()


def test_local_registry_is_shared_across_instances_and_rollback_is_atomic(tmp_path, monkeypatch):
    first, second = [LocalProjects(MarkdownStorage(tmp_path)) for _ in range(2)]
    project = first.mutate('one', lambda state: s.create_project(state, 'admin', {'name': 'Saved', 'project_type': 'research'}))
    assert second.read('two')['context_projects'][project['id']]['name'] == 'Saved'
    original = first.path.read_bytes()
    real_replace = Path.replace
    def fail_registry(path, target):
        if str(target) == str(first.path):
            raise OSError('Simulated storage failure')
        return real_replace(path, target)
    monkeypatch.setattr(Path, 'replace', fail_registry)
    with pytest.raises(Problem) as failure:
        second.mutate('two', lambda state: s.update_project(s.project(state, project['id']), 'admin', {'expected_version': 1, 'name': 'Not committed'}))
    assert failure.value.status == 503 and first.path.read_bytes() == original
    assert not list(tmp_path.glob('.projects-*.tmp'))


def test_local_instances_serialize_mutations(tmp_path):
    stores = [LocalProjects(MarkdownStorage(tmp_path)) for _ in range(2)]
    def save(number):
        return stores[number % 2].mutate(str(number), lambda state: s.create_project(state, 'admin', {'name': str(number), 'project_type': 'software'}))
    with ThreadPoolExecutor(max_workers=2) as pool:
        created = list(pool.map(save, range(6)))
    assert set(stores[0].read()['context_projects']) == {item['id'] for item in created}


def test_invalid_local_registry_never_falls_back_to_seed_data(tmp_path):
    (tmp_path / 'projects.json').write_text('not JSON', encoding='utf-8')
    with pytest.raises(Problem) as failure:
        LocalProjects(MarkdownStorage(tmp_path)).read()
    assert failure.value.status == 409
    assert (tmp_path / 'projects.json').read_text(encoding='utf-8') == 'not JSON'


def test_local_firebase_identities_keep_their_verified_access_scope(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTH_MODE', 'firebase')
    store = LocalProjects(MarkdownStorage(tmp_path))
    first = store.mutate('team-one', lambda state: s.create_project(state, 'one', {'name': 'One', 'project_type': 'software'}))
    second = store.mutate('team-two', lambda state: s.create_project(state, 'two', {'name': 'Two', 'project_type': 'software'}))
    assert '_access_scope' not in first
    assert set(store.read('team-one')['context_projects']) == {first['id']}
    assert set(store.read('team-two')['context_projects']) == {second['id']}
    assert store.read()['context_projects'] == {}
    with pytest.raises(Problem) as denied:
        store.mutate('team-one', lambda state: s.update_project(s.project(state, second['id']), 'one', {'expected_version': 1, 'name': 'Forbidden'}))
    assert denied.value.status == 404
    assert store.read('team-two')['context_projects'][second['id']]['name'] == 'Two'


@pytest.mark.parametrize('production', ['firestore', 'cloud_run'])
def test_production_provider_uses_only_the_configured_store(monkeypatch, production):
    monkeypatch.setenv('STORE_BACKEND', 'firestore' if production == 'firestore' else 'sqlite')
    monkeypatch.setenv('K_SERVICE', 'service' if production == 'cloud_run' else '')
    class Store:
        state = {'context_projects': {}}
        def read(self, identity):
            assert identity == 'verified-team'
            return deepcopy(self.state)
        def mutate(self, identity, operation):
            assert identity == 'verified-team'
            return operation(self.state)
    cloud = make_project_store(Store(), None)
    assert isinstance(cloud, FirestoreProjects)
    assert cloud.read('verified-team') == {'context_projects': {}}
    cloud.mutate('verified-team', lambda state: state.update(context_projects={'saved': {}}))
    assert cloud.read('verified-team')['context_projects'] == {'saved': {}}
    assert cloud.content('saved', {'content': 'Approved cloud Markdown'}) == 'Approved cloud Markdown'
    assert cloud.candidate('saved', {'candidate': {'content': 'Proposed cloud Markdown'}}) == 'Proposed cloud Markdown'


def test_production_failure_does_not_fall_back_to_disk():
    class Offline:
        def read(self, identity):
            raise ConnectionError('Firestore unavailable')
    with pytest.raises(ConnectionError):
        FirestoreProjects(Offline()).read('team')
