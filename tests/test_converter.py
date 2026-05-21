from src.converter import Converter, _inject_list_placeholders


def convert(xml: str, page_name: str = "TestPage") -> str:
    return Converter(page_name).convert(xml).strip()


def test_list_followed_by_callout_has_no_blank_line():
    # Trailing blank after list is collapsed when next block starts with >.
    xml = '<ul><li>X</li></ul><ac:structured-macro ac:name="info"><ac:rich-text-body><p>note</p></ac:rich-text-body></ac:structured-macro>'
    out = convert(xml)
    assert out == "- X\n> [!info]\n> note"


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
    assert out == "- X\n<strong>Y</strong>"


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
    # The list→quote collapse removes the blank line BEFORE the separator's `> `;
    # the trailing blank+next-list pair is preserved.
    assert convert(xml) == "1. HELLO\n2. WORLD\n> \n\n1. HELLO\n2. WORLD"


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
    assert convert("<p><strong>bold</strong> and <em>italic</em></p>") == "<strong>bold</strong> and <em>italic</em>"


def test_strong_whitespace_only_unwraps():
    assert convert("<p>hello world.<strong> </strong>snss</p>") == "hello world. snss"


def test_em_whitespace_only_unwraps():
    assert convert("<p>hello world.<em> </em>snss</p>") == "hello world. snss"


def test_nested_strong_em_whitespace_only_unwraps_recursively():
    assert convert("<p>hello world.<strong><em> </em></strong>snss</p>") == "hello world. snss"


def test_strong_with_content_preserves_inner_whitespace():
    out = convert("<p>hello<strong> world. </strong>snss</p>")
    assert out == "hello<strong> world. </strong>snss"


def test_em_with_content_preserves_inner_whitespace():
    out = convert("<p>hello<em> world. </em>snss</p>")
    assert out == "hello<em> world. </em>snss"


def test_nested_strong_em_with_content_keeps_both_wrappers():
    out = convert("<p>hello<strong><em> world. </em></strong>snss</p>")
    assert out == "hello<strong><em> world. </em></strong>snss"


def test_truly_empty_strong_unwraps_to_nothing():
    assert convert("<p>a<strong></strong>b</p>") == "ab"


def test_b_treated_as_strong():
    assert convert("<p><b>bold</b></p>") == "<strong>bold</strong>"


def test_i_treated_as_em():
    assert convert("<p><i>italic</i></p>") == "<em>italic</em>"


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


def test_list_item_with_only_expand_drops_marker():
    # Empty <li> with only block content → marker line dropped entirely;
    # the hoisted block is the sole output for that <li>.
    xml = (
        '<ul><li>'
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">T</ac:parameter>'
        '<ac:rich-text-body><p>body</p></ac:rich-text-body></ac:structured-macro>'
        '</li></ul>'
    )
    out = convert(xml).strip()
    expected = (
        "> [!expand]- T\n"
        "> body"
    )
    assert out == expected


def test_ordered_list_empty_item_with_block_content_drops_marker():
    xml = (
        '<ol><li>'
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">T</ac:parameter>'
        '<ac:rich-text-body><p>body</p></ac:rich-text-body></ac:structured-macro>'
        '</li></ol>'
    )
    out = convert(xml).strip()
    expected = (
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
    assert out == "before <strong>\\[bold\\]</strong> after"


def test_escape_applies_inside_em():
    out = convert("<p><em>[italic]</em></p>")
    assert out == "<em>\\[italic\\]</em>"


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


def test_escape_full_set_applied_inside_code():
    # The narrowed-to-`<>#` escape inside <code> was unified with the plain-text
    # set after observing that Obsidian's HTML extension processes Markdown inside
    # <code> (e.g. `*foo*` renders as italics). All 11 metacharacters are escaped.
    assert convert("<p>use <code>[brackets]</code> here</p>") == "use <code>\\[brackets\\]</code> here"


def test_escape_full_set_applied_inside_pre():
    out = convert("<pre>[raw] code</pre>")
    assert "\\[raw\\] code" in out


def test_pre_wrapper_carries_whitespace_pre_wrap_style():
    out = convert("<pre>def f():\n    return 1\n\tprint(2)</pre>")
    assert out.startswith('<span style="white-space: pre-wrap">')
    assert '<code>    return 1</code>' in out
    assert '<code>\tprint(2)</code>' in out


def test_pre_hoisted_from_li_flushes_against_following_p_inside_li():
    # <li> containing <p>BEFORE</p><pre>...</pre><p>AFTER</p>:
    # both <pre> and trailing <p> are hoisted; the blank line between the hoisted
    # <span>-wrapper and the following plain text AFTER is collapsed to a single
    # newline (exception (5) of the Block-spacing rule).
    xml = '<ul><li><p>BEFORE</p><pre>    HELLO\n</pre><p>AFTER</p></li></ul>'
    out = convert(xml)
    assert out == (
        '- BEFORE\n'
        '<span style="white-space: pre-wrap"><code>    HELLO</code></span>\n'
        'AFTER'
    )


def test_pre_hoisted_from_li_preserves_blank_line_before_p_outside_li():
    # When <p>AFTER</p> sits at document level after </ul>, the boundary between
    # the list and the next paragraph keeps its blank line — the in-<li> hoist
    # collapse only fires for blocks hoisted from the same list item, not for
    # adjacent blocks at the document level.
    xml = '<ul><li><p>BEFORE</p><pre>    HELLO\n</pre></li></ul><p>AFTER</p>'
    out = convert(xml)
    assert out == (
        '- BEFORE\n'
        '<span style="white-space: pre-wrap"><code>    HELLO</code></span>\n\n'
        'AFTER'
    )


def test_pre_hoisted_from_li_keeps_blank_line_before_heading():
    # The block-marker guard preserves the blank line when the next content
    # starts with a heading marker (#) — heading needs the blank to parse.
    xml = '<ul><li><p>BEFORE</p><pre>    HELLO\n</pre></li></ul><h1>AFTER</h1>'
    out = convert(xml)
    assert '</span>\n\n# AFTER' in out


def test_pre_hoisted_from_li_keeps_blank_line_before_list():
    # Block-marker guard: list bullet `- ` is a Markdown block marker.
    xml = '<ul><li><p>BEFORE</p><pre>    HELLO\n</pre></li></ul><ul><li>NEXT</li></ul>'
    out = convert(xml)
    assert '</span>\n\n- NEXT' in out


def test_br_inside_li_first_p_emits_continuation_indent():
    # <br/> inside an <li>'s inline body becomes a newline followed by a
    # 2-space continuation indent (matching the `- ` marker's text-start
    # column), so the multi-line body stays inside the same list item.
    xml = '<ul><li><p>BEFORE<br/>HELLO</p></li></ul><p>AFTER</p>'
    out = convert(xml)
    assert out == (
        '- BEFORE\n'
        '  HELLO\n\n'
        'AFTER'
    )


def test_br_inside_li_multiple_br_with_uncolored_span():
    # Multiple <br/>s inside the inline body; the uncolored <span style="letter-spacing:...">
    # (no `color:` so it unwraps) contributes "AFTER" inline. All three lines stay
    # in the same list item.
    xml = (
        '<ul><li><p>BEFORE<br/>HELLO<br/>'
        '<span style="letter-spacing: 0.0px;">AFTER</span></p></li></ul>'
    )
    out = convert(xml)
    assert out == (
        '- BEFORE\n'
        '  HELLO\n'
        '  AFTER'
    )


def test_br_inside_ordered_li_uses_three_space_continuation():
    # `1. ` marker is 3 chars wide; continuation indent is 3 spaces.
    xml = '<ol><li><p>BEFORE<br/>HELLO</p></li></ol>'
    out = convert(xml)
    assert out == '1. BEFORE\n   HELLO'


def test_br_inside_nested_li_drops_to_column_zero():
    # `<br/>` continuation indent applies only at depth 0; nested <li>s (depth ≥ 1)
    # produce a bare \n so the post-<br/> content sits at column 0, effectively
    # terminating the inner list at the <br/> boundary.
    xml = '<ul><li><p>OUTER</p><ul><li><p>X<br/>Y</p></li></ul></li></ul>'
    out = convert(xml)
    assert '\t- X\nY' in out
    assert '\t  Y' not in out


def _table_for_nested_li_examples():
    return (
        '<table class="wrapped" style="text-align: left;"><colgroup><col /></colgroup>'
        '<tbody style="text-align: left;"><tr style="text-align: left;">'
        '<td style="text-align: left;"><p style="text-align: left;">'
        '<code class="java plain" style="text-align: left;">INSIDE TABLE</code>'
        '</p></td></tr></tbody></table>'
    )


def test_li_with_block_nested_and_trailing_p_interleaves_in_source_order():
    # Outer <ol> <li> has: <p>WORLD</p>, <table>, <ul><li>HELLO</li></ul>, <p>AFTER</p>
    # The <table> is now a ```merge-table fenced block; the fence-exception in
    # the <li>-block rule indents it inside the list item rather than hoisting
    # to column 0. The intervening fence lines reset the depth-jump pass's
    # list-line scan, so the nested <ul> still gets a `- ` placeholder injected
    # at depth 0. Trailing <p>AFTER</p> still picks up the 2-space post-nested
    # indent.
    xml = (
        '<ol><li>'
        '<p class="auto-cursor-target">WORLD</p>'
        + _table_for_nested_li_examples() +
        '<ul><li>HELLO</li></ul>'
        '<p class="auto-cursor-target">AFTER</p>'
        '</li></ol>'
    )
    out = convert(xml)
    assert '1. WORLD' in out
    # Merge-table fence is indented 4 spaces inside the depth-0 list item.
    assert '    ```merge-table\n' in out
    assert '    ```\n' in out
    # Table-level tableStyle carries the style attribute verbatim.
    assert '"tableStyle": "text-align: left;"' in out
    # Nested list still appears (with depth-jump placeholder above it).
    assert '\n- \n\t- HELLO' in out
    # Source order preserved.
    assert out.index('\t- HELLO') < out.index('AFTER')
    # Trailing hoisted content gets the 2-space post-nested indent.
    assert '\n\n  AFTER' in out


def test_li_with_block_nested_and_br_inside_nested_li_drops_after_to_column_zero():
    # Outer <ol> <li> has: <p>WORLD</p>, <table>, <ul><li>HELLO<br/>AFTER</li></ul>
    # The <br/> inside the depth-1 nested <li> body produces a bare \n (no
    # continuation indent), so AFTER lands at column 0.
    xml = (
        '<ol><li>'
        '<p class="auto-cursor-target">WORLD</p>'
        + _table_for_nested_li_examples() +
        '<ul><li>HELLO<br />AFTER</li></ul>'
        '</li></ol>'
    )
    out = convert(xml)
    assert '\t- HELLO\nAFTER' in out
    assert '\t  AFTER' not in out


def test_paragraph_with_margin_left_40px_emits_indent_callout_depth_one():
    # Confluence emits `<p style="margin-left: Npx;">` when the author indents a
    # paragraph via the toolbar (each toolbar-indent level = 40px). The
    # paragraph becomes a `> [!indent]` callout; depth is RELATIVE within a
    # consecutive run of margin paragraphs (smallest margin = depth 1).
    xml = '<h1>X</h1><p style="margin-left: 40.0px;">AFTER</p>'
    out = convert(xml)
    assert out == "# X\n\n> [!indent]\n> AFTER"


def test_paragraph_with_margin_left_80px_alone_still_emits_depth_one():
    # 80px alone (no smaller margin in the same run) is depth 1, not depth 2 —
    # the rule is relative, not absolute.
    xml = '<h1>X</h1><p style="margin-left: 80px;">AFTER</p>'
    out = convert(xml)
    assert out == "# X\n\n> [!indent]\n> AFTER"


def test_tag_only_p_with_colored_span_only_preserves_break():
    # Colored <span> direct child of tag-only <p> (no nested formatting inside
    # the span) still preserves the paragraph break via single `\n`. Broadens
    # last turn's rule which required nested-tag descendants.
    xml = (
        '<h1><span style="color: rgb(51,51,51);">HEADER</span></h1>'
        '<p><span style="color: rgb(51,51,51);">TEXT</span></p>'
    )
    out = convert(xml)
    assert out == (
        '# <font style="color: rgb(51,51,51);">HEADER</font>\n'
        '<font style="color: rgb(51,51,51);">TEXT</font>'
    )


def test_heading_then_text_then_indent_then_text_full_shape():
    # User's Example 2: heading, plain-colored-paragraph, indented paragraph,
    # plain-colored-paragraph. The indented one becomes a single-depth callout
    # surrounded by blank-line paragraph spacing on both sides.
    xml = (
        '<h1><span style="color: rgb(51,51,51);">HEADER</span></h1>'
        '<p><span style="color: rgb(51,51,51);">TEXT_1</span></p>'
        '<p style="margin-left: 80.0px;"><span style="color: rgb(51,51,51);">INDENTED_TEXT</span></p>'
        '<p><span style="color: rgb(51,51,51);">TEXT_2</span></p>'
    )
    out = convert(xml)
    assert out == (
        '# <font style="color: rgb(51,51,51);">HEADER</font>\n'
        '<font style="color: rgb(51,51,51);">TEXT\\_1</font>\n'
        '\n'
        '> [!indent]\n'
        '> <font style="color: rgb(51,51,51);">INDENTED\\_TEXT</font>\n'
        '\n'
        '<font style="color: rgb(51,51,51);">TEXT\\_2</font>'
    )


def test_consecutive_margin_paragraphs_progressive_nest_relative_depths():
    # A consecutive run of margin paragraphs with progressively deeper margins
    # nests at relative depths 1, 2, 3, …. The smallest margin in the run is
    # depth 1; each next-deeper margin adds one level of `> ` prefix.
    xml = (
        '<p style="margin-left: 40.0px;">ONE</p>'
        '<p style="margin-left: 80.0px;">TWO</p>'
        '<p style="margin-left: 120.0px;">THREE</p>'
    )
    out = convert(xml)
    assert out == (
        "> [!indent]\n"
        "> ONE\n"
        "> > [!indent]\n"
        "> > TWO\n"
        "> > > [!indent]\n"
        "> > > THREE"
    )


def test_margin_left_px_rounded_to_nearest_forty():
    # Non-multiples of 40 (e.g. 30, 70) round to nearest 40 via round(px/40).
    xml = (
        '<p style="margin-left: 30.0px;">A</p>'
        '<p style="margin-left: 70.0px;">B</p>'
    )
    out = convert(xml)
    # 30 → round(0.75) = 1; 70 → round(1.75) = 2. Run [1, 2], min=1, depths [1, 2].
    assert out == "> [!indent]\n> A\n> > [!indent]\n> > B"


def test_paragraph_with_margin_left_zero_no_indent():
    xml = '<h1>X</h1><p style="margin-left: 0px;">AFTER</p>'
    out = convert(xml)
    assert out == "# X\n\nAFTER"


def test_paragraph_without_margin_left_no_indent():
    xml = '<h1>X</h1><p>AFTER</p>'
    out = convert(xml)
    assert out == "# X\n\nAFTER"


def test_li_with_nested_then_doc_level_margin_p_after_emits_indent_callout():
    # Document-level <p style="margin-left: 40px;"> after a list with hoisted
    # blocks and a nested <ul>. Margin paragraph becomes a `[!indent]` callout
    # at depth 1 (single-paragraph run).
    xml = (
        '<ol><li>'
        '<p class="auto-cursor-target">WORLD</p>'
        + _table_for_nested_li_examples() +
        '<ul><li>HELLO</li></ul>'
        '</li></ol>'
        '<p style="margin-left: 40.0px;">AFTER</p>'
    )
    out = convert(xml)
    assert '\t- HELLO\n> [!indent]\n> AFTER' in out


def test_code_macro_in_li_only_content_emits_indented_fence_under_empty_marker():
    # <li> contains only the code macro (cursor-park <p>s drop) → empty marker
    # line followed by a 4-space-indented fenced block that stays inside the
    # list item under CommonMark.
    xml = (
        '<ul>'
        '<li>BEFORE</li>'
        '<li>'
        '<p class="auto-cursor-target"><br /></p>'
        '<ac:structured-macro ac:name="code"><ac:plain-text-body><![CDATA[CODE_TEXT]]></ac:plain-text-body></ac:structured-macro>'
        '<p class="auto-cursor-target"><br /></p>'
        '</li>'
        '<li>AFTER</li>'
        '</ul>'
    )
    out = convert(xml)
    assert out == (
        "- BEFORE\n"
        "- \n"
        "    ```\n"
        "    CODE_TEXT\n"
        "    ```\n"
        "- AFTER"
    )


def test_code_macro_in_li_after_inline_body_emits_indented_fence_below_marker():
    # <li> has BEFORE inline body and a code macro hoisted; under the new rule
    # the fenced block is 4-space indented to stay inside the list item rather
    # than column-0 hoisted.
    xml = (
        '<ul>'
        '<li>'
        '<p class="auto-cursor-target">BEFORE</p>'
        '<ac:structured-macro ac:name="code"><ac:plain-text-body><![CDATA[CODE_TEXT]]></ac:plain-text-body></ac:structured-macro>'
        '<p class="auto-cursor-target"><br /></p>'
        '</li>'
        '<li>AFTER</li>'
        '</ul>'
    )
    out = convert(xml)
    assert out == (
        "- BEFORE\n"
        "    ```\n"
        "    CODE_TEXT\n"
        "    ```\n"
        "- AFTER"
    )


def test_code_macro_at_document_level_between_lists_no_blank_line_before_fence():
    # Document-level code macro between two lists: the rule-(4) list-trailing
    # blank is suppressed before the fence so the code sits flush against the
    # list (same pattern as the `>` callout suppression).
    xml = (
        '<ul><li>BEFORE</li></ul>'
        '<ac:structured-macro ac:name="code"><ac:plain-text-body><![CDATA[CODE_TEXT]]></ac:plain-text-body></ac:structured-macro>'
        '<p><br /></p>'
        '<ul><li>AFTER</li></ul>'
    )
    out = convert(xml)
    assert out == (
        "- BEFORE\n"
        "```\n"
        "CODE_TEXT\n"
        "```\n"
        "- AFTER"
    )


def test_code_macro_in_nested_li_uses_tab_plus_four_space_indent():
    # Nested <li> at depth 1 → indent is `\t` (depth scaling) + 4 spaces.
    xml = (
        '<ul><li>'
        '<p>OUTER</p>'
        '<ul><li>'
        '<p class="auto-cursor-target">INNER</p>'
        '<ac:structured-macro ac:name="code"><ac:plain-text-body><![CDATA[X]]></ac:plain-text-body></ac:structured-macro>'
        '</li></ul>'
        '</li></ul>'
    )
    out = convert(xml)
    assert "\t- INNER\n\t    ```\n\t    X\n\t    ```" in out


def test_code_macro_only_in_li_does_not_log_block_content_warning():
    # The "list item with block content (hoisted to column 0)" warning was
    # noise for code macros under the new rule — code stays INSIDE the item,
    # not hoisted to column 0. Warning is suppressed when only code blocks
    # appear in the hoist set.
    from src.converter import Converter
    xml = (
        '<ul><li>'
        '<p>X</p>'
        '<ac:structured-macro ac:name="code"><ac:plain-text-body><![CDATA[y]]></ac:plain-text-body></ac:structured-macro>'
        '</li></ul>'
    )
    c = Converter('MyPage')
    c.convert(xml)
    assert not any("list item" in w.lower() for w in c.warnings)


def test_tag_only_p_with_nested_formatting_preserves_break_single_newline():
    # A tag-only <p> whose direct tag child has another tag descendant
    # (`<span color><strong>X</strong></span>` here) is the user's signal for
    # "meaningful paragraph, not cursor-park" — preserve the paragraph break
    # via a single `\n` (no blank line) so the line doesn't glue to the previous
    # block's content.
    xml = (
        '<h1><span style="color: rgb(51,51,51);">HEADER</span></h1>'
        '<p><span style="color: rgb(51,51,51);"><strong>TEXT</strong></span></p>'
    )
    out = convert(xml)
    assert out == (
        '# <font style="color: rgb(51,51,51);">HEADER</font>\n'
        '<font style="color: rgb(51,51,51);"><strong>TEXT</strong></font>'
    )


def test_tag_only_p_with_single_inline_no_nesting_still_unwraps():
    # The cursor-park carve-out is intact when the direct tag child has NO
    # tag descendants — `<p><code>X</code></p>` and `<p><span color>X</span></p>`
    # still unwrap so they glue inline to the previous content.
    xml = '<p>before</p><p><code>X</code></p>'
    out = convert(xml)
    # Cursor-park unwrap → no `\n` before the <code>; glues to "before".
    assert out == 'before<code>X</code>'


def test_tag_only_p_with_strong_no_nesting_still_unwraps():
    xml = '<p>before</p><p><strong>X</strong></p>'
    out = convert(xml)
    assert out == 'before<strong>X</strong>'


def test_tag_only_p_with_double_nested_formatting_preserves_break():
    # `<strong><em>X</em></strong>` inside <p> — `<em>` is nested under `<strong>`,
    # triggers the carve-out, paragraph break preserved.
    xml = '<h2>HEAD</h2><p><strong><em>X</em></strong></p>'
    out = convert(xml)
    assert out == '## HEAD\n<strong><em>X</em></strong>'


def test_tag_only_p_with_macro_only_still_unwraps():
    # `ac:*` descendants don't trigger the carve-out — macro-only <p>s keep
    # the original cursor-park-style unwrap, so callouts and other macros sit
    # flush against their preceding content without an extra paragraph break.
    xml = (
        '<h1>HEAD</h1>'
        '<p><ac:structured-macro ac:name="info">'
        '<ac:rich-text-body><p>note</p></ac:rich-text-body>'
        '</ac:structured-macro></p>'
    )
    out = convert(xml)
    # info macro renders as `> [!info]\n> note`; wrapper <p> unwraps because
    # the macro's direct children (ac:rich-text-body, ac:parameter, …) all
    # start with `ac:` so the nested-formatting check stays False.
    assert "# HEAD\n> [!info]\n> note" in out


def test_li_with_block_nested_then_document_level_p_after_keeps_blank_line():
    # Outer <ol> <li> has block + nested <ul>; <p>AFTER</p> at document level
    # after </ol>. The document-level boundary keeps the blank line; AFTER at
    # column 0 (no continuation indent — it's not hoisted from the outer <li>).
    xml = (
        '<ol><li>'
        '<p class="auto-cursor-target">WORLD</p>'
        + _table_for_nested_li_examples() +
        '<ul><li>HELLO</li></ul>'
        '</li></ol>'
        '<p>AFTER</p>'
    )
    out = convert(xml)
    assert '\t- HELLO\n\nAFTER' in out
    assert '  AFTER' not in out  # no 2-space indent because AFTER is doc-level


def test_pre_uncolored_span_unwraps_but_colored_becomes_font():
    out = convert('<pre><span>plain</span> <span style="color: red;">red</span></pre>')
    assert out == '<span style="white-space: pre-wrap"><code>plain <font style="color: red;">red</font></code></span>'


def test_pre_strong_renders_as_raw_html():
    out = convert("<pre><strong>foo</strong></pre>")
    assert out == '<span style="white-space: pre-wrap"><code><strong>foo</strong></code></span>'


def test_pre_empty_emits_nothing():
    assert convert("<pre></pre>") == ""
    assert convert("<pre>  \n  </pre>") == ""


def test_pre_user_example_br_separator():
    # Per spec: <pre>Hello<br/>World</pre> wraps the multi-<code>-with-<br> in a
    # <span style="white-space: pre-wrap"> so Obsidian preserves indentation.
    out = convert("<pre>Hello<br/>World</pre>")
    assert out == '<span style="white-space: pre-wrap"><code>Hello</code><br><code>World</code></span>'


def test_pre_splits_on_br_and_newline():
    out = convert("<pre>a<br/>b\nc</pre>")
    assert out == '<span style="white-space: pre-wrap"><code>a</code><br><code>b</code><br><code>c</code></span>'


def test_pre_drops_trailing_empty_lines():
    out = convert("<pre>foo\n\n\n</pre>")
    assert out == '<span style="white-space: pre-wrap"><code>foo</code></span>'


def test_pre_keeps_internal_empty_lines():
    out = convert("<pre>foo\n\nbar</pre>")
    assert out == '<span style="white-space: pre-wrap"><code>foo</code><br><code></code><br><code>bar</code></span>'


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
        '<span style="white-space: pre-wrap">'
        '<code><font style="color: rgb(0,0,255);">GET</font> '
        '<font style="color: rgb(0,0,255);">/index.html</font> '
        '<font style="color: rgb(0,128,0);">HTTP</font>'
        '<font style="color: rgb(102,102,102);">/</font>'
        '<font style="color: rgb(102,102,102);">1.1</font></code><br>'
        '<code><font style="color: rgb(125,144,41);">Host</font>'
        '<font style="color: rgb(102,102,102);">:</font> www.example.org</code><br>'
        '<code>...</code>'
        '</span>'
    )
    assert convert(xml) == expected


def test_escape_full_set_applied_inside_colored_span_font():
    # Colored <span> becomes <font> in output. Obsidian's HTML extension processes
    # Markdown inside <font> the same as inside <code>, so the full plain-text
    # escape set applies (was previously left verbatim — corrected after observing
    # `**bold**` / `*italic*` rendering between <font> tags).
    out = convert('<p><span style="color: red;">[red text]</span></p>')
    assert out == '<font style="color: red;">\\[red text\\]</font>'


def test_escape_bold_pattern_inside_colored_span_font():
    # Real-world case: **TEXT** inside <font> would render as bold without the
    # escape — same observation as inside <code>.
    out = convert('<p><span style="color: red;">**TEXT**</span></p>')
    assert out == '<font style="color: red;">\\*\\*TEXT\\*\\*</font>'


def test_escape_full_plain_text_set_inside_colored_span_font():
    out = convert('<p><span style="color: red;">\\ ` * _ ~ # [ ] $</span></p>')
    assert out == '<font style="color: red;">\\\\ \\` \\* \\_ \\~ \\# \\[ \\] \\$</font>'


def test_escape_applied_to_colored_span_inside_pre():
    # Colored span inside <pre> renders as <font> inside <code>; the escape applies
    # because both the <pre>'s child rendering and the colored-span rule resolve
    # to the same full plain-text set.
    out = convert('<pre><span style="color: red;">*foo*</span></pre>')
    assert '<font style="color: red;">\\*foo\\*</font>' in out


def test_escape_suppressed_in_code_macro_body():
    # Code macro body comes from ac:plain-text-body (CDATA), no escape applied
    xml = '<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">python</ac:parameter><ac:plain-text-body><![CDATA[a = [1, 2]]]></ac:plain-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "a = [1, 2]" in out
    assert "\\[" not in out


def test_escape_closer_code_wins_over_outer_paragraph():
    # <code> short-circuits the ancestor walk in _plain_text_escape_re — closer
    # wins on which regex applies. Both <p> and <code> now use the same plain-text
    # set, so `[` / `]` get the same backslash escape regardless.
    out = convert("<p>foo <code>[x]</code> bar</p>")
    assert out == "foo <code>\\[x\\]</code> bar"


def test_escape_brackets_only_when_anchor_anywhere_in_chain():
    # <strong> inside <a>: the <a> ancestor demotes the inner text to brackets-only mode,
    # so [ ] are escaped but the <strong> wrapper survives as raw HTML.
    out = convert('<p><a href="u"><strong>[link]</strong></a></p>')
    assert "[<strong>\\[link\\]</strong>](u)" in out


def test_escape_angle_brackets_in_paragraph():
    assert convert("<p>&lt;&gt;</p>") == "\\<\\>"


def test_escape_angle_brackets_in_heading():
    assert convert("<h2>Section &lt;X&gt;</h2>") == "## Section \\<X\\>"


def test_escape_angle_brackets_in_list_item():
    out = convert("<ul><li>&lt;item&gt;</li></ul>").strip()
    assert out == "- \\<item\\>"


def test_escape_angle_brackets_inside_anchor_link_text():
    out = convert('<p><a href="u">X &lt;Y&gt;</a></p>')
    assert "[X \\<Y\\>](u)" in out


def test_escape_angle_brackets_inside_code():
    # Angle escape applies inside <code> (HTML parser would otherwise read <Y> as a tag).
    # Other markdown metacharacters still NOT escaped inside <code>.
    assert convert("<p>use <code>&lt;Y&gt;</code> here</p>") == "use <code>\\<Y\\></code> here"


def test_escape_full_plain_text_set_applied_inside_code():
    # The full plain-text set is escaped inside <code> — `*`, `_`, `~`, `[`, `]`,
    # `$`, `#`, `<`, `>`, `\`, `` ` `` — because Obsidian's HTML extension processes
    # Markdown (bold/italics etc.) inside inline-code.
    out = convert("<p>X <code>*foo* &lt;Y&gt;</code> Z</p>")
    assert out == "X <code>\\*foo\\* \\<Y\\></code> Z"


def test_escape_full_set_inside_inline_code_each_char():
    # Each of \, `, *, _, ~, [, ], $ picks up a backslash inside <code>
    # (in addition to <, >, # already covered elsewhere).
    out = convert("<p><code>\\ ` * _ ~ [ ] $</code></p>")
    assert out == "<code>\\\\ \\` \\* \\_ \\~ \\[ \\] \\$</code>"


def test_escape_full_set_inside_pre_each_char():
    out = convert("<pre>\\ ` * _ ~ [ ] $</pre>")
    assert '<code>\\\\ \\` \\* \\_ \\~ \\[ \\] \\$</code>' in out


def test_escape_bold_pattern_inside_inline_code():
    # Real-world case: **TEXT** inside <code> would render as bold without
    # the escape. Each `*` gets backslash-escaped.
    out = convert("<p>see <code>**TEXT**</code></p>")
    assert out == "see <code>\\*\\*TEXT\\*\\*</code>"


def test_full_set_not_escaped_in_document_level_code_macro_body():
    # Document-level fenced ```py block stays verbatim — Markdown isn't processed
    # inside the fence, so escapes would render as visible backslashes.
    xml = (
        '<ac:structured-macro ac:name="code">'
        '<ac:parameter ac:name="language">py</ac:parameter>'
        '<ac:plain-text-body><![CDATA[a * b _c_ ~d~ [e] $f]]></ac:plain-text-body>'
        '</ac:structured-macro>'
    )
    out = convert(xml)
    assert "a * b _c_ ~d~ [e] $f" in out
    assert "\\*" not in out
    assert "\\_" not in out
    assert "\\~" not in out
    assert "\\[" not in out
    assert "\\$" not in out


def test_escape_hash_inside_inline_code():
    # `#` inside <code> is backslash-escaped to defeat Obsidian's tag extension,
    # which fires on `#word` patterns even inside HTML inline-code.
    out = convert("<p>use <code>#define</code> here</p>")
    assert out == "use <code>\\#define</code> here"


def test_escape_hash_inside_inline_code_multiple_occurrences():
    out = convert("<p><code>color=#ff0000 # red</code></p>")
    assert out == "<code>color=\\#ff0000 \\# red</code>"


def test_escape_angle_brackets_inside_pre():
    # <pre> renders as multi-<code> lines wrapped in <span style="white-space: pre-wrap">;
    # angle escape applies inside each line.
    out = convert("<pre>&lt;X&gt;</pre>")
    assert out == '<span style="white-space: pre-wrap"><code>\\<X\\></code></span>'


def test_escape_hash_inside_pre():
    out = convert("<pre>#define FOO 1\nx = #ff0000</pre>")
    assert out == (
        '<span style="white-space: pre-wrap">'
        '<code>\\#define FOO 1</code><br><code>x = \\#ff0000</code>'
        '</span>'
    )


def test_escape_angle_brackets_not_applied_in_code_macro_body():
    # ac:plain-text-body becomes a fenced code block — no HTML parsing inside the
    # fence, so <> stay literal (not escaped).
    xml = '<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">py</ac:parameter><ac:plain-text-body><![CDATA[x = <Y>]]></ac:plain-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "x = <Y>" in out
    assert "\\<" not in out


def test_hash_not_escaped_in_document_level_code_macro_body():
    # Document-level ac:name="code" emits a fenced ```py block; Markdown isn't
    # processed inside the fence, so `\#` would render as a visible backslash to
    # the reader. Skip the escape — `#` stays literal in fenced blocks.
    xml = '<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">py</ac:parameter><ac:plain-text-body><![CDATA[x = 1 # comment\ny = #ff0000]]></ac:plain-text-body></ac:structured-macro>'
    out = convert(xml)
    assert "x = 1 # comment" in out
    assert "y = #ff0000" in out
    assert "\\#" not in out


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


def test_br_becomes_plain_newline():
    # Soft break inside the paragraph; Obsidian's default "Strict line breaks"
    # OFF setting converts this to a rendered <br>.
    out = convert("<p>line1<br/>line2</p>")
    assert out == "line1\nline2"
    assert "\\" not in out


def test_sub_preserved_as_raw_html():
    assert convert("<p>H<sub>2</sub>O</p>") == "H<sub>2</sub>O"


def test_sup_preserved_as_raw_html():
    assert convert("<p>E = mc<sup>2</sup></p>") == "E = mc<sup>2</sup>"


def test_sup_with_spaces_and_inline_markup():
    out = convert("<p>x<sup>n + 1</sup> and y<sub><strong>k</strong></sub></p>")
    assert "x<sup>n + 1</sup>" in out
    assert "y<sub><strong>k</strong></sub>" in out


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


def test_colored_span_wrapping_children_macro_drops_font_wrapper():
    # A colored <span> wrapping a block-emitting macro is meaningless —
    # the <font> tag can't color a dataview/code/callout block. Drop it.
    xml = '<p><span style="color: rgb(51,51,51);"><ac:structured-macro ac:name="children"/></span></p>'
    out = convert(xml)
    assert "<font" not in out
    assert "```dataview" in out


def test_nested_colored_spans_wrapping_children_macro_unwrap_recursively():
    xml = (
        '<p><span style="color: rgb(51,51,51);">'
        '<span style="color: rgb(88,88,88);">'
        '<ac:structured-macro ac:name="children"/>'
        '</span></span></p>'
    )
    out = convert(xml)
    assert "<font" not in out
    assert "```dataview" in out


def test_colored_span_wrapping_code_macro_drops_font_wrapper():
    xml = (
        '<span style="color: red;"><ac:structured-macro ac:name="code">'
        '<ac:parameter ac:name="language">py</ac:parameter>'
        '<ac:plain-text-body><![CDATA[x = 1]]></ac:plain-text-body>'
        '</ac:structured-macro></span>'
    )
    out = convert(xml)
    assert "<font" not in out
    assert "```py" in out


def test_colored_span_wrapping_inline_text_keeps_font_wrapper():
    # Regression: inline (single-line) content still gets the <font> wrapper.
    out = convert('<p><span style="color: red;">hello</span></p>')
    assert out == '<font style="color: red;">hello</font>'


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


def test_macro_children_outside_list_single_wrap():
    # Case 1 — Children macro after </ul> at document level (no <li> ancestor)
    # → single-level [!list-indent-undo] callout. The trailing blank line
    # after the list is collapsed when the next line starts with > (callout).
    xml = (
        '<ul><li>ROOT</li></ul>'
        '<p><ac:structured-macro ac:name="children" /></p>'
    )
    out = convert(xml)
    expected = (
        "- ROOT\n"
        "> [!list-indent-undo]\n"
        "> ```dataview\n"
        "> LIST\n"
        '> FROM ""\n'
        '> WHERE file.folder = this.file.folder + "/" + this.file.name\n'
        "> ```"
    )
    assert expected in out


def test_macro_children_after_paragraph_is_bare():
    # No <li> ancestor AND no preceding list — emit bare dataview without
    # the [!list-indent-undo] callout (nothing to indent-undo from).
    xml = (
        '<p>BEFORE</p>'
        '<p class="auto-cursor-target"><ac:structured-macro ac:name="children" /></p>'
    )
    out = convert(xml)
    assert out == (
        "BEFORE\n"
        "```dataview\n"
        "LIST\n"
        'FROM ""\n'
        'WHERE file.folder = this.file.folder + "/" + this.file.name\n'
        "```"
    )
    assert "[!list-indent-undo]" not in out


def test_macro_children_after_ol_keeps_single_wrap():
    # Preceded by <ol> (ordered list, not just <ul>) → still wrap.
    xml = (
        '<ol><li>ITEM</li></ol>'
        '<p><ac:structured-macro ac:name="children" /></p>'
    )
    out = convert(xml)
    assert "> [!list-indent-undo]" in out
    assert "> ```dataview" in out


def test_macro_children_orphan_is_bare():
    # No preceding sibling at all → bare dataview.
    xml = '<p><ac:structured-macro ac:name="children" /></p>'
    out = convert(xml)
    assert "[!list-indent-undo]" not in out
    assert out.startswith("```dataview")


def test_macro_children_after_paragraph_then_list_is_bare():
    # Immediate prior sibling check — a list earlier in the document doesn't
    # count if a paragraph sits between it and the macro.
    xml = (
        '<ul><li>EARLY</li></ul>'
        '<p>SEPARATOR</p>'
        '<p><ac:structured-macro ac:name="children" /></p>'
    )
    out = convert(xml)
    assert "[!list-indent-undo]" not in out
    assert "```dataview" in out


def test_macro_children_inside_li_double_wrap_and_marker_dropped():
    # Case 2 — Children macro IS the entire <li> content. Two-level wrap,
    # and the empty list marker line is dropped (no orphan "- " above the callout).
    xml = (
        '<ul>'
        '<li>TWO</li>'
        '<li><ac:structured-macro ac:name="children" /></li>'
        '</ul>'
    )
    out = convert(xml)
    expected = (
        "- TWO\n"
        "> [!list-indent-undo]\n"
        "> > [!indent]\n"
        "> > ```dataview\n"
        "> > LIST\n"
        '> > FROM ""\n'
        '> > WHERE file.folder = this.file.folder + "/" + this.file.name\n'
        "> > ```"
    )
    assert expected in out
    # The empty <li>'s marker is dropped — no orphan "- " line between TWO and the callout.
    assert "TWO\n- \n>" not in out
    assert "TWO\n-\n>" not in out


def test_macro_children_inside_nested_li_double_wrap():
    # Case 3 — Children macro inside a nested <li> at depth > 0. Still 2 wraps;
    # the callout sits at column 0 regardless of source nesting depth.
    xml = (
        '<ul><li>ROOT'
        '<ul>'
        '<li>ROOTTWO</li>'
        '<li><ac:structured-macro ac:name="children" /></li>'
        '</ul>'
        '</li></ul>'
    )
    out = convert(xml)
    expected = (
        "- ROOT\n"
        "\t- ROOTTWO\n"
        "> [!list-indent-undo]\n"
        "> > [!indent]\n"
        "> > ```dataview\n"
        "> > LIST\n"
        '> > FROM ""\n'
        '> > WHERE file.folder = this.file.folder + "/" + this.file.name\n'
        "> > ```"
    )
    assert expected in out


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
    assert "<strong>bold</strong> and <em>italic</em>" in out
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


def test_image_inside_li_wraps_in_double_callout_and_hoists():
    # Image inside <li> → 2-level callout wrap, hoisted to column 0.
    # Text content of the <li> stays on the marker line.
    xml = (
        '<ul><li>TWO<br/>'
        '<ac:image ac:width="301"><ri:attachment ri:filename="linear-chain-crf.png"/></ac:image>'
        '</li></ul>'
    )
    out = convert(xml, page_name="15 TODO")
    expected = (
        "- TWO\n"
        "> [!list-indent-undo]\n"
        "> > [!indent]\n"
        "> > ![[15 TODO/linear-chain-crf.png|301]]"
    )
    assert expected in out


def test_image_outside_list_no_callout_wrap():
    # Image at document level (no <li> ancestor) → no callout wrap, just the
    # bare wiki-link with the existing block-spacing rules around it.
    xml = (
        '<ul><li>TWO</li></ul>'
        '<p><ac:image ac:width="301"><ri:attachment ri:filename="linear-chain-crf.png"/></ac:image></p>'
    )
    out = convert(xml, page_name="15 TODO")
    expected = "- TWO\n\n![[15 TODO/linear-chain-crf.png|301]]"
    assert expected in out
    assert "[!list-indent-undo]" not in out


def test_li_with_only_image_drops_marker():
    # An <li> whose only content is an image → marker line dropped, just the
    # callout-wrapped image emitted.
    xml = (
        '<ul><li>OUTER</li>'
        '<li><ac:image ac:width="200"><ri:attachment ri:filename="img.png"/></ac:image></li>'
        '</ul>'
    )
    out = convert(xml, page_name="P")
    expected = (
        "- OUTER\n"
        "> [!list-indent-undo]\n"
        "> > [!indent]\n"
        "> > ![[P/img.png|200]]"
    )
    assert expected in out
    # No empty "- " line for the second <li>.
    assert "OUTER\n- \n>" not in out


def test_empty_ac_link_self_closing_emits_self_link():
    xml = '<p>before <ac:link/> after</p>'
    out = convert(xml)
    assert out == "before [[TestPage]] after"


def test_empty_ac_link_empty_pair_emits_self_link():
    xml = '<p>before <ac:link></ac:link> after</p>'
    out = convert(xml)
    assert out == "before [[TestPage]] after"


def test_empty_ac_link_sanitizes_current_page_title():
    xml = '<ac:link/>'
    out = Converter("Design  v2", page_title="Design: v2").convert(xml).strip()
    assert out == "[[Design： v2]]"


def test_empty_ac_link_drops_collision_suffix():
    xml = '<ac:link/>'
    out = Converter("Foo (12345)", page_title="Foo").convert(xml).strip()
    assert out == "[[Foo]]"


def test_ac_link_with_unsupported_ri_user_target_unchanged():
    xml = '<p>before <ac:link><ri:user ri:username="x"/></ac:link> after</p>'
    out = convert(xml)
    assert out == "before  after"
    assert "[[TestPage]]" not in out


def test_empty_ac_link_in_table_cell_self_links_via_document_mode():
    # With document-mode cell rendering, empty <ac:link/> in a cell now self-links
    # to the current page (same as at document level), not the old cell-context
    # fallback of empty text. Behavior change introduced with the merge-table
    # migration.
    xml = '<table><tbody><tr><td>before <ac:link/> after</td></tr></tbody></table>'
    out = convert(xml)
    assert '"before [[TestPage]] after"' in out


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


def test_ac_link_to_attachment_emits_bare_filename_wiki_link():
    # No per-page prefix — Obsidian resolves the wiki-link by name across the vault.
    xml = '<ac:link><ri:attachment ri:filename="report.pdf" /></ac:link>'
    out = convert(xml, page_name="MyPage")
    assert out == "[[report.pdf]]"


def test_ac_link_to_attachment_with_display_text_uses_pipe_separator():
    # <ac:plain-text-link-body> CDATA becomes the display text after the | separator.
    xml = (
        '<ac:link>'
        '<ri:attachment ri:filename="report.pdf" />'
        '<ac:plain-text-link-body><![CDATA[Q1 Report]]></ac:plain-text-link-body>'
        '</ac:link>'
    )
    out = convert(xml, page_name="MyPage")
    assert out == "[[report.pdf|Q1 Report]]"


def test_ac_link_to_attachment_normalizes_unicode_whitespace_in_filename():
    # NBSP in the filename normalizes to ASCII space on both the wiki-link target
    # and the on-disk filename — they must agree for Obsidian to resolve the link.
    nbsp = chr(0xa0)
    xml = f'<ac:link><ri:attachment ri:filename="My{nbsp}File.pdf" /></ac:link>'
    out = convert(xml, page_name="MyPage")
    assert out == "[[My File.pdf]]"
    assert nbsp not in out


def test_ac_link_to_attachment_in_table_cell_emits_bare_filename():
    # Cell context goes through document-mode <ac:link> handler (post-merge-table),
    # so the bare-filename rule applies inside cells too.
    xml = '<table><tr><td><ac:link><ri:attachment ri:filename="a.pdf" /></ac:link></td></tr></table>'
    out = convert(xml, page_name="MyPage")
    assert '"[[a.pdf]]"' in out
    assert '[[MyPage/a.pdf]]' not in out

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


def test_macro_ui_tabs_emits_callout_block():
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
        "> [!tabs]\n"
        ">\n"
        "> === Tab 1\n"
        ">\n"
        "> Tab 1 content here\n"
        ">\n"
        "> === Tab 2\n"
        ">\n"
        "> Tab 2 content here\n"
        ">\n"
        "> === Tab 3\n"
        ">\n"
        "> Tab 3 content here"
    )
    assert out == expected
    assert "~~~tabs" not in out
    assert "---tab" not in out


def test_macro_ui_tabs_single_tab():
    xml = (
        '<ac:structured-macro ac:name="ui-tabs"><ac:rich-text-body>'
        '<ac:structured-macro ac:name="ui-tab"><ac:parameter ac:name="title">Only</ac:parameter>'
        '<ac:rich-text-body><p>body</p></ac:rich-text-body></ac:structured-macro>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml).strip()
    assert out == "> [!tabs]\n>\n> === Only\n>\n> body"


def test_macro_ui_tabs_tab_body_renders_full_markdown():
    # Each line of the tab body picks up `> ` prefix (callout-block convention),
    # so list items and fenced blocks inside a tab are quoted into the [!tabs] callout.
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
    assert "> === T" in out
    assert "> - one" in out
    assert "> - two" in out
    assert "> ```python" in out
    assert "> print(1)" in out


def test_macro_ui_tabs_with_nested_callout_body_double_quotes():
    # An inner `> [!tip]` becomes `> > [!tip]` under the outer tabs callout
    # because the per-line `> ` prefix nests naturally.
    xml = (
        '<ac:structured-macro ac:name="ui-tabs"><ac:rich-text-body>'
        '<ac:structured-macro ac:name="ui-tab"><ac:parameter ac:name="title">T</ac:parameter>'
        '<ac:rich-text-body>'
        '<ac:structured-macro ac:name="info"><ac:rich-text-body><p>note</p></ac:rich-text-body></ac:structured-macro>'
        '</ac:rich-text-body></ac:structured-macro>'
        '</ac:rich-text-body></ac:structured-macro>'
    )
    out = convert(xml)
    assert "> > [!info]" in out
    assert "> > note" in out


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
    # The wrapping <p> is unwrapped; the children macro renders bare (no
    # `[!list-indent-undo]` callout) because the preceding sibling at document
    # level is <h1>, not a list — nothing to indent-undo from.
    assert out.startswith("# Subpages\n```dataview")
    assert "[!list-indent-undo]" not in out


def test_spacing_pure_whitespace_text_between_blocks_ignored():
    xml = "<h1>A</h1>\n\n\n<h2>B</h2>"
    out = convert(xml)
    assert out == "# A\n## B"


def test_p_with_only_code_child_is_unwrapped():
    out = convert("<p><code>TEXT</code></p>")
    assert out == "<code>TEXT</code>"


def test_p_with_only_colored_span_child_is_unwrapped():
    out = convert('<p><span style="color: red;">X</span></p>')
    assert out == '<font style="color: red;">X</font>'


def test_p_with_text_and_code_keeps_paragraph_wrapping():
    out = convert("<p>OUTSIDE<code>TEXT</code>OUTSIDE</p>")
    assert out == "OUTSIDE<code>TEXT</code>OUTSIDE"


def test_p_with_only_strong_child_is_unwrapped():
    out = convert("<p><strong>bold</strong></p>")
    assert out == "<strong>bold</strong>"


def test_p_with_only_anchor_child_is_unwrapped():
    out = convert('<p><a href="https://x.com">link</a></p>')
    assert out == "[link](https://x.com)"


def test_unwrapped_p_glues_to_preceding_content_but_following_p_keeps_break():
    # The unwrap drops the unwrapped-<p>'s OWN paragraph spacing — surrounding
    # <p>s still emit their leading "\n\n". So "before" + unwrapped <p> glue,
    # but the following <p> still starts a new paragraph block.
    out = convert(
        "<p>before</p><p><code>X</code></p><p>after</p>"
    )
    assert out == "before<code>X</code>\n\nafter"


def test_attachments_referenced_tracked():
    c = Converter("MyPage")
    c.convert('<ac:image><ri:attachment ri:filename="a.png" /></ac:image>')
    c.convert('<ac:image><ri:attachment ri:filename="b.png" /></ac:image>')
    assert "a.png" in c.attachments_referenced
    assert "b.png" in c.attachments_referenced


# =============================================================================
# merge-table tests (new tabular output format)
# =============================================================================


def test_merge_table_empty_emits_fenced_block_with_empty_rows():
    xml = "<table></table>"
    out = convert(xml)
    assert out == "```merge-table\n{\n  \"rows\": []\n}\n```"


def test_merge_table_single_text_cell_uses_string_shorthand():
    xml = "<table><tr><td>hello</td></tr></table>"
    out = convert(xml)
    assert out == (
        "```merge-table\n"
        "{\n"
        "  \"rows\": [\n"
        "    [\n"
        "      \"hello\"\n"
        "    ]\n"
        "  ]\n"
        "}\n"
        "```"
    )


def test_merge_table_th_gets_header_true_and_auto_tint():
    xml = "<table><tr><th>H</th></tr></table>"
    out = convert(xml)
    assert "\"header\": true" in out
    assert "\"bg\": \"#F4F5F7\"" in out
    assert "\"content\": \"H\"" in out


def test_merge_table_two_rows_two_cells_each():
    xml = "<table><tr><td>a</td><td>b</td></tr><tr><td>c</td><td>d</td></tr></table>"
    out = convert(xml)
    assert "\"a\"" in out and "\"b\"" in out and "\"c\"" in out and "\"d\"" in out
    # rows are JSON-arrays containing the cells
    import json
    body = out.split("```merge-table\n", 1)[1].rsplit("\n```", 1)[0]
    parsed = json.loads(body)
    assert parsed == {"rows": [["a", "b"], ["c", "d"]]}


# --- cell attribute mapping ---


def test_merge_table_empty_cell_uses_empty_string_shorthand():
    out = convert("<table><tr><td></td></tr></table>")
    import json
    body = out.split("```merge-table\n", 1)[1].rsplit("\n```", 1)[0]
    assert json.loads(body) == {"rows": [[""]]}


def test_merge_table_data_highlight_colour_becomes_bg():
    out = convert('<table><tr><td data-highlight-colour="red">x</td></tr></table>')
    assert '"bg": "red"' in out
    assert '"content": "x"' in out


def test_merge_table_data_highlight_colour_grey_remaps_to_hex():
    out = convert('<table><tr><td data-highlight-colour="grey">x</td></tr></table>')
    assert '"bg": "#F4F5F7"' in out


def test_merge_table_style_background_color_becomes_bg():
    out = convert('<table><tr><td style="background-color: yellow;">x</td></tr></table>')
    assert '"bg": "yellow"' in out


def test_merge_table_data_highlight_colour_overrides_style_background():
    out = convert('<table><tr><td style="background-color: blue;" data-highlight-colour="red">x</td></tr></table>')
    assert '"bg": "red"' in out
    assert '"bg": "blue"' not in out


def test_merge_table_style_color_becomes_color():
    out = convert('<table><tr><td style="color: #ff0000;">x</td></tr></table>')
    assert '"color": "#ff0000"' in out


def test_merge_table_style_text_align_center_becomes_align():
    out = convert('<table><tr><td style="text-align: center;">x</td></tr></table>')
    assert '"align": "center"' in out


def test_merge_table_style_text_align_justify_filtered_out():
    out = convert('<table><tr><td style="text-align: justify;">x</td></tr></table>')
    assert '"align"' not in out


def test_merge_table_style_vertical_align_middle_becomes_valign():
    out = convert('<table><tr><td style="vertical-align: middle;">x</td></tr></table>')
    assert '"valign": "middle"' in out


def test_merge_table_style_vertical_align_baseline_filtered_out():
    out = convert('<table><tr><td style="vertical-align: baseline;">x</td></tr></table>')
    assert '"valign"' not in out


def test_merge_table_unsupported_style_declarations_dropped():
    out = convert('<table><tr><td style="width: 200px; padding: 4px; font-family: serif;">x</td></tr></table>')
    assert 'width' not in out
    assert 'padding' not in out
    assert 'font-family' not in out


def test_merge_table_colspan_emits_attr_and_null_placeholders():
    out = convert('<table><tr><td colspan="3">x</td></tr></table>')
    import json
    body = out.split("```merge-table\n", 1)[1].rsplit("\n```", 1)[0]
    parsed = json.loads(body)
    assert parsed == {"rows": [[{"content": "x", "colspan": 3}, None, None]]}


def test_merge_table_rowspan_emits_attr_no_padding():
    out = convert('<table><tr><td rowspan="2">x</td><td>y</td></tr><tr><td>z</td></tr></table>')
    import json
    body = out.split("```merge-table\n", 1)[1].rsplit("\n```", 1)[0]
    parsed = json.loads(body)
    assert parsed == {"rows": [[{"content": "x", "rowspan": 2}, "y"], ["z"]]}


def test_merge_table_th_with_explicit_bg_skips_auto_tint():
    out = convert('<table><tr><th data-highlight-colour="red">H</th></tr></table>')
    assert '"bg": "red"' in out
    assert '#F4F5F7' not in out


def test_merge_table_table_style_becomes_tableStyle():
    out = convert('<table style="width: 600px;"><tr><td>x</td></tr></table>')
    assert '"tableStyle": "width: 600px;"' in out


def test_merge_table_colgroup_stripped():
    out = convert('<table><colgroup><col/><col/></colgroup><tr><td>x</td></tr></table>')
    assert 'colgroup' not in out
    assert 'col' not in out.replace('color', '').replace('color"', '').replace('colspan', '').replace('"content"', '').replace('null', '')


def test_merge_table_caption_dropped_silently():
    out = convert('<table><caption>Title here</caption><tr><td>x</td></tr></table>')
    assert 'caption' not in out
    assert 'Title here' not in out


def test_merge_table_thead_tbody_tfoot_passthrough():
    out = convert("<table><thead><tr><th>H</th></tr></thead><tbody><tr><td>x</td></tr></tbody></table>")
    import json
    body = out.split("```merge-table\n", 1)[1].rsplit("\n```", 1)[0]
    parsed = json.loads(body)
    assert parsed["rows"] == [
        [{"content": "H", "header": True, "bg": "#F4F5F7"}],
        ["x"],
    ]


# --- cell content via document-mode renderer ---


def test_merge_table_cell_with_bold_uses_document_mode_strong():
    out = convert("<table><tr><td><strong>hello</strong></td></tr></table>")
    assert '"<strong>hello</strong>"' in out


def test_merge_table_cell_with_inline_code_uses_html_code():
    out = convert("<table><tr><td><code>x</code></td></tr></table>")
    assert '"<code>x</code>"' in out


def test_merge_table_cell_with_ac_link_emits_wiki_link():
    xml = '<table><tr><td><ac:link><ri:page ri:content-title="Other Page" /></ac:link></td></tr></table>'
    c = Converter("MyPage", title_map={"Other Page": "Other Page"})
    out = c.convert(xml).strip()
    assert '"[[Other Page]]"' in out


def test_merge_table_cell_with_ac_image_emits_wiki_link_embed():
    xml = '<table><tr><td><ac:image><ri:attachment ri:filename="a.png" /></ac:image></td></tr></table>'
    c = Converter("MyPage")
    out = c.convert(xml).strip()
    assert '"![[MyPage/a.png]]"' in out


def test_merge_table_cell_with_ac_image_with_width_carries_size_suffix():
    xml = '<table><tr><td><ac:image ac:width="100"><ri:attachment ri:filename="a.png" /></ac:image></td></tr></table>'
    c = Converter("MyPage")
    out = c.convert(xml).strip()
    assert '"![[MyPage/a.png|100]]"' in out


def test_merge_table_cell_with_code_macro_emits_fenced_block():
    xml = (
        '<table><tr><td>'
        '<ac:structured-macro ac:name="code">'
        '<ac:parameter ac:name="language">py</ac:parameter>'
        '<ac:plain-text-body><![CDATA[x = 1]]></ac:plain-text-body>'
        '</ac:structured-macro>'
        '</td></tr></table>'
    )
    out = convert(xml)
    # JSON-encoded: ```py\nx = 1\n```
    assert '"```py\\nx = 1\\n```"' in out


def test_merge_table_cell_with_latex_inline_emits_inline_math():
    xml = (
        '<table><tr><td>'
        '<ac:structured-macro ac:name="latex-inline">'
        '<ac:plain-text-body><![CDATA[x^2]]></ac:plain-text-body>'
        '</ac:structured-macro>'
        '</td></tr></table>'
    )
    out = convert(xml)
    assert '"$x^2$"' in out


def test_merge_table_cell_with_latex_block_emits_inline_math_with_warning():
    xml = (
        '<table><tr><td>'
        '<ac:structured-macro ac:name="latex-block">'
        '<ac:plain-text-body><![CDATA[x]]></ac:plain-text-body>'
        '</ac:structured-macro>'
        '</td></tr></table>'
    )
    c = Converter("MyPage")
    out = c.convert(xml).strip()
    assert '"$x$"' in out
    assert any("latex-block" in w and "MyPage" in w for w in c.warnings)


def test_merge_table_cell_with_info_callout_emits_native_obsidian_callout():
    xml = (
        '<table><tr><td>'
        '<ac:structured-macro ac:name="info">'
        '<ac:rich-text-body><p>note</p></ac:rich-text-body>'
        '</ac:structured-macro>'
        '</td></tr></table>'
    )
    out = convert(xml)
    assert '"> [!info]\\n> note"' in out


def test_merge_table_cell_with_expand_emits_native_collapsible_callout():
    xml = (
        '<table><tr><td>'
        '<ac:structured-macro ac:name="expand">'
        '<ac:parameter ac:name="title">More</ac:parameter>'
        '<ac:rich-text-body><p>body</p></ac:rich-text-body>'
        '</ac:structured-macro>'
        '</td></tr></table>'
    )
    out = convert(xml)
    assert '"> [!expand]- More\\n> body"' in out


def test_merge_table_cell_with_unknown_macro_drops_and_logs():
    xml = (
        '<table><tr><td>'
        '<ac:structured-macro ac:name="custom-thing"/>'
        '</td></tr></table>'
    )
    c = Converter("MyPage")
    out = c.convert(xml).strip()
    # No visible XML in cell
    assert "&lt;ac:" not in out
    assert "ac:name=\"custom-thing\"" not in out
    # Empty cell → empty string shorthand
    import json
    body = out.split("```merge-table\n", 1)[1].rsplit("\n```", 1)[0]
    assert json.loads(body) == {"rows": [[""]]}
    # And the unknown-macro list captures it
    assert "custom-thing" in c.unknown_macros


def test_merge_table_cell_with_nested_table_uses_object_content():
    xml = (
        '<table><tr><td>'
        '<table><tr><td>inner</td></tr></table>'
        '</td></tr></table>'
    )
    out = convert(xml)
    import json
    body = out.split("```merge-table\n", 1)[1].rsplit("\n```", 1)[0]
    parsed = json.loads(body)
    assert parsed == {"rows": [[{"content": {"rows": [["inner"]]}}]]}


def test_merge_table_cell_with_prose_then_nested_table_uses_array_content():
    xml = (
        '<table><tr><td>'
        '<p>before</p>'
        '<table><tr><td>inner</td></tr></table>'
        '</td></tr></table>'
    )
    out = convert(xml)
    import json
    body = out.split("```merge-table\n", 1)[1].rsplit("\n```", 1)[0]
    parsed = json.loads(body)
    assert parsed == {"rows": [[{"content": ["before", {"rows": [["inner"]]}]}]]}


def test_merge_table_cell_with_prose_table_prose_uses_three_element_array():
    xml = (
        '<table><tr><td>'
        '<p>before</p>'
        '<table><tr><td>inner</td></tr></table>'
        '<p>after</p>'
        '</td></tr></table>'
    )
    out = convert(xml)
    import json
    body = out.split("```merge-table\n", 1)[1].rsplit("\n```", 1)[0]
    parsed = json.loads(body)
    assert parsed == {"rows": [[{"content": ["before", {"rows": [["inner"]]}, "after"]}]]}


# --- tag-only <p> single-<a> carve-out ---


def test_tag_only_p_with_single_a_promotes_to_real_paragraph():
    # A <p> whose only direct Tag child is <a> is NOT cursor-park-unwrapped —
    # it renders as a real paragraph with full \n\n leading spacing.
    xml = '<p>TODO</p><p><a href="LINK">DISPLAY</a></p>'
    out = convert(xml)
    assert out == "TODO\n\n[DISPLAY](LINK)"


def test_p_with_inline_a_after_text_still_works():
    # Mixed-content <p> (text + <a>) is NOT tag-only — falls through to normal
    # <p> rendering. No behavior change from this fix; included as regression.
    xml = '<p>TODO<a href="LINK">DISPLAY</a></p>'
    out = convert(xml)
    assert out == "TODO[DISPLAY](LINK)"


def test_tag_only_p_with_single_a_and_decorative_br_still_promotes():
    # <br> is decorative for the tag-only check, so single-<a>+<br> still has
    # exactly one meaningful Tag child (<a>) → promotes.
    xml = '<p>TODO</p><p><a href="LINK">DISPLAY</a><br/></p>'
    out = convert(xml)
    assert out == "TODO\n\n[DISPLAY](LINK)"


def test_tag_only_p_with_two_a_children_still_unwraps_as_cursor_park():
    # Multi-link <p> stays in the standard cursor-park unwrap path — the
    # carve-out is narrow ("single direct Tag child is <a>").
    xml = '<p>before</p><p><a href="u1">X</a> <a href="u2">Y</a></p>'
    out = convert(xml)
    assert out == "before[X](u1) [Y](u2)"


def test_tag_only_p_with_strong_then_a_still_unwraps_as_cursor_park():
    # Mixed-tag <p> (strong + a) stays in the cursor-park unwrap path.
    xml = '<p>before</p><p><strong>BOLD</strong><a href="u">LINK</a></p>'
    out = convert(xml)
    assert out == "before<strong>BOLD</strong>[LINK](u)"


# --- tag-only <p> single embed-macro carve-out (extends single-<a> rule) ---


def test_tag_only_p_with_widget_macro_promotes_to_real_paragraph():
    # Mirrors the single-<a> carve-out: a <p> whose only direct Tag child is a
    # widget macro renders as a real paragraph, not cursor-park-unwrapped.
    xml = (
        '<h1><span>HEADER</span></h1>'
        '<p><ac:structured-macro ac:name="widget">'
        '<ac:parameter ac:name="url">'
        '<ri:url ri:value="https://www.youtube.com/watch?v=6htbyY3rH1w" />'
        '</ac:parameter></ac:structured-macro></p>'
    )
    out = convert(xml)
    assert out == "# HEADER\n\n![](https://www.youtube.com/watch?v=6htbyY3rH1w)"


def test_widget_inline_in_heading_stays_inline():
    # Widget INSIDE the <h1> stays inline with the heading text (regression —
    # this case already worked; new carve-out shouldn't break it).
    xml = (
        '<h1><span style="font-size: 24.0px;">HEADER</span>'
        '<ac:structured-macro ac:name="widget">'
        '<ac:parameter ac:name="url">'
        '<ri:url ri:value="https://www.youtube.com/watch?v=6htbyY3rH1w" />'
        '</ac:parameter></ac:structured-macro></h1>'
    )
    out = convert(xml)
    assert out == "# HEADER![](https://www.youtube.com/watch?v=6htbyY3rH1w)"


def test_tag_only_p_with_view_file_macro_promotes_to_real_paragraph():
    xml = (
        '<p>before</p>'
        '<p><ac:structured-macro ac:name="view-file">'
        '<ac:parameter ac:name="name">'
        '<ri:attachment ri:filename="doc.pdf" />'
        '</ac:parameter></ac:structured-macro></p>'
    )
    out = convert(xml, page_name="MyPage")
    assert out == "before\n\n![[MyPage/doc.pdf]]"


def test_tag_only_p_with_multimedia_macro_promotes_to_real_paragraph():
    xml = (
        '<p>before</p>'
        '<p><ac:structured-macro ac:name="multimedia">'
        '<ac:parameter ac:name="name">'
        '<ri:attachment ri:filename="clip.mp4" />'
        '</ac:parameter></ac:structured-macro></p>'
    )
    out = convert(xml, page_name="MyPage")
    assert out == "before\n\n![[MyPage/clip.mp4]]"


def test_tag_only_p_with_info_macro_still_cursor_park_unwraps():
    # Block-shaped macros (info / warning / expand / code etc.) already begin
    # with \n so they self-separate. Cursor-park unwrap is correct for them —
    # the carve-out must NOT extend here.
    xml = (
        '<p>before</p>'
        '<p><ac:structured-macro ac:name="info">'
        '<ac:rich-text-body><p>note</p></ac:rich-text-body>'
        '</ac:structured-macro></p>'
    )
    out = convert(xml)
    assert out == "before\n> [!info]\n> note"


def test_tag_only_p_with_two_widgets_stays_cursor_park_unwrap():
    # Multi-embed shapes (rare) stay in the cursor-park unwrap path — the
    # carve-out predicate is narrow ("single direct meaningful Tag child").
    xml = (
        '<p>before</p>'
        '<p>'
        '<ac:structured-macro ac:name="widget"><ac:parameter ac:name="url"><ri:url ri:value="u1" /></ac:parameter></ac:structured-macro>'
        '<ac:structured-macro ac:name="widget"><ac:parameter ac:name="url"><ri:url ri:value="u2" /></ac:parameter></ac:structured-macro>'
        '</p>'
    )
    out = convert(xml)
    assert out == "before![](u1)![](u2)"


def test_tag_only_p_with_latex_inline_still_cursor_park_unwraps():
    # latex-inline is explicitly excluded — $X$ shape is ambiguous (standalone
    # equation vs. cursor-parked inline math); err on cursor-park.
    xml = (
        '<p>before</p>'
        '<p><ac:structured-macro ac:name="latex-inline">'
        '<ac:plain-text-body><![CDATA[x^2]]></ac:plain-text-body>'
        '</ac:structured-macro></p>'
    )
    out = convert(xml)
    assert out == "before$x^2$"
