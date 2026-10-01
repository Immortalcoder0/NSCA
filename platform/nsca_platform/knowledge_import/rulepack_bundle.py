"""Rulepack export/import with signature verification — 07-vendor-rulepacks.md
§9.2, backend-02 §4.5, M4.

**What "signature verification" means here.** 07-vendor-rulepacks.md §9.2's
bundle layout (`manifest.yaml` with "platform, version, checksums,
dependencies" plus a separate `signature.sig`) and TECH-STACK.md's silence
on any PKI/keypair infrastructure together point at **integrity
verification via a checksum manifest**, not cryptographic authentication —
there is no mention anywhere in the read docs of a trust root, a signing
key, or a certificate chain. `signature.sig` here is a SHA-256 digest over
the manifest's own canonical bytes (which itself embeds every bundled
file's SHA-256) — verification confirms *the bundle was not altered in
transit / matches what was exported*, not *who* produced it. This is stated
plainly rather than dressed up as PKI, per the task's explicit instruction
to read before assuming.

**"Imported bundles are verified, tier-marked, and validated against the
local corpus before use — an imported rulepack is never trusted on the
strength of its signature alone"** (07-vendor-rulepacks.md §9.2):
`import_bundle` therefore writes the verified content to a **staging**
path (`knowledge/rulepacks/imported/`) and tags it `verified_community`
(07-vendor-rulepacks.md §8's own table entry for "Imported from another
organisation"), never overwriting the active rulepack a campaign might be
running against — promoting a staged import to active use is a separate,
out-of-scope-for-this-milestone corpus-validation step.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

MANIFEST_NAME = "manifest.yaml"
SIGNATURE_NAME = "signature.sig"
RULEPACK_ENTRY_NAME = "rulepack.yaml"

DEFAULT_STAGING_DIR = Path(__file__).resolve().parents[3] / "knowledge" / "rulepacks" / "imported"


class BundleError(ValueError):
    pass


class SignatureVerificationError(BundleError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest_bytes(manifest: dict[str, Any]) -> bytes:
    # `sort_keys=True`: the manifest's own serialisation must be
    # deterministic, since the signature is computed over it (D6 extended
    # to content authoring, not just assessment).
    return yaml.safe_dump(manifest, sort_keys=True, default_flow_style=False).encode("utf-8")


def _compute_signature(manifest: dict[str, Any]) -> str:
    return "sha256:" + _sha256(_manifest_bytes(manifest))


def export_bundle(rulepack_path: Path | str, *, dependencies: list[str] | None = None) -> bytes:
    """Reads one `knowledge/rulepacks/<platform>.yaml` file and produces a
    signed bundle (07-vendor-rulepacks.md §9.2's layout, `.rpk`-equivalent
    zip): `manifest.yaml`, `signature.sig`, `rulepack.yaml`."""

    path = Path(rulepack_path)
    if not path.exists():
        raise BundleError(f"no such rulepack file: {path}")
    content = path.read_bytes()
    doc = yaml.safe_load(content) or {}

    manifest = {
        "platform": doc.get("platform", path.stem),
        "version": str(doc.get("version", "0.0.0")),
        "vendor": doc.get("vendor"),
        "trust_tier": doc.get("trust_tier", "local"),
        "dependencies": dependencies or [],
        "checksums": {RULEPACK_ENTRY_NAME: f"sha256:{_sha256(content)}"},
    }
    signature = _compute_signature(manifest)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_NAME, _manifest_bytes(manifest))
        zf.writestr(SIGNATURE_NAME, signature)
        zf.writestr(RULEPACK_ENTRY_NAME, content)
    return buf.getvalue()


@dataclass(frozen=True, slots=True)
class ImportResult:
    platform: str
    version: str
    trust_tier: str
    signature_verified: bool
    staged_path: str


def import_bundle(bundle_bytes: bytes, *, staging_dir: Path | str = DEFAULT_STAGING_DIR) -> ImportResult:
    """Verifies the bundle's manifest checksums and signature, then writes
    the rulepack content to the staging directory. Raises
    `SignatureVerificationError` — refusal, never a partial/best-effort
    import — if either check fails."""

    try:
        zf = zipfile.ZipFile(io.BytesIO(bundle_bytes))
    except zipfile.BadZipFile as exc:
        raise BundleError(f"not a valid bundle archive: {exc}") from exc

    names = set(zf.namelist())
    missing = {MANIFEST_NAME, SIGNATURE_NAME, RULEPACK_ENTRY_NAME} - names
    if missing:
        raise BundleError(f"bundle is missing required member(s): {sorted(missing)}")

    manifest_bytes = zf.read(MANIFEST_NAME)
    manifest = yaml.safe_load(manifest_bytes) or {}
    signature = zf.read(SIGNATURE_NAME).decode("utf-8").strip()
    rulepack_content = zf.read(RULEPACK_ENTRY_NAME)

    expected_signature = _compute_signature(manifest)
    if signature != expected_signature:
        raise SignatureVerificationError(
            "bundle signature does not match its manifest — altered in transit or corrupted"
        )

    declared_checksum = manifest.get("checksums", {}).get(RULEPACK_ENTRY_NAME)
    actual_checksum = f"sha256:{_sha256(rulepack_content)}"
    if declared_checksum != actual_checksum:
        raise SignatureVerificationError(
            f"rulepack content checksum mismatch: manifest declares {declared_checksum!r}, "
            f"actual content hashes to {actual_checksum!r}"
        )

    platform = str(manifest.get("platform", "unknown"))
    version = str(manifest.get("version", "0.0.0"))

    staging = Path(staging_dir)
    staging.mkdir(parents=True, exist_ok=True)
    dest = staging / f"{platform}-{version}.yaml"
    dest.write_bytes(rulepack_content)

    return ImportResult(
        platform=platform, version=version,
        # Never trust the bundle's own claimed trust_tier verbatim —
        # 07-vendor-rulepacks.md §8: an imported rulepack is
        # `verified_community` regardless of what it claims to be, until a
        # separate, out-of-scope corpus-validation step promotes it.
        trust_tier="verified_community",
        signature_verified=True, staged_path=str(dest),
    )
