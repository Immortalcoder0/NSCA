# TRD-09.1 · Report Generation Pipeline

---

## 1. Scope

Deterministic production of the **per-device PDF** — the problem statement's
mandated deliverable — plus estate reports and machine-readable exports.
Immutability, amendment, and the exclusions enforced at generation time.

**Out of scope:** report content design (PRD 10); determinism infrastructure
(TRD-10.1).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-RPT-001…013 | Per-device PDF with all mandated sections |
| FR-RPT-014…016 | Estate report and campaign comparison |
| FR-RPT-017…019 | JSON, CSV, OSCAL, editable exports |
| FR-RPT-020 | Byte-identical determinism |
| FR-RPT-021 | Immutability and amendment |
| NFR-PERF-005 | Under 5 s per device |

---

## 3. Design

### 3.1 Generation is rendering, not computation

```
  assessment results (stored, immutable)
        │
   1  gather            verdicts, evidence, findings, remediation, manifest
   2  filter            apply exclusion rules  ← §3.3
   3  compose           document model
   4  render            PDF · DOCX · JSON · CSV · OSCAL
   5  seal              content hash, manifest, immutability
```

**INV-09.1-01 — No verdict, score, severity or finding is computed during
rendering.** The renderer reads stored results. If a figure can only be produced
at render time, it belongs upstream.

Two reasons this is a hard rule rather than a style preference:

- **Determinism.** A renderer that computes can drift from the engine that
  computed, producing a report that disagrees with the stored assessment.
- **Reproducibility.** Re-rendering a historical report must reproduce it
  exactly, and that is only guaranteed if rendering is a pure function of stored
  data.

### 3.2 Document model

An intermediate representation shared by all output formats:

```
Document {
  sections[]: { id, title, blocks[] }
  blocks: Heading | Paragraph | Table | EvidenceExcerpt
        | SeverityIndicator | Chart | Playbook | Manifest
}
```

**DD-09.1-01 — All formats render from one document model.** PDF, DOCX and HTML
therefore cannot diverge in content. A finding present in the PDF is present in
the DOCX, with identical evidence.

`EvidenceExcerpt` is a distinct block type rather than preformatted text because
it carries obligations: verbatim reproduction, line numbers, highlight markers,
and secret masking (§3.5).

### 3.3 Exclusion rules — enforced at generation

These are correctness gates, not presentation choices.

| Rule | Enforcement |
|---|---|
| **Provisional rulepack findings** excluded from issued reports | FR-LRN-016, INV-08.3-04 |
| **Provisional schema registrations** excluded | TRD-03.3 INV-03.3-02 |
| Draft reports may include them, **clearly flagged** | — |

**INV-09.1-02 — Exclusion is enforced in the generator, not the caller.** A
client requesting an issued report containing provisional findings receives a
report without them. There is no parameter that overrides this.

> A finding derived from provisional parsing is not evidence.

### 3.4 Mandated sections

Per PRD 10 §2. Three warrant specific treatment here.

**Device identification (FR-RPT-002, 003).** Serial numbers are mandated and come
from `show inventory`, not the running configuration.

```
INV-09.1-03  Where serials cannot be determined, the section renders
             `NOT DETERMINED` with the reason. It is never omitted.
```

Omitting a mandated section is indistinguishable from a device having no serial,
and quietly fails an explicit requirement.

**Unassessed section (FR-RPT-010).** Every UNKNOWN with its closed-set reason and
remedy (TRD-05.2 §3.9), plus every unaudited capability. This is the section no
competing product contains, and the one that makes the rest of the report
credible.

**Trust tier and framework versions (FR-RPT-011, 012).** Rendered on the cover.
An assessor must know whether a finding rests on certified parsing.

### 3.5 Evidence rendering obligations

```
INV-09.1-04  An evidence excerpt reproduces the artifact verbatim.
```

| Obligation | Requirement |
|---|---|
| Verbatim text | Character-for-character from the artifact |
| Line numbers | Post-normalisation, matching TRD-01.1 DD-01.1-01 |
| Highlight | The specific line(s) the fact derives from |
| Abbreviation | Shows the operator's **original** text, not the expanded form (TRD-02.1 INV-02.1-03) |
| **Secret masking** | FR-RPT-009 — masked, with masking indicated |

Masking must preserve verifiability:

```
  ▸ 6 │ username admin privilege 15 password 7 08224••••••
                                                  ↑ masked
```

Enough of the line remains for the administrator to locate and verify it; the
credential does not appear.

**DD-09.1-02 — Masking is applied at render, from declared credential
positions.** Facts and artifacts retain full content — redacting at storage would
break re-assessment and reproducibility.

### 3.6 Accessibility and print

| Requirement | Implementation |
|---|---|
| Severity never by colour alone (NFR-USE-006) | Glyph plus label plus hue |
| UNKNOWN visually distinct from PASS (NFR-USE-005) | Distinct glyph and background; verified in monochrome |
| Legible in monochrome print (FR-RPT / PRD 10 RPT-10) | Rendered greyscale during verification |
| Evidence as accessible text | Never rasterised |

**Verification renders every report to monochrome and asserts that verdict states
remain distinguishable.** A report where UNKNOWN and PASS become identical when
printed reintroduces the product's central failure mode at the last step.

### 3.7 Determinism

FR-RPT-020, and a direct consequence of §3.1.

| Source of drift | Control |
|---|---|
| Timestamps in output | Generation time is an input, recorded once, rendered from the stored value |
| Font metrics and versions | Fonts embedded; version pinned in the manifest |
| PDF object ordering | Deterministic writer; fixed object order |
| PDF creation-date metadata | Set from the recorded generation time, never from the clock |
| Collection iteration | Explicitly sorted (D6) |
| Locale | Fixed formatting locale (D8) |
| Chart rendering | Deterministic layout; no randomised label placement |

**INV-09.1-05 — Re-rendering a report from unchanged stored results produces a
byte-identical file.** Verified by hash comparison, not by visual inspection.

### 3.8 Immutability and amendment

FR-RPT-021.

```
issue(report) →
  compute content hash
  attach reproducibility manifest
  state → issued          # immutable
```

Corrections are **linked amendments**, never edits:

```
RPT-2026Q3-CORE-SW-01-001      issued 2026-09-12    superseded
RPT-2026Q3-CORE-SW-01-001-A1   issued 2026-09-24    amendment
  Reason: rulepack cisco_iosxe@7.2.1 → 7.2.2 corrected an extractor
          defect affecting NSCA-CRYPTO-003.
  Effect: 1 finding withdrawn, 1 UNKNOWN resolved to PASS.
  Original retained unaltered.
```

**INV-09.1-06 — An issued report is never regenerated in place.** An audit
history that can be rewritten is not an audit history.

### 3.9 Machine-readable exports

| Format | Notes |
|---|---|
| **JSON** | Full findings with evidence, provenance, framework mappings |
| **CSV** | Flattened for ticketing; evidence referenced, not embedded |
| **OSCAL** | NIST assessment-results. **Compliance-derived results only** — security posture is excluded (TRD-06.1 DD-06.1-04) |
| **DOCX** | Editable; same document model, so content cannot diverge |

**INV-09.1-07 — Non-redistributable framework text never appears in any export.**
CIS and ISO items render identifiers only (TRD-05.3 INV-05.3-02). Enforced in the
renderer as well as the data layer, because an export path is exactly where such
a leak would occur.

### 3.10 Performance

NFR-PERF-005: under 5 s per device.

Estate-scale generation (500 devices) is queued and parallel, with deterministic
per-document output. Documents are independent, so parallelism introduces no
ordering hazard.

---

## 4. Interfaces

```
generate(campaign, device, format, mode) → Report
generate_estate(campaign, format) → Report
compare(campaign_a, campaign_b) → ComparisonReport
issue(report_id) → IssuedReport
amend(report_id, reason) → Amendment
verify(report_id) → ⟨MATCH | MISMATCH, original_hash, recomputed_hash⟩
```

`mode ∈ { draft, issued }`. Draft may include provisional findings, flagged;
issued may not.

---

## 5. Edge cases

| Case | Handling |
|---|---|
| Device with 0% coverage | Report generated stating the device could not be assessed, with reasons. Not suppressed |
| Device with no findings | Report generated; states full compliance within stated coverage |
| Device whose artifacts were deleted under retention | Report renders from stored results; manifest notes artifacts unavailable, reproducibility no longer verifiable |
| Evidence excerpt exceeding a page | Truncated with an explicit marker and a reference to the full artifact |
| Very large playbook (100+ steps) | Rendered in full; summary at the head |
| Campaign comparison where scope changed | Delta decomposition includes a scope-change component (PRD 11 §10) |
| Report requested for an in-progress campaign | Draft only; issuance refused until the campaign reaches Review |
| Non-Latin content in configurations | Rendered with appropriate embedded fonts; falls back with a recorded note rather than dropping characters |

**The deleted-artifact case is a real tension** between retention policy and
audit reproducibility (NFR-DAT-003). The report remains valid and readable; what
is lost is the ability to *re-verify* it. Stating this in the manifest is the
honest treatment.

---

## 6. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Renderer computes a figure | V-09.1-002 | Report disagrees with stored assessment |
| Provisional finding in an issued report | V-09.1-003 | Non-evidence presented as evidence |
| Secret rendered unmasked | V-09.1-005 | Credential disclosure in a distributed document |
| Non-deterministic output | V-09.1-001 | Reproducibility claim invalid |
| Mandated section omitted | V-09.1-004 | Explicit requirement failed |
| UNKNOWN indistinguishable from PASS in print | V-09.1-006 | Central failure mode reintroduced at the last step |
| Restricted framework text in an export | V-09.1-008 | Licensing violation |

---

## 7. Verification

```
V-09.1-001   Report generation is byte-identical on re-render
  Requirement  FR-RPT-020, INV-09.1-05
  Method       PROPERTY
  Procedure    Generate every corpus device report 10 times across process
               restarts, varying locale, timezone, and parallelism.
  Acceptance   Byte-identical files. Hash equality, not visual comparison.
  Severity     BLOCKING
```

```
V-09.1-002   Rendering computes nothing
  Requirement  INV-09.1-01
  Method       UNIT + static analysis
  Procedure    Enumerate renderer inputs. Assert no verdict, score, severity
               or finding is derived during composition.
  Acceptance   Zero computed values. Every rendered figure traces to a
               stored field.
  Severity     BLOCKING
```

```
V-09.1-003   Provisional content is excluded from issued reports
  Requirement  INV-09.1-02, FR-LRN-016
  Method       INTEGRATION
  Procedure    Assess with provisional rulepacks and provisional schema
               registrations. Generate draft and issued reports, including
               via direct API calls attempting to override.
  Acceptance   Draft includes them, flagged. Issued excludes them.
               No override parameter exists.
  Severity     BLOCKING
```

```
V-09.1-004   All mandated sections are present, including when data is absent
  Requirement  FR-RPT-002, 003, 010, INV-09.1-03
  Method       CORPUS
  Procedure    Generate reports for devices with and without show_inventory,
               with and without UNKNOWNs.
  Acceptance   100% contain device identification, findings, remediation and
               unassessed sections. Missing serials render NOT DETERMINED
               with a reason. Zero omitted sections.
  Severity     BLOCKING
```

```
V-09.1-005   Secrets are masked, evidence remains verifiable
  Requirement  FR-RPT-009, INV-09.1-04
  Method       CORPUS
  Procedure    Generate reports for devices with type 7 passwords, SNMP
               communities and pre-shared keys in evidence.
  Acceptance   Zero credential material rendered. Masking indicated.
               Sufficient surrounding text remains for the administrator to
               locate the line. Excerpts otherwise verbatim.
  Severity     BLOCKING
```

```
V-09.1-006   Verdict states are distinguishable in monochrome
  Requirement  NFR-USE-005, NFR-USE-006
  Method       INTEGRATION + MANUAL
  Procedure    Render reports to greyscale. Present to three readers and ask
               them to classify verdict states.
  Acceptance   UNKNOWN never classified as PASS. Severity distinguishable
               without colour. Zero information conveyed by hue alone.
  Severity     BLOCKING
```

```
V-09.1-007   Issued reports are immutable; corrections are amendments
  Requirement  FR-RPT-021, INV-09.1-06
  Method       INTEGRATION
  Procedure    Issue a report. Update the rulepack. Attempt regeneration.
               Issue an amendment.
  Acceptance   Original unchanged and still retrievable. Amendment linked,
               stating reason and effect. Zero in-place regeneration paths.
  Severity     BLOCKING
```

```
V-09.1-008   Restricted framework text never appears in any output
  Requirement  INV-09.1-07, NFR-CMP-001, 002
  Method       INTEGRATION
  Procedure    Generate PDF, DOCX, JSON, CSV and OSCAL for devices assessed
               against CIS and ISO. Scan all output.
  Acceptance   Zero occurrences of CIS or ISO body text. Identifiers present.
  Severity     BLOCKING
```

```
V-09.1-009   OSCAL export contains compliance results only
  Requirement  FR-RPT-018, TRD-06.1 DD-06.1-04
  Method       INTEGRATION
  Procedure    Export OSCAL assessment results for a campaign with a computed
               security posture.
  Acceptance   Valid OSCAL. Zero occurrences of security posture within
               conformance structures.
  Severity     BLOCKING
```

```
V-09.1-010   All formats render identical content
  Requirement  DD-09.1-01
  Method       PROPERTY + CORPUS
  Procedure    Generate PDF, DOCX and JSON for every corpus device. Extract
               findings and evidence from each and compare.
  Acceptance   Identical finding sets, verdicts, severities and evidence
               line references across all formats.
  Severity     MAJOR
```

```
V-09.1-011   Report generation performance
  Requirement  NFR-PERF-005
  Method       PERFORMANCE
  Procedure    Generate per-device PDFs for 500 devices, reference profile.
  Acceptance   < 5 s per device. Estate generation parallel and
               deterministic.
  Severity     MAJOR
```

```
V-09.1-012   Reports generate fully offline
  Requirement  NFR-DEP-001
  Method       INTEGRATION
  Procedure    Generate all report formats with no external network access.
  Acceptance   Identical output to a connected run. Zero outbound requests.
               Fonts and assets embedded.
  Severity     BLOCKING
```

---

## 8. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should draft reports be exportable outside the platform at all? | Exporting drafts risks provisional findings circulating as evidence; refusing export impedes internal review. Current design: exportable with a prominent draft watermark and provisional flags on every affected finding |
| Q2 | Should reports embed the source artifacts for offline verification? | Embedding makes a report self-verifying but multiplies size and duplicates sensitive content into a distributed document. Current design: hashes in the manifest, artifacts retained in the platform |
| Q3 | Should multi-VDOM devices produce one report or one per context? | The problem statement mandates one PDF per device, and a VDOM is not a device. Current design: one report with VDOM-qualified findings and a per-VDOM summary on the cover |
