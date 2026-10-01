"""Per-device PDF — WeasyPrint + Jinja2 + pikepdf, TECH-STACK.md §11,
backend-02 §4.6, M4.

Two-stage pipeline, deliberately split so the deterministic parts are
testable without WeasyPrint's native Pango/cairo/GTK dependency (not always
present outside the container image — see this module's tests):

    Document (document_model.py)
        │  render_html()      pure Jinja2, no native deps
        ▼
    HTML string                <- hashed for content_hash_hex, sha256
        │  render_pdf()        WeasyPrint HTML -> PDF bytes
        ▼
    raw PDF bytes
        │  determinism.normalise_pdf()   pikepdf metadata normalisation
        ▼
    final PDF bytes             <- this is what V-10.1-001 hashes

Section order and headings follow 10-reporting.md §2's eight sections
verbatim, in the doc's own order (backend-02 §4.6).
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

import jinja2

from nsca_platform.reporting import determinism
from nsca_platform.reporting.document_model import (
    Chart,
    Document,
    EvidenceExcerpt,
    Heading,
    Manifest,
    Paragraph,
    Playbook,
    SeverityIndicator,
    Table,
)

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{{ title }}</title>
<style>
  @page { size: A4; margin: 2cm; }
  body { font-family: "DejaVu Sans", sans-serif; font-size: 10pt; color: #000; }
  h1 { font-size: 18pt; }
  h2 { font-size: 14pt; border-bottom: 1px solid #000; }
  h3 { font-size: 12pt; }
  table { border-collapse: collapse; width: 100%; margin: 0.4em 0; }
  th, td { border: 1px solid #666; padding: 2px 6px; text-align: left; font-size: 9pt; }
  .paragraph-warning { font-weight: bold; }
  .paragraph-caveat { font-style: italic; }
  .evidence { font-family: "DejaVu Sans Mono", monospace; white-space: pre; background: #f0f0f0; padding: 4px; }
  .evidence-highlight { font-weight: bold; }
  .evidence-masked::after { content: " [masked]"; }
  .severity-critical::before { content: "[!! CRITICAL] "; font-weight: bold; }
  .severity-high::before { content: "[! HIGH] "; font-weight: bold; }
  .severity-medium::before { content: "[~ MEDIUM] "; }
  .severity-low::before { content: "[- LOW] "; }
  .severity-info::before { content: "[. INFO] "; }
  .chart-bar { font-family: monospace; }
  .step-blocked { text-decoration: line-through; color: #900; }
  .section { page-break-inside: avoid; margin-bottom: 1em; }
</style>
</head>
<body>
{% for section in sections %}
<div class="section" id="section-{{ section.id }}">
<h2>{{ loop.index }} &middot; {{ section.title }}</h2>
{% for block in section.blocks %}
  {{ render_block(block) }}
{% endfor %}
</div>
{% endfor %}
</body>
</html>
"""


def _esc(s: Any) -> str:
    import html as html_mod

    return html_mod.escape(str(s), quote=True)


def _render_block(block: Any) -> str:
    if isinstance(block, Heading):
        level = min(max(block.level, 1), 6)
        return f"<h{level}>{_esc(block.text)}</h{level}>"
    if isinstance(block, Paragraph):
        cls = f"paragraph-{block.kind}" if block.kind != "body" else ""
        text = _esc(block.text).replace("\n", "<br>")
        return f'<p class="{cls}">{text}</p>'
    if isinstance(block, Table):
        head = "".join(f"<th>{_esc(h)}</th>" for h in block.headers)
        rows = "".join(
            "<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in row.cells) + "</tr>"
            for row in block.rows
        )
        return f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"
    if isinstance(block, EvidenceExcerpt):
        lines_html = []
        for ln in block.lines:
            cls = []
            if ln.highlighted:
                cls.append("evidence-highlight")
            if ln.masked:
                cls.append("evidence-masked")
            cls_attr = f' class="{" ".join(cls)}"' if cls else ""
            marker = "&#9656;" if ln.highlighted else "&nbsp;"
            lines_html.append(f'<div{cls_attr}>{marker} {ln.number:>4} | {_esc(ln.text)}</div>')
        truncated = "<div><em>&hellip; truncated, see full artifact</em></div>" if block.truncated else ""
        return (
            f'<div class="evidence"><strong>{_esc(block.artifact_filename)}</strong>'
            + "".join(lines_html) + truncated + "</div>"
        )
    if isinstance(block, SeverityIndicator):
        return f'<p class="severity-{_esc(block.severity)}">{_esc(block.label)}</p>'
    if isinstance(block, Chart):
        rows = []
        for bar in block.bars:
            filled = 0 if bar.total == 0 else (bar.value * 30) // bar.total
            bar_text = bar.fill_glyph * filled + bar.empty_glyph * (30 - filled)
            rows.append(f"<div class='chart-bar'>{_esc(bar.label):>10} {bar_text} {bar.value}</div>")
        return f"<div><strong>{_esc(block.title)}</strong>" + "".join(rows) + "</div>"
    if isinstance(block, Playbook):
        return _render_playbook(block)
    if isinstance(block, Manifest):
        return _render_manifest(block)
    return f"<pre>{_esc(block)}</pre>"


def _render_playbook(block: Playbook) -> str:
    parts = ["<div class='playbook'>"]
    for step in block.steps:
        cls = "step-blocked" if step.blocked else ""
        parts.append(f"<div class='{cls}'>")
        parts.append(
            f"<strong>STEP {step.id}</strong> {_esc(step.command)} "
            f"&mdash; IMPACT: {_esc(step.impact.upper())}"
        )
        if step.reason:
            parts.append(f"<br>{_esc(step.reason)}")
        if step.requires_verified:
            parts.append("<br><em>&#9208; VERIFY BEFORE CONTINUING</em>")
        if step.addresses_findings:
            parts.append(f"<br>Addresses {', '.join(_esc(x) for x in step.addresses_findings)}")
        if step.rollback:
            incomplete = " (INCOMPLETE)" if step.rollback_incomplete else ""
            parts.append(f"<br>Rollback{incomplete}: {_esc(step.rollback)}")
        if step.blocked:
            parts.append(f"<br><strong>BLOCKED: {_esc(step.blocked_reason)}</strong>")
        parts.append("</div>")
    for cp in block.checkpoints:
        parts.append(
            f"<div class='paragraph-warning'>&#9208; VERIFY BEFORE CONTINUING (after step "
            f"{cp.after_step})<br>{_esc(cp.instruction)}</div>"
        )
    for control_id, reason in block.unavailable:
        parts.append(f"<div class='paragraph-warning'>Remediation unavailable — {_esc(control_id)}: {_esc(reason)}</div>")
    if block.lockout:
        lo = block.lockout
        parts.append(
            f"<h3>LOCKOUT ANALYSIS</h3><p>Operator source: {_esc(lo.operator_source)}<br>"
            f"Result: <strong>{_esc(lo.result)}</strong><br>{_esc(lo.reason)}</p>"
        )
    if block.dry_run:
        dr = block.dry_run
        parts.append(
            f"<h3>DRY RUN — modelled outcome, not applied</h3>"
            f"<p>Compliance {dr.before_compliance_num}/{dr.before_compliance_den} -> "
            f"{dr.after_compliance_num}/{dr.after_compliance_den}<br>"
            f"Resolved {len(dr.resolved)} findings</p>"
        )
        if dr.newly_failing:
            parts.append("<p class='paragraph-warning'>NEWLY FAILING:</p><ul>")
            for cid, reason in dr.newly_failing:
                parts.append(f"<li>{_esc(cid)} — {_esc(reason)}</li>")
            parts.append("</ul>")
        parts.append(f"<p class='paragraph-caveat'>{_esc(dr.fidelity_note)}</p>")
    parts.append("</div>")
    return "".join(parts)


def _render_manifest(block: Manifest) -> str:
    parts = [f"<div class='manifest'><p>report_id: {_esc(block.report_id)}<br>generated: {_esc(block.generated_at)}</p>"]
    parts.append("<table><thead><tr><th>Input artifact</th><th>sha256</th></tr></thead><tbody>")
    for filename, sha in block.inputs:
        parts.append(f"<tr><td>{_esc(filename)}</td><td>{_esc(sha)}</td></tr>")
    parts.append("</tbody></table>")
    parts.append("<table><thead><tr><th>Knowledge base</th><th>Version</th></tr></thead><tbody>")
    for entry in block.knowledge_base:
        parts.append(f"<tr><td>{_esc(entry.key)}</td><td>{_esc(entry.value)}</td></tr>")
    parts.append("</tbody></table>")
    parts.append(f"<p>report_hash: {_esc(block.report_hash or 'PENDING')}</p>")
    parts.append(f"<p class='paragraph-caveat'>{_esc(block.statement)}</p></div>")
    return "".join(parts)


_ENV = jinja2.Environment(
    loader=jinja2.BaseLoader(),
    autoescape=False,  # blocks are pre-escaped by _render_block (raw HTML fragments)
    trim_blocks=True,
    lstrip_blocks=True,
)
_ENV.globals["render_block"] = _render_block
_TEMPLATE = _ENV.from_string(_HTML_TEMPLATE)


def render_html(document: Document) -> str:
    """Pure Jinja2 render — deterministic, no native library dependency.
    Two calls with an unchanged `Document` produce byte-identical strings
    (dict/dataclass iteration is always over `tuple`s, defined order —
    D6/D7)."""

    title = f"{document.device_hostname or 'ESTATE'} — Compliance Audit Report"
    return _TEMPLATE.render(title=title, sections=document.sections)


def render_pdf(
    document: Document,
    *,
    generated_at: datetime,
    engine_version: str = "n/a",
) -> bytes:
    """WeasyPrint HTML -> PDF, then pikepdf normalisation
    (`determinism.normalise_pdf`) — TECH-STACK.md §11. `generated_at` is
    always a parameter, from the recorded assessment/report generation
    time, never `datetime.now()` (TRD-10.1 D2).

    Raises whatever WeasyPrint raises if its native Pango/cairo/GTK
    dependency is not importable on this host — callers (and this
    milestone's tests) treat that as an environment precondition to skip
    on, exactly like the existing `requires_db` pattern for Postgres, not
    something to catch-and-approximate.
    """

    from weasyprint import HTML  # imported lazily: native-lib import failure
    # must only surface when a PDF is actually requested, not at module
    # import time (which would break every other reporting import).

    html_str = render_html(document)
    content_hash_hex = hashlib.sha256(html_str.encode("utf-8")).hexdigest()

    raw_pdf = HTML(string=html_str, base_url=".").write_pdf()
    return determinism.normalise_pdf(
        raw_pdf, generated_at=generated_at, engine_version=engine_version,
        content_hash_hex=content_hash_hex,
    )


def weasyprint_available() -> bool:
    """Best-effort probe, used by tests to skip gracefully when WeasyPrint's
    native Pango/cairo/GTK libraries are not importable on this host — the
    same graceful-skip pattern `db.engine.database_available()` uses for
    Postgres reachability."""

    try:
        from weasyprint import HTML

        HTML(string="<html><body>probe</body></html>").write_pdf()
        return True
    except Exception:
        return False
