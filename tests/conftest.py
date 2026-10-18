"""Keep API test applications away from the developer's local project files."""
import sys
from functools import partial

import pytest

from backend.app import create_app
from backend.data.storage import MarkdownStorage


@pytest.fixture(autouse=True)
def isolated_project_storage(tmp_path, monkeypatch, request):
    module = sys.modules[request.module.__name__]
    if getattr(module, 'create_app', None) is create_app:
        monkeypatch.setattr(module, 'create_app', partial(
            create_app, markdown_storage=MarkdownStorage(tmp_path / 'storage')))
