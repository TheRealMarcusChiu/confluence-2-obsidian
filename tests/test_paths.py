from pathlib import Path

from src.paths import PathResolver


def make_page(page_id: str, title: str, space_key: str, ancestor_titles: list[str]):
    return {
        "id": page_id,
        "title": title,
        "space": {"key": space_key},
        "ancestors": [{"title": t} for t in ancestor_titles],
    }


def test_simple_path():
    r = PathResolver(Path("/v"))
    p, base = r.resolve(make_page("1", "Child", "PROJ", ["Root", "Parent"]))
    assert p == Path("/v/PROJ/Root/Parent/Child.md")
    assert base == "Child"


def test_sanitized_title_used_in_path():
    r = PathResolver(Path("/v"))
    p, _ = r.resolve(make_page("1", "Design: v2", "PROJ", []))
    assert p == Path("/v/PROJ/Design： v2.md")


def test_collision_resolved_with_page_id():
    r = PathResolver(Path("/v"))
    r.resolve(make_page("1", "Design: v2", "PROJ", []))
    p, base = r.resolve(make_page("999", "Design: v2", "PROJ", []))
    assert p == Path("/v/PROJ/Design： v2 (999).md")
    assert base == "Design： v2 (999)"
    assert len(r.collisions) == 1


def test_no_collision_for_same_page():
    r = PathResolver(Path("/v"))
    r.resolve(make_page("1", "Design: v2", "PROJ", []))
    p, _ = r.resolve(make_page("1", "Design: v2", "PROJ", []))
    assert p == Path("/v/PROJ/Design： v2.md")
    assert len(r.collisions) == 0


def test_title_map_populated():
    r = PathResolver(Path("/v"))
    r.resolve(make_page("1", "Design: v2", "PROJ", []))
    assert r.title_map["Design: v2"] == "Design： v2"


def test_distinct_invalid_chars_no_longer_collide():
    r = PathResolver(Path("/v"))
    r.resolve(make_page("1", "Design: v2", "PROJ", []))
    p, base = r.resolve(make_page("999", "Design/ v2", "PROJ", []))
    assert p == Path("/v/PROJ/Design／ v2.md")
    assert base == "Design／ v2"
    assert len(r.collisions) == 0
