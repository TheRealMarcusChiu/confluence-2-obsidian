import json
import re
from bs4 import BeautifulSoup, NavigableString, Tag

from src.sanitize import normalize_filename_whitespace, sanitize_title


CDATA_RE = re.compile(r'<!\[CDATA\[(.*?)\]\]>', re.DOTALL)
PLAIN_TEXT_ESCAPE_RE = re.compile(r'([\\`*_~#\[\]$<>])')
BRACKETS_ONLY_ESCAPE_RE = re.compile(r'([\[\]<>])')
ESCAPE_TRIGGER_TAGS = frozenset({'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                                  'li', 'strong', 'em', 'u', 'sub', 'sup'})
LINK_DISPLAY_TAGS = frozenset({'a', 'ac:link'})
INLINE_HTML_CODE_TAGS = frozenset({'code', 'pre'})
CDATA_VERBATIM_TAGS = frozenset({'ac:plain-text-body', 'ac:plain-text-link-body'})


def _balance_url_parens(url: str) -> str:
    chars = []
    open_count = 0
    for ch in url:
        if ch == '(':
            open_count += 1
            chars.append(ch)
        elif ch == ')':
            if open_count > 0:
                open_count -= 1
                chars.append(ch)
            else:
                chars.append('%29')
        else:
            chars.append(ch)
    if open_count == 0:
        return ''.join(chars)
    remaining = open_count
    encoded = []
    for ch in reversed(chars):
        if ch == '(' and remaining > 0:
            encoded.append('%28')
            remaining -= 1
        else:
            encoded.append(ch)
    return ''.join(reversed(encoded))


def _escape_html(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _unescape_html(text: str) -> str:
    return text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')


_LIST_LINE_RE = re.compile(r'^(\t*)(- |\d+\. )')
_OL_RESTART_RE = re.compile(r'((\t*)\d+\. [^\n]*)\n+\2(1\. )')
_LIST_BLANK_BEFORE_QUOTE_RE = re.compile(
    r'(^\t*(?:- |\d+\. )[^\n]*)\n\n(>)',
    re.MULTILINE,
)
_LIST_BLANK_BEFORE_FENCE_RE = re.compile(
    r'(^\t*(?:- |\d+\. )[^\n]*)\n\n(```)',
    re.MULTILINE,
)
_LIST_BR_LIST_RE = re.compile(
    r'(^\t*(?:- |\d+\. )[^\n]*)\n\n<br>\n\n(\t*(?:- |\d+\. ))',
    re.MULTILINE,
)


def _break_adjacent_ordered_lists(text: str) -> str:
    return _OL_RESTART_RE.sub(r'\1\n\n\2> \n\n\2\3', text)


def _collapse_blank_between_list_and_quote(text: str) -> str:
    return _LIST_BLANK_BEFORE_QUOTE_RE.sub(r'\1\n\2', text)


def _collapse_blank_between_list_and_fence(text: str) -> str:
    return _LIST_BLANK_BEFORE_FENCE_RE.sub(r'\1\n\2', text)


def _collapse_blanks_around_br_between_lists(text: str) -> str:
    return _LIST_BR_LIST_RE.sub(r'\1\n<br>\n\2', text)


_INDENT_MARKER_RE = re.compile(r'<<INDENT:(\d+)>>(.*?)<<INDENT_END>>', re.DOTALL)


def _emit_indent_callouts(text: str) -> str:
    matches = list(_INDENT_MARKER_RE.finditer(text))
    if not matches:
        return text
    groups: list[list] = []
    current = [matches[0]]
    for m in matches[1:]:
        gap = text[current[-1].end():m.start()]
        if gap.strip() == '':
            current.append(m)
        else:
            groups.append(current)
            current = [m]
    groups.append(current)
    out = text
    for group in reversed(groups):
        start = group[0].start()
        end = group[-1].end()
        min_level = min(int(m.group(1)) for m in group)
        lines = []
        for m in group:
            depth = int(m.group(1)) - min_level + 1
            prefix = '> ' * depth
            lines.append(f'{prefix}[!indent]')
            for line in m.group(2).split('\n'):
                lines.append(f'{prefix}{line}' if line else prefix.rstrip())
        out = out[:start] + '\n'.join(lines) + out[end:]
    return out


def _inject_list_placeholders(text: str) -> str:
    lines = text.split('\n')
    out = []
    stack: list[int] = []
    for line in lines:
        m = _LIST_LINE_RE.match(line)
        if m is None:
            if stack:
                prefix = '\t' * stack[-1]
                if line.startswith(prefix) and line[len(prefix):].startswith(' '):
                    out.append(line)
                    continue
            stack = []
            out.append(line)
            continue
        depth = len(m.group(1))
        while stack and stack[-1] > depth:
            stack.pop()
        if not stack or stack[-1] != depth:
            start = stack[-1] + 1 if stack else 0
            for missing in range(start, depth):
                out.append('\t' * missing + '- ')
                stack.append(missing)
            stack.append(depth)
        out.append(line)
    return '\n'.join(out)


def _plain_text_escape_re(node):
    parent = getattr(node, 'parent', None)
    triggered = False
    while parent is not None:
        name = (parent.name or '').lower()
        if name in LINK_DISPLAY_TAGS:
            return BRACKETS_ONLY_ESCAPE_RE
        if name in CDATA_VERBATIM_TAGS:
            return None
        if name in INLINE_HTML_CODE_TAGS:
            return PLAIN_TEXT_ESCAPE_RE
        if name == 'span':
            style = parent.attrs.get('style', '') or ''
            if 'color:' in style:
                return PLAIN_TEXT_ESCAPE_RE
            triggered = True
        elif name in ESCAPE_TRIGGER_TAGS:
            triggered = True
        parent = getattr(parent, 'parent', None)
    return PLAIN_TEXT_ESCAPE_RE if triggered else None


class Converter:
    def __init__(self, page_name: str, page_title: str | None = None, title_map: dict[str, str] | None = None):
        self.page_name = page_name
        self.page_title = page_title if page_title is not None else page_name
        self.title_map = title_map or {}
        self.unknown_macros: list[str] = []
        self.warnings: list[str] = []
        self.attachments_referenced: list[str] = []

    def _resolve_link_target(self, original_title: str) -> str:
        if original_title in self.title_map:
            return self.title_map[original_title]
        return sanitize_title(original_title)

    def convert(self, storage_xml: str) -> str:
        preprocessed = CDATA_RE.sub(lambda m: _escape_html(m.group(1)), storage_xml)
        soup = BeautifulSoup(preprocessed, "html.parser")
        out = self._render_children(soup)
        return self._collapse_blanks(out)

    def _collapse_blanks(self, text: str) -> str:
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = _emit_indent_callouts(text)
        text = _inject_list_placeholders(text)
        text = _break_adjacent_ordered_lists(text)
        text = _collapse_blank_between_list_and_quote(text)
        text = _collapse_blank_between_list_and_fence(text)
        text = _collapse_blanks_around_br_between_lists(text)
        return text.strip() + '\n'

    def _render(self, node) -> str:
        if isinstance(node, NavigableString):
            text = str(node)
            if text.strip() == '' and '\n' in text:
                return ''
            escape_re = _plain_text_escape_re(node)
            if escape_re is not None:
                text = escape_re.sub(r'\\\1', text)
            return text
        if isinstance(node, Tag):
            return self._render_tag(node)
        return self._render_children(node)

    def _render_children(self, node) -> str:
        if not hasattr(node, 'children'):
            return ''
        return ''.join(self._render(c) for c in node.children)

    def _inline(self, node) -> str:
        return self._render_children(node).strip()

    def _render_tag(self, tag: Tag) -> str:
        name = (tag.name or '').lower()

        if name == 'p':
            margin_level = self._margin_left_level(tag)
            if margin_level is not None:
                inner = self._render_children(tag).strip()
                if not inner:
                    return ''
                return f'\n\n<<INDENT:{margin_level}>>{inner}<<INDENT_END>>\n\n'
            if self._is_tag_only_paragraph(tag) and not self._has_single_real_paragraph_child(tag):
                if (self._has_nested_formatting_child(tag)
                        or self._has_multi_plain_span_children(tag)
                        or self._has_multi_anchor_children(tag)):
                    prev = self._previous_block_sibling(tag)
                    if prev is not None and (prev.name or '').lower() in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                        return '\n' + ''.join(self._render(c) for c in tag.children)
                    # Fall through to standard <p> rendering (\n\n lead)
                else:
                    return ''.join(self._render(c) for c in tag.children)
            inner = self._render_children(tag).strip()
            if not inner or all(c in ' \t\n\\' for c in inner):
                if self._is_list_separator_cursor_park(tag):
                    return '\n<br>\n'
                return ''
            return '\n\n' + inner
        if name == 'br':
            return '\n'
        if name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            return self._render_heading(tag, int(name[1]))
        if name in ('strong', 'b'):
            inner = self._render_children(tag)
            return inner if not inner.strip() else f"<strong>{inner.strip(chr(10))}</strong>"
        if name in ('em', 'i'):
            inner = self._render_children(tag)
            return inner if not inner.strip() else f"<em>{inner.strip(chr(10))}</em>"
        if name == 'u':
            return f"<u>{self._inline(tag)}</u>"
        if name in ('sub', 'sup'):
            return f"<{name}>{self._inline(tag)}</{name}>"
        if name == 'code':
            return f"<code>{self._inline(tag)}</code>"
        if name == 'pre':
            return self._render_pre(tag)
        if name == 'a':
            return self._render_a(tag)
        if name in ('ul', 'ol'):
            return self._render_list(tag, ordered=(name == 'ol'))
        if name == 'li':
            return self._render_children(tag)
        if name == 'table':
            return self._render_table(tag)
        if name == 'blockquote':
            return self._render_blockquote(tag)
        if name == 'span':
            style = tag.attrs.get('style', '')
            if 'color:' in style:
                sole_code = self._sole_code_child(tag)
                if sole_code is not None:
                    code_inner = self._render_children(sole_code)
                    if not code_inner.strip():
                        return ''
                    if (self._style_color_is_dark_gray(style)
                            and not self._has_non_dark_gray_color_ancestor(tag)):
                        return f'<code>{code_inner}</code>'
                    return f'<code><font style="{style}">{code_inner}</font></code>'
                inner = self._render_children(tag).strip(chr(10))
                if '\n' in inner.strip():
                    return inner
                if not inner.strip():
                    return ''
                if (self._style_color_is_dark_gray(style)
                        and not self._has_non_dark_gray_color_ancestor(tag)):
                    return inner
                return f'<font style="{style}">{inner}</font>'
            return self._render_children(tag)
        if name == 'hr':
            return '\n---'
        if name == 'ac:structured-macro':
            return self._render_macro(tag)
        if name == 'ac:link':
            return self._render_ac_link(tag)
        if name == 'ac:image':
            return self._render_ac_image(tag)
        if name == 'ac:emoticon':
            return tag.attrs.get('ac:name', '') or ''
        if name in ('ac:parameter', 'ac:plain-text-body', 'ac:rich-text-body',
                    'ac:plain-text-link-body', 'ac:link-body'):
            return self._render_children(tag)
        if name in ('tbody', 'thead', 'tfoot', 'colgroup', 'col'):
            return self._render_children(tag)

        return self._render_children(tag)

    def _render_heading(self, tag: Tag, level: int) -> str:
        new_level = level if level <= 3 else 6
        text = self._inline(tag)
        return '\n' + '#' * new_level + ' ' + text

    DARK_GRAY_MAX = 88
    _STYLE_COLOR_RE = re.compile(r'(?:^|;)\s*color\s*:\s*([^;]+?)\s*(?:;|$)')
    _RGB_RE = re.compile(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)')

    def _style_color_is_dark_gray(self, style: str) -> bool:
        m = self._STYLE_COLOR_RE.search(style)
        if not m:
            return False
        rgb = self._RGB_RE.search(m.group(1))
        if not rgb:
            return False
        return max(int(rgb.group(1)), int(rgb.group(2)), int(rgb.group(3))) <= self.DARK_GRAY_MAX

    def _has_non_dark_gray_color_ancestor(self, tag: Tag) -> bool:
        parent = tag.parent
        while parent is not None:
            if (getattr(parent, 'name', None) or '').lower() == 'span':
                style = parent.attrs.get('style', '') or ''
                if 'color:' in style and not self._style_color_is_dark_gray(style):
                    return True
            parent = getattr(parent, 'parent', None)
        return False

    def _sole_code_child(self, tag: Tag) -> Tag | None:
        code = None
        for child in tag.children:
            if isinstance(child, NavigableString):
                if str(child).strip():
                    return None
                continue
            if isinstance(child, Tag):
                if (child.name or '').lower() == 'code' and code is None:
                    code = child
                else:
                    return None
        return code

    def _render_pre(self, tag: Tag) -> str:
        body = self._render_pre_body(tag)
        return f'\n{body}\n' if body else ''

    def _render_pre_body(self, tag: Tag) -> str:
        parts = []
        for child in tag.children:
            if isinstance(child, NavigableString):
                parts.append(PLAIN_TEXT_ESCAPE_RE.sub(r'\\\1', str(child)))
            elif isinstance(child, Tag):
                if (child.name or '').lower() == 'code':
                    parts.append(self._render_children(child))
                else:
                    parts.append(self._render(child))
        lines = ''.join(parts).split('\n')
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            return ''
        inner = '<br>'.join(f'<code>{line}</code>' for line in lines)
        return f'<span style="white-space: pre-wrap">{inner}</span>'

    def _margin_left_level(self, tag: Tag) -> int | None:
        style = tag.attrs.get('style', '') or ''
        m = re.search(r'margin-left:\s*(\d+(?:\.\d+)?)px', style)
        if not m:
            return None
        level = int(round(float(m.group(1)) / 40))
        if level < 1:
            return None
        return level

    def _has_nested_formatting_child(self, tag: Tag) -> bool:
        for child in tag.children:
            if isinstance(child, Tag):
                if (child.name or '').lower() == 'span':
                    style = child.attrs.get('style', '') or ''
                    if 'color:' in style:
                        return True
                for grandchild in child.children:
                    if isinstance(grandchild, Tag) and not (grandchild.name or '').startswith('ac:'):
                        return True
        return False

    PROMOTE_MACRO_NAMES = frozenset({
        'widget', 'view-file', 'viewpdf', 'multimedia', 'excerpt-include',
    })

    def _is_list_separator_cursor_park(self, tag: Tag) -> bool:
        has_br = False
        for child in tag.children:
            if isinstance(child, NavigableString):
                if str(child).strip():
                    return False
            elif isinstance(child, Tag):
                if (child.name or '').lower() == 'br':
                    has_br = True
                else:
                    return False
        if not has_br:
            return False
        prev = self._previous_block_sibling(tag)
        nxt = self._next_block_sibling(tag)
        if prev is None or nxt is None:
            return False
        prev_name = (prev.name or '').lower()
        nxt_name = (nxt.name or '').lower()
        if prev_name not in ('ul', 'ol'):
            return False
        return prev_name == nxt_name

    def _previous_block_sibling(self, tag: Tag):
        sib = tag.previous_sibling
        while sib is not None:
            if isinstance(sib, Tag):
                return sib
            if isinstance(sib, NavigableString) and not str(sib).strip():
                sib = sib.previous_sibling
                continue
            return None
        return None

    def _next_block_sibling(self, tag: Tag):
        sib = tag.next_sibling
        while sib is not None:
            if isinstance(sib, Tag):
                return sib
            if isinstance(sib, NavigableString) and not str(sib).strip():
                sib = sib.next_sibling
                continue
            return None
        return None

    def _has_multi_anchor_children(self, tag: Tag) -> bool:
        a_count = 0
        for child in tag.children:
            if isinstance(child, Tag):
                name = (child.name or '').lower()
                if name == 'br':
                    continue
                if name == 'a':
                    a_count += 1
                else:
                    return False
        return a_count >= 2

    def _has_multi_plain_span_children(self, tag: Tag) -> bool:
        span_count = 0
        for child in tag.children:
            if isinstance(child, Tag):
                name = (child.name or '').lower()
                if name == 'br':
                    continue
                if name == 'span':
                    style = child.attrs.get('style', '') or ''
                    if 'color:' in style:
                        return False
                    span_count += 1
                else:
                    return False
        return span_count >= 2

    PROMOTE_INLINE_TAGS = frozenset({'a', 'strong', 'b', 'em', 'i'})
    BARE_PROMOTE_INLINE_TAGS = frozenset({'strong', 'b', 'em', 'i'})

    def _has_single_real_paragraph_child(self, tag: Tag) -> bool:
        real_count = 0
        for child in tag.children:
            if isinstance(child, Tag):
                name = (child.name or '').lower()
                if name == 'br':
                    continue
                if name in self.BARE_PROMOTE_INLINE_TAGS:
                    if any(isinstance(gc, Tag)
                           and not (gc.name or '').lower().startswith('ac:')
                           for gc in child.children):
                        return False
                    real_count += 1
                elif name in self.PROMOTE_INLINE_TAGS:
                    real_count += 1
                elif (name == 'ac:structured-macro'
                      and child.attrs.get('ac:name', '') in self.PROMOTE_MACRO_NAMES):
                    real_count += 1
                elif name == 'span':
                    style = child.attrs.get('style', '') or ''
                    if 'color:' in style:
                        return False
                    real_count += 1
                else:
                    return False
        return real_count == 1

    def _is_tag_only_paragraph(self, tag: Tag) -> bool:
        has_meaningful_tag = False
        for child in tag.children:
            if isinstance(child, NavigableString):
                if str(child).strip():
                    return False
            elif isinstance(child, Tag):
                if child.name == 'br':
                    continue
                has_meaningful_tag = True
        return has_meaningful_tag

    def _render_a(self, tag: Tag) -> str:
        href = tag.attrs.get('href', '')
        text = self._inline(tag)
        if not href:
            return text
        if not text:
            text = href
        return f"[{text}]({_balance_url_parens(href)})"

    _PARAGRAPHLIKE_LI_TAGS = frozenset({
        'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'ul', 'ol', 'br',
    })

    def _li_has_block_children(self, item: Tag) -> bool:
        for child in item.children:
            if isinstance(child, Tag):
                name = (child.name or '').lower()
                if name in self._PARAGRAPHLIKE_LI_TAGS:
                    continue
                if self._render(child).strip():
                    return True
        return False

    def _render_list(self, tag: Tag, ordered: bool) -> str:
        return '\n' + self._render_list_inner(tag, ordered, depth=0) + '\n\n'

    def _render_list_inner(self, tag: Tag, ordered: bool, depth: int) -> str:
        items = [c for c in tag.children if isinstance(c, Tag) and c.name == 'li']
        lines = []
        indent = '\t' * depth
        for i, item in enumerate(items):
            marker = f"{i+1}." if ordered else "-"
            continuation = indent + ' ' * (len(marker) + 1)
            inline_parts = []
            # post_items: (kind, content) in source order
            # kind: 'block' (pre-nested), 'nested', 'block_post_nested'
            post_items = []
            seen_first_p = False
            seen_nested = False
            last_split_was_heading = False
            li_can_loose = not self._li_has_block_children(item)
            for child in item.children:
                if isinstance(child, Tag) and child.name in ('ul', 'ol'):
                    sub_ordered = (child.name == 'ol')
                    rendered = self._render_list_inner(child, sub_ordered, depth + 1)
                    post_items.append(('nested', rendered))
                    seen_nested = True
                    continue
                is_p = isinstance(child, Tag) and child.name == 'p'
                is_heading = isinstance(child, Tag) and (child.name or '').lower() in (
                    'h1', 'h2', 'h3', 'h4', 'h5', 'h6'
                )
                is_pre = isinstance(child, Tag) and (child.name or '').lower() == 'pre'
                is_paragraphlike = is_p or is_heading or is_pre
                rendered = self._render(child)
                stripped = rendered.strip()
                if is_paragraphlike and not seen_first_p and stripped:
                    inline_parts.append(stripped)
                    seen_first_p = True
                    last_split_was_heading = is_heading
                elif is_paragraphlike and seen_first_p and stripped and li_can_loose:
                    if depth == 0:
                        sep = '\n' if last_split_was_heading else '\n\n'
                    else:
                        sep = ('\n' + continuation
                               if last_split_was_heading
                               else '\n' + continuation + '\n' + continuation)
                    inline_parts.append(sep + stripped)
                    last_split_was_heading = is_heading
                elif seen_first_p:
                    if stripped:
                        kind = 'block_post_nested' if seen_nested else 'block'
                        post_items.append((kind, stripped))
                elif stripped and '\n' in stripped:
                    kind = 'block_post_nested' if seen_nested else 'block'
                    post_items.append((kind, stripped))
                else:
                    inline_parts.append(rendered)
            if depth == 0:
                body = ''.join(inline_parts).strip().replace('\n', '\n' + continuation)
            else:
                body = ''.join(inline_parts).strip()
            has_hoisted_block = any(
                k in ('block', 'block_post_nested') and not c.startswith('```')
                for k, c in post_items
            )
            if not body and has_hoisted_block:
                # Empty body + block content → drop marker; emit blocks at column 0
                # followed by any nested lists. Source-order interleaving collapses
                # here — the no-marker degenerate case doesn't need it.
                blocks_only = [c for k, c in post_items if k != 'nested']
                nested_only = [c for k, c in post_items if k == 'nested']
                result = '\n\n'.join(blocks_only)
                for nested_content in nested_only:
                    result += '\n' + nested_content
                lines.append(result)
                continue
            item_line = f"{indent}{marker} {body}"
            result = item_line
            prev = item_line
            code_indent = '\t' * depth + '    '
            for idx, (kind, content) in enumerate(post_items):
                if kind == 'block':
                    is_code = content.startswith('```')
                    if is_code:
                        content = '\n'.join(code_indent + line for line in content.split('\n'))
                        sep = '\n'
                    elif idx == 0 or prev.endswith('</span>'):
                        sep = '\n'
                    else:
                        sep = '\n\n'
                    result += sep + content
                    prev = content
                elif kind == 'nested':
                    result += '\n' + content
                    prev = content
                elif kind == 'block_post_nested':
                    is_code = content.startswith('```')
                    if is_code:
                        content = '\n'.join(code_indent + line for line in content.split('\n'))
                        result += '\n' + content
                    else:
                        indented = '\n'.join('  ' + line if line else line for line in content.split('\n'))
                        result += '\n\n' + indented
                    prev = content
            lines.append(result)
        return '\n'.join(lines)

    def _render_blockquote(self, tag: Tag) -> str:
        inner = self._render_children(tag).strip()
        if not inner:
            return ''
        quoted = '\n'.join(f"> {line}" for line in inner.split('\n'))
        return '\n' + quoted

    TH_DEFAULT_BG = '#F4F5F7'
    ALIGN_VALUES = frozenset({'left', 'center', 'right'})
    VALIGN_VALUES = frozenset({'top', 'middle', 'bottom'})

    def _render_table(self, tag: Tag) -> str:
        table_def = self._build_table_def(tag)
        body = json.dumps(table_def, indent=2, ensure_ascii=False)
        return f'\n\n```merge-table\n{body}\n```'

    def _build_table_def(self, tag: Tag) -> dict:
        rows = [self._build_row(tr) for tr in self._iter_table_rows(tag)]
        result: dict = {"rows": rows}
        style = (tag.attrs.get('style') or '').strip()
        if style:
            result["tableStyle"] = style
        return result

    def _iter_table_rows(self, tag: Tag):
        for child in tag.children:
            if not isinstance(child, Tag):
                continue
            name = (child.name or '').lower()
            if name == 'tr':
                yield child
            elif name in ('thead', 'tbody', 'tfoot'):
                for grandchild in child.children:
                    if isinstance(grandchild, Tag) and (grandchild.name or '').lower() == 'tr':
                        yield grandchild

    def _build_row(self, tr: Tag) -> list:
        row: list = []
        for cell in tr.children:
            if not isinstance(cell, Tag):
                continue
            name = (cell.name or '').lower()
            if name not in ('td', 'th'):
                continue
            row.append(self._build_cell(cell))
            colspan = self._int_attr(cell, 'colspan', 1)
            for _ in range(colspan - 1):
                row.append(None)
        return row

    def _int_attr(self, tag: Tag, name: str, default: int) -> int:
        try:
            return int(tag.attrs.get(name, default))
        except (ValueError, TypeError):
            return default

    def _build_cell(self, cell: Tag):
        is_header = (cell.name or '').lower() == 'th'
        content = self._render_cell_content(cell)
        attrs = self._extract_cell_attrs(cell, is_header)
        if not attrs:
            if isinstance(content, str):
                return content
            return {"content": content}
        obj: dict = {}
        if content != "":
            obj["content"] = content
        obj.update(attrs)
        return obj

    def _extract_cell_attrs(self, cell: Tag, is_header: bool) -> dict:
        out: dict = {}
        if is_header:
            out["header"] = True
        style = cell.attrs.get('style') or ''
        bg = self._style_value(style, 'background-color')
        color = self._style_value(style, 'color')
        text_align = self._style_value(style, 'text-align')
        vertical_align = self._style_value(style, 'vertical-align')
        data_colour = cell.attrs.get('data-highlight-colour')
        if data_colour:
            bg = self.TH_DEFAULT_BG if data_colour == 'grey' else data_colour
        if bg:
            out["bg"] = bg
        elif is_header:
            out["bg"] = self.TH_DEFAULT_BG
        if color:
            out["color"] = color
        if text_align in self.ALIGN_VALUES:
            out["align"] = text_align
        if vertical_align in self.VALIGN_VALUES:
            out["valign"] = vertical_align
        colspan = self._int_attr(cell, 'colspan', 1)
        if colspan > 1:
            out["colspan"] = colspan
        rowspan = self._int_attr(cell, 'rowspan', 1)
        if rowspan > 1:
            out["rowspan"] = rowspan
        return out

    _STYLE_DECL_RE = re.compile(r'\s*([\w-]+)\s*:\s*([^;]+?)\s*(?:;|$)')

    def _style_value(self, style: str, prop: str) -> str:
        if not style:
            return ''
        for m in self._STYLE_DECL_RE.finditer(style):
            if m.group(1).lower() == prop.lower():
                return m.group(2).strip()
        return ''

    def _render_cell_content(self, cell: Tag):
        parts: list = []
        buffer: list = []
        for child in cell.children:
            if isinstance(child, Tag) and (child.name or '').lower() == 'table':
                md = self._render_nodes_as_markdown(buffer)
                if md:
                    parts.append(md)
                buffer = []
                parts.append(self._build_table_def(child))
            else:
                buffer.append(child)
        md = self._render_nodes_as_markdown(buffer)
        if md:
            parts.append(md)
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0]
        return parts

    def _render_nodes_as_markdown(self, nodes: list) -> str:
        if not nodes:
            return ""
        raw = ''.join(self._render(n) for n in nodes)
        return self._collapse_blanks(raw).strip()

    DROPPED_SILENTLY = frozenset({
        'anchor', 'toc',
        'pagetree', 'pagetreesearch', 'livesearch',
        'section', 'details',
    })

    def _render_macro(self, tag: Tag) -> str:
        name = tag.attrs.get('ac:name', '')
        if name in ('children', 'children-display'):
            return self._render_children_macro(tag)
        if name == 'excerpt':
            return self._render_excerpt(tag)
        if name == 'excerpt-include':
            return self._render_excerpt_include(tag)
        if name in ('latex-inline', 'latex', 'latex-block'):
            if name == 'latex-block':
                self.warnings.append(
                    f"latex-block rendered as inline math on page '{self.page_name}' (verify equation renders correctly)"
                )
            body = self._macro_text_body(tag).strip()
            body = re.sub(r'\s*[\r\n]+\s*', ' ', body)
            body = re.sub(r'\s', ' ', body)
            suffix = '\n' if name == 'latex-block' else ''
            return f"${body}${suffix}"
        if name == 'code':
            return self._render_code_macro(tag)
        if name == 'info':
            return self._render_callout(tag, 'info')
        if name == 'warning':
            return self._render_callout(tag, 'warning')
        if name in ('expand', 'ui-expand'):
            return self._render_collapsible(tag)
        if name == 'ui-tabs':
            return self._render_ui_tabs(tag)
        if name == 'widget':
            return self._render_widget(tag)
        if name in ('view-file', 'viewpdf', 'multimedia'):
            return self._render_file_embed(tag)
        if name == 'recently-updated':
            return self._render_recently_updated(tag)
        if name in self.DROPPED_SILENTLY:
            return ''
        self.unknown_macros.append(name)
        return ''

    def _render_children_macro(self, tag: Tag) -> str:
        inside_li = self._has_li_ancestor(tag)
        preceded_by_list = (not inside_li) and self._is_preceded_by_list_at_doc_level(tag)
        page_param = tag.find('ac:parameter', attrs={'ac:name': 'page'})
        if page_param is None:
            return self._dataview_children('this', inside_li, preceded_by_list)
        ri_page = page_param.find('ri:page')
        title = ri_page.attrs.get('ri:content-title', '') if ri_page is not None else ''
        if not title:
            return self._dataview_children('this', inside_li, preceded_by_list)
        if title not in self.title_map:
            self.warnings.append(f"children macro references unmigrated page: {title}")
            return ''
        return self._dataview_children(self.title_map[title], inside_li, preceded_by_list)

    def _has_li_ancestor(self, tag: Tag) -> bool:
        parent = tag.parent
        while parent is not None:
            if (parent.name or '').lower() == 'li':
                return True
            parent = parent.parent
        return False

    def _is_preceded_by_list_at_doc_level(self, tag: Tag) -> bool:
        node = tag
        while node.parent is not None and getattr(node.parent, 'name', None) != '[document]':
            node = node.parent
        prev = node.previous_sibling
        while prev is not None and not isinstance(prev, Tag):
            prev = prev.previous_sibling
        return prev is not None and (prev.name or '').lower() in ('ul', 'ol')

    def _dataview_children(self, target: str, inside_li: bool, preceded_by_list: bool = False) -> str:
        if target == 'this':
            scope = 'this.file.folder + "/" + this.file.name'
        else:
            scope = f'[[{target}]].file.folder + "/" + [[{target}]].file.name'
        body = [
            '```dataview',
            'LIST',
            'FROM ""',
            f'WHERE file.folder = {scope}',
            '```',
        ]
        if inside_li:
            wrapped = ['> [!list-indent-undo]', '> > [!indent]'] + [f'> > {line}' for line in body]
        elif preceded_by_list:
            wrapped = ['> [!list-indent-undo]'] + [f'> {line}' for line in body]
        else:
            wrapped = body
        return '\n' + '\n'.join(wrapped) + '\n\n'

    def _render_excerpt(self, tag: Tag) -> str:
        body_tag = tag.find('ac:rich-text-body') or tag.find('ac:plain-text-body')
        if body_tag is None:
            inner = self._render_children(tag).strip()
        else:
            inner = self._render_children(body_tag).strip()
        if not inner:
            return ''
        return f"\n````excerpt\n{inner}\n````\n^excerpt\n\n"

    def _render_callout(self, tag: Tag, callout_type: str) -> str:
        body_tag = tag.find('ac:rich-text-body') or tag.find('ac:plain-text-body')
        if body_tag is None:
            inner = self._render_children(tag).strip()
        else:
            inner = self._render_children(body_tag).strip()
        if not inner:
            return ''
        inner = re.sub(r'\n{3,}', '\n\n', inner)
        quoted = '\n'.join(f"> {line}" if line else ">" for line in inner.split('\n'))
        return f"\n> [!{callout_type}]\n{quoted}"

    def _direct_parameter(self, tag: Tag, name: str) -> Tag | None:
        for child in tag.children:
            if (isinstance(child, Tag)
                and child.name == 'ac:parameter'
                and child.attrs.get('ac:name', None) == name):
                return child
        return None

    def _direct_parameter_text(self, tag: Tag, name: str) -> str:
        param = self._direct_parameter(tag, name)
        return param.get_text().strip() if param is not None else ''

    def _render_collapsible(self, tag: Tag) -> str:
        macro_name = tag.attrs.get('ac:name', '')
        callout_type = 'expand-ui' if macro_name == 'ui-expand' else 'expand'
        title = self._direct_parameter_text(tag, 'title') or 'Click here to expand...'
        body_tag = tag.find('ac:rich-text-body') or tag.find('ac:plain-text-body')
        body = self._render_children(body_tag).strip() if body_tag is not None else ''
        if not body:
            body = "TODO"
        header = f"> [!{callout_type}]- {title}"
        body = re.sub(r'\n{3,}', '\n\n', body)
        quoted = '\n'.join(f"> {line}" if line else ">" for line in body.split('\n'))
        return f"\n\n{header}\n{quoted}"

    def _render_ui_tabs(self, tag: Tag) -> str:
        body_tag = tag.find('ac:rich-text-body')
        if body_tag is None:
            return ''
        tabs = []
        for child in body_tag.children:
            if (isinstance(child, Tag)
                and child.name == 'ac:structured-macro'
                and child.attrs.get('ac:name', '') == 'ui-tab'):
                title = self._direct_parameter_text(child, 'title')
                inner_body_tag = child.find('ac:rich-text-body')
                body = self._render_children(inner_body_tag).strip() if inner_body_tag is not None else ''
                body = re.sub(r'\n{3,}', '\n\n', body)
                tabs.append((title, body))
        if not tabs:
            return ''
        lines = ['> [!tabs]']
        for title, body in tabs:
            lines.append('>')
            lines.append(f'> === {title}')
            if body:
                lines.append('>')
                for body_line in body.split('\n'):
                    lines.append(f'> {body_line}' if body_line else '>')
        return '\n' + '\n'.join(lines) + '\n\n'

    def _render_widget(self, tag: Tag) -> str:
        param = self._direct_parameter(tag, 'url')
        if param is None:
            return ''
        ri_url = param.find('ri:url')
        href = ri_url.attrs.get('ri:value', '') if ri_url is not None else param.get_text().strip()
        if not href:
            return ''
        return f"![]({_balance_url_parens(href)})"

    def _render_file_embed(self, tag: Tag) -> str:
        attach = tag.find('ri:attachment')
        if attach is None:
            return ''
        filename = attach.attrs.get('ri:filename', '')
        if not filename:
            return ''
        filename = normalize_filename_whitespace(filename)
        self.attachments_referenced.append(filename)
        subfolder = self.page_name
        page_param = self._direct_parameter(tag, 'page')
        if page_param is not None:
            ri_page = page_param.find('ri:page')
            if ri_page is not None:
                title = ri_page.attrs.get('ri:content-title', '')
                if title:
                    subfolder = self._resolve_link_target(title)
        return f"![[{subfolder}/{filename}]]"

    def _render_recently_updated(self, tag: Tag) -> str:
        max_val = self._direct_parameter_text(tag, 'max') or '15'
        return (
            '\n```dataview\n'
            'LIST\n'
            'FROM ""\n'
            'SORT modified DESC\n'
            f'LIMIT {max_val}\n'
            '```'
        )

    def _render_excerpt_include(self, tag: Tag) -> str:
        for param in tag.find_all('ac:parameter'):
            if param.attrs.get('ac:name', None) == '':
                page = param.find('ri:page')
                if page is not None:
                    title = page.attrs.get('ri:content-title', '')
                    if title:
                        target = self._resolve_link_target(title)
                        return f"![[{target}#^excerpt]]"
        return ''

    def _macro_text_body(self, tag: Tag) -> str:
        body = tag.find('ac:plain-text-body') or tag.find('ac:rich-text-body')
        if body is None:
            return ''
        return _unescape_html(body.get_text())

    def _render_code_macro(self, tag: Tag) -> str:
        language = ''
        for param in tag.find_all('ac:parameter'):
            if param.attrs.get('ac:name', None) == 'language':
                language = param.get_text().strip()
                break
        body = self._macro_text_body(tag)
        return f"\n```{language}\n{body}\n```"

    def _render_ac_link(self, tag: Tag) -> str:
        if not list(tag.children):
            return f"[[{sanitize_title(self.page_title)}]]"
        page = tag.find('ri:page')
        url = tag.find('ri:url')
        attach = tag.find('ri:attachment')
        body_tag = tag.find('ac:plain-text-link-body') or tag.find('ac:link-body')
        display = body_tag.get_text().strip() if body_tag is not None else ''

        if page is not None:
            title = page.attrs.get('ri:content-title', '')
            if not title:
                return display
            target = self._resolve_link_target(title)
            if display and display != title:
                return f"[[{target}|{display}]]"
            if target != title:
                return f"[[{target}|{title}]]"
            return f"[[{target}]]"
        if url is not None:
            href = url.attrs.get('ri:value', '')
            text = display or href
            return f"[{text}]({_balance_url_parens(href)})"
        if attach is not None:
            filename = normalize_filename_whitespace(attach.attrs.get('ri:filename', ''))
            self.attachments_referenced.append(filename)
            if display:
                return f"[[{filename}|{display}]]"
            return f"[[{filename}]]"
        has_ri_target = any(
            isinstance(c, Tag) and (c.name or '').lower().startswith('ri:')
            for c in tag.children
        )
        if not has_ri_target:
            target = sanitize_title(self.page_title)
            if display:
                return f"[[{target}|{display}]]"
            return f"[[{target}]]"
        return display

    INLINE_IMAGE_PARENTS = frozenset({
        'p', 'span', 'strong', 'b', 'em', 'i', 'u', 'sub', 'sup',
        'code', 'a', 'pre', 'td', 'th', 'caption',
    })

    def _render_ac_image(self, tag: Tag) -> str:
        attach = tag.find('ri:attachment')
        if attach is not None:
            filename = normalize_filename_whitespace(attach.attrs.get('ri:filename', ''))
            self.attachments_referenced.append(filename)
            width = tag.attrs.get('ac:width')
            height = tag.attrs.get('ac:height')
            if width and height:
                size = f"|{width}x{height}"
            elif width:
                size = f"|{width}"
            else:
                size = ""
            wikilink = f"![[{self.page_name}/{filename}{size}]]"
            if self._has_li_ancestor(tag):
                return (
                    '\n> [!list-indent-undo]\n'
                    '> > [!indent]\n'
                    f'> > {wikilink}\n\n'
                )
            parent_name = (getattr(tag.parent, 'name', None) or '').lower()
            if parent_name in self.INLINE_IMAGE_PARENTS:
                return wikilink
            return f'\n\n{wikilink}\n\n'
        url = tag.find('ri:url')
        if url is not None:
            return f"![]({url.attrs.get('ri:value', '')})"
        return ''
