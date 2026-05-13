from collections import Counter
from pathlib import Path


REPORT_FILENAME = "migration-report.md"


class MigrationReport:
    def __init__(self):
        self.unknown_macros: Counter = Counter()
        self.unknown_macro_pages: dict[str, set[str]] = {}
        self.sanitized_titles: list[tuple[str, str]] = []
        self.title_collisions: list[tuple[str, str, str]] = []
        self.page_failures: list[tuple[str, str]] = []
        self.warnings: list[str] = []
        self.pages_migrated: int = 0

    def record_unknown_macros(self, page_title: str, macro_names: list[str]):
        for name in macro_names:
            self.unknown_macros[name] += 1
            self.unknown_macro_pages.setdefault(name, set()).add(page_title)

    def record_sanitization(self, original: str, sanitized: str):
        self.sanitized_titles.append((original, sanitized))

    def record_collision(self, title: str, page_id: str, resolved_name: str):
        self.title_collisions.append((title, page_id, resolved_name))

    def record_failure(self, page_title: str, error: str):
        self.page_failures.append((page_title, error))

    def record_warnings(self, warnings: list[str]):
        self.warnings.extend(warnings)

    def write(self, vault_path: Path):
        lines = ["# Migration Report", ""]
        lines.append(f"Pages migrated: {self.pages_migrated}")
        lines.append("")

        lines.append("## Unknown Macros")
        if not self.unknown_macros:
            lines.append("None.")
        else:
            lines.append("| Macro | Count | Pages |")
            lines.append("| --- | --- | --- |")
            for macro, count in sorted(self.unknown_macros.items(), key=lambda x: -x[1]):
                pages = ", ".join(sorted(self.unknown_macro_pages.get(macro, set()))[:5])
                more = len(self.unknown_macro_pages.get(macro, set())) - 5
                if more > 0:
                    pages += f", ... (+{more} more)"
                lines.append(f"| `{macro}` | {count} | {pages} |")
        lines.append("")

        lines.append("## Title Collisions (resolved with page ID suffix)")
        if not self.title_collisions:
            lines.append("None.")
        else:
            lines.append("| Original Title | Page ID | Resolved Filename |")
            lines.append("| --- | --- | --- |")
            for title, pid, resolved in self.title_collisions:
                lines.append(f"| {title} | {pid} | {resolved} |")
        lines.append("")

        lines.append("## Sanitized Titles")
        if not self.sanitized_titles:
            lines.append("None.")
        else:
            lines.append("| Original | Sanitized |")
            lines.append("| --- | --- |")
            for orig, san in self.sanitized_titles:
                lines.append(f"| {orig} | {san} |")
        lines.append("")

        lines.append("## Page Failures")
        if not self.page_failures:
            lines.append("None.")
        else:
            lines.append("| Page | Error |")
            lines.append("| --- | --- |")
            for title, err in self.page_failures:
                err_oneline = err.replace('\n', ' ').replace('|', '\\|')
                lines.append(f"| {title} | {err_oneline} |")
        lines.append("")

        lines.append("## Warnings")
        if not self.warnings:
            lines.append("None.")
        else:
            for w in self.warnings:
                lines.append(f"- {w}")
        lines.append("")

        vault_path.mkdir(parents=True, exist_ok=True)
        (vault_path / REPORT_FILENAME).write_text("\n".join(lines), encoding="utf-8")
