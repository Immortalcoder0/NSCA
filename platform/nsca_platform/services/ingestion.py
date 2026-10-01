"""Real custody/correlation persistence — 15-api-specification.md §3.

Implements the fixture-then-real pattern from backend-02 §3.

**Correlation** now calls Track A's real, batch-oriented
`nsca_engine.api.correlate_artifacts` (added M5) — this module still does
its own heuristic, per-artifact *hostname extraction* from raw text first
(`_heuristic_correlate`; regex over the config body, or a directory-per-
device upload path), since that is genuinely platform's own job — the
engine's `correlate()` groups already-known identity signals into devices
(TRD-01.1 §3.5: serial outranks hostname, escalates on conflict), it does
not itself extract a hostname from raw config text (that only happens
inside the full parse/extract pipeline, which needs a `KnowledgeBase` this
ingestion path doesn't have). `_run_batch_correlation` below does the real
call, once per upload batch (not once per artifact — correlation is a
property of the *set*, same reasoning as `correlate_artifacts`'s own
docstring), and this is where a same-hostname/different-serial escalation
actually gets caught for real rather than silently assigned.

**Fingerprint** now calls Track A's real `nsca_engine.api.fingerprint_artifact`
(M5) against the real `KnowledgeBase` built by `knowledge_base_loader`
(closing the gap this module used to flag: the function existed, the
`KnowledgeBase` argument didn't). `_fingerprint` tries the real engine
call first and only falls back to `_heuristic_fingerprint` when the engine
returns `None` — i.e. the real fingerprinter did not reach a confident
`KNOWN` outcome for this artifact's text (too small/synthetic a sample, or
a platform with no loaded rulepack at all). In practice this means: real,
corpus-realistic configs for a loaded-rulepack platform (`cisco_ios`,
`cloud_generic_fw`, `fortios`, `juniper_junos_curly`, `juniper_junos_set`,
`panos`, `routeros`) are identified by the real engine; small synthetic
test fixtures below `fingerprint.confidence`'s KNOWN threshold, or genuinely
untaught platforms, still fall through to the heuristic exactly as before
— this is why the M1-era four-outcome-states test (`test_stub_endpoints.py
::test_upload_artifacts_four_outcome_states`) is unaffected by this change:
its synthetic fixtures score below KNOWN in the real engine too.

Produces the four ingestion outcome states from
15-api-specification.md §3's example, never a binary:
  - ``parsed``               — recognised, taught platform, verbose export
  - ``parsed_with_caveat``   — recognised, taught platform, terse export
                                (FR-ING-014)
  - ``platform_not_taught``  — recognisable vendor/platform, but no
                                rulepack is loaded for it yet
  - ``unidentified``         — fingerprint/grammar confidence too low to
                                even say what this is

Every artifact is hashed and stored content-addressed
(`db/artifact_store.py`) before any classification happens (FR-ING-012:
"hashed at receipt ... before processing").
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nsca_engine.api import (
    CorrelationOutcome,
    IdentityCandidate,
    correlate_artifacts,
)
from nsca_engine.api import fingerprint_artifact as engine_fingerprint_artifact
from sqlalchemy import select
from sqlalchemy.engine import Connection

from nsca_platform.audit import log as audit_log
from nsca_platform.db import artifact_store
from nsca_platform.db.models.artifact import artifact as artifact_table
from nsca_platform.db.models.campaign import campaign as campaign_table
from nsca_platform.db.models.device import device as device_table
from nsca_platform.knowledge_base_loader import (
    KnowledgeBaseUnavailable,
    get_knowledge_base,
)
from nsca_platform.services import training as training_service

# Bug fix (Phase 3 rehearsal): this used to be a hardcoded
# frozenset({"cisco_ios", "cisco_iosxe"}) — a snapshot of M1's rulepack set
# that was never updated after M2 added 6 more platforms (fortios, panos,
# juniper x2, routeros, cloud_generic_fw) or after the learning subsystem
# started writing genuinely new rulepacks to disk (see
# `services/training.py::_write_and_activate`). A real, engine-loaded
# rulepack for e.g. `routeros` was silently misclassified as
# `platform_not_taught` regardless of what the KnowledgeBase actually
# contained — no device row was ever created for it, so it could never be
# assessed, which is exactly the "teach it, then it's still untaught"
# symptom the rehearsal found. `_taught_platforms()` now derives this set
# from the same real `KnowledgeBase` `_fingerprint` already consults, so a
# newly-taught platform becomes assessable the moment its rulepack is
# written and the cache is cleared (`knowledge_base_loader.clear_cache()`)
# — no separate bookkeeping to fall out of sync again. Falls back to the
# original hardcoded set only if the KnowledgeBase genuinely can't be
# loaded at all (same defensive pattern as `_try_engine_fingerprint`).
_FALLBACK_TAUGHT_PLATFORMS = frozenset({"cisco_ios", "cisco_iosxe"})


# Platform-family aliases: a platform string the fingerprinter/heuristic
# can produce that isn't its own separate rulepack file, but is served by
# another loaded platform's grammar/extractors (IOS-XE is CLI-compatible
# with classic IOS for the constructs this rulepack extracts — the API
# spec's own example, 15-api-specification.md §2's `cisco_iosxe@7.2.1`
# knowledge-base pin, treats it as taught for exactly this reason). Add
# here, never by shipping a near-duplicate rulepack file.
_PLATFORM_ALIASES: dict[str, str] = {"cisco_iosxe": "cisco_ios"}


def _taught_platforms() -> frozenset[str]:
    try:
        kb = get_knowledge_base()
    except KnowledgeBaseUnavailable:
        return _FALLBACK_TAUGHT_PLATFORMS
    loaded = frozenset(rp.platform for rp in kb.rulepacks if rp.loaded is not None)
    if not loaded:
        return _FALLBACK_TAUGHT_PLATFORMS
    aliased = {alias for alias, real in _PLATFORM_ALIASES.items() if real in loaded}
    return loaded | aliased

_VERBOSE_MARKERS = ("ip classless", "no service pad", "ip cef", "no ip source-route")

_ROUTEROS_LINE_PREFIXES = ("/ip", "/system", "/interface", "/user", "set ", "add ", "#")

# Bug found during the Phase 3 demo rehearsal (reproduced twice): this dict
# used to be keyed only "mikrotik_routeros" — the local heuristic
# fingerprinter's own made-up platform id (`_heuristic_fingerprint` below)
# — while the real engine (`nsca_engine.api.fingerprint_artifact`, which
# `_fingerprint` now tries first) returns the canonical id `"routeros"`,
# matching `nsca/knowledge/rulepacks/routeros.yaml`'s own `platform:`
# field. The lookup always missed for any config the real engine could
# actually identify, silently reporting 0.0 grammar coverage regardless of
# how close the config was to the known grammar. Both keys are kept: the
# heuristic fallback path can still produce "mikrotik_routeros", and real
# engine identification produces "routeros" — same prefix set either way.
_KNOWN_LINE_PREFIXES: dict[str, tuple[str, ...]] = {
    "cisco_ios": ("hostname", "interface", "ip ", "line ", "!", "version", "service", "aaa", "access-list",
                  "no ", "banner", "end", "transport", "enable", "username", "vlan", "spanning-tree"),
    "cisco_iosxe": ("hostname", "interface", "ip ", "line ", "!", "version", "service", "aaa", "access-list",
                    "no ", "banner", "end", "transport", "enable", "username", "vlan", "spanning-tree"),
    "mikrotik_routeros": _ROUTEROS_LINE_PREFIXES,
    "routeros": _ROUTEROS_LINE_PREFIXES,
}

_HOSTNAME_PATTERNS = (
    re.compile(r"(?im)^\s*hostname\s+(\S+)"),  # Cisco IOS/IOS-XE
    re.compile(r"(?im)^\s*set\s+name=(\S+)"),  # MikroTik `/system identity`
)


class IngestionError(Exception):
    pass


def _decode(data: bytes) -> str:
    # FR-ING-017: handle non-UTF8/mixed encodings gracefully rather than
    # raising and aborting the whole bulk job.
    return data.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Correlation — fixture-then-real (backend-02 §3)
# ---------------------------------------------------------------------------


def _heuristic_correlate(text: str, filename: str) -> str | None:
    for pattern in _HOSTNAME_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    # No hostname line found in content — fall back to the artifact's own
    # path, per FR-ING-010's "hostname and/or serial" (a directory-per-
    # device upload layout, e.g. "CORE-SW-01/running-config.txt", carries
    # the hostname in the path when the content doesn't state it).
    parts = Path(filename.replace("\\", "/")).parts
    if len(parts) > 1:
        return parts[0]
    return None


def _run_batch_correlation(
    heuristic_hostnames: dict[str, str],
) -> dict[str, tuple[str | None, str]]:
    """Real call into Track A's `correlate_artifacts` (TRD-01.1 §3.5),
    once per upload batch. `heuristic_hostnames` maps `filename ->
    hostname` for whatever this module's own text heuristic
    (`_heuristic_correlate`) could extract per artifact — chassis serial
    is not extracted anywhere in this package yet, so every
    `IdentityCandidate` here has `chassis_serial=None`; the engine's
    serial-outranks-hostname logic degrades gracefully to hostname-only
    grouping in that case, which is honestly what this call site can offer
    today (flagged, not silently pretended to be serial-aware).

    Returns `filename -> (device_key_or_None, method)`. `ASSIGNED` maps to
    the engine's resolved `device_key` with method `"engine"`; `ESCALATED`
    (a real hostname/serial conflict signal — TRD-01.1 §3.5's escalation
    table) maps to `(None, "engine_escalated")`, deliberately withholding a
    device assignment rather than guessing which of two conflicting
    identities is right; `HELD` (no identity signal) is unreachable here
    since only artifacts with a non-None heuristic hostname are submitted.
    Filenames with no heuristic hostname at all are absent from the
    returned dict — callers fall back to path-based heuristics for those.
    """

    if not heuristic_hostnames:
        return {}

    candidates = tuple(
        IdentityCandidate(artifact_id=filename, hostname=hostname, chassis_serial=None)
        for filename, hostname in sorted(heuristic_hostnames.items())
    )
    results = correlate_artifacts(candidates)

    resolved: dict[str, tuple[str | None, str]] = {}
    for result in results:
        for artifact_id in result.artifact_ids:
            if result.outcome == CorrelationOutcome.ASSIGNED:
                resolved[artifact_id] = (result.device_key, "engine")
            elif result.outcome == CorrelationOutcome.ESCALATED:
                resolved[artifact_id] = (None, "engine_escalated")
            else:  # HELD — not expected here, handled defensively
                resolved[artifact_id] = (None, "engine_held")
    return resolved


def _resolve_correlation(
    filename: str, text: str, batch_correlation: dict[str, tuple[str | None, str]],
) -> tuple[str | None, str]:
    """Per-artifact correlation result: prefer the real batch-wide engine
    result (`_run_batch_correlation`); fall back to the local heuristic
    (path-based hostname guess) only when the engine had no identity
    signal to work with for this artifact at all."""

    if filename in batch_correlation:
        return batch_correlation[filename]
    return _heuristic_correlate(text, filename), "heuristic"


# ---------------------------------------------------------------------------
# Fingerprint — fixture-then-real (backend-02 §3)
# ---------------------------------------------------------------------------


def _heuristic_fingerprint(text: str, filename: str) -> dict[str, Any]:
    lower = text.lower()
    fname_lower = filename.lower()

    if "ios-xe" in lower or "ios xe software" in lower:
        return {"vendor": "cisco", "platform": "cisco_iosxe", "confidence": 0.97}
    if "cisco" in lower and ("hostname" in lower or "interface" in lower):
        return {"vendor": "cisco", "platform": "cisco_ios", "confidence": 0.9}
    if fname_lower.endswith(".rsc") or "routeros" in lower or "/system identity" in lower:
        return {"vendor": "mikrotik", "platform": "mikrotik_routeros", "confidence": 0.9}
    if "hostname" in lower or "interface" in lower:
        # Recognisable network-device shape but no vendor markers matched —
        # confident enough it's *a* config, not confident enough to name
        # the platform.
        return {"vendor": "unknown", "platform": None, "confidence": 0.5}
    return {"vendor": "unknown", "platform": None, "confidence": 0.3}


def _try_engine_fingerprint(content: bytes) -> dict[str, Any] | None:
    """Real call into `nsca_engine.api.fingerprint_artifact` — see module
    docstring's "Fingerprint" section. Returns `None` (never raises) if the
    `KnowledgeBase` can't be loaded, or the engine's own outcome isn't
    `KNOWN` — both cases fall through to `_heuristic_fingerprint` at the
    call site."""

    try:
        kb = get_knowledge_base()
    except KnowledgeBaseUnavailable:
        return None

    result = engine_fingerprint_artifact(content, kb)
    if result is None:
        return None
    return {
        "vendor": result.vendor,
        "platform": result.platform,
        "confidence": float(result.confidence),
        "os_version": result.os_version,
    }


def _try_cisco_command_output(content: bytes) -> dict[str, Any] | None:
    """Bug fix (Phase 3 rehearsal, finding 7 / §9 checklist item 5): a real
    `show inventory`/`show version` artifact — command output, not config
    syntax — can never match `fingerprint_artifact`'s grammar-signature
    scoring (`cisco_ios`'s rulepack signatures are all config constructs),
    so it always fell through to `_heuristic_fingerprint`'s generic
    keyword checks, which also don't recognise it (no `hostname`/
    `interface` marker either) -> `platform=None` -> `unidentified` ->
    no `device_id` -> the artifact never reaches `assess_device` at all,
    regardless of how good the engine's serial extraction is. Confirmed
    live: this is the exact reason a real, correctly-formatted show-
    inventory upload never even got the chance to attach to its device.

    Real fix: `nsca_engine.api.classify_cisco_command_output` — content
    sniffing over the actual text (NAME/DESCR/PID/VID/SN pairs, or a
    `Processor board ID`/`Cisco IOS Software` line), same honesty
    discipline as every other real classifier in this module (never a
    guess from the filename alone). Only trusted when `cisco_ios` is
    actually a taught platform (`_taught_platforms()`) — this function
    exists to recognise Cisco command output specifically, not to invent a
    platform this build has no rulepack for."""

    if "cisco_ios" not in _taught_platforms():
        return None

    from nsca_engine.api import classify_cisco_command_output

    kind = classify_cisco_command_output(content)
    if kind is None:
        return None
    return {"vendor": "cisco", "platform": "cisco_ios", "confidence": 0.93}


def _fingerprint(content: bytes, text: str, filename: str) -> dict[str, Any]:
    engine_fp = _try_engine_fingerprint(content)
    if engine_fp is not None:
        if engine_fp.get("os_version") is None:
            engine_fp["os_version"] = _guess_os_version(text, engine_fp.get("platform"))
        return engine_fp

    fp = _heuristic_fingerprint(text, filename)
    if fp.get("platform") is None:
        command_output_fp = _try_cisco_command_output(content)
        if command_output_fp is not None:
            fp = command_output_fp
    fp["os_version"] = _guess_os_version(text, fp.get("platform"))
    return fp


def _guess_os_version(text: str, platform: str | None) -> str | None:
    if platform in ("cisco_ios", "cisco_iosxe"):
        m = re.search(r"[Vv]ersion\s+([0-9][\w.()]*)", text)
        if m:
            return m.group(1)
    if platform == "mikrotik_routeros":
        m = re.search(r"RouterOS\s+([\d.]+)", text)
        if m:
            return m.group(1)
    return None


def _grammar_coverage(text: str, platform: str | None) -> float:
    prefixes = _KNOWN_LINE_PREFIXES.get(platform or "", ())
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or not prefixes:
        return 0.0
    matched = sum(1 for line in lines if line.startswith(prefixes))
    return round(matched / len(lines), 3)


def _training_info_for_platform(conn: Connection, platform: str) -> dict[str, Any]:
    """Bug found during the Phase 3 demo rehearsal: this used to return
    `questions_prepared: 9, estimated_minutes: 8` unconditionally for
    every `platform_not_taught` result, regardless of platform or content
    — self-documented in the old code as a placeholder. Real fix: look up
    whether a training queue has actually been seeded for this platform
    (`services/training.py`'s `queue_for_platform` — the real mine-then-
    propose pipeline output) and report its real question count.

    No live code path runs that mine/propose pipeline synchronously during
    artifact upload yet — doing so needs a real parse/grammar-inference
    attempt against this specific unrecognised config (TRD-02.2), which
    isn't wired into the ingestion path at all. That remains a real,
    separate gap (flagged, not solved here). Until a queue exists for this
    platform, this honestly reports zero rather than a fabricated non-zero
    count that was never based on anything."""

    existing = training_service.queue_for_platform(conn, platform)
    if not existing:
        return {"questions_prepared": 0, "estimated_minutes": 0, "url": f"/api/v1/training/queue/{platform}"}
    # ~50s/question is this product's own worked-example ballpark
    # (08-learning-system.md §9: 8m12s for 9 real, human-judged questions)
    # — a real per-question estimate, not a fixed total regardless of count.
    estimated_minutes = max(1, round(len(existing) * 50 / 60))
    return {
        "questions_prepared": len(existing),
        "estimated_minutes": estimated_minutes,
        "url": f"/api/v1/training/queue/{platform}",
    }


def _export_mode(text: str) -> str:
    lower = text.lower()
    hits = sum(1 for marker in _VERBOSE_MARKERS if marker in lower)
    return "verbose" if hits >= 2 else "terse"


def _guess_artifact_type(text: str, filename: str) -> str:
    lower = text.lower()
    fname_lower = filename.lower()
    if "show version" in lower or "uptime is" in lower:
        return "show_version"
    if "inventory" in fname_lower or "show inventory" in lower:
        return "show_inventory"
    if "hostname" in lower or "/system identity" in lower:
        return "running_config"
    return "unknown"


# ---------------------------------------------------------------------------
# Device correlation (create-or-reuse)
# ---------------------------------------------------------------------------


def _get_or_create_device(
    conn: Connection, hostname: str, platform: str | None, os_version: str | None
) -> uuid.UUID:
    existing = conn.execute(select(device_table.c.id).where(device_table.c.hostname == hostname)).first()
    if existing:
        conn.execute(
            device_table.update()
            .where(device_table.c.id == existing.id)
            .values(
                platform=platform or device_table.c.platform,
                os_version=os_version or device_table.c.os_version,
                last_assessed=datetime.now(UTC),
            )
        )
        return uuid.UUID(str(existing.id))

    device_id = uuid.uuid4()
    conn.execute(
        device_table.insert().values(
            id=device_id,
            hostname=hostname,
            platform=platform,
            os_version=os_version,
            serials=[],
        )
    )
    return device_id


# ---------------------------------------------------------------------------
# Per-file classification
# ---------------------------------------------------------------------------


def _classify_and_persist(
    conn: Connection,
    campaign_row: Any,
    filename: str,
    content: bytes,
    batch_correlation: dict[str, tuple[str | None, str]],
) -> dict[str, Any]:
    text = _decode(content)
    stored = artifact_store.store(content)
    public_id = f"ART-{uuid.uuid4().hex[:6].upper()}"

    fp = _fingerprint(content, text, filename)
    platform = fp.get("platform")
    os_version = fp.get("os_version")
    confidence = float(fp.get("confidence", 0.0))
    taught = _taught_platforms()

    hostname, correlation_method = (None, "none")
    if platform in taught:
        hostname, correlation_method = _resolve_correlation(filename, text, batch_correlation)

    result: dict[str, Any]
    device_id: uuid.UUID | None = None
    status: str

    if platform in taught and hostname:
        export_mode = _export_mode(text)
        artifact_type = _guess_artifact_type(text, filename)
        device_id = _get_or_create_device(conn, hostname, platform, os_version)

        if export_mode == "verbose":
            status = "parsed"
            result = {
                "artifact_id": public_id,
                "filename": filename,
                "sha256": stored.sha256,
                "device": hostname,
                "platform": platform,
                "os_version": os_version,
                "artifact_type": artifact_type,
                "export_mode": export_mode,
                "status": status,
            }
        else:
            status = "parsed_with_caveat"
            hits = sum(1 for marker in _VERBOSE_MARKERS if marker in text.lower())
            controls_unassessable = (len(_VERBOSE_MARKERS) - hits) * 8
            caveat = {
                "code": "TERSE_EXPORT",
                "message": "Settings at platform defaults are not present",
                "controls_unassessable": controls_unassessable,
                "remedy": "Re-collect with `show running-config all`",
            }
            result = {
                "artifact_id": public_id,
                "filename": filename,
                "platform": platform,
                "export_mode": export_mode,
                "status": status,
                "caveat": caveat,
            }
    elif platform:
        # Recognised vendor/platform, but no rulepack loaded for it yet.
        status = "platform_not_taught"
        coverage = _grammar_coverage(text, platform)
        result = {
            "artifact_id": public_id,
            "filename": filename,
            "platform": platform,
            "os_version": os_version,
            "status": status,
            "grammar_coverage": coverage,
            "training": _training_info_for_platform(conn, platform),
        }
    else:
        status = "unidentified"
        coverage = _grammar_coverage(text, "cisco_ios")  # best-effort estimate against the nearest known grammar
        result = {
            "artifact_id": public_id,
            "filename": filename,
            "status": status,
            "grammar_coverage": coverage,
            "message": "Grammar inference unreliable; assisted authoring required",
        }

    conn.execute(
        artifact_table.insert().values(
            id=uuid.uuid4(),
            public_id=public_id,
            device_id=device_id,
            campaign_id=campaign_row.id,
            filename=filename,
            content_hash=stored.sha256,
            size_bytes=stored.size_bytes,
            artifact_type=result.get("artifact_type", "unknown"),
            export_mode=result.get("export_mode", "unknown"),
            received_from="upload",
            status=status,
            platform=platform,
            os_version=os_version,
            fingerprint_confidence=confidence,
            grammar_coverage=result.get("grammar_coverage"),
            caveat=result.get("caveat"),
            training=result.get("training"),
            message=result.get("message"),
            storage_path=str(stored.path),
        )
    )
    return result


def upload_artifacts(
    conn: Connection,
    campaign_public_id: str,
    files: list[tuple[str, bytes]],
    actor: str,
) -> dict[str, Any]:
    campaign_row = conn.execute(
        select(campaign_table).where(campaign_table.c.public_id == campaign_public_id)
    ).first()
    if campaign_row is None:
        raise IngestionError(f"Unknown campaign: {campaign_public_id}")

    # Batch-wide heuristic hostname extraction feeds one real engine
    # correlation call (see module docstring) — computed once up front so
    # every artifact in this upload is correlated against its siblings,
    # not in isolation.
    heuristic_hostnames: dict[str, str] = {}
    for filename, content in files:
        candidate = _heuristic_correlate(_decode(content), filename)
        if candidate:
            heuristic_hostnames[filename] = candidate
    batch_correlation = _run_batch_correlation(heuristic_hostnames)

    results = [
        _classify_and_persist(conn, campaign_row, filename, content, batch_correlation)
        for filename, content in files
    ]

    job_id = f"job-{uuid.uuid4().hex[:10]}"
    audit_log.record(
        conn,
        actor=actor,
        action="ingestion.upload",
        entity_type="campaign",
        entity_id=campaign_public_id,
        details={"job_id": job_id, "accepted": len(results), "statuses": [r["status"] for r in results]},
    )
    return {"job_id": job_id, "accepted": len(results), "results": results}
