# TRD-06.2 · Attack Path Computation

---

## 1. Scope

Assembly of individual findings into **ordered chains** that together enable
reachability from an untrusted zone to a protected asset; identification of the
lowest-cost link whose remediation breaks each chain; production of the
prioritised remediation list.

**Out of scope:** reachability analysis itself (TRD-04.2); severity weighting
(TRD-06.1); remediation planning (TRD-07.1).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-RSK-003 | Attack path computation |
| FR-RSK-004 | Lowest-cost breaking link |
| FR-RSK-005 | Prioritised list with unreachability count |
| FR-RPT-009 | Report's top-N remediation section |

---

## 3. Design

### 3.1 Why this exists

A report with 400 findings sorted by severity is not actionable. It answers
*"what is wrong"* — which the administrator broadly knows — rather than the
question they actually have:

> *"I have Thursday afternoon. What do I fix?"*

An attacker does not see a list. They see a route. Inverting the report into
chains changes it from an inventory into a prioritisation argument:

```
Remediate these 6 findings and 340 of 400 become unreachable.
```

### 3.2 The enabling-condition model

A finding participates in a path when it **enables a transition** the attacker
needs. Controls declare this:

```yaml
control_id: NSCA-MGMT-002
attack_semantics:
  enables: credential_exposure          # what a violation gives an attacker
  requires: network_reachability        # what the attacker needs first
```

Enabling categories, deliberately small:

| Category | Meaning |
|---|---|
| `network_reachability` | Traffic can reach the target |
| `credential_exposure` | Credentials become obtainable |
| `authentication_bypass` | Authentication can be skipped or defeated |
| `privilege_escalation` | Lower privilege becomes higher |
| `code_execution` | Arbitrary code can be run |
| `detection_evasion` | Activity is not recorded |
| `lateral_movement` | Access extends to another device |

**DD-06.2-01 — Categories are coarse deliberately.** A fine-grained model would
require the control library to encode an exploitation taxonomy it cannot keep
current. Seven categories are enough to chain findings meaningfully and simple
enough that an author can classify a control correctly without specialist
knowledge.

### 3.3 Path assembly

```
assemble(findings, graph, targets) →
  paths = []
  for each ⟨source_zone, target_asset⟩ in targets:
      reach = TRD-04.2.query(graph, source_zone → target_asset)
      if reach.outcome ≠ reachable: continue

      # findings on devices along the reachable path
      candidates = findings on reach.path devices, verdict == FAIL

      # order by the transition each enables
      chain = order_by_dependency(candidates, reach.path)
      if chain is a valid enabling sequence:
          paths += AttackPath(reach, chain)
```

**INV-06.2-01 — A path requires an established reachability result.** Chains are
never assembled from findings alone. Without a concrete reachable path from
TRD-04.2, three severe findings on three devices are three findings, not a chain.

This prevents the most tempting error in this area: inferring a chain from
plausibility rather than from the network.

**INV-06.2-02 — Every path inherits its reachability counterexample.** The path's
evidence is the packet and rule chain from TRD-04.2, plus the findings at each
step. A path without a counterexample is not emitted.

### 3.4 Ordering within a chain

Links are ordered by the sequence in which an attacker would need them:

```
network_reachability → credential_exposure → authentication_bypass
                     → privilege_escalation → lateral_movement
```

Where two findings occupy the same position, both are recorded as alternatives at
that step. A step with alternatives is **harder to break** — remediating one
leaves the other — and this is reflected in cost (§3.5).

### 3.5 Breaking-link identification

FR-RSK-004. Breaking any single link breaks the chain — so the question is which
link is cheapest.

```
cost(finding) = w₁·command_count
              + w₂·impact_class_weight        # safe < service_affecting < lockout_risk
              + w₃·prerequisite_count
              + w₄·alternative_count          # other findings at the same step
              + w₅·(1 if remediation unavailable for this version)
```

```
breaking_link(path) = argmin cost over path.links
```

**DD-06.2-02 — Cost is operational, not security-weighted.** A critical-severity
finding is not automatically the best link to break; a medium-severity finding
removable with one safe command frequently is. Severity determines *importance*;
cost determines *sequencing*. Conflating them reproduces the severity-sorted list
this subsystem exists to replace.

**A step with alternatives cannot be broken by remediating one alternative.**
`alternative_count` therefore raises cost sharply, and where every link has
alternatives the path reports that no single remediation breaks it.

### 3.6 The prioritised list

```
prioritise(paths, findings) →
  selected = ∅
  while ∃ path not broken by selected:
      f = the finding breaking the most unbroken paths,
          tie-broken by lowest cost, then by finding id      # deterministic
      selected += f
  unreachable = findings whose only paths are all broken by selected
  return selected, |unreachable|
```

This is a greedy set-cover. **DD-06.2-03 — Greedy is chosen over optimal
deliberately.** An optimal cover is NP-hard, and — more importantly — a greedy
solution is *explainable*: each selection is justified by the paths it breaks. An
assessor can follow the reasoning; they cannot follow a solver's output.

Determinism requires the full tie-break chain: paths broken, then cost, then
finding identifier (D6).

```
TOP 5 REMEDIATIONS
Resolving these 5 makes 23 of 31 findings unreachable.

  1  F-000518  Remove 0.0.0.0/0 from group Partners     1 cmd   safe
              breaks AP-003, AP-007
  2  F-000412  Disable Telnet on EDGE-FW-01             3 cmds  lockout-risk
              breaks AP-001
  ...
```

### 3.7 "Unreachable" is precise

**INV-06.2-03 — Unreachable means not reachable by the analysed paths, not
harmless.**

A finding whose paths are all broken remains a finding. It is still non-compliant,
still reported, still requires remediation eventually. What changes is priority.

The report states this:

```
23 findings become unreachable by external attack paths once the above
are remediated. They remain non-compliant and are listed in full in
Section 3.
```

Without this sentence the figure reads as *"340 findings will be fixed"*, which
is false and would be a serious misrepresentation in an audit report.

### 3.8 Confidence propagation

Paths inherit the **weakest** confidence along their route:

- Weak inter-device edges (TRD-04.1 DD-04.1-02)
- Incomplete collection (TRD-04.1 DD-04.1-03)
- NAT traversal

```
AP-003   confidence: medium
  Weakest element: VLAN-inferred adjacency between SW-Core-02 and EDGE-FW-01
  Assumption: based on 389 of 412 in-scope devices
```

**DD-06.2-04 — Low-confidence paths are reported separately** from
high-confidence ones, and the prioritised list is computed over high-confidence
paths first. Directing an administrator's limited time at a speculative path
spends credibility that is difficult to recover.

### 3.9 Determinism

Path assembly, cost computation and greedy selection are pure functions of
`⟨findings, graph, targets⟩`. Traversal ordering is explicit (D6); tie-breaks
terminate in a stable identifier; no clock, no randomness.

---

## 4. Interfaces

```
compute(findings, graph, target_definitions) → AttackPathResult

AttackPathResult {
  paths[]: {
     id, source_zone, target_asset
     links[]: ⟨finding, enabling_category, alternatives[]⟩
     counterexample                      // inherited from TRD-04.2
     breaking_link, breaking_cost
     confidence, assumptions[]
  }
  prioritised[]: ⟨finding, paths_broken[], cost, rank⟩
  findings_made_unreachable: int
  paths_unbreakable[]                    // every link has alternatives
}
```

---

## 5. Edge cases

| Case | Handling |
|---|---|
| No reachable paths | Empty result; report states no external attack paths were found, with the collection bound |
| Path with a single link | Valid; breaking link is that finding |
| Every link has alternatives | Path reported as unbreakable by a single remediation; minimum breaking set computed |
| Finding on a device outside the reachable path | Not a link; remains in the findings list |
| Cyclic path | Terminated by TRD-04.2 visited-set |
| Path through a device whose findings are all UNKNOWN | Path confidence reduced; reported with the gap named |
| Target asset present on no collected device | Target skipped; recorded |
| Two paths sharing all links | Deduplicated by link set |

**The all-UNKNOWN device case is worth attention.** A device we could not assess
sitting on a reachable path is a genuine blind spot — the path may be worse than
reported. This is stated rather than assumed benign.

---

## 6. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Chain inferred without reachability | V-06.2-001 | Speculative paths; credibility loss |
| Breaking link chosen by severity | V-06.2-003 | Reproduces the severity-sorted list |
| "Unreachable" read as "resolved" | V-06.2-005 | **Misrepresentation in an audit report** |
| Low-confidence path prioritised | V-06.2-006 | Administrator time wasted on speculation |
| Non-deterministic selection | V-06.2-007 | G1 violation; report instability |
| Combinatorial blow-up on dense estates | Budget in TRD-04.2 | UNKNOWN paths, not a hang |

---

## 7. Verification

```
V-06.2-001   Paths require established reachability
  Requirement  INV-06.2-01
  Method       PROPERTY + INTEGRATION
  Procedure    Construct findings that would plausibly chain, on devices
               between which no reachable path exists.
  Acceptance   Zero paths emitted. Findings reported individually.
  Severity     BLOCKING
```

```
V-06.2-002   Every path carries a counterexample
  Requirement  INV-06.2-02, G3
  Method       CORPUS
  Procedure    Compute paths across all corpus campaigns.
  Acceptance   100% carry a concrete packet and rule chain inherited from
               TRD-04.2. Zero paths without one.
  Severity     BLOCKING
```

```
V-06.2-003   Breaking link is chosen by cost, not severity
  Requirement  FR-RSK-004, DD-06.2-02
  Method       UNIT
  Procedure    Path with a critical finding requiring 4 lockout-risk commands
               and a medium finding requiring 1 safe command.
  Acceptance   The medium finding is selected. Cost breakdown recorded and
               displayable.
  Severity     MAJOR
```

```
V-06.2-004   Prioritised list maximises paths broken
  Requirement  FR-RSK-005
  Method       INTEGRATION
  Procedure    Synthetic estate with 12 known paths and a known optimal
               cover of 4 findings.
  Acceptance   Greedy selection breaks all 12 with ≤ 6 findings.
               Each selection states which paths it breaks.
  Severity     MAJOR
```

```
V-06.2-005   "Unreachable" is stated precisely
  Requirement  INV-06.2-03
  Method       INTEGRATION + MANUAL
  Procedure    Generate a report with a top-N section. Present it to three
               readers unfamiliar with the tool and ask what happens to the
               unreachable findings.
  Acceptance   Report states unreachable findings remain non-compliant.
               All three readers answer correctly. Zero readers conclude the
               findings are resolved.
  Severity     BLOCKING
  Note         This is a misrepresentation risk in a formal audit report.
```

```
V-06.2-006   Low-confidence paths are separated
  Requirement  DD-06.2-04
  Method       CORPUS
  Procedure    Compute paths on a campaign with VLAN-inferred adjacency,
               NAT boundaries and 94% collection completeness.
  Acceptance   Paths carry inherited confidence. Prioritised list computed
               over high-confidence paths first. Low-confidence paths
               reported separately with assumptions named.
  Severity     MAJOR
```

```
V-06.2-007   Path computation is deterministic
  Requirement  G1, D3, D6
  Method       PROPERTY
  Procedure    Compute paths for all corpus campaigns 10 times with shuffled
               finding ordering and varied concurrency.
  Acceptance   Identical paths, identical breaking links, identical
               prioritised ordering including tie-breaks.
  Severity     BLOCKING
```

```
V-06.2-008   Unbreakable paths are reported honestly
  Requirement  §5
  Method       UNIT
  Procedure    Path in which every link has an alternative at the same step.
  Acceptance   Reported as not breakable by a single remediation.
               Minimum breaking set computed and shown. Zero claims that one
               finding breaks it.
  Severity     MAJOR
```

```
V-06.2-009   Unassessed devices on a path are surfaced
  Requirement  §5
  Method       INTEGRATION
  Procedure    Path traversing a device whose controls are all UNKNOWN.
  Acceptance   Path confidence reduced. The unassessed device named in the
               path evidence. Zero implications that the path is fully
               characterised.
  Severity     MAJOR
```

```
V-06.2-010   Path computation performance
  Requirement  NFR-PERF-006
  Method       PERFORMANCE
  Procedure    1,000-device synthetic estate with ~2,500 findings.
  Acceptance   Path assembly and prioritisation < 30 s, on top of the
               60 s graph budget.
  Severity     MINOR
```

---

## 8. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should enabling categories be extended toward a full exploitation taxonomy? | Richer chaining, but the library would need continuous curation against an evolving threat landscape and control authors would need specialist knowledge. Current design: seven coarse categories (DD-06.2-01) |
| Q2 | Should paths chain across campaigns, capturing an attacker's persistence over time? | Temporally realistic, but a finding remediated in Q3 cannot enable an attack in Q4. Current design: within-campaign only |
| Q3 | Should the cost function weights be tunable per organisation? | Different estates weigh lockout risk very differently. Current design: fixed weights with the breakdown displayed, so an assessor can override the ordering manually |
