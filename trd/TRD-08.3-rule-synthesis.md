# TRD-08.3 · Rule Synthesis and Validation Gates

---

## 1. Scope

Conversion of a confirmed proposal into a **deterministic extraction rule**, the
validation gates that rule must survive before acceptance, test freezing, and
two-person ratification.

> This is where a model-assisted proposal becomes deterministic knowledge. After
> this point, the platform is consulted for that construct exactly zero times.

**Out of scope:** proposal generation (TRD-08.2); the extractor runtime
(TRD-03.1).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-LRN-009 | Synthesis of a deterministic rule |
| FR-LRN-010…012 | Self-match, corpus scope and conflict gates |
| FR-LRN-013 | Confirmed examples frozen as tests |
| FR-LRN-014…017 | Provisional status, two-person ratification, attribution |
| FR-LRN-018 | Versioning and revertibility |
| FR-LRN-024 | Declarative rules, no code execution |
| NFR-MNT-001 | New platform without code change |

---

## 3. Synthesis

### 3.1 From confirmation to rule

```
synthesise(template, confirmation) → Extractor
```

```yaml
extractor_id: mikrotik_routeros.ip_service.enabled
version: 1
status: provisional

applies_to:
  platform: mikrotik_routeros
  version_range: "*"

scope:
  section: "/ip service"

match: 'set (?P<svc>\S+).*disabled=(?P<state>yes|no)'

emit:
  fact:  "mgmt.protocols.{{ svc | service_map }}.enabled"
  value: "{{ state == 'no' }}"        # polarity inverted, human-confirmed

service_map:
  telnet: telnet
  ssh:    ssh
  www:    http
  ftp:    ftp
  api:    api

tests:                                 # frozen from confirmed examples
  - { input: "set telnet disabled=no port=23", expect: { telnet.enabled: true  } }
  - { input: "set api disabled=yes",           expect: { api.enabled:    false } }

provenance:
  taught_by: r.kulkarni
  taught_at: 2026-09-14T10:22:00Z
  source_artifact: RTR-Pune-02.rsc
  confirmed_examples: 5
  proposal_source: model | heuristic
  polarity_confirmed: true
```

### 3.2 Pattern generation

The match pattern is derived from the template skeleton, not authored freely.

```
skeleton:  set <service> disabled=<yes|no> [port=<n>]
              ↓
pattern:   'set (?P<svc>\S+).*disabled=(?P<state>yes|no)'
```

| Rule | Reason |
|---|---|
| Slots become named capture groups | Deterministic mapping to emissions |
| Literal tokens are anchored | Prevents accidental matching of adjacent constructs |
| Optional elements become non-capturing optional groups | Robustness across observed variants |
| No unbounded nested quantifiers | Catastrophic backtracking is a denial-of-service vector in imported rulepacks |
| Case sensitivity follows the platform grammar | Cisco is case-insensitive; RouterOS is not |

**INV-08.3-01 — Generated patterns are checked for pathological backtracking
before acceptance.** Rulepacks are importable content; an imported rule with a
catastrophic pattern would be a denial-of-service vector against every importer.

### 3.3 Value expression generation

Generated from the confirmed polarity and value domain, never authored freely:

```
observed domain { yes, no }, polarity inverted, target boolean
    → "{{ state == 'no' }}"
```

**INV-08.3-02 — The polarity decision is visible in the generated expression.**
Reading the rule shows the inversion. A rule whose polarity is buried in an
opaque lookup cannot be reviewed at ratification, and ratification is the last
defence against the product's most dangerous error class.

---

## 4. Validation gates

A synthesised rule must survive all six gates before it can be saved. Failure at
any gate returns the administrator to correction, not to a partial save.

### 4.1 Gate 1 — Self-match

```
matches = apply(rule, source_artifact)
```

Every matched line is displayed to the administrator with its line number.

| Condition | Outcome |
|---|---|
| Matches all confirmed examples | Pass |
| Misses a confirmed example | **Fail** — pattern too narrow |
| Matches lines not in the template | Warn — administrator reviews and confirms or corrects |
| Zero matches | **Fail** — synthesis defect |

### 4.2 Gate 2 — Corpus scope

FR-LRN-011. Run the rule against **every artifact in the corpus**, including
other platforms.

| Condition | Outcome |
|---|---|
| Matches only this platform | Pass |
| Matches another platform's artifacts | **Fail** — too broad; narrow the scope or the pattern |
| Matches unexpected sections within this platform | Warn — displayed for review |

**DD-08.3-01 — Cross-platform matching is a hard failure, not a warning.** A rule
firing on the wrong platform corrupts that platform's facts silently, and the
corruption is systematic across every device of that platform. There is no
acceptable reason for a platform-scoped rule to match another platform's
configuration.

### 4.3 Gate 3 — Conflict

FR-LRN-012. Does another rule already produce this fact for this platform?

| Condition | Outcome |
|---|---|
| No existing producer | Pass |
| Existing producer, identical values on all corpus devices | Warn — probable duplicate; offer to supersede |
| Existing producer, differing values | **Fail** — conflict must be resolved before saving |

Saving a conflicting rule would make every affected fact `default_unknown` at
runtime (TRD-03.1 DD-03.1-02), silently reducing coverage. Better to refuse.

### 4.4 Gate 4 — Type conformance

The emitted value must match the schema registry's declared type, and the fact
path must be registered (TRD-03.3 INV-03.3-01).

### 4.5 Gate 5 — Regression

All existing frozen tests for this rulepack must still pass. A new rule that
breaks an existing rule's expectations indicates an unresolved overlap.

### 4.6 Gate 6 — Metamorphic

Apply semantics-preserving mutations to the matched lines (TRD-11.2): whitespace
variation, attribute reordering where the grammar permits, quoting variation,
comment insertion.

```
∀ mutation m : extract(rule, m(line)) == extract(rule, line)
```

**DD-08.3-02 — Metamorphic validation at synthesis time, not only in CI.** A rule
that only matches the exact whitespace of the artifact it was taught from will
fail silently on the next device. Catching this at synthesis is far cheaper than
discovering it in a report six weeks later.

### 4.7 Reporting

```
VALIDATION

  Self-match          6 lines in RTR-Pune-02.rsc               ✓
  Corpus scope        0 matches on other platforms             ✓
  Conflicts           none                                     ✓
  Type conformance    boolean → mgmt.protocols.*.enabled       ✓
  Regression          412 existing tests pass                  ✓
  Metamorphic         1,000 mutations, facts stable            ✓

  Coverage effect     +71 pp on 3 devices
```

---

## 5. Test freezing

FR-LRN-013.

**INV-08.3-03 — The annotation and the regression test are the same artifact.**

Every confirmed example becomes a permanent test attached to the rule.
Consequences:

- The system can never silently regress on something a human verified
- The test suite accumulates at zero marginal cost
- A rulepack's test count is a legible quality signal
- **Teaching produces validation, not merely capability**

Tests are frozen at synthesis and are immutable. Editing a rule requires either
adding tests or explicitly retiring an obsolete one with a recorded reason.

---

## 6. Provisional status and ratification

### 6.1 Provisional

FR-LRN-014, 016.

```
status: provisional
```

| Usable for | Provisional | Ratified |
|---|---|---|
| Exploration, coverage estimation | Yes, flagged | Yes |
| Draft reports | Yes, flagged | Yes |
| **Issued reports** | **No** | Yes |

**INV-08.3-04 — Findings derived from provisional rules cannot appear in an
issued report.** Enforced at report generation (TRD-09.1), not merely displayed
as a warning.

> A finding derived from provisional parsing is not evidence.

### 6.2 Two-person ratification

FR-LRN-015. The rulepack is a control surface: a wrong rule produces wrong
findings that look identical to right ones.

```
ratify(rule, user) →
  require user ≠ rule.taught_by                    # hard constraint
  require all validation gates passed
  record ratifier, timestamp
  status → ratified
```

This is the same control the product recommends for network changes, applied to
itself.

The ratification view presents the evidence needed to judge — not merely a
confirmation button:

```
┌────────────────────────────────────────────────────────┐
│  RATIFY  mikrotik_routeros.ip_service.enabled@1        │
│  Taught by r.kulkarni · 14 Sep 2026 10:22              │
│  From RTR-Pune-02.rsc · 5 examples confirmed           │
│                                                        │
│  Reads     /ip service → set <svc> disabled=<yes|no>   │
│  Produces  mgmt.protocols.{telnet,ssh,http,ftp,api}    │
│  Polarity  INVERTED (disabled=no → enabled=true) ✓     │
│                                                        │
│  [validation results]                                  │
│                                                        │
│  ⚠ You did not author this rule. Review before         │
│    ratifying.                                          │
│         [ Ratify ]  [ Reject ]  [ Comment ]            │
└────────────────────────────────────────────────────────┘
```

**Polarity is displayed prominently in the ratification view**, because this is
the last human checkpoint before the highest-consequence error class becomes
operational.

---

## 7. Versioning and reversibility

FR-LRN-018.

| Operation | Effect |
|---|---|
| Edit a rule | New version; prior version retained |
| Revert | Prior version becomes current; recorded |
| Retire | Marked deprecated; not deleted |
| Rulepack version | Bumped on any constituent change |

**INV-08.3-05 — Nothing is deleted.** A campaign pinned to a rulepack version
must remain reproducible (TRD-10.1). Deleting a rule that a historical campaign
depended on destroys that campaign's reproducibility.

Every operation records actor, timestamp and reason.

---

## 8. Interfaces

```
synthesise(template, confirmation) → Extractor | SynthesisError
validate(extractor, corpus, rulepack) → ValidationReport
save(extractor) → provisional entry            # requires all gates passed
ratify(extractor_id, user) → ratified entry    # requires user ≠ author
revert(rulepack, version) → RulepackVersion
```

---

## 9. Edge cases

| Case | Handling |
|---|---|
| Confirmed example that the generated pattern cannot match | Synthesis fails; template returned for re-answering with the mismatch shown |
| Two administrators teaching the same template concurrently | Second synthesis detects the conflict at Gate 3; presented as a duplicate |
| Rule matching zero lines on other devices of the same platform | Warned — possibly device-specific configuration; administrator confirms |
| Ratifier is the only other authorised user and is unavailable | Rule remains provisional; usable for exploration only. No override |
| Rule superseding a certified rulepack rule | Permitted; local rule takes precedence; trust tier of affected facts becomes `local` |
| Corpus is empty (new deployment) | Gate 2 degrades to a warning; recorded so the rule can be re-validated when a corpus exists |
| Metamorphic mutation the grammar forbids | Skipped; mutation set is grammar-aware |

**The empty-corpus case matters for first deployment.** A brand-new installation
has nothing to validate against. Gate 2 cannot fail meaningfully, so it warns and
the rule is flagged for re-validation once corpus data exists.

---

## 10. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Rule too broad, matches another platform | Gate 2 | Blocked before save |
| Rule too narrow, matches only exact whitespace | Gate 6 | Blocked before save |
| Polarity wrong despite confirmation | Corpus values implausible; peer anomaly divergence; ratification review | **Systematic false PASS across the platform.** Three human checkpoints |
| Conflicting rule saved | Gate 3 | Blocked; would otherwise silently reduce coverage |
| Provisional rule in an issued report | V-08.3-005 | Non-evidence presented as evidence |
| Ratification self-approved | V-08.3-006 | Two-person control defeated |
| Rule deleted, breaking a historical campaign | V-08.3-008 | Reproducibility lost |

---

## 11. Verification

```
V-08.3-001   All six validation gates are enforced before save
  Requirement  FR-LRN-010…012, §4
  Method       UNIT
  Procedure    Submit rules failing each gate individually: missing a
               confirmed example; matching another platform; conflicting
               with an existing producer; wrong type; breaking a regression
               test; failing metamorphic stability.
  Acceptance   All six rejected. Zero partial saves. Administrator returned
               to correction with the failing gate named.
  Severity     BLOCKING
```

```
V-08.3-002   A polarity-inverting rule cannot be saved without confirmation
  Requirement  INV-08.3-02, TRD-08.2 INV-08.2-02
  Method       UNIT + INTEGRATION
  Procedure    Attempt synthesis from a confirmation lacking
               polarity_confirmed for a negation-bearing template, via API
               and via UI.
  Acceptance   Rejected. No rule created. The generated expression, when a
               rule is created, visibly contains the inversion.
  Severity     BLOCKING
  Note         Referenced in the TRD README as one of the five criteria that
               prove the product's central claims.
```

```
V-08.3-003   Cross-platform matching is a hard failure
  Requirement  DD-08.3-01
  Method       UNIT + CORPUS
  Procedure    Synthesise a deliberately broad rule that also matches
               Cisco IOS artifacts.
  Acceptance   Gate 2 fails. Rule not saved. Matching artifacts displayed.
               Zero warnings-only outcomes.
  Severity     BLOCKING
```

```
V-08.3-004   Confirmed examples become immutable frozen tests
  Requirement  FR-LRN-013, INV-08.3-03
  Method       INTEGRATION
  Procedure    Teach a platform with 5 confirmations. Inspect the rule.
               Attempt to modify a frozen test.
  Acceptance   5 tests attached and executable. Modification refused;
               retirement requires a recorded reason. Tests run in CI.
  Severity     BLOCKING
```

```
V-08.3-005   Provisional rules are excluded from issued reports
  Requirement  FR-LRN-016, INV-08.3-04
  Method       INTEGRATION
  Procedure    Teach a platform; leave rules provisional; assess; issue a
               report.
  Acceptance   Findings flagged in draft. Absent from the issued report.
               Enforced at generation, reproducible with the UI bypassed.
  Severity     BLOCKING
```

```
V-08.3-006   Ratifier must differ from author
  Requirement  FR-LRN-015, NFR-SEC / FR-ADM-004
  Method       UNIT + INTEGRATION
  Procedure    Attempt self-ratification via UI and via API, including with
               Platform Administrator privileges.
  Acceptance   Refused in all cases. No override path exists.
  Severity     BLOCKING
```

```
V-08.3-007   Full attribution is recorded
  Requirement  FR-LRN-017
  Method       CORPUS
  Procedure    Teach and ratify rules across three platforms.
  Acceptance   Every rule records author, ratifier, timestamps, source
               artifact, confirmed example count, polarity decision and
               proposal source. All appear in the audit log.
  Severity     MAJOR
```

```
V-08.3-008   Rules are versioned and never deleted
  Requirement  FR-LRN-018, INV-08.3-05
  Method       INTEGRATION
  Procedure    Assess a campaign at rulepack v1. Edit a rule to v2 and
               retire another. Re-execute the historical campaign.
  Acceptance   Byte-identical results. v1 rules still resolvable.
               Zero hard deletions.
  Severity     BLOCKING
```

```
V-08.3-009   Generated patterns are free of catastrophic backtracking
  Requirement  INV-08.3-01
  Method       PROPERTY
  Procedure    Synthesise rules from 200 templates across five platforms.
               Execute each against adversarial inputs designed to trigger
               exponential backtracking.
  Acceptance   Zero patterns exceed the per-node time bound. Any that would
               are rejected at synthesis.
  Severity     MAJOR
```

```
V-08.3-010   Synthesis is deterministic
  Requirement  G1, D6
  Method       PROPERTY
  Procedure    Synthesise from the same confirmations 10 times.
  Acceptance   Byte-identical rules including pattern, value expression,
               lookup tables and test ordering.
  Severity     BLOCKING
```

```
V-08.3-011   End-to-end: a platform is taught without code change
  Requirement  NFR-MNT-001, FR-LRN-019
  Method       INTEGRATION
  Procedure    Using only the running system, teach a held-out platform to
               ≥ 70% coverage: mine, propose, confirm, synthesise, validate,
               ratify, re-assess.
  Acceptance   Completed with zero source modification, zero restart, zero
               redeployment. Coverage measurably increased. Findings carry
               correct evidence.
  Severity     BLOCKING
  Note         This is the problem statement's central demand, verified
               end to end.
```

---

## 12. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should Gate 2 run against the local corpus only, or against imported community corpora? | A wider corpus catches over-broad rules more reliably, but importing corpora raises data-governance questions and is impossible air-gapped. Current design: local corpus, with the limitation recorded on the rule |
| Q2 | Should a rule superseding a certified rule require a higher ratification bar? | Overriding vendor-team content is a significant act, but requiring more than two people may be impractical in small teams. Current design: standard two-person, with the supersession prominently recorded and affected facts marked `local` tier |
| Q3 | Should synthesis attempt to generalise a pattern beyond the observed examples? | Generalisation improves coverage on unseen variants but risks over-broad matching, which Gate 2 may not catch if the corpus is small. Current design: conservative — generalise only to observed variants, with subsequent devices driving refinement |
