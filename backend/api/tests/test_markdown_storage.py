import pytest
from backend.data.storage import MarkdownStorage
from backend.domain import Problem


def test_version_files_are_immutable_isolated_and_content_addressed(tmp_path):
    storage = MarkdownStorage(tmp_path)
    root = storage.root
    doc = {'id': 'CTX-one', 'version': 1, 'content': 'Approved Markdown\r\nUnicode: café\r\n'}
    assert storage.revision('PRJ-one', doc) == doc['content']
    first = next(root.rglob('v*.md'))
    assert first.is_relative_to(root / 'projects' / 'PRJ-one')
    assert not (root / 'workspaces').exists()
    storage.revision('PRJ-one', doc)
    assert len(list(root.rglob('v*.md'))) == 1
    # An uncommitted competing version cannot overwrite another proposal's file.
    storage.revision('PRJ-one', {**doc, 'content': 'Competing proposal'})
    assert first.read_bytes().decode('utf-8') == doc['content']
    assert len(list(root.rglob('v*.md'))) == 2
    storage.revision('PRJ-two', {**doc, 'content': 'Another project'})
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
