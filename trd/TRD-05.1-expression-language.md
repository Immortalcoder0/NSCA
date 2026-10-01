# TRD-05.1 · Assertion Expression Language

---

## 1. Scope

The restricted language in which control assertions, vacuity conditions, risk
modifiers and applicability clauses are written. Its type system, its
**three-valued logic**, and the guarantees that make control packs safe to
import.

**Out of scope:** evaluation orchestration and verdict production (TRD-05.2);
the extractor value language, which is separate and simpler (TRD-03.1 §3.3).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-CTL-002 | Controls are declarative data, not code |
| FR-CTL-005 | Missing facts yield UNKNOWN via three-valued logic |
| FR-CTL-017 | Deterministic; no model invocation |
| NFR-SEC-007 | No arbitrary code execution |
| G2 | Unknown propagates rather than collapsing to false |

---

## 3. Design

### 3.1 Why a restricted language rather than a general one

Control packs are **importable content**. An organisation may import a framework
pack authored elsewhere. If assertions could execute arbitrary code, importing a
control pack would be a remote code execution vector — and the portability that
makes framework sharing valuable would become its most dangerous property.

The language is therefore **total**: every expression terminates, has no side
effects, and cannot reach outside the fact set it was given.

| Property | Guarantee |
|---|---|
| Termination | No loops, no recursion, no unbounded quantification |
| Purity | No I/O, no clock, no randomness, no mutation |
| Isolation | Reads only the supplied fact set and declared lookup tables |
| Determinism | Same inputs → same result, always (D1, D3) |

### 3.2 Three-valued logic — the central mechanism

This is how G2 is enforced at the language level rather than by convention.

Values are `true`, `false`, or `⊥` (unknown). A reference to a fact whose
provenance is `default_unknown` evaluates to `⊥`.

**Conjunction**

| `and` | true | false | ⊥ |
|---|---|---|---|
| **true** | true | false | **⊥** |
| **false** | false | false | **false** |
| **⊥** | ⊥ | false | ⊥ |

**Disjunction**

| `or` | true | false | ⊥ |
|---|---|---|---|
| **true** | true | true | **true** |
| **false** | true | false | **⊥** |
| **⊥** | true | ⊥ | ⊥ |

**Negation:** `not ⊥ = ⊥`

**DD-05.1-01 — The two shaded cells are the whole point.**

`false and ⊥ = false` — if one conjunct is definitively false, the conjunction is
false regardless of the unknown. A control asserting *"telnet off AND http off"*
where telnet is known to be **on** correctly returns FAIL even though http is
unknown. Requiring full knowledge before reporting a definite failure would hide
real findings.

`true and ⊥ = ⊥` — if the only thing standing between a PASS and an unknown is an
undetermined fact, the answer is unknown. **This is the cell that prevents the
product's central failure mode.**

Symmetrically, `true or ⊥ = true`: a satisfied disjunct settles the matter.

### 3.3 Comparison with unknown

Any comparison involving `⊥` yields `⊥`:

```
⊥ == 2        → ⊥
⊥ > 600       → ⊥
⊥ in [a, b]   → ⊥
```

**Not** `false`. This is the most common implementation error in three-valued
systems and it silently converts unknowns into passes.

### 3.4 Type system

| Type | Literals | Operations |
|---|---|---|
| `boolean` | `true false` | `and or not` |
| `integer` | `0 42 -1` | `== != < <= > >= + - * /` |
| `string` | `"ssh"` | `== != contains startswith endswith lower trim` |
| `enum` | bare identifiers | `== != in` |
| `cidr` | `"10.0.0.0/8"` | `contains overlaps == subset_of` |
| `version` | `"16.12.04"` | `== != < <= > >= in_range` |
| `algorithm` | canonical identifiers | `== != in` |
| `list<T>` | `[a, b]` | `any all none count in ∪ ∩ \` |
| `object` | fact-defined | field access |

**Static typing against the schema registry.** A control comparing a boolean fact
to an integer is rejected at load, not at evaluation. Type errors are authoring
defects and must surface before a report depends on them.

### 3.5 Quantifiers over collections

```
snmp.communities | none(c => c.is_default)
auth.local_users | none(u => u.privilege_level >= 15 and u.reversible)
crypto.ssh.ciphers | all(c => c in ALLOWED_CIPHERS)
filter.rules | count(r => r.action == "permit" and r.source == "any") == 0
```

**Three-valued quantifier semantics:**

| Quantifier | Result |
|---|---|
| `all(p)` | `false` if any element is `false`; `⊥` if none false but some `⊥`; else `true` |
| `any(p)` | `true` if any element is `true`; `⊥` if none true but some `⊥`; else `false` |
| `none(p)` | `not any(p)` |
| `count(p)` | `⊥` if any element is `⊥`, else the integer count |

**DD-05.1-02 — `count` is strict.** A count over a collection containing an
unknown element is unknown, because the number is wrong if the unknown resolves
either way. `all` and `any` can short-circuit on a definite answer; `count`
cannot.

**INV-05.1-01 — An unknown-valued *collection* is not an empty collection.**
`crypto.ssh.ciphers` with provenance `default_unknown` evaluates to `⊥`, so
`all(...)` over it yields `⊥`. An implementation that treats an unknown list as
`[]` would make `all` vacuously true — a false PASS on precisely the crypto
controls that matter (TRD-03.1 V-03.1-005).

### 3.6 Scope-qualified fact access

Facts may be emitted per VTY range or per VDOM (TRD-03.1 §3.4). Controls declare
the aggregation:

```yaml
requires_facts:
  - mgmt.protocols.telnet.enabled
scope_aggregation: none        # none | all | any
assert: "mgmt.protocols.telnet.enabled == false"
```

| Aggregation | Meaning |
|---|---|
| `none` | The assertion must hold for **no** instance to fail — i.e. all instances satisfy it |
| `all` | Every scoped instance must satisfy the assertion |
| `any` | At least one instance must satisfy it |

**DD-05.1-03 — Default aggregation is `all`.** A device with one compliant VTY
range and one non-compliant range is non-compliant. Defaulting to `any` would
hide exactly the configuration error worth finding.

If any scoped instance is `⊥`, the aggregate follows the quantifier semantics of
§3.5.

### 3.7 Lookup tables

```
c in lookup('weak_algorithms')
name in lookup('default_community_names')
```

Declared as content, versioned with the control pack, campaign-pinned. Not
mutable at evaluation time.

A lookup against an unregistered table is a load-time error.

### 3.8 What is deliberately absent

| Absent | Reason |
|---|---|
| Loops, recursion | Termination guarantee |
| Function definition | Keeps the language auditable by a non-programmer assessor |
| Regular expressions constructed from data | Injection and backtracking risk |
| Arbitrary string formatting | Output-shaping belongs in reporting, not assertion |
| Date and time functions | D2 — no clock in evaluation |
| Random or sampling functions | D3 |
| Cross-device references | Device-scoped by design; cross-device analysis is the graph's role (TRD-04.2) |
| Nested quantifiers beyond depth 2 | Complexity bound; deeper logic indicates the control should be decomposed |

### 3.9 Evaluation trace

Every evaluation emits a trace, used by the report to explain *why*:

```
assert: telnet.enabled == false and http.enabled == false and ftp.enabled == false

trace:
  telnet.enabled == false   →  false   (explicit, line 143)
  http.enabled   == false   →  true    (default_known, IOS >= 15.0)
  ftp.enabled    == false   →  ⊥       (default_unknown)
  false and true and ⊥      →  false
result: FAIL
```

**INV-05.1-02 — The trace names the deciding term.** For a FAIL, the report must
say which conjunct failed. For an UNKNOWN, it must say which fact was
undetermined — that is what populates the Unassessed section (PRD 10 §2.6) with
an actionable reason rather than a bare count.

---

## 4. Interfaces

```
compile(source, schema_registry) → CompiledExpression | CompileError[]
evaluate(expr, fact_set, lookup_tables) → ⟨value ∈ {true, false, ⊥}, Trace⟩
type_of(expr, schema_registry) → Type | TypeError
```

Compilation happens once at control-pack load. Evaluation never parses.

---

## 5. Edge cases

| Case | Handling |
|---|---|
| Fact path valid in the schema but never produced by this platform's rulepack | `⊥` if the platform could produce it; `not_applicable` if the platform declares it absent |
| Division by zero | Compile-time rejection where detectable; `⊥` at runtime otherwise |
| Integer overflow | Arbitrary-precision integers; no wraparound |
| Comparing `algorithm` values with different spellings | Canonicalised at extraction (TRD-03.3 §3.3); comparison is on canonical identifiers |
| Empty collection with `all(p)` | `true` — vacuously satisfied. **This is why vacuity classification exists** (TRD-05.2) |
| Empty collection with `any(p)` | `false` |
| CIDR comparison across address families | Type error at compile time |
| Version comparison where precision is insufficient | `⊥` (TRD-01.2 INV-01.2-01) |

**The empty-collection case is subtle and important.** `all(ciphers, strong)`
over an empty configured cipher list is `true` — technically correct, and
security-meaningless. The language returns `true`; TRD-05.2's vacuity
classification is what prevents that from being reported as a meaningful pass.

---

## 6. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| `⊥` implemented as `false` in comparison | V-05.1-002 | **G2 violation.** Unknowns silently become passes — the product's central failure |
| Unknown collection treated as empty | V-05.1-004 | False PASS on `all` quantifiers |
| `count` short-circuiting on unknowns | V-05.1-003 | Wrong counts reported confidently |
| Scope aggregation defaulting to `any` | V-05.1-005 | Non-compliant scoped instances masked |
| Type error surfacing at evaluation rather than load | V-05.1-006 | A control silently never evaluates |
| Non-terminating expression | Impossible by construction | — |

---

## 7. Verification

```
V-05.1-001   Three-valued truth tables are correct
  Requirement  §3.2, G2
  Method       PROPERTY
  Procedure    Exhaustively evaluate and/or/not over all combinations of
               {true, false, ⊥}.
  Acceptance   Matches the specified tables exactly, including
               false and ⊥ = false and true and ⊥ = ⊥.
  Severity     BLOCKING
```

```
V-05.1-002   Comparison with unknown yields unknown, never false
  Requirement  §3.3, G2
  Method       PROPERTY
  Procedure    Generate comparisons of every operator against ⊥ operands
               across every type.
  Acceptance   100% yield ⊥. Zero yield false.
  Severity     BLOCKING
  Note         The most common three-valued implementation error, and the
               one that silently converts unknowns into passes.
```

```
V-05.1-003   Quantifier semantics under unknown
  Requirement  §3.5, DD-05.1-02
  Method       PROPERTY
  Procedure    Collections mixing true, false and ⊥ elements against
               all / any / none / count.
  Acceptance   all → false if any false, else ⊥ if any ⊥, else true.
               any  → true if any true, else ⊥ if any ⊥, else false.
               count → ⊥ if any element ⊥.
  Severity     BLOCKING
```

```
V-05.1-004   Unknown collection is not an empty collection
  Requirement  INV-05.1-01
  Method       UNIT
  Procedure    Evaluate all(c => c in ALLOWED) over (a) an explicitly empty
               list, (b) a list with provenance default_unknown.
  Acceptance   (a) true, flagged vacuous downstream. (b) ⊥.
               Zero cases where (b) returns true.
  Severity     BLOCKING
```

```
V-05.1-005   Scope aggregation defaults to all
  Requirement  DD-05.1-03
  Method       UNIT
  Procedure    Control without an explicit scope_aggregation, evaluated
               against a device with one compliant and one non-compliant
               VTY range.
  Acceptance   Verdict FAIL. Zero cases where a compliant instance masks a
               non-compliant one.
  Severity     BLOCKING
```

```
V-05.1-006   Type errors are caught at load, not evaluation
  Requirement  §3.4
  Method       UNIT
  Procedure    Load control packs containing type mismatches: boolean
               compared to integer, cross-family CIDR comparison, quantifier
               over a scalar.
  Acceptance   All rejected at load with the offending control named.
               Zero type errors reachable at evaluation.
  Severity     BLOCKING
```

```
V-05.1-007   No arbitrary code execution
  Requirement  NFR-SEC-007
  Method       UNIT + static analysis
  Procedure    Attempt assertions invoking I/O, imports, process execution,
               dynamic evaluation, unbounded recursion and clock access.
  Acceptance   All rejected at compile. The evaluator exposes no such
               capability at any call depth.
  Severity     BLOCKING
```

```
V-05.1-008   Evaluation is total and terminating
  Requirement  §3.1
  Method       PROPERTY
  Procedure    Evaluate every shipped control against 10,000 generated fact
               sets including adversarial shapes (deeply nested objects,
               very large collections, all-unknown sets).
  Acceptance   100% terminate. Zero timeouts. Zero exceptions escaping the
               evaluator.
  Severity     BLOCKING
```

```
V-05.1-009   Evaluation is deterministic
  Requirement  G1, D1, D3
  Method       PROPERTY
  Procedure    Evaluate all controls against the corpus 10 times with varied
               fact-set iteration order.
  Acceptance   Identical values and identical traces every run.
  Severity     BLOCKING
```

```
V-05.1-010   Traces name the deciding term
  Requirement  INV-05.1-02
  Method       CORPUS
  Procedure    Evaluate all controls across the corpus; inspect traces for
               every FAIL and every UNKNOWN.
  Acceptance   100% of FAIL traces identify the failing conjunct.
               100% of UNKNOWN traces identify the undetermined fact path.
  Severity     BLOCKING
  Note         This populates the report's Unassessed section with reasons
               rather than counts.
```

```
V-05.1-011   No clock, randomness or external state is reachable
  Requirement  D2, D3
  Method       INTEGRATION
  Procedure    Evaluate the full control set with the system clock advanced
               by one year between runs.
  Acceptance   Identical results and traces.
  Severity     BLOCKING
```

---

## 8. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should a strict mode treat `false and ⊥` as `⊥`, requiring complete knowledge before any definite verdict? | Strictness is philosophically cleaner but would suppress real findings whenever any adjacent fact is unknown — most findings on partially-parsed devices would vanish. Current design: Kleene semantics as specified |
| Q2 | Should nested quantifier depth beyond 2 be permitted for genuinely complex controls? | Deeper nesting is occasionally justified but usually signals that the control should be decomposed into named intermediate facts. Current design: depth 2, with derived facts as the escape hatch |
| Q3 | Should lookup tables be shareable across control packs? | Sharing prevents divergent weak-algorithm lists, but creates cross-pack dependencies that complicate import and pinning. Current design: pack-local, reconciled on import |
