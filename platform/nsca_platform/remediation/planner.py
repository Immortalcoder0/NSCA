"""Remediation planner — TRD-07.1, backend-02 §4.4, M4.

Version-specific (`(control, platform, version_range)`-keyed) selection,
dependency ordering, impact classification. Content lives in the control
pack YAML's own `remediation:` block per control
(`knowledge/control_packs/nsca_native.yaml`), read here with a small,
private `yaml.safe_load()` reader — **never** via
`nsca_engine.controls.rulepack_loader`, which is sanctioned by backend-02
§2.2 for round-trip verification tests only. `load_control_pack` (Track A's
real loader) was verified empirically to ignore unknown top-level keys on a
control entry (`c.get(...)` throughout), so adding a `remediation:` block to
the same YAML files Track A parses is safe and does not require a second
copy of the content.

**DD-07.1-01 — classification is authored on the control, not inferred.**
This module trusts the YAML's `impact` field verbatim; it does not attempt
to guess `lockout_risk` from command text. A step with no declared `impact`
defaults to `lockout_risk` (the conservative failure mode — never silently
downgrade an unclassified step).

**INV-07.1-01 — no matching version range means refusal, not
approximation.** A `(control, platform)` combination with no authored
remediation content, or whose device version falls outside every declared
`version_range`, is reported in `RemediationPlan.unavailable`, never
approximated from a different platform's or version's commands.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONTROL_PACK_PATHS: tuple[Path, ...] = (
    Path(__file__).resolve().parents[3] / "knowledge" / "control_packs" / "nsca_native.yaml",
    Path(__file__).resolve().parents[3] / "knowledge" / "control_packs" / "nsca_native_m2.yaml",
)


class RemediationContentError(Exception):
    """Raised for a control-authoring defect in remediation content
    (TRD-07.1 §3.4: "Cycles are a control-authoring defect and are rejected
    at load"). Never raised for a device/finding-level condition — those
    are `unavailable[]` entries, not exceptions."""


# ---------------------------------------------------------------------------
# Content model — what's read from YAML
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FactEffect:
    """One declared post-remediation fact mutation (DD-07.1-03: "the plan is
    translated into fact-level effects declared on the control"). `op`
    is either `"set"` (replace the value at `path`) or `"remove_admin"`
    (a narrow, named operation — never a general scripting hook, per
    G4/NFR-SEC-007 — that filters `auth.local_users` down to entries that
    are not both `privilege_level >= 15` and named `admin`)."""

    path: str
    op: str = "set"
    value: Any = None


@dataclass(frozen=True, slots=True)
class RawStepDoc:
    control_id: str
    local_id: int
    cmd: str
    impact: str
    reason: str | None
    depends_on: tuple[int, ...]
    after_control: str | None
    requires_verified: bool
    checkpoint: str | None
    rollback: str | None
    rollback_from_prior_fact: str | None
    fact_effects: tuple[FactEffect, ...]


@dataclass(frozen=True, slots=True)
class VersionBand:
    version_range: str
    steps: tuple[RawStepDoc, ...]
    dry_run_check: Mapping[str, Any] | None


@dataclass(frozen=True, slots=True)
class ControlRemediationContent:
    control_id: str
    remediation_by_platform: Mapping[str, tuple[VersionBand, ...]]
    top_level_dry_run_check: Mapping[str, Any] | None


RemediationLibrary = Mapping[str, ControlRemediationContent]


def _parse_fact_effects(docs: Iterable[Mapping[str, Any]] | None) -> tuple[FactEffect, ...]:
    if not docs:
        return ()
    return tuple(
        FactEffect(path=d["path"], op=d.get("op", "set"), value=d.get("value"))
        for d in docs
    )


def _parse_steps(docs: list[Mapping[str, Any]], control_id: str) -> tuple[RawStepDoc, ...]:
    steps = []
    for d in docs:
        steps.append(
            RawStepDoc(
                control_id=control_id,
                local_id=int(d["id"]),
                cmd=d["cmd"],
                # Unclassified is the conservative default (DD-07.1-01 note above).
                impact=d.get("impact") or "lockout_risk",
                reason=d.get("reason"),
                depends_on=tuple(int(x) for x in d.get("depends_on", [])),
                after_control=d.get("after_control"),
                requires_verified=bool(d.get("requires_verified", False)),
                checkpoint=d.get("checkpoint"),
                rollback=d.get("rollback"),
                rollback_from_prior_fact=d.get("rollback_from_prior_fact"),
                fact_effects=_parse_fact_effects(d.get("fact_effects")),
            )
        )
    return tuple(steps)


def load_remediation_library(
    control_pack_paths: Sequence[Path | str] = DEFAULT_CONTROL_PACK_PATHS,
) -> RemediationLibrary:
    """Reads every control's `remediation:` block (and, for controls with no
    remediation content at all, a bare top-level `dry_run_check:` — see
    NSCA-AUTH-003 in `nsca_native.yaml`) out of the given control pack YAML
    files. Pure file read, no engine import."""

    library: dict[str, ControlRemediationContent] = {}
    for raw_path in control_pack_paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for c in doc.get("controls", []):
            control_id = c["control_id"]
            remediation_doc = c.get("remediation")
            by_platform: dict[str, tuple[VersionBand, ...]] = {}
            if remediation_doc:
                for platform, band_doc in remediation_doc.items():
                    steps = _parse_steps(band_doc.get("steps", []), control_id)
                    band = VersionBand(
                        version_range=band_doc.get("version_range", "*"),
                        steps=steps,
                        dry_run_check=band_doc.get("dry_run_check"),
                    )
                    by_platform[platform] = (band,)
            library[control_id] = ControlRemediationContent(
                control_id=control_id,
                remediation_by_platform=by_platform,
                top_level_dry_run_check=c.get("dry_run_check"),
            )
    return library


def dry_run_check_for(
    library: RemediationLibrary, control_id: str, platform: str, os_version: str | None
) -> Mapping[str, Any] | None:
    """The `dry_run_check` applicable to this control on this device — the
    control's platform/version-scoped band if one matches, else its
    top-level (platform-independent) check, else `None` (unmodelled,
    TRD-07.1 §5)."""

    content = library.get(control_id)
    if content is None:
        return None
    band = _select_band(content, platform, os_version)
    if band is not None and band.dry_run_check is not None:
        return band.dry_run_check
    return content.top_level_dry_run_check


# ---------------------------------------------------------------------------
# Version matching
# ---------------------------------------------------------------------------

_RANGE_TOKEN = re.compile(r"(>=|<=|==|>|<)\s*([0-9]+(?:\.[0-9]+)*)")


def _parse_version(v: str) -> tuple[int, ...]:
    parts = []
    for p in v.strip().split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def _cmp_versions(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def version_in_range(version: str | None, range_expr: str) -> bool:
    """`">=12.0,<15.0"`-style ranges (TRD-07.1 §3.2), AND-combined. `"*"` or
    an empty range always matches (once a version string is present) —
    version PRECISION being insufficient is a separate, upstream refusal
    (TRD-01.2 INV-01.2-01), not this function's job."""

    if version is None:
        return False
    if not range_expr or range_expr.strip() == "*":
        return True
    v = _parse_version(version)
    for op, ver_str in _RANGE_TOKEN.findall(range_expr):
        bound = _parse_version(ver_str)
        c = _cmp_versions(v, bound)
        ok = {
            ">=": c >= 0, "<=": c <= 0, ">": c > 0, "<": c < 0, "==": c == 0,
        }[op]
        if not ok:
            return False
    return True


def _select_band(
    content: ControlRemediationContent, platform: str, os_version: str | None
) -> VersionBand | None:
    bands = content.remediation_by_platform.get(platform, ())
    for band in bands:
        if version_in_range(os_version, band.version_range):
            return band
    return None


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RemediationStep:
    id: int
    control_id: str
    command: str
    impact: str
    reason: str | None
    depends_on: tuple[int, ...]
    requires_verified: bool
    rollback: str | None
    rollback_incomplete: bool
    fact_effects: tuple[FactEffect, ...]
    addresses_findings: tuple[str, ...]
    blocked: bool = False
    blocked_reason: str | None = None


@dataclass(frozen=True, slots=True)
class UnavailableRemediation:
    finding_id: str
    control_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class Checkpoint:
    after_step: int | None
    instruction: str


@dataclass(frozen=True, slots=True)
class ConflictNote:
    fact_path: str
    control_a: str
    control_b: str
    value_a: Any
    value_b: Any
    step_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class RemediationPlan:
    device_id: str
    platform: str
    os_version: str | None
    steps: tuple[RemediationStep, ...]
    unavailable: tuple[UnavailableRemediation, ...]
    checkpoints: tuple[Checkpoint, ...]
    conflicts: tuple[ConflictNote, ...]


# ---------------------------------------------------------------------------
# Dependency ordering — deterministic Kahn's algorithm (D6/D7: no reliance
# on dict/set iteration order; ties broken by a fixed sort key)
# ---------------------------------------------------------------------------

_Node = tuple[str, int]  # (control_id, local_id)


def _topological_order(
    nodes: list[_Node], edges: dict[_Node, set[_Node]]
) -> list[_Node]:
    remaining = {n: set(edges.get(n, set())) for n in nodes}
    order: list[_Node] = []
    ready = sorted(n for n, deps in remaining.items() if not deps)
    placed: set[_Node] = set()
    while ready:
        ready.sort()
        node = ready.pop(0)
        order.append(node)
        placed.add(node)
        del remaining[node]
        newly_ready = []
        for n, deps in remaining.items():
            if node in deps:
                deps.discard(node)
                if not deps and n not in ready:
                    newly_ready.append(n)
        ready.extend(newly_ready)
    if remaining:
        cyclic = ", ".join(f"{c}:{i}" for c, i in sorted(remaining))
        raise RemediationContentError(f"cycle detected among remediation steps: {cyclic}")
    return order


def _detect_conflicts(
    steps_by_node: dict[_Node, RawStepDoc],
) -> tuple[ConflictNote, ...]:
    """TRD-07.1 §5: "Two findings whose remediations conflict → Conflict
    reported; neither auto-resolved; assessor decides." A conflict is two
    steps from *different* controls declaring `op == "set"` on the same
    fact path with different literal values."""

    by_path: dict[str, list[tuple[_Node, RawStepDoc, FactEffect]]] = {}
    for node, step in steps_by_node.items():
        for fe in step.fact_effects:
            if fe.op != "set":
                continue
            by_path.setdefault(fe.path, []).append((node, step, fe))

    conflicts: list[ConflictNote] = []
    for path in sorted(by_path):
        entries = sorted(by_path[path], key=lambda e: e[0])
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                (node_a, step_a, fe_a) = entries[i]
                (node_b, step_b, fe_b) = entries[j]
                if step_a.control_id == step_b.control_id:
                    continue
                if fe_a.value == fe_b.value:
                    continue
                conflicts.append(
                    ConflictNote(
                        fact_path=path,
                        control_a=step_a.control_id, control_b=step_b.control_id,
                        value_a=fe_a.value, value_b=fe_b.value,
                        step_ids=(),  # filled in by caller once global ids are assigned
                    )
                )
    return tuple(conflicts)


def plan(
    findings: Sequence[Mapping[str, Any]],
    *,
    device_id: str,
    platform: str,
    os_version: str | None,
    facts: Mapping[str, Any],
    library: RemediationLibrary | None = None,
    operator_source: str | None = None,
) -> RemediationPlan:
    """TRD-07.1 §4's `plan(findings[], device, operator_source?) →
    RemediationPlan`.

    `findings` is a sequence of `{finding_id, control_id, verdict}` dicts
    (e.g. from `finding_lifecycle.list_findings`). **V-07.1-010**: only
    `verdict == "FAIL"` findings receive remediation — UNKNOWN and
    NOT_APPLICABLE never do ("you cannot fix what you could not
    determine"). Lockout checking (`remediation/lockout.py`) is invoked by
    the caller (not here) — this function's job stops at producing an
    ordered, safety-classified step list plus `unavailable[]`/`conflicts[]`;
    `remediation/dry_run.py` and the lockout check are deliberately separate
    passes over this same `RemediationPlan`, per TRD-07.1 §4's own
    three-part interface.
    """

    if library is None:
        library = load_remediation_library()

    fail_findings = [f for f in findings if f.get("verdict") == "FAIL"]
    fail_findings.sort(key=lambda f: f.get("control", f.get("control_id", "")))
    attempted_control_ids = {f.get("control") or f.get("control_id") for f in fail_findings}

    available: dict[str, tuple[VersionBand, list[str]]] = {}
    unavailable: list[UnavailableRemediation] = []

    for f in fail_findings:
        control_id = f.get("control") or f.get("control_id")
        finding_id = f.get("id") or f.get("finding_id", "")
        content = library.get(control_id)
        if content is None or not content.remediation_by_platform:
            unavailable.append(
                UnavailableRemediation(
                    finding_id=finding_id, control_id=control_id,
                    reason=f"No remediation content exists for {control_id}. "
                           f"The finding stands. Remediation must be determined manually.",
                )
            )
            continue
        band = _select_band(content, platform, os_version)
        if band is None:
            unavailable.append(
                UnavailableRemediation(
                    finding_id=finding_id, control_id=control_id,
                    reason=f"No remediation content exists for {platform} "
                           f"{os_version or '(unknown version)'}. "
                           f"The finding stands. Remediation must be determined manually.",
                )
            )
            continue
        if control_id in available:
            existing_ids = available[control_id][1]
            existing_ids.append(finding_id)
        else:
            available[control_id] = (band, [finding_id])

    # Chain propagation (TRD-07.1 §5: "Remediation whose prerequisite is
    # itself unavailable → whole chain marked unavailable with the root
    # reason"), fixed-point over possibly-nested after_control references.
    # Only fires when the prerequisite control was itself a FAIL finding
    # that failed to get remediation content — an `after_control` naming a
    # control that simply wasn't FAIL at all (already compliant, no
    # remediation needed) is not a broken chain, just no ordering
    # constraint to add.
    changed = True
    while changed:
        changed = False
        for control_id, (band, finding_ids) in list(available.items()):
            for step in band.steps:
                if (
                    step.after_control
                    and step.after_control in attempted_control_ids
                    and step.after_control not in available
                ):
                    for fid in finding_ids:
                        unavailable.append(
                            UnavailableRemediation(
                                finding_id=fid, control_id=control_id,
                                reason=(
                                    f"{control_id}'s remediation depends on {step.after_control}, "
                                    f"which has no available remediation for {platform} "
                                    f"{os_version or '(unknown version)'} — whole chain unavailable."
                                ),
                            )
                        )
                    del available[control_id]
                    changed = True
                    break

    # Build the dependency graph over every selected control's steps.
    steps_by_node: dict[_Node, RawStepDoc] = {}
    findings_by_control: dict[str, tuple[str, ...]] = {}
    for control_id, (band, finding_ids) in available.items():
        findings_by_control[control_id] = tuple(finding_ids)
        for step in band.steps:
            steps_by_node[(control_id, step.local_id)] = step

    edges: dict[_Node, set[_Node]] = {}
    for node, step in steps_by_node.items():
        deps: set[_Node] = {(step.control_id, d) for d in step.depends_on}
        if step.after_control and step.after_control in available:
            other_band = available[step.after_control][0]
            deps |= {(step.after_control, s.local_id) for s in other_band.steps}
        edges[node] = deps

    order = _topological_order(list(steps_by_node.keys()), edges)
    global_id: dict[_Node, int] = {node: i + 1 for i, node in enumerate(order)}

    final_conflicts = tuple(
        ConflictNote(
            fact_path=c.fact_path, control_a=c.control_a, control_b=c.control_b,
            value_a=c.value_a, value_b=c.value_b,
            step_ids=tuple(
                sorted(
                    global_id[n] for n, s in steps_by_node.items()
                    if s.control_id in (c.control_a, c.control_b)
                    and any(fe.path == c.fact_path and fe.op == "set" for fe in s.fact_effects)
                )
            ),
        )
        for c in _detect_conflicts(steps_by_node)
    )
    blocked_nodes: dict[_Node, str] = {}
    for c in final_conflicts:
        for node, step in steps_by_node.items():
            if step.control_id not in (c.control_a, c.control_b):
                continue
            if any(fe.path == c.fact_path and fe.op == "set" for fe in step.fact_effects):
                blocked_nodes[node] = (
                    f"conflicting remediation on fact {c.fact_path!r}: "
                    f"{c.control_a}={c.value_a!r} vs {c.control_b}={c.value_b!r} "
                    f"— neither auto-resolved, assessor decides"
                )

    steps: list[RemediationStep] = []
    checkpoints: list[Checkpoint] = []
    for node in order:
        step = steps_by_node[node]
        gid = global_id[node]
        rollback_text, rollback_incomplete = _resolve_rollback(step, facts)
        is_blocked = node in blocked_nodes
        steps.append(
            RemediationStep(
                id=gid, control_id=step.control_id, command=step.cmd, impact=step.impact,
                reason=step.reason,
                depends_on=tuple(sorted(global_id[(step.control_id, d)] for d in step.depends_on)),
                requires_verified=step.requires_verified,
                rollback=rollback_text, rollback_incomplete=rollback_incomplete,
                fact_effects=step.fact_effects,
                addresses_findings=findings_by_control.get(step.control_id, ()),
                blocked=is_blocked,
                blocked_reason=blocked_nodes.get(node),
            )
        )
        if step.requires_verified and step.checkpoint:
            prereqs = edges.get(node, set())
            after = max((global_id[p] for p in prereqs), default=None)
            checkpoints.append(Checkpoint(after_step=after, instruction=step.checkpoint))

    steps.sort(key=lambda s: s.id)
    checkpoints.sort(key=lambda c: (c.after_step or 0, c.instruction))

    return RemediationPlan(
        device_id=device_id, platform=platform, os_version=os_version,
        steps=tuple(steps), unavailable=tuple(unavailable),
        checkpoints=tuple(checkpoints), conflicts=tuple(final_conflicts),
    )



_INCOMPLETE_MSG = (
    "prior value is unknown (unset/default_unknown) — rollback cannot be "
    "verified against the device's actual prior configuration; manual "
    "verification required before executing this step's rollback"
)


def _resolve_rollback(step: RawStepDoc, facts: Mapping[str, Any]) -> tuple[str | None, bool]:
    """INV-07.1-05: "Rollback is generated from the observed prior state,
    not from the control's generic template." What's implemented: a
    completeness signal (do we actually know the prior fact value, i.e. is
    it not `None`/absent — JSONB NULL = unknown, same convention as the
    rest of the system) rather than literal CLI-text reconstruction from
    structured fact values, which is out of scope for this milestone and
    would risk *overclaiming* fidelity. See module docstring."""

    if step.rollback_from_prior_fact:
        prior = facts.get(step.rollback_from_prior_fact)
        if prior is None:
            return _INCOMPLETE_MSG, True
        return step.rollback, False

    if step.rollback is None:
        if not step.fact_effects:
            return "n/a — enters configuration context only", False
        return None, True

    if step.fact_effects:
        for fe in step.fact_effects:
            if facts.get(fe.path) is None:
                return _INCOMPLETE_MSG, True
    return step.rollback, False
