import json
from pathlib import Path


CHECKPOINT_FILENAME = ".migration-checkpoint.json"


class Checkpoint:
    def __init__(self, vault_path: Path):
        self.path = vault_path / CHECKPOINT_FILENAME
        self.completed: set[str] = set()
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.completed = set(str(x) for x in data.get("completed", []))
            except (json.JSONDecodeError, OSError):
                self.completed = set()

    def is_done(self, page_id: str) -> bool:
        return str(page_id) in self.completed

    def mark_done(self, page_id: str):
        self.completed.add(str(page_id))
        self.flush()

    def flush(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"completed": sorted(self.completed)}, indent=2),
            encoding="utf-8",
        )
