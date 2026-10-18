import pytest
from backend.data.storage import MarkdownStorage
from backend.domain import Problem


def test_version_files_are_immutable_isolated_and_content_addressed(tmp_path):
    storage = MarkdownStorage(tmp_path)
    root = storage.root
    doc = {'id': 'CTX-one', 'version': 1, 'content': 'Approved Markdown\r\nUnicode: café\r\n'}
    assert storage.revision('PRJ-one', doc, create=True) == doc['content']
    first = next(root.rglob('v*.md'))
    assert first.is_relative_to(root / 'projects' / 'PRJ-one')
    assert not (root / 'workspaces').exists()
    storage.revision('PRJ-one', doc, create=True)
    assert len(list(root.rglob('v*.md'))) == 1
    # An uncommitted competing version cannot overwrite another proposal's file.
    storage.revision('PRJ-one', {**doc, 'content': 'Competing proposal'}, create=True)
    assert first.read_bytes().decode('utf-8') == doc['content']
    assert len(list(root.rglob('v*.md'))) == 2
    storage.revision('PRJ-two', {**doc, 'content': 'Another project'}, create=True)
    assert storage.project_path('PRJ-one') != storage.project_path('PRJ-two')
    assert first.read_bytes().decode('utf-8') == doc['content']
    first.write_text('Modified outside approval')
    with pytest.raises(Problem) as error:
        storage.revision('PRJ-one', doc)
    assert error.value.status == 409


def test_storage_rejects_paths_from_record_ids(tmp_path):
    storage = MarkdownStorage(tmp_path)
    for field in ('id', 'project_id'):
        with pytest.raises(Problem):
            storage.revision('../outside' if field == 'project_id' else 'PRJ-one',
                             {'id': '../outside' if field == 'id' else 'CTX-one', 'version': 1, 'content': 'x'})
    assert list(tmp_path.rglob('*.md')) == []


def test_firestore_content_adapter_needs_no_local_files(tmp_path):
    from backend.data.storage import make_markdown_storage
    from backend.store import FirestoreStore
    storage = make_markdown_storage(FirestoreStore.__new__(FirestoreStore), tmp_path / 'unused')
    old = {'id': 'CTX-one', 'version': 1, 'content': 'Accepted v1'}
    latest = {**old, 'version': 2, 'content': 'Accepted v2'}
    assert storage.revision('PRJ-one', old) == 'Accepted v1'
    assert storage.revision('PRJ-one', latest) == 'Accepted v2'
    proposal = {'id': 'PRO-one', 'candidate': {'content': 'Pending suggestion'}}
    assert storage.proposal('PRJ-one', proposal) == 'Pending suggestion'
    storage.sync({'context_projects': {}})
    assert not (tmp_path / 'unused').exists()
