from src.converter import Converter, _inject_list_placeholders


def convert(xml: str, page_name: str = "TestPage") -> str:
    return Converter(page_name).convert(xml).strip()


def test_list_followed_by_macro_has_blank_line():
    xml = '<ul><li>X</li></ul><ac:structured-macro ac:name="info"><ac:rich-text-body><p>note</p></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml)
    assert out == "- X\n\n> [!info]\n> note"


def test_list_followed_by_latex_block_has_blank_line():
    xml = '<ul><li>X</li></ul><ac:structured-macro ac:name="latex-block"><ac:plain-text-body><![CDATA[y]]></ac:plain-text-body></ac:structured-macro>'
    out = convert(xml)
    assert out == "- X\n\n$y$"


def test_list_followed_by_heading_has_blank_line():
    xml = "<ul><li>X</li></ul><h2>Title</h2>"
    out = convert(xml)
    assert out == "- X\n\n## Title"


def test_nested_list_no_extra_blank_line_after_inner():
    xml = "<ul><li>outer<ul><li>inner</li></ul></li></ul>"
    out = convert(xml)
    assert out == "- outer\n\t- inner"


def test_li_with_p_and_text_after_hoists_to_next_line():
    xml = '<ul><li><p class="auto-cursor-target">hello world</p>after-text</li></ul>'
    out = convert(xml)
    assert out == "- hello world\nafter-text"


def test_li_with_p_and_strong_after_hoists():
    xml = '<ul><li><p class="auto-cursor-target">X</p><strong>Y</strong></li></ul>'
    out = convert(xml)
    assert out == "- X\n**Y**"


def test_li_with_empty_p_then_inline_macro_keeps_macro_inline():
    # Empty <p> shouldn't claim the <p>-split — the latex should stay inline
    # on the list-item line, not get hoisted out leaving a bare "- ".
    xml = '<ul><li><p></p><ac:structured-macro ac:name="latex-inline"><ac:plain-text-body><![CDATA[X]]></ac:plain-text-body></ac:structured-macro></li></ul>'
    out = convert(xml)
    assert out == "- $X$"


def test_li_with_cursor_park_p_then_inline_macro_keeps_macro_inline():
    xml = '<ul><li><p><br/></p><ac:structured-macro ac:name="latex-inline"><ac:plain-text-body><![CDATA[X]]></ac:plain-text-body></ac:structured-macro></li></ul>'
    out = convert(xml)
    assert out == "- $X$"


def test_li_with_only_p_no_hoist():
    xml = '<ul><li><p>just paragraph</p></li></ul>'
    out = convert(xml)
    assert out == "- just paragraph"


def test_li_with_p_followed_by_another_p_hoists_second():
    xml = '<ul><li><p>first</p><p>second</p></li></ul>'
    out = convert(xml)
    assert out == "- first\nsecond"


def test_inject_list_placeholders_indented_list_after_non_list_content():
    src = "ANY_NON_LIST_CONTENT\n\t- Hello"
    assert _inject_list_placeholders(src) == "ANY_NON_LIST_CONTENT\n- \n\t- Hello"


def test_inject_list_placeholders_valid_list_unchanged():
    src = "ANY_NON_LIST_CONTENT\n- ANYTHING\n\t- Hello"
    assert _inject_list_placeholders(src) == src


def test_inject_list_placeholders_recursive_for_deeper_jump():
    src = "ANY_NON_LIST_CONTENT\n\t\t- Hello"
    expected = "ANY_NON_LIST_CONTENT\n- \n\t- \n\t\t- Hello"
    assert _inject_list_placeholders(src) == expected


def test_adjacent_ordered_lists_with_cursor_park_break_inserts_blockquote_separator():
    # Confluence emits a cursor-park <p><br/></p> between two <ol>s; the empty
    # paragraph is dropped, so without the separator the two lists merge into
    # one in Obsidian. The post-process inserts an empty-blockquote breaker.
    xml = (
        '<ol><li>HELLO</li><li>WORLD</li></ol>'
        '<p><br /></p>'
        '<ol><li>HELLO</li><li>WORLD</li></ol>'
    )
    assert convert(xml) == "1. HELLO\n2. WORLD\n\n> \n\n1. HELLO\n2. WORLD"


def test_single_ordered_list_does_not_get_blockquote_separator():
    xml = '<ol><li>A</li><li>B</li><li>C</li></ol>'
    assert convert(xml) == "1. A\n2. B\n3. C"


def test_ordered_lists_separated_by_text_paragraph_no_separator():
    # Real content between the two <ol>s already breaks the merge — no
    # post-process injection needed.
    xml = (
        '<ol><li>A</li></ol>'
        '<p>break</p>'
        '<ol><li>B</li></ol>'
    )
    out = convert(xml)
    assert "> " not in out
    assert "1. A" in out
    assert "break" in out
    assert "1. B" in out


def test_inject_list_placeholders_handles_mid_list_jump():
    src = "- something\n\t\t- Hello"
    expected = "- something\n\t- \n\t\t- Hello"
    assert _inject_list_placeholders(src) == expected


def test_inject_list_placeholders_ordered_uses_dash_placeholder():
    # Deeper line is ordered; placeholder is always bare "- ", never "1. "
    src = "ANY_NON_LIST_CONTENT\n\t\t1. Hello"
    expected = "ANY_NON_LIST_CONTENT\n- \n\t- \n\t\t1. Hello"
    assert _inject_list_placeholders(src) == expected


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
    assert "\t- child" in out


def test_doubly_nested_list_uses_two_tabs():
    xml = "<ul><li>a<ul><li>b<ul><li>c</li></ul></li></ul></li></ul>"
    out = convert(xml)
    assert "- a" in out
    assert "\t- b" in out
    assert "\t\t- c" in out


def test_list_item_with_expand_hoists_callout_to_column_zero():
    xml = (
        '<ul style="list-style-type: square;"><li>'
        '<p class="auto-cursor-target">outside text</p>'
        '<ac:structured-macro ac:name="expand">'
        '<ac:rich-text-body><p>inside text</p></ac:rich-text-body>'
        '</ac:structured-macro>'
        '<p class="auto-cursor-target"><br /></p>'
        '</li></ul>'
    )
    out = convert(xml).strip()
    expected = (
        "- outside text\n"
        "> [!expand]- Click here to expand...\n"
        "> inside text"
    )
    assert out == expected


def test_list_item_with_ui_expand_hoists_callout_to_column_zero():
    xml = (
        '<ul><li>outer'
        '<ac:structured-macro ac:name="ui-expand"><ac:parameter ac:name="title">UI</ac:parameter>'
        '<ac:rich-text-body><p>ui body</p></ac:rich-text-body></ac:structured-macro>'
        '</li></ul>'
    )
    out = convert(xml).strip()
    expected = (
        "- outer\n"
        "> [!expand-ui]- UI\n"
        "> ui body"
    )
    assert out == expected


def test_list_item_with_multiple_blocks_separated_by_blank_line():
    xml = (
        '<ul><li>text'
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">A</ac:parameter>'
        '<ac:rich-text-body><p>body A</p></ac:rich-text-body></ac:structured-macro>'
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">B</ac:parameter>'
        '<ac:rich-text-body><p>body B</p></ac:rich-text-body></ac:structured-macro>'
        '</li></ul>'
    )
    out = convert(xml).strip()
    expected = (
        "- text\n"
        "> [!expand]- A\n"
        "> body A\n"
        "\n"
        "> [!expand]- B\n"
        "> body B"
    )
    assert out == expected


def test_list_item_with_only_expand_no_inline_text():
    xml = (
        '<ul><li>'
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">T</ac:parameter>'
        '<ac:rich-text-body><p>body</p></ac:rich-text-body></ac:structured-macro>'
        '</li></ul>'
    )
    out = convert(xml).strip()
    expected = (
        "- \n"
        "> [!expand]- T\n"
        "> body"
    )
    assert out == expected


def test_ordered_list_empty_item_with_block_content_keeps_marker_space():
    xml = (
        '<ol><li>'
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">T</ac:parameter>'
        '<ac:rich-text-body><p>body</p></ac:rich-text-body></ac:structured-macro>'
        '</li></ol>'
    )
    out = convert(xml).strip()
    expected = (
        "1. \n"
        "> [!expand]- T\n"
        "> body"
    )
    assert out == expected


def test_list_item_with_block_content_logs_warning():
    from src.converter import Converter
    xml = (
        '<ul><li>text'
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">T</ac:parameter>'
        '<ac:rich-text-body><p>body</p></ac:rich-text-body></ac:structured-macro>'
        '</li></ul>'
    )
    c = Converter('MyPage')
    c.convert(xml)
    assert any("MyPage" in w and "list item" in w.lower() for w in c.warnings)


def test_list_item_inline_only_unchanged_no_warning():
    from src.converter import Converter
    c = Converter('MyPage')
    out = c.convert("<ul><li>plain text</li><li>another</li></ul>").strip()
    assert out == "- plain text\n- another"
    assert not any("list item" in w.lower() for w in c.warnings)


def test_escape_brackets_in_paragraph():
    assert convert("<p>literal [draft] text</p>") == "literal \\[draft\\] text"


def test_escape_backslash_in_paragraph():
    assert convert("<p>path\\to\\file</p>") == "path\\\\to\\\\file"


def test_escape_dollar_in_paragraph():
    assert convert("<p>price is $5 or $10</p>") == "price is \\$5 or \\$10"


def test_escape_backtick_in_paragraph():
    assert convert("<p>use `quote` here</p>") == "use \\`quote\\` here"


def test_escape_asterisk_in_paragraph():
    assert convert("<p>star *foo* end</p>") == "star \\*foo\\* end"


def test_escape_underscore_in_paragraph():
    assert convert("<p>name_with_underscores</p>") == "name\\_with\\_underscores"


def test_escape_tilde_in_paragraph():
    assert convert("<p>~~strike~~</p>") == "\\~\\~strike\\~\\~"


def test_escape_hash_in_paragraph():
    assert convert("<p>issue #123</p>") == "issue \\#123"


def test_escape_combined_typed_backslash_bracket():
    # User typed `\]` in Confluence; output must render back as `\]` (not just `]`).
    # Source `\]` → after escape: `\` → `\\`, `]` → `\]`, giving `\\\]` (4 chars).
    assert convert("<p>typed \\] here</p>") == "typed \\\\\\] here"


def test_escape_applies_in_heading():
    assert convert("<h1>Section [v2]</h1>") == "# Section \\[v2\\]"


def test_escape_applies_in_list_item():
    out = convert("<ul><li>item [pending]</li></ul>").strip()
    assert out == "- item \\[pending\\]"


def test_escape_applies_inside_strong():
    out = convert("<p>before <strong>[bold]</strong> after</p>")
    assert out == "before **\\[bold\\]** after"


def test_escape_applies_inside_em():
    out = convert("<p><em>[italic]</em></p>")
    assert out == "*\\[italic\\]*"


def test_escape_applies_inside_u():
    out = convert("<p><u>[under]</u></p>")
    assert out == "<u>\\[under\\]</u>"


def test_escape_applies_inside_sub_sup():
    out = convert("<p>H<sub>[2]</sub>O<sup>[+]</sup></p>")
    assert out == "H<sub>\\[2\\]</sub>O<sup>\\[+\\]</sup>"


def test_escape_applies_inside_uncolored_span():
    out = convert('<p>before <span class="x">[span]</span> after</p>')
    assert out == "before \\[span\\] after"


def test_escape_brackets_only_inside_anchor_link_text():
    # Inside <a>: brackets ARE escaped (so [text](url) parser sees a clean link
    # display), but other chars stay verbatim so inline formatting still works.
    out = convert('<p>see <a href="https://example.com">[link text]</a> here</p>')
    assert "[\\[link text\\]](https://example.com)" in out


def test_escape_formatting_chars_not_escaped_inside_anchor():
    # `*`, `_`, `$`, etc. inside <a> are NOT escaped — formatting survives.
    out = convert('<p><a href="u">*bold* and $x$</a></p>')
    assert "[*bold* and $x$](u)" in out
    assert "\\*" not in out
    assert "\\$" not in out


def test_escape_suppressed_inside_code():
    assert convert("<p>use <code>[brackets]</code> here</p>") == "use <code>[brackets]</code> here"


def test_escape_suppressed_inside_pre():
    out = convert("<pre>[raw] code</pre>")
    assert "[raw] code" in out
    assert "\\[" not in out


def test_pre_in_table_cell_stays_raw_html_and_logs_warning():
    from src.converter import Converter
    xml = "<table><tr><td><pre>x</pre></td></tr></table>"
    c = Converter("MyPage")
    out = c.convert(xml).strip()
    assert "<pre>x</pre>" in out
    assert "<code>x</code>" not in out
    assert any("pre" in w.lower() and "MyPage" in w for w in c.warnings)


def test_pre_uncolored_span_unwraps_but_colored_becomes_font():
    out = convert('<pre><span>plain</span> <span style="color: red;">red</span></pre>')
    assert out == '<code>plain <font style="color: red;">red</font></code>'


def test_pre_strong_renders_as_literal_markdown():
    out = convert("<pre><strong>foo</strong></pre>")
    assert out == "<code>**foo**</code>"


def test_pre_empty_emits_nothing():
    assert convert("<pre></pre>") == ""
    assert convert("<pre>  \n  </pre>") == ""


def test_pre_splits_on_br_and_newline():
    out = convert("<pre>a<br/>b\nc</pre>")
    assert out == "<code>a</code>\n<code>b</code>\n<code>c</code>"


def test_pre_drops_trailing_empty_lines():
    out = convert("<pre>foo\n\n\n</pre>")
    assert out == "<code>foo</code>"


def test_pre_keeps_internal_empty_lines():
    out = convert("<pre>foo\n\nbar</pre>")
    assert out == "<code>foo</code>\n<code></code>\n<code>bar</code>"


def test_pre_emits_multi_code_one_per_line():
    xml = (
        '<pre>'
        '<span class="nf" style="color: rgb(0,0,255);">GET</span> '
        '<span class="nn" style="color: rgb(0,0,255);">/index.html</span> '
        '<span class="kr" style="color: rgb(0,128,0);">HTTP</span>'
        '<span class="o" style="color: rgb(102,102,102);">/</span>'
        '<span class="m" style="color: rgb(102,102,102);">1.1</span>\n'
        '<span class="na" style="color: rgb(125,144,41);">Host</span>'
        '<span class="o" style="color: rgb(102,102,102);">:</span> '
        '<span class="l">www.example.org</span>\n'
        '<span class="err">...<br /></span><br /><br />'
        '</pre>'
    )
    expected = (
        '<code><font style="color: rgb(0,0,255);">GET</font> '
        '<font style="color: rgb(0,0,255);">/index.html</font> '
        '<font style="color: rgb(0,128,0);">HTTP</font>'
        '<font style="color: rgb(102,102,102);">/</font>'
        '<font style="color: rgb(102,102,102);">1.1</font></code>\n'
        '<code><font style="color: rgb(125,144,41);">Host</font>'
        '<font style="color: rgb(102,102,102);">:</font> www.example.org</code>\n'
        '<code>...</code>'
    )
    assert convert(xml) == expected


def test_escape_suppressed_inside_colored_span_font():
    out = convert('<p><span style="color: red;">[red text]</span></p>')
    assert out == '<font style="color: red;">[red text]</font>'
    assert "\\[" not in out


def test_escape_suppressed_in_code_macro_body():
    # Code macro body comes from ac:plain-text-body (CDATA), no escape applied
    xml = '<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">python</ac:parameter><ac:plain-text-body><![CDATA[a = [1, 2]]]></ac:plain-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "a = [1, 2]" in out
    assert "\\[" not in out


def test_escape_closer_no_escape_wins_over_outer_paragraph():
    # <p> says escape, but <code> closer says no — code wins.
    out = convert("<p>foo <code>[x]</code> bar</p>")
    assert out == "foo <code>[x]</code> bar"


def test_escape_brackets_only_when_anchor_anywhere_in_chain():
    # <strong> inside <a>: the <a> ancestor demotes the inner text to brackets-only mode,
    # so [ ] are escaped but ** (strong) is preserved as inline formatting.
    out = convert('<p><a href="u"><strong>[link]</strong></a></p>')
    assert "[**\\[link\\]**](u)" in out


def test_escape_intraword_underscore_still_escapes():
    # Per docs: simplicity over precision — escape every _, even intraword.
    assert convert("<p>foo_bar_baz</p>") == "foo\\_bar\\_baz"


def test_macro_latex_inline_joins_multiline_with_single_space():
    xml = (
        '<ac:structured-macro ac:name="latex-inline">'
        '<ac:plain-text-body><![CDATA[\\sum_{i=1}^p |\\beta_i| ≤ t\n'
        '\\;\\;\\;\\; \\text{ for some } t > 0]]></ac:plain-text-body>'
        '</ac:structured-macro>'
    )
    out = convert(xml).strip()
    assert out == "$\\sum_{i=1}^p |\\beta_i| ≤ t \\;\\;\\;\\; \\text{ for some } t > 0$"
    assert "\n" not in out


def test_macro_latex_inline_collapses_multiple_newlines_to_single_space():
    xml = (
        '<ac:structured-macro ac:name="latex-inline">'
        '<ac:plain-text-body><![CDATA[a\n\n\nb]]></ac:plain-text-body>'
        '</ac:structured-macro>'
    )
    out = convert(xml).strip()
    assert out == "$a b$"


def test_macro_latex_block_collapses_multiline_to_inline_math():
    xml = (
        '<ac:structured-macro ac:name="latex-block">'
        '<ac:plain-text-body><![CDATA[a\nb]]></ac:plain-text-body>'
        '</ac:structured-macro>'
    )
    out = convert(xml).strip()
    assert out == "$a b$"


def test_macro_latex_block_is_alias_of_latex_inline():
    # Same math wrapping after strip — block adds a trailing \n that strip() removes.
    body = '<ac:plain-text-body><![CDATA[\\frac{a}{b} + c]]></ac:plain-text-body>'
    inline_xml = f'<ac:structured-macro ac:name="latex-inline">{body}</ac:structured-macro>'
    block_xml = f'<ac:structured-macro ac:name="latex-block">{body}</ac:structured-macro>'
    assert convert(inline_xml).strip() == convert(block_xml).strip()


def test_macro_latex_inline_normalizes_nbsp_to_ascii_space():
    xml = (
        '<ac:structured-macro ac:name="latex-inline">'
        '<ac:plain-text-body><![CDATA[\\sum x]]></ac:plain-text-body>'
        '</ac:structured-macro>'
    )
    out = convert(xml)
    assert out == "$\\sum x$"
    assert " " not in out


def test_macro_latex_inline_normalizes_various_unicode_whitespace():
    # NBSP (U+00A0), em-space (U+2003), narrow no-break space (U+202F),
    # ideographic space (U+3000) — each → one ASCII space, one-to-one.
    body = 'a b c d　e'
    xml = (
        '<ac:structured-macro ac:name="latex-inline">'
        f'<ac:plain-text-body><![CDATA[{body}]]></ac:plain-text-body>'
        '</ac:structured-macro>'
    )
    out = convert(xml)
    assert out == "$a b c d e$"


def test_macro_latex_block_normalizes_unicode_space():
    xml = (
        '<ac:structured-macro ac:name="latex-block">'
        '<ac:plain-text-body><![CDATA[\\alpha \\beta]]></ac:plain-text-body>'
        '</ac:structured-macro>'
    )
    assert convert(xml).strip() == "$\\alpha \\beta$"


def test_macro_latex_block_separates_consecutive_blocks_with_newline():
    xml = (
        '<ac:structured-macro ac:name="latex-block">'
        '<ac:plain-text-body><![CDATA[x]]></ac:plain-text-body>'
        '</ac:structured-macro>'
        '<ac:structured-macro ac:name="latex-block">'
        '<ac:plain-text-body><![CDATA[y]]></ac:plain-text-body>'
        '</ac:structured-macro>'
    )
    assert convert(xml) == "$x$\n$y$"


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


def test_colored_span_preserves_trailing_whitespace_in_content():
    # Confluence syntax-highlighted code wraps tokens in <span style="color:...">
    # — trailing space inside a span MUST survive so tokens don't glue together.
    xml = '<code><span style="color: rgb(0,0,0);">refresh </span><span style="color: rgb(102,102,0);">-</span></code>'
    out = convert(xml)
    assert out == '<code><font style="color: rgb(0,0,0);">refresh </font><font style="color: rgb(102,102,0);">-</font></code>'


def test_colored_span_preserves_leading_whitespace_in_content():
    xml = '<code><span style="color: rgb(0,0,0);"> hello</span></code>'
    out = convert(xml)
    assert out == '<code><font style="color: rgb(0,0,0);"> hello</font></code>'


def test_colored_span_wrapping_sole_code_swaps_to_code_outer():
    # Reverse source nesting (span outer, code inner) normalizes to code-outer
    # so Obsidian's font-color plugin renders the colour inside <code>.
    xml = '<p><span style="color: rgb(122,134,154);"><code>CODE</code></span></p>'
    assert convert(xml) == '<code><font style="color: rgb(122,134,154);">CODE</font></code>'


def test_colored_span_with_mixed_content_around_code_does_not_swap():
    # Span has more than just one <code> child — keep span outer.
    xml = '<p><span style="color: red;">prefix <code>X</code> suffix</span></p>'
    out = convert(xml)
    assert out.startswith('<font style="color: red;">')
    assert "<code>X</code>" in out
    assert out.endswith("</font>")


def test_colored_span_with_multiple_code_children_does_not_swap():
    xml = '<p><span style="color: red;"><code>X</code><code>Y</code></span></p>'
    out = convert(xml)
    assert out == '<font style="color: red;"><code>X</code><code>Y</code></font>'


def test_external_link():
    out = convert('<p><a href="https://example.com">site</a></p>')
    assert "[site](https://example.com)" in out


def test_table_emits_prettified_raw_html():
    xml = "<table><tbody><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></tbody></table>"
    out = convert(xml)
    expected = (
        "<table>\n"
        "    <tbody>\n"
        "        <tr>\n"
        '            <th style="background-color: #F4F5F7;">A</th>\n'
        '            <th style="background-color: #F4F5F7;">B</th>\n'
        "        </tr>\n"
        "        <tr>\n"
        "            <td>1</td>\n"
        "            <td>2</td>\n"
        "        </tr>\n"
        "    </tbody>\n"
        "</table>"
    )
    assert out == expected


def test_table_strips_colgroup():
    xml = "<table><colgroup><col/><col/></colgroup><tbody><tr><td>x</td></tr></tbody></table>"
    out = convert(xml)
    assert "colgroup" not in out
    assert "<col" not in out


def test_table_strips_unknown_attributes_keeps_colspan_rowspan():
    xml = '<table class="confluenceTable" data-x="1"><tbody><tr><td colspan="2" rowspan="3" class="cell">x</td></tr></tbody></table>'
    out = convert(xml)
    assert 'class="confluenceTable"' not in out
    assert 'data-x' not in out
    assert 'class="cell"' not in out
    assert '<table>' in out
    assert 'colspan="2"' in out
    assert 'rowspan="3"' in out


def test_table_data_highlight_colour_becomes_style():
    xml = '<table><tbody><tr><td data-highlight-colour="grey">x</td></tr></tbody></table>'
    out = convert(xml)
    assert 'data-highlight-colour' not in out
    assert 'style="background-color: #F4F5F7;"' in out


def test_table_style_attribute_kept_verbatim():
    xml = '<table style="width: 100%;"><tbody><tr><td style="text-align: center;">x</td></tr></tbody></table>'
    out = convert(xml)
    assert 'style="width: 100%;"' in out
    assert 'style="text-align: center;"' in out


def test_table_cell_style_and_highlight_colour_merge():
    xml = '<table><tbody><tr><td style="text-align: center;" data-highlight-colour="grey">x</td></tr></tbody></table>'
    out = convert(xml)
    assert 'data-highlight-colour' not in out
    assert 'style="text-align: center; background-color: #F4F5F7;"' in out


def test_table_cell_style_without_trailing_semicolon_merges_cleanly():
    xml = '<table><tbody><tr><td style="text-align: center" data-highlight-colour="grey">x</td></tr></tbody></table>'
    out = convert(xml)
    assert 'style="text-align: center; background-color: #F4F5F7;"' in out


def test_table_th_with_no_styling_gets_auto_background():
    xml = '<table><tbody><tr><th>head</th></tr></tbody></table>'
    out = convert(xml)
    assert '<th style="background-color: #F4F5F7;">head</th>' in out


def test_table_th_with_explicit_data_highlight_skips_auto_background():
    xml = '<table><tbody><tr><th data-highlight-colour="red">head</th></tr></tbody></table>'
    out = convert(xml)
    assert '<th style="background-color: red;">head</th>' in out
    assert '#F4F5F7' not in out


def test_table_th_with_explicit_background_in_style_skips_auto():
    xml = '<table><tbody><tr><th style="background-color: yellow;">head</th></tr></tbody></table>'
    out = convert(xml)
    assert '<th style="background-color: yellow;">head</th>' in out
    assert '#F4F5F7' not in out


def test_table_th_with_non_background_style_appends_auto():
    xml = '<table><tbody><tr><th style="text-align: center;">head</th></tr></tbody></table>'
    out = convert(xml)
    assert '<th style="text-align: center; background-color: #F4F5F7;">head</th>' in out


def test_table_data_highlight_colour_other_than_grey_passes_through():
    xml = '<table><tbody><tr><td data-highlight-colour="red">x</td></tr></tbody></table>'
    out = convert(xml)
    assert 'style="background-color: red;"' in out


def test_table_cell_with_ac_link_no_body_uses_page_title():
    xml = '<table><tbody><tr><td><p><ac:link><ri:page ri:space-key="NOT" ri:content-title="Samsung" /></ac:link></p></td></tr></tbody></table>'
    out = convert(xml)
    assert "<p>Samsung</p>" in out
    assert "ac:link" not in out
    assert "ri:page" not in out


def test_table_cell_with_ac_link_with_body_uses_alt_text():
    xml = '<table><tbody><tr><td><p><ac:link><ri:page ri:space-key="NOT" ri:content-title="Samsung" /><ac:plain-text-link-body><![CDATA[ALT_TEXT]]></ac:plain-text-link-body></ac:link></p></td></tr></tbody></table>'
    out = convert(xml)
    assert "<p>ALT_TEXT</p>" in out
    assert "Samsung" not in out


def test_table_cell_with_ac_macro_emitted_as_escaped_source_xml():
    xml = '<table><tbody><tr><td><ac:structured-macro ac:name="info"><ac:rich-text-body><p>note</p></ac:rich-text-body></ac:structured-macro></td></tr></tbody></table>'
    out = convert(xml)
    assert "&lt;ac:structured-macro" in out
    assert 'ac:name="info"' in out
    assert "&lt;/ac:structured-macro&gt;" in out
    assert "<ac:structured-macro" not in out


def test_table_cell_latex_inline_renders_as_math_display_span():
    xml = (
        '<table><tbody><tr><td>'
        '<ac:structured-macro ac:name="latex-inline">'
        '<ac:plain-text-body><![CDATA[x^2 + y^2]]></ac:plain-text-body>'
        '</ac:structured-macro>'
        '</td></tr></tbody></table>'
    )
    out = convert(xml)
    assert '<span class="math display">x^2 + y^2</span>' in out
    assert "&lt;ac:structured-macro" not in out


def test_table_cell_latex_block_renders_as_math_display_span():
    xml = (
        '<table><tbody><tr><td>'
        '<ac:structured-macro ac:name="latex-block">'
        '<ac:plain-text-body><![CDATA[\\int x dx]]></ac:plain-text-body>'
        '</ac:structured-macro>'
        '</td></tr></tbody></table>'
    )
    out = convert(xml)
    assert '<span class="math display">\\int x dx</span>' in out


def test_table_cell_latex_alias_renders_as_math_display_span():
    xml = (
        '<table><tbody><tr><td>'
        '<ac:structured-macro ac:name="latex">'
        '<ac:plain-text-body><![CDATA[\\alpha]]></ac:plain-text-body>'
        '</ac:structured-macro>'
        '</td></tr></tbody></table>'
    )
    out = convert(xml)
    assert '<span class="math display">\\alpha</span>' in out


def test_table_cell_latex_normalizes_multiline_and_unicode_whitespace():
    # Multi-line CDATA + NBSP in body — both normalized to single ASCII space
    nbsp = chr(0xa0)
    body = f'\\alpha\n\\beta{nbsp}\\gamma'
    xml = (
        '<table><tbody><tr><td>'
        '<ac:structured-macro ac:name="latex-inline">'
        f'<ac:plain-text-body><![CDATA[{body}]]></ac:plain-text-body>'
        '</ac:structured-macro>'
        '</td></tr></tbody></table>'
    )
    out = convert(xml)
    assert '<span class="math display">\\alpha \\beta \\gamma</span>' in out
    assert nbsp not in out


def test_document_level_latex_block_logs_warning():
    xml = '<ac:structured-macro ac:name="latex-block"><ac:plain-text-body><![CDATA[x]]></ac:plain-text-body></ac:structured-macro>'
    c = Converter("MyPage")
    c.convert(xml)
    assert any("latex-block" in w and "MyPage" in w for w in c.warnings)


def test_document_level_latex_inline_does_not_log_latex_warning():
    xml = '<ac:structured-macro ac:name="latex-inline"><ac:plain-text-body><![CDATA[x]]></ac:plain-text-body></ac:structured-macro>'
    c = Converter("MyPage")
    c.convert(xml)
    assert not any("latex-block" in w or "latex-inline" in w for w in c.warnings)


def test_cell_latex_block_logs_warning():
    xml = (
        '<table><tbody><tr><td>'
        '<ac:structured-macro ac:name="latex-block">'
        '<ac:plain-text-body><![CDATA[x]]></ac:plain-text-body>'
        '</ac:structured-macro>'
        '</td></tr></tbody></table>'
    )
    c = Converter("MyPage")
    c.convert(xml)
    assert any("latex-block" in w and "MyPage" in w for w in c.warnings)


def test_cell_untransformed_structured_macro_logs_with_name():
    xml = (
        '<table><tbody><tr><td>'
        '<ac:structured-macro ac:name="info"><ac:rich-text-body><p>note</p></ac:rich-text-body></ac:structured-macro>'
        '</td></tr></tbody></table>'
    )
    c = Converter("MyPage")
    c.convert(xml)
    assert any(
        "info" in w and "table cell" in w.lower() and "MyPage" in w
        for w in c.warnings
    )


def test_cell_untransformed_anchor_macro_logs_warning():
    xml = (
        '<table><tbody><tr><td>'
        '<ac:structured-macro ac:name="anchor"><ac:parameter ac:name="">foo</ac:parameter></ac:structured-macro>'
        '</td></tr></tbody></table>'
    )
    c = Converter("MyPage")
    c.convert(xml)
    assert any(
        "anchor" in w and "table cell" in w.lower() and "MyPage" in w
        for w in c.warnings
    )


def test_cell_other_ac_element_logs_warning():
    # ac:emoticon has no cell-specific handler — falls through to source-XML escape
    xml = (
        '<table><tbody><tr><td>'
        '<ac:emoticon ac:name="smile" />'
        '</td></tr></tbody></table>'
    )
    c = Converter("MyPage")
    c.convert(xml)
    assert any(
        "ac:emoticon" in w and "table cell" in w.lower() and "MyPage" in w
        for w in c.warnings
    )


def test_table_cell_latex_html_escapes_body():
    # < and > inside LaTeX body must be HTML-escaped so the surrounding span stays valid HTML
    xml = (
        '<table><tbody><tr><td>'
        '<ac:structured-macro ac:name="latex-inline">'
        '<ac:plain-text-body><![CDATA[a < b > c & d]]></ac:plain-text-body>'
        '</ac:structured-macro>'
        '</td></tr></tbody></table>'
    )
    out = convert(xml)
    assert '<span class="math display">a &lt; b &gt; c &amp; d</span>' in out


def test_table_cell_expand_with_title_renders_inline_details():
    xml = (
        '<table><tbody><tr><td>'
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">ALT TEXT</ac:parameter>'
        '<ac:rich-text-body><p>CONTENT</p></ac:rich-text-body></ac:structured-macro>'
        '</td></tr></tbody></table>'
    )
    out = convert(xml)
    assert "<details><summary>ALT TEXT</summary><p>CONTENT</p></details>" in out
    assert "&lt;ac:structured-macro" not in out


def test_table_cell_ui_expand_renders_inline_details():
    xml = (
        '<table><tbody><tr><td>'
        '<ac:structured-macro ac:name="ui-expand"><ac:parameter ac:name="title">T</ac:parameter>'
        '<ac:rich-text-body><p>body</p></ac:rich-text-body></ac:structured-macro>'
        '</td></tr></tbody></table>'
    )
    out = convert(xml)
    assert "<details><summary>T</summary><p>body</p></details>" in out


def test_table_cell_expand_without_title_uses_default_summary():
    xml = (
        '<table><tbody><tr><td>'
        '<ac:structured-macro ac:name="expand">'
        '<ac:rich-text-body><p>x</p></ac:rich-text-body></ac:structured-macro>'
        '</td></tr></tbody></table>'
    )
    out = convert(xml)
    assert "<details><summary>Click here to expand...</summary><p>x</p></details>" in out


def test_table_cell_expand_body_keeps_cell_rules_for_nested_ac_macros():
    xml = (
        '<table><tbody><tr><td>'
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">T</ac:parameter>'
        '<ac:rich-text-body>'
        '<ac:structured-macro ac:name="info"><ac:rich-text-body><p>n</p></ac:rich-text-body></ac:structured-macro>'
        '</ac:rich-text-body></ac:structured-macro>'
        '</td></tr></tbody></table>'
    )
    out = convert(xml)
    assert "<details><summary>T</summary>" in out
    assert "&lt;ac:structured-macro" in out
    assert 'ac:name="info"' in out


def test_table_cell_with_ac_image_transforms_to_img_tag():
    xml = (
        '<table><tbody><tr><th rowspan="3">'
        '<div class="content-wrapper">'
        '<p><ac:image ac:style="max-height: 250.0px;" ac:thumbnail="true" ac:height="250">'
        '<ri:attachment ri:filename="Screenshot 2026-04-30 at 2.00.51 PM.png" />'
        '</ac:image></p></div></th></tr></tbody></table>'
    )
    out = convert(xml)
    assert '<th rowspan="3" style="background-color: #F4F5F7;">' in out
    assert "content-wrapper" not in out
    assert "<div" not in out
    assert "<p>" not in out
    assert '<img src="Screenshot 2026-04-30 at 2.00.51 PM.png" height="250" />' in out
    assert "ac:image" not in out
    assert "ac:thumbnail" not in out
    assert "ac:style" not in out


def test_table_cell_ac_image_normalizes_unicode_whitespace_in_filename():
    xml = '<table><tbody><tr><td><ac:image><ri:attachment ri:filename="a\u00a0b\u202fc.png" /></ac:image></td></tr></tbody></table>'
    out = convert(xml)
    assert '<img src="a b c.png" />' in out
    assert '\u00a0' not in out
    assert '\u202f' not in out


def test_table_cell_ac_image_minimal():
    xml = '<table><tbody><tr><td><ac:image><ri:attachment ri:filename="x.png" /></ac:image></td></tr></tbody></table>'
    out = convert(xml)
    assert '<img src="x.png" />' in out


def test_table_cell_ac_image_with_width():
    xml = '<table><tbody><tr><td><ac:image ac:width="450"><ri:attachment ri:filename="image.png" /></ac:image></td></tr></tbody></table>'
    out = convert(xml)
    assert '<img src="image.png" width="450" />' in out


def test_table_cell_ac_image_with_width_and_height():
    xml = '<table><tbody><tr><td><ac:image ac:width="450" ac:height="200"><ri:attachment ri:filename="image.png" /></ac:image></td></tr></tbody></table>'
    out = convert(xml)
    assert '<img src="image.png" width="450" height="200" />' in out


def test_table_cell_ac_image_without_filename_falls_back_to_escape_and_logs():
    xml = '<table><tbody><tr><td><ac:image><ri:url ri:value="https://x.com/y.png" /></ac:image></td></tr></tbody></table>'
    from src.converter import Converter
    c = Converter("MyPage")
    out = c.convert(xml).strip()
    assert "&lt;ac:image" in out
    assert "<img" not in out
    assert any("ac:image" in w and "MyPage" in w for w in c.warnings)


def test_table_cell_strips_div_content_wrapper():
    xml = '<table><tbody><tr><td><div class="content-wrapper"><span>x</span></div></td></tr></tbody></table>'
    out = convert(xml)
    assert "content-wrapper" not in out
    assert "<div" not in out
    assert "<td><span>x</span></td>" in out


def test_table_cell_strips_p_around_ac_macro():
    xml = '<table><tbody><tr><td><p><ac:structured-macro ac:name="info"><ac:rich-text-body><p>note</p></ac:rich-text-body></ac:structured-macro></p></td></tr></tbody></table>'
    out = convert(xml)
    assert "&lt;ac:structured-macro" in out
    out_first_p_stripped = out.split('<td>', 1)[1].split('</td>', 1)[0]
    assert not out_first_p_stripped.startswith('<p>')


def test_table_nested_table_recursively_prettified():
    xml = (
        '<table><tbody><tr><td>'
        '<table><tbody><tr><td>x</td></tr></tbody></table>'
        '</td></tr></tbody></table>'
    )
    out = convert(xml)
    expected = (
        "<table>\n"
        "    <tbody>\n"
        "        <tr>\n"
        "            <td><table>\n"
        "                    <tbody>\n"
        "                        <tr>\n"
        "                            <td>x</td>\n"
        "                        </tr>\n"
        "                    </tbody>\n"
        "                </table></td>\n"
        "        </tr>\n"
        "    </tbody>\n"
        "</table>"
    )
    assert out == expected


def test_table_nested_table_applies_full_clean_rules():
    xml = (
        '<table><tbody><tr><td>'
        '<table class="x"><colgroup><col/></colgroup><tbody><tr>'
        '<td data-highlight-colour="grey" class="y">inner</td>'
        '</tr></tbody></table>'
        '</td></tr></tbody></table>'
    )
    out = convert(xml)
    assert 'class="x"' not in out
    assert 'class="y"' not in out
    assert 'colgroup' not in out
    assert 'data-highlight-colour' not in out
    assert 'style="background-color: #F4F5F7;"' in out


def test_table_nested_table_with_surrounding_text_stays_inline():
    xml = (
        '<table><tbody><tr><td>before'
        '<table><tbody><tr><td>x</td></tr></tbody></table>'
        'after</td></tr></tbody></table>'
    )
    out = convert(xml)
    assert "<td>before<table>" in out
    assert "</table>after</td>" in out


def test_table_cell_drops_p_with_only_br():
    xml = (
        '<table><tbody><tr><td>'
        '<p>real</p>'
        '<p><br/></p>'
        '<p>more</p>'
        '</td></tr></tbody></table>'
    )
    out = convert(xml)
    assert "<td><p>real</p><p>more</p></td>" in out
    assert "<br" not in out


def test_table_cell_drops_auto_cursor_target_paragraph_regardless_of_attrs():
    xml = (
        '<table><tbody><tr><td>'
        '<p>a</p>'
        '<p class="auto-cursor-target"><br /></p>'
        '<p>b</p>'
        '</td></tr></tbody></table>'
    )
    out = convert(xml)
    assert "<td><p>a</p><p>b</p></td>" in out
    assert "auto-cursor-target" not in out
    assert "<br" not in out


def test_table_cell_drops_p_with_multiple_brs():
    xml = (
        '<table><tbody><tr><td>'
        '<p>a</p><p><br/><br/></p><p>b</p>'
        '</td></tr></tbody></table>'
    )
    out = convert(xml)
    assert "<td><p>a</p><p>b</p></td>" in out


def test_table_cell_keeps_p_with_text_and_br():
    xml = (
        '<table><tbody><tr><td>'
        '<p>hello<br/></p>'
        '</td></tr></tbody></table>'
    )
    out = convert(xml)
    assert "<p>hello<br/></p>" in out


def test_table_cell_keeps_p_with_mixed_text_and_ac_macro():
    xml = '<table><tbody><tr><td><p>before <ac:structured-macro ac:name="info"><ac:rich-text-body><p>n</p></ac:rich-text-body></ac:structured-macro> after</p></td></tr></tbody></table>'
    out = convert(xml)
    assert "<p>before " in out
    assert " after</p>" in out
    assert "&lt;ac:structured-macro" in out


def test_table_cell_with_multiple_paragraphs_stays_inline():
    xml = '<table><tbody><tr><td><p>a</p><p>b</p></td></tr></tbody></table>'
    out = convert(xml)
    assert "<td><p>a</p><p>b</p></td>" in out


def test_table_cell_preserves_raw_text_newlines():
    xml = '<table><tbody><tr><td>line1\nline2</td></tr></tbody></table>'
    out = convert(xml)
    assert "<td>line1\nline2</td>" in out


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
    assert out == "$\\int x dx$"


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


def test_inline_image_normalizes_unicode_whitespace_in_filename():
    # NBSP (U+00A0) — common in Confluence screenshot filenames
    nbsp = chr(0xa0)
    xml = f'<ac:image><ri:attachment ri:filename="Screenshot{nbsp}at{nbsp}12.png" /></ac:image>'
    out = convert(xml, page_name="MyPage")
    assert out == "![[MyPage/Screenshot at 12.png]]"
    assert nbsp not in out

def test_inline_image_with_width_only_emits_obsidian_size_suffix():
    xml = '<ac:image ac:width="400"><ri:attachment ri:filename="image.png" /></ac:image>'
    out = convert(xml, page_name="MyPage")
    assert out == "![[MyPage/image.png|400]]"


def test_inline_image_with_height_only_emits_no_size_suffix():
    # Obsidian's |0xH "height-only" suffix doesn't render reliably; drop the
    # hint entirely when ac:width is absent and let Obsidian use natural size.
    xml = '<ac:image ac:style="max-height: 250.0px;" ac:height="250"><ri:attachment ri:filename="image.png" /></ac:image>'
    out = convert(xml, page_name="MyPage")
    assert out == "![[MyPage/image.png]]"


def test_inline_image_with_width_and_height_emits_w_x_h_suffix():
    xml = '<ac:image ac:width="400" ac:height="250"><ri:attachment ri:filename="image.png" /></ac:image>'
    out = convert(xml, page_name="MyPage")
    assert out == "![[MyPage/image.png|400x250]]"


def test_ac_link_to_attachment_normalizes_unicode_whitespace_in_filename():
    nbsp = chr(0xa0)
    xml = f'<ac:link><ri:attachment ri:filename="My{nbsp}File.pdf" /></ac:link>'
    out = convert(xml, page_name="MyPage")
    assert out == "[[MyPage/My File.pdf]]"
    assert nbsp not in out

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
    assert out == "[[Design： v2|Design: v2]]"


def test_link_target_uses_title_map_for_collision():
    xml = '<ac:link><ri:page ri:content-title="Design: v2" /></ac:link>'
    c = Converter("p", title_map={"Design: v2": "Design  v2 (123)"})
    out = c.convert(xml).strip()
    assert out == "[[Design  v2 (123)|Design: v2]]"


def test_excerpt_include_uses_resolved_target():
    xml = '<ac:structured-macro ac:name="excerpt-include"><ac:parameter ac:name=""><ac:link><ri:page ri:content-title="Design: v2" /></ac:link></ac:parameter></ac:structured-macro>'
    out = convert(xml)
    assert out == "![[Design： v2#^excerpt]]"


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


def test_macro_expand_with_title_emits_callout():
    xml = '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">TITLE HERE</ac:parameter><ac:rich-text-body><p>content here</p></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "> [!expand]- TITLE HERE\n> content here" in out
    assert "<details>" not in out
    assert "~~~expand" not in out


def test_macro_expand_without_title_uses_default_in_callout_header():
    xml = '<ac:structured-macro ac:name="expand"><ac:rich-text-body><p>content here</p></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "> [!expand]- Click here to expand...\n> content here" in out


def test_macro_ui_expand_with_title_emits_expand_ui_callout():
    xml = '<ac:structured-macro ac:name="ui-expand"><ac:parameter ac:name="title">UI TITLE</ac:parameter><ac:rich-text-body><p>body</p></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "> [!expand-ui]- UI TITLE\n> body" in out
    assert "<details>" not in out
    assert "~~~expand-ui" not in out


def test_macro_ui_expand_without_title_uses_default_in_callout_header():
    xml = '<ac:structured-macro ac:name="ui-expand"><ac:rich-text-body><p>body</p></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "> [!expand-ui]- Click here to expand...\n> body" in out


def test_macro_expand_callout_title_not_html_escaped():
    xml = '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">a &lt; b</ac:parameter><ac:rich-text-body><p>x</p></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "> [!expand]- a < b\n> x" in out
    assert "&lt;" not in out


def test_macro_expand_empty_body_still_emits_header():
    xml = '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">T</ac:parameter><ac:rich-text-body></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml).strip()
    assert out == "> [!expand]- T"


def test_macro_ui_expand_empty_body_still_emits_header():
    xml = '<ac:structured-macro ac:name="ui-expand"><ac:parameter ac:name="title">T</ac:parameter><ac:rich-text-body></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml).strip()
    assert out == "> [!expand-ui]- T"


def test_macro_expand_body_renders_full_markdown_inside_callout():
    xml = (
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">T</ac:parameter>'
        '<ac:rich-text-body>'
        '<ul><li>one</li><li>two</li></ul>'
        '<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">python</ac:parameter>'
        '<ac:plain-text-body><![CDATA[print(1)]]></ac:plain-text-body></ac:structured-macro>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml)
    assert "> [!expand]- T" in out
    assert "> - one" in out
    assert "> - two" in out
    assert "> ```python" in out
    assert "> print(1)" in out
    assert "<details>" not in out
    assert "~~~expand" not in out


def test_macro_expand_nested_inside_expand_quotes_deeper():
    xml = (
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">OUTER</ac:parameter>'
        '<ac:rich-text-body>'
        '<p>outer body</p>'
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">INNER</ac:parameter>'
        '<ac:rich-text-body><p>inner body</p></ac:rich-text-body></ac:structured-macro>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml)
    expected = (
        "> [!expand]- OUTER\n"
        "> outer body\n"
        ">\n"
        "> > [!expand]- INNER\n"
        "> > inner body"
    )
    assert expected in out


def test_macro_ui_expand_nested_inside_ui_expand_quotes_deeper():
    xml = (
        '<ac:structured-macro ac:name="ui-expand"><ac:parameter ac:name="title">OUTER</ac:parameter>'
        '<ac:rich-text-body>'
        '<p>outer body</p>'
        '<ac:structured-macro ac:name="ui-expand"><ac:parameter ac:name="title">INNER</ac:parameter>'
        '<ac:rich-text-body><p>inner body</p></ac:rich-text-body></ac:structured-macro>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml)
    expected = (
        "> [!expand-ui]- OUTER\n"
        "> outer body\n"
        ">\n"
        "> > [!expand-ui]- INNER\n"
        "> > inner body"
    )
    assert expected in out


def test_macro_expand_nested_as_only_child_no_leading_blank_quoted_line():
    xml = (
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">OUTER</ac:parameter>'
        '<ac:rich-text-body>'
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">INNER</ac:parameter>'
        '<ac:rich-text-body><p>inner body</p></ac:rich-text-body></ac:structured-macro>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml)
    expected = (
        "> [!expand]- OUTER\n"
        "> > [!expand]- INNER\n"
        "> > inner body"
    )
    assert expected in out


def test_macro_expand_triple_nested_quotes_three_deep():
    xml = (
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">L1</ac:parameter>'
        '<ac:rich-text-body>'
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">L2</ac:parameter>'
        '<ac:rich-text-body>'
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">L3</ac:parameter>'
        '<ac:rich-text-body><p>deep</p></ac:rich-text-body></ac:structured-macro>'
        '</ac:rich-text-body></ac:structured-macro>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml)
    expected = (
        "> [!expand]- L1\n"
        "> > [!expand]- L2\n"
        "> > > [!expand]- L3\n"
        "> > > deep"
    )
    assert expected in out


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


def test_macro_view_file_normalizes_unicode_whitespace_in_filename():
    nbsp = chr(0xa0)
    xml = f'<ac:structured-macro ac:name="view-file"><ac:parameter ac:name="name"><ri:attachment ri:filename="Quarterly{nbsp}Report.docx" /></ac:parameter></ac:structured-macro>'
    c = Converter("MyPage")
    out = c.convert(xml).strip()
    assert out == "![[MyPage/Quarterly Report.docx]]"
    assert nbsp not in out

def test_macro_viewpdf_emits_attachment_embed():
    xml = '<ac:structured-macro ac:name="viewpdf"><ac:parameter ac:name="name"><ri:attachment ri:filename="doc.pdf" /></ac:parameter></ac:structured-macro>'
    out = convert(xml, page_name="MyPage")
    assert out == "![[MyPage/doc.pdf]]"


def test_macro_multimedia_emits_attachment_embed():
    xml = '<ac:structured-macro ac:name="multimedia"><ac:parameter ac:name="name"><ri:attachment ri:filename="clip.mp4" /></ac:parameter></ac:structured-macro>'
    out = convert(xml, page_name="MyPage")
    assert out == "![[MyPage/clip.mp4]]"


def test_macro_ui_tabs_emits_fenced_tabs_block():
    xml = (
        '<ac:structured-macro ac:name="ui-tabs"><ac:rich-text-body>'
        '<p class="auto-cursor-target"><br /></p>'
        '<ac:structured-macro ac:name="ui-tab"><ac:parameter ac:name="title">Tab 1</ac:parameter>'
        '<ac:rich-text-body><p>Tab 1 content here</p></ac:rich-text-body></ac:structured-macro>'
        '<p class="auto-cursor-target"><br /></p>'
        '<ac:structured-macro ac:name="ui-tab"><ac:parameter ac:name="title">Tab 2</ac:parameter>'
        '<ac:rich-text-body><p>Tab 2 content here</p></ac:rich-text-body></ac:structured-macro>'
        '<p class="auto-cursor-target"><br /></p>'
        '<ac:structured-macro ac:name="ui-tab"><ac:parameter ac:name="title">Tab 3</ac:parameter>'
        '<ac:rich-text-body><p>Tab 3 content here</p></ac:rich-text-body></ac:structured-macro>'
        '<p class="auto-cursor-target"><br /></p>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml).strip()
    expected = (
        "~~~tabs\n"
        "---tab Tab 1\n"
        "Tab 1 content here\n"
        "---tab Tab 2\n"
        "Tab 2 content here\n"
        "---tab Tab 3\n"
        "Tab 3 content here\n"
        "~~~"
    )
    assert out == expected
    assert "<details>" not in out


def test_macro_ui_tabs_single_tab():
    xml = (
        '<ac:structured-macro ac:name="ui-tabs"><ac:rich-text-body>'
        '<ac:structured-macro ac:name="ui-tab"><ac:parameter ac:name="title">Only</ac:parameter>'
        '<ac:rich-text-body><p>body</p></ac:rich-text-body></ac:structured-macro>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml).strip()
    assert out == "~~~tabs\n---tab Only\nbody\n~~~"


def test_macro_ui_tabs_tab_body_renders_full_markdown():
    xml = (
        '<ac:structured-macro ac:name="ui-tabs"><ac:rich-text-body>'
        '<ac:structured-macro ac:name="ui-tab"><ac:parameter ac:name="title">T</ac:parameter>'
        '<ac:rich-text-body>'
        '<ul><li>one</li><li>two</li></ul>'
        '<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">python</ac:parameter>'
        '<ac:plain-text-body><![CDATA[print(1)]]></ac:plain-text-body></ac:structured-macro>'
        '</ac:rich-text-body></ac:structured-macro>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml)
    assert "---tab T" in out
    assert "- one" in out
    assert "- two" in out
    assert "```python" in out
    assert "print(1)" in out


def test_macro_ui_tabs_drops_non_tab_content_silently():
    xml = (
        '<ac:structured-macro ac:name="ui-tabs"><ac:rich-text-body>'
        '<p>stray paragraph that confluence never showed</p>'
        '<ac:structured-macro ac:name="ui-tab"><ac:parameter ac:name="title">T</ac:parameter>'
        '<ac:rich-text-body><p>real tab body</p></ac:rich-text-body></ac:structured-macro>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml)
    assert "stray paragraph" not in out
    assert "real tab body" in out


def test_macro_ui_tabs_with_no_tabs_drops_block():
    xml = (
        '<ac:structured-macro ac:name="ui-tabs"><ac:rich-text-body>'
        '<p class="auto-cursor-target"><br /></p>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml).strip()
    assert out == ""


def test_orphan_ui_tab_logged_as_unknown_macro():
    from src.converter import Converter
    c = Converter("p")
    c.convert(
        '<ac:structured-macro ac:name="ui-tab"><ac:parameter ac:name="title">T</ac:parameter>'
        '<ac:rich-text-body><p>body</p></ac:rich-text-body></ac:structured-macro>'
    )
    assert "ui-tab" in c.unknown_macros


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


def test_spacing_blank_line_after_top_level_table_before_heading():
    xml = "<table><tbody><tr><td>x</td></tr></tbody></table><h1>Next</h1>"
    out = convert(xml)
    assert "</table>\n\n# Next" in out


def test_spacing_blank_line_after_top_level_table_before_list():
    xml = "<table><tbody><tr><td>x</td></tr></tbody></table><ul><li>item</li></ul>"
    out = convert(xml)
    assert "</table>\n\n- item" in out


def test_spacing_blank_line_between_two_top_level_tables():
    xml = (
        "<table><tbody><tr><td>1</td></tr></tbody></table>"
        "<table><tbody><tr><td>2</td></tr></tbody></table>"
    )
    out = convert(xml)
    assert "</table>\n\n<table>" in out


def test_spacing_top_level_table_before_paragraph_one_blank_line_only():
    xml = "<table><tbody><tr><td>x</td></tr></tbody></table><p>after</p>"
    out = convert(xml)
    assert "</table>\n\nafter" in out
    assert "</table>\n\n\nafter" not in out


def test_spacing_table_inside_info_callout_followed_by_heading_has_blank_quoted_line():
    xml = (
        '<ac:structured-macro ac:name="info"><ac:rich-text-body>'
        '<table><tbody><tr><td>x</td></tr></tbody></table>'
        '<h1>after</h1>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml)
    assert "> </table>\n>\n> # after" in out


def test_spacing_table_inside_warning_callout_followed_by_heading_has_blank_quoted_line():
    xml = (
        '<ac:structured-macro ac:name="warning"><ac:rich-text-body>'
        '<table><tbody><tr><td>x</td></tr></tbody></table>'
        '<h1>after</h1>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml)
    assert "> </table>\n>\n> # after" in out


def test_spacing_table_inside_info_callout_followed_by_paragraph_no_overquoting():
    xml = (
        '<ac:structured-macro ac:name="info"><ac:rich-text-body>'
        '<table><tbody><tr><td>x</td></tr></tbody></table>'
        '<p>after</p>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml)
    assert "> </table>\n>\n> after" in out
    assert "> </table>\n>\n>\n>" not in out


def test_spacing_table_inside_ui_tab_followed_by_heading_has_blank_line():
    xml = (
        '<ac:structured-macro ac:name="ui-tabs"><ac:rich-text-body>'
        '<ac:structured-macro ac:name="ui-tab"><ac:parameter ac:name="title">T</ac:parameter>'
        '<ac:rich-text-body>'
        '<table><tbody><tr><td>x</td></tr></tbody></table>'
        '<h1>after</h1>'
        '</ac:rich-text-body></ac:structured-macro>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml)
    assert "</table>\n\n# after" in out


def test_spacing_table_inside_expand_body_followed_by_heading_has_blank_quoted_line():
    xml = (
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">T</ac:parameter>'
        '<ac:rich-text-body>'
        '<table><tbody><tr><td>x</td></tr></tbody></table>'
        '<h1>after</h1>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml)
    assert "> </table>\n>\n> # after" in out


def test_spacing_table_inside_ui_expand_body_followed_by_heading_has_blank_quoted_line():
    xml = (
        '<ac:structured-macro ac:name="ui-expand"><ac:parameter ac:name="title">T</ac:parameter>'
        '<ac:rich-text-body>'
        '<table><tbody><tr><td>x</td></tr></tbody></table>'
        '<h1>after</h1>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml)
    assert "> </table>\n>\n> # after" in out


def test_spacing_nested_table_in_cell_stays_flush_no_trailing_blank_line():
    xml = (
        '<table><tbody><tr><td>before'
        '<table><tbody><tr><td>x</td></tr></tbody></table>'
        'after</td></tr></tbody></table>'
    )
    out = convert(xml)
    assert "</table>after</td>" in out


def test_attachments_referenced_tracked():
    c = Converter("MyPage")
    c.convert('<ac:image><ri:attachment ri:filename="a.png" /></ac:image>')
    c.convert('<ac:image><ri:attachment ri:filename="b.png" /></ac:image>')
    assert "a.png" in c.attachments_referenced
    assert "b.png" in c.attachments_referenced
