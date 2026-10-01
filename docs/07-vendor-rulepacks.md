# 07 · Vendor Rulepacks

> The *reading* side of the architecture. A rulepack is everything the platform
> needs in order to convert one vendor's configuration dialect into the Security
> Baseline Model.

---

## 1. The unifying principle

There is **no separate mechanism** for platforms shipped with the product and
platforms taught by a customer.

The learning subsystem ([08](08-learning-system.md)) is the **authoring tool for
every rulepack**, including the ones that ship in the box. The Cisco IOS rulepack
is built the same way an administrator builds a MikroTik one: feed in fifty real
configurations, let the system mine templates, confirm the mappings.

Three consequences:

- The training interface is battle-tested by the product team before any customer
  touches it
- Shipped and taught rulepacks are the same kind of object, so they version,
  diff, sign, export and roll back identically
- There is no second codebase to maintain

The difference between "known" and "unknown" is therefore not architectural. It
is **maturity** — how much validation sits behind a rulepack — which is captured
explicitly as a trust tier (§8).

---

## 2. Anatomy of a rulepack

Six components.

```
rulepack: cisco_ios
version:  7.2.1
├── 1  fingerprint signatures      how to recognise this platform
├── 2  structural grammar          how to turn text into a tree
├── 3  extractors                  how to turn the tree into facts   (the bulk)
├── 4  defaults table              what absence means, per version
├── 5  inheritance rules           how to compute the effective config
└── 6  platform quirks             the unglamorous reality
```

**One vendor is not one platform.** Cisco alone ships IOS, IOS-XE, NX-OS and
IOS-XR — four genuinely different operating systems with different syntax.
Rulepacks are keyed per platform. Getting this wrong at the schema level is
expensive to correct later.

---

## 3. Fingerprint signatures

Weighted evidence, not a single pattern. Produces
`(vendor, platform, os_version, model, serials[])` with a confidence score.

```yaml
platform: cisco_ios
signatures:
  - { type: line_regex,   pattern: '^version (\d+)\.(\d+)$',        weight: 0.35 }
  - { type: line_exact,   pattern: 'service timestamps debug datetime', weight: 0.15 }
  - { type: comment_char, value: '!',                                weight: 0.10 }
  - { type: block_regex,  pattern: '^line vty \d+ \d+$',             weight: 0.25 }
  - { type: negative,     pattern: '^set system ',                   weight: -0.50 }

version_extraction:
  - artifact: show_version
    pattern: 'Cisco IOS Software.*Version (?P<ver>[\d.()A-Za-z]+)'
    confidence: 1.0
  - artifact: running_config
    pattern: '^version (?P<ver>\d+\.\d+)$'
    confidence: 0.6          # major.minor only — less precise

model_extraction:
  - artifact: show_version
    pattern: 'cisco (?P<model>\S+) .*processor'

serial_extraction:
  - artifact: show_inventory
    pattern: 'NAME: "(?P<component>[^"]+)".*\n.*SN: (?P<serial>\S+)'
    multiple: true
```

**Note the negative signature.** Juniper set-format configurations begin every
line with `set`; explicitly penalising that pattern prevents misidentification,
which matters because a wrong fingerprint applies a wrong grammar and produces
silently wrong facts.

**Note the confidence on version extraction.** The running configuration gives
only `major.minor`; `show version` gives the full release string. Since
defaults and remediation are keyed on version ranges, precision here directly
affects correctness — which is one more reason multi-artifact ingestion is
mandatory rather than optional.

---

## 4. Structural grammar

For a mature platform this is authored rather than inferred.

```yaml
grammar:
  paradigm:       indentation
  comment_char:   "!"
  indent_unit:    1
  max_depth:      4
  continuation:   none
  block_start:    implicit_by_indent
  case_sensitive: false

  # Blocks whose child lines are context-dependent
  context_blocks:
    - { pattern: '^interface (?P<name>\S+)$',        context: interface }
    - { pattern: '^line vty (?P<lo>\d+) (?P<hi>\d+)$', context: vty_range }
    - { pattern: '^router (?P<proto>\S+)',           context: routing }
    - { pattern: '^ip access-list \S+ (?P<name>\S+)$', context: acl }
```

Supported paradigms across the platform set:

| Paradigm | Platforms |
|---|---|
| Indentation hierarchy | Cisco IOS / IOS-XE / NX-OS, Arista EOS |
| Flat path statements | Juniper set-format |
| Brace nesting | Juniper curly-format |
| Block keywords (`config`/`end`, `edit`/`next`) | FortiOS |
| XML | PAN-OS |
| Path headers with key-value pairs | MikroTik RouterOS |
| Native structured | AWS / Azure / GCP policy JSON |

---

## 5. Extractors

The bulk of a rulepack — typically **150–250 for a mature platform**. Each maps
parse-tree structure to schema facts, and each carries its own tests.

```yaml
extractor_id: cisco_ios.vty.transport_input
version:      7
scope:
  context: vty_range
match:  '^\s*transport input (?P<protos>.+)$'
emit:
  - fact:  mgmt.protocols.telnet.enabled
    value: "'telnet' in protos.split() or 'all' in protos.split()"
  - fact:  mgmt.protocols.ssh.enabled
    value: "'ssh' in protos.split() or 'all' in protos.split()"
tests:
  - { input: "transport input ssh",        expect: { telnet: false, ssh: true  } }
  - { input: "transport input telnet ssh", expect: { telnet: true,  ssh: true  } }
  - { input: "transport input all",        expect: { telnet: true,  ssh: true  } }
  - { input: "transport input none",       expect: { telnet: false, ssh: false } }
```

### 5.1 Extractor rules

| Rule | Reason |
|---|---|
| **Declarative only — no arbitrary code** | Rulepacks are importable content. Executable rulepacks make an imported community pack a code execution vector |
| **Scoped to a context** | A line has no meaning outside its position in the hierarchy |
| **Emit into the schema, never a vendor-shaped structure** | Otherwise controls stop being portable |
| **Handle polarity explicitly** | The value expression states the positive assertion; inversion is visible in the rulepack, not hidden |
| **Ship with tests** | Generated automatically from confirmed examples during teaching |
| **Versioned independently** | So a single extractor can be corrected without republishing an entire rulepack |

### 5.2 Overlapping-scope resolution

Cisco permits `line vty 0 4` and `line vty 0 15` in the same configuration,
overlapping on 0–4. Extractors must emit **per-scope-instance** facts, and the
rulepack's inheritance rules then resolve which wins.

This is a small detail that determines whether the tool is correct on real
enterprise configurations or only on documentation examples.

---

## 6. The defaults table

**This is what a mature rulepack has that a freshly taught one does not**, and it
is what resolves the absence problem described in
[05-security-baseline-model.md](05-security-baseline-model.md).

```yaml
defaults:
  mgmt.protocols.http.enabled:
    - { version_range: "<15.0",  value: true,
        source: "CIS Cisco IOS Benchmark, Default Value" }
    - { version_range: ">=15.0", value: false }

  mgmt.session.idle_timeout_sec:
    - { version_range: "*", value: 600 }

  mgmt.protocols.ssh.version:
    - { version_range: "<12.3",  value: 1 }
    - { version_range: ">=12.3", value: 2,
        condition: "crypto key present",
        note: "SSH unavailable until RSA key generated" }

  logging.timestamps_enabled:
    - { version_range: "*", value: false }
```

Three things to note:

**Defaults are version-ranged.** They change between releases. A single global
default table produces wrong answers on older or newer firmware.

**Defaults cite their source.** An auditor may be challenged on a finding derived
from a default rather than from an explicit line, and must be able to say where
the default came from.

**Defaults may be conditional.** Some settings depend on other configuration
being present. Where a condition cannot be evaluated, the fact resolves to
`default_unknown` rather than guessing.

### 6.1 Bootstrapping defaults from benchmarks

CIS Benchmarks document default values explicitly — every recommendation has a
"Default Value" section. **Importing a benchmark therefore also populates the
defaults table**, directly reducing `default_unknown` facts and raising coverage.

### 6.2 Inferring defaults from the fleet

Where no documented default exists, the estate itself is evidence.

If forty devices of a platform exist and thirty-nine never mention SSH cipher
configuration while one does:

1. **The concept exists on this platform** — proof by existence
2. **The syntax is now known** — free, without asking anyone
3. **The other thirty-nine are at default** — they could have expressed it and
   did not

This yields provenance `default_inferred`: the system knows the setting is at
default, but not what the default *value* is. Under strict assessment mode this
still produces UNKNOWN; under standard mode it can be combined with a documented
default if one later arrives.

**The union of every setting observed across N devices of a platform
approximates that platform's configurable surface** — and it improves passively
as more configurations are ingested.

---

## 7. Inheritance rules and platform quirks

### 7.1 Effective configuration resolution

The text is not the truth.

```yaml
inheritance:
  model: layered_merge
  layers:
    - { name: shared,         precedence: 1 }
    - { name: device_group,   precedence: 2 }
    - { name: template_stack, precedence: 3 }
    - { name: local,          precedence: 4 }
  conflict_resolution: highest_precedence_wins
  record_source_layer: true       # mandatory — auditors will ask
```

| Platform | Mechanism |
|---|---|
| PAN-OS | shared → device-group → template stack → local override |
| Juniper | `groups` + `apply-groups` expansion |
| Cisco | overlapping `line vty` range resolution |
| FortiOS | VDOM scoping |

**A parser that ignores inheritance produces confidently wrong answers on every
real enterprise deployment** — and enterprise deployments are exactly the ones
that matter.

### 7.2 Platform quirks

The unglamorous knowledge that separates a rulepack that works on production
configurations from one that works on documentation examples.

```yaml
quirks:
  command_abbreviation:
    enabled: true
    expansions:
      "int":  "interface"
      "gi":   "GigabitEthernet"
      "te":   "TenGigabitEthernet"
      "no sh": "no shutdown"

  password_encodings:
    - { type: 0, name: plaintext,  reversible: true,  strength: none }
    - { type: 7, name: vigenere,   reversible: true,  strength: none }
    - { type: 5, name: md5_crypt,  reversible: false, strength: weak }
    - { type: 8, name: pbkdf2_sha256, reversible: false, strength: strong }
    - { type: 9, name: scrypt,     reversible: false, strength: strong }

  redaction_markers: ["<removed>", "$8$***"]

  show_tech_sections:
    - { marker: "------------------ show running-config ------------------",
        artifact: running_config }
    - { marker: "------------------ show version ------------------",
        artifact: show_version }

  encoding: { accept: [utf8, latin1], line_endings: [lf, crlf] }
```

**Command abbreviation is a real trap.** A regular expression written against
`interface GigabitEthernet0/1` silently fails on `int gi0/1`. Silent failure
means the fact is never produced, which means the control returns UNKNOWN, which
lowers coverage — safe, but invisible unless the quirk is handled.

**Password encoding knowledge is itself a control.** Distinguishing Cisco type 7
(trivially reversible) from type 8/9 (properly hashed) is the difference between
a critical finding and a pass.

---

## 8. Trust tiers

Because shipped and taught rulepacks are the same kind of object, the amount of
validation behind each must be explicit.

| Tier | Meaning | Validation performed |
|---|---|---|
| **Certified** | Authored by the platform team | Validated against a large corpus, full regression suite, two-person ratified, cross-checked against a reference implementation |
| **Verified community** | Imported from another organisation | Signature verified, tests pass locally, but not independently corpus-validated here |
| **Local** | Taught by this organisation | Ratified under the two-person rule; tests generated from confirmations |
| **Provisional** | Taught, not yet ratified | Usable for exploration. **Findings flagged and excluded from issued reports** |

**Every report states the trust tier of every rulepack used.** An assessor must
know whether a finding rests on certified parsing or on something a colleague
taught the system yesterday afternoon.

> A finding derived from provisional parsing is not evidence.

This property exists only because knowledge is stored as inspectable data. Model
weights have no equivalent — you cannot state the trust tier of a fine-tuning
run, roll back one bad lesson, or share a fraction of it.

---

## 9. Rulepack lifecycle

```
   AUTHOR ──► VALIDATE ──► RATIFY ──► PUBLISH ──► MAINTAIN ──► DEPRECATE
      │           │           │           │            │
   learning    corpus &    2nd user    signed      version
   subsystem   conflict    approval    bundle      bump per
               checks                              change
```

### 9.1 Validation gates

Before a rulepack version is accepted:

| Gate | Check |
|---|---|
| **Self-match** | Every extractor matches at least one line in its source corpus, and the matched lines are displayed |
| **Cross-platform** | No extractor fires on artifacts of a different platform |
| **Conflict** | No two extractors produce different values for the same fact on the same device |
| **Regression** | All frozen tests pass |
| **Metamorphic** | Semantics-preserving mutations of corpus configurations (reordered blocks, renamed objects, altered whitespace, abbreviated commands) produce identical facts |
| **Coverage delta** | The change is reported as its effect on estate coverage |

**Metamorphic validation is the highest-value gate** because it finds defects no
hand-written test would catch — you would never have thought to write the test
case that exposes them.

### 9.2 Portability

Rulepacks export as signed bundles:

```
cisco_ios-7.2.1.rpk
├── manifest.yaml        platform, version, checksums, dependencies
├── signature.sig
├── fingerprint.yaml
├── grammar.yaml
├── extractors/          one file per extractor, with tests
├── defaults.yaml
├── inheritance.yaml
├── quirks.yaml
└── provenance.yaml      authorship, ratification, corpus statistics
```

One organisation teaches a platform once; others import the result. Platform
knowledge compounds across deployments rather than being relearned everywhere.

Imported bundles are **verified, tier-marked, and validated against the local
corpus before use** — an imported rulepack is never trusted on the strength of
its signature alone.

---

## 10. Coverage reporting per rulepack

A rulepack knows how much of its platform it can read:

```
Rulepack: cisco_ios @ 7.2.1        Tier: Certified

  Schema facts producible                  71 of 84    (85%)
  Corpus line coverage                     94.2%
  Extractors                               186
  Regression tests                         412  (all passing)

  Unproducible facts (13)
    crypto.ipsec.esp_proposals[]           not yet implemented
    auth.password_policy.history_count     platform capability unclear
    ...

  Corpus: 340 configurations · 41 distinct OS versions
```

This drives three things: the automation coverage manifest
([06](06-controls-and-frameworks.md)), the rulepack development backlog, and an
honest statement to the user about what the tool can and cannot see on their
estate.

---

## 11. What good looks like

A mature rulepack:

- Identifies its platform and version with high confidence from multiple
  independent signals
- Parses ≥ 95% of corpus lines into typed tree nodes
- Produces ≥ 80% of the schema facts its platform is capable of expressing
- Carries a documented, version-ranged, source-cited defaults table
- Resolves inheritance correctly on real enterprise configurations
- Handles abbreviation, encodings, redaction and diagnostic bundles
- Survives metamorphic mutation without changing a single fact
- States plainly which facts it cannot produce and why
