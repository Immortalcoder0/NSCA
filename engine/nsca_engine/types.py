"""Core dataclasses for the Security Baseline Model and the engine's internal
vocabulary.

Every type here is ``frozen=True, slots=True`` — the pattern used throughout
``nsca_engine`` (see TECH-STACK.md §3 and backend-01 §3). Frozen makes every
engine value hashable-safe and immutable, which is what makes "calling
``assess_device`` twice with identical arguments returns byte-for-byte
identical results" (00-master-plan.md §5.1) checkable by ``==`` in the first
place — a mutable dataclass would let a caller invalidate that guarantee by
accident. ``slots`` keeps large fact sets (tens of thousands of ``Fact``
instances per device on a 500k-line config, TECH-STACK.md §3) memory-cheap.

Determinism rules that apply to every type in this module (backend-01 §2.1,
TRD-00 §7):

- No ``random``, no ``time.time()``/``datetime.now()`` anywhere in this
  package. Timestamps are always caller-supplied.
- No ``float`` for any ratio/score. Use ``fractions.Fraction`` (D5) — a float
  ratio silently renders differently across platforms/library versions at
  boundary values, which breaks the byte-identical output guarantee (G1).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum, StrEnum, auto
from fractions import Fraction
from typing import Any

# ---------------------------------------------------------------------------
# Provenance and facts
# ---------------------------------------------------------------------------


class ProvenanceSource(StrEnum):
    """The six (plus `derived`) provenance source classifications from
    05-security-baseline-model.md §3.1 / §5 and 14-data-model.md §2.

    This enum *is* the mechanism that lets the system say "I do not know"
    instead of silently defaulting to compliant (SBM-3). Downstream trust
    differs per member — see the doc's table — and ``default_unknown`` is
    what structurally forces a dependent control's verdict to UNKNOWN
    (backend-01 §5.4, V-05.2-004), never something a code path "remembers"
    to check.
    """

    EXPLICIT = "explicit"
    DEFAULT_KNOWN = "default_known"
    DEFAULT_INFERRED = "default_inferred"
    INHERITED = "inherited"
    DEFAULT_UNKNOWN = "default_unknown"
    NOT_APPLICABLE = "not_applicable"
    DERIVED = "derived"


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where a `Fact`'s value came from (05-security-baseline-model.md §3,
    14-data-model.md §2 FACT entity).

    ``layer`` is populated only when ``source == INHERITED`` (which layer —
    template, device-group, shared — produced the value, TRD-02.3).
    ``depends_on`` is populated only when ``source == DERIVED``, and per
    05-security-baseline-model.md §5 a derived fact's provenance must be the
    *weakest* of the facts it depends on — that rule is enforced by whatever
    constructs the derived Fact, not by this dataclass itself.
    """

    source: ProvenanceSource
    artifact_id: str | None = None
    lines: tuple[int, ...] = ()
    excerpt: str | None = None
    extractor: str | None = None
    confidence: Fraction | None = None
    layer: str | None = None
    depends_on: tuple[str, ...] = ()
    # Version-ranged/documented-default citation, for default_known facts —
    # "an auditor may be challenged on a finding derived from a default...
    # and must be able to say where the default came from" (07-vendor-
    # rulepacks.md §6).
    default_source: str | None = None
    platform: str | None = None
    version_range: str | None = None


@dataclass(frozen=True, slots=True)
class Fact:
    """The atomic unit of the Security Baseline Model
    (05-security-baseline-model.md §3, 14-data-model.md §2 FACT entity).

    ``value`` is intentionally ``Any`` here — the schema registry (not this
    dataclass) is the source of truth for what type a given ``path`` must
    hold (TRD-03.3 §3.3); enforcing that at construction time would require
    threading the registry through every extractor call. ``value is None``
    is the structural representation of ⊥ (unknown), mirroring the JSONB
    ``NULL`` design called out in TECH-STACK.md §5 ("NULL = ⊥, never
    confusable with false").
    """

    path: str
    value: Any
    type: str
    provenance: Provenance


# ---------------------------------------------------------------------------
# Verdicts
# ---------------------------------------------------------------------------


class Verdict(Enum):
    """Three-valued (Kleene) logic outcome of evaluating a control against a
    device's facts, plus NOT_APPLICABLE for controls that don't apply to
    this device's capability surface (TRD-05.1/05.2, TECH-STACK.md §7, C4).

    Deliberately not a StrEnum: verdict values participate in Kleene
    logic operations (``true and UNKNOWN == UNKNOWN``) that are easy to get
    subtly wrong if the enum silently coerces to a comparable string
    elsewhere in the codebase. Keep it an opaque, explicit token.
    """

    PASS = auto()
    FAIL = auto()
    UNKNOWN = auto()
    NOT_APPLICABLE = auto()


class ArtifactType(Enum):
    """Kinds of artifact the engine can be handed, per
    14-data-model.md §2 ARTIFACT entity (`artifact_type` field)."""

    RUNNING_CONFIG = auto()
    SHOW_VERSION = auto()
    SHOW_INVENTORY = auto()
    CLOUD_POLICY = auto()
    TECH_SUPPORT_BUNDLE = auto()
    UNKNOWN = auto()


# ---------------------------------------------------------------------------
# Fingerprinting
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeviceSerial:
    """One `{component, serial}` pair (05-security-baseline-model.md §4.1)."""

    component: str
    serial: str


@dataclass(frozen=True, slots=True)
class FingerprintResult:
    """Output of the fingerprinting stage (TRD-01.2): `(vendor, platform,
    os_version, model, serials[])` plus a confidence score
    (07-vendor-rulepacks.md §3).
    """

    vendor: str
    platform: str
    os_version: str | None
    model: str | None
    serials: tuple[DeviceSerial, ...]
    confidence: Fraction


# ---------------------------------------------------------------------------
# Findings and coverage
# ---------------------------------------------------------------------------


class Severity(StrEnum):
    """Control-defined severity band (05-security-baseline-model.md §8:
    "Control-defined; platform severities mapped, never inherited raw").
    Exact bands aren't specified anywhere in the read docs beyond the
    conventional set — flagged as an open judgment call in the final
    report.
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class PassQuality(StrEnum):
    """When `verdict == PASS`, whether the pass is meaningful or vacuous
    (14-data-model.md §2 FINDING entity `pass_quality` field)."""

    MEANINGFUL = "meaningful"
    VACUOUS = "vacuous"


class UnknownReason(StrEnum):
    """Why a finding resolved to UNKNOWN (14-data-model.md §2 FINDING
    entity `unknown_reason` field)."""

    FACTS_MISSING = "facts_missing"
    DEFAULT_UNKNOWN = "default_unknown"
    PARSE_GAP = "parse_gap"
    EXPORT_INCOMPLETE = "export_incomplete"
    DATA_NOT_COLLECTED = "data_not_collected"


@dataclass(frozen=True, slots=True)
class Evidence:
    """One evidentiary excerpt backing a finding (14-data-model.md §2
    EVIDENCE entity), minus the parts (owner, lifecycle) that belong to
    Track B."""

    artifact_id: str
    lines: tuple[int, ...]
    highlight_lines: tuple[int, ...]
    excerpt: str
    fact_paths: tuple[str, ...]
    counterexample: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class DeviceFinding:
    """Per-device, per-control finding
    (backend-01 §4.1, 14-data-model.md §2 FINDING entity), minus the
    fields that belong to Track B (owner, due date, lifecycle state,
    dispute, campaign id).

    ``severity`` is **base** severity only — exposure-weighted **effective**
    severity is a campaign-wide computation (backend-01 §4.1) and lives on
    `CampaignAssessment.effective_severities` in `api.py`, keyed by
    `FindingKey`, not here.
    """

    control_id: str
    verdict: Verdict
    pass_quality: PassQuality | None
    unknown_reason: UnknownReason | None
    severity: Severity
    severity_reason: str | None
    evidence: tuple[Evidence, ...]
    framework_refs: tuple[str, ...]
    contamination_reason: str | None
    coverage_inputs: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class FindingKey:
    """Identity of a finding for cross-structure lookups, mirroring
    14-data-model.md §2's `identity_key = (device, control)`. Used as the
    key type for `CampaignAssessment.effective_severities`."""

    device_id: str
    control_id: str


@dataclass(frozen=True, slots=True)
class DeviceScores:
    """Per-device scoring block (14-data-model.md §2 ASSESSMENT entity).

    All ratios are `Fraction`, never `float` — D5. A float here would
    silently render `112/143` as `78%` on one run and `79%` on another at
    boundary values (TECH-STACK.md §14).
    """

    compliance_score: Fraction
    coverage_score: Fraction
    meaningful_ratio: Fraction
    security_score: Fraction
    pass_count: int = 0
    fail_count: int = 0
    unknown_count: int = 0
    not_applicable_count: int = 0
    partial_count: int = 0


# ---------------------------------------------------------------------------
# Unmatched constructs (→ Track B's learning queue)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UnmatchedConstruct:
    """A parsed construct with no extractor mapping — routed to Track B's
    learning queue (backend-01 §4.1, 14-data-model.md §2 ASSESSMENT entity
    `unmatched_constructs[]`)."""

    artifact_id: str
    lines: tuple[int, ...]
    excerpt: str
    parse_path: tuple[str, ...]


# ---------------------------------------------------------------------------
# Graph fragments (per-device contribution; full Graph type is graph/build.py's)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GraphNode:
    """One node contributed by a device to the estate graph
    (TRD-04.1). Kept intentionally small in M0 — the graph module itself
    (Phase 1, M3) owns richer node semantics; this is the shape the engine
    contract (`GraphFragment`) commits to today."""

    node_id: str
    device_id: str
    kind: str
    attrs: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """One edge contributed by a device to the estate graph (TRD-04.1)."""

    source_id: str
    target_id: str
    kind: str
    attrs: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphFragment:
    """This device's nodes/edges only (backend-01 §4.1) — the campaign-wide
    merge into the full estate `Graph` happens in `assess_campaign`
    (graph/build.py, TRD-04.1), not here. Node/edge tuples are kept in
    sorted order by the producer (D6/D7): no dict/set iteration order is
    ever relied upon downstream.
    """

    device_id: str
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
