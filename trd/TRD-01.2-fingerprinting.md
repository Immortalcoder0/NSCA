# TRD-01.2 · Platform Fingerprinting

---

## 1. Scope

Determination of `⟨vendor, platform, os_version, model, serials⟩` from ingested
artifacts, with a confidence score; routing of the three identification outcomes;
and version-based vulnerability correlation, which operates **before any parsing
occurs**.

**Out of scope:** parsing (TRD-02.1), grammar inference for unknown platforms
(TRD-02.2).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-FPR-001 | Vendor, platform, version, model, serial determination |
| FR-FPR-002 | Platform discrimination within a vendor |
| FR-FPR-003 | Confidence scoring and low-confidence escalation |
| FR-FPR-004 | Three-outcome routing |
| FR-FPR-005 | Pre-parse vulnerability lookup |
| FR-FPR-006 | Retrospective assessability when a platform is later taught |

---

## 3. Design

### 3.1 Why fingerprinting is separated from parsing

A wrong fingerprint applies a wrong grammar, which produces a plausible parse
tree containing **silently wrong facts**. This is more dangerous than a parse
failure, which produces UNKNOWN.

Fingerprinting therefore runs first, independently, and refuses to commit to a
platform below a confidence threshold.

### 3.2 Weighted signature evaluation

Each rulepack declares signatures with weights. Signatures may be **negative** —
evidence *against* a platform.

```
score(platform, artifact) =
    Σ  w_i · match_i(artifact)          for all signatures i of platform

  where match_i ∈ {0, 1} and w_i ∈ [-1, 1]

normalised(platform) = clamp(score / Σ |w_i| for positive w_i, 0, 1)
```

```yaml
platform: cisco_ios
signatures:
  - { type: line_regex,   pattern: '^version (\d+)\.(\d+)$',           w:  0.35 }
  - { type: line_exact,   pattern: 'service timestamps debug datetime', w:  0.15 }
  - { type: comment_char, value: '!',                                   w:  0.10 }
  - { type: block_regex,  pattern: '^line vty \d+ \d+$',                w:  0.25 }
  - { type: structural,   paradigm: indentation,                        w:  0.15 }
  - { type: negative,     pattern: '^set system ',                      w: -0.50 }
  - { type: negative,     pattern: '^config system global$',            w: -0.50 }
```

**DD-01.2-01 — Negative signatures are mandatory for near-neighbour platforms.**
Juniper set-format and Cisco IOS share tokens (`interface`, `description`,
`snmp`). Without negative evidence, a Juniper configuration scores non-trivially
as Cisco. Every rulepack must declare negative signatures against platforms with
which it shares vocabulary.

### 3.3 Decision procedure

```
fingerprint(artifact) →
  scores = { p : normalised(p, artifact) for p in loaded_platforms }
  best, second = top two by score

  if best.score ≥ 0.75 and (best.score − second.score) ≥ 0.20:
      → KNOWN(best.platform, confidence = best.score)

  if best.score ≥ 0.75 and margin < 0.20:
      → AMBIGUOUS(best, second)              // escalate, do not guess

  if best.score < 0.40:
      identity = extract_self_identification(artifact)
      if identity: → IDENTIFIABLE_UNTAUGHT(identity)
      else:        → UNKNOWN

  otherwise (0.40 ≤ best < 0.75):
      → LOW_CONFIDENCE(best)                 // escalate for confirmation
```

**DD-01.2-02 — The margin requirement is as important as the threshold.** A
configuration scoring 0.80 for IOS and 0.78 for NX-OS is not an 80%-confident
IOS identification; it is an unresolved choice between two platforms with
different grammars. Guessing here is exactly the failure mode §3.1 exists to
prevent.

### 3.4 Self-identification for untaught platforms

Most platforms announce themselves in a header comment even when nothing else is
recognisable:

```
# aug/25/2026 14:32:11 by RouterOS 7.11.2
! NX-OS Image file is: bootflash:///nxos.9.3.10.bin
## Last commit: 2026-08-14 by admin   (JunOS)
```

A vendor-independent pattern set extracts `⟨vendor_string, version_string⟩` from
comment regions. This yields `IDENTIFIABLE_UNTAUGHT`, which is materially more
useful than `UNKNOWN`:

- Vulnerability correlation works immediately (§3.6)
- The training queue is labelled with the real platform name
- **FR-FPR-006:** when the platform is later taught, every previously ingested
  artifact bearing that identity becomes retrospectively assessable

### 3.5 Version extraction and normalisation

Version drives defaults resolution and remediation selection, so precision
matters and is tracked.

| Source | Precision | Confidence |
|---|---|---|
| `show version` release string | Full (`16.12.04`) | 1.0 |
| Config `version` line | Major.minor only (`16.12`) | 0.6 |
| Self-identification comment | Varies | 0.7 |
| Absent | ⊥ | 0 |

Normalisation to a comparable ordered structure:

```
parse_version("16.12.04")        → ⟨16, 12, 4, ∅⟩
parse_version("15.2(4)E7")       → ⟨15, 2, 4, "E7"⟩
parse_version("7.11.2")          → ⟨7, 11, 2, ∅⟩
parse_version("9.3(10)")         → ⟨9, 3, 10, ∅⟩
parse_version("10.2.3-h4")       → ⟨10, 2, 3, "h4"⟩
```

**INV-01.2-01.** Where version precision is insufficient to resolve a
version-ranged default or remediation unambiguously, the affected fact resolves
`default_unknown` and the affected remediation is withheld. **Precision loss
becomes coverage loss, never a guess** (G2).

This is a direct argument for multi-artifact ingestion: without `show version`,
a device is stuck at major.minor precision and its coverage suffers measurably.

### 3.6 Vulnerability correlation — before parsing

FR-FPR-005. Once `⟨platform, version⟩` is known, an offline vulnerability index
is consulted. **No parsing is required.**

```
vuln_lookup(platform, version) →
  index: platform → [ ⟨version_constraint, vuln_id, severity, summary⟩ ]
  return all entries whose constraint contains version
```

This produces real findings at **0% parse coverage on a platform never seen
before**:

```
⚠ RouterOS 6.42 — CVE-2018-14847
  Authentication bypass permitting unauthenticated retrieval of the
  user database. Publicly exploited. Upgrade required.
  Source: offline vulnerability index, current as of 2026-08-14 (43 days).
```

**DD-01.2-03.** The index age is stated wherever findings derived from it appear.
Offline data with an unstated age is a false assurance — the report must say what
it could not have known.

### 3.7 Model and serial extraction

Extracted from `show_version` and `show_inventory` by rulepack-declared patterns.
Multiple serials per device is the normal case: chassis, line cards, power
supplies, modules.

```yaml
serial_extraction:
  - artifact: show_inventory
    pattern: 'NAME: "(?P<component>[^"]+)".*?SN: (?P<serial>\S+)'
    multiple: true
    component_role_map:
      Chassis: chassis
      Slot:    line_card
      Power Supply: psu
```

**INV-01.2-02.** Exactly one serial is designated `chassis`. It is the device's
correlation key (TRD-01.1 §3.5) and the identifier printed on the report cover.
Where no chassis serial is determinable, the device record records
`serials: NOT_DETERMINED` — the report states this explicitly rather than
omitting a mandated section (FR-RPT-003).

### 3.8 Outcome routing

| Outcome | Downstream |
|---|---|
| `KNOWN` | Parse with rulepack grammar (TRD-02.1) |
| `LOW_CONFIDENCE` | Hold; assessor confirmation required; then as `KNOWN` |
| `AMBIGUOUS` | Hold; assessor disambiguation required |
| `IDENTIFIABLE_UNTAUGHT` | Grammar inference (TRD-02.2) + training queue, labelled with the real platform name. Vulnerability findings produced |
| `UNKNOWN` | Grammar inference + training queue, labelled by artifact |

**Held artifacts are not assessed.** They appear in the completeness report as
missing with reason `fingerprint_unresolved`.

---

## 4. Interfaces

**Input:** `⟨artifact_id, normalised_content, artifact_type⟩` from TRD-01.1

**Output**

```
Fingerprint {
  outcome: KNOWN | LOW_CONFIDENCE | AMBIGUOUS
         | IDENTIFIABLE_UNTAUGHT | UNKNOWN
  vendor, platform, rulepack_ref
  os_version: ⟨major, minor, patch, qualifier⟩ | ⊥
  version_precision: full | major_minor | none
  version_confidence: [0,1]
  model: string | ⊥
  serials[]: ⟨component, serial, role⟩
  confidence: [0,1]
  signals_matched[]                     // for explainability
  runner_up?: ⟨platform, score⟩         // when AMBIGUOUS
  self_identification?: ⟨vendor_string, version_string⟩
  vulnerabilities[]: ⟨id, severity, summary, index_age_days⟩
}
```

**Explainability requirement:** `signals_matched[]` must be sufficient for an
assessor to understand *why* a platform was chosen. Fingerprinting is the first
point at which the system can be wrong in a way that produces confident garbage;
it must be inspectable.

---

## 5. Edge cases

| Case | Handling |
|---|---|
| Multi-VDOM / multi-context configuration in one file | Fingerprint the container platform; contexts are handled at parse (TRD-02.3) |
| Config exported through a management platform, reformatted | Signatures may not match the device's native format. Management-export signatures are declared separately in the rulepack |
| Two platforms sharing a grammar (Arista EOS resembling IOS) | Negative signatures plus platform-unique tokens. Where genuinely ambiguous → `AMBIGUOUS`, never a guess |
| Version present in config but contradicting `show version` | `show version` wins (higher precision); conflict recorded |
| Cloud policy JSON | Fingerprinted by document shape and required keys; version is the API version |
| Config fragment (a single section) | Low confidence expected → held; a fragment cannot be audited as a device |
| Platform renamed across releases (Firepower → Secure Firewall) | Rulepack declares platform aliases; the canonical identifier is stable |

**The management-export case is commonly missed.** A configuration retrieved
through Panorama or a network management system may be reformatted, reordered,
or re-indented relative to what the device itself emits. If only device-native
signatures are declared, such artifacts land in `UNKNOWN` and enter the training
queue unnecessarily.

---

## 6. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Wrong platform, high confidence | Downstream parse coverage collapse; extractor conflicts | **Worst case: silently wrong facts.** Mitigated by margin requirement (DD-01.2-02) and by V-01.2-003 |
| Version imprecision | `version_precision` field | Defaults unresolved → `default_unknown` → coverage falls. Safe |
| No chassis serial | Extraction returns ∅ | Report states `NOT DETERMINED`; correlation falls back to hostname |
| Stale vulnerability index | Index age exceeds threshold | Age stated in every derived finding; warning above 90 days |
| New OS release outside all declared ranges | No version-range match | Defaults and remediation withheld; coverage falls; rulepack backlog entry raised |

---

## 7. Verification

```
V-01.2-001   Platform discrimination within a vendor
  Requirement  FR-FPR-002
  Method       CORPUS
  Procedure    Corpus containing IOS, IOS-XE, NX-OS and IOS-XR
               configurations, ≥ 10 each.
  Acceptance   ≥ 98% correct platform. Zero cross-platform assignments
               at confidence ≥ 0.75.
  Severity     BLOCKING
```

```
V-01.2-002   Near-neighbour platforms are separated by negative signatures
  Requirement  DD-01.2-01
  Method       CORPUS
  Procedure    Juniper set-format and Cisco IOS configurations scored
               against both rulepacks.
  Acceptance   Correct platform scores ≥ 0.75; incorrect platform < 0.40
               in every case.
  Severity     BLOCKING
```

```
V-01.2-003   Ambiguity is escalated, never resolved by guessing
  Requirement  FR-FPR-003, DD-01.2-02
  Method       UNIT + PROPERTY
  Procedure    Construct artifacts scoring within 0.20 of two platforms.
  Acceptance   Outcome is AMBIGUOUS. No parse occurs. Device held and
               reported missing with reason `fingerprint_unresolved`.
               Zero findings produced.
  Severity     BLOCKING
```

```
V-01.2-004   Untaught platforms are still identified where self-identifying
  Requirement  FR-FPR-004
  Method       CORPUS
  Procedure    Remove the MikroTik rulepack; ingest RouterOS configurations.
  Acceptance   Outcome IDENTIFIABLE_UNTAUGHT with vendor "RouterOS" and
               version 7.11.2. Training queue labelled with the platform name.
  Severity     MAJOR
```

```
V-01.2-005   Vulnerability correlation operates at zero parse coverage
  Requirement  FR-FPR-005
  Method       INTEGRATION
  Procedure    Ingest a RouterOS 6.42 configuration with the MikroTik
               rulepack removed. Do not teach.
  Acceptance   CVE finding produced. Parse coverage 0%. Control coverage 0%.
               Finding includes the vulnerability index age.
  Severity     BLOCKING
  Note         This is the "value at zero coverage" claim, verified.
```

```
V-01.2-006   Version precision loss becomes coverage loss, not a guess
  Requirement  INV-01.2-01, G2
  Method       INTEGRATION
  Procedure    Ingest a config without show_version, where the defaults
               table has distinct values for 16.12.03 and 16.12.05.
  Acceptance   Affected facts resolve default_unknown; dependent controls
               return UNKNOWN. Zero facts resolved by choosing a default
               from an unresolved range.
  Severity     BLOCKING
```

```
V-01.2-007   Serial extraction reaches the report
  Requirement  FR-FPR-001, INV-01.2-02, FR-RPT-002
  Method       CORPUS + INTEGRATION
  Procedure    All corpus devices supplying show_inventory.
  Acceptance   ≥ 98% chassis serial extraction. All extracted serials appear
               on the report cover. Where absent, cover states
               `NOT DETERMINED` — never an omitted section.
  Severity     BLOCKING
```

```
V-01.2-008   Version comparison ordering is correct
  Requirement  §3.5
  Method       PROPERTY
  Procedure    Generated version strings across all supported formats,
               with known orderings including qualifier handling.
  Acceptance   Total order matches the reference ordering for 100% of pairs.
               15.2(4)E7 > 15.2(4)E3;  16.12.04 > 16.12.4 is equal, not greater.
  Severity     MAJOR
```

```
V-01.2-009   Management-platform exports are recognised
  Requirement  §5 edge case
  Method       CORPUS
  Procedure    Corpus subset of Panorama-exported PAN-OS and NMS-retrieved
               IOS configurations.
  Acceptance   ≥ 90% correctly fingerprinted. Failures land in
               IDENTIFIABLE_UNTAUGHT or UNKNOWN — never a wrong platform.
  Severity     MAJOR
```

```
V-01.2-010   Fingerprinting is deterministic and explainable
  Requirement  G1, FR-FPR-003
  Method       PROPERTY
  Procedure    Fingerprint the full corpus 10 times with varied rulepack
               load order.
  Acceptance   Identical outcome, confidence and signals_matched every time.
               signals_matched non-empty for every KNOWN outcome.
  Severity     BLOCKING
```

```
V-01.2-011   Retrospective assessability after teaching
  Requirement  FR-FPR-006
  Method       INTEGRATION
  Procedure    Ingest 3 untaught-platform artifacts. Teach the platform.
               Re-assess without re-ingesting.
  Acceptance   All 3 assessed from the originally stored artifacts.
               Artifact hashes unchanged.
  Severity     MAJOR
```

---

## 8. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should the 0.75 / 0.20 thresholds be per platform rather than global? | Per platform is more accurate for crowded families (Cisco) but adds tuning surface and risks over-fitting to the corpus. Current design: global, with corpus calibration reported |
| Q2 | Should `LOW_CONFIDENCE` block assessment, or assess with every finding flagged? | Blocking is safest but may frustrate an assessor with an unusual but valid export. Current design: block, because a wrong grammar yields silently wrong facts |
| Q3 | What vulnerability index age triggers a hard warning rather than a note? | Too aggressive and air-gapped deployments are permanently warned; too lax and stale data looks current. Current design: note always, warning above 90 days |
