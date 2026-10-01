# TRD-08.1 · Template Mining and Question Selection

---

## 1. Scope

Reduction of thousands of unrecognised configuration lines into a small,
ordered set of questions: template collapse, relevance filtering, and
information-gain ordering.

> **4,000 unknown lines → 9 questions, best-first, where the first three deliver
> most of the coverage.** This reduction is the difference between a training
> interface an administrator will use and one they will close after thirty
> seconds.

**Out of scope:** proposing what a template means (TRD-08.2); synthesising rules
(TRD-08.3).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-LRN-003 | Template collapse |
| FR-LRN-004 | Relevance ranking against required facts |
| FR-LRN-005 | Information-gain ordering |
| NFR-PERF-007 | Mining within 30 s for a 10,000-line configuration |
| NFR-USE-003 | Contributes to the ≤ 15 minute onboarding target |

---

## 3. Input

Unmatched constructs from TRD-03.1 §3.7, each carrying:

```
⟨ enclosing_path, head, attribute_keys[], raw, lines, frequency ⟩
```

Comments, blanks, verbatim regions and rulepack-declared ignorable heads are
already excluded.

---

## 4. Design

### 4.1 Template collapse

Replace variable-looking tokens with typed slots, then cluster identical
skeletons.

```
add address=10.0.0.1/24 interface=bridge1
add address=192.168.5.1/24 interface=bridge2      ─┐  one template
add address=172.16.0.1/30 interface=WAN            ─┘
        ↓
add address=<cidr> interface=<identifier>
```

**Slot inference by position, not by token.**

```
slot_type(position, values_at_position) →
  if all values match a CIDR pattern            → <cidr>
  if all match an address pattern               → <address>
  if all are integers                           → <integer>
  if all are quoted strings                     → <string>
  if all match a MAC pattern                    → <mac>
  if cardinality/occurrences > VARIABILITY_RATIO → <identifier>
  otherwise                                      → literal
```

**DD-08.1-01 — Slot inference is positional and corpus-wide, not per-line.** A
token is variable if it *varies across occurrences of the same skeleton*, not
because it looks like a value. `set telnet disabled=no` and
`set ssh disabled=no` share a skeleton; `telnet`/`ssh` vary and become a slot.
`disabled` does not vary and stays literal — which is correct, because it is the
semantically load-bearing token.

`VARIABILITY_RATIO = 0.5`: a position is a slot if distinct values exceed half
the occurrences.

**INV-08.1-01 — Collapse is lossless.** Every template retains references to
every source line it subsumes. The administrator is always shown real lines from
their own device (TRD-08.2 §5), and rule validation (TRD-08.3) tests against all
of them.

Typical reduction: **4,000 lines → 60–120 templates.**

### 4.2 Relevance filtering

Most templates are irrelevant to compliance:

```
add name=bridge1 protocol-mode=rstp            → no control cares
set [ find default-name=ether1 ] name=WAN      → no control cares
add address=10.0.0.1/24 interface=bridge1      → no control cares
```

The system knows exactly which schema facts its loaded controls require.

```
relevance(template) =
      w₁ · lexical_proximity(template.tokens, required_fact_vocabulary)
    + w₂ · structural_analogy(template.enclosing_path, known_fact_sections)
    + w₃ · value_shape_compatibility(template.slots, required_fact_types)
    + w₄ · anomaly_boost(template)              # TRD-06.3 §3.7
```

**Lexical proximity exploits the domain's one gift.** Networking vocabulary is
standardised even where syntax is not — every vendor writes `telnet`, `ssh`,
`snmp`, `ntp`, `radius`, because these are interoperability protocols defined in
published RFCs. **The vocabulary shared across all these dialects is precisely
the security-relevant vocabulary.**

| High-scoring | Low-scoring |
|---|---|
| telnet ssh snmp community password user privilege radius tacacs log syslog ntp timeout cipher key certificate acl permit deny | description comment name vlan route bandwidth mtu color speed duplex |

The vocabulary is derived from the loaded controls' `requires_facts` plus the
schema registry's descriptions and known synonyms — **not from a hand-maintained
keyword list**, which would drift from the control library.

**DD-08.1-02 — Filtering suppresses, it does not delete.** Low-relevance
templates remain available behind a "show all" affordance. An administrator who
knows a construct matters must be able to reach it even when scoring disagrees.

Typical reduction: **120 templates → ~15 candidates.**

### 4.3 Information-gain ordering

Of the remaining candidates, order by how many currently-undetermined controls
each answer would resolve.

```
gain(template) =
    | { C : C.verdict == UNKNOWN
          ∧ ∃ f ∈ C.requires_facts : f ∈ candidate_facts(template)
          ∧ all other facts of C are already determined
              or resolvable by higher-ranked templates } |
```

```
Q1  /ip service        → 5 facts → unlocks 8 controls    ← ask first
Q2  /user              → 4 facts → unlocks 6 controls
Q3  /snmp community    → 3 facts → unlocks 5 controls
...
Q9  /user aaa          → 1 fact  → unlocks 1 control
```

**DD-08.1-03 — Gain is recomputed after each answer.** Answering Q1 may make Q7
more valuable than Q2, because Q7's control now needs only one more fact.
Recomputation is cheap and materially improves the ordering. Greedy sequential
selection, standard active learning.

**INV-08.1-02 — Ordering is deterministic.** Ties break on relevance, then
frequency, then template identifier (D6). Two runs present identical questions in
identical order.

### 4.4 Question budget

```
present = templates with gain > 0, capped at INITIAL_BUDGET = 12
```

**DD-08.1-04 — Present a bounded, completable set rather than everything.**
An administrator faced with 40 questions abandons; faced with 9 they finish.
After the initial set, remaining UNKNOWNs generate the next round — the loop is
self-directing, and coverage rises visibly between rounds.

Estimated time is shown, calibrated from observed answer times (TRD-08.4).

### 4.5 Grouping related templates

Templates from the same section that map to the same fact family are presented as
one question with multiple mappings, rather than as separate questions:

```
set telnet disabled=no
set ssh    disabled=no      →  one question, three mappings
set www    disabled=no
```

This is why the worked example asks 9 questions rather than 15 — and why
answering Q1 resolves 8 controls at once.

### 4.6 Performance

NFR-PERF-007: mining within 30 s for a 10,000-line configuration.

| Stage | Complexity |
|---|---|
| Slot inference | O(n) over unmatched lines |
| Skeleton clustering | O(n) with a hash on the skeleton |
| Relevance scoring | O(t · v), t templates × vocabulary size |
| Gain computation | O(t · c) per round, c undetermined controls |

Dominated by the linear pass. Gain recomputation across rounds is bounded by the
question budget.

---

## 5. Interfaces

```
mine(unmatched[], controls, schema, anomalies?) → TrainingQueue {
  templates[]: {
     id, skeleton, slots[]
     enclosing_path, occurrence_count
     source_lines[]                        // INV-08.1-01
     relevance, candidate_facts[]
  }
  questions[]: {
     rank, templates[]                     // grouped per §4.5
     gain, controls_unlocked[]
     estimated_seconds
  }
  suppressed_count, total_templates
  estimated_total_minutes
}
```

---

## 6. Edge cases

| Case | Handling |
|---|---|
| Fewer than 20 unmatched lines | Mining still runs; all templates presented; statistics weak but harmless |
| Every unmatched line is unique | No collapse; templates equal lines; relevance filtering does the reduction |
| All templates score zero relevance | No questions; reported as "no compliance-relevant constructs detected", with "show all" available |
| Template spanning multiple lines (a block) | Skeleton includes child structure to a bounded depth |
| Two templates with identical skeleton but different enclosing paths | Distinct — the path carries meaning |
| Answering a question resolves zero controls | Recorded; gain estimate calibration adjusted |
| Very high template count (> 500) | Budget applies; suppressed count reported so the scale is visible |

**The all-zero-relevance case is worth handling explicitly.** It occurs when a
configuration is genuinely all routing and interface definitions. Reporting *"no
compliance-relevant constructs detected"* is accurate and useful; presenting 80
irrelevant questions is not.

---

## 7. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Over-aggressive slot inference | V-08.1-002 | Semantically distinct constructs merged; wrong mappings proposed |
| Under-aggressive slot inference | V-08.1-002 | Template explosion; too many questions |
| Relevant template suppressed | V-08.1-004 | Coverage gap persists; mitigated by DD-08.1-02 |
| Gain estimate wrong | V-08.1-005 | Poor ordering; more questions than necessary |
| Non-deterministic ordering | V-08.1-007 | Different questions between runs; erodes trust |
| Source lines lost in collapse | V-08.1-001 | Cannot show real lines; cannot validate rules |

---

## 8. Verification

```
V-08.1-001   Collapse is lossless
  Requirement  INV-08.1-01
  Method       PROPERTY + CORPUS
  Procedure    Mine unmatched constructs across held-out platforms. Assert
               the union of all templates' source_lines equals the input
               line set exactly.
  Acceptance   100%. Zero lines lost, zero duplicated.
  Severity     BLOCKING
```

```
V-08.1-002   Slot inference is semantically correct
  Requirement  DD-08.1-01
  Method       UNIT + CORPUS
  Procedure    Mine known constructs across five platforms with expert-
               labelled expected skeletons.
  Acceptance   ≥ 90% of skeletons match the expected slotting. Zero cases
               where a semantically load-bearing token (telnet, disabled,
               permit) becomes a slot.
  Severity     BLOCKING
  Note         Slotting a load-bearing token merges distinct constructs and
               produces wrong mappings downstream.
```

```
V-08.1-003   Reduction ratio meets the target
  Requirement  FR-LRN-003, FR-LRN-004
  Method       CORPUS
  Procedure    Mine full unmatched sets from held-out platform configurations
               of ≥ 3,000 lines.
  Acceptance   Median: ≥ 3,000 lines → ≤ 120 templates → ≤ 15 candidates
               → ≤ 12 presented questions.
  Severity     BLOCKING
```

```
V-08.1-004   Relevance filtering does not suppress security-relevant constructs
  Requirement  FR-LRN-004, DD-08.1-02
  Method       CORPUS
  Procedure    For held-out platforms with known ground-truth mappings,
               mine and inspect suppressed templates.
  Acceptance   Zero templates mapping to a required schema fact are
               suppressed. All suppressed templates reachable via "show all".
  Severity     BLOCKING
```

```
V-08.1-005   Information-gain ordering front-loads coverage
  Requirement  FR-LRN-005
  Method       CORPUS
  Procedure    For each held-out platform, answer questions in presented
               order using ground truth. Record coverage after each answer.
  Acceptance   The first three answers deliver ≥ 60% of the coverage
               achievable from the full presented set.
  Severity     MAJOR
```

```
V-08.1-006   Gain is recomputed between answers
  Requirement  DD-08.1-03
  Method       UNIT
  Procedure    Construct a queue where answering Q1 raises Q7's gain above
               Q2's.
  Acceptance   Q7 is presented second. Ordering adapts to answers.
  Severity     MAJOR
```

```
V-08.1-007   Mining and ordering are deterministic
  Requirement  INV-08.1-02, G1, D6
  Method       PROPERTY
  Procedure    Mine the same unmatched sets 10 times with shuffled input
               ordering.
  Acceptance   Identical templates, identical identifiers, identical question
               order including tie-breaks.
  Severity     BLOCKING
```

```
V-08.1-008   Related templates are grouped into one question
  Requirement  §4.5
  Method       UNIT
  Procedure    Mine a `/ip service` section containing telnet, ssh, www, ftp
               and api statements.
  Acceptance   One question with five mappings, not five questions.
  Severity     MAJOR
```

```
V-08.1-009   Zero-relevance configurations are reported honestly
  Requirement  §6
  Method       UNIT
  Procedure    Mine a configuration consisting entirely of routing and
               interface definitions.
  Acceptance   No questions presented. Message states no compliance-relevant
               constructs were detected. "Show all" remains available.
  Severity     MINOR
```

```
V-08.1-010   Mining performance
  Requirement  NFR-PERF-007
  Method       PERFORMANCE
  Procedure    Mine a 10,000-line configuration with ~4,000 unmatched lines,
               reference profile.
  Acceptance   < 30 s including relevance scoring and initial gain ordering.
  Severity     MAJOR
```

```
V-08.1-011   Anomalous templates are promoted
  Requirement  TRD-06.3 §3.7
  Method       INTEGRATION
  Procedure    Mine an untaught platform where peer anomaly detection has
               flagged specific elements.
  Acceptance   Templates containing anomalous elements rank above
               equally-relevant, equally-frequent non-anomalous templates.
  Severity     MINOR
```

---

## 9. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should the relevance vocabulary include synonyms mined from taught platforms, or only schema descriptions? | Mined synonyms improve recall on unusual vendor terminology but risk drift as more platforms are taught. Current design: schema descriptions plus registered synonyms, with mined candidates surfaced for review rather than applied automatically |
| Q2 | Should the question budget adapt to observed administrator engagement? | Adapting would keep engaged users productive and avoid overwhelming reluctant ones, but makes the interaction non-reproducible. Current design: fixed budget, with rounds providing the adaptation |
| Q3 | Should templates be shared across platforms so that a construct taught once is recognised elsewhere? | This is TRD-08.4's transfer mechanism operating at proposal level rather than template level. Current design: templates are platform-local; transfer happens in proposal (TRD-08.2) |
