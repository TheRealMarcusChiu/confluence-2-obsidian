from src.converter import Converter


def convert(xml: str, page_name: str = "TestPage") -> str:
    return Converter(page_name).convert(xml).strip()


def test_plain_paragraph():
    assert convert("<p>Hello world</p>") == "Hello world"


def test_bold_and_italic():
    assert convert("<p><strong>bold</strong> and <em>italic</em></p>") == "**bold** and *italic*"


def test_h1_h2_h3_pass_through_unchanged():
    assert convert("<h1>Top</h1>") == "# Top"
    assert convert("<h2>Sub</h2>") == "## Sub"
    assert convert("<h3>Sub Sub</h3>") == "### Sub Sub"


def test_h4_h5_h6_all_clamp_to_six_hashes():
    assert convert("<h4>Astrology</h4>") == "###### Astrology"
    assert convert("<h5>Deep</h5>") == "###### Deep"
    assert convert("<h6>Deepest</h6>") == "###### Deepest"


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


def test_sub_preserved_as_raw_html():
    assert convert("<p>H<sub>2</sub>O</p>") == "H<sub>2</sub>O"


def test_sup_preserved_as_raw_html():
    assert convert("<p>E = mc<sup>2</sup></p>") == "E = mc<sup>2</sup>"


def test_sup_with_spaces_and_inline_markup():
    out = convert("<p>x<sup>n + 1</sup> and y<sub><strong>k</strong></sub></p>")
    assert "x<sup>n + 1</sup>" in out
    assert "y<sub>**k**</sub>" in out


def test_inline_code_emitted_as_raw_html():
    assert convert("<p>use <code>foo()</code> here</p>") == "use <code>foo()</code> here"


def test_span_with_color_becomes_font():
    xml = '<p><span style="color: rgb(128,128,128);">gray text</span></p>'
    assert convert(xml) == '<font style="color: rgb(128,128,128);">gray text</font>'


def test_span_without_color_is_stripped():
    assert convert('<p><span class="x">plain</span></p>') == "plain"
    assert convert('<p><span>plain</span></p>') == "plain"


def test_span_with_color_and_other_styles_preserves_full_style():
    xml = '<p><span style="color: rgb(255,0,0); background-color: yellow;">x</span></p>'
    out = convert(xml)
    assert '<font style="color: rgb(255,0,0); background-color: yellow;">x</font>' in out


def test_colored_inline_code_composes():
    xml = '<p><code><span style="color: rgb(128,128,128);">CODE</span></code></p>'
    assert convert(xml) == '<code><font style="color: rgb(128,128,128);">CODE</font></code>'


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


def test_macro_children_with_page_param_in_title_map():
    xml = '<ac:structured-macro ac:name="children"><ac:parameter ac:name="page"><ac:link><ri:page ri:content-title="Computer" /></ac:link></ac:parameter></ac:structured-macro>'
    c = Converter("p", title_map={"Computer": "Computer"})
    out = c.convert(xml).strip()
    assert "```dataview" in out
    assert 'WHERE file.folder = [[Computer]].file.folder + "/" + [[Computer]].file.name' in out
    assert c.warnings == []


def test_macro_children_with_page_param_uses_collision_resolved_title():
    xml = '<ac:structured-macro ac:name="children"><ac:parameter ac:name="page"><ac:link><ri:page ri:content-title="Design: v2" /></ac:link></ac:parameter></ac:structured-macro>'
    c = Converter("p", title_map={"Design: v2": "Design  v2 (123)"})
    out = c.convert(xml).strip()
    assert 'WHERE file.folder = [[Design  v2 (123)]].file.folder + "/" + [[Design  v2 (123)]].file.name' in out


def test_macro_children_with_page_param_not_migrated_drops_and_logs():
    xml = '<ac:structured-macro ac:name="children"><ac:parameter ac:name="page"><ac:link><ri:page ri:content-title="External Page" /></ac:link></ac:parameter></ac:structured-macro>'
    c = Converter("p", title_map={"Computer": "Computer"})
    out = c.convert(xml).strip()
    assert "```dataview" not in out
    assert out == ""
    assert len(c.warnings) == 1
    assert "External Page" in c.warnings[0]


def test_macro_excerpt_fenced_block_with_anchor():
    xml = '<ac:structured-macro ac:name="excerpt"><ac:rich-text-body><p>excerpt body</p></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "```excerpt\nexcerpt body\n```\n^excerpt" in out
    assert "> [!quote]" not in out


def test_macro_excerpt_preserves_markdown_inside_fence():
    xml = '<ac:structured-macro ac:name="excerpt"><ac:rich-text-body><p><strong>bold</strong> and <em>italic</em></p></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "```excerpt" in out
    assert "**bold** and *italic*" in out
    assert "```\n^excerpt" in out


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


def test_macro_info_callout():
    xml = '<ac:structured-macro ac:name="info"><ac:rich-text-body><p>heads up</p></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "> [!info]" in out
    assert "> heads up" in out
    assert "^excerpt" not in out


def test_macro_warning_callout():
    xml = '<ac:structured-macro ac:name="warning"><ac:rich-text-body><p>careful</p></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "> [!warning]" in out
    assert "> careful" in out


def test_macro_expand_with_title():
    xml = '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">TITLE HERE</ac:parameter><ac:rich-text-body><p>content here</p></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "<details>" in out
    assert "<summary>TITLE HERE</summary>" in out
    assert "content here" in out
    assert "</details>" in out


def test_macro_expand_without_title_inlines_body():
    xml = '<ac:structured-macro ac:name="expand"><ac:rich-text-body><p>content here</p></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "<details>" not in out
    assert "content here" in out


def test_macro_ui_expand_with_title():
    xml = '<ac:structured-macro ac:name="ui-expand"><ac:parameter ac:name="title">UI TITLE</ac:parameter><ac:rich-text-body><p>body</p></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "<summary>UI TITLE</summary>" in out
    assert "body" in out


def test_macro_expand_escapes_html_in_title():
    xml = '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">a &lt; b</ac:parameter><ac:rich-text-body><p>x</p></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "<summary>a &lt; b</summary>" in out


def test_macro_anchor_dropped_silently():
    c = Converter("p")
    out = c.convert('<p>before<ac:structured-macro ac:name="anchor"><ac:parameter ac:name="">x</ac:parameter></ac:structured-macro>after</p>').strip()
    assert "anchor" not in c.unknown_macros
    assert "before" in out and "after" in out


def test_macro_toc_dropped_silently():
    c = Converter("p")
    out = c.convert('<ac:structured-macro ac:name="toc"></ac:structured-macro>').strip()
    assert out == ""
    assert "toc" not in c.unknown_macros


def test_macro_view_file_emits_attachment_embed():
    xml = '<ac:structured-macro ac:name="view-file"><ac:parameter ac:name="name"><ri:attachment ri:filename="report.docx" /></ac:parameter></ac:structured-macro>'
    c = Converter("MyPage")
    out = c.convert(xml).strip()
    assert out == "![[MyPage/report.docx]]"
    assert "report.docx" in c.attachments_referenced


def test_macro_viewpdf_emits_attachment_embed():
    xml = '<ac:structured-macro ac:name="viewpdf"><ac:parameter ac:name="name"><ri:attachment ri:filename="doc.pdf" /></ac:parameter></ac:structured-macro>'
    out = convert(xml, page_name="MyPage")
    assert out == "![[MyPage/doc.pdf]]"


def test_macro_multimedia_emits_attachment_embed():
    xml = '<ac:structured-macro ac:name="multimedia"><ac:parameter ac:name="name"><ri:attachment ri:filename="clip.mp4" /></ac:parameter></ac:structured-macro>'
    out = convert(xml, page_name="MyPage")
    assert out == "![[MyPage/clip.mp4]]"


def test_macro_ui_tabs_and_ui_tab_stacked_details():
    xml = (
        '<ac:structured-macro ac:name="ui-tabs"><ac:rich-text-body>'
        '<p class="auto-cursor-target"><br /></p>'
        '<ac:structured-macro ac:name="ui-tab"><ac:parameter ac:name="title">Tab 1</ac:parameter>'
        '<ac:rich-text-body><p>Tab 1 content here</p></ac:rich-text-body></ac:structured-macro>'
        '<p class="auto-cursor-target"><br /></p>'
        '<ac:structured-macro ac:name="ui-tab"><ac:parameter ac:name="title">Tab 2</ac:parameter>'
        '<ac:rich-text-body><p>Tab 2 content here</p></ac:rich-text-body></ac:structured-macro>'
        '<p class="auto-cursor-target"><br /></p>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml)
    assert out.count("<details>") == 2
    assert "<summary>Tab 1</summary>" in out
    assert "<summary>Tab 2</summary>" in out
    assert "Tab 1 content here" in out
    assert "Tab 2 content here" in out


def test_macro_widget_youtube_embed():
    xml = '<ac:structured-macro ac:name="widget"><ac:parameter ac:name="url"><ri:url ri:value="https://www.youtube.com/watch?v=abc" /></ac:parameter></ac:structured-macro>'
    out = convert(xml)
    assert out == "![](https://www.youtube.com/watch?v=abc)"


def test_macro_section_dropped_with_body():
    c = Converter("p")
    out = c.convert(
        '<ac:structured-macro ac:name="section"><ac:rich-text-body><p>hidden content</p></ac:rich-text-body></ac:structured-macro>'
    ).strip()
    assert out == ""
    assert "hidden content" not in out
    assert "section" not in c.unknown_macros


def test_macro_details_dropped_with_body():
    c = Converter("p")
    out = c.convert(
        '<ac:structured-macro ac:name="details"><ac:rich-text-body><table><tr><th>k</th><td>v</td></tr></table></ac:rich-text-body></ac:structured-macro>'
    ).strip()
    assert out == ""
    assert "details" not in c.unknown_macros


def test_macro_pagetree_dropped_silently():
    c = Converter("p")
    out = c.convert('<ac:structured-macro ac:name="pagetree"></ac:structured-macro>').strip()
    assert out == ""
    assert "pagetree" not in c.unknown_macros


def test_macro_pagetreesearch_and_livesearch_dropped():
    c = Converter("p")
    out = c.convert(
        '<ac:structured-macro ac:name="pagetreesearch"></ac:structured-macro>'
        '<ac:structured-macro ac:name="livesearch"></ac:structured-macro>'
    ).strip()
    assert out == ""
    assert "pagetreesearch" not in c.unknown_macros
    assert "livesearch" not in c.unknown_macros


def test_macro_recently_updated_dataview():
    xml = (
        '<ac:structured-macro ac:name="recently-updated">'
        '<ac:parameter ac:name="types">page</ac:parameter>'
        '<ac:parameter ac:name="max">15</ac:parameter>'
        '<ac:parameter ac:name="spaces"><ri:space ri:space-key="@self" /></ac:parameter>'
        '<ac:parameter ac:name="theme">concise</ac:parameter>'
        '</ac:structured-macro>'
    )
    out = convert(xml)
    assert "```dataview" in out
    assert "SORT modified DESC" in out
    assert "LIMIT 15" in out
    assert 'FROM ""' in out


def test_macro_recently_updated_defaults_to_15_when_max_missing():
    xml = '<ac:structured-macro ac:name="recently-updated"></ac:structured-macro>'
    out = convert(xml)
    assert "LIMIT 15" in out


def test_spacing_no_blank_line_between_heading_and_list():
    xml = "<h1>Title</h1>\n<ul><li>item</li></ul>"
    out = convert(xml)
    assert out == "# Title\n- item"


def test_spacing_no_blank_line_between_heading_and_code_block():
    xml = '<h1>Title</h1>\n<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">py</ac:parameter><ac:plain-text-body><![CDATA[x = 1]]></ac:plain-text-body></ac:structured-macro>'
    out = convert(xml)
    assert out == "# Title\n```py\nx = 1\n```"


def test_spacing_blank_line_after_excerpt_anchor():
    xml = '<ac:structured-macro ac:name="excerpt"><ac:rich-text-body><p>body</p></ac:rich-text-body></ac:structured-macro><h1>Next</h1>'
    out = convert(xml)
    assert "^excerpt\n\n# Next" in out


def test_spacing_blank_line_between_paragraphs():
    xml = "<p>first</p>\n<p>second</p>"
    out = convert(xml)
    assert out == "first\n\nsecond"


def test_spacing_paragraph_wrapping_only_macro_is_unwrapped():
    xml = '<h1>Subpages</h1>\n<p><ac:structured-macro ac:name="children" /></p>'
    out = convert(xml)
    assert out.startswith("# Subpages\n```dataview")


def test_spacing_pure_whitespace_text_between_blocks_ignored():
    xml = "<h1>A</h1>\n\n\n<h2>B</h2>"
    out = convert(xml)
    assert out == "# A\n## B"


def test_attachments_referenced_tracked():
    c = Converter("MyPage")
    c.convert('<ac:image><ri:attachment ri:filename="a.png" /></ac:image>')
    c.convert('<ac:image><ri:attachment ri:filename="b.png" /></ac:image>')
    assert "a.png" in c.attachments_referenced
    assert "b.png" in c.attachments_referenced
