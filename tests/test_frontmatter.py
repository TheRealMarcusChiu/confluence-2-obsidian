from src.frontmatter import build_frontmatter


def _page(title="Page", **extras):
    base = {
        "title": title,
        "history": {"createdDate": "2024-01-01T00:00:00Z", "createdBy": {"displayName": "Alice"}},
        "version": {"when": "2024-02-01T00:00:00Z"},
        "_links": {"webui": "/spaces/PROJ/pages/1"},
    }
    base.update(extras)
    return base


def test_frontmatter_emits_empty_children_list_for_leaf_page():
    out = build_frontmatter(_page(), "https://confluence.example.com")
    assert "children: []" in out


def test_frontmatter_omits_parent_for_root_page():
    out = build_frontmatter(_page(), "https://confluence.example.com")
    assert "parent:" not in out


def test_frontmatter_emits_parent_as_wiki_link():
    out = build_frontmatter(_page(), "https://confluence.example.com", parent="Root Page")
    assert 'parent: "[[Root Page]]"' in out


def test_frontmatter_emits_children_as_wiki_link_yaml_block():
    out = build_frontmatter(
        _page(),
        "https://confluence.example.com",
        children=["Child A", "Child B"],
    )
    assert "children:" in out
    assert '  - "[[Child A]]"' in out
    assert '  - "[[Child B]]"' in out
    assert "children: []" not in out


def test_frontmatter_parent_value_yaml_quoted_when_contains_special_chars():
    out = build_frontmatter(
        _page(),
        "https://confluence.example.com",
        parent='Design： v2',  # sanitized fullwidth colon
    )
    assert 'parent: "[[Design： v2]]"' in out
