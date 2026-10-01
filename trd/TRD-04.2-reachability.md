# TRD-04.2 · Reachability and Counterexamples

---

## 1. Scope

Evaluation of reachability queries over the campaign graph, and generation of
**concrete counterexamples** — a specific packet plus the rule chain that permits
it — for every graph-derived finding.

**Out of scope:** graph construction (TRD-04.1); assembling findings into attack
paths (TRD-06.2).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-GRF-004 | Reachability queries including multi-device paths |
| FR-GRF-005 | Concrete counterexample with rule chain |
| FR-GRF-007 | Emergent violations where no single statement is non-compliant |
| FR-GRF-008 | Compensating control verification |
| G3 | Counterexamples are evidence, bound to configuration lines |

---

## 3. Design

### 3.1 Why counterexamples rather than assertions

A finding stating *"management plane may be reachable from an untrusted zone"* is
an opinion. A finding stating:

```
203.0.113.5:44210 → 10.0.0.1:22 TCP is permitted, via
  EDGE-FW-01 rule `outside-in` line 14
  → group Trusted-Admins → group Partners → 0.0.0.0/0
```

is a fact an administrator can verify in ninety seconds, and cannot argue with.

**INV-04.2-01 — Every graph finding carries a counterexample.** A reachability
finding without one is not emitted. If the analysis can establish that a path
exists but cannot produce a concrete instance, the result is UNKNOWN, not FAIL
(G2).

### 3.2 The packet model

Reachability is evaluated over a five-field packet space:

```
Packet = ⟨src_addr, dst_addr, protocol, src_port, dst_port⟩
```

Rules partition this space. Analysis operates on **sets** of packets, not
individual packets, and materialises a single representative only when producing
a counterexample.

```
PacketSet = ⟨src: cidr_set, dst: cidr_set,
             proto: proto_set, sport: range_set, dport: range_set⟩
```

**DD-04.2-01 — Set-based evaluation, point-based reporting.** Evaluating
individual packets does not scale; reporting a set is unconvincing. The analysis
therefore carries sets through traversal and selects one concrete representative
at the end, choosing the most plausible member (a routable source address, a
realistic ephemeral port).

### 3.3 Rule chain evaluation

Access rules are first-match ordered. Evaluating a rule set against a packet set
splits it:

```
evaluate(packet_set, rules) →
  remaining = packet_set
  permitted = ∅
  chain     = []

  for rule in rules:                     # source order — INV-03.1-03
      matched = remaining ∩ rule.selector
      if matched ≠ ∅:
          chain += ⟨rule, matched⟩
          if rule.action == permit: permitted ∪= matched
          remaining −= matched
      if remaining == ∅: break

  return permitted, chain
```

**INV-04.2-02 — Rule ordering is load-bearing.** `filter.rules[]` element order
is source order (TRD-03.1 INV-03.1-03) and TRD-02.3 DD-02.3-01 preserves it
through inheritance merge. If either is wrong, this analysis reports on a policy
the device does not implement.

### 3.4 Multi-device traversal

```
reachable(src_zone, dst_service, graph) →
  frontier = { ⟨src_zone, full_packet_set, [] ⟩ }
  visited  = ∅
  results  = []

  while frontier ≠ ∅:                    # deterministic ordering
      ⟨node, pkts, path⟩ = pop_lowest_ordered(frontier)
      if ⟨node, pkts⟩ ∈ visited: continue
      visited ∪= { ⟨node, pkts⟩ }

      if node ≍ dst_service and pkts ≠ ∅:
          results += ⟨pkts, path⟩
          continue

      for edge in outgoing(node):        # sorted — D6
          pkts' = apply(edge, pkts)      # filters, NAT, routing
          if pkts' ≠ ∅ and |path| < MAX_DEPTH:
              frontier += ⟨edge.to, pkts', path + edge⟩
```

| Bound | Value | Reason |
|---|---|---|
| `MAX_DEPTH` | 12 hops | Beyond this, path confidence is negligible |
| Visited-set key | `⟨node, packet_set⟩` | Prevents revisiting with a narrower set |
| Time budget | 30 s per query | Beyond this the query returns UNKNOWN, not partial |

**DD-04.2-02 — Budget exhaustion yields UNKNOWN, never "no path found".**
A truncated search that reports no path is a false negative presented as a clean
result. On exhaustion the query returns UNKNOWN with the reason recorded.

### 3.5 Counterexample selection

From a permitted packet set, choose one representative:

```
select_counterexample(packet_set) →
  src   = first non-reserved, non-private address in src set,
          else the lowest address
  dst   = the specific target address
  proto = the most specific protocol in the set
  sport = a plausible ephemeral port (44210 by convention — deterministic)
  dport = the service port
```

**DD-04.2-03 — Selection is deterministic.** Two runs produce the identical
counterexample packet (D3). A counterexample that changes between runs
undermines the report's reproducibility and looks like instability.

### 3.6 Emergent violation detection

FR-GRF-007. The controls that only a graph can evaluate.

```yaml
control_id: NSCA-GRAPH-004
title: Management plane must not be reachable from untrusted zones
family: access_control
severity_base: critical

graph_query:
  type: reachability
  source: "zones where trust_level <= external"
  target: "services where category == management_plane"
  expect: unreachable

requires_graph: true
```

| Query type | Semantics |
|---|---|
| `reachability` | Does any packet reach the target? |
| `unreachable` | Assert no packet reaches the target |
| `membership` | Does an object transitively contain a prohibited member? |
| `applied` | Is an over-broad rule bound to an interface in a given zone? |
| `path_property` | Does every path satisfy a predicate (e.g. traverses a firewall)? |

**Verdict mapping:**

| Analysis outcome | Verdict |
|---|---|
| No path, search complete | PASS |
| Path found, counterexample produced | FAIL |
| Path found, no counterexample producible | UNKNOWN (INV-04.2-01) |
| Search budget exhausted | UNKNOWN (DD-04.2-02) |
| Graph incomplete in a relevant region | UNKNOWN, assumptions stated |

### 3.7 Compensating control verification

FR-GRF-008. The capability that changes the assessor/administrator relationship
(PRD 09 §6).

An administrator disputes a finding: *"that device is only reachable from the
isolated management network."* Rather than accepting the claim, the platform
checks it.

```
verify_compensating(claim) →
  translate claim → reachability query
  run query
  match outcome:
      no path, complete search      → CONFIRMED
      path found + counterexample   → REFUTED, attach counterexample
      budget exhausted              → UNVERIFIABLE (analysis incomplete)
      claim not translatable        → UNVERIFIABLE (out of model)
```

**Three outcomes, never two.** Claims resting on facts outside the configuration
model — physical segmentation, an air gap, a procedural control — are
`UNVERIFIABLE` with the reason stated. Asserting `REFUTED` for a claim the model
cannot represent would be exactly the over-claiming G2 forbids.

Assumptions are always attached:

```
Verification: REFUTED
  MGMT-SW-04 Gi0/8 bridges VLAN 250 and VLAN 40.
  Counterexample: 10.40.7.19 → 10.250.0.11:23 TCP
  Rule chain: SW-Core-02 acl[user-out]:22 permit

  Assumptions
    Based on 389 of 412 in-scope devices. Additional paths through the
    23 uncollected devices cannot be excluded.
  Confidence: medium
```

### 3.8 Explaining a PASS

A `PASS` on an `unreachable` query is a claim that **no** path exists — a
universal statement, and therefore only as strong as the graph's completeness.

```
NSCA-GRAPH-004 → PASS
  No path from any external zone to a management service across the
  389 collected devices.
  ⚠ 23 in-scope devices were not collected. This conclusion cannot
    exclude paths through them.
```

**DD-04.2-04.** Where collection completeness is below 100%, an `unreachable`
PASS is downgraded to `PASS (PARTIAL)` with the bound stated. This is the same
mechanism as scope contamination (PRD 09 §2.2), applied to graph conclusions.

---

## 4. Interfaces

```
query(graph, GraphQuery) → QueryResult

QueryResult {
  outcome: reachable | unreachable | unknown
  counterexample?: ⟨packet, path[]⟩
  path[]: ⟨node, device, edge_kind, rule_ref, artifact_lines, confidence⟩
  weakest_edge_confidence
  assumptions[]
  search_stats: ⟨nodes_visited, depth_reached, budget_used, exhausted⟩
}
```

`search_stats` is required for explainability: an assessor challenged on an
`unreachable` result must be able to see that the search was complete rather than
truncated.

---

## 5. Edge cases

| Case | Handling |
|---|---|
| Reachability through NAT | Address translation applied as an edge transform; path confidence reduced |
| Asymmetric paths | Directional; forward reachability does not imply return path |
| Stateful firewall return traffic | Modelled as implicitly permitted for established flows; noted in the path |
| Rule referencing an unresolvable object | Rule contributes UNKNOWN; the query cannot return PASS |
| Zero-device or single-device campaign | Multi-device queries return unknown with the reason stated |
| Cyclic routing | Visited-set key terminates traversal |
| Overlapping address space across sites | Traversal suppressed where linkage confidence is below threshold |
| Query target that no device implements | NOT_APPLICABLE rather than PASS |

**The stateful-return case matters for correctness.** Treating return traffic as
requiring an explicit permit rule produces large numbers of false findings on
every modern firewall.

---

## 6. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Rule ordering wrong upstream | Differential testing (TRD-02.3 V-02.3-003) | Analysis describes a policy the device does not implement |
| Truncated search reported as PASS | V-04.2-004 | **False assurance.** DD-04.2-02 prevents |
| Counterexample not reproducible | V-04.2-006 | Report instability; undermines credibility |
| Spurious edge produces a false path | Edge confidence surfaced in the path | Assessor can weigh; V-04.2-008 |
| Incompleteness not stated on a PASS | V-04.2-005 | G2 violation |
| Combinatorial blow-up on large policies | Budget and packet-set representation | UNKNOWN, not hang |

---

## 7. Verification

```
V-04.2-001   Every graph FAIL carries a counterexample
  Requirement  FR-GRF-005, INV-04.2-01
  Method       PROPERTY + CORPUS
  Procedure    Run all graph controls across all corpus campaigns.
  Acceptance   100% of FAIL verdicts carry a concrete packet and a rule chain.
               Zero FAIL verdicts without one.
  Severity     BLOCKING
```

```
V-04.2-002   Counterexamples are correct
  Requirement  FR-GRF-005, G3
  Method       INTEGRATION
  Procedure    Synthetic estate with known reachability. For each generated
               counterexample, independently simulate the packet against the
               rule sets.
  Acceptance   100% of counterexample packets are genuinely permitted by the
               stated chain. Zero fabricated paths.
  Severity     BLOCKING
```

```
V-04.2-003   Rule chain references resolve to configuration lines
  Requirement  G3
  Method       PROPERTY + CORPUS
  Procedure    For every path element carrying rule_ref, resolve
               artifact_lines and compare against the rule's source text.
  Acceptance   100% resolve to real configuration lines.
  Severity     BLOCKING
```

```
V-04.2-004   Budget exhaustion yields unknown, not pass
  Requirement  DD-04.2-02, G2
  Method       UNIT
  Procedure    Construct a graph and query exceeding the time budget.
  Acceptance   outcome == unknown. search_stats.exhausted == true.
               Zero PASS verdicts from exhausted searches.
  Severity     BLOCKING
```

```
V-04.2-005   Incomplete collection downgrades an unreachable PASS
  Requirement  DD-04.2-04, G2
  Method       INTEGRATION
  Procedure    Campaign with 94% collection completeness; graph control
               returning no path.
  Acceptance   Verdict PASS (PARTIAL). Assumption stated naming the
               uncollected count. Zero unqualified PASS verdicts.
  Severity     BLOCKING
```

```
V-04.2-006   Counterexample selection is deterministic
  Requirement  DD-04.2-03, G1, D3
  Method       PROPERTY
  Procedure    Run all graph queries across the corpus 10 times.
  Acceptance   Byte-identical counterexample packets and paths every run.
  Severity     BLOCKING
```

```
V-04.2-007   Compensating control verification produces three outcomes
  Requirement  FR-GRF-008, PRD 09 §6
  Method       INTEGRATION
  Procedure    Three claims: (a) isolation that holds, (b) isolation refuted
               by a bridging interface, (c) a claim of physical segmentation.
  Acceptance   (a) CONFIRMED, (b) REFUTED with counterexample,
               (c) UNVERIFIABLE with reason "outside configuration model".
               Zero REFUTED verdicts on unrepresentable claims.
  Severity     BLOCKING
```

```
V-04.2-008   Weak-confidence paths are labelled
  Requirement  TRD-04.1 DD-04.1-02
  Method       CORPUS
  Procedure    Queries traversing VLAN-inferred adjacency and NAT boundaries.
  Acceptance   weakest_edge_confidence reported. Findings surface it in
               evidence. Assessor can distinguish a certain path from an
               inferred one.
  Severity     MAJOR
```

```
V-04.2-009   Stateful return traffic does not generate false findings
  Requirement  §5
  Method       CORPUS
  Procedure    Assess corpus firewall configurations with stateful policies.
  Acceptance   Zero findings asserting that permitted outbound flows lack
               return-path rules.
  Severity     MAJOR
```

```
V-04.2-010   Emergent violation detected where no single statement is wrong
  Requirement  FR-GRF-007
  Method       INTEGRATION
  Procedure    Synthetic estate where a permit-any rule, an interface binding
               and a nested over-broad group jointly expose the management
               plane, but each is individually defensible.
  Acceptance   NSCA-GRAPH-004 FAIL with a three-element chain. Zero
               line-level controls fail on the contributing devices.
  Severity     BLOCKING
  Note         This is the capability that distinguishes the product from a
               checklist tool.
```

```
V-04.2-011   Reachability analysis performance
  Requirement  NFR-PERF-006
  Method       PERFORMANCE
  Procedure    All graph controls against a 1,000-device synthetic estate.
  Acceptance   Full graph control set < 60 s including construction.
  Severity     MAJOR
```

---

## 8. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should packet sets be represented as interval unions or as decision diagrams? | Decision diagrams handle large overlapping rule sets more efficiently; interval unions are simpler and easier to make deterministic. Current design: interval unions, revisit if large firewall policies exhaust the budget |
| Q2 | Should the analysis model routing protocols dynamically, or only static and connected routes? | Dynamic modelling is more accurate but requires simulating protocol convergence from configuration, which is a substantially larger problem. Current design: static and connected only, stated as a limitation |
| Q3 | Should an `unreachable` PASS ever be issued at less than 100% collection completeness? | Never issuing one makes the control useless in practice, since 100% collection is rare. Current design: PASS (PARTIAL) with the bound stated — the assessor decides whether it is sufficient |
