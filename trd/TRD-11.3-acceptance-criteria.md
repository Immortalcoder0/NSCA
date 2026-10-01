# TRD-11.3 · Acceptance Criteria and Coverage Assertion

---

## 1. Scope

The release gate: the fourteen **blocking** criteria that must pass before the
product can ship, the coverage assertion that every requirement is verified, and
the acceptance procedure.

---

## 2. The acceptance principle

> **A product that cannot demonstrate its own guarantees has not earned the right
> to make claims about anyone else's network.**

The blocking criteria are not a sample of the test suite. They are the specific
proofs of the four guarantees (G1–G4) and the five mandated platform features.
A release with any of them failing is not a release with known issues; it is a
product whose central claims are unproven.

---

## 3. The fourteen blocking criteria

Ordered by the guarantee or requirement they prove.

### G2 · Never over-claim — five criteria

```
B1   V-03.2-001   Absence never becomes false
     A boolean fact absent from configuration, with no known default,
     resolves to default_unknown with no value assigned.
     Zero instances of value == false.

B2   V-05.2-001   A missing required fact yields UNKNOWN, never PASS
     For every control × every required fact, omitting the fact produces
     UNKNOWN. Zero PASS verdicts across all pairs.

B3   V-05.1-002   Comparison with unknown yields unknown, never false
     Every operator, every type, against ⊥ operands. 100% yield ⊥.

B4   V-03.2-005   Uncertainty propagates through derived facts
     A derived fact inherits the weakest provenance of its inputs.
     Zero derived facts with stronger provenance than their weakest input.

B5   V-05.2-005   Scope contamination downgrades passing controls
     An unassessed capability downgrades every passing control in its
     family to PASS (PARTIAL) with the reason attached.
```

**Why five.** G2 is the guarantee that distinguishes this product, and it can be
violated independently at five layers — extraction, evaluation, the expression
language, derivation, and reporting scope. A single criterion would leave four
paths open.

### G1 · Determinism — two criteria

```
B6   V-10.1-001   Byte-identical output for identical inputs
     20 golden campaigns × 10 runs × 2 host configurations, varied
     concurrency, locale, timezone and input ordering.
     Identical report hashes throughout.

B7   V-10.1-002   No model inference in the assessment path
     Full campaigns execute identically with all model endpoints
     unreachable. Zero inference calls reachable from assessment.
```

### G3 · Evidence binding — two criteria

```
B8   V-02.1-002   Line ranges resolve to exact source text
     Every parse node's line range extracts text matching its raw content,
     across the full corpus.

B9   V-03.1-002   Every fact carries resolvable provenance
     Every explicit fact's provenance resolves to real artifact text
     matching its recorded excerpt.
```

### G4 · Assessor independence — one criterion

```
B10  V-01.3-001   No write-capable code path exists
     Every transport call site draws from the compile-time allowlist.
     Zero allowlist entries contain a configuration, write, commit, copy
     or reload verb. No signature accepts a free-form command string.
```

### Polarity — one criterion

```
B11  V-08.3-002   A polarity-inverting rule cannot be saved without
                  explicit confirmation
     Enforced as a data constraint, reproducible with the UI bypassed.
     The generated expression visibly contains the inversion.
```

**Why polarity has its own blocking criterion.** Every other error in the system
degrades toward uncertainty. This one degrades toward **false confidence**, is
invisible in output, and is systematic across every device of the affected
platform.

### Robustness — one criterion

```
B12  V-11.2-001   Semantics-preserving mutation produces identical facts
     Full mutation catalogue across the full corpus.
     Zero relation violations.
```

### The core product claims — two criteria

```
B13  V-08.3-011   A new platform is taught without code change
     Using only the running system: mine, propose, confirm, synthesise,
     validate, ratify, re-assess a held-out platform to ≥ 70% coverage.
     Zero source modification, zero restart, zero redeployment.

B14  V-08.4-007   Onboarding target met by a real administrator
     A network administrator unfamiliar with the tool teaches the untaught
     holdout, unaided and timed, to ≥ 70% coverage in ≤ 15 minutes.
     Zero expression syntax encountered.
```

**B14 requires a genuinely fresh holdout** (TRD-11.1 INV-11.1-02). Teaching it
during earlier testing consumes it and invalidates the gate.

---

## 4. Mandated feature acceptance

The five features the problem statement enumerates. Each must be demonstrable end
to end.

| # | Feature | Demonstration | Criteria |
|---|---|---|---|
| **F1** | Unified ingestion, single and bulk, **including cloud JSON** | Upload 200 mixed artifacts across ≥ 5 platforms plus AWS/Azure policy JSON; all parsed or correctly routed | V-01.1-002, V-02.1-006 |
| **F2** | Training GUI that persists and changes the next run | Teach the holdout; re-assess; coverage measurably increased | B13, B14 |
| **F3** | Multi-framework engine, user-selected | Same artifacts assessed against CIS-only, STIG-only and all four; identical verdicts, different reported identifiers | V-05.3-004 |
| **F4** | **One PDF per device** with serials, severity, version-specific remediation | Generate reports; verify all mandated sections including serial numbers | V-09.1-004, V-01.2-007, V-07.1-001 |
| **F5** | Vendors, standards and OS versions as data | Add a platform, a framework and a schema fact with zero code change | B13, V-03.3-003, NFR-MNT-002 |

**F1's cloud JSON requirement is easy to overlook.** The problem statement lists
cloud-native firewalls and SASE platforms twice; a CLI-only implementation fails
an explicitly stated requirement.

**F4's serial number requirement forces multi-artifact ingestion.** Serials come
from `show inventory`, not the running configuration — a system that ingests only
running-configs cannot populate a mandated report section.

---

## 5. Coverage assertion

**INV-11.3-01 — Every FR and NFR maps to at least one verification criterion,
and every criterion maps to at least one requirement.**

Enforced as a CI gate (V-11.1-001). The map is generated, not maintained by hand.

| Area | Requirements | Primary TRD |
|---|---|---|
| Campaigns | 10 | 01.1, 10.1 |
| Ingestion | 18 | 01.1, 01.3 |
| Fingerprinting | 6 | 01.2 |
| Parsing | 14 | 02.1, 02.2, 02.3 |
| Extraction | 10 | 03.1, 03.2, 03.3 |
| Graph | 8 | 04.1, 04.2 |
| Control evaluation | 17 | 05.1, 05.2, 05.3 |
| Risk | 10 | 06.1, 06.2, 06.3 |
| Remediation | 11 | 07.1 |
| Learning | 28 | 08.1, 08.2, 08.3, 08.4 |
| Findings | 16 | 05.2, 09.1 |
| Reporting | 21 | 09.1 |
| Integrity | 12 | 10.1, 10.2 |
| Interface | 12 | 09.1, 08.2 |
| Administration | 10 | 01.3, 10.2 |
| API | 6 | 01.3, 10.2 |
| **Functional** | **209** | |
| Non-functional | 71 | 11.1, 11.2, 13 |

**Total verification criteria across the TRD set: ~290**, of which 14 are
blocking, ~130 major, and the remainder minor.

---

## 6. Acceptance procedure

```
1  AUTOMATED     unit, property, integration, corpus, metamorphic,
                 determinism golden set                        [ CI ]
2  DIFFERENTIAL  device truth, reference implementation,
                 golden set false-positive rate              [ manual ]
3  BLOCKING      all 14 criteria executed and recorded       [ manual ]
4  FEATURE       five mandated features demonstrated end to end
5  MANUAL        usability procedures with recorded outcomes
6  SIGN-OFF      results recorded; failures block
```

### 6.1 Manual procedures

Four properties central to the product's value have **no automated oracle**
(TRD-11.1 §9). They are executed as recorded procedures, not asserted:

| Procedure | Criterion | What is judged |
|---|---|---|
| Administrator teaches the holdout unaided, timed | B14 | Usability by the intended user |
| Three readers classify verdict states in monochrome | V-09.1-006 | UNKNOWN never read as PASS |
| Administrator locates an inherited setting from its evidence | V-02.3-010 | Evidence comprehensibility |
| Three readers state what happens to "unreachable" findings | V-06.2-005 | Absence of misrepresentation |

**These are stated rather than quietly omitted.** Claiming automated coverage of
properties that cannot be automatically verified would be the same over-claiming
the product exists to prevent.

### 6.2 Failure handling

| Severity | On failure |
|---|---|
| **BLOCKING** | Release impossible. No waiver, no sign-off, no exception |
| **MAJOR** | Release requires recorded sign-off plus a remediation plan with a date |
| **MINOR** | Tracked; does not block |

**DD-11.3-01 — Blocking criteria admit no waiver process.** A waiver mechanism
becomes a habit. If a criterion is genuinely too strict, the correct response is
to change the criterion deliberately and record why — not to bypass it under
schedule pressure.

---

## 7. Release record

Every release produces a signed record:

```yaml
release: v1.0.0
date: 2026-11-14

blocking_criteria:
  total: 14
  passed: 14
  results:
    - { id: B1,  criterion: V-03.2-001, result: PASS, evidence: run-8841 }
    - { id: B2,  criterion: V-05.2-001, result: PASS, evidence: run-8841 }
    ...
    - { id: B14, criterion: V-08.4-007, result: PASS,
        evidence: "manual-2026-11-12; administrator A.R.; 11 min 40 s;
                   holdout: Extreme EXOS; coverage 0% → 74%" }

major_criteria:   { total: 131, passed: 129, signed_off: 2 }
minor_criteria:   { total: 145, passed: 141 }

measured:
  golden_set_false_positive_rate: 1.2%
  golden_set_false_negative_rate: 0.4%
  differential_agreement_device_truth: 99.3%
  differential_agreement_reference_impl: 96.1%
  corpus_platforms: 6
  corpus_configurations: 247
  learning_curve: [47, 31, 22, 14, 11, 8]
  polarity_correction_rate: 3.1%

knowledge_base:
  engine: v1.0.0
  schema_registry: v1.0.0
  rulepacks: [ ... ]
  control_packs: [ nsca-core@1.0.0 ]
  automation_coverage:
    - { framework: cis,  benchmark: cisco_ios_15, automated: 82% }
    - { framework: stig, benchmark: cisco_iosxe_router, automated: 87% }

holdouts_remaining: 2
```

**INV-11.3-02 — Measured figures appear in the release record, not marketing
claims.** The learning curve, the false-positive rate and the automation coverage
are all evidence produced by the acceptance run. A figure that cannot be traced
to a recorded run does not appear.

---

## 8. What acceptance does not establish

Stated explicitly.

| Not established | Why |
|---|---|
| That the control library's requirements are correct | No oracle exists — it is a professional judgement, addressed by expert review at ratification |
| That the platform finds every misconfiguration | Coverage is measured and published; completeness is not claimed |
| That remediation is safe in every operational context | Safety checks cover modelled lockout modes; operational context is not fully knowable |
| That a capability leaving no configuration trace can be found | Out of scope by construction (PRD 00 §5.2) |
| That the tool is correct on a platform outside the corpus | Corpus platforms are enumerated; extrapolation is not claimed |

**The last row matters most.** The product's honest claim is: *"verified on these
six platforms; capable of being taught others; coverage reported per platform."*
It is not *"works on any vendor."*

---

## 9. Verification of this document

```
V-11.3-001   All fourteen blocking criteria are executable and recorded
  Method       INTEGRATION
  Procedure    Execute the acceptance procedure end to end on a
               release candidate.
  Acceptance   All 14 executed. Each result traceable to a recorded run
               with evidence. Zero criteria skipped or assumed.
  Severity     BLOCKING
```

```
V-11.3-002   Requirement coverage is complete and generated
  Requirement  INV-11.3-01
  Method       INTEGRATION (CI gate)
  Procedure    Generate the traceability map from PRD requirements and TRD
               criteria.
  Acceptance   Zero unmapped requirements. Zero orphan criteria. The map is
               generated, not hand-maintained.
  Severity     BLOCKING
```

```
V-11.3-003   Blocking failures cannot be waived
  Method       INTEGRATION
  Procedure    Attempt to complete a release record with a blocking criterion
               marked failed or skipped.
  Acceptance   Refused. No waiver field exists in the record schema.
  Severity     BLOCKING
```

```
V-11.3-004   The release record's measured figures trace to runs
  Requirement  INV-11.3-02
  Method       INTEGRATION
  Procedure    For every measured figure in a release record, resolve its
               evidence reference.
  Acceptance   100% resolve to a recorded run with retained output.
  Severity     MAJOR
```

```
V-11.3-005   Holdout accounting is maintained
  Requirement  TRD-11.1 INV-11.1-02
  Method       INTEGRATION (CI gate)
  Procedure    After a release consuming a holdout, verify the count and the
               absence of the consumed platform from all shipped content.
  Acceptance   holdouts_remaining decremented. Consumed platform now present
               in rulepacks. At least one holdout remains, or the release is
               blocked pending designation of a new one.
  Severity     BLOCKING
```

---

## 10. Summary — the fourteen, in one place

| # | Proves | Criterion |
|---|---|---|
| B1 | Absence never becomes false | V-03.2-001 |
| B2 | Missing fact ⇒ UNKNOWN, never PASS | V-05.2-001 |
| B3 | Comparison with ⊥ ⇒ ⊥, never false | V-05.1-002 |
| B4 | Uncertainty propagates through derivation | V-03.2-005 |
| B5 | Unassessed capability downgrades passes | V-05.2-005 |
| B6 | Byte-identical output for identical inputs | V-10.1-001 |
| B7 | No model in the assessment path | V-10.1-002 |
| B8 | Line ranges resolve to source text | V-02.1-002 |
| B9 | Every fact has resolvable provenance | V-03.1-002 |
| B10 | No write-capable code path exists | V-01.3-001 |
| B11 | Polarity requires explicit confirmation | V-08.3-002 |
| B12 | Facts stable under semantics-preserving mutation | V-11.2-001 |
| B13 | New platform taught with zero code change | V-08.3-011 |
| B14 | Real administrator onboards a holdout in ≤ 15 min | V-08.4-007 |

**Ten of the fourteen prove that the platform refuses to over-claim.** That
proportion is deliberate: it reflects where this product's value and its risk
both concentrate.
