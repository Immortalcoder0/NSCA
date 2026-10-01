# TRD-02.2 · Grammar Inference

---

## 1. Scope

Statistical recovery of an unknown configuration format's **structure**, with no
human input and no model inference, producing a grammar hypothesis usable by
TRD-02.1.

This is the subsystem that makes the training loop tractable: it removes the
syntactic problem entirely, leaving only the semantic problem for a human.

**Out of scope:** semantic mapping (TRD-08.2); rule synthesis (TRD-08.3).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-PRS-012 | Automatic grammar inference for unknown platforms |
| FR-PRS-013 | Inference coverage reporting |
| FR-LRN-001 | Enables the training workflow rather than failing |
| NFR-DEP-001 | Runs entirely offline; no model involved |

---

## 3. Design

### 3.1 The governing separation

> **Syntax is inferable statistically. Semantics is not.**

This separation is what makes the whole learning system practical. Structure has
an objectively checkable success criterion — *does the grammar account for every
line?* — and can therefore be searched automatically. Meaning has no such
criterion and requires a human.

Inference stops precisely at the boundary: it produces a complete parse tree in
which nothing has meaning.

**DD-02.2-01 — No model is used in grammar inference.** Two reasons: it must
function in an air-gapped deployment before any teaching has occurred, and its
output is objectively verifiable, which makes a statistical method both
sufficient and preferable.

### 3.2 Inference pipeline

```
  artifact text
      │
  1  comment character detection
      │
  2  verbatim region detection
      │
  3  paradigm hypothesis generation and scoring   ← the core step
      │
  4  statement shape detection
      │
  5  verb and selector detection
      │
  6  grammar assembly and validation
      │
  grammar hypothesis + coverage
```

### 3.3 Step 1 — Comment character

A comment character prefixes lines that (a) never contain the format's assignment
structure and (b) exhibit high natural-language token entropy.

```
for each candidate c ∈ { #, !, ;, //, /*, --, " }:
    L_c    = lines beginning with c
    if |L_c| < 2: skip
    assign_rate = fraction of L_c containing '=' or ':' or multiple tokens
                  in a repeated positional pattern
    entropy     = mean token entropy of L_c
    score(c)    = entropy · (1 − assign_rate) · log(1 + |L_c|)

comment_char = argmax score, if score > threshold
```

**The `log(1 + |L_c|)` term matters.** Without it, a single stray line beginning
with an unusual character outscores the real comment character in a configuration
that happens to have few comments.

### 3.4 Step 2 — Verbatim regions

Detected before paradigm scoring, because unrecognised verbatim content
(certificates, banners, keys) severely distorts structural statistics.

| Region | Signature |
|---|---|
| PEM block | `-----BEGIN … -----` / `-----END … -----` |
| Base64 run | ≥ 3 consecutive lines of ≥ 40 chars, base64 alphabet, no separators |
| Delimited banner | A repeated non-alphanumeric delimiter opening and closing a multi-line region |

Verbatim regions are excluded from statistics and re-attached as single nodes
afterwards.

### 3.5 Step 3 — Paradigm hypothesis scoring

Each of the six paradigms is scored; the highest wins if it clears both an
absolute threshold and a margin.

| Paradigm | Evidence | Score components |
|---|---|---|
| **Indentation** | Multi-modal leading-whitespace distribution with a stable unit | Distinct depth levels ≥ 2; consistent unit; ≥ 20% of lines indented |
| **Flat path** | A single verb prefix on ≥ 70% of lines; deep common prefixes | Verb dominance; mean common-prefix length ≥ 2 |
| **Brace** | Balanced `{`/`}` outside strings; `;` line terminators | Balance = 0; nesting depth ≥ 2 |
| **Block keyword** | Repeated paired open/close tokens with consistent nesting | Balanced pairs; ≥ 2 distinct pair types is stronger evidence |
| **XML** | Well-formed document | Binary |
| **Path header** | Lines beginning with a delimiter that carry no value, followed by lines that do | Header/body alternation ratio |

```
score(paradigm) = Σ evidence weights, normalised to [0,1]

if best ≥ 0.70 and (best − second) ≥ 0.15  →  accept
otherwise                                   →  ambiguous, escalate
```

**DD-02.2-02 — Ambiguity escalates rather than defaults.** Choosing the wrong
paradigm produces a plausible tree with wrong structure, which is worse than
declaring the format unhandled. Same principle as fingerprinting (TRD-01.2
DD-01.2-02).

#### Worked example — MikroTik RouterOS

```
# aug/25/2026 by RouterOS 7.11.2
/ip service
set telnet disabled=no port=23
set ssh disabled=no port=22
/snmp community
set [ find default=yes ] name=public read-access=yes
```

| Paradigm | Score | Reason |
|---|---|---|
| Indentation | 0.08 | Almost all lines at depth 0 |
| Flat path | 0.31 | Two verbs, no deep common prefixes |
| Brace | 0.00 | No braces |
| Block keyword | 0.05 | No paired tokens |
| XML | 0.00 | Not well-formed |
| **Path header** | **0.89** | `/`-prefixed valueless lines followed by value-bearing lines |

Accepted: margin 0.58, well clear.

### 3.6 Step 4 — Statement shape

Within the chosen paradigm, determine how a statement expresses its content.

```
separator_density(s) = occurrences of s per statement line, for s ∈ { =, :, space }

if '=' density ≥ 0.8      →  key_value        key=value pairs
elif ':' density ≥ 0.8    →  colon_key_value
else                      →  positional       token order carries meaning
```

Quoting convention is detected by counting balanced quote pairs containing
whitespace. Continuation is detected by trailing-backslash frequency.

### 3.7 Step 5 — Verbs and selectors

**Verbs.** Leading tokens appearing in the first position of ≥ 10% of statement
lines with a small closed vocabulary (≤ 8 distinct values) are verbs.

```
RouterOS  → { set, add, remove }
Juniper   → { set, delete, deactivate }
FortiOS   → { set, unset, config, edit, next, end }
```

**Selectors.** Bracketed or predicate-shaped sub-expressions appearing in a
consistent position:

```
set [ find default=yes ] name=public
    └────────┬────────┘
          selector — an operand, not an attribute
```

**Misclassifying a selector as attributes is a common inference error** and
produces spurious facts. Selectors are recognised by enclosure characters and by
containing their own key-value content in a position preceding the statement's
own attributes.

### 3.8 Step 6 — Assembly and validation

The assembled grammar is fed to TRD-02.1 and validated by coverage.

```
grammar = { comment_char, paradigm, statement_shape, verbs,
            selectors, quoting, continuation, verbatim_regions }

coverage = parse(artifact, grammar).coverage
```

| Coverage | Outcome |
|---|---|
| ≥ 0.95 | Accept |
| 0.80 – 0.95 | Accept with gaps; unmatched routed to training |
| 0.50 – 0.80 | Accept with warning; assisted authoring offered |
| < 0.50 | **Reject.** Assisted grammar authoring required |

```
⚠ Grammar inference achieved 43% line coverage on RTR-Pune-02.
  Structure could not be reliably determined.
  → Assisted grammar authoring required, or supply an alternative
    export format.
```

**INV-02.2-01.** A rejected grammar produces no nodes, no facts and no findings.
An unreliable grammar is worse than none (G2).

### 3.9 Corroboration across artifacts

Where several artifacts of the same unknown platform are present, inference runs
on each and the results are compared. Agreement raises confidence; disagreement
indicates either misfingerprinting or genuinely different export formats, and is
surfaced.

```
infer_platform(artifacts) →
  hypotheses = [ infer(a) for a in artifacts ]
  if all paradigms agree      → merge, confidence ↑
  if paradigms disagree       → escalate; likely two platforms
```

This is cheap and materially improves reliability — a single small artifact is a
weak statistical sample.

---

## 4. Interfaces

**Input:** `⟨artifact_id, normalised_content⟩`, plus sibling artifacts of the
same unknown platform where available.

**Output**

```
GrammarHypothesis {
  comment_char, paradigm, paradigm_confidence
  statement_shape, quoting, continuation
  verbs[], selectors[]
  verbatim_regions[]
  coverage: ratio
  status: accepted | accepted_with_gaps | warning | rejected
  paradigm_scores[]                 // all six, for explainability
  corroborating_artifacts: int
}
```

`paradigm_scores[]` is required for explainability: when inference is wrong, an
engineer must be able to see why without re-running it.

---

## 5. Edge cases

| Case | Handling |
|---|---|
| Configuration with fewer than 20 statement lines | Statistics unreliable; confidence capped at 0.5; corroboration sought |
| Two paradigms genuinely combined (FortiOS: block keywords **and** key-value statements) | Paradigm and statement shape are independent axes; this composes correctly by design |
| Format using significant whitespace *and* braces | Both score; margin rule escalates |
| Configuration that is mostly comments | Comment detection succeeds; statement statistics weak; confidence capped |
| Binary or partially binary artifact | Rejected at intake (TRD-01.1) before inference |
| Format where the comment character also appears as an operator | Comment detection's assign-rate term suppresses it |
| Very regular XML-like format that is not well-formed XML | XML scores 0; falls to another paradigm or escalates |

**The FortiOS case is worth noting** because it is the one that breaks naïve
implementations: `config`/`end` blocks contain `set key value` statements. If
paradigm and statement shape are conflated into a single classification, no
single label fits. Keeping them orthogonal handles it without special-casing.

---

## 6. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Wrong paradigm accepted | Coverage below threshold | Rejected or warned; never silently used |
| Paradigm right, statement shape wrong | Attributes mis-extracted; unmatched elevated | Surfaces as training queue noise |
| Selector read as attributes | Spurious attribute keys | Detected during rule synthesis validation (TRD-08.3) |
| Verbatim region undetected | Coverage depressed; unmatched inflated | Visible in coverage; assisted authoring offered |
| Small-sample overfitting | Confidence cap; corroboration | Conservative confidence |
| Inference non-determinism | Property test | D3/D6 apply — no randomness, explicit ordering |

---

## 7. Verification

```
V-02.2-001   Paradigm identification on held-out platforms
  Requirement  FR-PRS-012
  Method       CORPUS
  Procedure    For each of ≥ 6 platforms, remove its rulepack and run
               inference on ≥ 10 of its artifacts.
  Acceptance   Correct paradigm for ≥ 90% of artifacts. Zero incorrect
               paradigms accepted at confidence ≥ 0.70 — incorrect results
               must escalate as ambiguous, not be accepted.
  Severity     BLOCKING
```

```
V-02.2-002   Inferred grammar achieves usable coverage
  Requirement  FR-PRS-012, FR-PRS-013
  Method       CORPUS
  Procedure    Parse held-out platform artifacts using only the inferred
               grammar.
  Acceptance   Median coverage ≥ 0.90. No artifact accepted below 0.50.
  Severity     BLOCKING
```

```
V-02.2-003   Ambiguous paradigm escalates
  Requirement  DD-02.2-02
  Method       UNIT
  Procedure    Construct artifacts scoring within 0.15 for two paradigms.
  Acceptance   status = rejected or warning with assisted authoring offered.
               Never silently accepted.
  Severity     BLOCKING
```

```
V-02.2-004   Rejected grammar produces nothing downstream
  Requirement  INV-02.2-01, G2
  Method       INTEGRATION
  Procedure    Ingest an artifact for which inference yields < 0.50 coverage.
  Acceptance   Zero nodes, zero facts, zero findings. Device appears in
               completeness as missing with reason `format_unrecognised`.
  Severity     BLOCKING
```

```
V-02.2-005   No model is invoked during inference
  Requirement  DD-02.2-01, NFR-DEP-001
  Method       INTEGRATION
  Procedure    Run inference across all held-out platforms with all model
               endpoints unreachable and local inference disabled.
  Acceptance   Identical results to a run with models available.
               Zero inference calls recorded.
  Severity     BLOCKING
```

```
V-02.2-006   Verbatim region detection prevents statistical distortion
  Requirement  §3.4
  Method       UNIT + CORPUS
  Procedure    Infer on artifacts containing PEM certificate blocks and
               delimited banners. Compare paradigm scores against the same
               artifacts with those regions removed.
  Acceptance   Paradigm choice identical. Score deviation ≤ 0.05.
  Severity     MAJOR
```

```
V-02.2-007   Orthogonal paradigm and statement shape handle FortiOS
  Requirement  §5
  Method       UNIT
  Procedure    Infer on FortiOS artifacts.
  Acceptance   paradigm = block_keyword, statement_shape = positional,
               verbs include config/edit/next/end. Coverage ≥ 0.95.
  Severity     MAJOR
```

```
V-02.2-008   Selectors are not misclassified as attributes
  Requirement  §3.7
  Method       UNIT
  Procedure    Infer on RouterOS artifacts containing `[ find … ]` selectors.
  Acceptance   Selector content appears as a selector operand.
               Zero attribute keys derived from selector interiors.
  Severity     MAJOR
```

```
V-02.2-009   Inference is deterministic
  Requirement  G1, D3, D6
  Method       PROPERTY
  Procedure    Run inference on all held-out artifacts 10 times.
  Acceptance   Identical grammar, identical paradigm_scores, identical
               coverage every run.
  Severity     BLOCKING
```

```
V-02.2-010   Corroboration across sibling artifacts raises reliability
  Requirement  §3.9
  Method       CORPUS
  Procedure    Infer on single artifacts versus sets of ≥ 5 sibling artifacts
               for the same held-out platform.
  Acceptance   Set-based inference paradigm accuracy ≥ single-artifact
               accuracy. Disagreement escalates rather than voting silently.
  Severity     MINOR
```

```
V-02.2-011   Inference performance
  Requirement  NFR-PERF-007
  Method       PERFORMANCE
  Procedure    Infer on a 10,000-line artifact, reference profile.
  Acceptance   < 10 s.
  Severity     MINOR
```

---

## 8. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should inference attempt to *learn* a paradigm not in the six, rather than escalating? | General grammar induction is a research problem with weak guarantees; the six paradigms cover the realistic space. Current design: escalate to assisted authoring |
| Q2 | Should assisted grammar authoring be a distinct UI, or an extension of the Training Studio? | A separate tool is clearer for a rare, technical task; an extension avoids a second interface. Current design: extension, gated to Platform Administrator |
| Q3 | Should an inferred grammar be promoted to a rulepack automatically once teaching completes? | Automatic promotion is convenient but bypasses ratification. Current design: the grammar becomes part of the provisional rulepack and is ratified with it |
