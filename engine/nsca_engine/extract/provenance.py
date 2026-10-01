"""Provenance classification and defaults resolution (TRD-03.2).

Implements the decision procedure of TRD-03.2 §4.1, trimmed to the M1 scope:
explicit / default_known / default_unknown. ``default_inferred`` (fleet-based
capability inference, FR-EXT-006, TRD-03.2 §4.4) is **deliberately deferred**
— flagged as an open item in the M1 report — because it requires a
multi-device fleet index that does not exist until a campaign has more than
one device assessed, which is beyond M1's single-worked-example scope.
``inherited``/``not_applicable`` are likewise not exercised by the Cisco IOS
M1 path (no template/group inheritance mechanism applies to Cisco; overlap
resolution, not layered inheritance, is what M1's effective-config module
handles).

INV-03.2-01 — the default branch is always ``default_unknown``: any fact this
module has not positively resolved to ``explicit`` or ``default_known`` ends
here, with ``value=None`` (⊥).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from nsca_engine.types import Fact, Provenance, ProvenanceSource

# Rank used for INV-03.2-03 "weakest provenance wins" in derived-fact
# computation (extract/runtime.py). Lower rank == stronger.
_PROVENANCE_RANK: dict[ProvenanceSource, int] = {
    ProvenanceSource.EXPLICIT: 0,
    ProvenanceSource.DEFAULT_KNOWN: 0,
    ProvenanceSource.INHERITED: 0,
    ProvenanceSource.DERIVED: 0,
    ProvenanceSource.DEFAULT_INFERRED: 1,
    ProvenanceSource.DEFAULT_UNKNOWN: 2,
    ProvenanceSource.NOT_APPLICABLE: 2,
}


def weakest_source(sources: list[ProvenanceSource]) -> ProvenanceSource:
    """TRD-03.2 INV-03.2-03: a derived fact inherits the weakest provenance
    of its inputs. Ties among "strong" sources resolve to DERIVED itself,
    since the derived fact is genuinely computed, not merely relabelled."""

    if not sources:
        return ProvenanceSource.DEFAULT_UNKNOWN
    worst = max(sources, key=lambda s: _PROVENANCE_RANK[s])
    if _PROVENANCE_RANK[worst] == 0:
        return ProvenanceSource.DERIVED
    return worst


@dataclass(frozen=True, slots=True)
class DefaultEntry:
    """One row of a rulepack's defaults table (07-vendor-rulepacks.md §6,
    TRD-03.2 §4.2). ``source`` is a mandatory citation (INV-03.2-02)."""

    version_range: str
    value: Any
    source: str
    condition: str | None = None


DefaultsTable = Mapping[str, tuple[DefaultEntry, ...]]


_VERSION_CMP = re.compile(r"^(<|<=|>|>=)?\s*([0-9]+(?:\.[0-9]+)*)$")


def _parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split("."))


def _version_in_range(version: tuple[int, ...], range_spec: str) -> bool:
    range_spec = range_spec.strip()
    if range_spec == "*":
        return True
    m = _VERSION_CMP.match(range_spec)
    if not m:
        return False
    op, bound_str = m.groups()
    bound = _parse_version(bound_str)
    op = op or "=="
    # pad both to equal length for lexicographic comparison
    length = max(len(version), len(bound))
    v = version + (0,) * (length - len(version))
    b = bound + (0,) * (length - len(bound))
    if op == "<":
        return v < b
    if op == "<=":
        return v <= b
    if op == ">":
        return v > b
    if op == ">=":
        return v >= b
    return v == b


def resolve_default(
    fact_path: str,
    defaults_table: DefaultsTable,
    platform: str,
    os_version: str | None,
) -> tuple[Any, str, str | None] | None:
    """Look up ``fact_path`` in the defaults table for the given device
    version. Returns ``(value, source_citation, condition)`` or ``None`` if
    no entry applies (→ the caller resolves ``default_unknown``,
    INV-03.2-01).

    Version ambiguity (TRD-03.2 §4.2 "Version ambiguity"): if more than one
    entry's range matches, that is by construction a mis-authored defaults
    table for a single, unambiguous ``os_version`` — treated the same as "no
    match" (default_unknown), never a guess (G2).
    """

    entries = defaults_table.get(fact_path)
    if not entries:
        return None
    if os_version is None:
        # M2: a device whose OS version could not be extracted (most
        # non-Cisco M2 rulepacks do not yet declare a version_pattern) can
        # still resolve defaults that apply unconditionally ("*"). A
        # version-ranged entry cannot be evaluated without a version, so it
        # is excluded rather than guessed at (G2).
        matches = [e for e in entries if e.version_range.strip() == "*"]
    else:
        version = _parse_version(os_version)
        matches = [e for e in entries if _version_in_range(version, e.version_range)]
    if len(matches) != 1:
        return None
    entry = matches[0]
    return entry.value, entry.source, entry.condition


def classify_absent(
    fact_path: str,
    defaults_table: DefaultsTable,
    platform: str,
    os_version: str | None,
    artifact_id: str,
) -> Fact:
    """Classify a fact whose path was not produced by any extractor
    (TRD-03.2 §4.1, absent branch).

    Phase 3 demo rehearsal fix (finding 11, §9 checklist item 11): both
    branches now carry `artifact_id` — the artifact this device was
    assessed from, which really was searched for a matching construct and
    genuinely did not contain one. This is what lets an absence-based
    finding (e.g. "no login banner configured") cite a real, honest
    citation ("looked in ART-XXX, found nothing") instead of empty evidence,
    without fabricating line numbers that don't exist (`lines` stays `()`
    — there is no line to highlight for something that isn't there).
    `default_known`'s existing `default_source` citation is preserved
    unchanged; `excerpt` is new on both branches, distinguishing "a
    documented platform default applies" from "no default is known either."
    """

    resolved = resolve_default(fact_path, defaults_table, platform, os_version)
    if resolved is not None:
        value, source_citation, _condition = resolved
        return Fact(
            path=fact_path,
            value=value,
            type="unknown",
            provenance=Provenance(
                source=ProvenanceSource.DEFAULT_KNOWN,
                artifact_id=artifact_id,
                excerpt=(
                    f"no explicit configuration found for '{fact_path}' in this "
                    f"artifact; platform default applies ({source_citation})"
                ),
                platform=platform,
                version_range="*",
                default_source=source_citation,
            ),
        )
    return Fact(
        path=fact_path,
        value=None,
        type="unknown",
        provenance=Provenance(
            source=ProvenanceSource.DEFAULT_UNKNOWN,
            artifact_id=artifact_id,
            excerpt=f"no matching construct found for '{fact_path}' in this artifact",
        ),
    )
