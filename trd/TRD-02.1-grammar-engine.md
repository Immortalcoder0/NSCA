# TRD-02.1 · Grammar Engine and Parse Tree

---

## 1. Scope

Conversion of normalised artifact text into a typed parse tree, across six
structural paradigms plus natively structured input. Definition of the parse tree
contract that every downstream subsystem depends upon.

**Out of scope:** inferring a grammar for an unknown platform (TRD-02.2);
resolving inheritance and overrides (TRD-02.3); assigning semantic meaning
(TRD-03.1).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-PRS-001…007 | Six paradigms plus structured input |
| FR-PRS-008 | Every node retains its source line range |
| FR-PRS-011 | Command abbreviation handling |
| FR-PRS-013 | Grammar coverage reporting |
| FR-PRS-014 | Unmatched lines retained, never discarded |
| G3 | Line-range retention is the root of evidence binding |

---

## 3. Design

### 3.1 The parse tree contract

Every paradigm produces the same structure. Downstream subsystems are written
against this contract and are paradigm-agnostic.

```
Node {
  id          : stable within the parse
  parent      : Node | ⊥
  children    : Node[]                    // ordered, source order
  path        : string[]                  // hierarchical address from root
  verb        : string | ⊥                // add / set / delete / ⊥
  head        : string                    // the significant leading token(s)
  attributes  : map<string, Value>        // key=value pairs, if any
  operands    : Value[]                   // positional operands, if any
  raw         : string                    // verbatim source line(s)
  lines       : ⟨first, last⟩             // 1-indexed, post-normalisation
  kind        : statement | container | comment | blank | unmatched
}
```

**INV-02.1-01 — Line binding.** Every node carries a line range that resolves to
the exact text in the artifact. This is the foundation of G3: a fact's evidence
is ultimately a node's line range.

**INV-02.1-02 — Total coverage.** Every line of the artifact belongs to exactly
one node. Nothing is dropped. Lines matching no production become `unmatched`
nodes, which is how FR-PRS-014 is satisfied structurally rather than by
convention.

```
∀ line ∈ artifact : ∃! node ∈ tree : line ∈ node.lines
```

### 3.2 The two-phase model

```
  text ──► LEX ──► token stream ──► STRUCTURE ──► parse tree
             │                          │
        comments, strings,        paradigm-specific
        continuations,            nesting rules
        quoting
```

**DD-02.1-01 — Lexing is paradigm-independent; structuring is not.** Comment
detection, quoting and line continuation behave consistently enough across
platforms to share one lexer parameterised by the rulepack grammar block.
Nesting does not, and each paradigm implements its own structurer.

This split means adding a paradigm is one structurer, not a whole parser.

### 3.3 Paradigm structurers

#### P1 · Indentation (Cisco family, Arista)

Depth from leading whitespace; `!` or blank returns to depth 0.

```
line vty 0 4              depth 0  container
 login local              depth 1  statement, parent = line vty 0 4
 transport input ssh      depth 1  statement
!                                  comment, closes container
```

Hazards: mixed tabs and spaces; continuation lines in banners; `!` appearing
inside a banner body.

**Banner handling is special-cased.** A banner delimiter opens a verbatim region
in which no structural interpretation occurs until the closing delimiter. Without
this, a banner containing `!` or indented text corrupts the tree — and banners
routinely contain both.

#### P2 · Flat path statements (Juniper set-format)

Each line is a complete path. The tree is reconstructed by common-prefix merging.

```
set system services ssh protocol-version v2
set system services ssh root-login deny
        │
        ▼
system → services → ssh → { protocol-version: v2, root-login: deny }
```

**DD-02.1-02.** `delete` lines are retained as nodes with `verb: delete`, not
applied as deletions during structuring. Application is TRD-02.3's
responsibility, because a `delete` may target something introduced by an
inherited group.

#### P3 · Brace nesting (Juniper curly-format)

Conventional block nesting; statements terminated by `;`.

Hazards: braces inside quoted strings; comments (`/* */` and `#`) inside blocks.

#### P4 · Block keywords (FortiOS)

```
config system global          container open
    set admin-telnet disable  statement
end                           container close

config firewall policy        container open
    edit 1                    sub-container open
        set srcintf "wan1"
    next                      sub-container close
end
```

Two nesting mechanisms operating simultaneously (`config`/`end` and
`edit`/`next`). **An unbalanced `end` changes the meaning of everything
following it**, so imbalance is a hard parse error rather than a recovery case.

#### P5 · XML (PAN-OS)

Direct mapping: element → node, attribute → attribute, text → operand. Line
ranges come from the parser's position tracking, which must be enabled — many
XML parsers discard it by default, and without it G3 is unsatisfiable.

#### P6 · Path headers with key-value (MikroTik RouterOS)

```
/ip service                                  container
set telnet disabled=no port=23               statement, verb=set
```

A `/path` line opens a container that persists until the next `/path`. Bracketed
selectors (`[ find default=yes ]`) are parsed as a selector operand, not as
attributes.

#### P7 · Native structured (cloud policy JSON)

Already a tree. Line ranges from a position-preserving JSON parse.

**These are the easiest inputs to support and are explicitly listed in the
problem statement's vendor set** — cloud-native firewalls and SASE platforms.
A CLI-only implementation fails a stated requirement.

### 3.4 Command abbreviation

FR-PRS-011. Real configurations contain abbreviated forms, particularly when
retrieved through management platforms.

```
int gi0/1              ≡  interface GigabitEthernet0/1
no sh                  ≡  no shutdown
```

Expansion is applied at lex time using the rulepack's declared expansion table.

**INV-02.1-03.** `raw` retains the abbreviated source text; `head` holds the
expanded canonical form. Evidence excerpts show what the operator actually wrote;
matching operates on the canonical form.

This matters for both correctness and credibility: an assessor shown an excerpt
that does not match their configuration file will not trust the tool.

### 3.5 Grammar coverage

FR-PRS-013.

```
coverage = (lines assigned to non-unmatched nodes) / (total non-blank lines)
```

| Coverage | Interpretation | Action |
|---|---|---|
| ≥ 0.95 | Healthy | Proceed |
| 0.80 – 0.95 | Gaps present | Proceed; unmatched routed to training |
| 0.50 – 0.80 | Substantial gaps | Proceed with a report warning |
| < 0.50 | Grammar likely wrong | **Refuse.** Escalate as a fingerprint or grammar failure |

**DD-02.1-03 — Refusal below 0.50.** A grammar that matches less than half an
artifact is probably the wrong grammar, and a wrong grammar produces plausible
but incorrect nodes. Refusing is safer than producing facts nobody can trust
(G2).

### 3.6 Error recovery

Structuring never aborts on a single bad line. Recovery is per-paradigm:

| Paradigm | Unrecoverable condition |
|---|---|
| Indentation | None — bad lines become `unmatched` at their observed depth |
| Flat path | None |
| Brace | Unbalanced braces at end of input → hard error |
| Block keyword | Unbalanced `config`/`end` → hard error |
| XML | Malformed document → hard error |
| Path header | None |

**DD-02.1-04.** Paradigms whose imbalance changes the meaning of subsequent
content fail hard; paradigms where a bad line is locally contained recover. The
distinction is whether the error is *local* or *contaminating*.

### 3.7 Streaming for large artifacts

NFR-PERF-003 requires handling 500,000-line configurations. Structuring is
single-pass and streaming; only the open-container stack is held in memory.

Large firewall policy sets are the realistic case — a full node materialisation
of a 100,000-rule policy exceeds practical memory if nodes carry raw text.
`raw` is therefore stored as an offset pair into the artifact and materialised on
demand.

---

## 4. Interfaces

**Input:** `⟨artifact_id, normalised_content, grammar⟩`, grammar supplied by the
rulepack (TRD-01.2 KNOWN) or by inference (TRD-02.2).

**Output**

```
ParseResult {
  tree: Node                       // root
  coverage: ratio                  // exact integer pair, not float (D5)
  unmatched[]: ⟨lines, raw, enclosing_path⟩
  errors[]: ⟨line, code, message⟩
  status: parsed | parsed_with_gaps | refused
  paradigm_used
  node_count, max_depth
}
```

`unmatched[]` carries `enclosing_path` because the training system needs section
context to group templates meaningfully (TRD-08.1).

**Downstream contract:** TRD-02.3 consumes the tree and produces an effective
tree; TRD-03.1 consumes the effective tree. Neither may assume a paradigm.

---

## 5. Edge cases

| Case | Handling |
|---|---|
| Banner containing `!`, braces, or indented text | Verbatim region; no structural interpretation until the closing delimiter |
| Mixed tabs and spaces | Tab expanded to the grammar's declared tab width; mixing recorded |
| Certificate or key block embedded in configuration | Recognised as a verbatim region by its BEGIN/END markers |
| Line exceeding 64 KB | Accepted; flagged; typically a certificate or a very large object group |
| Config with Windows CRLF inside a quoted string | Preserved inside quotes, normalised outside |
| Empty container (`config system global` immediately followed by `end`) | Valid container node with no children |
| Duplicate keys in the same block | Both retained as separate nodes; resolution is TRD-02.3's concern |
| XML with namespaces | Namespaces preserved in `path`; matching is namespace-aware |
| JSON policy with unordered keys | Ordered deterministically by key for tree construction (D6) |

**The certificate-block case is a frequent source of corruption.** A PEM block
contains base64 text that can resemble indented statements. Without verbatim
handling, a certificate produces dozens of spurious `unmatched` nodes and
depresses coverage below the warning threshold.

---

## 6. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Wrong grammar applied | Coverage collapse | Refused below 0.50 (DD-02.1-03) |
| Banner mis-parsed | Structural anomaly; coverage dip | Verbatim regions; V-02.1-004 |
| Unbalanced block delimiters | Structurer detects at end of input | Hard error; artifact not assessed |
| Line-range drift after abbreviation expansion | Property test (V-02.1-003) | **G3 violation risk** — evidence would cite wrong lines |
| Memory exhaustion on very large artifacts | Bounded by streaming design | Offset-based `raw` storage |
| Node ordering non-determinism | Property test | D6 requires explicit ordering |

---

## 7. Verification

```
V-02.1-001   Total line coverage — nothing is dropped
  Requirement  FR-PRS-014, INV-02.1-02
  Method       PROPERTY + CORPUS
  Procedure    For every corpus artifact, assert every non-blank line index
               appears in exactly one node's line range.
  Acceptance   100% of lines assigned. Zero lines in two nodes.
               Zero lines in no node.
  Severity     BLOCKING
```

```
V-02.1-002   Line ranges resolve to the exact source text
  Requirement  FR-PRS-008, INV-02.1-01, G3
  Method       PROPERTY + CORPUS
  Procedure    For every node, extract artifact[node.lines] and compare
               against node.raw.
  Acceptance   Exact match for 100% of nodes across the corpus.
  Severity     BLOCKING
  Note         This is the root verification for evidence binding.
```

```
V-02.1-003   Abbreviation expansion preserves line binding
  Requirement  FR-PRS-011, INV-02.1-03
  Method       UNIT + PROPERTY
  Procedure    Parse configurations containing abbreviated commands.
               Assert head is canonical, raw is the abbreviated original,
               and lines resolve to the abbreviated text.
  Acceptance   100%. An evidence excerpt shows the operator's own text.
  Severity     BLOCKING
```

```
V-02.1-004   Banners and verbatim regions do not corrupt structure
  Requirement  §5
  Method       UNIT + CORPUS
  Procedure    Configurations with banners containing `!`, `{`, `}`, `end`,
               indented lines, and section-marker-like text. Plus embedded
               PEM certificate blocks.
  Acceptance   Banner and certificate content is one verbatim node.
               Coverage unaffected. Structure identical to the same config
               with the banner removed.
  Severity     BLOCKING
```

```
V-02.1-005   All six paradigms produce a conforming tree
  Requirement  FR-PRS-001…007
  Method       CORPUS
  Procedure    Parse ≥ 20 artifacts per paradigm. Validate each tree against
               the Node contract.
  Acceptance   100% contract conformance. Mean coverage ≥ 0.95 per paradigm.
  Severity     BLOCKING
```

```
V-02.1-006   Cloud policy JSON parses through the same contract
  Requirement  FR-PRS-007
  Method       CORPUS
  Procedure    Parse AWS security group, Azure NSG and GCP firewall exports.
  Acceptance   Conforming trees with resolvable line ranges. Downstream
               subsystems require no paradigm-specific handling.
  Severity     BLOCKING
  Note         Explicitly listed twice in the problem statement's vendor set.
```

```
V-02.1-007   Contaminating imbalance fails hard; local errors recover
  Requirement  DD-02.1-04
  Method       UNIT
  Procedure    (a) FortiOS config with an unbalanced `end`.
               (b) Cisco config with 5 syntactically invalid lines.
  Acceptance   (a) hard error, artifact not assessed.
               (b) 5 unmatched nodes, coverage reduced, parse succeeds.
  Severity     BLOCKING
```

```
V-02.1-008   Grammar coverage below 0.50 is refused
  Requirement  DD-02.1-03, G2
  Method       INTEGRATION
  Procedure    Parse a Juniper artifact using the Cisco IOS grammar.
  Acceptance   status = refused. Zero nodes emitted downstream.
               Zero facts. Zero findings. Escalated as a grammar failure.
  Severity     BLOCKING
```

```
V-02.1-009   Parsing is deterministic
  Requirement  G1, D6
  Method       PROPERTY
  Procedure    Parse the full corpus 10 times, varying thread count and
               input ordering.
  Acceptance   Identical trees: identical node ordering, paths, line ranges
               and coverage values.
  Severity     BLOCKING
```

```
V-02.1-010   Very large artifacts parse within bounds
  Requirement  NFR-PERF-003, NFR-PERF-002
  Method       PERFORMANCE
  Procedure    Synthetic 500,000-line firewall policy on the reference profile.
  Acceptance   Completes without memory exhaustion. A 10,000-line
               configuration parses in < 2 s.
  Severity     MAJOR
```

```
V-02.1-011   Unmatched nodes carry section context
  Requirement  FR-PRS-014, TRD-08.1 dependency
  Method       UNIT
  Procedure    Parse an artifact with unmatched lines nested inside containers.
  Acceptance   Every unmatched entry carries enclosing_path, sufficient for
               template grouping.
  Severity     MAJOR
```

---

## 8. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should the 0.50 refusal threshold be paradigm-specific? | Sparse formats legitimately produce lower coverage on small configurations. Current design: global, with per-paradigm calibration reported from the corpus |
| Q2 | Should duplicate keys within a block be merged at parse time? | Merging simplifies extraction but discards ordering information that override resolution needs. Current design: retain both; resolve in TRD-02.3 |
| Q3 | Should verbatim-region detection be rulepack-declared or heuristic? | Declared is precise but requires every rulepack to enumerate its verbatim constructs; heuristic generalises to untaught platforms. Current design: declared where a rulepack exists, heuristic during grammar inference |
