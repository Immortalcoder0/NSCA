# TRD-00 · Conventions and Verification Framework

---

## 1. Purpose

Defines the structure every TRD follows, the identifier schemes, and — most
importantly — **what it means for a requirement to be verified**.

A TRD without verification criteria is a design note. This set is a contract.

---

## 2. TRD document template

Every TRD contains these sections, in this order:

```
1. Scope                What this subsystem does and does not do
2. Requirements         PRD FR/NFR IDs satisfied, and how
3. Design               Algorithms, data structures, formats, invariants
4. Interfaces           Inputs, outputs, contracts with adjacent subsystems
5. Edge cases           Known-hard inputs and their handling
6. Failure modes        What breaks, how it is detected, how it degrades
7. Verification         V-* criteria: method, procedure, acceptance threshold
8. Open questions       Decisions deferred to implementation, with the trade-off
```

Section 7 is mandatory and non-negotiable. A requirement with no verification
criterion is not a requirement — it is an intention.

---

## 3. Identifier schemes

| Scheme | Format | Example | Defined in |
|---|---|---|---|
| Functional requirement | `FR-<AREA>-<NNN>` | `FR-CTL-005` | PRD 03 |
| Non-functional requirement | `NFR-<AREA>-<NNN>` | `NFR-REL-001` | PRD 13 |
| **Verification criterion** | `V-<TRD>-<NNN>` | `V-05.2-004` | This set |
| Invariant | `INV-<TRD>-<NN>` | `INV-03.2-01` | This set |
| Design decision | `DD-<TRD>-<NN>` | `DD-02.2-03` | This set |

---

## 4. Verification methods

Every criterion declares exactly one primary method.

| Method | Meaning | Runs in |
|---|---|---|
| **UNIT** | Deterministic test on a single component with fixed inputs | CI, every commit |
| **PROPERTY** | Generated inputs asserting an invariant holds universally | CI, every commit |
| **METAMORPHIC** | Semantics-preserving input mutation; output must not change | CI, nightly |
| **CORPUS** | Executed across the full real-configuration corpus | CI, every knowledge-base change |
| **INTEGRATION** | End-to-end through multiple subsystems | CI, every merge |
| **PERFORMANCE** | Timed against a defined workload and hardware profile | Nightly, release |
| **DIFFERENTIAL** | Compared against an independent reference implementation | Release |
| **MANUAL** | Human procedure with a defined script and recorded outcome | Release |

### 4.1 Why METAMORPHIC is called out separately

Conventional tests verify inputs you thought of. Metamorphic tests verify
**inputs you did not think of**, by asserting that transformations which should
not change the answer do not change the answer.

For a configuration parser this is disproportionately powerful: reorder blocks,
rename objects, abbreviate commands, alter whitespace — the extracted facts must
be identical. Any difference is a defect that no hand-written case would have
found, because you would never have thought to write it.

Specified in full in [TRD-11.2](TRD-11.2-metamorphic-testing.md).

---

## 5. Criterion format

```
V-05.2-004   A required fact that is missing or default_unknown yields UNKNOWN

  Requirement   FR-CTL-005
  Method        PROPERTY + CORPUS
  Procedure     For every control C and every fact F in C.requires_facts:
                construct a fact set omitting F; evaluate C.
  Acceptance    verdict == UNKNOWN for 100% of (C, F) pairs.
                Zero instances of PASS.
  Severity      BLOCKING
```

### 5.1 Severity classes

| Severity | Meaning |
|---|---|
| **BLOCKING** | Release is impossible while failing. Violates a core product guarantee |
| **MAJOR** | Release requires documented sign-off and a remediation plan |
| **MINOR** | Tracked; does not block |

BLOCKING criteria are enumerated in
[TRD-11.3 §3](TRD-11.3-acceptance-criteria.md). There are fourteen.

---

## 6. The four inviolable guarantees

Every TRD is written to preserve these. Any design that cannot is rejected.

| # | Guarantee | Enforced by |
|---|---|---|
| **G1** | **Determinism.** Identical inputs and knowledge base versions produce byte-identical output | [TRD-10.1](TRD-10.1-determinism.md) |
| **G2** | **Never over-claim.** An undetermined result is never reported as compliant | [TRD-05.2](TRD-05.2-evaluation.md), [TRD-03.2](TRD-03.2-provenance-defaults.md) |
| **G3** | **Evidence binding.** Every fact and finding traces to specific artifact lines | [TRD-03.1](TRD-03.1-extractor-runtime.md) |
| **G4** | **Assessor independence.** No code path exists that modifies an audited device | [TRD-01.3](TRD-01.3-collection.md) |

### 6.1 G4 is verified by absence

G4 cannot be verified by testing that modification fails — it is verified by
proving the capability does not exist:

- Static analysis asserts no call site issues a configuration-mode command
- The collection driver's command allowlist is a compile-time constant
- No API endpoint accepts a device-write operation
- CI fails on introduction of any write-capable transport call

See `V-01.3-001` through `V-01.3-004`.

---

## 7. Determinism rules binding on all subsystems

Any subsystem violating these breaks G1.

| Rule | Requirement |
|---|---|
| **D1** | No model inference in the assessment path |
| **D2** | No reads of wall-clock time during evaluation. Assessment time is an input, recorded once |
| **D3** | No randomness. Where sampling is required, it is seeded from a campaign-stable value |
| **D4** | All collection iteration is explicitly ordered |
| **D5** | No floating-point arithmetic in scoring. Ratios are exact integer pairs, rendered at fixed precision |
| **D6** | No dependency on filesystem enumeration order, hash-map order, or thread scheduling |
| **D7** | Parallel work produces order-independent results; aggregation applies a deterministic sort before reduction |
| **D8** | No locale-dependent comparison, casing, or number formatting |

### D5 rationale

`112/143` stored as a float and rendered as `78%` will, across platforms and
library versions, occasionally render as `78%` and occasionally as `79%` at
boundary values. Storing the exact pair and rendering with a defined rounding
rule eliminates a whole class of irreproducibility that is otherwise nearly
impossible to diagnose.

---

## 8. Test data classes

| Class | Contents | Used by |
|---|---|---|
| **Fixtures** | Hand-written minimal configurations exercising one construct | UNIT |
| **Corpus** | Real production configurations, sanitised, ≥ 5 platforms | CORPUS, METAMORPHIC |
| **Golden set** | Corpus subset with expert-verified expected findings | DIFFERENTIAL, acceptance |
| **Adversarial set** | Malformed, truncated, injection-bearing, encoding-hostile inputs | PROPERTY, security |
| **Synthetic estate** | Multi-device topology with known reachability properties | Graph, attack path |
| **Untaught holdout** | ≥ 1 platform deliberately excluded from all shipped rulepacks | Learning acceptance |

### 8.1 The untaught holdout is a release gate

At least one real platform must be withheld from every shipped rulepack, so that
the learning system can be verified against a platform it has genuinely never
seen. Teaching it during testing invalidates the gate; a fresh holdout must be
designated.

This is what makes `V-11.3-009` meaningful rather than circular.

### 8.2 Corpus requirements

| Property | Minimum |
|---|---|
| Platforms | 5 distinct, ≥ 3 structural paradigms |
| Configurations | 200 |
| OS versions per platform | 3 |
| Real production configurations | ≥ 60% (not documentation examples) |
| Multi-artifact devices | ≥ 30 with `show version` and `show inventory` |
| Inheritance-bearing | ≥ 10 (PAN-OS device groups or Juniper `apply-groups`) |
| Terse exports | ≥ 20 |
| Cloud policy objects | ≥ 15 |

Sanitisation replaces credentials, public addresses and organisation identifiers
**structure-preservingly** — a sanitised type 7 password must remain a
syntactically valid type 7 password, or the corpus stops testing what it claims
to test.

---

## 9. Notation used in designs

```
⟨a, b⟩          tuple
X → Y           function from X to Y
X ⊎ Y           disjoint union
⊥               undefined / unknown
∀ x ∈ S         universal quantification
INV-xx-nn       invariant, asserted at runtime in debug builds
```

Pseudocode is language-neutral and describes behaviour, not implementation.

---

## 10. What TRDs deliberately do not specify

| Not specified | Why |
|---|---|
| Programming language, frameworks, libraries | Implementation choice; the design constrains the shape, not the tooling |
| Database engine and physical schema | Constrained by the data model and access patterns in PRD 14 |
| Deployment orchestration | Constrained by NFR-DEP; specific tooling is an operational decision |
| UI component library | Constrained by PRD 12 behaviour and accessibility requirements |

Where a design genuinely depends on a specific capability — such as
constrained-output generation for candidate proposal — the *capability* is
specified, not the product providing it.
