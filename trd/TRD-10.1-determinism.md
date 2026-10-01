# TRD-10.1 · Determinism Enforcement

---

## 1. Scope

The infrastructure that makes **G1 — determinism** an enforced property rather
than an aspiration: knowledge base pinning, the reproducibility manifest,
verification mode, and the mechanisms that prevent drift from being introduced.

> Identical `(input artifacts, knowledge base versions)` **MUST** produce
> byte-identical findings and reports.

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-INT-001 | Byte-identical results |
| FR-INT-002 | Reproducibility manifest |
| FR-INT-003 | Verification mode |
| FR-CMP-009 | Knowledge base pinning per campaign |
| NFR-REL-001, 002 | Determinism and verification |
| G1 | The guarantee itself |

---

## 3. Why this is load-bearing

A tool that produces different answers on different runs cannot be used as
evidence. Worse, **an assessor cannot notice it is happening** — two runs a week
apart will differ for legitimate reasons (new firmware, changed configuration,
updated content) unless determinism is guaranteed by construction and the
legitimate causes are individually attributable.

This is also the strongest argument against the obvious architecture, in which a
language model reads the configuration and reports findings. Such a system is
**structurally incapable** of this guarantee, and no amount of prompt engineering
changes that.

---

## 4. The eight determinism rules

Restated from TRD-00 §7 with their enforcement mechanism.

| Rule | Requirement | Enforced by |
|---|---|---|
| **D1** | No model inference in the assessment path | Static analysis; runtime assertion; V-10.1-002 |
| **D2** | No wall-clock reads during evaluation | Clock access forbidden in the evaluation module; V-10.1-003 |
| **D3** | No randomness | No RNG import in the assessment path; seeded where sampling is required |
| **D4** | All collection iteration explicitly ordered | Lint rule; property tests |
| **D5** | No floating point in scoring | Ratios are exact integer pairs; type-level enforcement |
| **D6** | No dependency on enumeration, hash or scheduling order | Sorted iteration; property tests with shuffled inputs |
| **D7** | Parallel work is order-independent; aggregation sorts before reducing | Design constraint; property tests with varied concurrency |
| **D8** | No locale-dependent comparison, casing or formatting | Fixed formatting locale; property tests under varied locale |

### 4.1 D5 deserves specific attention

`112/143` stored as a floating-point value and rendered as a percentage will,
across platforms and library versions, occasionally render as `78%` and
occasionally as `79%` at boundary values.

```
compliance : ⟨numerator: int, denominator: int⟩       // never a float
render(ratio, precision) → deterministic rounding, banker's rounding excluded
```

This eliminates a class of irreproducibility that is otherwise nearly impossible
to diagnose — the difference appears once in several hundred devices and looks
like a transient glitch.

### 4.2 D2 is subtler than it appears

Assessment time is an **input**, recorded once at campaign execution, and is
never read during evaluation. Anything that depends on "now" — an accepted risk
approaching expiry, a stale vulnerability index — is a *lifecycle* or *reporting*
concern, computed outside the assessment path from the recorded time.

**INV-10.1-01 — Re-executing an assessment one year later, with unchanged
inputs, produces identical results.** Verified by V-10.1-003 with the system
clock advanced.

---

## 5. Knowledge base pinning

FR-CMP-009. A campaign records the exact version of every component that can
influence a result.

```yaml
knowledge_base_pin:
  engine:          v2.4.0
  schema_registry: v1.8.0
  rulepacks:
    - { id: cisco_iosxe, version: 7.2.1, tier: certified }
    - { id: mikrotik_routeros, version: 1.0.0, tier: local }
  control_packs:
    - { id: nsca-core, version: 3.1.0 }
  frameworks:
    - { id: cis,  benchmark: cisco_ios_15,       version: 4.1.0 }
    - { id: stig, benchmark: cisco_iosxe_router, release: 2026-01 }
    - { id: nist, catalog: 800-53, revision: Rev5 }
  lookup_tables:
    - { id: weak_algorithms, version: 2026-08 }
  vulnerability_index: { version: 2026-08-14 }
```

**INV-10.1-02 — Pinning is complete.** Any component capable of influencing a
verdict must appear. A component omitted from the pin is a determinism hole:
updating it would silently change historical results.

**INV-10.1-03 — Pins are immutable once a campaign is issued** (PRD 14 DM-2).
Adopting new content affects future campaigns only (TRD-05.3 INV-05.3-04).

### 5.1 Mid-campaign mutation

Knowledge base changes submitted while an assessment is running are **queued**,
not applied (TRD-03.3 V-03.3-010). A campaign executes against one consistent
knowledge base from first device to last.

Without this, a campaign assessing 400 devices over two days could evaluate the
first 200 against different content than the last 200 — producing an internally
inconsistent audit that no manifest could describe.

---

## 6. The reproducibility manifest

FR-INT-002. Attached to every issued report.

```yaml
report_id: RPT-2026Q3-CORE-SW-01-001
generated: 2026-09-12T14:22:31Z
inputs:
  - { artifact: ART-004121, sha256: 3f9a...c21b }
  - { artifact: ART-004122, sha256: 7c04...19af }
  - { artifact: ART-004123, sha256: e281...b30c }
knowledge_base: { ...as §5... }
report_hash: 9a41...7f2e
statement: >
  Re-executing with identical inputs and knowledge base versions will
  produce a byte-identical report.
```

The manifest is **sufficient to re-execute**. Anything needed for reproduction
and absent from the manifest is a defect.

---

## 7. Verification mode

FR-INT-003. Re-execute a historical campaign and compare.

```
verify(report) →
  1  resolve artifacts by hash            → missing ⇒ UNVERIFIABLE
  2  resolve knowledge base by pin        → missing ⇒ UNVERIFIABLE
  3  re-execute assessment
  4  re-render report
  5  compare hashes
```

| Outcome | Meaning | Action |
|---|---|---|
| **MATCH** | Reproduced exactly | Findings stand |
| **MISMATCH**, knowledge base differs | Expected if content changed | Delta decomposed and explained |
| **MISMATCH**, knowledge base identical | **Determinism defect** | Investigate immediately; release-blocking |
| **UNVERIFIABLE** | Artifacts or pinned versions unavailable | Stated, with the cause |

**DD-10.1-01 — The third row is why the guarantee must be enforced by
construction.** If determinism were merely hoped for, this case would be
indistinguishable from an ordinary content change and would never be noticed.
Because it is guaranteed, a mismatch under an identical pin is unambiguous
evidence of a bug.

### 7.1 Continuous verification

Verification runs automatically as a CI gate against a fixed set of golden
campaigns on every knowledge base or engine change. A determinism regression is
caught in minutes rather than discovered by an assessor a year later.

---

## 8. Preventing drift

Determinism decays unless actively defended.

| Mechanism | Catches |
|---|---|
| **Static analysis** | Clock, RNG or model calls introduced into the assessment path |
| **Lint rules** | Unordered iteration over sets and maps |
| **Type-level constraint** | Floating point in scoring paths |
| **Property tests** | Shuffled input ordering, varied concurrency, varied locale and timezone |
| **CI verification gate** | Golden campaign hash mismatch |
| **Manifest completeness check** | A component influencing results but absent from the pin |

**INV-10.1-04 — Introducing a determinism violation fails the build**, in the
same way that introducing a device-write capability fails the build (TRD-01.3
V-01.3-002). Both are architectural guarantees, and both are defended
prospectively rather than audited retrospectively.

### 8.1 The manifest completeness check

Automated: for each component in the knowledge base, mutate it and re-run a
golden campaign.

```
∀ component c :
    mutate(c) ⇒ golden campaign result changes
             ⇒ c MUST appear in the pin
```

A component whose mutation changes results but which is absent from the pin is a
determinism hole, and the check fails the build. This catches the failure mode
where a new lookup table or content file is added without being pinned.

---

## 9. Interfaces

```
pin(campaign) → KnowledgeBasePin
manifest(report) → ReproducibilityManifest
verify(report_id) → VerificationResult
verify_golden_set() → CI gate result
check_pin_completeness() → CI gate result
```

---

## 10. Edge cases

| Case | Handling |
|---|---|
| Artifact deleted under retention | `UNVERIFIABLE`, cause stated (NFR-DAT-003) |
| Rulepack version reverted then re-created with the same number | Rejected — versions are immutable once used in an issued campaign |
| Engine upgrade changing output format but not verdicts | Verdict-level match reported separately from byte-level; byte mismatch expected and explained |
| Campaign spanning a content update | Update queued; campaign completes on its original pin (§5.1) |
| Verification on a different host architecture | Must still match; V-10.1-005 |
| Golden campaign whose platform rulepack is legitimately corrected | Golden set updated with the change recorded and reviewed |

**The engine-upgrade case needs care.** A change to PDF layout alters bytes
without altering findings. Verification therefore reports two levels: verdict
equality (the substantive claim) and byte equality (the strict claim). A byte
mismatch with verdict equality under a changed engine version is expected; under
an identical engine version it is a defect.

---

## 11. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Model call introduced into assessment | Static analysis; V-10.1-002 | **G1 destroyed.** Build fails |
| Clock read during evaluation | V-10.1-003 | Results drift over time, undetectably |
| Unordered iteration | V-10.1-004 | Intermittent, near-undiagnosable differences |
| Float in scoring | V-10.1-006 | Rare boundary-value flips |
| Component missing from the pin | Pin completeness check | Historical results change silently |
| Mid-campaign mutation | V-10.1-007 | Internally inconsistent campaign |

---

## 12. Verification

```
V-10.1-001   Byte-identical output for identical inputs
  Requirement  FR-INT-001, G1
  Method       PROPERTY
  Procedure    Execute 20 golden campaigns 10 times each, across process
               restarts, on at least two host configurations, with varied
               concurrency, locale, timezone and input ordering.
  Acceptance   Identical report hashes in every run. Zero exceptions.
  Severity     BLOCKING
  Note         Referenced in the TRD README as one of the five criteria that
               prove the product's central claims.
```

```
V-10.1-002   No model inference in the assessment path
  Requirement  D1
  Method       Static analysis + INTEGRATION
  Procedure    Enumerate all call sites in ingestion, parsing, extraction,
               graph, evaluation, risk, remediation and reporting. Execute
               full campaigns with all model endpoints unreachable and local
               inference disabled.
  Acceptance   Zero inference calls reachable. Identical results with and
               without model availability. CI blocks introduction of a call.
  Severity     BLOCKING
```

```
V-10.1-003   No clock dependence in evaluation
  Requirement  D2, INV-10.1-01
  Method       PROPERTY
  Procedure    Execute golden campaigns with the system clock advanced by
               one day, one year, and set to a past date.
  Acceptance   Identical verdicts, severities and traces. Only the recorded
               generation timestamp differs, and it is an input.
  Severity     BLOCKING
```

```
V-10.1-004   No ordering dependence
  Requirement  D4, D6, D7
  Method       PROPERTY
  Procedure    Execute golden campaigns with shuffled artifact ordering,
               shuffled extractor ordering, shuffled control ordering, and
               concurrency from 1 to 32 threads.
  Acceptance   Identical results in all permutations.
  Severity     BLOCKING
```

```
V-10.1-005   Cross-host reproducibility
  Requirement  FR-INT-001
  Method       INTEGRATION
  Procedure    Execute the golden set on two hosts with different CPU
               architectures, operating system versions and locales.
  Acceptance   Identical report hashes.
  Severity     BLOCKING
```

```
V-10.1-006   No floating point in scoring
  Requirement  D5
  Method       Static analysis + PROPERTY
  Procedure    Inspect scoring types. Generate boundary-value ratios
               (1/3, 2/3, 112/143, 1/7) and render across platforms.
  Acceptance   Ratios stored as integer pairs. Identical rendered values
               everywhere. Zero floating-point operations in scoring paths.
  Severity     BLOCKING
```

```
V-10.1-007   Mid-campaign knowledge base mutation is queued
  Requirement  §5.1
  Method       INTEGRATION
  Procedure    Begin a 200-device campaign; submit a rulepack update and a
               schema registration mid-execution.
  Acceptance   Campaign completes on its original pin. Results identical to
               a run without the concurrent submissions. Updates applied
               afterwards.
  Severity     BLOCKING
```

```
V-10.1-008   The manifest is sufficient to re-execute
  Requirement  FR-INT-002, INV-10.1-02
  Method       INTEGRATION
  Procedure    On a clean deployment, reconstruct a campaign using only the
               manifest and the referenced artifacts.
  Acceptance   Byte-identical report. Zero information required that is
               absent from the manifest.
  Severity     BLOCKING
```

```
V-10.1-009   Pin completeness is enforced
  Requirement  INV-10.1-02, §8.1
  Method       INTEGRATION (CI gate)
  Procedure    For each knowledge base component, mutate it and re-run a
               golden campaign.
  Acceptance   Every component whose mutation changes results appears in the
               pin. A component that does not fails the build.
  Severity     BLOCKING
```

```
V-10.1-010   Verification mode distinguishes the three mismatch causes
  Requirement  FR-INT-003, DD-10.1-01
  Method       INTEGRATION
  Procedure    Verify (a) unchanged, (b) after a ratified content update,
               (c) with an artificially injected non-determinism, (d) with
               artifacts deleted.
  Acceptance   (a) MATCH, (b) MISMATCH with knowledge base delta explained,
               (c) MISMATCH flagged as a determinism defect and
               release-blocking, (d) UNVERIFIABLE with cause.
  Severity     BLOCKING
```

```
V-10.1-011   Determinism violations fail the build
  Requirement  INV-10.1-04
  Method       INTEGRATION (CI gate)
  Procedure    Submit branches introducing: a clock read in evaluation, an
               RNG call, unordered map iteration, and a float in scoring.
  Acceptance   All four fail the build with an explicit G1 violation message.
  Severity     BLOCKING
```

---

## 13. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should byte-level determinism be required across engine versions, or only verdict-level? | Byte-level across versions would freeze report layout permanently. Current design: verdict-level across versions, byte-level within a version, both reported by verification |
| Q2 | How large should the golden campaign set be? | Larger catches more, but CI runtime bounds it. Current design: 20 campaigns spanning all platforms and paradigms, extended whenever a determinism defect is found |
| Q3 | Should verification be offered to end users as a self-service action on any historical report? | It is the strongest possible demonstration of the reproducibility claim, but re-execution is expensive at estate scale. Current design: available per report on demand, and automatically for the golden set in CI |
