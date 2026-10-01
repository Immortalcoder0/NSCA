# TRD-03.3 · Schema Registry

---

## 1. Scope

The runtime-extensible registry defining every fact path, its type, category and
security properties. The mechanism by which a platform introducing a genuinely
new concept can be represented **without a code change or redeployment**.

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-EXT-010 | Extensible fact paths |
| NFR-MNT-003 | New schema facts require no code change |
| FR-LRN-026 | Newly registered facts with no controls become unaudited surface |
| FR-CTL-014 | Property metadata drives property-derived controls |

---

## 3. Design

### 3.1 Three things get learned, not one

Most implementations treat "learning a new vendor" as learning to parse it. The
problem statement asks for more:

> *"support new vendors, **standards**, and OS versions"*

Three layers must be extensible:

| Layer | Learned when | Owner |
|---|---|---|
| **Extraction rules** | A platform's syntax is unfamiliar | TRD-08.3 |
| **Schema fields** | A platform introduces a concept the schema lacks | **This TRD** |
| **Controls** | A concept has no requirement attached | TRD-05.3, TRD-08.2 |

Omitting the middle layer means a genuinely novel capability — a proprietary
management protocol, a container runtime, a programmable data plane — cannot be
represented at all, and therefore silently disappears from the audit.

### 3.2 Fact definition

```yaml
fact_definition:
  path:        mgmt.protocols.winbox.enabled
  type:        boolean
  category:    management_plane
  description: "Proprietary MikroTik management protocol (TCP/8291)"

  properties:                       # universal security properties
    listens:       true
    authenticates: true
    executes:      false
    mutates:       true
    transports:    true
    persists:      false
    default_on:    true

  registered_by:          r.kulkarni
  registered_at:          2026-09-14T10:31:00Z
  introduced_by_platform: mikrotik_routeros
  ratified_by:            p.sharma
  status:                 ratified
  schema_version:         1.8.0
```

**INV-03.3-01 — No unregistered fact may be emitted.** An extractor emitting an
unregistered path is rejected at rulepack load (TRD-03.1 V-03.1-009). Registration
is explicit, attributed and ratified — the schema cannot grow by accident.

### 3.3 Type system

| Type | Notes |
|---|---|
| `boolean` | Positive assertion only (PRD 05 §8) |
| `integer` | With optional declared unit — durations always seconds |
| `string` | With optional declared pattern |
| `enum` | Closed (TLS versions) or open-with-registry (management protocols) |
| `cidr` | Normalised; wildcard masks converted |
| `version` | Structured, comparable |
| `algorithm` | Canonical identifier from the equivalence table |
| `ref` | Reference to another object |
| `list<T>` | Ordered; ordering is source order (TRD-03.1 INV-03.1-03) |
| `object` | Declared field set |

**Algorithm canonicalisation is registry-owned.** `aes128-cbc`, `AES-128-CBC` and
`aes-128-cbc` are one algorithm. The equivalence table lives here so that control
assertions compare canonical identifiers rather than performing per-platform
string matching — which would defeat the purpose of a vendor-neutral schema.

### 3.4 Open versus closed enumerations

```yaml
# closed — the domain is fixed by a standard
crypto.tls.versions:
  type: enum
  closed: true
  values: [ssl3, tls1.0, tls1.1, tls1.2, tls1.3]

# open — vendors invent new members
mgmt.protocols.<name>:
  type: enum
  closed: false
  registry: management_protocols
  known: [telnet, ssh, http, https, ftp, tftp, snmp, netconf, restconf, api]
```

**DD-03.3-01.** Open enumerations are where novel capabilities enter the schema.
A new member is registered with its properties, becomes immediately visible to
property-derived controls (TRD-05.1), and — if no control references it —
triggers unaudited-surface reporting.

### 3.5 Registration workflow

```
1  DISCOVER    training proposes a fact path with no registry entry
2  PROPOSE     path, type, category, description, properties
                 properties inferred where possible; confirmed by the operator
3  VALIDATE    naming conventions, no collision, no vendor terminology
4  REGISTER    status: provisional
5  RATIFY      second user (two-person rule)
6  ACTIVE      usable in issued reports
```

**INV-03.3-02 — Facts from provisional registrations are excluded from issued
reports**, consistent with provisional rulepacks (PRD 11 §8).

### 3.6 Naming validation

Automated gates at registration:

| Gate | Rule |
|---|---|
| **No vendor terminology** | Path segments checked against a vendor-term denylist (`vty`, `transport_input`, `admintimeout`). Rejection message explains why |
| **Category prefix** | Path must begin with a registered top-level domain |
| **Duplication** | Lexical and semantic similarity check against existing paths, with suggestions |
| **Depth** | ≤ 5 segments |
| **Casing** | `snake_case`; collections suffixed `[]` |

**The vendor-terminology gate is the one that preserves the architecture.**
A fact named `mgmt.vty.transport_input` looks harmless and quietly makes every
control referencing it Cisco-specific — collapsing the vendor-neutral design one
registration at a time.

```
✗ Rejected: mgmt.vty.transport_input
  "vty" and "transport_input" are Cisco terminology.
  Facts must be semantic. Consider: mgmt.protocols.<protocol>.enabled
```

### 3.7 Property inference

Property values (§3.2) drive property-derived controls. Inferred where possible,
confirmed by the operator.

| Property | Inference signal |
|---|---|
| `listens` | Sibling fact of type port; the word "port" in the source construct |
| `authenticates` | Sibling credential-shaped attribute (`password`, `secret`, `key`, `community`) |
| `executes` | Tokens: `script`, `container`, `image`, `exec`, `run`, `plugin` |
| `mutates` | Category is management or configuration |
| `transports` | Sibling remote endpoint (`host`, `server`, `url`, `registry`) |
| `persists` | Tokens: `store`, `save`, `database`, `cache` |
| `default_on` | The defaults table, once populated |

**Operator confirmation is eight yes/no questions**, not authoring a control.
Anyone who administers the platform can answer them.

### 3.8 Unaudited surface detection

```
unaudited(device) →
  { f ∈ device.facts :
        f.definition.category ≠ informational
    and no loaded control references f.path }
```

Produces two effects (PRD 09 §2.2):

1. A finding: *"capability present, outside the scope of all selected
   frameworks, not assessed"*
2. **Scope contamination** of every passing control in the same family

**DD-03.3-02.** Contamination is driven by the fact's `category`, which is why
category is a required registration field rather than documentation. A capability
registered with the wrong category contaminates the wrong control family — or
none.

### 3.9 Versioning

The registry is versioned and campaign-pinned. A historical campaign is
reproduced against the schema as it existed then, not as it exists now.

| Change | Version impact | Compatibility |
|---|---|---|
| New fact path | Minor | Backward compatible |
| New enum member (open) | Patch | Backward compatible |
| New optional object field | Minor | Backward compatible |
| Type change | **Major** | Breaking — requires migration |
| Path rename | **Major** | Breaking — requires an alias |
| Deprecation | Minor | Alias retained for two major versions |

**INV-03.3-03 — Breaking registry changes invalidate reproducibility of prior
campaigns unless an alias is retained.** Aliases are therefore mandatory for
renames, and type changes require an explicit migration recorded in the campaign
history.

---

## 4. Interfaces

```
resolve(path)            → FactDefinition | ⊥
validate(path, value)    → ok | type_error
register(proposal)       → provisional entry
ratify(path, user)       → active entry
properties(path)         → property set
canonicalise(algo)       → canonical identifier
unaudited(fact_paths, loaded_controls) → unaudited fact paths
```

---

## 5. Edge cases

| Case | Handling |
|---|---|
| Two platforms introduce the same concept under different names | Similarity check at registration proposes the existing path; operator confirms |
| A registered fact is never produced by any rulepack | Retained; reported as unused in registry health |
| A control references a fact path that is later deprecated | Alias resolves; deprecation warning raised against the control |
| A platform expresses a concept that maps to *two* existing facts | Registration rejected; the extractor should emit both |
| Algorithm name not in the equivalence table | Registered as an unrecognised algorithm; treated as unknown strength, never as strong |
| Registration proposed during assessment | Queued; does not mutate the schema mid-campaign (D6) |

**The unrecognised-algorithm case matters.** Treating an unknown cipher as strong
produces a false PASS; treating it as weak produces a false FAIL. The correct
answer is unknown strength → UNKNOWN, consistent with G2.

---

## 6. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Vendor terminology enters a fact path | Naming gate | Controls silently become platform-specific |
| Duplicate concept registered under two paths | Similarity check | Controls reference one; the other becomes unaudited surface — visible, but noisy |
| Wrong category registered | Manual review | Contamination targets the wrong family |
| Wrong properties registered | Operator confirmation | Property-derived controls mis-fire or fail to fire |
| Breaking change without alias | Reproducibility verification (TRD-10.1) | Historical campaigns unreproducible |
| Schema mutated mid-campaign | Queueing (§5) | Determinism violation |

---

## 7. Verification

```
V-03.3-001   Unregistered fact paths are rejected
  Requirement  INV-03.3-01
  Method       UNIT
  Procedure    Load a rulepack emitting an unregistered path.
  Acceptance   Rejected at load, naming the offending path. Zero facts
               produced from unregistered paths at runtime.
  Severity     BLOCKING
```

```
V-03.3-002   Vendor terminology is rejected at registration
  Requirement  §3.6, PRD 05 SBM-1
  Method       UNIT
  Procedure    Attempt registration of 20 vendor-specific paths spanning
               five platforms (vty, admintimeout, transport_input,
               apply-groups, winbox-as-category …).
  Acceptance   All rejected with an explanatory message and a suggested
               semantic alternative.
  Severity     BLOCKING
  Note         This gate is what keeps controls portable over time.
```

```
V-03.3-003   A new platform concept is registrable without code change
  Requirement  NFR-MNT-003, FR-EXT-010
  Method       INTEGRATION
  Procedure    Using only the running system, register a novel fact path
               with properties, teach an extractor producing it, and assess.
  Acceptance   Completed with no source modification, no restart, no
               redeployment. Fact appears with correct provenance.
  Severity     BLOCKING
```

```
V-03.3-004   Unaudited surface is detected and contaminates its family
  Requirement  FR-LRN-026, DD-03.3-02, PRD 09 §2.2
  Method       INTEGRATION
  Procedure    Register a management-plane capability with no referencing
               control. Assess a device exposing it.
  Acceptance   Unaudited-surface finding produced. All passing
               management-plane controls downgraded to PASS (PARTIAL) with
               the reason attached.
  Severity     BLOCKING
```

```
V-03.3-005   Algorithm canonicalisation is complete and consistent
  Requirement  §3.3
  Method       PROPERTY + CORPUS
  Procedure    Canonicalise every algorithm string appearing in the corpus.
  Acceptance   Equivalent spellings map to one identifier. Unrecognised
               algorithms are flagged, never silently mapped or assumed strong.
  Severity     BLOCKING
```

```
V-03.3-006   Unrecognised algorithms yield unknown, not strong
  Requirement  §5, G2
  Method       UNIT
  Procedure    Configuration specifying a cipher absent from the equivalence
               table.
  Acceptance   crypto.weak_algorithms_present resolves default_unknown.
               Dependent controls UNKNOWN. Zero PASS.
  Severity     BLOCKING
```

```
V-03.3-007   Provisional registrations are excluded from issued reports
  Requirement  INV-03.3-02
  Method       INTEGRATION
  Procedure    Register a fact provisionally; produce facts and findings;
               issue a report.
  Acceptance   Findings derived from provisional registrations flagged in
               draft and absent from the issued report.
  Severity     BLOCKING
```

```
V-03.3-008   Duplicate concept detection
  Requirement  §3.6
  Method       UNIT
  Procedure    Attempt to register mgmt.protocols.ssh_service.enabled when
               mgmt.protocols.ssh.enabled exists.
  Acceptance   Flagged as a probable duplicate with the existing path
               suggested. Registration requires explicit override.
  Severity     MAJOR
```

```
V-03.3-009   Registry versioning preserves reproducibility
  Requirement  INV-03.3-03
  Method       INTEGRATION
  Procedure    Assess a campaign at registry v1.8.0. Register new facts and
               deprecate one with an alias, reaching v1.9.0. Re-execute the
               historical campaign.
  Acceptance   Byte-identical results, evaluated against v1.8.0.
  Severity     BLOCKING
```

```
V-03.3-010   Schema is not mutated mid-campaign
  Requirement  §5, D6
  Method       INTEGRATION
  Procedure    Submit a registration while an assessment is running.
  Acceptance   Queued. The running assessment uses the pinned registry
               version throughout. Results identical to a run without the
               concurrent registration.
  Severity     BLOCKING
```

```
V-03.3-011   Property inference proposals are reasonable
  Requirement  §3.7
  Method       CORPUS
  Procedure    Infer properties for 30 known capabilities across platforms,
               compare against expert-labelled ground truth.
  Acceptance   ≥ 80% of individual property values correct before operator
               confirmation. `listens` and `authenticates` ≥ 90%.
  Severity     MINOR
```

---

## 8. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should the registry be shareable between deployments alongside rulepacks? | Sharing prevents divergent naming for the same concept across organisations, but a shared registry becomes a coordination dependency incompatible with air-gapped autonomy. Current design: local registry; exported rulepacks carry their registry additions and are reconciled on import |
| Q2 | Should the vendor-term denylist be maintained as content, updated with rulepacks? | Content updates keep it current as new vendors appear, but a denylist shipped as content could be weakened by an import. Current design: shipped with the engine, extended locally with attribution |
| Q3 | How should a fact that is genuinely two concepts on different platforms be handled? | Splitting the path breaks existing controls; keeping it conflates semantics. Current design: split with aliases and an explicit migration, treated as a major registry change |
