from pathlib import Path

from src.sanitize import sanitize_title


class PathResolver:
    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.taken: dict[Path, str] = {}
        self.title_map: dict[str, str] = {}
        self.collisions: list[tuple[str, str, str]] = []

    def resolve(self, page: dict) -> tuple[Path, str]:
        space_key = page.get("space", {}).get("key", "")
        ancestors = page.get("ancestors", []) or []
        title = page.get("title", "")
        page_id = str(page.get("id", ""))

        parts = [space_key]
        for ancestor in ancestors:
            parts.append(sanitize_title(ancestor.get("title", "")))
        sanitized_title = sanitize_title(title)
        directory = self.vault_path.joinpath(*parts) if parts else self.vault_path
        candidate = directory / f"{sanitized_title}.md"
        basename = sanitized_title

        if candidate in self.taken and self.taken[candidate] != page_id:
            basename = f"{sanitized_title} ({page_id})"
            candidate = directory / f"{basename}.md"
            self.collisions.append((title, page_id, candidate.name))

        self.taken[candidate] = page_id
        self.title_map[title] = basename
        return candidate, basename
