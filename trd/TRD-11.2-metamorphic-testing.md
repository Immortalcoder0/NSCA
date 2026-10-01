# TRD-11.2 · Metamorphic Testing

---

## 1. Scope

The mutation catalogue, the relations asserted, and the execution model for
metamorphic testing — the method that finds defects **no hand-written test would
catch, because you would never have thought to write it.**

---

## 2. The idea

Conventional testing verifies inputs you thought of. Metamorphic testing verifies
inputs you did not, by asserting that transformations which *should not* change
the answer *do not* change the answer.

```
∀ configuration c, ∀ semantics-preserving mutation m :
        facts(parse(m(c)))  ==  facts(parse(c))
```

For a configuration parser this is disproportionately powerful. Reorder blocks,
rename objects, abbreviate commands, alter whitespace — the extracted facts must
be identical. **Any difference is a defect.**

No oracle is required. You do not need to know the correct answer; you only need
to know that two inputs have the same answer.

---

## 3. Requirements satisfied

| PRD | How |
|---|---|
| NFR-REL-005 | Metamorphic validation |
| FR-LRN-010, 011 | Synthesis-time rule robustness (TRD-08.3 Gate 6) |
| G1 | Stability under semantically irrelevant variation |

---

## 4. Mutation catalogue

Grouped by the relation they test. **Grammar-aware**: a mutation the platform's
grammar forbids is skipped rather than applied and expected to fail.

### 4.1 Lexical — facts must be identical

| Mutation | Example |
|---|---|
| Whitespace variation | `set  telnet   disabled=no` |
| Indentation width | 1-space → 2-space where the grammar permits |
| Tab/space substitution | Within the declared tab width |
| Line ending | LF ↔ CRLF |
| Trailing whitespace | Added or removed |
| Blank line insertion | Between statements |
| Comment insertion | Between statements, using the grammar's comment character |
| Case variation | Keywords only, on case-insensitive platforms |
| Quoting variation | `"value"` ↔ `value` where equivalent |

### 4.2 Structural — facts must be identical

| Mutation | Example |
|---|---|
| Sibling block reordering | Two `interface` blocks swapped |
| Attribute reordering | `port=23 disabled=no` ↔ `disabled=no port=23` |
| Statement reordering within a block | Where the grammar makes order insignificant |
| Object definition reordering | Address objects declared in a different sequence |

**DD-11.2-01 — Order-significant constructs are excluded, and the exclusion is
declared, not inferred.** `filter.rules[]` is first-match ordered; reordering
firewall rules changes the policy. The mutation engine consults the rulepack's
declaration of which constructs are order-significant.

Getting this wrong in either direction is costly: mutating an order-significant
construct produces false failures; failing to mutate an order-insignificant one
loses coverage.

### 4.3 Naming — facts must be identical modulo the renaming

| Mutation | Example |
|---|---|
| Object rename | `Trusted-Admins` → `OBJ-A1`, consistently everywhere |
| Interface rename | Where the platform permits arbitrary names |
| Hostname change | — |
| Address substitution | Consistent, preserving family and prefix length |

Relation is **isomorphism**, not equality: fact values referencing the renamed
entity change correspondingly, and the graph structure is preserved.

### 4.4 Syntactic equivalence — facts must be identical

| Mutation | Example |
|---|---|
| Command abbreviation | `interface GigabitEthernet0/1` ↔ `int gi0/1` |
| Equivalent forms | Juniper set-format ↔ curly-format for the same configuration |
| Wildcard/netmask | `0.0.0.255` ↔ `/24` where equivalent |
| Numeric formatting | `08` ↔ `8` where the grammar permits |

**Abbreviation is the highest-yield mutation in this group.** A pattern written
against the expanded form fails silently on abbreviated configurations, which
management-platform exports frequently produce. The failure is invisible — the
fact is simply never emitted, coverage drops slightly, and nobody notices.

### 4.5 Additive — facts must be a superset

| Mutation | Relation |
|---|---|
| Add an unrelated block | Existing facts unchanged; new facts may appear |
| Add a comment block | Facts unchanged |
| Add an unused object | Existing facts unchanged |

### 4.6 Semantic negation — the verdict must flip

The inverse relation, and the one that catches polarity errors.

| Mutation | Expected |
|---|---|
| `transport input ssh` → `transport input telnet ssh` | `telnet.enabled` false → true |
| `set telnet disabled=yes` → `disabled=no` | false → true |
| `set admin-telnet disable` → `enable` | false → true |

**INV-11.2-01 — Negation mutations must flip the fact.** A fact that does *not*
flip when its source is negated indicates the extractor is not reading that
construct at all — or is reading it with inverted polarity.

This is the automated check against the product's highest-consequence error
class, and it is the reason §4.6 exists as a distinct mutation family rather than
being folded into ordinary testing.

---

## 5. Relations asserted

| Relation | Applies to | Assertion |
|---|---|---|
| **Identity** | §4.1, §4.2, §4.4 | Fact sets byte-identical, provenance line numbers adjusted |
| **Isomorphism** | §4.3 | Fact sets equal under the renaming; graph structure preserved |
| **Superset** | §4.5 | Original facts present and unchanged |
| **Negation** | §4.6 | The targeted fact flips; all others unchanged |

**Provenance line numbers legitimately change** under mutations that add or
remove lines. The relation is over fact *paths and values*, with provenance
compared after adjusting for the mutation's line-offset effect.

---

## 6. Execution model

### 6.1 Two execution points

| Point | Scale | Purpose |
|---|---|---|
| **Rule synthesis** (TRD-08.3 Gate 6) | ~1,000 mutations of the matched lines | Catch a whitespace-brittle rule before it is saved |
| **Nightly** | Full corpus × full catalogue | Catch defects across the whole knowledge base |

Catching a brittle rule at synthesis costs seconds. Catching it six weeks later
costs a report amendment (TRD-09.1 §3.8).

### 6.2 Generation

```
generate(artifact, grammar, catalogue) →
  applicable = mutations permitted by this grammar
             minus mutations of order-significant constructs
  for each mutation family:
      sample deterministically, seeded from artifact hash
```

**INV-11.2-02 — Mutation generation is deterministic.** Seeded from the artifact
hash, so a failure is reproducible from the artifact identifier alone (D3). A
metamorphic failure that cannot be reproduced is not actionable.

### 6.3 Failure triage

A failure yields the original, the mutation applied, and the fact-set difference:

```
METAMORPHIC FAILURE
  artifact   ART-004121 (cisco_iosxe)
  mutation   command_abbreviation: interface GigabitEthernet0/1 → int gi0/1
  extractor  cisco_iosxe.interface.description@4

  Expected   topology.interfaces[3].description = "Uplink to Router"
  Actual     fact absent

  Diagnosis  Pattern anchored to the expanded form. The rulepack's
             abbreviation expansion table is missing `gi`.
```

**Failures are almost always actionable and specific**, because the mutation
isolates the cause. This is the practical advantage over property testing on
random inputs, where a failure often requires substantial shrinking to interpret.

### 6.4 Budget

| Scope | Mutations |
|---|---|
| Per rule at synthesis | 1,000 |
| Per corpus artifact nightly | 500 across all families |
| Full nightly run | ≤ 2 h on the reference CI profile |

Sampling is stratified across families so that no family is starved by a large
one.

---

## 7. What metamorphic testing does not catch

Stated explicitly, because a method this effective invites over-reliance.

| Not caught | Why | Covered by |
|---|---|---|
| A wrong default value | Consistent under every mutation | Differential testing (TRD-11.1 §4.6) |
| A wrong control requirement | Mutation does not change the control | Expert review |
| A consistently inverted polarity in the *control*, not the extractor | Negation mutations flip the fact correctly; the control is wrong | Control fixtures, expert review |
| Missing coverage of a construct entirely | Nothing to mutate | Corpus coverage reporting |
| A wrong framework mapping | Not a parsing property | Equivalence rationale review |

**Metamorphic testing establishes robustness, not correctness.** A parser can be
perfectly stable under every mutation and still describe the device incorrectly.
Only differential testing settles correctness.

---

## 8. Interfaces

```
mutate(artifact, grammar, family, seed) → MutatedArtifact
assert_relation(original_facts, mutated_facts, relation) → Result
run_synthesis_check(rule, matched_lines) → Gate6Result
run_nightly(corpus) → MetamorphicReport
```

---

## 9. Verification

```
V-11.2-001   Semantics-preserving mutation produces identical facts
  Requirement  NFR-REL-005
  Method       METAMORPHIC (CI gate)
  Procedure    Apply the full catalogue across the full corpus. Assert the
               declared relation for each family.
  Acceptance   Zero identity-relation violations. Zero isomorphism
               violations. Zero superset violations.
  Severity     BLOCKING
  Note         Referenced in the TRD README as one of the five criteria that
               prove the product's central claims.
```

```
V-11.2-002   Negation mutations flip the targeted fact
  Requirement  INV-11.2-01
  Method       METAMORPHIC
  Procedure    Apply §4.6 mutations to every boolean fact extractable from
               the corpus.
  Acceptance   100% of targeted facts flip. Zero facts remain unchanged.
               Zero unrelated facts change.
  Severity     BLOCKING
  Note         This is the automated check against inverted polarity.
```

```
V-11.2-003   Order-significant constructs are excluded from reordering
  Requirement  DD-11.2-01
  Method       UNIT
  Procedure    Attempt rule-reordering mutations on filter.rules[] and on
               order-insignificant blocks.
  Acceptance   Reordering skipped for order-significant constructs, applied
               to others. Exclusions read from rulepack declarations, not
               inferred.
  Severity     BLOCKING
```

```
V-11.2-004   Abbreviation mutations are applied and pass
  Requirement  §4.4, FR-PRS-011
  Method       METAMORPHIC + CORPUS
  Procedure    Apply abbreviation mutations across all Cisco-family corpus
               artifacts.
  Acceptance   Identical facts. Any expansion-table gap surfaces as a
               specific, diagnosable failure.
  Severity     BLOCKING
```

```
V-11.2-005   Mutation generation is deterministic and reproducible
  Requirement  INV-11.2-02, D3
  Method       PROPERTY
  Procedure    Generate mutations for the same artifacts 10 times.
  Acceptance   Identical mutation sets. Every failure reproducible from
               artifact id, family and seed alone.
  Severity     BLOCKING
```

```
V-11.2-006   Synthesis-time checking blocks brittle rules
  Requirement  TRD-08.3 Gate 6, DD-11.2-01
  Method       INTEGRATION
  Procedure    Synthesise a rule anchored to exact whitespace. Run Gate 6.
  Acceptance   Gate 6 fails. Rule not saved. The failing mutation shown to
               the administrator.
  Severity     BLOCKING
```

```
V-11.2-007   Provenance adjusts correctly under line-shifting mutations
  Requirement  §5
  Method       METAMORPHIC
  Procedure    Apply blank-line and comment-insertion mutations.
  Acceptance   Fact paths and values identical. Provenance line numbers
               shifted by exactly the mutation's offset. Excerpts still
               resolve to matching text.
  Severity     BLOCKING
```

```
V-11.2-008   Grammar-forbidden mutations are skipped, not failed
  Requirement  §4
  Method       UNIT
  Procedure    Attempt case-variation mutations on a case-sensitive platform
               and quoting mutations where the grammar forbids them.
  Acceptance   Skipped and recorded as inapplicable. Zero false failures.
  Severity     MAJOR
```

```
V-11.2-009   Sampling is stratified across families
  Requirement  §6.4
  Method       INTEGRATION
  Procedure    Run a nightly cycle; inspect the mutation distribution.
  Acceptance   Every applicable family represented. No family below 5% of
               the artifact's mutation budget.
  Severity     MINOR
```

```
V-11.2-010   Nightly run stays within budget
  Requirement  §6.4
  Method       PERFORMANCE
  Procedure    Full nightly cycle on the reference CI profile.
  Acceptance   ≤ 2 h. Full corpus and full catalogue covered.
  Severity     MINOR
```

---

## 10. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should mutations be generated for controls as well as extractors — perturbing fact sets to check verdict stability? | Would extend the method to the evaluation layer, but fact-set perturbation is closer to property testing and the relation is harder to define. Current design: extractors and parsing only; control stability covered by property tests |
| Q2 | Should cross-format mutation (Juniper set ↔ curly) be a standard family or a special case? | It is the strongest available check that the neutral schema genuinely abstracts syntax, but only two platforms support both forms. Current design: standard family where the grammar declares an equivalent form |
| Q3 | Should synthesis-time budget scale with rule complexity? | A complex rule warrants more mutations, but administrators are waiting during synthesis. Current design: fixed 1,000, with full coverage deferred to the nightly run |
