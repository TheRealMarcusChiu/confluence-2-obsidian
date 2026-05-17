def _yaml_quote(s: str) -> str:
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def build_frontmatter(
    page: dict,
    confluence_base_url: str,
    parent: str | None = None,
    children: list[str] | None = None,
) -> str:
    history = page.get("history", {})
    version = page.get("version", {})
    created = history.get("createdDate", "")
    modified = version.get("when", "")

    labels_data = page.get("metadata", {}).get("labels", {}).get("results", [])
    labels = []
    for entry in labels_data:
        name = entry.get("name") or entry.get("label")
        if name:
            labels.append(name)

    lines = ["---"]
    if created:
        lines.append(f"created: {created}")
    if modified:
        lines.append(f"modified: {modified}")
    if labels:
        lines.append("tags:")
        for label in labels:
            lines.append(f"  - {label}")
    if parent:
        lines.append(f"parent: {_yaml_quote(f'[[{parent}]]')}")
    if children:
        lines.append("children:")
        for child in children:
            lines.append(f"  - {_yaml_quote(f'[[{child}]]')}")
    else:
        lines.append("children: []")
    lines.append("---")
    return "\n".join(lines) + "\n"
