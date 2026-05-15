# confluence-2-obsidian

One-shot migrator that pulls pages from a Confluence Server REST API and writes them as Markdown into an Obsidian vault, mirroring the page tree.

## Install

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Configure

Create a `.env` file in the repo root:

```env
CONFLUENCE_URL=https://confluence.example.com
CONFLUENCE_USER=your-username
CONFLUENCE_PASS=your-password
VAULT_PATH=~/Obsidian/MyVault
CONFLUENCE_VERIFY_SSL=false
DOWNLOAD_ATTACHMENTS=true
```

| Variable | Description | Default |
| --- | --- | --- |
| `CONFLUENCE_URL` | Base URL of the Confluence instance | — |
| `CONFLUENCE_USER` | Username for Basic Auth | — |
| `CONFLUENCE_PASS` | Password for Basic Auth | — |
| `VAULT_PATH` | Local Obsidian vault directory | — |
| `CONFLUENCE_VERIFY_SSL` | Verify SSL certificates | `false` |
| `DOWNLOAD_ATTACHMENTS` | Download page attachments | `true` |

Space keys are passed as CLI arguments, not env vars.

## Run

Pass one or more Confluence space keys:

```sh
.venv/bin/python migrate.py SPACEKEY1 SPACEKEY2
```

Progress prints `[n/total] Page Title`. Migration is one-shot — Ctrl+C aborts the run, and the next invocation re-fetches and re-writes every page from scratch.

## Output

```
<VAULT_PATH>/
├── SPACEKEY/
│   ├── Parent Page.md
│   └── Parent Page/
│       ├── Child Page.md
│       └── Child Page/
│           └── attachment.png
└── migration-report.md
```

- Each page → `.md` file with YAML frontmatter (title, created, modified, author, confluence_url, labels as tags).
- Every page exists as both a `.md` file and a same-named directory at the same level (the directory holds child pages and per-page attachments).
- Attachments and inline images live in the per-page subfolder; referenced as `![[PageName/file]]`.
- Filenames containing characters illegal on disk (`: / ? * < > | \`) get their fullwidth Unicode equivalents (`：／？＊＜＞｜＼`) — lossless and visually identical. Post-sanitization title collisions are resolved by suffixing the Confluence page ID and logged.
- `migration-report.md` lists unknown macros, collisions, page failures, and warnings.

## Supported macros

| Confluence macro | Obsidian output |
| --- | --- |
| `code` | Fenced code block with language |
| `latex-inline` / `latex` | `$…$` |
| `latex-block` | `$$…$$` |
| `excerpt` | Fenced `` ```excerpt `` code block with `^excerpt` anchor (rendered by a custom Obsidian plugin) |
| `excerpt-include` | `![[Page#^excerpt]]` block transclusion |
| `children` / `children-display` | Dataview query listing direct children |
| `info` | `> [!info]` callout |
| `warning` | `> [!warning]` callout |
| `expand` / `ui-expand` | `<details><summary>title</summary>body</details>`. `expand` with no title defaults to `Click here to expand...`. Inside table cells, rendered as a single-line inline `<details>`. |
| `ui-tabs` / `ui-tab` | `~~~tabs / ---tab TITLE / body / ~~~` block for the Obsidian Tabs plugin. Bodies render as full Markdown (lists, code blocks, callouts, nested expands all work inside a tab). |
| `widget` | `![](url)` Media Extended embed (used for YouTube) |
| `view-file` / `viewpdf` / `multimedia` | `![[PageName/filename]]` attachment embed |
| `recently-updated` | Dataview query sorted by `modified` frontmatter |

Silently dropped (no output, not logged): `anchor`, `toc`, `pagetree`, `pagetreesearch`, `livesearch`, `section`, `details`.

Any other macro is logged in `migration-report.md` and skipped.

### Tables

Tables are emitted as cleaned, prettified raw HTML (not Markdown pipe tables — Obsidian doesn't render Markdown inside `<table>`). Cell-highlight colours (`data-highlight-colour`) are merged into `style` as `background-color`; `<th>` cells without explicit styling get Confluence's default `#F4F5F7` tint. Inside a cell, most `ac:*` macros are escaped as visible source XML — a manual-cleanup signal — with exceptions for `ac:link` (plain text), `ac:image` (→ `<img src="…">`), and `expand`/`ui-expand` (→ inline `<details>`).

## Recommended Obsidian plugins

- **Dataview** (required) — needed for `children-display` and `recently-updated` query blocks.
- **Tabs** ([ycnmhd/obsidian-tabs](https://github.com/ycnmhd/obsidian-tabs), required if pages use Confluence `ui-tabs`) — renders the `~~~tabs` blocks as actual horizontal tabs; without it they fall back to a literal fenced code block.
- **Media Extended** — required only if pages have YouTube embeds (`widget` / `<ri:url>` images).
- **Folder Notes** (required for the intended UX) — every page is emitted as both a `.md` file and a same-named folder; this plugin treats the `.md` as the folder's index so the doubled entries collapse into one navigable item in the explorer.
- **Font color / Colored Text** — only if your Confluence pages use coloured text; `<span style="color:…">` is preserved as `<font style="color:…">`, which the font-color plugin renders. Without it, the colour is ignored but the text still shows.

Callouts, `<details>`, LaTeX math, wiki-links, raw HTML tables, and PDF/audio/video embeds are handled by Obsidian core — no plugin needed.

## Tests

```sh
.venv/bin/python -m pytest
```

## Design

See [`CONTEXT.md`](CONTEXT.md) for the full set of decisions behind the implementation.
