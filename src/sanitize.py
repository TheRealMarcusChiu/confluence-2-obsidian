import re


_FILENAME_WHITESPACE_RE = re.compile(r'\s')


def normalize_filename_whitespace(filename: str) -> str:
    return _FILENAME_WHITESPACE_RE.sub(' ', filename)


INVALID_TO_FULLWIDTH = {
    ':': '：',
    '/': '／',
    '?': '？',
    '*': '＊',
    '<': '＜',
    '>': '＞',
    '|': '｜',
    '\\': '＼',
}


def sanitize_title(title: str) -> str:
    return ''.join(INVALID_TO_FULLWIDTH.get(c, c) for c in title)


def was_sanitized(title: str) -> bool:
    return any(c in INVALID_TO_FULLWIDTH for c in title)
