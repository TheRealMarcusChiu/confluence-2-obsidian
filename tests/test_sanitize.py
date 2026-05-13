from src.sanitize import sanitize_title, was_sanitized


def test_sanitize_passes_clean_title_unchanged():
    assert sanitize_title("Plain Title") == "Plain Title"


def test_sanitize_replaces_colon_with_space():
    assert sanitize_title("Design: v2") == "Design  v2"


def test_sanitize_replaces_slash_with_space():
    assert sanitize_title("a/b") == "a b"


def test_sanitize_replaces_all_invalid_chars():
    assert sanitize_title('a:b/c?d*e<f>g|h\\i') == "a b c d e f g h i"


def test_sanitize_replaces_backslash_with_space():
    assert sanitize_title("path\\to\\thing") == "path to thing"


def test_was_sanitized_true_when_changed():
    assert was_sanitized("Design: v2") is True


def test_was_sanitized_false_when_unchanged():
    assert was_sanitized("Plain Title") is False
