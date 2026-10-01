# TRD-08.2 · Candidate Proposal and Polarity

---

## 1. Scope

Generation of a **proposed semantic mapping** for each template before asking the
administrator; the confirmation interaction; and the handling of **polarity** —
the highest-consequence error class in the entire product.

This is the only subsystem in which a language model participates, and the
boundary is precise: the model produces a *proposal for human confirmation*, and
what is stored is a *deterministic rule*.

**Out of scope:** template selection (TRD-08.1); rule synthesis and validation
(TRD-08.3).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-LRN-006 | Candidate proposal from lexical, structural and value-shape priors |
| FR-LRN-007 | Explicit polarity confirmation |
| FR-LRN-008 | Confirmation-oriented interaction |
| FR-LRN-027 | Local inference mode mandatory |
| FR-LRN-028 | Redaction before any model invocation |
| NFR-USE-001, 002 | Usable without programming experience |

---

## 3. Three corroborating signals

Proposals are generated from three independent sources. Agreement between them
raises confidence materially; disagreement lowers it and is surfaced.

### 3.1 Lexical priors

The system already knows that Cisco's `transport input telnet` produces
`mgmt.protocols.telnet.enabled`, and that FortiOS's `set admin-telnet disable`
produces the same fact.

The MikroTik template reads `set <service> disabled=<yes|no>`, and one observed
value of `<service>` is `telnet`.

> **Networking vocabulary is standardised even where syntax is not.** Every
> vendor writes `telnet`, `ssh`, `snmp`, `ntp`, `radius`, `tacacs` — they have no
> choice, because these are interoperability protocols defined in published RFCs.
> Vendors differentiate on syntax, never on protocol names.

```
lexical_score(token, fact) =
      exact match against the fact's registered synonyms          → 1.0
    + normalised edit distance below threshold                    → 0.7
    + token appears in the fact's schema description              → 0.5
```

### 3.2 Structural analogy

In previously taught platforms, `mgmt.protocols.*.enabled` was extracted from
nodes under a section semantically equivalent to "system services". Here the
template sits under `/ip service`.

```
structural_score(enclosing_path, fact) =
    semantic similarity between this path and the paths from which
    this fact was extracted on other platforms
```

Two independent signals agreeing is materially stronger evidence than either
alone, and the proposal records which signals contributed.

### 3.3 Value shape

```
value_shape_score(slot_values, fact) =
    type compatibility between the observed value domain and the
    fact's registered type
```

`disabled=<yes|no>` has a two-valued domain; `mgmt.protocols.telnet.enabled` is
boolean. Compatible.

**But the key contains a negation** — which brings us to the critical part.

---

## 4. Polarity

### 4.1 Why this is the highest-consequence error class

```
disabled = no    →    enabled = TRUE
```

Invert this and a device with Telnet wide open is certified **compliant**.

Unlike a parse failure, which surfaces as UNKNOWN and lowers coverage visibly, a
polarity error surfaces as a **confident PASS**. It is invisible, it is
systematic across every device of that platform, and it produces exactly the
false assurance the entire product exists to prevent.

Every other error in the system degrades toward uncertainty. This one degrades
toward false confidence.

### 4.2 Detection

```
negation_indicators = { disabled, deny, no-, off, shutdown, suppress,
                        inactive, block, prohibit, reject, restrict, none }

polarity_inverted(template) =
      key contains a negation indicator
    ⊻ value domain is itself negative ({ no, false, off, disable })
```

Note the exclusive-or: **double negatives cancel**. `disabled=no` means enabled;
`disabled=yes` means disabled. Both must be handled, and a naïve implementation
that flips once gets one of them wrong.

Cross-platform examples the design must handle:

```
Cisco     transport input ssh            → telnet.enabled = FALSE  (absence from list)
Cisco     transport input telnet ssh     → telnet.enabled = TRUE
Fortinet  set admin-telnet disable       → telnet.enabled = FALSE  (negated key)
MikroTik  set telnet disabled=no         → telnet.enabled = TRUE   (double negative)
Juniper   delete system services telnet  → telnet.enabled = FALSE  (delete verb)
```

Five syntactic forms, five different polarity derivations, one semantic fact.

### 4.3 Mandatory explicit confirmation

**INV-08.2-01 — Polarity is never inferred silently.** It is presented as its own
visually distinct block, requiring its own affirmative answer.

```
┌── ⚠ POLARITY CHECK ────────────────────────────────────────┐
│ "disabled=no" is being read as the service being ON.       │
│ Is that correct?                                           │
└────────────────────────────────────────────────────────────┘

  [ ✓ Confirm ]   [ ⇄ Polarity is inverted ]
```

**INV-08.2-02 — A negation-bearing template cannot be confirmed without a
separate polarity answer.** The API rejects a confirmation lacking
`polarity_confirmed` with HTTP 422 (PRD 15 §6). This is enforced as a data
constraint, not a UI convention — a client that skips the check cannot save a
rule.

**DD-08.2-01 — Polarity correction rate is tracked as a safety metric**
(TRD-08.4). A rising rate indicates the detection heuristics are degrading on
newer platforms, and is a release-blocking signal rather than a curiosity.

---

## 5. The model's contribution and its boundary

### 5.1 What the model does

Given the template, the observed lines, the target schema subset, and the
heuristic candidates, a language model proposes mappings with justifications. It
is genuinely good at this: reading unfamiliar structured text and relating it to
a described schema.

```
propose(template, schema_subset, heuristic_candidates) →
    [ ⟨slot_value, fact_path, polarity, confidence, justification⟩ ]
```

Output is **structurally constrained** — the model selects from registered fact
paths rather than emitting free text. A proposal naming an unregistered path is
discarded before it reaches the administrator.

### 5.2 What the model does not do

| Boundary | Enforcement |
|---|---|
| Never produces a stored fact | What is saved is a deterministic rule (TRD-08.3) |
| Never decides a verdict | No model in the assessment path (D1) |
| Never consulted again for this platform | Once rules exist, extraction is deterministic |
| Never sees secrets | Redaction precedes invocation (§5.3) |
| Never required | Heuristic-only mode degrades to plainer proposals |

**INV-08.2-03 — The system functions with no model available.** Heuristic-only
proposals are less specific and require more correction, but teaching still
works. This is not a graceful-degradation nicety; it is a deployment requirement
for air-gapped installations where no local inference host exists.

### 5.3 Redaction

FR-LRN-028. Before any content leaves the process:

| Redacted | Detection |
|---|---|
| Password hashes and encoded credentials | Rulepack-declared credential positions; hash-shaped tokens |
| SNMP community strings | Positional; known key names |
| Pre-shared keys, certificates, private keys | Verbatim region markers |
| Public IP addresses and hostnames | Optional, per deployment policy |

**Redaction is structure-preserving.** A redacted type 7 password remains a
syntactically valid type 7 password, so the proposal still sees the shape it
needs to reason about.

### 5.4 Local inference

FR-LRN-027. A local inference mode is **mandatory**, not optional. Configuration
content is a complete map of a network's defences; transmitting it to an external
service in a critical-infrastructure deployment is an intelligence loss, not a
policy violation.

| Mode | Behaviour |
|---|---|
| `local` | Inference on a host inside the deployment boundary |
| `hosted` | External service; requires explicit configuration and is refused in air-gapped mode |
| `none` | Heuristic-only proposals |

Default is `local` where an inference host is configured, `none` otherwise.

---

## 6. The confirmation interaction

### 6.1 Design principle

> **Humans are fast and accurate at *"is this right?"* and slow and unreliable at
> *"write the correct rule."***

Every effective annotation interface exploits this asymmetry. Here it is what
allows a network engineer who has never written a regular expression to teach a
parser — which is exactly what the problem statement requires.

**INV-08.2-04 — No regular expression, expression, or query is ever shown to the
administrator.** They see their own configuration lines and a plain-language
reading of them.

### 6.2 The presented question

```
┌────────────────────────────────────────────────────────┐
│  MikroTik RouterOS       Question 1 of 9               │
│                                    Coverage 0% → ?     │
│  Section:  /ip service                                 │
│  Pattern:  set <service> disabled=<yes|no> [port=<n>]  │
│                                                        │
│  Found in RTR-Pune-02.rsc — 6 matching lines           │
│      14 │ set telnet  disabled=no  port=23             │
│      17 │ set ssh     disabled=no  port=22             │
│      16 │ set www     disabled=no  port=80             │
│      19 │ set api     disabled=yes                     │
│                                                        │
│  ── OUR READING ─────────────────────────────────────  │
│  This appears to enable or disable management services │
│                                                        │
│      telnet  →  Telnet service        ENABLED          │
│      ssh     →  SSH service           ENABLED          │
│      www     →  HTTP management       ENABLED          │
│      api     →  API service           disabled         │
│                                                        │
│  ┌── ⚠ POLARITY CHECK ──────────────────────────────┐ │
│  │ "disabled=no" is read as the service being ON.   │ │
│  │ Is that correct?                                 │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  Confirming resolves 8 controls.                       │
│                                                        │
│  [ ✓ Confirm ]  [ ⇄ Inverted ]                         │
│  [ ✎ Edit ]  [ ✗ Not compliance-relevant ]  [ Skip ]   │
└────────────────────────────────────────────────────────┘
```

### 6.3 Interaction requirements

| Requirement | Reason |
|---|---|
| Real lines from **their own device**, with line numbers | Concrete beats abstract; they recognise their equipment |
| One question at a time | Reduces error rate versus a wall of decisions |
| Impact stated **before** answering | Motivation, and makes progress legible |
| Polarity as a separate block | The highest-consequence error class |
| *"Not compliance-relevant"* as a first-class answer | Prevents forced incorrect mappings; the negative answer is itself information |
| Reversible before ratification | Mistakes are recoverable |
| Progress and time estimate | Nine questions is tractable; unknown length is not |

**DD-08.2-02 — *"Not compliance-relevant"* is recorded, not discarded.** It
suppresses the template permanently for that platform and feeds back into
relevance scoring (TRD-08.1). An administrator's judgement that a construct does
not matter is valuable training signal.

### 6.4 Answer types

| Answer | Effect |
|---|---|
| `confirm` | Proposal accepted as presented; proceeds to synthesis |
| `polarity_inverted` | Polarity flipped; mappings otherwise accepted |
| `edit` | Administrator adjusts individual slot→fact mappings |
| `not_relevant` | Template suppressed for this platform; recorded |
| `skip` | Deferred to the next round; no record |

`edit` presents fact selection as a searchable list with plain-language
descriptions, never as free text — preserving INV-08.2-04.

---

## 7. Interfaces

```
propose(template, schema, taught_platforms, mode) → Proposal {
  mappings[]: ⟨slot_value, fact_path, value_expression_intent⟩
  polarity: ⟨inverted: bool, indicator, requires_explicit_confirmation: bool⟩
  confidence
  signals[]: ⟨kind, contribution⟩          // explainability
  description                              // plain language
  impact: ⟨facts_resolved, controls_unlocked⟩
  source: model | heuristic
}

answer(question_id, response, polarity_confirmed?, edits?) → AnswerResult
```

`signals[]` is required: when a proposal is wrong, the administrator and later an
engineer must be able to see why it was made.

---

## 8. Edge cases

| Case | Handling |
|---|---|
| Model proposes an unregistered fact path | Discarded before presentation; heuristic fallback used |
| Model and heuristics disagree | Both shown; confidence reduced; disagreement stated |
| Template with no plausible mapping | Presented as "we could not determine what this does"; administrator may map manually or mark irrelevant |
| Slot value that is itself a negation (`set telnet enabled=no`) | Polarity derived from the value domain; still requires confirmation |
| Same template on two platforms with opposite polarity | Platform-scoped; no cross-contamination |
| Administrator confirms a mapping contradicting an existing rule | Conflict detected at synthesis (TRD-08.3), not at proposal |
| Model unavailable mid-session | Falls back to heuristic proposals; session continues |

---

## 9. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Polarity confirmed incorrectly by the administrator | Corpus validation at synthesis; peer anomaly divergence | **A vulnerable device certified compliant.** Mitigated by explicit confirmation, ratification, and rate tracking |
| Polarity check omitted for a negation-bearing template | V-08.2-002 | Same, without even the confirmation gate |
| Model hallucinates a plausible but wrong mapping | Administrator confirmation; synthesis validation | Wrong facts on that platform; caught by TRD-08.3 gates |
| Configuration content sent to an external service | V-08.2-006 | Intelligence loss |
| Regular expression shown to the administrator | V-08.2-005 | Interface becomes unusable by its intended user |
| Proposal quality degrades silently | Acceptance-rate tracking (TRD-08.4) | More corrections required; visible in metrics |

---

## 10. Verification

```
V-08.2-001   Polarity is correctly detected across all five syntactic forms
  Requirement  FR-LRN-007, §4.2
  Method       UNIT + CORPUS
  Procedure    Templates covering: absence-from-list (Cisco), negated key
               (Fortinet), double negative (MikroTik), delete verb (Juniper),
               and positive assertion.
  Acceptance   100% correct polarity derivation. Double negatives resolve
               correctly in both directions.
  Severity     BLOCKING
```

```
V-08.2-002   Negation-bearing templates cannot be confirmed without an
             explicit polarity answer
  Requirement  INV-08.2-01, INV-08.2-02
  Method       UNIT + INTEGRATION
  Procedure    Submit a confirmation for a negation-bearing template with
               polarity_confirmed absent, via API and via UI.
  Acceptance   Rejected with 422. No rule synthesised. Enforced as a data
               constraint, reproducible with the UI bypassed.
  Severity     BLOCKING
  Note         Referenced in the TRD README as one of the five criteria that
               prove the product's central claims.
```

```
V-08.2-003   Proposal quality on held-out platforms
  Requirement  FR-LRN-006
  Method       CORPUS
  Procedure    Generate proposals for held-out platforms with expert-labelled
               ground-truth mappings.
  Acceptance   ≥ 70% of proposals confirmable without edit at first
               presentation. ≥ 90% of polarity determinations correct.
  Severity     MAJOR
```

```
V-08.2-004   Teaching functions with no model available
  Requirement  INV-08.2-03, FR-LRN-027
  Method       INTEGRATION
  Procedure    Teach a held-out platform to ≥ 70% coverage with all model
               endpoints unreachable and local inference disabled.
  Acceptance   Completed. Proposals present, marked source: heuristic.
               More corrections required, but no capability lost.
  Severity     BLOCKING
```

```
V-08.2-005   No expression syntax is exposed to the administrator
  Requirement  INV-08.2-04, NFR-USE-002
  Method       MANUAL + INTEGRATION
  Procedure    Complete a full teaching session including `edit` answers.
               Inspect every rendered screen and API response consumed by
               the UI.
  Acceptance   Zero regular expressions, value expressions or query syntax
               presented. Fact selection is a searchable descriptive list.
  Severity     BLOCKING
```

```
V-08.2-006   Redaction precedes model invocation
  Requirement  FR-LRN-028, NFR-SEC-006
  Method       INTEGRATION
  Procedure    Teach using configurations containing type 7 passwords, SNMP
               communities, pre-shared keys and certificates, with model
               traffic captured.
  Acceptance   Zero credential material in captured payloads. Redaction is
               structure-preserving — a redacted type 7 password remains
               syntactically valid.
  Severity     BLOCKING
```

```
V-08.2-007   Air-gapped mode refuses hosted inference
  Requirement  §5.4, NFR-DEP-001
  Method       INTEGRATION
  Procedure    Configure hosted inference in an air-gapped deployment.
  Acceptance   Refused at configuration with an explicit message. Zero
               outbound attempts.
  Severity     BLOCKING
```

```
V-08.2-008   Proposals carry explainable signals
  Requirement  §7
  Method       CORPUS
  Procedure    Generate proposals across held-out platforms.
  Acceptance   100% carry non-empty signals[] identifying which of lexical,
               structural and value-shape evidence contributed, with weights.
  Severity     MAJOR
```

```
V-08.2-009   Model and heuristic disagreement is surfaced
  Requirement  §8
  Method       UNIT
  Procedure    Construct a template where the model and heuristics propose
               different facts.
  Acceptance   Both presented. Confidence reduced. Disagreement stated to the
               administrator rather than silently resolved.
  Severity     MAJOR
```

```
V-08.2-010   "Not compliance-relevant" is recorded and reused
  Requirement  DD-08.2-02
  Method       INTEGRATION
  Procedure    Mark a template not relevant; re-run mining on another device
               of the same platform.
  Acceptance   Template suppressed. Suppression attributed and reversible.
               Relevance scoring updated.
  Severity     MINOR
```

```
V-08.2-011   Proposal generation does not affect assessment determinism
  Requirement  D1, G1
  Method       INTEGRATION
  Procedure    Assess a taught platform with the model available and with it
               unreachable.
  Acceptance   Byte-identical assessment results. Zero inference calls during
               assessment in either configuration.
  Severity     BLOCKING
```

---

## 11. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should polarity confirmation be required even for templates with no negation indicator? | Universal confirmation is maximally safe but adds friction to every question, which risks answer fatigue and careless confirmation — itself a safety risk. Current design: required only where a negation indicator is present, with the indicator list treated as safety-critical content |
| Q2 | Should a second administrator be required to confirm polarity specifically, separate from rulepack ratification? | Polarity is the highest-consequence decision, so a dedicated second check is defensible; but ratification already provides one, and doubling the gates may reduce engagement. Current design: covered by ratification, with polarity displayed prominently in the ratification view |
| Q3 | Should proposals learn from correction patterns within a session? | Adapting mid-session would improve later questions, but makes the session non-reproducible and could amplify an early mistake. Current design: no intra-session adaptation; learning happens across platforms (TRD-08.4) |
