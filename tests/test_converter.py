from src.converter import Converter


def convert(xml: str, page_name: str = "TestPage") -> str:
    return Converter(page_name).convert(xml).strip()


def test_plain_paragraph():
    assert convert("<p>Hello world</p>") == "Hello world"


def test_bold_and_italic():
    assert convert("<p><strong>bold</strong> and <em>italic</em></p>") == "**bold** and *italic*"


def test_heading_shifts_down_one_level():
    assert convert("<h1>Top</h1>") == "## Top"
    assert convert("<h2>Sub</h2>") == "### Sub"
    assert convert("<h5>Deep</h5>") == "###### Deep"


def test_h6_becomes_seven_hashes_with_warning():
    c = Converter("p")
    out = c.convert("<h6>x</h6>")
    assert "####### x" in out
    assert any("h6" in w for w in c.warnings)


def test_unordered_list():
    out = convert("<ul><li>a</li><li>b</li></ul>")
    assert "- a" in out and "- b" in out


def test_ordered_list():
    out = convert("<ol><li>a</li><li>b</li></ol>")
    assert "1. a" in out and "2. b" in out


def test_nested_list():
    xml = "<ul><li>parent<ul><li>child</li></ul></li></ul>"
    out = convert(xml)
    assert "- parent" in out
    assert "  - child" in out


def test_br_becomes_backslash_break():
    out = convert("<p>line1<br/>line2</p>")
    assert "line1\\\nline2" in out


def test_external_link():
    out = convert('<p><a href="https://example.com">site</a></p>')
    assert "[site](https://example.com)" in out


def test_simple_table_pipe():
    xml = "<table><tbody><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></tbody></table>"
    out = convert(xml)
    assert "| A | B |" in out
    assert "| --- | --- |" in out
    assert "| 1 | 2 |" in out


def test_merged_cell_table_kept_as_html():
    xml = '<table><tbody><tr><td colspan="2">spanned</td></tr><tr><td>a</td><td>b</td></tr></tbody></table>'
    out = convert(xml)
    assert "<table>" in out
    assert 'colspan="2"' in out


def test_macro_code_with_language():
    xml = '<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">python</ac:parameter><ac:plain-text-body><![CDATA[print("hi")]]></ac:plain-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "```python" in out
    assert 'print("hi")' in out
    assert "```" in out


def test_macro_latex_inline():
    xml = '<ac:structured-macro ac:name="latex-inline"><ac:plain-text-body><![CDATA[x^2]]></ac:plain-text-body></ac:structured-macro>'
    out = convert(xml)
    assert out == "$x^2$"


def test_macro_latex_block():
    xml = '<ac:structured-macro ac:name="latex-block"><ac:plain-text-body><![CDATA[\\int x dx]]></ac:plain-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "$$\\int x dx$$" in out


def test_macro_children_display():
    xml = '<ac:structured-macro ac:name="children"></ac:structured-macro>'
    out = convert(xml)
    assert "```dataview" in out
    assert 'WHERE file.folder = this.file.folder + "/" + this.file.name' in out


def test_macro_excerpt_wraps_in_callout():
    xml = '<ac:structured-macro ac:name="excerpt"><ac:rich-text-body><p>excerpt body</p></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "> [!quote]" in out
    assert "> excerpt body" in out
    assert "^excerpt" in out


def test_macro_excerpt_include_extracts_page_title():
    xml = '<ac:structured-macro ac:name="excerpt-include"><ac:parameter ac:name="nopanel">true</ac:parameter><ac:parameter ac:name=""><ac:link><ri:page ri:content-title="AI - Subfields" /></ac:link></ac:parameter></ac:structured-macro>'
    out = convert(xml)
    assert out == "![[AI - Subfields#^excerpt]]"


def test_unknown_macro_logged_and_skipped():
    c = Converter("p")
    out = c.convert('<p>before<ac:structured-macro ac:name="mystery"></ac:structured-macro>after</p>')
    assert "mystery" in c.unknown_macros
    assert "before" in out and "after" in out


def test_internal_page_link():
    xml = '<ac:link><ri:page ri:content-title="Other Page" /><ac:plain-text-link-body><![CDATA[Custom Text]]></ac:plain-text-link-body></ac:link>'
    out = convert(xml)
    assert out == "[[Other Page|Custom Text]]"


def test_internal_page_link_no_body():
    xml = '<ac:link><ri:page ri:content-title="Other Page" /></ac:link>'
    out = convert(xml)
    assert out == "[[Other Page]]"


def test_inline_image_attachment():
    xml = '<ac:image><ri:attachment ri:filename="diagram.png" /></ac:image>'
    out = convert(xml, page_name="MyPage")
    assert out == "![[MyPage/diagram.png]]"


def test_image_with_ri_url_youtube():
    xml = '<ac:image><ri:url ri:value="https://youtube.com/watch?v=abc" /></ac:image>'
    out = convert(xml)
    assert out == "![](https://youtube.com/watch?v=abc)"


def test_blockquote():
    xml = "<blockquote><p>quoted text</p></blockquote>"
    out = convert(xml)
    assert "> quoted text" in out


def test_link_target_sanitized_when_title_has_invalid_chars():
    xml = '<ac:link><ri:page ri:content-title="Design: v2" /></ac:link>'
    out = convert(xml)
    assert out == "[[Design  v2|Design: v2]]"


def test_link_target_uses_title_map_for_collision():
    xml = '<ac:link><ri:page ri:content-title="Design: v2" /></ac:link>'
    c = Converter("p", title_map={"Design: v2": "Design  v2 (123)"})
    out = c.convert(xml).strip()
    assert out == "[[Design  v2 (123)|Design: v2]]"


def test_excerpt_include_uses_resolved_target():
    xml = '<ac:structured-macro ac:name="excerpt-include"><ac:parameter ac:name=""><ac:link><ri:page ri:content-title="Design: v2" /></ac:link></ac:parameter></ac:structured-macro>'
    out = convert(xml)
    assert out == "![[Design  v2#^excerpt]]"


def test_attachments_referenced_tracked():
    c = Converter("MyPage")
    c.convert('<ac:image><ri:attachment ri:filename="a.png" /></ac:image>')
    c.convert('<ac:image><ri:attachment ri:filename="b.png" /></ac:image>')
    assert "a.png" in c.attachments_referenced
    assert "b.png" in c.attachments_referenced
