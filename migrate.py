import argparse
import os
import sys
import traceback
from pathlib import Path

from dotenv import load_dotenv

from src.checkpoint import Checkpoint
from src.confluence_client import ConfluenceClient
from src.converter import Converter
from src.frontmatter import build_frontmatter
from src.paths import PathResolver
from src.report import MigrationReport


def env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"Missing required env var: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def parse_args():
    p = argparse.ArgumentParser(description="Migrate Confluence pages to an Obsidian vault.")
    p.add_argument("space_keys", nargs="+", help="Confluence space keys to migrate (one or more).")
    return p.parse_args()


def migrate_page(
    page: dict,
    file_path: Path,
    basename: str,
    client: ConfluenceClient,
    resolver: PathResolver,
    report: MigrationReport,
    confluence_url: str,
    download_attachments: bool,
):
    page_id = str(page.get("id", ""))
    title = page.get("title", "")
    storage = page.get("body", {}).get("storage", {}).get("value", "") or ""

    converter = Converter(basename, title_map=resolver.title_map)
    markdown = converter.convert(storage)
    frontmatter = build_frontmatter(page, confluence_url)

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(frontmatter + markdown, encoding="utf-8")
    (file_path.parent / basename).mkdir(exist_ok=True)

    report.record_unknown_macros(title, converter.unknown_macros)
    report.record_warnings(converter.warnings)

    if not download_attachments:
        return

    attachment_dir = file_path.parent / basename
    for attachment in client.list_attachments(page_id):
        filename = attachment.get("title") or ""
        if not filename:
            continue
        try:
            content = client.download_attachment(attachment)
        except Exception as e:
            report.record_failure(f"{title} :: {filename}", f"attachment download: {e}")
            continue
        attachment_dir.mkdir(parents=True, exist_ok=True)
        (attachment_dir / filename).write_bytes(content)


def main():
    load_dotenv()
    args = parse_args()

    confluence_url = require_env("CONFLUENCE_URL")
    user = require_env("CONFLUENCE_USER")
    password = require_env("CONFLUENCE_PASS")
    vault_path = Path(require_env("VAULT_PATH")).expanduser().resolve()
    verify_ssl = env_bool("CONFLUENCE_VERIFY_SSL", default=False)
    download_attachments = env_bool("DOWNLOAD_ATTACHMENTS", default=True)

    vault_path.mkdir(parents=True, exist_ok=True)

    client = ConfluenceClient(confluence_url, user, password, verify_ssl=verify_ssl)
    checkpoint = Checkpoint(vault_path)
    report = MigrationReport()
    resolver = PathResolver(vault_path)

    print(f"Fetching page metadata from {len(args.space_keys)} space(s): {', '.join(args.space_keys)}")
    resolved: list[tuple[dict, Path, str]] = []
    for space_key in args.space_keys:
        for page in client.list_pages(space_key):
            file_path, basename = resolver.resolve(page)
            resolved.append((page, file_path, basename))

    total = len(resolved)
    print(f"Total pages: {total}")

    for title, page_id, name in resolver.collisions:
        report.record_collision(title, page_id, name)

    exit_code = 0
    try:
        for index, (page, file_path, basename) in enumerate(resolved, 1):
            page_id = str(page.get("id", ""))
            title = page.get("title", "")

            if checkpoint.is_done(page_id):
                continue

            print(f"[{index}/{total}] {title}")
            try:
                migrate_page(
                    page,
                    file_path,
                    basename,
                    client,
                    resolver,
                    report,
                    confluence_url,
                    download_attachments,
                )
                report.pages_migrated += 1
                checkpoint.mark_done(page_id)
            except Exception as e:
                report.record_failure(title, f"{type(e).__name__}: {e}")
                print(f"  FAILED: {e}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nGraceful stop requested.", file=sys.stderr)
        exit_code = 130
    except Exception as e:
        print(f"\nFatal error: {e}", file=sys.stderr)
        traceback.print_exc()
        report.record_failure("<orchestrator>", f"{type(e).__name__}: {e}")
        exit_code = 1
    finally:
        report.write(vault_path)
        checkpoint.flush()
        print(f"Report written to {vault_path / 'migration-report.md'}")
        print(f"Pages migrated: {report.pages_migrated}/{total}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
