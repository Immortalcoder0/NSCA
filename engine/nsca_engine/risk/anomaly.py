"""Peer anomaly detection and systemic-finding clustering (TRD-06.3).

Scope note on peer anomaly's "structural mode" (flagged, not silently
narrowed): TRD-06.3 §3.3's flagship claim is that structural-mode anomaly
detection works on a platform the system was **never taught** — no facts, no
controls, parse tree only (V-06.3-001: "Coverage 0%. Zero facts extracted.
Zero controls evaluated."). That scenario is unreachable through the current
`api.py` pipeline as built in M0-M3: `assess_device` raises
`NotImplementedError` for any artifact whose fingerprint isn't a confidently
identified, fully-loaded rulepack (see that function's own docstring) — so no
`DeviceAssessment` is ever produced for an untaught platform in the first
place, and this module (which only ever sees `DeviceAssessment` objects, per
`assess_campaign`'s signature) cannot detect anomalies on data that was never
allowed to reach it. Fixing this is a pipeline-level change (letting
`assess_device` return a minimal parse-tree-only assessment for an
unidentified-but-parseable platform) out of this milestone's scope. This
module therefore implements TRD-06.3's **semantic mode** (§3.3: "compares
resolved fact values directly") over every taught platform's `Fact` paths,
using presence/absence of each *normalised path* (bracket indices collapsed,
values excluded — the closest available approximation to "shape, not value"
given only `Fact` tuples, not parse trees, are available here) as the
comparison element. Flagged in the M4 report as a genuine gap versus
TRD-06.3's stated ambition, not a silent narrowing.

Systemic clustering (§4) is implemented per TRD-06.3 §4.2 literally,
including its explicitly specified threshold — this is *not* one of the
"propose a default" open questions from backend-01 §8, because TRD-06.3 §4.2
already states it:

    systemic(cluster) = |cluster| >= max(5, 0.20 * platform_device_count)
                         and evidence patterns identical after normalisation

Determinism (§4.6/TRD-06.3 §3.x): sorted iteration throughout, stable cluster
ids derived from the cluster key (never from insertion order), and
`fractions.Fraction` for the proportional threshold (D5) — never float.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING

from nsca_engine.graph.exposure import ExposureResult
from nsca_engine.types import DeviceFinding, Fact, Verdict

if TYPE_CHECKING:
    from nsca_engine.api import DeviceAssessment, PeerAnomaly, SystemicFindingCandidate

LOW = Fraction(15, 100)
HIGH = Fraction(85, 100)
MIN_GROUP_SIZE = 5

_BRACKET_IDX = re.compile(r"\[\d+\]")


def _normalise_path(path: str) -> str:
    return _BRACKET_IDX.sub("[]", path)


def _major_version(os_version: str | None) -> str | None:
    if not os_version:
        return None
    return os_version.split(".")[0]


@dataclass(frozen=True, slots=True)
class PeerGroup:
    key: tuple[str, str | None, str | None]  # (platform, major_version, exposure)
    device_ids: tuple[str, ...]
    analysed: bool
    reason: str | None


def _signature(facts: tuple[Fact, ...]) -> frozenset[str]:
    """Semantic-mode signature (TRD-06.3 §3.3: "compares resolved fact
    values directly" — this module's documented substitute for the
    parse-tree-only structural mode, see module docstring). Each element is
    ``"normalised_path=value"`` for every ``EXPLICIT`` fact: restricting to
    explicitly-configured facts keeps common-default/derived paths every
    device shares from drowning out genuine per-device configuration shape;
    including the value (rather than path alone) is what lets this catch a
    same-shaped-but-differently-set line (e.g. `transport input telnet ssh`
    vs `transport input ssh` — same fact path, different resolved value)."""

    from nsca_engine.types import ProvenanceSource

    return frozenset(
        f"{_normalise_path(f.path)}={f.value!r}" for f in facts
        if f.provenance.source == ProvenanceSource.EXPLICIT
    )


def peer_groups(
    device_assessments: tuple[DeviceAssessment, ...],
    exposures: Mapping[str, ExposureResult],
) -> tuple[PeerGroup, ...]:
    by_key: dict[tuple[str, str | None, str | None], list[str]] = {}
    for da in device_assessments:
        device_id = da.graph_contribution.device_id
        exposure = exposures.get(device_id)
        key = (
            da.fingerprint.platform,
            _major_version(da.fingerprint.os_version),
            exposure.classification if exposure is not None else None,
        )
        by_key.setdefault(key, []).append(device_id)

    groups = []
    for key in sorted(by_key, key=lambda k: (k[0], k[1] or "", k[2] or "")):
        members = tuple(sorted(by_key[key]))
        analysed = len(members) >= MIN_GROUP_SIZE
        reason = None if analysed else f"peer group has {len(members)} member(s), below the minimum of {MIN_GROUP_SIZE} (DD-06.3-01)"
        groups.append(PeerGroup(key=key, device_ids=members, analysed=analysed, reason=reason))
    return tuple(groups)


def detect_peer_anomalies(
    device_assessments: tuple[DeviceAssessment, ...],
    exposures: Mapping[str, ExposureResult],
) -> tuple[PeerAnomaly, ...]:
    from nsca_engine.api import PeerAnomaly

    facts_by_device = {da.graph_contribution.device_id: da.facts for da in device_assessments}
    signature_by_device = {dev: _signature(facts) for dev, facts in facts_by_device.items()}

    out: list[PeerAnomaly] = []
    for group in peer_groups(device_assessments, exposures):
        if not group.analysed:
            continue

        signatures = {dev: signature_by_device[dev] for dev in group.device_ids}
        universe = sorted(frozenset().union(*signatures.values())) if signatures else []
        if not universe:
            continue

        prevalence: dict[str, Fraction] = {
            elem: Fraction(sum(1 for dev in group.device_ids if elem in signatures[dev]), len(group.device_ids))
            for elem in universe
        }

        # §6 edge case: every device identical -> uniform, no anomalies.
        if all(p in (Fraction(0), Fraction(1)) for p in prevalence.values()):
            continue

        # §6 edge case: no modal signature at all (every device pairwise
        # distinct, i.e. no element shared by a majority) -> heterogeneous,
        # no anomalies emitted.
        if not any(p >= Fraction(1, 2) for p in prevalence.values()):
            continue

        for dev in group.device_ids:
            sig = signatures[dev]
            deviations = []
            for elem in universe:
                p = prevalence[elem]
                if elem in sig and p < LOW:
                    deviations.append((elem, p, True))
                elif elem not in sig and p > HIGH:
                    deviations.append((elem, p, False))
            for elem, p, present_here in sorted(deviations):
                platform, major_version, exposure_cls = group.key
                where = "present here" if present_here else "absent here"
                pct = f"{p.numerator}/{p.denominator}"
                out.append(
                    PeerAnomaly(
                        device_id=dev,
                        fact_path=elem,
                        peer_group_platform=platform,
                        description=(
                            f"Differs from {len(group.device_ids) - 1} structurally similar "
                            f"{platform} peers: {where} {elem!r} (prevalence {pct} in group). "
                            f"Direction: undetermined (DD-06.3-02) — this is a deviation, "
                            f"not a compliance finding."
                        ),
                    )
                )

    out.sort(key=lambda a: (a.device_id, a.fact_path))
    return tuple(out)


# ---------------------------------------------------------------------------
# Systemic finding clustering (TRD-06.3 §4)
# ---------------------------------------------------------------------------

_QUOTED = re.compile(r'"[^"]*"|\'[^\']*\'')
_IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
_NUMBER = re.compile(r"\b\d+\b")


def _normalise_evidence(text: str) -> str:
    """TRD-06.3 §4.2: "addresses, hostnames, numbers and quoted strings" ->
    slots. Hostname normalisation is deliberately not attempted here (no
    reliable, low-false-positive heuristic for "is this token a hostname"
    without a schema of what a hostname looks like on this platform) —
    flagged as a narrower-than-spec normalisation, safer to under-normalise
    (miss a systemic cluster) than to over-merge unrelated findings."""

    text = _QUOTED.sub("<STR>", text)
    text = _IPV4.sub("<ADDR>", text)
    text = _NUMBER.sub("<NUM>", text)
    return text


def _evidence_pattern(finding: DeviceFinding) -> str:
    # Deliberately excludes `Evidence.artifact_id` — that's the raw
    # artifact/device identifier, exactly the kind of per-device identity
    # TRD-06.3 §4.2's normalisation is designed to strip (it also carries no
    # signal: two devices with the *same* defect never share an artifact
    # id). `fact_paths` is kept (unaffected by normalisation) since it names
    # *which* fact drove the finding, which is part of the pattern's shape.
    parts = [
        f"{','.join(e.fact_paths)}:{_normalise_evidence(e.excerpt)}" for e in finding.evidence
    ]
    return "|".join(sorted(parts))


@dataclass(frozen=True, slots=True)
class _Cluster:
    control_id: str
    platform: str
    evidence_pattern: str
    device_ids: tuple[str, ...]
    unaffected_peers: tuple[str, ...]
    corroborating_signals: tuple[str, ...]


def _confidence_label(signal_count: int) -> str:
    if signal_count >= 4:
        return "probable"
    if signal_count >= 2:
        return "possible"
    return "cluster_only"


def detect_systemic(
    device_assessments: tuple[DeviceAssessment, ...],
) -> tuple[SystemicFindingCandidate, ...]:
    from nsca_engine.api import SystemicFindingCandidate

    platform_by_device = {
        da.graph_contribution.device_id: da.fingerprint.platform for da in device_assessments
    }
    os_version_by_device = {
        da.graph_contribution.device_id: da.fingerprint.os_version for da in device_assessments
    }
    platform_device_count: dict[str, int] = {}
    for platform in platform_by_device.values():
        platform_device_count[platform] = platform_device_count.get(platform, 0) + 1

    # cluster_key -> (device_ids seen, one representative finding)
    clusters: dict[tuple[str, str, str], list[str]] = {}
    for da in device_assessments:
        device_id = da.graph_contribution.device_id
        platform = platform_by_device[device_id]
        for finding in da.findings:
            if finding.verdict != Verdict.FAIL:
                continue
            key = (finding.control_id, platform, _evidence_pattern(finding))
            clusters.setdefault(key, []).append(device_id)

    out: list[SystemicFindingCandidate] = []
    for key in sorted(clusters):
        control_id, platform, pattern = key
        members = tuple(sorted(clusters[key]))
        platform_count = platform_device_count.get(platform, 0)
        threshold = max(Fraction(MIN_GROUP_SIZE), Fraction(1, 5) * Fraction(platform_count))
        if Fraction(len(members)) < threshold:
            continue

        all_platform_devices = sorted(
            d for d, p in platform_by_device.items() if p == platform
        )
        unaffected = tuple(d for d in all_platform_devices if d not in members)

        # Corroborating signals (§4.3) computable from what's on hand today:
        signals: list[str] = ["identical normalised evidence pattern"]
        os_versions = {os_version_by_device.get(d) for d in members}
        if len(os_versions) == 1 and None not in os_versions:
            signals.append(f"identical OS version ({next(iter(os_versions))}) across all affected devices")

        is_platform_default = len(members) == platform_count and len(unaffected) == 0
        confidence = _confidence_label(len(signals))

        if is_platform_default:
            hypothesis = (
                f"{control_id} fails identically on all {len(members)} of {len(members)} "
                f"{platform} devices in this campaign. This matches a platform-default "
                f"pattern (TRD-06.3 §6) rather than a build-template defect: every device "
                f"of this platform fails the same way, with none to compare against."
            )
        elif confidence == "probable":
            hypothesis = (
                f"{control_id} fails identically on {len(members)} of {platform_count} "
                f"{platform} devices. Probable common root cause (build-template defect), "
                f"based on {len(signals)} corroborating signals: {', '.join(signals)}."
            )
        elif confidence == "possible":
            hypothesis = (
                f"{control_id} fails identically on {len(members)} of {platform_count} "
                f"{platform} devices. Possible common origin, based on "
                f"{len(signals)} corroborating signals: {', '.join(signals)}."
            )
        else:
            hypothesis = (
                f"{control_id} fails identically on {len(members)} of {platform_count} "
                f"{platform} devices. Reported as a cluster with no root-cause hypothesis "
                f"(only one corroborating signal available)."
            )

        if unaffected:
            hypothesis += (
                f" {len(unaffected)} unaffected peer(s) should be verified to confirm "
                f"they were built from a corrected/different template: "
                f"{', '.join(unaffected)}."
            )

        out.append(
            SystemicFindingCandidate(
                control_id=control_id, device_ids=members, description=hypothesis,
            )
        )

    out.sort(key=lambda c: (-len(c.device_ids), c.control_id))
    return tuple(out)
