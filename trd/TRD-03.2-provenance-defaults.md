# TRD-03.2 · Provenance and Defaults Resolution

---

## 1. Scope

The mechanism by which **absence** is interpreted: version-keyed defaults
resolution, fleet-based capability inference, provenance classification, derived
fact computation, and uncertainty propagation.

> This is the subsystem that enforces **G2 — never over-claim**. Everything else
> in the product can be correct and the product still dangerous if this is wrong.

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-EXT-003 | Six provenance source classifications |
| FR-EXT-004 | Version-keyed defaults resolution |
| FR-EXT-005 | No value assigned where no default is known |
| FR-EXT-006 | Fleet-based capability inference |
| G2 | Silence never becomes compliance |

---

## 3. The absence problem

If `service password-encryption` is absent from a Cisco configuration, it is
**off**. If `ip ssh version 2` is absent, some releases accept version 1.

**You cannot search only for bad patterns.** You must know the default for every
setting, on every platform, at every firmware version, and reason about what is
*not written*.

For an untaught platform there is no defaults table, and silence has three
possible meanings with identical evidence and opposite security consequences:

| Silence might mean | Security meaning |
|---|---|
| Feature exists, at its default, and the export omits defaults | Depends entirely on the default |
| Feature exists but was never configured | Probably off, probably bad |
| Feature does not exist on this platform | Not applicable — no finding |

The design resolves this by **never collapsing the three cases into a value**.

---

## 4. Design

### 4.1 Provenance classification — the decision procedure

```
classify(fact_path, extraction_result, platform, version, fleet) →

  if fact emitted by an extractor                   → explicit
  if node resolution == unresolved (TRD-02.3)       → default_unknown
  if extractor conflict (TRD-03.1 §3.6)             → default_unknown
  if platform declares fact not_applicable          → not_applicable
  if defaults table has an entry for (path, version)
        and the version resolves unambiguously      → default_known
  if fleet shows the concept exists on this platform
        but this device is silent                   → default_inferred
  otherwise                                         → default_unknown
```

**INV-03.2-01 — The default branch is `default_unknown`.** Every path that does
not positively establish a value ends here. New code paths inherit safety by
construction rather than by remembering to add a guard.

| Source | Value assigned | Trust | Effect on controls |
|---|---|---|---|
| `explicit` | From configuration | Full | Normal evaluation |
| `default_known` | From the defaults table | Full | Normal evaluation |
| `default_inferred` | ⊥ (concept known to exist, value unknown) | Partial | UNKNOWN in strict mode; UNKNOWN in standard mode too, until a documented default arrives |
| `inherited` | From a parent layer | Full | Normal; layer cited in evidence |
| `default_unknown` | **⊥ — none assigned** | None | **Forces UNKNOWN** |
| `not_applicable` | ⊥ | — | Control returns NOT_APPLICABLE |

**DD-03.2-01 — `default_inferred` does not assign a value.** It records that the
*concept exists* on the platform, which is genuinely useful information (it
distinguishes "this platform has SSH ciphers and this device didn't configure
them" from "this platform has no such concept"), but it does not guess what the
default *is*. It therefore still yields UNKNOWN.

Its value is that it converts an unknown-unknown into a known-unknown: the
report can say *"this device is at the platform default for SSH ciphers, and we
do not know what that default is"* rather than saying nothing.

### 4.2 The defaults table

```yaml
defaults:
  mgmt.protocols.http.enabled:
    - { version_range: "<15.0",  value: true,
        source: "CIS Cisco IOS Benchmark v4.1.0, Default Value" }
    - { version_range: ">=15.0", value: false,
        source: "CIS Cisco IOS Benchmark v4.1.0, Default Value" }

  mgmt.session.idle_timeout_sec:
    - { version_range: "*", value: 600,
        source: "Cisco IOS Configuration Guide 15.2" }

  mgmt.protocols.ssh.version:
    - { version_range: ">=12.3", value: 2,
        condition: "crypto.host_key_present == true",
        source: "Cisco IOS Security Configuration Guide" }
```

**INV-03.2-02 — Every default cites its source.** An assessor challenged on a
finding derived from a default rather than an explicit line must be able to say
where the default came from. A default without a citation is an assertion.

**Conditional defaults.** Where a default depends on other configuration
(`ssh.version` depends on whether a host key exists), the condition is evaluated
against already-resolved facts. If the condition itself cannot be evaluated, the
result is `default_unknown` — conditions do not resolve optimistically.

**Version ambiguity.** If version precision is major.minor only (TRD-01.2
INV-01.2-01) and the table has distinct values within that range:

```
version = 16.12  (precision: major_minor)
table has:  16.12.01–16.12.03 → false
            16.12.04+          → true
→ ambiguous → default_unknown
```

**Precision loss becomes coverage loss, never a guess.**

### 4.3 Bootstrapping defaults from benchmarks

CIS Benchmarks document default values explicitly — every recommendation has a
*Default Value* section. Importing a benchmark (TRD-05.3) therefore also
populates the defaults table, directly reducing `default_unknown` and raising
coverage.

This is a meaningful practical shortcut: benchmark import improves *both* the
control library and the extraction quality, from one source.

### 4.4 Fleet-based capability inference

FR-EXT-006. Where no documented default exists, the estate itself is evidence.

```
infer_capability(platform, fact_path, fleet) →
  devices = all assessed devices of this platform
  expressing = devices where fact_path has source == explicit

  if |expressing| ≥ 1:
      concept_exists = true
      for silent devices → default_inferred
  else:
      concept_exists = unknown
      for all devices → default_unknown
```

If forty RouterOS devices exist and thirty-nine never mention SSH ciphers while
one does, that single device establishes three things:

1. **The concept exists on this platform** — proof by existence
2. **The syntax is known** — obtained without asking anyone
3. **The other thirty-nine are at default** — they could have expressed it and
   did not

**DD-03.2-02 — Threshold of one.** A single expressing device is sufficient to
establish existence, because existence is not a statistical claim — one
counterexample to "this platform has no such concept" settles it.

**The union of every setting observed across N devices of a platform approximates
that platform's configurable surface**, and it improves passively as more
configurations are ingested.

**Limitation, stated:** inference operates within a campaign's assessed devices
plus the historical corpus for that platform. It cannot establish existence for a
platform seen only once.

### 4.5 Derived facts

Computed in a pass after extraction (TRD-03.1 DD-03.1-01), so that extraction
remains order-independent.

```yaml
derived:
  - fact: auth.local_users[].reversible
    depends_on: [auth.local_users[].storage_type]
    compute: "storage_type in ['plaintext', 'reversible']"

  - fact: crypto.weak_algorithms_present
    depends_on: [crypto.ssh.ciphers, crypto.ssh.macs, crypto.ssh.kex_algorithms]
    compute: "intersect(concat(ciphers, macs, kex), lookup('weak_algorithms'))"

  - fact: filter.objects[].expanded
    depends_on: [filter.objects]
    compute: "transitive_expand(members, filter.objects)"

  - fact: snmp.communities[].is_default
    depends_on: [snmp.communities[].name]
    compute: "name in lookup('default_community_names')"
```

**INV-03.2-03 — Uncertainty propagates. A derived fact inherits the weakest
provenance among its inputs.**

```
weakest(sources) : ordering
  explicit ≈ default_known ≈ inherited   >  default_inferred  >  default_unknown

if any input is default_unknown  → derived fact is default_unknown
if any input is default_inferred → derived fact is default_inferred
```

This prevents the most insidious failure in any inference pipeline: an uncertain
input silently becoming a confident output three transformations later.

**Worked example.**

```
crypto.ssh.ciphers      source: default_unknown     (no default documented)
crypto.ssh.macs         source: explicit            (configured, line 88)
        ↓ derived
crypto.weak_algorithms_present
        source: default_unknown          ← weakest wins
        value:  ⊥
        ↓
NSCA-CRYPTO-007 → UNKNOWN, not PASS
```

Without INV-03.2-03, the derived fact would report "no weak algorithms found"
based on half the input — a confident, wrong, dangerous PASS.

**Dependency cycles** are rejected at rulepack load, not at runtime.

### 4.6 Transitive expansion

`filter.objects[].expanded` deserves specific mention because it catches one of
the most common real-world defects: a group named `Trusted-Admins` that
transitively contains `0.0.0.0/0` three nestings down. Nobody notices manually,
because noticing requires following references.

```
transitive_expand(group, all_objects, seen = ∅) →
  if group ∈ seen: record cycle; return ∅        # cycles exist in real configs
  seen ∪= { group }
  result = ∅
  for m in group.members:
      result ∪= (m is a group) ? transitive_expand(m, all_objects, seen)
                               : { m }
  return result
```

An unresolvable member reference makes the expansion `default_unknown` — a
partially expanded group would understate its true membership, producing a PASS
where a FAIL is warranted.

### 4.7 Coverage accounting

```
producible(platform)   = schema facts the platform's rulepack can produce
determined             = facts with source ∈ { explicit, default_known, inherited }
undetermined           = facts with source ∈ { default_inferred, default_unknown }

fact_coverage = |determined| / |producible|
```

Fact coverage feeds control coverage (TRD-05.2) but is reported separately,
because it distinguishes *"we could not read the device"* from *"we read it but
have no control for this"*.

---

## 5. Interfaces

**Input:** `⟨facts[] from TRD-03.1, platform, os_version, version_precision,
defaults_table, fleet_index, derived_rules⟩`

**Output**

```
ResolvedFactSet {
  facts[]: Fact                      // provenance fully classified
  by_source: map<source, int>
  fact_coverage: ratio
  unresolved_reasons[]: ⟨fact_path, reason, remedy⟩
  capability_inferences[]: ⟨fact_path, expressing_devices, total_devices⟩
}
```

`unresolved_reasons[]` drives the report's Unassessed section (PRD 10 §2.6) and
must carry an actionable remedy where one exists:

```
crypto.ssh.ciphers    default_unknown
  reason: no documented default for cisco_iosxe 16.12
  remedy: configure explicitly, or supply vendor documentation for import
```

---

## 6. Edge cases

| Case | Handling |
|---|---|
| Defaults table entry whose condition cannot be evaluated | `default_unknown` — conditions do not resolve optimistically |
| Fact explicit on one VDOM, silent on another | Per-context classification; the silent context resolves independently |
| Terse export where a value *is* present | `explicit` wins regardless of export mode |
| Verbose export where a value is absent | Genuinely absent; `default_known` applies if a default exists |
| Platform declares a fact `not_applicable` but an extractor emits it | Extractor wins; the declaration is flagged as a rulepack defect |
| Fleet inference from a single device of a platform | Existence established; no statistical claim made |
| Derived fact whose inputs are all `not_applicable` | Derived fact is `not_applicable` |
| Cycle in object group membership | Recorded; expansion terminates; expansion marked partial → `default_unknown` |

**The terse-export interaction is important.** Export mode affects what is
*absent*, never what is *present*. An explicitly configured value in a terse
export is fully trustworthy. Only silence is affected — and TRD-01.1 DD-01.1-03
already treats unknown export mode as terse, so silence in a terse export
resolves conservatively.

---

## 7. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Wrong default value in the table | Differential testing against device-reported effective config | **Silently wrong fact.** Mitigated by source citation (INV-03.2-02) and differential testing |
| Default applied outside its correct version range | Version-range unit tests | Wrong fact on specific releases |
| Uncertainty laundered through a derived fact | V-03.2-005 | **G2 violation** — the most consequential failure in this TRD |
| Absence treated as `false` | V-03.2-001 | G2 violation; silently passes every device omitting the setting |
| Fleet inference on an unrepresentative fleet | Inference count reported | Conservative: still yields UNKNOWN |
| Partial group expansion treated as complete | V-03.2-007 | Understates group membership → false PASS |

---

## 8. Verification

```
V-03.2-001   Absence never becomes false
  Requirement  FR-EXT-005, INV-03.2-01, G2
  Method       PROPERTY + CORPUS
  Procedure    For every boolean fact path and every corpus device where the
               fact is absent and no default exists, inspect the resolved fact.
  Acceptance   source == default_unknown, value == ⊥, in 100% of cases.
               Zero instances of value == false with source default_unknown.
  Severity     BLOCKING
  Note         The single most important verification in the product.
```

```
V-03.2-002   default_unknown forces UNKNOWN downstream
  Requirement  FR-CTL-005, G2
  Method       INTEGRATION
  Procedure    For each control, construct a fact set where one required fact
               is default_unknown.
  Acceptance   Verdict UNKNOWN for 100% of controls. Zero PASS.
  Severity     BLOCKING
```

```
V-03.2-003   Defaults are version-correct
  Requirement  FR-EXT-004
  Method       UNIT + DIFFERENTIAL
  Procedure    For each defaults entry with multiple version ranges, resolve
               at versions inside and outside each range. Where lab devices
               exist, compare against device-reported effective values.
  Acceptance   100% correct range selection. ≥ 99% agreement with device
               behaviour where comparable.
  Severity     BLOCKING
```

```
V-03.2-004   Version ambiguity yields unknown
  Requirement  INV-01.2-01
  Method       UNIT
  Procedure    Resolve a fact at major.minor precision where the table has
               distinct values within that range.
  Acceptance   default_unknown. Zero instances of selecting either value.
  Severity     BLOCKING
```

```
V-03.2-005   Uncertainty propagates through derived facts
  Requirement  INV-03.2-03, G2
  Method       PROPERTY + CORPUS
  Procedure    For every derived fact, construct input sets where one input
               is default_unknown and others are explicit.
  Acceptance   Derived fact is default_unknown in 100% of cases.
               Zero derived facts with stronger provenance than their
               weakest input.
  Severity     BLOCKING
```

```
V-03.2-006   Every default cites a source
  Requirement  INV-03.2-02
  Method       UNIT (rulepack load gate)
  Procedure    Load every shipped rulepack; inspect every defaults entry.
  Acceptance   100% carry a non-empty source citation. A rulepack with an
               uncited default is rejected at load.
  Severity     MAJOR
```

```
V-03.2-007   Partial group expansion resolves to unknown
  Requirement  §4.6
  Method       UNIT
  Procedure    Object group referencing an undefined member; and a group
               containing a membership cycle.
  Acceptance   expanded fact is default_unknown in both cases. Zero partial
               expansions presented as complete. Cycle terminates.
  Severity     BLOCKING
```

```
V-03.2-008   Fleet inference establishes existence, not value
  Requirement  FR-EXT-006, DD-03.2-02
  Method       INTEGRATION
  Procedure    Fleet of 40 platform devices; 1 expresses a fact explicitly.
  Acceptance   The 39 resolve default_inferred, value ⊥. Dependent controls
               UNKNOWN. capability_inferences reports 1/40.
  Severity     MAJOR
```

```
V-03.2-009   Conditional defaults do not resolve optimistically
  Requirement  §4.2
  Method       UNIT
  Procedure    Resolve a conditional default where the condition's own
               fact is default_unknown.
  Acceptance   default_unknown. Zero instances of the condition being
               assumed true or false.
  Severity     BLOCKING
```

```
V-03.2-010   Explicit values are unaffected by export mode
  Requirement  §6
  Method       UNIT
  Procedure    Resolve an explicitly configured fact in both a terse and a
               verbose export of the same device.
  Acceptance   Identical: source explicit, identical value, in both cases.
  Severity     MAJOR
```

```
V-03.2-011   Unresolved reasons carry actionable remedies
  Requirement  §5, PRD 10 §2.6
  Method       CORPUS
  Procedure    Assess the full corpus; inspect every unresolved_reason.
  Acceptance   ≥ 90% carry a remedy. 100% carry a reason. Reasons are drawn
               from a closed set, not free text.
  Severity     MINOR
```

```
V-03.2-012   Derived-fact dependency cycles are rejected at load
  Requirement  §4.5
  Method       UNIT
  Procedure    Load a rulepack with derived facts A→B→A.
  Acceptance   Rejected at load with a specific error. No runtime cycle.
  Severity     MAJOR
```

---

## 9. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should `default_inferred` ever assign a value if the majority of a large fleet is consistent? | Would raise coverage materially, but a fleet majority is evidence about *this organisation's practice*, not about the platform's default — and inferring a vendor default from customer practice is unsound. Current design: never assigns a value |
| Q2 | Should a strict mode treat `default_known` as UNKNOWN, requiring explicit configuration? | Some audit regimes require explicit configuration of security settings regardless of the default. Current design: standard mode trusts documented defaults; strict mode is a plausible future option and would be a per-campaign flag |
| Q3 | Should fleet inference span campaigns and organisations (via shared rulepack telemetry)? | Would sharply improve capability surface knowledge, but sharing fleet observations is a data-governance question incompatible with air-gapped deployment. Current design: local fleet and local historical corpus only |
