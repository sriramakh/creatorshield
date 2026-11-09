"""Object storage abstraction.

Keys look like S3 object keys (``analyses/<uuid>/video.mp4``) so an
S3-compatible backend can be added by implementing ``Storage`` without changing
callers. Processing code asks for a local path via ``local_path`` because
FFmpeg/Tesseract need files on disk; a remote backend would download to a temp
dir there.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import BinaryIO, Protocol

from app.config import get_settings

_KEY_RE = re.compile(r"^[A-Za-z0-9_\-./]+$")


class StorageError(Exception):
    pass


class Storage(Protocol):
    def save_stream(self, key: str, stream: BinaryIO, max_bytes: int) -> int: ...
    def local_path(self, key: str) -> Path: ...
    def exists(self, key: str) -> bool: ...
    def delete_prefix(self, prefix: str) -> None: ...


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        if not _KEY_RE.match(key) or ".." in key or key.startswith("/"):
            raise StorageError(f"invalid storage key: {key!r}")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise StorageError("storage key escapes root")
        return path

    def save_stream(self, key: str, stream: BinaryIO, max_bytes: int) -> int:
        """Copy ``stream`` to ``key``, aborting if it exceeds ``max_bytes``."""
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        tmp = path.with_suffix(path.suffix + ".part")
        try:
            with tmp.open("wb") as out:
                while chunk := stream.read(1024 * 1024):
                    written += len(chunk)
                    if written > max_bytes:
                        raise StorageError("file exceeds maximum upload size")
                    out.write(chunk)
            tmp.replace(path)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        return written

    def local_path(self, key: str) -> Path:
        return self._resolve(key)

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def delete_prefix(self, prefix: str) -> None:
        path = self._resolve(prefix.rstrip("/"))
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink()


def get_storage() -> Storage:
    return LocalStorage(get_settings().storage_dir)


def analysis_prefix(analysis_id: object) -> str:
    return f"analyses/{analysis_id}"
