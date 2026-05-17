from urllib.parse import urljoin


def _yaml_quote(s: str) -> str:
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def build_frontmatter(
    page: dict,
    confluence_base_url: str,
    parent: str | None = None,
    children: list[str] | None = None,
) -> str:
    title = page.get("title", "")
    history = page.get("history", {})
    version = page.get("version", {})
    created = history.get("createdDate", "")
    modified = version.get("when", "")
    author = (
        history.get("createdBy", {}).get("displayName", "")
        or version.get("by", {}).get("displayName", "")
    )

    webui = page.get("_links", {}).get("webui", "")
    full_url = urljoin(confluence_base_url.rstrip('/') + '/', webui.lstrip('/')) if webui else ""

    labels_data = page.get("metadata", {}).get("labels", {}).get("results", [])
    labels = []
    for entry in labels_data:
        name = entry.get("name") or entry.get("label")
        if name:
            labels.append(name)

    lines = ["---"]
    lines.append(f"title: {_yaml_quote(title)}")
    if created:
        lines.append(f"created: {created}")
    if modified:
        lines.append(f"modified: {modified}")
    if author:
        lines.append(f"author: {_yaml_quote(author)}")
    if full_url:
        lines.append(f"confluence_url: {full_url}")
    if labels:
        lines.append("tags:")
        for label in labels:
            lines.append(f"  - {label}")
    if parent:
        lines.append(f"parent: {_yaml_quote(parent)}")
    if children:
        lines.append("children:")
        for child in children:
            lines.append(f"  - {_yaml_quote(child)}")
    else:
        lines.append("children: []")
    lines.append("---")
    return "\n".join(lines) + "\n"
