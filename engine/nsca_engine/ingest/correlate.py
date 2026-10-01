"""Artifact correlation into one device record (TRD-01.1 §3.5).

M1 scope: the engine's ``assess_device`` entry point is already handed one
device's artifacts (per `api.py`'s contract — correlation into per-device
artifact sets is Track B's orchestration job upstream of
``KnowledgeBase``/``assess_device``). What belongs to Track A here is the
*logic* of correlation (DD-01.1-02: serial outranks hostname; escalation
conditions) as a reusable, independently testable function — exercised by
unit tests in this milestone even though `assess_device` itself does not
call it yet (there being exactly one artifact set per call, so correlation
is a no-op there).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class CorrelationOutcome(Enum):
    ASSIGNED = auto()
    ESCALATED = auto()
    HELD = auto()


@dataclass(frozen=True, slots=True)
class IdentityCandidate:
    artifact_id: str
    hostname: str | None
    chassis_serial: str | None


@dataclass(frozen=True, slots=True)
class CorrelationResult:
    outcome: CorrelationOutcome
    device_key: str | None
    reason: str | None
    artifact_ids: tuple[str, ...]


def correlate(candidates: tuple[IdentityCandidate, ...]) -> tuple[CorrelationResult, ...]:
    """DD-01.1-02: serial outranks hostname. Groups candidates by chassis
    serial when present; falls back to hostname only when no candidate in
    the batch has a serial at all. Escalates when two artifacts share a
    hostname but disagree on serial (two devices, or a renamed device) —
    per TRD-01.1 §3.5's escalation table."""

    with_serial = [c for c in candidates if c.chassis_serial]
    without_serial = [c for c in candidates if not c.chassis_serial]

    results: list[CorrelationResult] = []

    by_serial: dict[str, list[IdentityCandidate]] = {}
    for c in with_serial:
        by_serial.setdefault(c.chassis_serial, []).append(c)  # type: ignore[arg-type]

    # Detect hostname/serial disagreement: same hostname, different serial.
    hostname_to_serials: dict[str, set[str]] = {}
    for c in with_serial:
        if c.hostname:
            hostname_to_serials.setdefault(c.hostname, set()).add(c.chassis_serial)  # type: ignore[arg-type]

    conflicted_hostnames = {h for h, serials in hostname_to_serials.items() if len(serials) > 1}

    for serial, members in sorted(by_serial.items()):
        hostnames = {m.hostname for m in members if m.hostname}
        if hostnames & conflicted_hostnames:
            results.append(
                CorrelationResult(
                    outcome=CorrelationOutcome.ESCALATED,
                    device_key=None,
                    reason="hostname_serial_conflict",
                    artifact_ids=tuple(m.artifact_id for m in members),
                )
            )
        else:
            results.append(
                CorrelationResult(
                    outcome=CorrelationOutcome.ASSIGNED,
                    device_key=serial,
                    reason="hostname_changed" if len(hostnames) > 1 else None,
                    artifact_ids=tuple(m.artifact_id for m in members),
                )
            )

    by_hostname: dict[str, list[IdentityCandidate]] = {}
    for c in without_serial:
        if c.hostname:
            by_hostname.setdefault(c.hostname, []).append(c)
        else:
            results.append(
                CorrelationResult(
                    outcome=CorrelationOutcome.HELD,
                    device_key=None,
                    reason="no_identity_signal",
                    artifact_ids=(c.artifact_id,),
                )
            )
    for hostname, members in sorted(by_hostname.items()):
        results.append(
            CorrelationResult(
                outcome=CorrelationOutcome.ASSIGNED,
                device_key=hostname,
                reason=None,
                artifact_ids=tuple(m.artifact_id for m in members),
            )
        )

    return tuple(results)
