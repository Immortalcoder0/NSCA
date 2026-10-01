"""Content-addressed artifact filesystem — TECH-STACK.md §5, backend-02 §4.1.

    artifacts/<sha256[:2]>/<sha256[2:4]>/<sha256>

Write-once, `0400` (owner read-only, no write, no execute) at receipt —
matching DM-1 ("an artifact is never modified after receipt") at the
storage layer rather than only in application code.

Windows note: NTFS has no POSIX permission-bit concept identical to `0400`.
`os.chmod` on Windows only understands the read-only *attribute* bit (it
clears/sets `stat.S_IWRITE`; group/other bits and the distinction between
"owner can't write" vs "nobody can write" don't exist). We call
`os.chmod(path, stat.S_IREAD)` on every platform: on POSIX this is exactly
`0400`; on Windows it sets the file's read-only attribute, which is the
closest available equivalent and does at least prevent accidental
in-place modification through normal file APIs — it is not a full
substitute for POSIX permission enforcement. This limitation is called out
here so it isn't silently assumed to be equivalent.
"""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    sha256: str
    path: Path
    size_bytes: int
    already_existed: bool


class ArtifactAlreadyExistsError(Exception):
    """Raised only if content at the target path exists but does not match
    the hash being written — i.e. filesystem corruption, not a normal
    dedup hit (a normal dedup hit is not an error, per TECH-STACK.md §5:
    "Content addressing gives deduplication ... for free")."""


def _root_from_env() -> Path:
    return Path(os.environ.get("NSCA_ARTIFACT_ROOT", "artifacts"))


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def path_for_hash(sha256: str, root: Path | None = None) -> Path:
    root = root if root is not None else _root_from_env()
    return root / sha256[:2] / sha256[2:4] / sha256


def store(data: bytes, root: Path | None = None) -> StoredArtifact:
    """Writes `data` to its content-addressed path if not already present.

    Idempotent: uploading identical bytes twice (e.g. re-collection that
    happens to match, or a duplicate upload) is a dedup hit, not an error —
    the artifact DB row is still created fresh per receipt event (custody
    is per-receipt, not per-blob), but the bytes are stored once.
    """

    sha256 = content_hash(data)
    dest = path_for_hash(sha256, root)
    if dest.exists():
        existing = dest.read_bytes()
        if content_hash(existing) != sha256:
            raise ArtifactAlreadyExistsError(
                f"Path {dest} exists with content not matching its own hash — "
                "filesystem corruption or hash collision."
            )
        return StoredArtifact(sha256=sha256, path=dest, size_bytes=len(existing), already_existed=True)

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, dest)
    _make_write_once(dest)
    return StoredArtifact(sha256=sha256, path=dest, size_bytes=len(data), already_existed=False)


def _make_write_once(path: Path) -> None:
    try:
        # POSIX: 0400. Windows: sets the read-only attribute (best-effort
        # equivalent — see module docstring).
        os.chmod(path, stat.S_IREAD)
    except OSError:
        # Best-effort: some CI/sandboxed filesystems reject chmod entirely.
        # Not fatal — the write-once *intent* is still honoured by never
        # calling store() with the same hash twice through anything but
        # this function.
        pass


def read(sha256: str, root: Path | None = None) -> bytes:
    return path_for_hash(sha256, root).read_bytes()
