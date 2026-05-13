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
- **Hard line breaks**: `<br/>` outside HTML contexts → backslash hard break (`\` at end of line); `<br/>` inside raw HTML (e.g., within a color span) needs no special handling
- **Macro: Children Display** → inserted only when the Confluence page explicitly contains the macro; renders as a Dataview query block with `WHERE file.folder = this.file.folder + "/" + this.file.name` (dynamic, direct children only)
- **Heading levels**: all body headings shifted down one level (`<h1>` → `##`, `<h2>` → `###`, etc.); `<h6>` → `#######` is logged as a warning since Obsidian doesn't render it as a heading
- **Macro: Excerpt** → content wrapped in a `> [!quote]` callout block with `^excerpt` anchor appended; handles multi-block content as a single transcludable unit
- **Macro: Include Excerpt** → `![[Page Title#^excerpt]]` Obsidian block transclusion; page title extracted from `ac:parameter[ac:name=""]` → `ri:page[@ri:content-title]`; `nopanel` parameter ignored
- **Macro: `latex-inline`** → `$<CDATA>$` (Obsidian inline math)
- **Macro: `latex-block`** → `$$<CDATA>$$` (Obsidian block math)
- **Macro: `code`** → fenced code block with language from `ac:parameter[language]`
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
