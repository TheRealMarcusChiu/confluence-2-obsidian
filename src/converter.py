import re
from bs4 import BeautifulSoup, NavigableString, Tag

from src.sanitize import sanitize_title


CDATA_RE = re.compile(r'<!\[CDATA\[(.*?)\]\]>', re.DOTALL)


def _escape_html(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _unescape_html(text: str) -> str:
    return text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')


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
            return '\\\n'
        if name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            return self._render_heading(tag, int(name[1]))
        if name in ('strong', 'b'):
            return f"**{self._inline(tag)}**"
        if name in ('em', 'i'):
            return f"*{self._inline(tag)}*"
        if name == 'u':
            return f"<u>{self._inline(tag)}</u>"
        if name == 'code':
            return f"`{self._inline(tag)}`"
        if name == 'pre':
            return f"\n```\n{self._render_children(tag)}\n```"
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
        indent = '  ' * depth
        for i, item in enumerate(items):
            marker = f"{i+1}." if ordered else "-"
            inline_parts = []
            nested = []
            for child in item.children:
                if isinstance(child, Tag) and child.name in ('ul', 'ol'):
                    nested.append((child.name == 'ol', child))
                else:
                    inline_parts.append(self._render(child))
            body = ''.join(inline_parts).strip().replace('\n', ' ')
            lines.append(f"{indent}{marker} {body}".rstrip())
            for sub_ordered, sub in nested:
                lines.append(self._render_list_inner(sub, sub_ordered, depth + 1))
        return '\n'.join(lines)

    def _render_blockquote(self, tag: Tag) -> str:
        inner = self._render_children(tag).strip()
        if not inner:
            return ''
        quoted = '\n'.join(f"> {line}" for line in inner.split('\n'))
        return '\n' + quoted

    def _render_table(self, tag: Tag) -> str:
        for cell in tag.find_all(['td', 'th']):
            if cell.attrs.get('colspan') or cell.attrs.get('rowspan'):
                return '\n' + str(tag)
        rows = tag.find_all('tr')
        if not rows:
            return ''
        lines = []
        for i, row in enumerate(rows):
            cells = row.find_all(['td', 'th'])
            texts = []
            for c in cells:
                t = self._inline(c).replace('\n', ' ').replace('|', '\\|')
                texts.append(t.strip())
            lines.append('| ' + ' | '.join(texts) + ' |')
            if i == 0:
                lines.append('| ' + ' | '.join('---' for _ in cells) + ' |')
        return '\n' + '\n'.join(lines)

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
        if name in ('latex-inline', 'latex'):
            body = self._macro_text_body(tag).strip()
            return f"${body}$"
        if name == 'latex-block':
            body = self._macro_text_body(tag).strip()
            return f"\n$${body}$$"
        if name == 'code':
            return self._render_code_macro(tag)
        if name == 'info':
            return self._render_callout(tag, 'info')
        if name == 'warning':
            return self._render_callout(tag, 'warning')
        if name in ('expand', 'ui-expand', 'ui-tab'):
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
        title = self._direct_parameter_text(tag, 'title')
        body_tag = tag.find('ac:rich-text-body') or tag.find('ac:plain-text-body')
        body = self._render_children(body_tag).strip() if body_tag is not None else ''
        if not title:
            return f"\n{body}" if body else ''
        safe_title = _escape_html(title)
        return f"\n<details>\n<summary>{safe_title}</summary>\n\n{body}\n\n</details>"

    def _render_ui_tabs(self, tag: Tag) -> str:
        body_tag = tag.find('ac:rich-text-body')
        target = body_tag if body_tag is not None else tag
        return '\n' + self._render_children(target).strip()

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
