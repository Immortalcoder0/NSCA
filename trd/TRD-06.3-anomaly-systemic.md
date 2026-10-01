# TRD-06.3 · Peer Anomaly and Systemic Findings

---

## 1. Scope

Two analyses that operate on the estate rather than the device:

- **Peer anomaly** — devices deviating from their own structurally similar peers,
  computed **without semantic understanding**, so it produces findings on
  platforms not yet taught
- **Systemic findings** — the same defect across many devices, reported as one
  root cause rather than N symptoms

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-RSK-006 | Peer anomaly detection |
| FR-RSK-007 | Functions without semantic understanding |
| FR-RSK-008 | Systemic findings as a single root cause |
| FR-RPT-015 | Estate report root-cause presentation |

---

## 3. Peer anomaly

### 3.1 Why this is valuable

Compliance frameworks encode what standards bodies imagined. **Peer comparison
encodes what the organisation actually decided** — a policy that exists but was
never written down, and which is recoverable from the estate itself.

If 37 of 40 sibling routers have Telnet disabled and 3 do not, those 3 are worth
looking at regardless of what any benchmark says.

Critically, this requires **no semantic understanding of the configuration
language**. It therefore produces findings on a platform the system has never
been taught — the only useful answer to *"what can you tell me about a device you
cannot parse?"*

### 3.2 Peer group formation

An anomaly is only meaningful relative to a genuine peer group.

```
peer_group(device) = devices sharing
     platform
  ∧  major OS version
  ∧  role
  ∧  exposure class
```

**DD-06.3-01 — Groups smaller than 5 are not analysed.** With 3 devices there is
no majority worth calling normal, and the analysis would produce noise on small
estates. Groups below the threshold are reported as unanalysable rather than
silently skipped.

Where role is undetermined, grouping falls back to platform plus version, and the
finding's confidence is reduced.

### 3.3 Two comparison modes

| Mode | Requires | Available when |
|---|---|---|
| **Structural** | Parse tree only | Platform parsed but not taught |
| **Semantic** | Resolved facts | Platform taught |

**Structural mode** is the one that matters for untaught platforms.

```
signature(device) = multiset of ⟨enclosing_path, head, attribute_keys⟩
                    over all statement nodes
```

Values are excluded — only the *shape* of the configuration is compared. Two
devices with different IP addresses have identical structural signatures; a
device with an extra `set telnet disabled=no` does not.

```
deviation(device, group) =
    signature(device) △ modal_signature(group)      # symmetric difference
```

**Semantic mode** compares resolved fact values directly, which is more precise
and produces directly actionable findings.

### 3.4 Anomaly scoring

```
for each signature element e:
    prevalence(e) = fraction of group members exhibiting e

anomaly(device) = { e : e ∈ signature(device) ∧ prevalence(e) < LOW  }
                ∪ { e : e ∉ signature(device) ∧ prevalence(e) > HIGH }

LOW = 0.15    HIGH = 0.85
```

Two thresholds because both directions matter: a device that has something almost
none of its peers have, and a device that lacks something almost all of its peers
have. **The second is the more commonly missed** — an absent logging
configuration is invisible to a "what's unusual here" check that only looks at
what is present.

### 3.5 Direction inference

An anomaly says a device differs; it does not say which side is correct. Where
semantic knowledge exists from other platforms, direction can be inferred:

```
if the deviating element maps to a fact the system understands,
and a control exists for that fact:
    direction = whichever side satisfies the control
else:
    direction = undetermined; report as deviation only
```

**DD-06.3-02 — Undetermined direction is reported as deviation, never as a
violation.** *"This device differs from its 39 peers"* is a defensible statement.
*"This device is misconfigured"* requires knowing which side is right, and
asserting it without that knowledge is over-claiming.

```
⚠ Peer deviation — RTR-Pune-02
  Differs from 39 structurally similar RouterOS peers:
    • present here, absent in 38/39:  /ip service → set telnet …
    • absent here, present in 37/39:  /system logging → action=remote

  Direction: undetermined (platform semantics not yet learned)
  This is a deviation, not a compliance finding.
```

### 3.6 Anomaly verdicts

Anomalies are **not control verdicts**. They:

- Do **not** contribute to compliance or coverage
- **Do** appear in the estate report as a distinct category
- **Do** feed the training queue — a deviating element is a high-value question
  (TRD-08.1)

**INV-06.3-01 — Anomalies never alter a control verdict.** Merging a heuristic
signal into a deterministic verdict would compromise G1 and G2 for the sake of a
signal that is, by design, uncertain.

### 3.7 Feedback into learning

An element present on 3 of 40 devices and absent on 37 is more likely to be
security-relevant than one present on all 40. Anomalous elements are therefore
promoted in the training queue's relevance ranking (TRD-08.1 §4.2).

This composes usefully: the unsupervised layer directs the supervised one.

---

## 4. Systemic findings

### 4.1 Why this is the assessor's most valuable output

Thirty-one findings with one root cause is **one insight**, not thirty-one
problems. An assessor who reports 31 findings has produced a list; one who
reports *"your build template is defective"* has produced an audit.

### 4.2 Clustering

```
cluster_key(finding) = ⟨ control_id,
                         platform,
                         normalised_evidence_pattern ⟩
```

The evidence pattern is normalised by replacing addresses, hostnames, numbers and
quoted strings with slots — the same abstraction used for template mining
(TRD-08.1 §4.1), reused rather than reimplemented.

```
systemic(cluster) =
      |cluster| ≥ max(5, 0.20 × platform_device_count)
  ∧   evidence patterns identical after normalisation
```

**DD-06.3-03 — Both an absolute and a proportional threshold.** Five devices out
of a thousand is not systemic; five out of eight is. Requiring both prevents
false systemic claims on large estates and missed ones on small.

### 4.3 Corroborating evidence

A cluster becomes a root-cause hypothesis when supporting signals agree:

| Signal | Strengthens |
|---|---|
| Identical normalised evidence | Common origin |
| Commissioning dates within one window | Common build process |
| Identical OS version and model | Common image or template |
| Same site or naming convention | Common provisioning run |
| Configuration statements adjacent to the defect are also identical | Common template |

```
SYSTEMIC FINDING  SF-2026Q3-004

  NSCA-MGMT-007 fails identically on 31 of 40 branch routers.
  All 31 share an identical management ACL block.
  All 31 commissioned between 2024-03 and 2025-11.
  All 31 run IOS-XE 16.12.04 on ISR4331.

  Assessment: build-template defect, not 31 independent errors.

  Recommended action
    1  Correct the build template
    2  Remediate the 31 affected devices
    3  Verify the 9 unaffected devices were built from a corrected template

  Affected: BR-RTR-001 … BR-RTR-031
```

**Step 3 is the part an inventory would miss.** The nine devices that pass may
pass for the wrong reason — a later template, a manual fix, or a different
provisioning path. An assessor needs to know which.

### 4.4 Relationship to individual findings

**INV-06.3-02 — Systemic findings supplement, never replace, individual
findings.** All 31 remain in the findings list, each with its own evidence,
lifecycle and remediation. The systemic finding is an additional layer of
interpretation.

Collapsing them would break per-device reporting (FR-RPT-001), remediation
tracking (FR-FND-005) and verification (FR-FND-013).

### 4.5 Confidence

Root cause is a **hypothesis**, and is labelled as such.

| Corroborating signals | Confidence |
|---|---|
| ≥ 4 | High — stated as a probable root cause |
| 2–3 | Medium — stated as a possible common origin |
| 1 | Low — reported as a cluster without a hypothesis |

A hypothesis is never asserted as fact. *"Build-template defect"* is a
conclusion the assessor draws; the platform supplies the evidence for it.

### 4.6 Determinism

Clustering is deterministic: sorted iteration, stable cluster identifiers derived
from the cluster key, no randomness. Cluster ordering in the report is by size
then by identifier (D6).

---

## 5. Interfaces

```
detect_anomalies(campaign) → AnomalyResult {
  groups[]: ⟨key, member_count, analysed: bool, reason?⟩
  anomalies[]: {
     device, peer_group, mode: structural | semantic
     elements[]: ⟨element, prevalence, present_here⟩
     direction: violating | compliant | undetermined
     confidence
  }
}

detect_systemic(findings) → SystemicResult {
  clusters[]: {
     id, control, platform, affected_devices[]
     evidence_pattern
     corroborating_signals[]
     root_cause_hypothesis?, confidence
     unaffected_peers[]                  // the "verify these too" set
  }
}
```

---

## 6. Edge cases

| Case | Handling |
|---|---|
| Peer group smaller than 5 | Not analysed; reported as unanalysable with the count |
| Every device in a group is identical | No anomalies; reported as uniform |
| Every device differs from every other | No modal signature; group reported as heterogeneous, no anomalies emitted |
| Anomaly on a device with 0% coverage | Structural mode still works — this is the primary value case |
| Systemic cluster spanning platforms | Rejected — a common root cause across platforms is not inferable from configuration |
| All devices of a platform fail one control | Systemic by proportion; hypothesis likely "platform default", labelled accordingly |
| Finding cluster where evidence differs after normalisation | Not systemic; reported as a common control failure without a root-cause claim |

**The all-devices-fail case deserves care.** If every device of a platform fails a
control, the root cause is usually the platform's default rather than a build
template — a materially different conclusion, and one that changes the
remediation from *"fix your template"* to *"this is how the vendor ships it"*.

---

## 7. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Anomaly reported as a compliance violation | V-06.3-003 | Over-claiming; direction was undetermined |
| Anomaly altering a control verdict | V-06.3-004 | G1/G2 compromise |
| Noise on small or heterogeneous groups | Group thresholds | DD-06.3-01 prevents |
| Systemic finding replacing individuals | V-06.3-006 | Breaks per-device reporting and tracking |
| Root cause asserted rather than hypothesised | V-06.3-007 | Assessor repeats an unverified claim |
| Non-deterministic clustering | V-06.3-008 | G1 violation |

---

## 8. Verification

```
V-06.3-001   Structural anomaly detection works with zero semantic knowledge
  Requirement  FR-RSK-007
  Method       INTEGRATION
  Procedure    Remove a platform's rulepack entirely. Ingest 40 devices of
               that platform, 3 seeded with a known deviation.
  Acceptance   All 3 detected. Coverage 0%. Zero facts extracted.
               Zero controls evaluated.
  Severity     BLOCKING
  Note         This is the "value before teaching" claim, verified.
```

```
V-06.3-002   Both anomaly directions are detected
  Requirement  §3.4
  Method       UNIT
  Procedure    Group of 40 where 3 devices have an extra element and
               3 different devices lack a common element.
  Acceptance   All 6 detected, correctly categorised as present-here or
               absent-here.
  Severity     MAJOR
```

```
V-06.3-003   Undetermined direction is reported as deviation only
  Requirement  DD-06.3-02, G2
  Method       INTEGRATION
  Procedure    Anomaly on an untaught platform where no control maps to the
               deviating element.
  Acceptance   Reported as a deviation. Zero use of the words violation or
               non-compliant. Direction stated as undetermined.
  Severity     BLOCKING
```

```
V-06.3-004   Anomalies never alter control verdicts
  Requirement  INV-06.3-01
  Method       INTEGRATION
  Procedure    Assess a campaign with anomaly detection enabled and disabled.
  Acceptance   Identical control verdicts, coverage and compliance in both
               runs. Anomalies appear only in their own report section.
  Severity     BLOCKING
```

```
V-06.3-005   Systemic clustering identifies a seeded common defect
  Requirement  FR-RSK-008
  Method       INTEGRATION
  Procedure    Synthetic estate of 40 devices, 31 sharing an identical
               defective ACL block, commissioned in one window.
  Acceptance   One systemic finding covering exactly the 31. Corroborating
               signals listed. The 9 unaffected peers enumerated for
               verification.
  Severity     MAJOR
```

```
V-06.3-006   Systemic findings supplement individual findings
  Requirement  INV-06.3-02
  Method       INTEGRATION
  Procedure    Campaign producing a systemic cluster of 31.
  Acceptance   All 31 individual findings present with their own evidence,
               owners and lifecycle. Each per-device report contains its own
               finding. Zero findings suppressed by clustering.
  Severity     BLOCKING
```

```
V-06.3-007   Root cause is labelled as a hypothesis
  Requirement  §4.5
  Method       CORPUS + MANUAL
  Procedure    Generate systemic findings at each confidence level. Review
               the wording.
  Acceptance   High confidence uses "probable"; medium uses "possible";
               low states a cluster with no hypothesis. Zero unqualified
               causal assertions.
  Severity     MAJOR
```

```
V-06.3-008   Anomaly and clustering are deterministic
  Requirement  G1, D3, D6
  Method       PROPERTY
  Procedure    Run both analyses 10 times over the corpus with shuffled
               device ordering.
  Acceptance   Identical groups, anomalies, clusters, cluster identifiers
               and report ordering.
  Severity     BLOCKING
```

```
V-06.3-009   Small and heterogeneous groups produce no noise
  Requirement  DD-06.3-01
  Method       UNIT
  Procedure    (a) Peer group of 3. (b) Group of 20 where every device is
               structurally distinct.
  Acceptance   (a) not analysed, reported as unanalysable.
               (b) no anomalies, reported as heterogeneous.
               Zero anomalies emitted in either case.
  Severity     MAJOR
```

```
V-06.3-010   Platform-default clusters are labelled correctly
  Requirement  §6
  Method       UNIT
  Procedure    Cluster in which 100% of a platform's devices fail one control.
  Acceptance   Hypothesis states a platform default rather than a build
               template. Remediation guidance reflects the distinction.
  Severity     MINOR
```

```
V-06.3-011   Anomalous elements are promoted in the training queue
  Requirement  §3.7
  Method       INTEGRATION
  Procedure    Untaught platform with detected anomalies; open the training
               queue.
  Acceptance   Templates containing anomalous elements rank above
               equally-frequent non-anomalous templates.
  Severity     MINOR
```

---

## 9. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should peer groups be formed by clustering rather than by declared attributes? | Learned grouping would find natural cohorts the attribute scheme misses, but becomes hard to explain — an assessor must be able to say why two devices are peers. Current design: declared attributes |
| Q2 | Should anomalies ever be promoted to findings once direction is determined? | It would convert a heuristic into a verdict, violating INV-06.3-01. Current design: never — instead, the anomaly drives training, and the resulting control produces a proper verdict |
| Q3 | Should systemic detection span campaigns to catch slow-spreading template defects? | Would catch defects introduced progressively, but cross-campaign clustering mixes different knowledge base versions. Current design: within-campaign, with recurrence tracking (PRD 09 §9) covering the temporal case |
