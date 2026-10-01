# TRD-05.3 · Framework Import and Mapping

---

## 1. Scope

Import of framework content from four sources of differing machine-readability;
the two-tier mapping between framework items and native controls; automation
coverage manifests; framework version pinning, conflict resolution and update
governance.

**Out of scope:** control evaluation (TRD-05.2); the expression language
(TRD-05.1).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-CTL-010 | Multi-framework evaluation and reporting |
| FR-CTL-011 | Framework version recording |
| FR-CTL-012 | Conflict resolution |
| FR-CTL-015 | Automation coverage manifest |
| FR-CTL-016 | Equivalence rationale |
| FR-ADM-007 | Import with estate impact preview |
| NFR-CMP-001…005 | Licensing constraints enforced at the data layer |
| NFR-MNT-002 | New frameworks as data, no code change |

---

## 3. The two-tier model

`CIS-IOS-1.2.4` is vendor-specific by construction. Native controls mention no
vendor. The mapping reconciles them.

```
   FRAMEWORK ITEMS                       NATIVE CONTROLS
   imported · vendor-specific            authored · vendor-neutral
   the reporting vocabulary              the evaluation engine

   CIS-IOS-1.2.4        ─┐
   CIS-JUNIPER-4.2.1    ─┤
   STIG V-216644 (IOS)  ─┼──► NSCA-MGMT-002 ──► mgmt.protocols.telnet.enabled
   STIG V-220987 (JunOS)─┤                              == false
   NIST AC-17, SC-8     ─┤
   ISO A.9.4.2          ─┘
```

**INV-05.3-01 — Evaluation happens once, in native terms.** Framework selection
changes *what is reported*, never *what is computed*. Two campaigns over the same
artifacts with different framework selections produce identical verdicts and
differ only in the identifiers attached to them.

This is what makes multi-framework support nearly free, and it is verified by
V-05.3-004.

### 3.1 Mapping cardinality

| Relationship | Share | Example |
|---|---|---|
| Item → universal native control | ~70% | *"Disable Telnet"* — true of every platform |
| → control with conditional applicability | ~20% | *"Authenticate OSPF"* — only if OSPF runs |
| → platform-specific native control | ~10% | *"No type 7 passwords"* — a Cisco-only encoding |

These proportions are **planning estimates from inspection of published
benchmarks**, not measurements. V-05.3-009 requires them to be measured against
real imported content and the figures corrected.

---

## 4. Import by source

| Source | Format | Machine-readable | Redistributable | Role |
|---|---|---|---|---|
| **DISA STIG** | XCCDF XML | Fully | Yes | **Primary import** |
| **CIS Benchmark** | PDF, fixed template | Structured, not native | **Text: no** | Assisted extraction; identifiers cited |
| **NIST SP 800-53** | OSCAL JSON | Fully | Yes | Catalogue for abstract mapping |
| **ISO/IEC 27001** | Paid standard | No | **No** | Identifiers only |

### 4.1 STIG import — direct

XCCDF is XML. Rules parse directly:

```
Rule → ⟨ rule_id, vuln_id, severity(CAT I/II/III), title,
         check_content, fix_text, cci_refs[] ⟩
```

`cci_refs` (Control Correlation Identifiers) map STIG rules to NIST 800-53
controls **in the published content itself**. This gives a free, authoritative
STIG→NIST mapping and is the single best reason to treat STIGs as the primary
import source.

Severity mapping: `CAT I → critical`, `CAT II → high`, `CAT III → medium`.

### 4.2 CIS import — assisted extraction

Every recommendation follows an identical template. You are parsing a form, not
free prose:

```
Recommendation → ⟨ number, title, profile_applicability, description,
                   rationale, impact, audit_procedure, remediation,
                   DEFAULT_VALUE, references, cis_controls_mapping ⟩
```

**Two things fall out of one import:**

1. Framework items for the mapping layer
2. **The `Default Value` field populates the defaults table** (TRD-03.2 §4.3),
   directly reducing `default_unknown` facts and raising coverage

This is a substantial practical shortcut — benchmark import improves both the
control library and extraction quality from one source.

**DD-05.3-01 — Model-assisted extraction, human ratification.** The model
proposes a structured item and a candidate native-control mapping from the
recommendation text; an assessor confirms. Same confirm-don't-author pattern as
the parsing loop (TRD-08.2), pointed at the other side of the bridge.

> The system is a bridge between two kinds of ambiguity — messy machine syntax on
> one side, messy human prose on the other — with something formal and
> deterministic in between.

### 4.3 NIST OSCAL — direct

The 800-53 catalogue imports directly as OSCAL JSON. These are policy-level
controls, so they are almost never mapped from a device fact directly; they are
reached **transitively** through concrete items:

```
NSCA-MGMT-002 → CIS-IOS-1.2.4 → (CIS mapping) → NIST AC-17
NSCA-MGMT-002 → STIG V-216644 → (CCI)         → NIST AC-17, SC-8
```

**DD-05.3-02 — Transitive NIST mappings are derived, not authored**, and are
labelled with their derivation path. An assessor asked *"why does this violate
AC-17?"* must be able to see the chain.

### 4.4 ISO — identifiers only

**NFR-CMP-002.** ISO/IEC 27001 is a paid standard whose text cannot be lawfully
redistributed.

```yaml
framework_item:
  framework: iso
  benchmark: iso_27001
  version: "2022"
  item_id: "A.9.4.2"
  title: null                    # NOT STORED
  text_redistributable: false
  satisfied_by: [NSCA-MGMT-002]
```

**INV-05.3-02 — `text_redistributable: false` is enforced at the data layer.**
The import pipeline refuses to persist title or body text for such items, and the
report renders identifiers only. Compliance is a schema property, not a
convention someone must remember.

The same flag applies to CIS body text: CIS identifiers are cited, CIS prose is
not reproduced.

Getting this right is itself a credibility signal — anyone familiar with the
standards landscape will notice, and anyone unfamiliar loses nothing.

---

## 5. Automation coverage manifest

FR-CTL-015. The first thing a serious assessor asks for, and almost no tool
provides.

```
CIS Cisco IOS 15 Benchmark v4.1.0 — Automation Coverage

  Total recommendations                    187
  ──────────────────────────────────────────────
  Automated from configuration             154   (82%)
  Requires manual assessment                21   (11%)
      physical security of the device
      documented change management process
      periodic personnel authorisation review
  Requires data not collected                7   (4%)
      needs `show crypto pki certificates`
      needs `show logging` runtime state
  Not yet implemented                        5   (3%)
      tracked in backlog, visible to the user
```

| Status | Meaning |
|---|---|
| `automated` | Mapped to ≥ 1 native control that evaluates from available facts |
| `manual_only` | Not determinable from configuration by anyone |
| `data_unavailable` | Determinable, but requires an artifact type not collected |
| `not_implemented` | Determinable and collectable; no control authored yet |

**INV-05.3-03 — Every imported item receives a status.** An item silently absent
from the manifest is indistinguishable from an item that passed, which is the
same class of failure as a silent UNKNOWN.

Two reasons this is mandatory:

**An assessor cannot sign off without it.** If they state *"assessed against
CIS"* and 33 recommendations were silently skipped, that is a professional
problem for them. Publishing coverage protects the person using the product.

**It is honest about a real limit.** *"Ensure the device is physically secured"*
cannot be determined from a text file by anyone. Distinguishing automatable from
procedural is audit maturity, not weakness.

### 5.1 Equivalence rationale

FR-CTL-016. CIS states an audit procedure; the platform checks a normalised fact.
The reasoning is recorded:

```yaml
framework_item: CIS-IOS-1.2.4
stated_audit: "show run | sec vty → verify transport input ssh"
platform_check: >
  mgmt.protocols.telnet.enabled == false and
  mgmt.protocols.http.enabled == false
equivalence: >
  The extractor parses all `line vty` blocks including overlapping ranges,
  resolving effective transport per line. This is strictly broader than the
  stated procedure, which inspects only the first matching block.
divergence: broader
reviewed_by: p.sharma
reviewed_at: 2026-08-30
```

`divergence ∈ { equivalent, broader, narrower }`. **A `narrower` mapping is a
defect** — the platform would pass an item the benchmark would fail — and is
rejected at ratification.

---

## 6. Version pinning and the matrix

A rulebook is a matrix, not an artifact:

```
                CIS v4.0   CIS v4.1   STIG 2025-10   STIG 2026-01
  IOS 12.x         ✓          ✓            —              —
  IOS 15.x         ✓          ✓            ✓              ✓
  IOS-XE 16.x      —          ✓            ✓              ✓
  NX-OS 9.x        —          —            ✓              ✓
```

**DD-05.3-03 — No content for a platform/version combination means refusal, not
approximation.** The system does not silently fall back to the nearest benchmark.

```
⚠ No CIS content exists for NX-OS 9.3 at any version.
  This framework cannot be evaluated for 14 devices.
  Available for these devices: DISA STIG 2026-01.
```

An approximate audit that looks defensible is worse than an honest refusal.

---

## 7. Conflict resolution

FR-CTL-012. Selecting CIS and STIG simultaneously produces disagreements.

```
resolve(item_a, item_b, native_control) →
  if both map to the same native control:
      if requirements identical      → no conflict
      if one strictly stricter       → apply stricter, report both
      if genuinely contradictory     → report conflict, verdict UNKNOWN
```

Strictness is comparable only where the requirement is a threshold on the same
fact:

```
NSCA-MGMT-004 · Session idle timeout
  Device value    600 s
  CIS-IOS-1.1.5   ≤ 600 s   → PASS
  STIG V-216620   ≤ 300 s   → FAIL
  Applied: STIG (stricter)  → FAIL
  ⚠ Framework conflict; reported against the stricter requirement.
```

**DD-05.3-04 — Genuinely contradictory requirements yield UNKNOWN.** If one
framework requires a setting enabled and another requires it disabled, there is
no compliant configuration and no principled winner. Silently choosing one would
produce a confident verdict for a device that cannot satisfy both.

---

## 8. Update governance

FR-ADM-007. Framework releases never silently change results.

```
1  DETECT     new release available
2  PREVIEW    dry-run against the most recent campaign
3  QUANTIFY   exactly which findings change
4  REVIEW     assessor examines the delta
5  RATIFY     second authorised user approves
6  ADOPT      current for future campaigns only
```

```
DISA STIG Cisco IOS-XE Router
  2025-10 (Rel 12)  →  2026-01 (Rel 13)

Content    + 6 new · ~ 4 modified · − 2 withdrawn

Estate impact — dry run against Campaign Q3-2026
  + 6 new findings across 41 devices
  ~ 2 findings CAT II → CAT I
  − 2 findings would close
  compliance delta: −0.03

  [ Review ]  [ Ratify ]  [ Defer ]
```

**INV-05.3-04 — Adoption never retroactively alters an issued campaign.**
Historical campaigns remain pinned to the content versions they used, which is
what makes benchmark drift decomposition possible (PRD 11 §10):

```
Q3 78%  →  Q4 71%
  −4 pp   benchmark updated CIS v3.0.1 → v3.1.0 (14 added, 6 tightened)
  −5 pp   genuine configuration regressions across 7 devices
  +2 pp   verified remediations closed (11 findings)
```

---

## 9. Interfaces

```
import(source_type, content, version)  → ImportResult
map(framework_item, native_control, equivalence) → Mapping | ValidationError
manifest(framework, benchmark, version) → AutomationCoverageManifest
preview(framework, from_version, to_version, campaign) → ImpactPreview
resolve_conflicts(items[], native_control) → ⟨applied, conflicts[]⟩
```

---

## 10. Edge cases

| Case | Handling |
|---|---|
| Framework item mapping to zero native controls | Status `not_implemented`; appears in the manifest backlog |
| Framework item mapping to many native controls | Item satisfied only if all mapped controls pass; partial mapping recorded |
| STIG rule with no CCI references | NIST mapping absent; recorded rather than inferred |
| CIS recommendation whose Default Value contradicts the rulepack's defaults table | Conflict raised; benchmark value preferred but flagged for review |
| Two benchmark versions selected simultaneously | Rejected — one version per framework per campaign |
| Framework covering a platform with no rulepack | Items imported; all statuses `data_unavailable` |
| Withdrawn item still referenced by an open finding | Finding retained; annotated as evaluated against a withdrawn item |

**The withdrawn-item case is a real audit problem.** A finding raised under STIG
Rel 12 whose rule is withdrawn in Rel 13 does not become invalid retroactively —
it was correct when issued. The annotation preserves that distinction.

---

## 11. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Framework selection changes computed verdicts | V-05.3-004 | INV-05.3-01 violation; results become framework-dependent |
| Restricted text persisted | V-05.3-002 | **Licensing violation** |
| Item silently absent from the manifest | V-05.3-003 | Assessor signs off on unassessed scope |
| Narrower equivalence accepted | V-05.3-006 | Platform passes what the benchmark fails |
| Approximate version fallback | V-05.3-005 | Defensible-looking, indefensible audit |
| Adoption alters an issued campaign | V-05.3-008 | Audit history rewritten |

---

## 12. Verification

```
V-05.3-001   STIG XCCDF imports directly with CCI-derived NIST mappings
  Requirement  FR-CTL-010, §4.1
  Method       INTEGRATION
  Procedure    Import a published DISA STIG XCCDF bundle.
  Acceptance   All rules imported with id, severity, check and fix text.
               CCI references produce NIST mappings automatically.
               Zero manual mapping required for the STIG→NIST relationship.
  Severity     MAJOR
```

```
V-05.3-002   Non-redistributable text is never persisted
  Requirement  NFR-CMP-001, NFR-CMP-002, INV-05.3-02
  Method       UNIT + INTEGRATION
  Procedure    Import CIS and ISO content. Inspect the datastore and every
               report, export format and API response.
  Acceptance   Zero occurrences of CIS or ISO body text. Identifiers present.
               Import pipeline refuses to persist title/body for items with
               text_redistributable == false.
  Severity     BLOCKING
```

```
V-05.3-003   Every imported item carries an automation status
  Requirement  FR-CTL-015, INV-05.3-03
  Method       CORPUS
  Procedure    Import all supported framework content; generate manifests.
  Acceptance   100% of items carry a status. Counts sum to the total.
               Zero items absent from the manifest.
  Severity     BLOCKING
```

```
V-05.3-004   Framework selection does not alter computed verdicts
  Requirement  INV-05.3-01
  Method       INTEGRATION
  Procedure    Assess the same artifacts three times: CIS only, STIG only,
               all four frameworks.
  Acceptance   Identical native control verdicts in all three runs.
               Only the attached framework identifiers differ.
  Severity     BLOCKING
  Note         This is what makes multi-framework support nearly free.
```

```
V-05.3-005   Missing version content is refused, not approximated
  Requirement  DD-05.3-03
  Method       INTEGRATION
  Procedure    Select CIS for a platform/version with no CIS content.
  Acceptance   Refusal with a clear message naming available alternatives.
               Zero evaluations against a substituted benchmark version.
  Severity     BLOCKING
```

```
V-05.3-006   Narrower equivalence mappings are rejected
  Requirement  FR-CTL-016, §5.1
  Method       UNIT
  Procedure    Submit a mapping whose platform check is strictly weaker than
               the framework item's stated audit procedure.
  Acceptance   Rejected at ratification with divergence: narrower.
  Severity     BLOCKING
```

```
V-05.3-007   Conflicts apply the stricter requirement and are reported
  Requirement  FR-CTL-012, DD-05.3-04
  Method       UNIT
  Procedure    (a) CIS ≤600 s versus STIG ≤300 s, device at 600 s.
               (b) One framework requiring a feature enabled, another
                   requiring it disabled.
  Acceptance   (a) FAIL under the stricter, both requirements reported.
               (b) UNKNOWN with the contradiction reported. Zero silent
                   selection of a winner.
  Severity     BLOCKING
```

```
V-05.3-008   Adoption does not alter issued campaigns
  Requirement  INV-05.3-04, FR-CTL-011
  Method       INTEGRATION
  Procedure    Issue a campaign at STIG 2025-10. Import and ratify 2026-01.
               Re-open and re-render the historical campaign report.
  Acceptance   Byte-identical to the original. Pinned versions unchanged.
  Severity     BLOCKING
```

```
V-05.3-009   Mapping cardinality is measured, not assumed
  Requirement  §3.1
  Method       CORPUS
  Procedure    After importing all framework content, compute the actual
               distribution of universal / conditional / platform-specific
               mappings.
  Acceptance   Measured figures published and the PRD estimates corrected
               where they diverge by more than 10 percentage points.
  Severity     MINOR
  Note         The ~70/20/10 split is a planning estimate and must not
               remain unverified.
```

```
V-05.3-010   Update preview quantifies estate impact before adoption
  Requirement  FR-ADM-007
  Method       INTEGRATION
  Procedure    Preview a framework update against a completed campaign.
  Acceptance   Reports added/modified/withdrawn counts, new findings,
               severity changes, closures and compliance delta — all
               computed against the real estate, before ratification.
  Severity     MAJOR
```

```
V-05.3-011   CIS Default Value populates the defaults table
  Requirement  §4.2, TRD-03.2 §4.3
  Method       INTEGRATION
  Procedure    Import a CIS benchmark; inspect the platform's defaults table.
  Acceptance   Default Value entries present with source citation
               "CIS <benchmark> <version>, Default Value". Measurable
               reduction in default_unknown facts on corpus devices.
  Severity     MAJOR
```

---

## 13. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should CIS extraction be automated end-to-end with ratification sampling, or item-by-item confirmation? | Full confirmation is safest but 187 items per benchmark is a large manual burden. Current design: item-by-item for security-relevant fields, with high-confidence extractions batch-confirmable |
| Q2 | Should transitive NIST mappings via both CIS and CCI be merged or kept separate? | Merging simplifies reporting; keeping them separate preserves the derivation chain for challenge. Current design: merged for display, derivation retained and shown on request (DD-05.3-02) |
| Q3 | Should a campaign be permitted to select two versions of one framework for comparison? | Useful for previewing an update in situ, but complicates conflict resolution and pinning semantics. Current design: one version per framework; comparison is served by the preview mechanism |
