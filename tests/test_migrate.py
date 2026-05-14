from pathlib import Path

from migrate import migrate_page
from src.paths import PathResolver
from src.report import MigrationReport


class FakeClient:
    def __init__(self, attachments=None):
        self._attachments = attachments or []

    def list_attachments(self, page_id):
        return self._attachments

    def download_attachment(self, attachment):
        return b""


def _page(page_id, title, space="PROJ", ancestors=()):
    return {
        "id": page_id,
        "title": title,
        "space": {"key": space},
        "ancestors": [{"title": t} for t in ancestors],
        "body": {"storage": {"value": "<p>hi</p>"}},
    }


def test_leaf_page_gets_empty_same_named_folder(tmp_path):
    resolver = PathResolver(tmp_path)
    page = _page("1", "Leaf")
    file_path, basename = resolver.resolve(page)
    migrate_page(page, file_path, basename, FakeClient(), resolver, MigrationReport(), "https://x", download_attachments=True)

    assert file_path.exists()
    assert (file_path.parent / basename).is_dir()
    assert list((file_path.parent / basename).iterdir()) == []


def test_folder_created_even_when_attachments_disabled(tmp_path):
    resolver = PathResolver(tmp_path)
    page = _page("2", "NoAttachments")
    file_path, basename = resolver.resolve(page)
    migrate_page(page, file_path, basename, FakeClient(), resolver, MigrationReport(), "https://x", download_attachments=False)

    assert (file_path.parent / basename).is_dir()
