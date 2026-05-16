import re
from bs4 import BeautifulSoup, NavigableString, Tag

from src.sanitize import sanitize_title


CDATA_RE = re.compile(r'<!\[CDATA\[(.*?)\]\]>', re.DOTALL)
PLAIN_TEXT_ESCAPE_RE = re.compile(r'([\\`*_~#\[\]$])')
BRACKETS_ONLY_ESCAPE_RE = re.compile(r'([\[\]])')
ESCAPE_TRIGGER_TAGS = frozenset({'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                                  'li', 'strong', 'em', 'u', 'sub', 'sup'})
LINK_DISPLAY_TAGS = frozenset({'a', 'ac:link'})
VERBATIM_TAGS = frozenset({'code', 'pre', 'ac:plain-text-body', 'ac:plain-text-link-body'})


def _escape_html(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _unescape_html(text: str) -> str:
    return text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')


def _plain_text_escape_re(node):
    parent = getattr(node, 'parent', None)
    triggered = False
    while parent is not None:
        name = (parent.name or '').lower()
        if name in LINK_DISPLAY_TAGS:
            return BRACKETS_ONLY_ESCAPE_RE
        if name in VERBATIM_TAGS:
            return None
        if name == 'span':
            style = parent.attrs.get('style', '') or ''
            if 'color:' in style:
                return None
            triggered = True
        elif name in ESCAPE_TRIGGER_TAGS:
            triggered = True
        parent = getattr(parent, 'parent', None)
    return PLAIN_TEXT_ESCAPE_RE if triggered else None


class Converter:
    def __init__(self, page_name: str, title_map: dict[str, str] | None = None):
        self.page_name = page_name
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
            macro_only = self._is_macro_only_paragraph(tag)
            if macro_only:
                return ''.join(self._render(c) for c in tag.children)
            inner = self._render_children(tag).strip()
            if not inner or all(c in ' \t\n\\' for c in inner):
                return ''
            return '\n\n' + inner
        if name == 'br':
            return '\n' if self._inside_pre(tag) else '\\\n'
        if name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            return self._render_heading(tag, int(name[1]))
        if name in ('strong', 'b'):
            return f"**{self._inline(tag)}**"
        if name in ('em', 'i'):
            return f"*{self._inline(tag)}*"
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
                return f'<font style="{style}">{self._inline(tag)}</font>'
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

    def _inside_pre(self, tag: Tag) -> bool:
        parent = tag.parent
        while parent is not None:
            if (parent.name or '').lower() == 'pre':
                return True
            parent = parent.parent
        return False

    def _render_pre(self, tag: Tag) -> str:
        parts = []
        for child in tag.children:
            if isinstance(child, NavigableString):
                parts.append(str(child))
            elif isinstance(child, Tag):
                parts.append(self._render(child))
        lines = ''.join(parts).split('\n')
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            return ''
        return '\n' + '\n'.join(f'<code>{line}</code>' for line in lines)

    def _is_macro_only_paragraph(self, tag: Tag) -> bool:
        macros = []
        for child in tag.children:
            if isinstance(child, NavigableString):
                if str(child).strip():
                    return False
            elif isinstance(child, Tag):
                if child.name == 'ac:structured-macro':
                    macros.append(child)
                elif child.name == 'br':
                    continue
                else:
                    return False
        return len(macros) >= 1

    def _render_a(self, tag: Tag) -> str:
        href = tag.attrs.get('href', '')
        text = self._inline(tag)
        if not href:
            return text
        if not text:
            text = href
        return f"[{text}]({href})"

    def _render_list(self, tag: Tag, ordered: bool) -> str:
        return '\n' + self._render_list_inner(tag, ordered, depth=0)

    def _render_list_inner(self, tag: Tag, ordered: bool, depth: int) -> str:
        items = [c for c in tag.children if isinstance(c, Tag) and c.name == 'li']
        lines = []
        indent = '\t' * depth
        for i, item in enumerate(items):
            marker = f"{i+1}." if ordered else "-"
            inline_parts = []
            block_parts = []
            nested = []
            for child in item.children:
                if isinstance(child, Tag) and child.name in ('ul', 'ol'):
                    nested.append((child.name == 'ol', child))
                    continue
                rendered = self._render(child)
                stripped = rendered.strip()
                if stripped and '\n' in stripped:
                    block_parts.append(stripped)
                else:
                    inline_parts.append(rendered)
            body = ''.join(inline_parts).strip().replace('\n', ' ')
            item_line = f"{indent}{marker} {body}".rstrip()
            if block_parts:
                self.warnings.append(
                    f"list item with block content (hoisted to column 0) on page '{self.page_name}'"
                )
                item_line += '\n' + '\n\n'.join(block_parts)
            lines.append(item_line)
            for sub_ordered, sub in nested:
                lines.append(self._render_list_inner(sub, sub_ordered, depth + 1))
        return '\n'.join(lines)

    def _render_blockquote(self, tag: Tag) -> str:
        inner = self._render_children(tag).strip()
        if not inner:
            return ''
        quoted = '\n'.join(f"> {line}" for line in inner.split('\n'))
        return '\n' + quoted

    TABLE_KEEP_ATTRS = frozenset({'colspan', 'rowspan', 'style'})

    def _render_table(self, tag: Tag) -> str:
        return '\n' + self._serialize_table_node(tag, depth=0) + '\n'

    def _serialize_table_node(self, tag: Tag, depth: int) -> str:
        indent = '    ' * depth
        attrs = self._table_filtered_attrs(tag)
        attr_str = self._format_html_attrs(attrs)

        if tag.name in ('td', 'th'):
            inner = self._render_cell_inner(tag, depth)
            return f'{indent}<{tag.name}{attr_str}>{inner}</{tag.name}>'

        child_lines = []
        for child in tag.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    child_lines.append('    ' * (depth + 1) + text)
                continue
            if not isinstance(child, Tag):
                continue
            if child.name == 'colgroup':
                continue
            child_lines.append(self._serialize_table_node(child, depth + 1))

        if not child_lines:
            return f'{indent}<{tag.name}{attr_str}></{tag.name}>'
        return (
            f'{indent}<{tag.name}{attr_str}>\n'
            + '\n'.join(child_lines)
            + f'\n{indent}</{tag.name}>'
        )

    TH_DEFAULT_BG = '#F4F5F7'

    def _table_filtered_attrs(self, tag: Tag) -> dict:
        keep = {k: v for k, v in tag.attrs.items() if k in self.TABLE_KEEP_ATTRS}
        if tag.name in ('td', 'th'):
            colour = tag.attrs.get('data-highlight-colour')
            if colour:
                if colour == 'grey':
                    colour = self.TH_DEFAULT_BG
                self._merge_style(keep, f'background-color: {colour};')
            if tag.name == 'th' and 'background-color:' not in keep.get('style', ''):
                self._merge_style(keep, f'background-color: {self.TH_DEFAULT_BG};')
        return keep

    def _merge_style(self, keep: dict, addition: str) -> None:
        existing = keep.get('style', '').rstrip().rstrip(';').rstrip()
        keep['style'] = f'{existing}; {addition}' if existing else addition

    def _format_html_attrs(self, attrs: dict) -> str:
        if not attrs:
            return ''
        return ' ' + ' '.join(f'{k}="{v}"' for k, v in attrs.items())

    def _render_cell_inner(self, cell: Tag, depth: int) -> str:
        return self._serialize_cell_children(cell, depth)

    def _serialize_cell_children(self, parent: Tag, depth: int) -> str:
        parts = []
        for child in parent.children:
            if isinstance(child, NavigableString):
                parts.append(str(child))
            elif isinstance(child, Tag):
                if self._is_empty_p_with_only_br(child):
                    continue
                if child.name == 'table':
                    parts.append(self._serialize_table_node(child, depth + 1).lstrip())
                else:
                    parts.append(self._render_cell_node(child, depth))
        return ''.join(parts)

    def _is_empty_p_with_only_br(self, tag: Tag) -> bool:
        if tag.name != 'p':
            return False
        has_br = False
        for child in tag.children:
            if isinstance(child, NavigableString):
                if str(child).strip():
                    return False
            elif isinstance(child, Tag):
                if child.name == 'br':
                    has_br = True
                else:
                    return False
        return has_br

    def _render_cell_node(self, tag: Tag, depth: int) -> str:
        if tag.name == 'pre':
            self.warnings.append(
                f"<pre> inside table cell (kept as raw HTML) on page '{self.page_name}'"
            )
        if tag.name == 'ac:link':
            return self._extract_ac_link_text(tag)
        if tag.name == 'ac:image':
            img = self._render_ac_image_in_cell(tag)
            if img is not None:
                return img
        if tag.name == 'ac:structured-macro':
            collapsed = self._render_cell_expand(tag, depth)
            if collapsed is not None:
                return collapsed
        if tag.name and tag.name.startswith('ac:'):
            return str(tag).replace('<', '&lt;').replace('>', '&gt;')
        if self._cell_wrapper_should_strip(tag):
            return self._serialize_cell_children(tag, depth)
        attr_str = self._format_html_attrs(self._table_filtered_attrs(tag))
        children = list(tag.children)
        if not children:
            if tag.name in ('br', 'img', 'hr'):
                return f'<{tag.name}{attr_str}/>'
            return f'<{tag.name}{attr_str}></{tag.name}>'
        inner = self._serialize_cell_children(tag, depth)
        return f'<{tag.name}{attr_str}>{inner}</{tag.name}>'

    def _cell_wrapper_should_strip(self, tag: Tag) -> bool:
        if tag.name == 'div' and 'content-wrapper' in (tag.attrs.get('class') or []):
            return True
        if tag.name == 'p' and self._p_has_only_escaped_ac_macros(tag):
            return True
        return False

    def _p_has_only_escaped_ac_macros(self, p: Tag) -> bool:
        has_macro = False
        for child in p.children:
            if isinstance(child, NavigableString):
                if str(child).strip():
                    return False
            elif isinstance(child, Tag):
                if child.name == 'br':
                    continue
                name = child.name or ''
                if not name.startswith('ac:') or name == 'ac:link':
                    return False
                has_macro = True
        return has_macro

    def _render_cell_expand(self, tag: Tag, depth: int) -> str | None:
        macro_name = tag.attrs.get('ac:name', '')
        if macro_name not in ('expand', 'ui-expand'):
            return None
        title = self._direct_parameter_text(tag, 'title')
        if not title:
            if macro_name == 'expand':
                title = 'Click here to expand...'
            else:
                return None
        safe_title = _escape_html(title)
        body_tag = tag.find('ac:rich-text-body') or tag.find('ac:plain-text-body')
        body = self._serialize_cell_children(body_tag, depth) if body_tag is not None else ''
        return f'<details><summary>{safe_title}</summary>{body}</details>'

    def _render_ac_image_in_cell(self, tag: Tag) -> str | None:
        ri = tag.find('ri:attachment')
        filename = ri.attrs.get('ri:filename') if ri is not None else None
        if not filename:
            self.warnings.append(
                f"unsupported ac:image (no ri:filename) on page '{self.page_name}'"
            )
            return None
        filename = re.sub(r'\s', ' ', filename)
        parts = [f'src="{filename}"']
        width = tag.attrs.get('ac:width')
        if width:
            parts.append(f'width="{width}"')
        height = tag.attrs.get('ac:height')
        if height:
            parts.append(f'height="{height}"')
        return f'<img {" ".join(parts)} />'

    def _extract_ac_link_text(self, tag: Tag) -> str:
        body = tag.find('ac:plain-text-link-body')
        if body is not None:
            return body.get_text()
        ri = tag.find('ri:page')
        if ri is not None:
            return ri.attrs.get('ri:content-title', '')
        return tag.get_text()

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
        page_param = tag.find('ac:parameter', attrs={'ac:name': 'page'})
        if page_param is None:
            return self._dataview_children('this')
        ri_page = page_param.find('ri:page')
        title = ri_page.attrs.get('ri:content-title', '') if ri_page is not None else ''
        if not title:
            return self._dataview_children('this')
        if title not in self.title_map:
            self.warnings.append(f"children macro references unmigrated page: {title}")
            return ''
        return self._dataview_children(self.title_map[title])

    def _dataview_children(self, target: str) -> str:
        if target == 'this':
            scope = 'this.file.folder + "/" + this.file.name'
        else:
            scope = f'[[{target}]].file.folder + "/" + [[{target}]].file.name'
        return (
            '\n```dataview\n'
            'LIST\n'
            'FROM ""\n'
            f'WHERE file.folder = {scope}\n'
            '```'
        )

    def _render_excerpt(self, tag: Tag) -> str:
        body_tag = tag.find('ac:rich-text-body') or tag.find('ac:plain-text-body')
        if body_tag is None:
            inner = self._render_children(tag).strip()
        else:
            inner = self._render_children(body_tag).strip()
        if not inner:
            return ''
        return f"\n```excerpt\n{inner}\n```\n^excerpt\n\n"

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
        header = f"> [!{callout_type}]- {title}"
        if not body:
            return f"\n\n{header}"
        body = re.sub(r'\n{3,}', '\n\n', body)
        quoted = '\n'.join(f"> {line}" if line else ">" for line in body.split('\n'))
        return f"\n\n{header}\n{quoted}"

    def _render_ui_tabs(self, tag: Tag) -> str:
        body_tag = tag.find('ac:rich-text-body')
        if body_tag is None:
            return ''
        tab_blocks = []
        for child in body_tag.children:
            if (isinstance(child, Tag)
                and child.name == 'ac:structured-macro'
                and child.attrs.get('ac:name', '') == 'ui-tab'):
                tab_blocks.append(self._render_one_ui_tab(child))
        if not tab_blocks:
            return ''
        return '\n~~~tabs\n' + '\n'.join(tab_blocks) + '\n~~~'

    def _render_one_ui_tab(self, tag: Tag) -> str:
        title = self._direct_parameter_text(tag, 'title')
        body_tag = tag.find('ac:rich-text-body')
        body = self._render_children(body_tag).strip() if body_tag is not None else ''
        if body:
            return f"---tab {title}\n{body}"
        return f"---tab {title}"

    def _render_widget(self, tag: Tag) -> str:
        param = self._direct_parameter(tag, 'url')
        if param is None:
            return ''
        ri_url = param.find('ri:url')
        href = ri_url.attrs.get('ri:value', '') if ri_url is not None else param.get_text().strip()
        if not href:
            return ''
        return f"![]({href})"

    def _render_file_embed(self, tag: Tag) -> str:
        attach = tag.find('ri:attachment')
        if attach is None:
            return ''
        filename = attach.attrs.get('ri:filename', '')
        if not filename:
            return ''
        self.attachments_referenced.append(filename)
        return f"![[{self.page_name}/{filename}]]"

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
            return f"[{text}]({href})"
        if attach is not None:
            filename = attach.attrs.get('ri:filename', '')
            self.attachments_referenced.append(filename)
            if display:
                return f"[[{self.page_name}/{filename}|{display}]]"
            return f"[[{self.page_name}/{filename}]]"
        return display

    def _render_ac_image(self, tag: Tag) -> str:
        attach = tag.find('ri:attachment')
        if attach is not None:
            filename = attach.attrs.get('ri:filename', '')
            self.attachments_referenced.append(filename)
            return f"![[{self.page_name}/{filename}]]"
        url = tag.find('ri:url')
        if url is not None:
            return f"![]({url.attrs.get('ri:value', '')})"
        return ''
