# TRD-02.3 · Effective Configuration Resolution

---

## 1. Scope

Computing what a device **actually does**, from a parse tree that may contain
inherited layers, overlapping scopes, deletions, and multi-context definitions.

> **The text is not the truth.** A parser that ignores inheritance produces
> confidently wrong answers on every real enterprise deployment — which are
> precisely the deployments that matter.

**Out of scope:** parsing (TRD-02.1); fact extraction (TRD-03.1).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-PRS-009 | Inheritance and override resolution across four mechanisms |
| FR-PRS-010 | Source layer recorded on every inherited node |
| G2 | Unresolvable inheritance yields UNKNOWN, never a guess |
| G3 | Resolved nodes retain traceability to their originating layer and lines |

---

## 3. Design

### 3.1 The four mechanisms

| Platform | Mechanism | Nature |
|---|---|---|
| **PAN-OS** | shared → device-group → template stack → local | Multi-layer merge across documents |
| **Juniper** | `groups` + `apply-groups` | Named group expansion within one document |
| **Cisco** | Overlapping `line vty` ranges | Range intersection within one document |
| **FortiOS** | VDOM scoping | Context partitioning within one document |

They differ enough that a single generic algorithm is inappropriate. The design
provides a common **resolution contract** and per-mechanism resolvers.

### 3.2 The resolution contract

```
resolve : ParseTree × ResolutionRules → EffectiveTree

EffectiveNode extends Node {
  origin_layer   : string | ⊥        // "shared", "device-group:DG-Mumbai", "local", ⊥
  origin_lines   : ⟨artifact, first, last⟩
  overridden_by  : EffectiveNode | ⊥
  overrides      : EffectiveNode[]
  resolution     : direct | inherited | merged | overridden | deleted | unresolved
}
```

**INV-02.3-01 — Traceability survives resolution.** Every effective node records
which artifact and lines produced it. An assessor challenged on a finding derived
from an inherited setting must be able to see the layer it came from — and in
PAN-OS deployments the setting frequently does not appear in the device's own
file at all.

**INV-02.3-02 — Unresolvable means unknown.** Where resolution cannot be
completed — a referenced group is absent, a template stack is not supplied — the
affected subtree is marked `unresolved` and every fact derived from it resolves
`default_unknown`. It is never resolved optimistically.

### 3.3 PAN-OS layered merge

The hardest case, and the one most often ignored.

```
effective = merge(shared, device_group_chain, template_stack, local)

precedence  local > template_stack > device_group(nearest) > shared
```

Device groups form a hierarchy; a device may inherit from a chain. Rules merge by
*position semantics* rather than simple override: pre-rules from ancestors
precede local rules, which precede post-rules from ancestors.

```
effective rulebase =
     ancestor pre-rules   (outermost first)
  ++ local rules
  ++ ancestor post-rules  (innermost first)
```

**DD-02.3-01 — Rule order is part of the security semantics.** Access rules are
evaluated first-match. Merging without preserving pre/post ordering produces a
policy that permits or denies different traffic than the device does. Any
resolver that gets ordering wrong produces findings about a policy that does not
exist.

**Missing layers are the common operational case.** An assessor is frequently
supplied only the device-local configuration. Then:

```
⚠ PAN-OS device FW-Mumbai-01 references device-group "DG-India" and
  template stack "TS-Branch", neither of which was supplied.
  Effective configuration cannot be computed.
  → 47 controls resolve UNKNOWN. Coverage capped at 38%.
  → Supply the Panorama configuration to raise coverage.
```

This is honest, actionable, and exactly what G2 requires.

### 3.4 Juniper group expansion

```
groups {
    mgmt-baseline {
        system { services { ssh { protocol-version v2; } } }
    }
}
system {
    apply-groups [ mgmt-baseline ];
    services { telnet; }
}
```

Resolution expands `apply-groups` into the target subtree.

| Rule | Behaviour |
|---|---|
| Multiple groups | Applied in declaration order; later wins on conflict |
| `apply-groups-except` | Suppresses a named group at that subtree |
| Local statement conflicting with a group | Local wins |
| `delete` targeting a group-supplied statement | Applies to the expanded result |
| Wildcard group targets (`<*>`) | Expanded against matching nodes |

**DD-02.3-02.** `delete` is applied *after* expansion, not during structuring
(consistent with TRD-02.1 DD-02.1-02), because a deletion may target something
that only exists by virtue of a group.

### 3.5 Cisco overlapping ranges

```
line vty 0 4
 transport input telnet ssh
 exec-timeout 0 0
line vty 0 15
 transport input ssh
```

Lines 0–4 are defined twice. Resolution produces per-instance effective values:

```
vty[0..4]   transport = {ssh}          ← later stanza wins
            exec_timeout = 0
vty[5..15]  transport = {ssh}
            exec_timeout = ⊥ (platform default)
```

**DD-02.3-03 — Facts from ranged scopes are emitted per range, then aggregated
by the control.** A control asserting *"no VTY line permits Telnet"* must see
every range. Emitting a single collapsed value would hide the case where one
range is compliant and another is not — which is the exact configuration error
worth finding.

Aggregation semantics are declared by the control, not by the resolver:
`any`, `all`, `none` over ranged instances.

### 3.6 FortiOS VDOM scoping

VDOMs partition a device into independent virtual contexts, each with its own
policy, interfaces and administrators.

**DD-02.3-04 — Each VDOM is assessed as a scoped context of one device, not as a
separate device.** The device has one serial and one report (FR-RPT-001), but
facts are VDOM-qualified:

```
vdom[root].mgmt.protocols.telnet.enabled     = false
vdom[customer-a].mgmt.protocols.telnet.enabled = true
```

Controls evaluate per VDOM; the device-level verdict is the aggregate declared by
the control. A device with one non-compliant VDOM is non-compliant.

Global settings apply to all VDOMs unless overridden within one.

### 3.7 Resolution order within a device

```
1  detect mechanism from platform and content
2  expand groups / merge layers
3  apply deletions
4  resolve scope overlaps
5  partition contexts (VDOM), if any
6  mark unresolved subtrees
7  emit effective tree with origin metadata
```

**INV-02.3-03 — Resolution is deterministic and order-independent with respect
to input ordering.** Given the same set of layer documents in any submission
order, the effective tree is identical (D6).

### 3.8 Reporting resolution outcomes

The report must distinguish these, because they mean different things to an
assessor:

| Resolution | Report treatment |
|---|---|
| `direct` | Evidence cites the device's own configuration |
| `inherited` | Evidence cites the originating layer **and states the layer name** |
| `merged` | Evidence cites all contributing layers |
| `overridden` | Evidence cites the winning statement; the overridden one is shown as context |
| `unresolved` | Facts `default_unknown`; coverage reduced; missing layer named |

Evidence for an inherited finding:

```
EVIDENCE   device-group DG-India, panorama-config.xml, lines 4821–4823
           (inherited — not present in FW-Mumbai-01's local configuration)

  4821 │ <service>
  4822 │   <disable-telnet>no</disable-telnet>      ← inherited setting
  4823 │ </service>
```

**Without the parenthetical, an administrator will look in the device's own
configuration, fail to find the line, and conclude the tool is wrong.**

---

## 4. Interfaces

**Input**

```
ResolutionRequest {
  primary_tree: ParseTree
  supporting_trees[]: ⟨role, ParseTree⟩   // panorama, template, group source
  rules: ResolutionRules                   // from the rulepack
}
```

**Output**

```
EffectiveTree {
  root: EffectiveNode
  unresolved[]: ⟨path, reason, missing_layer⟩
  layers_used[]: ⟨name, artifact⟩
  layers_missing[]: ⟨name, referenced_from⟩
  scoped_contexts[]: ⟨kind, name⟩          // VDOMs, virtual routers
  status: resolved | partially_resolved | unresolvable
}
```

---

## 5. Edge cases

| Case | Handling |
|---|---|
| Circular `apply-groups` reference | Cycle detected; subtree marked `unresolved`; error recorded |
| Group referenced but not defined | `unresolved`; missing layer named |
| Device group hierarchy supplied out of order | Ordering derived from declared parentage, not submission order (INV-02.3-03) |
| Template stack containing conflicting templates | Precedence by stack position; conflict recorded |
| `delete` targeting something that does not exist | No-op; recorded as an anomaly, not an error |
| VDOM inheriting a global setting that is later overridden globally | Re-resolved per VDOM |
| Overlapping ranges with identical bounds declared twice | Later declaration wins; both retained in evidence |
| Nested VDOM-like constructs (VRF inside VDOM) | Contexts compose; facts carry the full context path |
| Panorama config supplied for a device not present in it | Layers marked missing; device resolves local-only with a warning |

---

## 6. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Merge precedence implemented incorrectly | Differential testing against device-reported effective config | **Silently wrong facts** — the most dangerous outcome. Mitigated by V-02.3-002 |
| Rule ordering lost in PAN-OS merge | Policy simulation differs from device behaviour | Wrong access-control findings; V-02.3-003 |
| Missing layer treated as absent rather than unknown | Coverage anomaly | **G2 violation.** INV-02.3-02 prevents |
| Cycle in group references | Cycle detection | Subtree unresolved |
| Range collapse hiding a non-compliant range | Control aggregation semantics | DD-02.3-03 prevents by emitting per-range |
| VDOM facts merged into device-level facts | Fact path inspection | Non-compliant VDOM masked; V-02.3-005 |

---

## 7. Verification

```
V-02.3-001   Inherited facts record their originating layer
  Requirement  FR-PRS-010, INV-02.3-01
  Method       CORPUS
  Procedure    For every corpus artifact with inheritance, assert every
               effective node with resolution ∈ {inherited, merged} carries
               origin_layer and origin_lines resolving to real text.
  Acceptance   100%. Zero inherited nodes without a named layer.
  Severity     BLOCKING
```

```
V-02.3-002   Resolved configuration matches device-reported effective config
  Requirement  FR-PRS-009
  Method       DIFFERENTIAL
  Procedure    For lab devices supporting an effective-configuration command
               (Juniper `display inheritance`, PAN-OS effective running config),
               compare the resolver's output against the device's own.
  Acceptance   ≥ 99% semantic agreement on security-relevant statements.
               Every disagreement investigated and classified.
  Severity     BLOCKING
  Note         This is the only way to prove the resolver is correct rather
               than merely self-consistent.
```

```
V-02.3-003   PAN-OS rule ordering is preserved through merge
  Requirement  DD-02.3-01
  Method       UNIT + DIFFERENTIAL
  Procedure    Device group with pre-rules and post-rules plus local rules.
               Compare merged rule order against the device's evaluation order.
  Acceptance   Exact order match: ancestor pre-rules, local, ancestor
               post-rules innermost-first.
  Severity     BLOCKING
```

```
V-02.3-004   Missing layers yield UNKNOWN, never local-only resolution
  Requirement  INV-02.3-02, G2
  Method       INTEGRATION
  Procedure    Supply a PAN-OS device configuration referencing a device group
               and template stack, without supplying the Panorama configuration.
  Acceptance   status = partially_resolved. Affected facts default_unknown.
               Dependent controls UNKNOWN. Report names the missing layers.
               Zero PASS verdicts on affected controls.
  Severity     BLOCKING
```

```
V-02.3-005   Overlapping ranges are emitted per instance
  Requirement  DD-02.3-03
  Method       UNIT
  Procedure    Cisco config with `line vty 0 4` permitting Telnet and
               `line vty 5 15` permitting SSH only.
  Acceptance   Facts emitted for both ranges. A control asserting
               "no VTY permits Telnet" returns FAIL. Zero collapse to a
               single value.
  Severity     BLOCKING
```

```
V-02.3-006   VDOM facts remain context-qualified
  Requirement  DD-02.3-04
  Method       UNIT + CORPUS
  Procedure    FortiOS config with a compliant root VDOM and a
               non-compliant customer VDOM.
  Acceptance   Facts VDOM-qualified. Device verdict FAIL. Report identifies
               the offending VDOM. Zero masking by aggregation.
  Severity     BLOCKING
```

```
V-02.3-007   Juniper group expansion and deletion ordering
  Requirement  DD-02.3-02
  Method       UNIT
  Procedure    Config where `apply-groups` supplies a statement that a local
               `delete` then removes.
  Acceptance   Statement absent from the effective tree. Resolution recorded
               as `deleted` with both origins retained in evidence.
  Severity     MAJOR
```

```
V-02.3-008   Circular references are detected
  Requirement  §5
  Method       UNIT
  Procedure    Juniper config with groups A→B→A.
  Acceptance   Cycle detected. Subtree unresolved. Error recorded. No
               infinite loop, no stack exhaustion.
  Severity     BLOCKING
```

```
V-02.3-009   Resolution is independent of layer submission order
  Requirement  INV-02.3-03, D6
  Method       PROPERTY
  Procedure    Submit multi-layer PAN-OS artifact sets in 20 random orderings.
  Acceptance   Byte-identical effective trees in all orderings.
  Severity     BLOCKING
```

```
V-02.3-010   Inherited evidence is comprehensible to an administrator
  Requirement  §3.8
  Method       MANUAL
  Procedure    Present three inherited findings to a network administrator
               unfamiliar with the tool. Ask where the setting is defined.
  Acceptance   All three located correctly without assistance. Evidence
               states the layer name and that it is not in the local config.
  Severity     MAJOR
```

---

## 8. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should a device with unresolvable layers be assessed at all, or held like a correlation failure? | Holding is safest but discards the substantial local-only coverage that is genuinely determinable. Current design: assess with affected facts unknown and coverage capped |
| Q2 | Should each VDOM produce its own PDF section, or be interleaved by control? | Per-VDOM sections are clearer for multi-tenant devices but lengthen the report. Current design: interleaved with VDOM qualification, per-VDOM summary table on the cover |
| Q3 | Should the resolver attempt partial merge when only some device-group ancestors are supplied? | Partial merge risks a wrong effective policy; refusing loses coverage. Current design: partial merge permitted only where the missing ancestor contributes no security-relevant statements, which is itself unknowable — therefore refuse |
