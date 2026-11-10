"""Raw snapshots on disk under data/raw/<source>/<sha256>.json (git-ignored)."""

from __future__ import annotations

from pathlib import Path


class FileRawStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def put(self, source_slug: str, digest: str, content: bytes) -> str:
        relative = Path(source_slug) / f"{digest}.json"
        target = self.root / relative
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        return relative.as_posix()

    def get(self, path: str) -> bytes:
        return (self.root / path).read_bytes()
