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


def test_migrate_page_writes_parent_and_children_into_frontmatter(tmp_path):
    resolver = PathResolver(tmp_path)
    page = _page("42", "Architecture", ancestors=("Root",))
    file_path, basename = resolver.resolve(page)
    migrate_page(
        page,
        file_path,
        basename,
        FakeClient(),
        resolver,
        MigrationReport(),
        "https://x",
        download_attachments=False,
        parent="Root",
        children=["Module A", "Module B"],
    )
    content = file_path.read_text()
    assert 'parent: "[[Root]]"' in content
    assert "children:" in content
    assert '  - "[[Module A]]"' in content
    assert '  - "[[Module B]]"' in content


def test_migrate_page_writes_empty_children_for_leaf(tmp_path):
    resolver = PathResolver(tmp_path)
    page = _page("1", "Leaf")
    file_path, basename = resolver.resolve(page)
    migrate_page(
        page, file_path, basename, FakeClient(), resolver, MigrationReport(),
        "https://x", download_attachments=False,
    )
    content = file_path.read_text()
    assert "children: []" in content
    assert "parent:" not in content


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


def test_attachment_filename_unicode_whitespace_normalized_on_disk(tmp_path):
    # Confluence-supplied filenames sometimes embed NBSP / em-space etc.; the
    # on-disk filename must match the converter's normalized wiki-link.
    nbsp = chr(0xa0)
    raw_title = f"Screenshot{nbsp}at{nbsp}12.png"
    clean_title = "Screenshot at 12.png"

    resolver = PathResolver(tmp_path)
    page = _page("3", "WithAttachment")
    file_path, basename = resolver.resolve(page)
    attachments = [{
        "id": "att1",
        "title": raw_title,
        "_links": {"download": "/x"},
    }]
    migrate_page(
        page, file_path, basename, FakeClient(attachments=attachments),
        resolver, MigrationReport(), "https://x", download_attachments=True,
    )

    saved = file_path.parent / basename / clean_title
    assert saved.exists()
    raw_path = file_path.parent / basename / raw_title
    assert not raw_path.exists()
