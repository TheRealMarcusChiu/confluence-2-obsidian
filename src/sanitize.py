INVALID_CHARS = set(':/?*<>|\\')


def sanitize_title(title: str) -> str:
    return ''.join(' ' if c in INVALID_CHARS else c for c in title)


def was_sanitized(title: str) -> bool:
    return any(c in INVALID_CHARS for c in title)
