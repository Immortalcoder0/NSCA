"""The public contract of the Assessment Engine (Backend Track A).

This is the **only** module `platform/` may import
(00-master-plan.md §3, §5.1; backend-01 §1: "Your code has no dependency on
Track B's code, ever... Track B depends on you, via the single module
`nsca_engine/api.py`"). Everything defined here must be reproduced
byte-for-byte from 00-master-plan.md §5.1 / backend-01 §4 — if this file and
those docs ever disagree, the docs win and this file gets fixed.

M0 scope (backend-01 §6): the dataclasses here are real — not stubs — but
`assess_device`/`assess_campaign` bodies raise `NotImplementedError`. That is
the one place M0 explicitly allows a stub; every dataclass shape is meant to
be final.

Determinism (backend-01 §2.1): nothing in this module may read the clock,
use `random`, or touch the filesystem/network beyond what
`KnowledgeBase`/`SchemaRegistry` construction already did before these
functions are called. `assessed_at` is always a parameter.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

from nsca_engine.schema.registry import SchemaRegistry
from nsca_engine.types import (
    ArtifactType,
    DeviceFinding,
    DeviceScores,
    DeviceSerial,
    Evidence,
    Fact,
    FindingKey,
    FingerprintResult,
    GraphEdge,
    GraphFragment,
    GraphNode,
    PassQuality,
    Provenance,
    ProvenanceSource,
    Severity,
    UnknownReason,
    UnmatchedConstruct,
    Verdict,
)

# M5 addition: re-exported here (not just referenced internally) so
# `platform/` — which the import-boundary rule (00-master-plan.md §5.1,
# `gate_import_boundary`) restricts to `nsca_engine.api` only — can build
# and read the `Fact`/`DeviceFinding`/`DeviceAssessment` component types it
# maps to its own DB rows (db/mappers.py) without reaching into
# `nsca_engine.types` directly. These are all sub-components of the
# already-fixed `DeviceAssessment`/`CampaignAssessment` contract shapes
# (M0 §4.1), not new surface — just making them reachable through the one
# door the contract allows.

__all__ = [
    # Knowledge base
    "RawArtifact", "ExtractorRef", "Rulepack", "ControlPack",
    "KnowledgeBasePin", "KnowledgeBase",
    # Campaign-wide risk shapes
    "Graph", "ContaminationNote", "AttackPathStep", "AttackPath",
    "PeerAnomaly", "SystemicFindingCandidate",
    # Entry-point return shapes
    "DeviceAssessment", "CampaignAssessment",
    # The two fixed entry points (00-master-plan.md §5.1)
    "assess_device", "assess_campaign",
    # Narrow, documented additional entry points (M1/M5)
    "fingerprint_artifact", "correlate_artifacts", "extract_chassis_serial",
    "classify_cisco_command_output",
    "query_reachability", "query_reachability_zone",
    "compile_value_expression", "evaluate_value_expression",
    "load_knowledge_base",
    "ValueExpressionError",
    # Re-exported component/result types platform/ needs to construct or
    # interpret values returned by the above, without reaching past this
    # module (see the re-export note above and each wrapper's docstring)
    "ArtifactType", "DeviceFinding", "DeviceScores", "DeviceSerial",
    "Evidence", "Fact", "FindingKey", "FingerprintResult", "GraphEdge",
    "GraphFragment", "GraphNode", "PassQuality", "Provenance",
    "ProvenanceSource", "Severity", "UnknownReason", "UnmatchedConstruct",
    "Verdict", "IdentityCandidate", "CorrelationResult",
    "CorrelationOutcome", "Counterexample", "QueryResult", "RuleChainStep",
    "SearchStats",
]

# ---------------------------------------------------------------------------
# Knowledge base — everything the engine reads to assess a device/campaign
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RawArtifact:
    """One piece of raw evidence handed to the engine (00-master-plan.md
    §5.1). ``id`` is platform-assigned and opaque to the engine — the
    engine never generates its own artifact identifiers (that would be a
    hidden source of non-determinism/coupling to Track B's id scheme).
    """

    id: str
    filename: str
    content: bytes
    artifact_type_hint: ArtifactType | None
    received_from: str


@dataclass(frozen=True, slots=True)
class ExtractorRef:
    """Reference to one extractor within a rulepack
    (07-vendor-rulepacks.md §5). Full extractor semantics (match pattern,
    emit expressions, scope, tests) belong to `controls/rulepack_loader.py`
    (Phase 1) — this is the minimal shape `Rulepack` needs to exist as a
    real dataclass today.
    """

    extractor_id: str
    version: int


@dataclass(frozen=True, slots=True)
class Rulepack:
    """A vendor/platform rulepack (07-vendor-rulepacks.md §2): fingerprint
    signatures, structural grammar, extractors, defaults table, inheritance
    rules, platform quirks. The full loader (`controls/rulepack_loader.py`)
    is Phase 1 work — this dataclass fixes the shape the `KnowledgeBase`
    contract commits to today: identity, version, trust tier, and which
    extractors it carries.
    """

    platform: str
    version: str
    trust_tier: str  # certified | verified_community | local | provisional
    extractors: tuple[ExtractorRef, ...]
    # M1 addition (backward compatible — defaults to None, so every M0
    # construction of Rulepack(...) without this field keeps working
    # unchanged): the fully parsed rulepack content
    # (controls.rulepack_loader.LoadedRulepack) — fingerprint signatures,
    # grammar, extractor specs, defaults table, lookup tables. Kept as `Any`
    # rather than importing the concrete type here, so `api.py` — the one
    # module Track B may depend on — does not pull in the entire M1 engine
    # internals import graph just to describe the contract shape. Loading
    # happens once, at KnowledgeBase-construction time (the one allowed disk
    # read, per this module's own docstring), never inside assess_device.
    loaded: Any | None = None


@dataclass(frozen=True, slots=True)
class ControlPack:
    """A pack of controls to evaluate facts against
    (06-controls-and-frameworks.md §3). Full control/assertion semantics
    are `controls/evaluate.py` + `controls/expression.py` territory
    (TRD-05.1/05.2, Phase 1). Fixed here only to the extent the
    `KnowledgeBase` contract needs: identity, version, and which control
    ids it carries.
    """

    id: str
    version: str
    control_ids: tuple[str, ...]
    # M1 addition (backward compatible, see Rulepack.loaded above): the
    # fully parsed control pack content (controls.rulepack_loader.
    # LoadedControlPack) — compiled native controls, ready to evaluate.
    loaded: Any | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeBasePin:
    """Exact versions of engine + every content source, for the campaign
    manifest (14-data-model.md §2 CAMPAIGN entity `knowledge_base_pin`).
    Recorded so a historical campaign can be reproduced against the
    knowledge exactly as it existed then (TRD-03.3 §3.9).
    """

    engine_version: str
    schema_registry_version: str
    rulepack_versions: tuple[str, ...]
    control_pack_versions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class KnowledgeBase:
    """Everything `assess_device`/`assess_campaign` read to do their work
    (00-master-plan.md §5.1). Construction (including `SchemaRegistry.load`)
    is where the one allowed disk read happens — never inside the
    `assess_*` calls themselves.
    """

    schema_registry: SchemaRegistry
    rulepacks: tuple[Rulepack, ...]
    control_packs: tuple[ControlPack, ...]
    pin: KnowledgeBasePin


# ---------------------------------------------------------------------------
# Campaign-wide risk shapes (assess_campaign's output, §4.2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Graph:
    """The merged estate graph (TRD-04.1). Sorted adjacency, per
    TECH-STACK.md §8 — deterministic traversal by construction (D6). The
    full builder/reachability engine (`graph/build.py`,
    `graph/reachability.py`) is Phase 1 (M3) work; this is the shape
    `CampaignAssessment` commits to today: every node/edge contributed by
    every device, merged.
    """

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]


@dataclass(frozen=True, slots=True)
class ContaminationNote:
    """Scope-contamination annotation (FR-GRF-004, FR-RSK-008;
    05-security-baseline-model.md §4.10, TRD-03.3 §3.8) — a passing
    control's scope was contaminated by unaudited surface or a graph-level
    counterexample elsewhere in the estate.
    """

    device_id: str
    control_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class AttackPathStep:
    """One hop in an attack path chain (TRD-06.2)."""

    device_id: str
    node_id: str
    rule_id: str | None


@dataclass(frozen=True, slots=True)
class AttackPath:
    """A computed attack-path chain with its weakest link
    (TRD-06.2, 04-system-architecture.md §4.5's Trusted-Admins →
    Partners → 0.0.0.0/0 canonical example — reproduced exactly in M3, not
    this milestone)."""

    id: str
    steps: tuple[AttackPathStep, ...]
    weakest_link_reason: str


@dataclass(frozen=True, slots=True)
class PeerAnomaly:
    """A device whose facts diverge from its platform peers
    (TRD-06.3) — needs siblings of the same platform, hence campaign-wide
    rather than per-device."""

    device_id: str
    fact_path: str
    peer_group_platform: str
    description: str


@dataclass(frozen=True, slots=True)
class SystemicFindingCandidate:
    """A finding pattern repeated across enough of the fleet to be
    reported as systemic rather than per-device (TRD-06.3,
    09-findings-lifecycle.md §11.2's AP-003 example)."""

    control_id: str
    device_ids: tuple[str, ...]
    description: str


# ---------------------------------------------------------------------------
# The two entry points and their return shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeviceAssessment:
    """Output of `assess_device` (backend-01 §4.1). Everything
    14-data-model.md §2's ASSESSMENT, FACT and (per-device) FINDING
    entities need, minus what Track B attaches (owner, due date, lifecycle
    state, dispute, campaign id).

    `findings[].severity` is **base** severity only — exposure-weighted
    **effective** severity is a campaign-wide computation, because exposure
    is a graph-position property of the whole estate, not a single
    device's own facts (05-security-baseline-model.md §4.1:
    `device.exposure` is "computed from the graph, not read from
    configuration").
    """

    fingerprint: FingerprintResult
    facts: tuple[Fact, ...]
    unmatched_constructs: tuple[UnmatchedConstruct, ...]
    graph_contribution: GraphFragment
    findings: tuple[DeviceFinding, ...]
    grammar_coverage: Fraction
    scores: DeviceScores


@dataclass(frozen=True, slots=True)
class CampaignAssessment:
    """Output of `assess_campaign` (backend-01 §4.2). Everything that
    requires seeing more than one device at once: the merged estate graph,
    exposure-weighted effective severities, attack paths, peer anomalies,
    systemic findings, and scope-contamination annotations."""

    graph: Graph
    effective_severities: Mapping[FindingKey, Severity]
    scope_contamination: tuple[ContaminationNote, ...]
    attack_paths: tuple[AttackPath, ...]
    peer_anomalies: tuple[PeerAnomaly, ...]
    systemic_findings: tuple[SystemicFindingCandidate, ...]


def _normalise_text(content: bytes) -> str:
    """TRD-01.1 §3.2 encoding normalisation, trimmed to what M1 needs: BOM
    stripping, UTF-8 decode, CRLF/CR -> LF. Full undecodable-octet handling
    (U+FFFD replacement with offset tracking) is deferred — M1's fixtures
    are clean UTF-8 — and flagged in the M1 report."""

    if content.startswith(b"\xef\xbb\xbf"):
        content = content[3:]
    text = content.decode("utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Trailing-whitespace-per-line is stripped here, not left to each
    # downstream stage to handle independently — it is exactly the kind of
    # semantics-preserving variation TRD-11.2 metamorphic testing exists to
    # catch (leading indentation, which IS structurally significant for the
    # indentation paradigm, TRD-02.1 §3.3, is deliberately left untouched).
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text


def _select_loaded_rulepack(knowledge_base: KnowledgeBase, platform: str) -> Any:
    for rp in knowledge_base.rulepacks:
        if rp.platform == platform and rp.loaded is not None:
            return rp.loaded
    return None


def _all_native_controls(knowledge_base: KnowledgeBase) -> tuple[Any, ...]:
    controls: list[Any] = []
    for cp in knowledge_base.control_packs:
        if cp.loaded is not None:
            controls.extend(cp.loaded.controls)
    controls.sort(key=lambda c: c.control_id)
    return tuple(controls)


class ValueExpressionError(ValueError):
    """Public alias for `nsca_engine.extract.value_lang.ValueLangError`, so
    callers at the `platform/` boundary can catch a contract-stable
    exception type without importing the internal module directly."""


def compile_value_expression(source: str) -> Any:
    """Compile an extractor value expression (TRD-03.1 §3.3) — the same
    restricted, side-effect-free language rulepack `emit[].value` fields
    use — for repeated evaluation via `evaluate_value_expression`.

    Narrow contract addition, same rationale as `fingerprint_artifact`:
    Backend Track B's learning subsystem (rule synthesis, validation gates)
    needs to compile and evaluate candidate extractor expressions using
    engine semantics, not a reimplementation that could silently drift from
    what `extract/runtime.py` actually does at assessment time. Reaching
    into `nsca_engine.extract.value_lang` directly would violate the
    import-boundary rule (00-master-plan.md §5.1: platform may only import
    `nsca_engine.api`) — this wrapper is what keeps that rule true instead
    of aspirational.

    Returns an opaque compiled object; treat it as a black box and pass it
    straight to `evaluate_value_expression`. Raises `ValueExpressionError`
    on a malformed or disallowed expression.
    """

    from nsca_engine.extract.value_lang import ValueLangError, compile_expr

    try:
        return compile_expr(source)
    except ValueLangError as exc:
        raise ValueExpressionError(str(exc)) from exc


def evaluate_value_expression(
    compiled: Any,
    captures: Mapping[str, Any],
    lookup: Mapping[str, Any] | None = None,
) -> Any:
    """Evaluate a value expression compiled by `compile_value_expression`
    against regex capture groups plus optional `map_lookup` tables. See
    `compile_value_expression`'s docstring for why this wrapper exists."""

    from nsca_engine.extract.value_lang import ValueLangError, evaluate_expr

    try:
        return evaluate_expr(compiled, captures, lookup)
    except ValueLangError as exc:
        raise ValueExpressionError(str(exc)) from exc


from nsca_engine.graph.reachability import (  # noqa: E402
    Counterexample,
    QueryResult,
    RuleChainStep,
    SearchStats,
)
from nsca_engine.ingest.correlate import (  # noqa: E402 — see module docstring ordering note below
    CorrelationOutcome,
    CorrelationResult,
    IdentityCandidate,
)

# M5 addition: re-exporting these two modules' types (not just wrapping
# their functions below) for the same reason as the `nsca_engine.types`
# block above — `correlate_artifacts`/`query_reachability` callers need to
# construct `IdentityCandidate`s and interpret `QueryResult`s, and the
# import-boundary rule means they can only get those shapes from here.
# Imported at module level (not lazily, unlike the internal imports inside
# `assess_device`) because these are lightweight, side-effect-free
# dataclass/enum modules — no heavier than `nsca_engine.types` itself,
# already imported at module level above.


def correlate_artifacts(
    candidates: tuple[IdentityCandidate, ...],
) -> tuple[CorrelationResult, ...]:
    """Correlate a batch of artifacts' identity signals (hostname, chassis
    serial) into per-device groupings (TRD-01.1 §3.5: serial outranks
    hostname). Thin wrapper around `nsca_engine.ingest.correlate.correlate`
    — added so Backend Track B's ingestion pipeline can call the real
    correlation logic through `nsca_engine.api` instead of importing
    `nsca_engine.ingest` directly (00-master-plan.md §5.1).

    Batch-oriented by design, matching TRD-01.1's own model: correlation is
    a property of a *set* of artifacts (do these three uploads belong to
    one device or three?), not any single artifact in isolation — callers
    with only one artifact at a time should still pass a one-element tuple
    per call, or better, batch their whole upload before correlating.
    """

    from nsca_engine.ingest.correlate import correlate

    return correlate(candidates)


def query_reachability(
    graph: Graph, src_addr: str, dst_addr: str,
    protocol: str = "tcp", dport: int = 22,
) -> QueryResult:
    """Concrete-packet reachability query against a merged estate graph
    (TRD-04.2), producing a counterexample (rule chain) rather than a bare
    boolean. Thin wrapper around `nsca_engine.graph.reachability.query`.

    Added as a narrow contract addition (00-master-plan.md §5.1) so Backend
    Track B's dispute-adjudication (machine-verified compensating controls,
    backend-02 §4.3) and remediation lockout-check (backend-02 §4.4) code
    can call the real reachability engine instead of reaching into
    `nsca_engine.graph` directly. This does not by itself solve those call
    sites' bigger open question — they still need a real `Graph` built from
    persisted node/edge data, which platform does not yet assemble anywhere
    (flagged separately, M2/M4 reports) — but the *function* they need to
    call once they have a `Graph` is now reachable through the one door the
    import-boundary contract allows.

    See `nsca_engine.graph.reachability`'s module docstring for the
    documented scope simplifications (single concrete packet, not the full
    TRD-04.2 set-based algorithm; visited-set keyed on device_id alone;
    inbound ACLs only).
    """

    from nsca_engine.graph.reachability import query

    return query(graph, src_addr, dst_addr, protocol, dport)


def load_knowledge_base(
    knowledge_dir: Path | str,
    *, engine_version: str = "0.1.0", schema_registry_version: str = "0.1.0",
) -> KnowledgeBase:
    """Build a real `KnowledgeBase` from `knowledge_dir` (expects `schema/`,
    `rulepacks/`, `control_packs/` subdirectories, matching the repo's
    `nsca/knowledge/` layout) — every rulepack and control pack YAML found
    is loaded via `controls/rulepack_loader.py`. This is the one allowed
    disk read this contract permits (module docstring), performed once
    here rather than reimplemented ad hoc by every caller.

    Added as a narrow, generic contract addition: `nsca_engine`'s own test
    suite already assembled a `KnowledgeBase` this way per test module
    (`tests/helpers.py`, hand-listing each platform's rulepack path) —
    Backend Track B needs the same assembly to call `assess_device`/
    `fingerprint_artifact` for real instead of via fixtures, and
    duplicating engine-internal loader-wiring logic across the process
    boundary is exactly the kind of drift the single-loader design
    (backend-01 §5.4: "Track B never bypasses Track A's loader to
    interpret rulepack YAML itself") exists to prevent. Generic over
    whatever `*.yaml` files exist in the directory — unlike the test
    helper, it does not hardcode a platform list, so a newly taught/
    ratified rulepack (learning subsystem output, backend-02 §4.3) is
    picked up on the next call with no code change.

    A rulepack or control pack that fails to load is skipped (not fatal to
    the whole `KnowledgeBase` — one broken file for one platform should
    not block assessing every other already-working platform); raises
    `ValueError` only if the result would have zero usable rulepacks or
    zero usable control packs, since a `KnowledgeBase` that can assess
    nothing is not a value worth silently handing back.
    """

    from nsca_engine.controls.rulepack_loader import (
        RulepackLoadError,
        load_control_pack,
        load_rulepack,
    )

    knowledge_dir = Path(knowledge_dir)
    schema_registry = SchemaRegistry.load(knowledge_dir / "schema")

    rulepacks: list[Rulepack] = []
    rulepack_versions: list[str] = []
    load_errors: list[str] = []
    for path in sorted((knowledge_dir / "rulepacks").glob("*.yaml")):
        try:
            loaded = load_rulepack(path)
        except (RulepackLoadError, OSError, ValueError, KeyError) as exc:
            load_errors.append(f"{path}: {exc}")
            continue
        rulepacks.append(
            Rulepack(
                platform=loaded.platform, version=loaded.version,
                trust_tier=loaded.trust_tier, extractors=(), loaded=loaded,
            )
        )
        rulepack_versions.append(f"{loaded.platform}@{loaded.version}")

    control_packs: list[ControlPack] = []
    control_pack_versions: list[str] = []
    for path in sorted((knowledge_dir / "control_packs").glob("*.yaml")):
        try:
            loaded_cp = load_control_pack(path)
        except (RulepackLoadError, OSError, ValueError, KeyError) as exc:
            load_errors.append(f"{path}: {exc}")
            continue
        pack_id = path.stem
        control_packs.append(
            ControlPack(
                id=pack_id, version=loaded_cp.version,
                control_ids=tuple(c.control_id for c in loaded_cp.controls),
                loaded=loaded_cp,
            )
        )
        control_pack_versions.append(f"{pack_id}@{loaded_cp.version}")

    if not rulepacks or not control_packs:
        detail = "; ".join(load_errors) or "no *.yaml files found under rulepacks/ or control_packs/"
        raise ValueError(
            f"load_knowledge_base({knowledge_dir}): could not assemble a usable "
            f"KnowledgeBase ({len(rulepacks)} rulepacks, {len(control_packs)} "
            f"control packs loaded) — {detail}"
        )

    return KnowledgeBase(
        schema_registry=schema_registry,
        rulepacks=tuple(rulepacks),
        control_packs=tuple(control_packs),
        pin=KnowledgeBasePin(
            engine_version=engine_version,
            schema_registry_version=schema_registry_version,
            rulepack_versions=tuple(sorted(rulepack_versions)),
            control_pack_versions=tuple(sorted(control_pack_versions)),
        ),
    )


def query_reachability_zone(
    graph: Graph, src_zone: str, dst_addr: str,
    protocol: str = "tcp", dport: int = 22,
) -> QueryResult:
    """Zone-to-address convenience wrapper around `query_reachability`,
    resolving `src_zone` to a deterministic representative address
    (DD-04.2-03) — see `nsca_engine.graph.reachability.query_zone`, which
    this wraps."""

    from nsca_engine.graph.reachability import query_zone

    return query_zone(graph, src_zone, dst_addr, protocol, dport)


def fingerprint_artifact(
    content: bytes,
    knowledge_base: KnowledgeBase,
) -> FingerprintResult | None:
    """Identify which loaded rulepack's platform this raw artifact belongs
    to (TRD-01.2), without running the rest of the pipeline.

    This is a narrow, additional contract entry point — not one of the two
    functions §5.1 of the master plan fixes — added because Backend Track B
    needs fingerprint-only classification during ingestion (deciding
    ``parsed`` vs ``platform_not_taught`` vs ``unidentified`` per
    15-api-specification.md §3) before a device's full artifact set is even
    assembled, let alone ready for `assess_device`. It reuses exactly the
    same scoring/decision logic `assess_device` uses internally, so the two
    never drift apart.

    Returns ``None`` when the fingerprint outcome is not ``KNOWN`` (i.e. no
    fully-loaded rulepack could confidently claim this text) — callers that
    need the *reason* (AMBIGUOUS vs LOW_CONFIDENCE vs UNKNOWN vs
    IDENTIFIABLE_UNTAUGHT) rather than a bare pass/fail should call
    `nsca_engine.fingerprint.confidence.decide` directly with their own
    scores; this function intentionally only answers "do we know what this
    is," matching what ingestion classification needs.
    """

    from nsca_engine.fingerprint import confidence as fp_confidence
    from nsca_engine.fingerprint import signatures as fp_signatures

    text = _normalise_text(content)

    loaded_rulepacks = tuple(
        rp.loaded for rp in knowledge_base.rulepacks if rp.loaded is not None
    )
    if not loaded_rulepacks:
        return None

    scores = {
        lrp.platform: fp_signatures.score_platform(text, lrp.signature_set)
        for lrp in loaded_rulepacks
    }
    signals_by_platform = {
        lrp.platform: fp_signatures.matched_signals(text, lrp.signature_set)
        for lrp in loaded_rulepacks
    }
    decision = fp_confidence.decide(scores=scores, signals_by_platform=signals_by_platform)
    if decision.outcome != fp_confidence.FingerprintOutcome.KNOWN:
        return None

    rulepack = next(lrp for lrp in loaded_rulepacks if lrp.platform == decision.platform)

    os_version = None
    if rulepack.version_pattern is not None:
        ver_match = rulepack.version_pattern.search(text)
        if ver_match:
            os_version = ver_match.groupdict().get("v") or (
                ver_match.group(1) if ver_match.groups() else None
            )

    return FingerprintResult(
        vendor=rulepack.vendor, platform=rulepack.platform, os_version=os_version,
        model=None, serials=(), confidence=decision.confidence,
    )


def extract_chassis_serial(content: bytes) -> str | None:
    """Best-effort chassis-serial sniff straight from one artifact's raw
    bytes, with no `KnowledgeBase` required (unlike `fingerprint_artifact`,
    which needs loaded rulepack signatures) — narrow, additional contract
    entry point (00-master-plan.md §5.1) added for Backend Track B's
    ingestion-time `IdentityCandidate` construction (TRD-01.1 §3.5's "serial
    outranks hostname"), which runs before any device row — and therefore
    before any real `assess_device` call — exists.

    Currently Cisco IOS `show inventory`/`show version` text only (see
    `extract/cisco_inventory.py`); returns the first (chassis) serial found,
    preferring the more authoritative `show inventory` format when the text
    matches both. Returns `None` for anything else — never a fabricated
    value, and never a partial guess from ambiguous text.

    Deliberately NOT wired into `correlate_artifacts`'s live call site in
    `nsca_platform/services/ingestion.py` — see that module's own notes: the
    real-world case this product is built for (FR-ING-010, "hostname and
    serial routinely arrive in *different* artifacts of the same upload,
    e.g. running-config.txt + show-version.txt") means naively passing a
    per-artifact chassis serial into `correlate()` today, whose grouping key
    becomes the serial the moment any candidate in the batch carries one,
    would split those two files into two different devices rather than one
    (since only one of them carries the serial) — a regression, not a fix.
    Fixing that requires `correlate()` (or its caller) to merge signals
    *within* an already-agreed hostname group before grouping by serial,
    which is a real, separate design change flagged here rather than
    papered over with an unsafe wiring.
    """

    from nsca_engine.extract import cisco_inventory

    text = _normalise_text(content)
    if cisco_inventory.looks_like_show_inventory(text):
        result = cisco_inventory.extract_show_inventory(text, artifact_id="")
        if result.serials:
            return result.serials[0].serial
    if cisco_inventory.looks_like_show_version(text):
        result = cisco_inventory.extract_show_version_serial(text, artifact_id="")
        if result.serials:
            return result.serials[0].serial
    return None


def classify_cisco_command_output(content: bytes) -> ArtifactType | None:
    """Best-effort classification of raw artifact bytes as Cisco IOS `show
    inventory`/`show version` COMMAND OUTPUT (not configuration syntax) —
    narrow, additional contract entry point for Backend Track B's
    ingestion-time classification (15-api-specification.md §3's four
    outcome states).

    Added for a real gap the Phase 3 demo rehearsal exposed end to end: a
    `show inventory` artifact uploaded alongside a device's running-config
    (exactly FR-ING-010's directory-per-device multi-artifact scenario)
    could never be grammar-fingerprinted as `cisco_ios` — `fingerprint_
    artifact`/`assess_device`'s paradigm dispatch is built for *config*
    syntax (hostname/interface/`!` structure), and command output has none
    of that (see `extract/cisco_inventory.py`'s module docstring) — so
    `nsca_platform.services.ingestion._fingerprint` fell through to
    `platform=None`, the artifact was classified `unidentified`, given no
    `device_id`, and `assess_device` never saw it even after this milestone
    taught the engine to actually parse it. This function is what lets
    ingestion recognise the text well enough to still correlate it to the
    right device (via the existing hostname-based correlation path — this
    function does not touch identity/correlation logic itself, only
    classification), even though it can never become a `cisco_ios`
    grammar-fingerprint match. Returns `None` for anything that isn't
    recognisably one of these two, never a guess.
    """

    from nsca_engine.extract import cisco_inventory

    text = _normalise_text(content)
    if cisco_inventory.looks_like_show_inventory(text):
        return ArtifactType.SHOW_INVENTORY
    if cisco_inventory.looks_like_show_version(text):
        return ArtifactType.SHOW_VERSION
    return None


def assess_device(
    artifacts: tuple[RawArtifact, ...],
    knowledge_base: KnowledgeBase,
    assessed_at: datetime,
) -> DeviceAssessment:
    """Run the per-device pipeline (Ingest → Fingerprint → Parse → Extract
    → per-device Graph contribution → Evaluate) over one device's raw
    artifacts.

    Pure function: identical arguments must return byte-for-byte identical
    results (`==` and identical `repr()`), from any process, any run
    (00-master-plan.md §5.1). `assessed_at` is a parameter, never read from
    the wall clock (D2) — it is accepted for contract fidelity but this M1
    pipeline does not yet stamp anything with it (no fact or finding in the
    M1 fact set is time-derived).

    M1 scope (backend-01 §6): Cisco IOS only, end to end. Any other
    fingerprinted platform — or a Cisco IOS rulepack that was not supplied
    fully loaded in `knowledge_base` — raises a clear "not yet supported"
    error rather than silently producing an empty assessment (G2: never
    over-claim by pretending to have assessed something that was not
    assessed).
    """

    from nsca_engine.controls import evaluate as controls_evaluate
    from nsca_engine.extract import runtime as extract_runtime
    from nsca_engine.ingest import completeness as ingest_completeness
    from nsca_engine.parse import effective_config
    from nsca_engine.parse.paradigms import (
        block_keyword,
        brace,
        cloud_json,
        flat_path,
        indentation,
        path_header,
    )
    from nsca_engine.parse.paradigms import (
        xml as xml_paradigm,
    )
    # Fact/Provenance/ProvenanceSource are already module-level names (the
    # M5 re-export block above) — no local re-import needed here.

    if not artifacts:
        raise ValueError("assess_device requires at least one artifact")

    primary = artifacts[0]
    text = _normalise_text(primary.content)

    # -- Fingerprint (TRD-01.2) ----------------------------------------------
    # Delegates to `fingerprint_artifact` (below) so the scoring/decision
    # logic has exactly one implementation, used both here and by Track B's
    # ingestion-time classification.
    loaded_rulepacks = tuple(
        rp.loaded for rp in knowledge_base.rulepacks if rp.loaded is not None
    )
    if not loaded_rulepacks:
        raise NotImplementedError(
            "assess_device: no fully-loaded rulepack was supplied in "
            "knowledge_base.rulepacks (every Rulepack.loaded is None)."
        )

    fingerprint = fingerprint_artifact(primary.content, knowledge_base)
    if fingerprint is None:
        raise NotImplementedError(
            "assess_device: fingerprint outcome was not KNOWN — only a "
            "confidently-identified, fully-loaded-rulepack platform is "
            "assessed."
        )
    platform = fingerprint.platform
    os_version = fingerprint.os_version
    rulepack = next(lrp for lrp in loaded_rulepacks if lrp.platform == platform)

    # -- Parse (TRD-02.1) ------------------------------------------------------
    # Dispatch to the structural paradigm this platform's rulepack declares
    # (backend-01 M2 — "adding a paradigm is one structurer, not a whole
    # parser", TRD-02.1 §3.2 DD-02.1-01). Every paradigm module shares the
    # exact same `parse(artifact_id, text, grammar) -> ParseResult` shape.
    paradigm_module = {
        "indentation": indentation,
        "flat_path": flat_path,
        "brace": brace,
        "block_keyword": block_keyword,
        "xml": xml_paradigm,
        "path_header": path_header,
        "cloud_json": cloud_json,
    }.get(rulepack.paradigm)
    if paradigm_module is None:  # pragma: no cover - guarded at rulepack load
        raise NotImplementedError(
            f"assess_device: unsupported grammar paradigm {rulepack.paradigm!r}"
        )

    parse_result = paradigm_module.parse(primary.id, text, rulepack.grammar)
    if parse_result.status == "refused":
        raise NotImplementedError(
            "assess_device: grammar coverage below the refusal threshold, "
            "or a contaminating structural error (TRD-02.1 DD-02.1-03/04) "
            "— device not assessed."
        )

    # -- Effective configuration resolution (TRD-02.3) ----------------------
    # `effective_config.resolve` only special-cases Cisco's `vty_range`
    # context (M1 scope) and is a no-op (empty `vty_instances`) for every
    # other paradigm's tree — safe to call unconditionally.
    effective = effective_config.resolve(parse_result.tree)

    # -- Extract (TRD-03.1 / TRD-03.2) --------------------------------------
    extraction = extract_runtime.extract(
        parse_result.tree, effective, rulepack.extractors, primary.id,
        rulepack.lookup_tables,
    )
    derived = extract_runtime.compute_derived_facts(extraction.facts, primary.id)

    native_controls = _all_native_controls(knowledge_base)
    needed_base_paths = frozenset(
        p for c in native_controls for p in c.requires_facts
    )
    combined_so_far = extraction.facts + derived
    resolved_defaults = extract_runtime.resolve_needed_facts(
        combined_so_far, needed_base_paths, rulepack.defaults,
        platform, os_version, primary.id,
    )

    export_mode_result = ingest_completeness.detect_export_mode(text, ())
    export_mode_fact = Fact(
        path="device.config_export_mode",
        value=export_mode_result.mode.name.lower(),
        type="enum",
        provenance=Provenance(source=ProvenanceSource.DERIVED),
    )

    # -- Graph-relevant facts (TRD-04.1 input side, M3) ----------------------
    # Cisco IOS is the one platform with a dedicated code-based extractor for
    # ACLs/object-groups/interfaces/routes (extract/cisco_acl.py — see that
    # module's docstring for why this isn't expressed as YAML-declared
    # extractors). Every other platform's graph contribution is built from
    # whatever its own rulepack already extracts (graph/build.py's minimal
    # path) — no additional facts are synthesised for them here.
    graph_facts: tuple[Fact, ...] = ()
    if platform == "cisco_ios":
        from nsca_engine.extract import cisco_acl

        graph_facts = cisco_acl.extract_graph_facts(parse_result.tree, primary.id)

    # -- Chassis-serial extraction (05-security-baseline-model.md §4.1,
    # FR-RPT-002/003, FR-ING-010) --------------------------------------------
    # `device.serials[]` is populated from `show version`/`show inventory`
    # artifacts, never from the running configuration (the doc's own
    # explicit callout — a chassis serial simply does not appear in `show
    # running-config` output). Every artifact this device was assessed with
    # is examined here, not just `primary` — a serial-bearing artifact is
    # very often *not* the primary one (a directory-per-device upload of
    # `running-config.txt` + `show-version.txt` sorts the config first,
    # TRD-01.1 §3.2). `show inventory` output (multi-component, more
    # granular) is preferred over `show version`'s single chassis-only line
    # when both are present for this device; `show version` is used only as
    # a fallback. Cisco IOS only this milestone (see
    # `extract/cisco_inventory.py` module docstring) — flagged, not silently
    # extended to other platforms without a real per-platform extractor.
    device_serials: tuple[DeviceSerial, ...] = ()
    serial_facts: tuple[Fact, ...] = ()
    if platform == "cisco_ios":
        from nsca_engine.extract import cisco_inventory

        inventory_hits: list[cisco_inventory.InventoryExtraction] = []
        version_hits: list[cisco_inventory.InventoryExtraction] = []
        for art in artifacts:
            art_text = _normalise_text(art.content)
            hint = art.artifact_type_hint
            if hint == ArtifactType.SHOW_INVENTORY or (
                hint is None and cisco_inventory.looks_like_show_inventory(art_text)
            ):
                inventory_hits.append(cisco_inventory.extract_show_inventory(art_text, art.id))
            elif hint == ArtifactType.SHOW_VERSION or (
                hint is None and cisco_inventory.looks_like_show_version(art_text)
            ):
                version_hits.append(cisco_inventory.extract_show_version_serial(art_text, art.id))

        chosen = inventory_hits if any(h.serials for h in inventory_hits) else version_hits
        for hit in chosen:
            device_serials += hit.serials
            serial_facts += hit.facts

    all_facts = (
        combined_so_far + resolved_defaults + (export_mode_fact,) + graph_facts + serial_facts
    )
    all_facts = tuple(sorted(all_facts, key=lambda f: f.path))

    if device_serials:
        fingerprint = replace(fingerprint, serials=device_serials)

    # -- Evaluate (TRD-05.2) -------------------------------------------------
    control_lookup = {c.control_id: c for c in native_controls}
    lookup_tables: dict[str, Any] = {}
    for cp in knowledge_base.control_packs:
        if cp.loaded is not None:
            lookup_tables.update(cp.loaded.lookup_tables)

    results = tuple(
        controls_evaluate.evaluate_control(c, all_facts, platform, lookup_tables)
        for c in native_controls
    )
    summary = controls_evaluate.summarize(results)
    findings = controls_evaluate.to_device_findings(results, control_lookup, all_facts)
    scores = controls_evaluate.to_device_scores(summary)

    # -- Per-device graph contribution (TRD-04.1, M3) ------------------------
    from nsca_engine.graph import build as graph_build

    graph_contribution = graph_build.device_graph_contribution(primary.id, platform, all_facts)

    return DeviceAssessment(
        fingerprint=fingerprint,
        facts=all_facts,
        unmatched_constructs=extraction.unmatched,
        graph_contribution=graph_contribution,
        findings=findings,
        grammar_coverage=parse_result.coverage,
        scores=scores,
    )


def _compute_scope_contamination(
    device_assessments: tuple[DeviceAssessment, ...],
    knowledge_base: KnowledgeBase,
    attack_paths: tuple[AttackPath, ...],
) -> tuple[ContaminationNote, ...]:
    """Scope-contamination annotations (FR-GRF-004, FR-RSK-008;
    05-security-baseline-model.md §4.10, TRD-05.2 §3.6, TRD-03.3 §3.8).

    TRD-05.2 §3.6's literal algorithm contaminates every PASS verdict whose
    control shares a *family* with an unaudited fact's registered schema
    *category*. That precise linkage isn't available here:
    `UnmatchedConstruct` (the only "unaudited surface" signal a
    `DeviceAssessment` carries) has no `category` field yet — that mapping
    belongs to `extract/capability_surface.py` (module layout in
    backend-01 §3), which hasn't been built. Two coarser, documented triggers
    stand in for it (flagged, not silently narrowed):

    1. **Unaudited surface, device-scoped.** Any device with >=1
       `unmatched_constructs` contaminates *every* PASS finding on that
       device — coarser than family-scoped (TRD-05.2 §3.6), because the
       family link isn't available, but honest about direction (only PASS,
       per DD-05.2-03).
    2. **Graph-level counterexample elsewhere in the estate.** A device that
       appears as a step in a computed `AttackPath` (i.e. TRD-04.2 found a
       concrete reachable route touching it) contaminates its PASS findings
       in the `management_plane` family — a PASS on "this device's
       management access is fine" is undercut by a live route into it found
       elsewhere in the estate.
    """

    native_controls = _all_native_controls(knowledge_base)
    family_by_control = {c.control_id: c.family for c in native_controls}

    path_touched_devices: set[str] = {
        step.device_id for path in attack_paths for step in path.steps
    }

    notes: list[ContaminationNote] = []
    for da in sorted(device_assessments, key=lambda d: d.graph_contribution.device_id):
        device_id = da.graph_contribution.device_id
        unmatched_count = len(da.unmatched_constructs)
        on_touched_path = device_id in path_touched_devices

        for finding in sorted(da.findings, key=lambda f: f.control_id):
            if finding.verdict != Verdict.PASS:
                continue  # DD-05.2-03: contamination affects PASS only

            if unmatched_count > 0:
                notes.append(
                    ContaminationNote(
                        device_id=device_id, control_id=finding.control_id,
                        reason=(
                            f"unaudited capability surface: {unmatched_count} parsed "
                            f"construct(s) on this device have no extractor mapping "
                            f"(device-scoped approximation of TRD-05.2 §3.6's "
                            f"family-scoped contamination — see api.py docstring)"
                        ),
                    )
                )
                continue

            if on_touched_path and family_by_control.get(finding.control_id) == "management_plane":
                notes.append(
                    ContaminationNote(
                        device_id=device_id, control_id=finding.control_id,
                        reason=(
                            "graph-level counterexample: this device is reachable via "
                            "a computed attack path elsewhere in the estate; this "
                            "management_plane PASS should be reviewed against that route"
                        ),
                    )
                )

    return tuple(notes)


def assess_campaign(
    device_assessments: tuple[DeviceAssessment, ...],
    knowledge_base: KnowledgeBase,
) -> CampaignAssessment:
    """Run the campaign-wide pass (estate graph merge, reachability,
    exposure weighting, attack paths, peer anomaly, systemic clustering)
    over every device assessment collected so far.

    Pure function, same determinism guarantee as `assess_device`. No
    `assessed_at` parameter — this stage doesn't stamp anything with a
    time; the per-device `assessed_at` values already carried by each
    `DeviceAssessment`'s facts are sufficient.

    M4 (backend-01 §6): builds on M3's `graph/build.merge_estate`,
    `graph/reachability.query*` and `graph/exposure.classify_estate`, plus
    the new `risk/severity.py`, `risk/attack_paths.py` and `risk/anomaly.py`
    modules (TRD-06.1/06.2/06.3).
    """

    from nsca_engine.graph import build as graph_build
    from nsca_engine.graph import exposure as graph_exposure
    from nsca_engine.risk import anomaly as risk_anomaly
    from nsca_engine.risk import attack_paths as risk_attack_paths
    from nsca_engine.risk import severity as risk_severity

    graph = graph_build.merge_estate(device_assessments)
    exposures = graph_exposure.classify_estate(graph)

    effective_severities = risk_severity.compute_effective_severities(
        device_assessments, exposures,
    )
    attack_paths = risk_attack_paths.compute_attack_paths(
        device_assessments, graph, exposures,
    )
    peer_anomalies = risk_anomaly.detect_peer_anomalies(device_assessments, exposures)
    systemic_findings = risk_anomaly.detect_systemic(device_assessments)
    scope_contamination = _compute_scope_contamination(
        device_assessments, knowledge_base, attack_paths,
    )

    return CampaignAssessment(
        graph=graph,
        effective_severities=effective_severities,
        scope_contamination=scope_contamination,
        attack_paths=attack_paths,
        peer_anomalies=peer_anomalies,
        systemic_findings=systemic_findings,
    )
