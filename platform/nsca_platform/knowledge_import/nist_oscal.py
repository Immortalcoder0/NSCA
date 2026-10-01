"""NIST OSCAL catalog import — direct JSON parse, backend-02 §4.5, M4.

06-controls-and-frameworks.md §5: NIST SP 800-53 ships as OSCAL JSON,
"Fully" machine-readable, "Public domain" — every item here is
`text_redistributable=True`, same reasoning as STIG.

OSCAL catalog shape (NIST OSCAL 1.0+):
`{"catalog": {"metadata": {...}, "groups": [{"id", "title", "controls": [
{"id", "title", "parts": [...], "controls": [...nested enhancements...]}
]}]}}`. Controls can nest sub-controls (enhancements, e.g. `ac-17.1` under
`ac-17`) — `_walk_controls` recurses so both parents and enhancements
become their own `FRAMEWORK_ITEM` rows, matching how they're actually cited
(10-reporting.md §2's example cites the bare `NIST AC-17` control; an
enhancement would be cited the same way if a mapping needed it).
"""

from __future__ import annotations

import json
from typing import Any, Iterator

from nsca_platform.knowledge_import.stig_xccdf import ParsedFrameworkItem


class OscalParseError(ValueError):
    pass


# Phase 3 demo-rehearsal Bug 3: a real, valid OSCAL catalog with "ISO" in
# its title was previously labelled `"framework": "nist"` unconditionally
# — `framework` was a hardcoded literal on every `ParsedFrameworkItem`
# below, never read from the catalog's own metadata. OSCAL is a *format*
# (NIST's own schema for representing any control catalog, per
# 06-controls-and-frameworks.md §5's table — "NIST SP 800-53 | OSCAL JSON |
# Fully | ..."), not itself a framework family, so a catalog authored in
# OSCAL can legitimately describe CIS, STIG, ISO or NIST content. The
# family is derived from the catalog's own `metadata.title`/`metadata.id`
# text (keyword match against the four families 06-controls-and-
# frameworks.md §5's mapping table names — cis/nist/stig/iso) rather than
# assumed. Falls back to "nist" only when nothing in the metadata matches
# any known family — OSCAL's native/primary home per that same table — and
# that fallback is a documented default, not a silent mislabel.
_FAMILY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("iso", ("iso", "27001", "27002", "iec")),
    ("stig", ("stig", "disa", "xccdf")),
    ("cis", ("cis benchmark", "center for internet security", " cis ", "cis-")),
    ("nist", ("nist", "800-53", "800-171", "sp 800")),
)


def _framework_family(metadata: dict[str, Any]) -> str:
    haystack = " ".join(
        str(metadata.get(k, "")) for k in ("title", "id", "oscal-version")
    ).lower()
    padded = f" {haystack} "
    for family, keywords in _FAMILY_KEYWORDS:
        if any(kw in padded for kw in keywords):
            return family
    return "nist"


def _statement_prose(control: dict[str, Any]) -> str | None:
    for part in control.get("parts", []) or []:
        if part.get("name") == "statement":
            prose = part.get("prose")
            if prose:
                return prose
            # Statements are often broken into sub-parts rather than one
            # `prose` string directly on the statement part.
            sub_prose = [p.get("prose") for p in part.get("parts", []) or [] if p.get("prose")]
            if sub_prose:
                return " ".join(sub_prose)
    return None


def _walk_controls(controls: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for c in controls:
        yield c
        yield from _walk_controls(c.get("controls", []) or [])


def parse_oscal_catalog(
    content: bytes, *, benchmark: str | None = None
) -> list[ParsedFrameworkItem]:
    """Parses one OSCAL `catalog` JSON document into `FRAMEWORK_ITEM`-shaped
    records. Raises `OscalParseError` on malformed JSON or a document
    missing the `catalog` root key — refusal, not a best-effort guess."""

    try:
        doc = json.loads(content)
    except json.JSONDecodeError as exc:
        raise OscalParseError(f"malformed OSCAL JSON: {exc}") from exc

    catalog = doc.get("catalog")
    if not isinstance(catalog, dict):
        raise OscalParseError("expected a top-level \"catalog\" object (OSCAL catalog model)")

    metadata = catalog.get("metadata", {})
    version = str(metadata.get("version", "0"))
    bench_id = benchmark or metadata.get("title") or "unknown_catalog"
    framework = _framework_family(metadata)

    items: list[ParsedFrameworkItem] = []
    for group in catalog.get("groups", []) or []:
        for control in _walk_controls(group.get("controls", []) or []):
            control_id = control.get("id")
            if not control_id:
                continue
            items.append(
                ParsedFrameworkItem(
                    framework=framework, benchmark=bench_id, version=version,
                    item_id=control_id.upper(), title=control.get("title"),
                    severity=None,  # NIST 800-53 controls carry no built-in severity band
                    stated_audit_procedure=_statement_prose(control),
                    automation_status="not_implemented",
                    text_redistributable=True,
                )
            )
    # Catalog-level (ungrouped) controls, if the source has any.
    for control in _walk_controls(catalog.get("controls", []) or []):
        control_id = control.get("id")
        if not control_id:
            continue
        items.append(
            ParsedFrameworkItem(
                framework=framework, benchmark=bench_id, version=version,
                item_id=control_id.upper(), title=control.get("title"),
                severity=None, stated_audit_procedure=_statement_prose(control),
                automation_status="not_implemented", text_redistributable=True,
            )
        )
    items.sort(key=lambda i: i.item_id)  # deterministic order (D6)
    return items
