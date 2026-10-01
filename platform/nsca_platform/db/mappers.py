"""`nsca_engine.api` dataclass <-> SQLAlchemy row mapping.

Per backend-02 §3: "map them onto your own SQLAlchemy models in a single
`db/mappers.py` module rather than scattering the mapping across services."
This is the one place that happens.

M1 scope: `RawArtifact` (the artifact/ingestion boundary) and
`FingerprintResult` (the device-correlation boundary) — the two engine
contract dataclasses `services/ingestion.py` actually touches this
milestone. `DeviceAssessment`/`Fact` mapping (the ASSESSMENT/FACT tables)
is wired here too since the table shape already exists
(`db/models/assessment.py`), but the worker that produces real
`DeviceAssessment` objects is M2 — the round-trip test for it uses a
hand-built fixture, per backend-02 §3's fixture-then-real pattern.
"""

from __future__ import annotations

import uuid
from fractions import Fraction
from typing import Any, Mapping

from nsca_engine.api import (
    DeviceFinding,
    DeviceSerial,
    Evidence,
    Fact,
    FingerprintResult,
    ProvenanceSource,
    RawArtifact,
    UnmatchedConstruct,
)


# ---------------------------------------------------------------------------
# RawArtifact <-> artifact row
# ---------------------------------------------------------------------------


def raw_artifact_to_row(
    art: RawArtifact,
    *,
    campaign_id: uuid.UUID,
    device_id: uuid.UUID | None,
    content_hash: str,
    storage_path: str,
) -> dict[str, Any]:
    """Builds the column dict for an INSERT into `artifact`, from an engine
    `RawArtifact` plus the platform-side fields the engine doesn't know
    about (campaign, device, storage location)."""

    return {
        "id": uuid.uuid4(),
        "public_id": art.id,
        "device_id": device_id,
        "campaign_id": campaign_id,
        "filename": art.filename,
        "content_hash": content_hash,
        "size_bytes": len(art.content),
        "artifact_type": (art.artifact_type_hint.name.lower() if art.artifact_type_hint else "unknown"),
        "received_from": art.received_from,
        "storage_path": storage_path,
    }


def row_to_raw_artifact(row: Mapping[str, Any], content: bytes) -> RawArtifact:
    """Inverse of `raw_artifact_to_row` — reconstructs the engine-contract
    object from a persisted row plus its bytes (read separately from the
    content-addressed store, never from the DB)."""

    from nsca_engine.api import ArtifactType

    hint: ArtifactType | None
    try:
        hint = ArtifactType[row["artifact_type"].upper()] if row["artifact_type"] else None
    except KeyError:
        hint = None

    return RawArtifact(
        id=row["public_id"],
        filename=row["filename"],
        content=content,
        artifact_type_hint=hint,
        received_from=row["received_from"],
    )


# ---------------------------------------------------------------------------
# FingerprintResult <-> device row
# ---------------------------------------------------------------------------


def fingerprint_to_device_row(fp: FingerprintResult, hostname: str) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "hostname": hostname,
        "platform": fp.platform,
        "os_version": fp.os_version,
        "model": fp.model,
        "serials": [{"component": s.component, "serial": s.serial} for s in fp.serials],
    }


def row_to_fingerprint(row: Mapping[str, Any], *, vendor: str, confidence: Fraction) -> FingerprintResult:
    serials = tuple(DeviceSerial(component=s["component"], serial=s["serial"]) for s in (row["serials"] or []))
    return FingerprintResult(
        vendor=vendor,
        platform=row["platform"],
        os_version=row["os_version"],
        model=row["model"],
        serials=serials,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Fact <-> fact row (table shape exists in M1; producer is M2)
# ---------------------------------------------------------------------------


def fact_to_row(f: Fact, *, assessment_id: uuid.UUID, artifact_id: uuid.UUID | None) -> dict[str, Any]:
    prov = f.provenance
    return {
        "assessment_id": assessment_id,
        "path": f.path,
        "value": f.value,  # None -> JSONB NULL == unknown, never `false`
        "value_type": f.type,
        "source": prov.source.value,
        "artifact_id": artifact_id,
        "line_start": prov.lines[0] if prov.lines else None,
        "line_end": prov.lines[-1] if prov.lines else None,
        "excerpt": prov.excerpt,
        "extractor": prov.extractor,
        "confidence": float(prov.confidence) if prov.confidence is not None else None,
        "layer": prov.layer,
        "depends_on": list(prov.depends_on) if prov.depends_on else None,
    }


def row_to_fact(row: Mapping[str, Any]) -> Fact:
    from nsca_engine.api import Provenance

    confidence = Fraction(row["confidence"]).limit_denominator() if row["confidence"] is not None else None
    provenance = Provenance(
        source=ProvenanceSource(row["source"]),
        artifact_id=str(row["artifact_id"]) if row["artifact_id"] else None,
        lines=tuple(
            range(row["line_start"], row["line_end"] + 1)
        )
        if row["line_start"] is not None and row["line_end"] is not None
        else (),
        excerpt=row["excerpt"],
        extractor=row["extractor"],
        confidence=confidence,
        layer=row["layer"],
        depends_on=tuple(row["depends_on"]) if row["depends_on"] else (),
    )
    return Fact(path=row["path"], value=row["value"], type=row.get("value_type") or "unknown", provenance=provenance)


# ---------------------------------------------------------------------------
# DeviceFinding <-> finding row (M2)
# ---------------------------------------------------------------------------
#
# `DeviceFinding` (nsca_engine.types) is per-device/base-severity only —
# "minus the fields that belong to Track B (owner, due date, lifecycle
# state, dispute, campaign id)" per its own docstring. Everything the
# `finding` table needs beyond that — campaign/device/assessment refs,
# effective severity (a campaign-wide, exposure-weighted computation per
# 05-security-baseline-model.md §4.1), the richer `{framework, id,
# version}` objects 15-api-specification.md §5 renders (DeviceFinding's own
# `framework_refs` is just a tuple of bare id strings — control metadata,
# not Track B's data), attack-path ids, rulepack trust tier, and lifecycle
# bookkeeping (state, identity_key) — is supplied by the caller
# (`services/finding_lifecycle.create_finding_from_device_finding`), not
# reconstructed here. This mapper's job is strictly the DeviceFinding-shaped
# subset; round-tripping the full row happens through `row_to_device_finding`
# below, which reconstructs a real `DeviceFinding` from a persisted row
# (used by the mapper round-trip test) using only the engine-owned columns.


def evidence_to_dict(ev: Evidence) -> dict[str, Any]:
    return {
        "artifact": ev.artifact_id,
        "lines": list(ev.lines),
        "highlight": list(ev.highlight_lines),
        "excerpt": ev.excerpt,
        "facts": list(ev.fact_paths),
        "counterexample": dict(ev.counterexample) if ev.counterexample else None,
    }


def dict_to_evidence(d: Mapping[str, Any]) -> Evidence:
    return Evidence(
        artifact_id=d["artifact"],
        lines=tuple(d.get("lines", [])),
        highlight_lines=tuple(d.get("highlight", [])),
        excerpt=d.get("excerpt", ""),
        fact_paths=tuple(d.get("facts", [])),
        counterexample=d.get("counterexample"),
    )


def device_finding_to_row(
    f: DeviceFinding,
    *,
    campaign_id: uuid.UUID,
    device_id: uuid.UUID,
    assessment_id: uuid.UUID | None,
    public_id: str,
    identity_key: str,
    severity_effective: str | None = None,
    severity_effective_reason: str | None = None,
    framework_refs: list[dict[str, Any]] | None = None,
    attack_paths: list[str] | None = None,
    rulepack_trust_tier: str | None = None,
) -> dict[str, Any]:
    """Column dict for an INSERT into `finding`, from an engine
    `DeviceFinding` plus the campaign-wide/reporting fields Track B owns.

    `severity_effective`/`_reason` default to the base severity/None when
    not supplied — this is the fixture-then-real seam: M2's fixture
    findings and any device without a computed estate graph yet don't have
    a real exposure-weighted effective severity (that's `assess_campaign`,
    M4), so effective falls back to base rather than being left unset.
    """

    return {
        "id": uuid.uuid4(),
        "public_id": public_id,
        "campaign_id": campaign_id,
        "device_id": device_id,
        "assessment_id": assessment_id,
        "control_id": f.control_id,
        # `Verdict` is a plain `Enum` (not `StrEnum`, deliberately — see its
        # docstring), so `.value` is an opaque `auto()` int; `.name` is the
        # stable string ("PASS"/"FAIL"/"UNKNOWN"/"NOT_APPLICABLE") the DB
        # column and the API's `verdict` field both use.
        "verdict": f.verdict.name,
        "pass_quality": f.pass_quality.value if f.pass_quality else None,
        "unknown_reason": f.unknown_reason.value if f.unknown_reason else None,
        "severity_base": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
        "severity_effective": severity_effective
        or (f.severity.value if hasattr(f.severity, "value") else str(f.severity)),
        "severity_reason": severity_effective_reason or f.severity_reason,
        "evidence": [evidence_to_dict(ev) for ev in f.evidence],
        "framework_refs": framework_refs or [],
        "attack_paths": attack_paths or [],
        "contamination_reason": f.contamination_reason,
        "rulepack_trust_tier": rulepack_trust_tier,
        "identity_key": identity_key,
        "state": "New",
    }


def row_to_device_finding(row: Mapping[str, Any]) -> DeviceFinding:
    """Inverse of `device_finding_to_row`, reconstructing only the
    engine-owned subset (used by the mapper round-trip test)."""

    from nsca_engine.api import PassQuality, Severity, UnknownReason, Verdict

    return DeviceFinding(
        control_id=row["control_id"],
        verdict=Verdict[row["verdict"]],
        pass_quality=PassQuality(row["pass_quality"]) if row["pass_quality"] else None,
        unknown_reason=UnknownReason(row["unknown_reason"]) if row["unknown_reason"] else None,
        severity=Severity(row["severity_base"]),
        severity_reason=row["severity_reason"],
        evidence=tuple(dict_to_evidence(e) for e in (row["evidence"] or [])),
        framework_refs=tuple(fr["id"] for fr in (row["framework_refs"] or []) if "id" in fr),
        contamination_reason=row["contamination_reason"],
        coverage_inputs={},
    )


# ---------------------------------------------------------------------------
# UnmatchedConstruct <-> unmatched_construct row (M3, learning subsystem
# queue — db/models/learning.py). Track A's extractor runtime
# (`nsca_engine.extract.runtime.extract`) produces `UnmatchedConstruct`
# objects during real assessment; the fixture-then-real pattern applies
# here exactly as it did for M1's `RawArtifact`/`FingerprintResult`: until
# a real assessment worker routes these into the platform automatically
# (M2/M4 territory), `learning/template_mining.py`'s tests hand-build them
# from `08-learning-system.md`'s worked examples
# (`tests/fixtures/mikrotik.py`).
# ---------------------------------------------------------------------------


def unmatched_construct_to_row(uc: UnmatchedConstruct, *, platform: str) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "platform": platform,
        "artifact_id": uc.artifact_id,
        "lines": list(uc.lines),
        "excerpt": uc.excerpt,
        "parse_path": list(uc.parse_path),
    }


def row_to_unmatched_construct(row: Mapping[str, Any]) -> UnmatchedConstruct:
    return UnmatchedConstruct(
        artifact_id=row["artifact_id"],
        lines=tuple(row["lines"]),
        excerpt=row["excerpt"],
        parse_path=tuple(row["parse_path"]),
    )
