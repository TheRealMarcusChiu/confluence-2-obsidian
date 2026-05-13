# confluence-2-obsidian

One-shot migrator that pulls pages from a Confluence Server REST API and writes them as Markdown into an Obsidian vault, mirroring the page tree.

## Install

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Configure

Copy `.env.example` to `.env` and fill in your values:

```sh
cp .env.example .env
```

| Variable | Description | Default |
| --- | --- | --- |
| `CONFLUENCE_URL` | Base URL of the Confluence instance | — |
| `CONFLUENCE_USER` | Username for Basic Auth | — |
| `CONFLUENCE_PASS` | Password for Basic Auth | — |
| `VAULT_PATH` | Local Obsidian vault directory | — |
| `CONFLUENCE_VERIFY_SSL` | Verify SSL certificates | `false` |
| `DOWNLOAD_ATTACHMENTS` | Download page attachments | `true` |

## Run

Pass one or more Confluence space keys:

```sh
.venv/bin/python migrate.py SPACEKEY1 SPACEKEY2
```

Progress prints `[n/total] Page Title`. Press Ctrl+C at any time — the run is checkpointed after each successful page, so the next invocation resumes where it left off.

## Output

```
<VAULT_PATH>/
├── SPACEKEY/
│   └── Parent Page/
│       ├── Child Page.md
│       └── Child Page/
│           └── attachment.png
├── .migration-checkpoint.json
└── migration-report.md
```

- Each page → `.md` file with YAML frontmatter (title, created, modified, author, confluence_url, labels as tags).
- Parent pages with children exist as both a directory and a `.md` file at the same level.
- Attachments and inline images live in a per-page subfolder; referenced as `![[PageName/file]]`.
- `migration-report.md` lists unknown macros, sanitized titles, collisions, page failures, and warnings.

## Supported macros

| Confluence macro | Obsidian output |
| --- | --- |
| `code` | Fenced code block with language |
| `latex-inline` | `$…$` |
| `latex-block` | `$$…$$` |
| `excerpt` | `> [!quote]` callout with `^excerpt` anchor |
| `excerpt-include` | `![[Page#^excerpt]]` block transclusion |
| `children` / `children-display` | Dataview query listing direct children |

Unknown macros are logged in `migration-report.md` and skipped.

## Tests

```sh
.venv/bin/python -m pytest
```

## Design

See [`CONTEXT.md`](CONTEXT.md) for the full set of decisions behind the implementation.
