# TRD-04.1 · Graph Construction and Exposure

---

## 1. Scope

Construction of the configuration graph from resolved fact sets across all
devices in a campaign; computation of device exposure classification.

The graph exists because **relationships are where real breaches live**. Facts
alone give line-level checks; the graph gives findings in which no individual
configuration statement is non-compliant.

**Out of scope:** reachability queries and counterexample generation (TRD-04.2);
attack path assembly (TRD-06.2).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-GRF-001 | Graph across all campaign devices |
| FR-GRF-002 | Required node types |
| FR-GRF-003 | Transitive group expansion, over-broad detection |
| FR-GRF-006 | Device exposure classification |
| FR-GRF-008 | Substrate for compensating control verification |

---

## 3. Design

### 3.1 Node and edge model

```
Node {
  id            : ⟨campaign, kind, device?, identifier⟩   // deterministic
  kind          : device | interface | zone | acl | acl_rule
                | address_object | service_object | user | route
                | vlan | vrf | service
  device        : ref | ⊥                  // ⊥ for campaign-scoped nodes
  attributes    : map<string, Value>
  source_facts  : fact_path[]              // provenance
}

Edge {
  from, to      : Node
  kind          : applied_to | member_of | permits | denies | references
                | in_zone | routes_to | authenticates_via | inherits_from
  attributes    : map<string, Value>
  source_facts  : fact_path[]
}
```

**INV-04.1-01 — Every node and edge traces to source facts.** A graph-derived
finding must be explainable down to configuration lines (G3). An edge with no
`source_facts` is a defect, not a convenience.

**INV-04.1-02 — Node identity is deterministic.** `id` is derived from stable
content, never from insertion order or a counter. Two runs over the same fact
sets produce identical node identifiers (D6).

### 3.2 Construction pipeline

```
  resolved fact sets (all devices in campaign)
      │
  1  per-device node emission        devices, interfaces, zones, rules, objects
      │
  2  intra-device edge emission      applied_to, member_of, in_zone, references
      │
  3  transitive object expansion     group flattening with cycle handling
      │
  4  inter-device linkage            routes, adjacency, shared address space
      │
  5  exposure computation            per device
      │
  6  integrity validation            dangling refs, orphans, cycles
      │
  campaign graph
```

**DD-04.1-01 — Construction is a pure function of the campaign's fact sets.**
No device is queried, no topology is discovered actively. Everything the graph
knows comes from configuration, which keeps G1 and G4 intact — and means the
graph's completeness is bounded by collection completeness, which must be stated.

### 3.3 Inter-device linkage

The hardest part. Devices are linked by inference from configuration alone:

| Signal | Inference |
|---|---|
| Shared subnet on two interfaces | Layer-3 adjacency |
| Static route next-hop within a peer's interface subnet | `routes_to` edge |
| Matching VLAN identifier across trunk interfaces | Layer-2 adjacency (weak) |
| Discovery protocol neighbour tables, where collected | Adjacency (strong) |
| Consistent naming or description conventions | **Not used** — unreliable |

**DD-04.1-02 — Weak links are labelled, not discarded.** An edge carries a
`confidence` attribute. Reachability findings derived through low-confidence
edges state that fact in their evidence, so an assessor can weigh them.

**DD-04.1-03 — Missing devices bound the graph, and this must surface.** If 23 of
412 in-scope devices were not collected (TRD-01.1 §3.8), the graph cannot exclude
paths through them. Every reachability conclusion therefore carries:

```
assumptions: [ "Based on 389 of 412 in-scope devices. Paths through the
                23 uncollected devices cannot be excluded." ]
confidence: medium
```

This is the same honesty requirement as G2, applied to graph analysis: the system
states what it could not determine rather than implying completeness.

### 3.4 Transitive object expansion

FR-GRF-003. Catches one of the most common real-world defects: a group named
`Trusted-Admins` that transitively contains `0.0.0.0/0` three nestings down.

The expansion algorithm lives in TRD-03.2 §4.6 (it is a derived fact). The graph
consumes `filter.objects[].expanded` and emits:

```
address_object[Trusted-Admins] --member_of--> address_object[Partners]
address_object[Partners]       --member_of--> literal[0.0.0.0/0]
```

Over-broad detection:

```
over_broad(object) =
     "0.0.0.0/0" ∈ object.expanded
  or "::/0"      ∈ object.expanded
  or |object.expanded| covers > threshold of the address space
```

**A partially expanded group is `default_unknown` and produces no over-broad
determination** — understating membership would produce a false PASS.

### 3.5 Zone and trust modelling

Not every platform has explicit zones. Where absent, zones are derived:

| Platform | Zone source |
|---|---|
| PAN-OS, FortiOS, SRX | Explicit zone configuration |
| Cisco IOS, Arista | Derived from interface role: default route → external; RFC1918 only → internal |
| Cloud policy | VPC / VNet / subnet grouping |

Trust levels are ordinal, not absolute:

```
external < dmz < internal < management
```

**DD-04.1-04 — Derived zones are marked as derived.** A finding stating
*"management plane reachable from untrusted zone"* where the zone was inferred
rather than configured must say so, because the administrator may disagree with
the inference and needs to see the basis for it.

### 3.6 Exposure classification

FR-GRF-006. Feeds severity weighting (TRD-06.1).

```
exposure(device) =
    internet_facing  if ∃ interface in an external zone
                     or ∃ default route to a non-private next hop
                     or ∃ terminated external circuit (VPN, WAN)
    dmz              if ∃ interface in a dmz zone and none external
    isolated         if all interfaces are in a management zone
                     and no route reaches a non-management zone
    internal         otherwise
```

**INV-04.1-03 — Exposure is computed, never read from configuration.** No device
declares its own exposure. It is a property of position, and position is a
property of the graph.

Where the graph is incomplete (DD-04.1-03), exposure carries a confidence and
defaults to the **more severe** classification when ambiguous. Over-stating
exposure inflates severity, which is a false alarm; under-stating it hides a
critical finding. The asymmetry favours the false alarm.

### 3.7 Integrity validation

Before the graph is released to consumers:

| Check | On failure |
|---|---|
| No dangling edge endpoints | Edge dropped; defect recorded |
| No node without `source_facts` | Node dropped; defect recorded (INV-04.1-01) |
| Membership cycles terminate | Cycle recorded; expansion marked partial |
| Deterministic node ordering | Sort applied before release (D6) |
| Zone assignment total | Unassigned interfaces default to `internal`, flagged |

### 3.8 Scale

NFR-PERF-006: construction and analysis under 60 s for 1,000 devices.

| Estate | Nodes | Edges |
|---|---|---|
| 100 devices | ~5,000 | ~20,000 |
| 1,000 devices | ~50,000 | ~200,000 |
| 10,000 devices | ~500,000 | ~2,000,000 |

In-process graph representation is sufficient at these sizes; this is
estate-scale, not web-scale. Adjacency is stored as sorted arrays rather than
hash structures so that traversal order is deterministic without an explicit sort
at each step.

---

## 4. Interfaces

**Input:** `⟨campaign, resolved_fact_sets[], collection_completeness⟩`

**Output**

```
CampaignGraph {
  nodes[], edges[]
  exposure: map<device, ⟨classification, confidence, basis⟩>
  zones[]: ⟨name, trust_level, derived: bool⟩
  assumptions[]: string          // from incompleteness
  integrity_defects[]
  stats: ⟨node_count, edge_count, weak_edge_count⟩
}
```

---

## 5. Edge cases

| Case | Handling |
|---|---|
| Single-device campaign | Graph built; inter-device analysis yields nothing; stated rather than silently empty |
| Overlapping RFC1918 space across sites | Address-space linkage suppressed; adjacency requires a stronger signal |
| NAT between devices | Address translation modelled as an edge attribute; reachability through NAT flagged as lower confidence |
| Device with no interfaces extractable | Node emitted; exposure `unknown`; severity weighting falls back to base |
| Cloud policy with no topology | Security-group relationships modelled; no physical adjacency |
| Two devices with identical hostnames | Node identity uses device record identity, not hostname (TRD-01.1 DD-01.1-02) |
| Asymmetric routing | Both directions modelled independently; reachability is directional |

**The NAT case is worth flagging.** Reachability across a NAT boundary is
genuinely harder to establish from configuration alone, and a tool that models it
naively will produce confident wrong paths. Lower confidence plus explicit
labelling is the honest treatment.

---

## 6. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Spurious inter-device edge | Edge confidence; manual review | False reachability finding — mitigated by DD-04.1-02 labelling |
| Missing inter-device edge | Collection completeness | Missed finding; assumptions state the bound |
| Wrong zone derivation | DD-04.1-04 labelling | Wrong exposure → wrong severity. Visible in evidence |
| Non-deterministic node identity | V-04.1-006 | G1 violation |
| Graph memory exhaustion at 10,000 devices | Performance testing | Bounded by sorted-array representation |

---

## 7. Verification

```
V-04.1-001   Every node and edge traces to source facts
  Requirement  INV-04.1-01, G3
  Method       PROPERTY + CORPUS
  Procedure    Build graphs for all corpus campaigns. Assert every node and
               edge carries non-empty source_facts resolving to real facts.
  Acceptance   100%. Zero untraceable graph elements.
  Severity     BLOCKING
```

```
V-04.1-002   Transitive expansion detects nested over-broad membership
  Requirement  FR-GRF-003
  Method       UNIT + CORPUS
  Procedure    Object group A containing B containing C containing 0.0.0.0/0.
  Acceptance   over_broad(A) is true. Expansion path recorded and reportable
               as evidence. Detected at nesting depth ≥ 3.
  Severity     BLOCKING
```

```
V-04.1-003   Partial expansion does not yield an over-broad determination
  Requirement  §3.4, G2
  Method       UNIT
  Procedure    Object group referencing an undefined member.
  Acceptance   Expansion default_unknown. over_broad returns unknown, not
               false. Dependent controls UNKNOWN.
  Severity     BLOCKING
```

```
V-04.1-004   Exposure classification is correct on a known topology
  Requirement  FR-GRF-006, INV-04.1-03
  Method       INTEGRATION
  Procedure    Synthetic estate with known internet-facing, DMZ, internal and
               isolated devices.
  Acceptance   100% correct classification. Basis recorded for each.
  Severity     BLOCKING
```

```
V-04.1-005   Incompleteness is stated, not hidden
  Requirement  DD-04.1-03
  Method       INTEGRATION
  Procedure    Build a graph for a campaign with 23 of 412 devices uncollected.
  Acceptance   assumptions[] names the bound. Every reachability conclusion
               derived from this graph carries the assumption and a confidence
               below `high`.
  Severity     BLOCKING
```

```
V-04.1-006   Graph construction is deterministic
  Requirement  INV-04.1-02, G1, D6
  Method       PROPERTY
  Procedure    Build the same campaign graph 10 times with shuffled device
               ordering and varied concurrency.
  Acceptance   Identical node identifiers, identical edge sets, identical
               adjacency ordering, identical exposure classifications.
  Severity     BLOCKING
```

```
V-04.1-007   Derived zones are labelled as derived
  Requirement  DD-04.1-04
  Method       UNIT + CORPUS
  Procedure    Build graphs for platforms with and without explicit zones.
  Acceptance   Zones from Cisco/Arista configurations carry derived: true.
               Zones from PAN-OS/FortiOS carry derived: false. Findings
               referencing derived zones state the basis.
  Severity     MAJOR
```

```
V-04.1-008   Ambiguous exposure defaults to the more severe classification
  Requirement  §3.6
  Method       UNIT
  Procedure    Device whose exposure cannot be determined between internal
               and dmz owing to a missing peer.
  Acceptance   Classified dmz with confidence reduced. Never classified
               isolated when ambiguous.
  Severity     MAJOR
```

```
V-04.1-009   Weak inter-device edges are labelled
  Requirement  DD-04.1-02
  Method       CORPUS
  Procedure    Build graphs where adjacency is inferred from VLAN matching
               versus from collected neighbour tables.
  Acceptance   VLAN-derived edges carry confidence ≤ medium; neighbour-table
               edges carry high. Findings surface the weakest edge in the path.
  Severity     MAJOR
```

```
V-04.1-010   Graph performance at estate scale
  Requirement  NFR-PERF-006
  Method       PERFORMANCE
  Procedure    Construct a graph for a synthetic 1,000-device estate,
               reference profile.
  Acceptance   Construction and integrity validation < 60 s.
  Severity     MAJOR
```

---

## 8. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should discovery-protocol neighbour data be collected specifically to strengthen adjacency? | It materially improves inter-device linkage, but adds a collection command and only works where the protocol is enabled — which itself is often a compliance finding. Current design: used when present in a `show tech` bundle, not collected specifically |
| Q2 | Should NAT-traversing reachability be modelled at all, or excluded? | Excluding avoids confident wrong paths; modelling catches real exposures. Current design: modelled at reduced confidence with explicit labelling |
| Q3 | Should exposure be recomputed per campaign or persisted on the device record? | Per campaign is correct (topology changes) but means historical severity cannot be recomputed without the historical graph. Current design: per campaign, persisted with the campaign |
