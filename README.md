---
parent:
  - "[[confluence-2-obsidian]]"
---
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

- Each page → `.md` file with YAML frontmatter: `created`, `modified`, `labels` (as Obsidian tags), `parent` (wiki-link to the parent page, omitted on roots), `children` (list of wiki-links to direct children, `[]` on leaves).
- Every page exists as both a `.md` file and a same-named directory at the same level (the directory holds child pages and per-page attachments).
- Attachment **embeds** — inline images, `view-file` / `viewpdf` / `multimedia` macros — reference `![[PageName/file]]`. The per-page subfolder prefix matches the on-disk path so the embed resolves directly to the file owned by the page.
- Attachment **links** — `<ac:link>` pointing to an attachment — reference `[[file]]`. No prefix; Obsidian resolves wiki-links by name across the whole vault.
- Filenames containing characters illegal on disk (`: / ? * < > | \`) get their fullwidth Unicode equivalents (`：／？＊＜＞｜＼`) — lossless and visually identical. Post-sanitization title collisions are resolved by suffixing the Confluence page ID and logged.
- `migration-report.md` lists unknown macros, collisions, page failures, and warnings.

## Supported macros

| Confluence macro | Obsidian output |
| --- | --- |
| `code` | Fenced code block with language |
| `latex-inline` / `latex` | `$…$` |
| `latex-block` | `$…$\n` (rendered as inline math — not Obsidian block math `$$…$$` — with a trailing `\n` so consecutive `latex-block` macros land on separate lines). Every occurrence is logged so the operator can verify the equation renders correctly. |
| `excerpt` | 4-backtick fenced ` ````excerpt ` block with `^excerpt` anchor on the next line (rendered by a custom Obsidian plugin). 4 backticks so the body's own 3-backtick code blocks don't terminate the outer fence. |
| `excerpt-include` | `![[Page#^excerpt]]` block transclusion |
| `children` / `children-display` | Dataview LIST query scoped to the page's (or referenced page's) children. Wrapped in `> [!list-indent-undo]` / `> [!indent]` callouts when inside a list, so the dataview aligns flush with the surrounding bullets. |
| `info` | `> [!info]` callout (body renders through the full Markdown converter — nested lists, code blocks, callouts, etc. all work) |
| `warning` | `> [!warning]` callout |
| `expand` / `ui-expand` | Native foldable Obsidian callout: `> [!expand]- Title` (or `> [!expand-ui]- Title` for `ui-expand`) with body on subsequent `> `-prefixed lines. Default title `Click here to expand...` when absent. Empty body becomes `> TODO` placeholder. Visual differentiation between `expand` and `expand-ui` requires custom CSS on `[data-callout="expand"]` / `[data-callout="expand-ui"]`. |
| `ui-tabs` / `ui-tab` | `> [!tabs]` callout with `> === TITLE` separators per tab. Bodies render as full Markdown (lists, code blocks, callouts, nested expands all work inside a tab). Rendered as horizontal tabs by a custom Obsidian plugin maintained alongside this codebase. |
| `widget` | `![](url)` Media Extended embed (used in practice only for YouTube) |
| `view-file` / `viewpdf` / `multimedia` | `![[PageName/filename]]` attachment embed. When the macro carries a `<ac:parameter ac:name="page">` pointing to another page, the subfolder is the referenced page's title instead of the current page. |
| `recently-updated` | Dataview query sorted by `modified` frontmatter |

Silently dropped (no output, not logged): `anchor`, `toc`, `pagetree`, `pagetreesearch`, `livesearch`, `section`, `details`.

Any other macro is logged in `migration-report.md` and skipped.

### Tables

Tables are emitted as ` ```merge-table ` fenced JSON blocks rendered by the **Merge Table** Obsidian plugin (maintained alongside this codebase). The plugin renders Markdown natively inside cells — bold, italic, code blocks, lists, callouts, wiki-links, images, nested tables all work — so cell content goes through the same Markdown converter as document-level content.

````
```merge-table
{
  "rows": [
    [
      { "content": "Header", "header": true, "bg": "#F4F5F7" },
      { "content": "Other",  "header": true, "bg": "#F4F5F7" }
    ],
    [ "cell text", "more text" ]
  ]
}
```
````

Cell-level keys: `content` (string Markdown, nested table object `{rows: …}`, or array of interleaved strings/tables), `header` (bold + centred), `bg`/`color`, `align` (`left`/`center`/`right`), `valign` (`top`/`middle`/`bottom`), `colspan`, `rowspan`. Confluence's `data-highlight-colour` and inline `style="background-color:"` map to `bg`; `style="text-align:"` / `style="vertical-align:"` map to `align`/`valign` (filtered to supported values). `<th>` becomes `header: true` plus auto `bg: "#F4F5F7"`. Unsupported per-cell styles (`width`, `padding`, `font-family`, `border`, etc.) are dropped — merge-table has no per-cell CSS escape hatch and Obsidian renders tables responsively.

### Lists

Multi-paragraph list items render as CommonMark loose-list items — subsequent paragraphs are indented to the marker's text column with blank-with-indent separator lines. Headings count as paragraph-like (a heading inside an `<li>` becomes the marker line, followed by indented paragraph bodies). Nested lists get the same continuation indent at every depth. Multi-line block siblings (callouts, code macros, tables) hoist to column 0 to preserve source-order interleaving with paragraph siblings.

## Recommended Obsidian plugins

- **Dataview** (required) — needed for `children-display` and `recently-updated` query blocks.
- **Merge Table** (required) — renders the ` ```merge-table ` JSON blocks emitted for every Confluence table. Maintained alongside this codebase.
- **Excerpt plugin** (required) — renders the ` ````excerpt ` fenced blocks. Maintained alongside this codebase.
- **Tabs plugin** (required if pages use Confluence `ui-tabs`) — renders `> [!tabs]` callouts with `=== TITLE` separators as horizontal tabs. Maintained alongside this codebase (replaces the previous dependency on `ycnmhd/obsidian-tabs`).
- **Media Extended** — required only if pages have YouTube embeds (`widget` / `<ri:url>` images).
- **Folder Notes** (required for the intended UX) — every page is emitted as both a `.md` file and a same-named folder; this plugin treats the `.md` as the folder's index so the doubled entries collapse into one navigable item in the explorer.
- **Font color / Colored Text** — required only if your Confluence pages use coloured text. `<span style="color:…">` becomes `<font style="color:…">` which the font-color plugin renders. Dark-gray colours (`max(R,G,B) ≤ 88` in `rgb()` form — near-default text tints from Confluence's editor toggling colour and untoggling) drop the `<font>` wrapper since they're indistinguishable from default text.
- **Custom callout CSS** (required for the intended UX) — these callout types need custom CSS on `[data-callout="…"]` to render distinctively (without it they all render as plain "note" callouts):
  - `[data-callout="expand"]` / `[data-callout="expand-ui"]` — visual differentiation between `expand` and `ui-expand` macros.
  - `[data-callout="list-indent-undo"]` / `[data-callout="indent"]` — align `children-display` dataview blocks and inline images flush with surrounding list bullets.
  - `[data-callout="indent"]` — also used for paragraph-level indentation (from Confluence's editor `margin-left: Npx` toolbar indents).

Callouts, LaTeX math, wiki-links, and PDF/audio/video embeds are handled by Obsidian core — no plugin needed.

## Tests

```sh
.venv/bin/python -m pytest
```

## Design

See [`CONTEXT.md`](CONTEXT.md) for the full set of decisions behind the implementation.
