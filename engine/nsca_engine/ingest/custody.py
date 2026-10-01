"""Custody hashing and recording (TRD-01.1 §3.1 step 2, INV-01.1-01).

The content hash is computed on the exact octet sequence received, before any
encoding normalisation — a hash computed after transformation cannot
establish what was supplied.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CustodyRecord:
    artifact_id: str
    content_hash: str  # "sha256:<hex>"
    size_bytes: int
    filename: str
    received_from: str


def hash_content(content: bytes) -> str:
    """INV-01.1-01: hash before transform. Called on raw received octets,
    never on normalised text."""

    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def record_custody(
    artifact_id: str, content: bytes, filename: str, received_from: str
) -> CustodyRecord:
    return CustodyRecord(
        artifact_id=artifact_id,
        content_hash=hash_content(content),
        size_bytes=len(content),
        filename=filename,
        received_from=received_from,
    )
