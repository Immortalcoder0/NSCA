"""DISA STIG XCCDF import — direct XML parse, backend-02 §4.5, M4.

06-controls-and-frameworks.md §5: "STIGs are the best import. They are XML.
Parse them directly and obtain a large, structured, authoritative control
set per platform at no content-authoring cost. Begin here." — and "Freely
redistributable", so every parsed item is `text_redistributable=True`
(unlike CIS/ISO, which this milestone deliberately does not build, per the
task brief: "begin with STIG/NIST, they're direct machine-readable
parses").

XCCDF 1.1/1.2 shape (`http://checklists.nist.gov/xccdf/1.1` or `.../1.2`
namespace): a `Benchmark` containing `Group` elements, each wrapping one
`Rule` — `Group/@id` is the STIG's `V-NNNNNN` vulnerability id (the
identifier assessors actually cite, e.g. 10-reporting.md §2's
`STIG V-216644 (CAT I)`), `Rule/@severity` (`high`/`medium`/`low`) maps to
DISA's CAT I/II/III convention, and `Rule/check/check-content` is the
stated audit procedure. Namespace-agnostic (`lxml`'s `local-name()`) since
different STIG releases use `xccdf/1.1` and `xccdf/1.2` inconsistently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lxml import etree

_SEVERITY_TO_CAT = {"high": "CAT I", "medium": "CAT II", "low": "CAT III"}


class StigParseError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ParsedFrameworkItem:
    framework: str
    benchmark: str
    version: str
    item_id: str
    title: str | None
    severity: str | None
    stated_audit_procedure: str | None
    automation_status: str
    text_redistributable: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "framework": self.framework, "benchmark": self.benchmark, "version": self.version,
            "item_id": self.item_id, "title": self.title, "severity": self.severity,
            "stated_audit_procedure": self.stated_audit_procedure,
            "automation_status": self.automation_status,
            "text_redistributable": self.text_redistributable,
        }


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _findtext_local(elem: etree._Element, name: str) -> str | None:
    for child in elem:
        if _local(child.tag) == name:
            return "".join(child.itertext()).strip() or None
    return None


def _find_local(elem: etree._Element, name: str) -> etree._Element | None:
    for child in elem:
        if _local(child.tag) == name:
            return child
    return None


def _findall_local(elem: etree._Element, name: str) -> list[etree._Element]:
    return [c for c in elem if _local(c.tag) == name]


def parse_xccdf(content: bytes, *, benchmark: str | None = None) -> list[ParsedFrameworkItem]:
    """Parses one XCCDF `Benchmark` document into `FRAMEWORK_ITEM`-shaped
    records. `benchmark` overrides the auto-derived benchmark identifier
    (STIG releases don't always carry a machine-friendly short name in the
    XML itself — 10-reporting.md's own example cites
    `cisco_iosxe_router@2026-01`, a value an operator supplies at import
    time, not something reliably parseable from `<title>` prose).

    Raises `StigParseError` on malformed XML or a document that isn't an
    XCCDF Benchmark — refusal, not a best-effort guess (mirrors
    06-controls-and-frameworks.md's "confirm, don't author" symmetry: a
    machine parse that silently produces wrong data is worse than one that
    refuses).
    """

    try:
        root = etree.fromstring(content)
    except etree.XMLSyntaxError as exc:
        raise StigParseError(f"malformed XCCDF XML: {exc}") from exc

    if _local(root.tag) != "Benchmark":
        raise StigParseError(f"expected an XCCDF <Benchmark> root element, got <{_local(root.tag)}>")

    version_elem = _find_local(root, "version")
    version = (version_elem.text or "").strip() if version_elem is not None else "0"
    bench_id = benchmark or root.get("id") or "unknown_benchmark"

    items: list[ParsedFrameworkItem] = []
    for group in root.iter():
        if _local(group.tag) != "Group":
            continue
        group_id = group.get("id")
        if not group_id:
            continue
        rule = _find_local(group, "Rule")
        if rule is None:
            continue

        title = _findtext_local(rule, "title") or _findtext_local(group, "title")
        severity_raw = (rule.get("severity") or "").lower()
        severity = _SEVERITY_TO_CAT.get(severity_raw)

        check_content = None
        check = _find_local(rule, "check")
        if check is not None:
            check_content = _findtext_local(check, "check-content")

        items.append(
            ParsedFrameworkItem(
                framework="stig", benchmark=bench_id, version=version,
                item_id=group_id, title=title, severity=severity,
                stated_audit_procedure=check_content,
                # STIGs ship machine-checkable content; whether *this*
                # platform's rulepack actually maps to it is a separate
                # question (06-controls-and-frameworks.md §6's coverage
                # manifest) — refusal-not-approximation means we don't
                # guess "automated" here without a real mapping, so every
                # freshly-imported item starts `not_implemented` until a
                # control maps to it (satisfied_by populated elsewhere).
                automation_status="not_implemented",
                text_redistributable=True,
            )
        )
    items.sort(key=lambda i: i.item_id)  # deterministic order (D6)
    return items
