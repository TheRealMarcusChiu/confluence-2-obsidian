from src.sanitize import normalize_filename_whitespace, sanitize_title, was_sanitized


def test_normalize_filename_whitespace_replaces_nbsp():
    assert normalize_filename_whitespace("Screenshot at 12.png") == "Screenshot at 12.png"


def test_normalize_filename_whitespace_one_to_one():
    # NBSP, em-space, narrow-NBSP, ideographic space — each → exactly one ASCII space
    assert normalize_filename_whitespace("a b c d　e") == "a b c d e"


def test_normalize_filename_whitespace_passes_through_ascii_spaces():
    assert normalize_filename_whitespace("Plain Title.png") == "Plain Title.png"


def test_sanitize_passes_clean_title_unchanged():
    assert sanitize_title("Plain Title") == "Plain Title"


def test_sanitize_replaces_colon_with_fullwidth():
    assert sanitize_title("Design: v2") == "Design： v2"


def test_sanitize_replaces_slash_with_fullwidth_solidus():
    assert sanitize_title("a/b") == "a／b"


def test_sanitize_replaces_all_invalid_chars_with_fullwidth():
    assert sanitize_title('a:b/c?d*e<f>g|h\\i') == "a：b／c？d＊e＜f＞g｜h＼i"


def test_sanitize_replaces_backslash_with_fullwidth():
    assert sanitize_title("path\\to\\thing") == "path＼to＼thing"


def test_was_sanitized_true_when_changed():
    assert was_sanitized("Design: v2") is True


def test_was_sanitized_false_when_unchanged():
    assert was_sanitized("Plain Title") is False
