# confluence-2-obsidian Context

## Glossary

### Source
Confluence Cloud or Server instance, accessed via REST API.

### Sink
Obsidian vault — a local directory of Markdown files.

## Decisions

- **Data source**: Confluence Server REST API (self-hosted, v7.13.0, https://confluence.lan/)
- **API base**: `https://confluence.lan/rest/api/`
- **Auth**: Basic Auth (username + password in config/env)
- **Scope**: specific spaces, identified by space key, passed as CLI arguments
- **Content types**: pages and attachments only (no blog posts, no comments)
- **Vault structure**: mirrors Confluence page tree at full depth — each ancestor page becomes a directory; the leaf page is a `.md` file; ancestor pages with children exist as both a directory and a `.md` file at that level (e.g., `PROJ/Architecture/Backend/Services.md` alongside `PROJ/Architecture/Backend/Services/Auth Service.md`)
- **Language**: Python
- **HTML-to-Markdown**: custom recursive parser using BeautifulSoup; walks the Confluence XML tree in one pass, handling standard HTML elements and `ac:` macros together
- **Block spacing**: tight packing — no blank lines between block-level elements (headings, code blocks, lists, callouts, dataview blocks, tables, etc.). Two exceptions: (1) consecutive paragraphs are separated by a blank line (Markdown requires it), and (2) `^excerpt` block anchor is always followed by a blank line. A `<p>` containing only a structured-macro is unwrapped (the macro renders as its own block, no paragraph spacing)
- **Hard line breaks**: `<br/>` outside HTML contexts → backslash hard break (`\` at end of line); `<br/>` inside raw HTML (e.g., within a color span) needs no special handling
- **Inline HTML preserved**: `<sub>` and `<sup>` are emitted as raw HTML (`<sub>2</sub>`, `<sup>2</sup>`) — Markdown has no native equivalent and Obsidian renders them in reading view. Same approach as the existing `<u>` handling.
- **Macro: Children Display** → inserted only when the Confluence page explicitly contains the macro; renders as a Dataview LIST block. Two forms:
  - **No `page` parameter**: scoped to this page's children — `WHERE file.folder = this.file.folder + "/" + this.file.name`
  - **With `page` parameter** (e.g., `<ri:page ri:content-title="Computer"/>`): scoped to the referenced page's children — `WHERE file.folder = [[Computer]].file.folder + "/" + [[Computer]].file.name`. The wiki-link uses the sanitized/collision-resolved title (same resolver as internal page links). If the referenced page is not in the migrated title map, the macro is dropped and a broken-reference entry is added to `migration-report.md`.
- **Heading levels**: `<h1>` → `#`, `<h2>` → `##`, `<h3>` → `###`; `<h4>`, `<h5>`, `<h6>` all clamp to `######` (the deepest Markdown heading)
- **Macro: Excerpt** → rendered Markdown body wrapped in a fenced `` ```excerpt `` code block followed immediately by a `^excerpt` block anchor on the next line; rendered by a custom Obsidian plugin
- **Macro: Include Excerpt** → `![[Page Title#^excerpt]]` Obsidian block transclusion; page title extracted from `ac:parameter[ac:name=""]` → `ri:page[@ri:content-title]`; `nopanel` parameter ignored
- **Macro: `latex-inline`** → `$<CDATA>$` (Obsidian inline math)
- **Macro: `latex-block`** → `$$<CDATA>$$` (Obsidian block math)
- **Macro: `code`** → fenced code block with language from `ac:parameter[language]`
- **Macro: `info`** → `> [!info]` callout wrapping the body content
- **Macro: `warning`** → `> [!warning]` callout wrapping the body content
- **Macro: `expand`** / **`ui-expand`** → if `title` parameter present, HTML `<details><summary>TITLE</summary>\n\nbody\n\n</details>` (renders as collapsible in Obsidian reading view); if no title, body content from `ac:rich-text-body` rendered inline with no wrapper
- **Macro: `anchor`** → silently dropped (Obsidian has no equivalent free-floating anchor; not logged as unknown)
- **Macro: `toc`** → silently dropped (Obsidian's built-in Outline pane renders the heading tree natively)
- **Macro: `view-file`** / **`viewpdf`** / **`multimedia`** → `![[PageName/filename]]` where filename comes from the embedded `ri:attachment`; the attachment is downloaded into the per-page subfolder (same flow as inline images); Obsidian renders PDFs, video, and audio inline natively in reading view
- **Macro: `ui-tabs`** → emits nothing itself; children render sequentially in document order
- **Macro: `ui-tab`** → HTML `<details><summary>TAB TITLE</summary>\n\nbody\n\n</details>` using the `title` parameter; horizontal layout and mutual-exclusivity of Confluence tabs is lost (stacked collapsibles instead)
- **Macro: `widget`** → `![](url)` Media Extended embed; URL extracted from `ac:parameter[ac:name="url"]` → `ri:url[@ri:value]`; used in practice only for YouTube embeds
- **Macro: `section`** → entire macro and body dropped (no output, not logged as unknown); used for multi-column layouts that have no Markdown equivalent
- **Macro: `details`** → entire macro and body dropped (no output, not logged as unknown); Confluence Page Properties metadata has no Markdown equivalent
- **Macro: `pagetree`** / **`pagetreesearch`** / **`livesearch`** → silently dropped; Obsidian's file explorer and global search cover these natively
- **Macro: `recently-updated`** → Dataview query `LIST FROM "" SORT modified DESC LIMIT <max>` where `<max>` comes from the `max` parameter (default `15`); sorts by the `modified` frontmatter field (Confluence-recorded timestamp); `spaces`, `types`, and `theme` parameters are ignored
- **Internal page link** → `[[Page Title|Display Text]]` Obsidian wiki link (page titles are unique across the instance)
- **External URL link** → `[Display Text](url)` standard Markdown link
- **YouTube embed** (`<ri:url>`) → `![](url)` Media Extended plugin syntax
- **Attachments**: downloaded into per-page subfolder `<Space>/<Parent>/<PageName>/<filename>`, referenced as `![[PageName/filename]]`; inline images embedded in page body (`<ac:image><ri:attachment>`) are treated identically — downloaded to the same subfolder and emitted as `![[PageName/filename]]` at the point of the image
- **Unknown macros**: logged and skipped; a `migration-report.md` written to vault root with macro name, page, and count
- **Tables**: simple tables (no `colspan`/`rowspan`) → Markdown pipe tables; tables with merged cells → raw HTML `<table>` block (Obsidian renders it in reading view)
- **Filename sanitization**: invalid filesystem characters (`:`, `/`, `?`, `*`, `<`, `>`, `|`, `\`) in page titles are replaced with a space when used as file or directory names; any title that required sanitization is logged; post-sanitization collisions are resolved by suffixing the Confluence page ID (e.g., `Design  v2 (12345).md`) and logged prominently in `migration-report.md`
- **Migration mode**: one-time (no incremental sync)
- **Checkpoint/resume**: after each successfully migrated page, the page's Confluence ID is added to `.migration-checkpoint.json` at vault root; on restart the script fetches the full page list and skips any page whose ID is already in the checkpoint; Ctrl+C triggers a graceful stop that writes `migration-report.md` and flushes the checkpoint before exiting
- **migration-report.md**: written to vault root on graceful stop, crash, or completion; contains all unknown macros encountered (macro name, page title, count) and all per-page failures (page title, error reason); failed pages are not checkpointed and will be retried on the next run
- **Frontmatter**: title, created, modified, author, confluence_url, labels (as Obsidian tags)
- **Config**: `.env` file (`CONFLUENCE_URL`, `CONFLUENCE_USER`, `CONFLUENCE_PASS`, `VAULT_PATH`, `CONFLUENCE_VERIFY_SSL`, `DOWNLOAD_ATTACHMENTS`); space keys passed as CLI args
- **Progress display**: each page migration prints `[<n>/<total>] <Page Title>` to stdout
- **SSL**: verification skipped (`verify=False`), warnings suppressed; controlled by `CONFLUENCE_VERIFY_SSL` env var
- **Attachment download**: controlled by `DOWNLOAD_ATTACHMENTS` env var (default `true`); when `false`, attachments are skipped and attachment references are emitted as broken wiki-links (e.g., `![[PageName/diagram.png]]`)
