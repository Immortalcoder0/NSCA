# TRD-05.2 · Evaluation, Verdicts and Coverage

---

## 1. Scope

Orchestration of control evaluation: applicability determination, verdict
production, coverage scoring, vacuity classification, and scope contamination.

> This is where **G2 — never over-claim** becomes an observable property of the
> product rather than an aspiration.

**Out of scope:** the assertion language (TRD-05.1); framework mapping
(TRD-05.3); severity weighting (TRD-06.1).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-CTL-003 | `requires_facts` declaration |
| FR-CTL-004 | Four verdicts |
| FR-CTL-005 | Missing facts force UNKNOWN |
| FR-CTL-006 | NOT_APPLICABLE excluded from the denominator |
| FR-CTL-007 | Coverage score |
| FR-CTL-008 | Meaningful versus vacuous passes |
| FR-CTL-009 | Scope contamination |
| FR-CTL-013 | Applicability clauses |
| FR-CTL-017 | Deterministic, no model |

---

## 3. Design

### 3.1 Evaluation pipeline

```
  for each control C:
      1  applicability      → NOT_APPLICABLE, or continue
      2  fact gathering     → collect C.requires_facts
      3  knowledge check    → any ⊥ ? → UNKNOWN, or continue
      4  assertion          → PASS | FAIL
      5  vacuity            → PASS meaningful | PASS vacuous
      6  contamination      → PASS → PASS (PARTIAL)
```

**INV-05.2-01 — Step 3 precedes step 4.** The knowledge check is not an outcome
of evaluating the assertion; it is a gate before it. This makes UNKNOWN a
structural property of the architecture rather than something an implementer must
remember to handle.

A subtlety: step 3 does **not** short-circuit when the assertion can be decided
despite the unknown. Three-valued logic (TRD-05.1 §3.2) handles that —
`false and ⊥ = false` yields a legitimate FAIL. The gate applies only where the
assertion's own result is `⊥`.

```
step 3/4 combined, precisely:
    result = evaluate(C.assert, facts)
    if result == ⊥  → UNKNOWN (with the undetermined fact named)
    if result == false → FAIL
    if result == true  → PASS
```

### 3.2 Applicability

```yaml
applies_to:
  platform_family: "*"                    # or a list
  version_range: ">=15.0"
  requires_capability: [management_access]
  excludes_platform: [aws_sg]
```

```
applicable(C, device) =
      platform matches
  and version in range
  and all required capabilities present
  and platform not excluded
```

| Outcome | Verdict |
|---|---|
| Not applicable | `NOT_APPLICABLE` — excluded from the denominator |
| Capability presence undetermined | **`UNKNOWN`**, not NOT_APPLICABLE |

**DD-05.2-01 — Undetermined applicability is UNKNOWN, not NOT_APPLICABLE.**
Excluding a control from the denominator because we could not tell whether it
applies would silently inflate the compliance percentage. If we do not know
whether a device has a routing engine, we do not know whether routing-protocol
authentication controls apply — and that is a coverage gap, not an exemption.

### 3.3 The four verdicts

| Verdict | Numerator | Denominator | Meaning |
|---|---|---|---|
| `PASS` | ✓ | ✓ | Checked, compliant |
| `FAIL` | — | ✓ | Checked, violating |
| `UNKNOWN` | — | ✓ | Could not determine |
| `NOT_APPLICABLE` | — | — | Question is meaningless here |

Plus one qualifier: `PASS (PARTIAL)` — a PASS whose scope is bounded (§3.6).

### 3.4 Coverage scoring

```
applicable  = total − NOT_APPLICABLE
determined  = PASS + FAIL
coverage    = determined / applicable
compliance  = PASS / determined
```

**INV-05.2-02 — Compliance is over *determined*, not over *applicable*.**

Consider a device with 155 applicable controls, 30 determined, 28 passing:

- Compliance over determined: **93%** — with coverage 19%
- Compliance over applicable: **18%**

The first is honest and requires coverage to be read alongside it. The second
conflates "we could not check" with "it failed", which understates posture and
would drive remediation effort at phantom problems.

**Therefore coverage is reported with equal prominence everywhere compliance
appears.** A compliance figure without a coverage figure is meaningless, and the
report format (PRD 10 §2.2) enforces the pairing.

Ratios are stored as exact integer pairs and rendered at fixed precision (D5).

### 3.5 Vacuity classification

FR-CTL-008. Two devices pass the SNMP control: one because SNMPv3 is properly
configured, one because SNMP is not enabled at all. Identical tick, different
durability.

```yaml
vacuity:
  meaningful_when: "snmp.enabled == true"
```

```
classify(C, facts) →
  if C has no vacuity clause          → meaningful
  if evaluate(C.vacuity, facts) == true  → meaningful
  if == false                         → vacuous
  if == ⊥                             → meaningful      # DD-05.2-02
```

**DD-05.2-02 — Undetermined vacuity defaults to meaningful.** Vacuity is a
*quality* signal, not a safety one. Reporting an undetermined pass as vacuous
would overstate a weakness, which is a different kind of inaccuracy from the one
G2 guards against. The conservative direction here is the opposite of the
conservative direction for verdicts.

Reported as:

```
Compliance          94%
  meaningful        63%     feature present and securely configured
  vacuous           31%     feature absent or disabled
```

**Anticipated challenge:** *"if SNMP is disabled, the device is secure — why is
that a weaker pass?"* The answer is that it is not less secure **today**; it is
**less assured tomorrow**. A vacuous pass rests on an absent feature rather than
a configured control. Nothing constrains SNMP if anyone enables it, and no
control will warn when they do.

### 3.6 Scope contamination

FR-CTL-009. The most important safety property in the verdict model.

**A capability the system cannot assess can render an existing PASS wrong without
ever producing a FAIL.**

```
NSCA-MGMT-002   telnet ✓  http ✓  ftp ✓   → PASS
```

Except the device also exposes `winbox` on TCP/8291 — a second management path
no control contemplates. The conclusion *"management access is secure"* is
technically true and practically false. You verified the doors you knew about
while a window stood open.

This is worse than a FAIL, because a FAIL gets remediated and this gets filed as
evidence of compliance.

```
contaminate(verdicts, unaudited_facts) →
  for each unaudited fact u:
      family = u.definition.category
      for each verdict v where v == PASS and v.control.family == family:
          v → PASS (PARTIAL)
          v.contamination_reason = "unassessed capability: {u.path}"
```

**INV-05.2-03 — Findings are not independent.** Discovering a new capability
re-opens questions previously considered closed, and the system propagates that
backwards over already-computed verdicts.

**DD-05.2-03 — Contamination affects PASS only.** A FAIL is already actionable;
a FAIL adjacent to an unassessed capability is still a FAIL. UNKNOWN is already
undetermined. Only PASS carries a claim that contamination can invalidate.

Contaminated passes count as PASS in the compliance numerator — the control did
pass, within its scope — but the report states the bound. Removing them from the
numerator would conflate two distinct concepts and make the compliance figure
unstable as the schema grows.

### 3.7 Scope-qualified aggregation

Where facts are emitted per VTY range or per VDOM (TRD-03.1 §3.4), the control
declares aggregation (TRD-05.1 §3.6), defaulting to `all`.

The verdict records which instance decided it:

```
NSCA-MGMT-002 → FAIL
  aggregation: all over 2 scoped instances
  vty[0..4]   → FAIL  (telnet permitted, line 143)
  vty[5..15]  → PASS
  deciding instance: vty[0..4]
```

### 3.8 Evaluation ordering and independence

**INV-05.2-04 — Controls are independent.** No control reads another's verdict.
Contamination (§3.6) is a post-pass over the complete verdict set, not a
dependency during evaluation. This preserves order-independence (D6) and permits
parallel evaluation with deterministic aggregation (D7).

### 3.9 Unknown reason classification

Every UNKNOWN carries a reason drawn from a closed set, sourced from the
evaluation trace (TRD-05.1 INV-05.1-02):

| Reason | Source | Remedy |
|---|---|---|
| `facts_missing` | Rulepack cannot produce the fact | Extend the rulepack |
| `default_unknown` | No documented platform default | Configure explicitly, or import vendor documentation |
| `parse_gap` | Construct unmatched by any extractor | Training queue |
| `export_incomplete` | Terse export | Re-collect verbosely |
| `data_not_collected` | Requires an artifact not supplied | Supply `show inventory` etc. |
| `conflict` | Extractor conflict | Rulepack defect |
| `applicability_undetermined` | Capability presence unknown | Extend the rulepack |
| `unresolved_inheritance` | Missing configuration layer | Supply the parent configuration |

This is what makes the report's Unassessed section actionable rather than a bare
count (PRD 10 §2.6).

---

## 4. Interfaces

**Input:** `⟨resolved_fact_set, control_pack, platform, version, graph?,
unaudited_facts[]⟩`

**Output**

```
EvaluationResult {
  verdicts[]: {
     control, verdict, pass_quality?, contamination_reason?
     unknown_reason?, deciding_instance?, trace
  }
  counts: ⟨pass, fail, unknown, not_applicable, pass_partial⟩
  coverage: ⟨determined, applicable⟩       // exact pair, not float
  compliance: ⟨pass, determined⟩
  meaningful_ratio: ⟨meaningful, pass⟩
  unknown_reasons: map<reason, control[]>
}
```

---

## 5. Edge cases

| Case | Handling |
|---|---|
| Control with an empty `requires_facts` | Permitted only for graph controls and constant assertions; flagged at load otherwise |
| All controls NOT_APPLICABLE | applicable = 0; coverage undefined, reported as such rather than 0% or 100% |
| Graph control on a single-device campaign | Evaluated; multi-device queries return UNKNOWN with a reason |
| Contamination from a capability in an unregistered category | Cannot occur — category is a mandatory registration field (TRD-03.3) |
| Control whose vacuity clause references an unrequired fact | Load error; vacuity clause facts must be declared |
| Device where every fact is default_unknown | All applicable controls UNKNOWN; coverage 0%; report states the device could not be assessed |
| Two controls asserting contradictory requirements | Both evaluated independently; the conflict surfaces at framework mapping (TRD-05.3 §9.4) |

**The all-NOT_APPLICABLE case matters for cloud policy objects**, which have far
fewer applicable controls than a physical device. Reporting `coverage: undefined`
rather than a misleading percentage is the honest treatment.

---

## 6. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Knowledge gate bypassed | V-05.2-001 | **G2 violation** — unknowns become passes. The product's central failure |
| Compliance computed over applicable | V-05.2-003 | Understates posture; drives wrong remediation |
| NOT_APPLICABLE used for undetermined applicability | V-05.2-002 | Silently inflates compliance |
| Contamination not applied | V-05.2-005 | Passes reported without their bound |
| Vacuity misclassified as vacuous when unknown | V-05.2-004 | Overstates weakness |
| Control interdependence introduced | V-05.2-007 | G1 violation |

---

## 7. Verification

```
V-05.2-001   A missing required fact yields UNKNOWN, never PASS
  Requirement  FR-CTL-005, INV-05.2-01, G2
  Method       PROPERTY + CORPUS
  Procedure    For every control C and every fact F ∈ C.requires_facts,
               construct a fact set in which F has provenance
               default_unknown, holding all other facts at values that
               would otherwise produce PASS. Evaluate C.
  Acceptance   verdict == UNKNOWN for 100% of (C, F) pairs.
               Zero instances of PASS.
  Severity     BLOCKING
  Note         Referenced in the TRD README as one of the five criteria that
               prove the product's central claims.
```

```
V-05.2-002   Undetermined applicability is UNKNOWN, not NOT_APPLICABLE
  Requirement  DD-05.2-01
  Method       UNIT
  Procedure    Control requiring a capability whose presence fact is
               default_unknown.
  Acceptance   UNKNOWN with reason applicability_undetermined.
               Zero NOT_APPLICABLE verdicts. Denominator unaffected.
  Severity     BLOCKING
```

```
V-05.2-003   Coverage and compliance arithmetic
  Requirement  FR-CTL-006, FR-CTL-007, INV-05.2-02
  Method       PROPERTY + UNIT
  Procedure    Generated verdict sets across the full outcome space.
  Acceptance   coverage = determined/applicable;
               compliance = pass/determined;
               NOT_APPLICABLE never in either denominator.
               All ratios exact integer pairs (D5).
  Severity     BLOCKING
```

```
V-05.2-004   Vacuity classification
  Requirement  FR-CTL-008, DD-05.2-02
  Method       UNIT + CORPUS
  Procedure    (a) SNMP enabled and securely configured.
               (b) SNMP disabled.
               (c) SNMP presence undetermined.
  Acceptance   (a) meaningful, (b) vacuous, (c) meaningful.
               Report shows compliance, meaningful and vacuous separately.
  Severity     MAJOR
```

```
V-05.2-005   Scope contamination downgrades passing controls in the family
  Requirement  FR-CTL-009, INV-05.2-03
  Method       INTEGRATION
  Procedure    Device exposing an unaudited management-plane capability with
               6 passing management-plane controls.
  Acceptance   All 6 become PASS (PARTIAL) with the reason naming the
               capability. FAIL and UNKNOWN verdicts unchanged. Controls in
               other families unchanged.
  Severity     BLOCKING
```

```
V-05.2-006   Scope aggregation reports the deciding instance
  Requirement  §3.7
  Method       UNIT
  Procedure    Device with two VTY ranges, one compliant, one not.
  Acceptance   FAIL. deciding_instance names the failing range. Both
               instance results retained for evidence.
  Severity     MAJOR
```

```
V-05.2-007   Controls are independent and evaluation is deterministic
  Requirement  INV-05.2-04, G1, D6, D7
  Method       PROPERTY
  Procedure    Evaluate the full control set against the corpus 10 times
               with shuffled control ordering and varied parallelism.
  Acceptance   Identical verdicts, counts, ratios and traces every run.
  Severity     BLOCKING
```

```
V-05.2-008   Every UNKNOWN carries a closed-set reason
  Requirement  §3.9, PRD 10 §2.6
  Method       CORPUS
  Procedure    Assess the full corpus; inspect every UNKNOWN verdict.
  Acceptance   100% carry a reason from the closed set. Zero free-text
               reasons. ≥ 90% carry an actionable remedy.
  Severity     BLOCKING
```

```
V-05.2-009   Undefined coverage is reported as undefined
  Requirement  §5
  Method       UNIT
  Procedure    Device where every control is NOT_APPLICABLE.
  Acceptance   coverage reported as undefined. Never 0% or 100%.
  Severity     MAJOR
```

```
V-05.2-010   No model is invoked during evaluation
  Requirement  FR-CTL-017, D1
  Method       INTEGRATION
  Procedure    Evaluate the full corpus with all model endpoints unreachable
               and local inference disabled.
  Acceptance   Identical results to a run with models available.
               Zero inference calls recorded.
  Severity     BLOCKING
```

```
V-05.2-011   Evaluation performance
  Requirement  NFR-PERF-001, NFR-PERF-002
  Method       PERFORMANCE
  Procedure    Evaluate ~275 controls against 500 devices, reference profile.
  Acceptance   Full campaign evaluation < 5 minutes including parse and
               extraction. Single device < 2 s.
  Severity     MAJOR
```

---

## 8. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should `PASS (PARTIAL)` count toward the compliance numerator? | Excluding it makes compliance drop whenever the schema grows, which is perverse — learning about a capability would appear as a regression. Current design: counts as PASS, with the bound reported separately |
| Q2 | Should coverage be weighted by control severity, so undetermined critical controls depress it more? | Weighted coverage is more informative but harder to explain and no longer a simple proportion. Current design: unweighted, with severity breakdown of UNKNOWNs reported alongside |
| Q3 | Should a device below a coverage floor be excluded from estate aggregates? | Including barely-assessed devices distorts estate figures; excluding them hides devices. Current design: included, with estate coverage reported and low-coverage devices listed explicitly |
