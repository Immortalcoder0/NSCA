# TRD-03.1 · Extractor Runtime

---

## 1. Scope

Execution of rulepack extractors against an effective tree to produce facts in
the Security Baseline Model, with full provenance. Definition of the extractor
format, the value expression language, conflict detection, and the routing of
unmatched constructs to the learning queue.

**Out of scope:** defaults resolution and provenance classification (TRD-03.2);
the schema itself (TRD-03.3); rule authoring (TRD-08.3).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-EXT-001 | Effective tree → schema facts |
| FR-EXT-002 | Provenance on every fact |
| FR-EXT-007 | Conflict detection |
| FR-EXT-008 | Deterministic; no model invocation |
| FR-EXT-009 | Unmatched constructs routed to learning |
| NFR-SEC-007 | Declarative extractors; no arbitrary code execution |
| G3 | Evidence binding from fact to line |

---

## 3. Design

### 3.1 Extractor format

```yaml
extractor_id: cisco_ios.vty.transport_input
version: 7
applies_to:
  platform: cisco_ios
  version_range: ">=12.0"

scope:
  context: vty_range                # a container kind from the grammar
  # or: section: "/ip service"      # a path prefix
  # or: xpath: "/config/deviceconfig/system/service"

match: '^\s*transport input (?P<protos>.+)$'

emit:
  - fact:  mgmt.protocols.telnet.enabled
    value: "'telnet' in split(protos) or 'all' in split(protos)"
  - fact:  mgmt.protocols.ssh.enabled
    value: "'ssh' in split(protos) or 'all' in split(protos)"

scope_qualifier: "vty[{scope.lo}..{scope.hi}]"   # for ranged scopes

tests:
  - { input: "transport input ssh",        expect: { telnet: false, ssh: true  } }
  - { input: "transport input telnet ssh", expect: { telnet: true,  ssh: true  } }
  - { input: "transport input all",        expect: { telnet: true,  ssh: true  } }
  - { input: "transport input none",       expect: { telnet: false, ssh: false } }
```

**INV-03.1-01 — Extractors are data, never code.** `value` expressions are
evaluated by a restricted interpreter (§3.3). This is not defensive
over-engineering: rulepacks are **importable content** (FR-LRN-022), so an
extractor capable of arbitrary execution would make importing a community
rulepack a remote code execution vector.

### 3.2 Execution model

```
extract(effective_tree, rulepack) →
  facts = []
  matched_nodes = ∅

  for extractor e in rulepack.extractors:              # deterministic order
      if not applicable(e, platform, version): continue
      for node n in select(tree, e.scope):             # deterministic order
          m = match(e.match, n)
          if m is ⊥: continue
          matched_nodes ∪= { n }
          for emission in e.emit:
              v = evaluate(emission.value, m.captures, n)
              facts += Fact(
                  path        = qualify(emission.fact, e.scope_qualifier, n),
                  value       = v,
                  provenance  = Provenance(
                      source     = explicit,
                      artifact   = n.origin_artifact,
                      lines      = n.origin_lines,
                      excerpt    = n.raw,
                      extractor  = e.id @ e.version,
                      layer      = n.origin_layer,
                      confidence = 1.0))

  unmatched = security_relevant_nodes(tree) \ matched_nodes
  return facts, unmatched
```

**INV-03.1-02 — Extractor execution order does not affect the fact set.**
Extractors are independent; none consumes another's output. This is what makes
D6 achievable and is verified by V-03.1-006.

**DD-03.1-01 — Derived facts are computed in a separate pass** (TRD-03.2 §4),
not by extractors. Allowing an extractor to read another extractor's output would
introduce ordering dependence and break INV-03.1-02.

### 3.3 The value expression language

Deliberately minimal. Total, terminating, side-effect free.

| Category | Operations |
|---|---|
| Literals | string, integer, boolean, null |
| Captures | named regex groups from `match` |
| Node access | `node.attributes[k]`, `node.operands[i]`, `scope.lo`, `scope.hi` |
| Comparison | `== != < <= > >=` |
| Boolean | `and or not` |
| Membership | `x in y` |
| String | `split`, `lower`, `trim`, `startswith`, `contains`, `replace` |
| Numeric | `int`, `+ - * /`, `min`, `max` |
| Time | `to_seconds(value, unit)` |
| List | `map`, `filter`, `any`, `all`, `count`, `join` |
| Lookup | `map_lookup(table_name, key)` — tables declared in the rulepack |

**Explicitly absent:** loops, recursion, function definition, I/O, imports,
reflection, dynamic evaluation, regular-expression construction from data.

**`to_seconds` is a normalisation obligation, not a convenience.** PRD 05 §8
requires all durations in seconds. Platforms express `exec-timeout 5 30`
(5 min 30 s), `set admintimeout 5` (minutes), `timeout 300` (seconds). The
expression must convert explicitly:

```
value: "to_seconds(m, 'minutes') + to_seconds(s, 'seconds')"
```

### 3.4 Scope selection

| Scope kind | Selection |
|---|---|
| `context` | All container nodes of the named kind |
| `section` | Nodes under a path prefix |
| `xpath` | XML path expression (PAN-OS) |
| `root` | The whole tree |

**Ranged scopes** (TRD-02.3 DD-02.3-03) emit one fact instance per range, with
`scope_qualifier` distinguishing them:

```
vty[0..4].mgmt.protocols.telnet.enabled  = true
vty[5..15].mgmt.protocols.telnet.enabled = false
```

**Context scopes** (VDOM, VRF) qualify similarly:

```
vdom[customer-a].mgmt.protocols.telnet.enabled = true
```

Control aggregation over qualified instances is declared by the control
(TRD-05.2), not by the extractor.

### 3.5 List-valued and collection facts

Many facts are collections: `auth.local_users[]`, `filter.rules[]`,
`crypto.ssh.ciphers[]`. Extractors emit *elements*; the runtime assembles.

```yaml
emit:
  - fact: auth.local_users[]
    element:
      name:         "{{ username }}"
      privilege_level: "int(priv)"
      storage_type: "map_lookup('cisco_pw_types', pwtype)"
```

**INV-03.1-03 — Collection ordering is source order.** Element order in a fact
list matches source order, which matters critically for `filter.rules[]` where
first-match evaluation makes order part of the security semantics.

### 3.6 Conflict detection

FR-EXT-007. Two extractors producing different values for the same qualified fact
path on the same device is a defect — in a rulepack, or in the configuration
itself.

```
detect_conflicts(facts) →
  for each qualified path p with multiple emissions:
      if all values equal:      → merge, record contributing extractors
      if values differ:         → CONFLICT
```

**DD-03.1-02 — Conflict resolves to `default_unknown`, not to a winner.** There
is no principled basis for preferring one extractor's answer over another's. The
fact becomes undetermined, dependent controls return UNKNOWN, and the conflict is
raised as a rulepack defect.

```
⚠ Extractor conflict on CORE-SW-01
  fact: mgmt.session.idle_timeout_sec
  cisco_ios.vty.exec_timeout@3      → 0     (line 144)
  cisco_ios.line.timeout_legacy@2   → 600   (line 291)
  → fact resolves default_unknown; 3 controls UNKNOWN
  → rulepack defect raised
```

Silently choosing one would produce a confident wrong answer — precisely what G2
forbids.

### 3.7 Unmatched construct routing

FR-EXT-009. Nodes matched by no extractor are candidates for training.

Not every unmatched node is interesting. Pre-filtering reduces noise before the
learning queue applies its own relevance ranking (TRD-08.1):

| Excluded | Reason |
|---|---|
| Comment and blank nodes | No semantic content |
| Verbatim regions | Certificates, banners |
| Nodes whose head token is on the rulepack's `ignore` list | Known-irrelevant constructs |

Retained with `⟨enclosing_path, head, attribute_keys, frequency, sample_lines⟩`.

### 3.8 Performance

NFR-PERF-002 requires < 2 s for a 10,000-line configuration.

| Technique | Effect |
|---|---|
| Scope pre-indexing | Nodes bucketed by context kind once, reused by all extractors |
| Match pre-filtering | Cheap literal prefix test before regex evaluation |
| Compiled patterns | Regexes compiled once per rulepack load |
| Bounded backtracking | Patterns validated at rulepack ratification against catastrophic backtracking |

**Bounded backtracking is a security requirement, not only performance.** An
imported rulepack containing a pathological regex would otherwise be a
denial-of-service vector. Patterns are checked at ratification (TRD-08.3) and
execution is time-bounded per node.

---

## 4. Interfaces

**Input:** `⟨EffectiveTree, Rulepack, platform, os_version⟩`

**Output**

```
ExtractionResult {
  facts[]: Fact
  unmatched[]: ⟨enclosing_path, head, attribute_keys, frequency, sample_lines⟩
  conflicts[]: ⟨fact_path, extractors[], values[]⟩
  extractors_fired: int
  facts_by_source: map<provenance_source, int>
  coverage_contribution: ratio        // schema facts produced / producible
}
```

---

## 5. Edge cases

| Case | Handling |
|---|---|
| Extractor matches but the value expression fails to evaluate | Fact not emitted; error recorded as a rulepack defect; no partial fact |
| Regex capture group absent from a match | Expression referencing it evaluates to ⊥; fact not emitted |
| Same extractor matching a node twice (global regex) | First match only; multiple matches per node indicate a defective pattern and are flagged |
| Collection extractor producing zero elements | Empty list is a *value* — distinct from an absent fact. `crypto.ssh.ciphers = []` means "explicitly none", not "unknown" |
| Fact emitted for a path absent from the schema registry | Rejected; recorded as a rulepack defect. Registration is explicit (TRD-03.3) |
| Ranged scope with an unbounded upper limit | Represented symbolically; controls handle via aggregation |
| Node with `resolution: unresolved` (TRD-02.3) | Skipped; contributes to `default_unknown` |
| Extractor applicable to a version outside all declared ranges | Not applied; contributes to coverage loss, not to a guess |

**The empty-list case is a genuine distinction** and one that is easy to get
wrong. `ciphers = []` (explicitly configured to none) and `ciphers = ⊥`
(unknown) have opposite security meanings, and conflating them either fabricates
a finding or hides one.

---

## 6. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Extractor produces a wrong value | Extractor tests; corpus regression; metamorphic | **Silently wrong fact.** The most consequential failure; mitigated by the validation gates in TRD-08.3 |
| Polarity inverted in a value expression | Extractor tests; V-08.3-002 | A vulnerable device certified compliant — the worst outcome in the system |
| Conflict silently resolved | V-03.1-004 | DD-03.1-02 prevents |
| Provenance lost | V-03.1-002 | G3 violation; findings become unusable as evidence |
| Extraction order dependence | V-03.1-006 | G1 violation |
| Pathological regex in an imported rulepack | Ratification check; execution time bound | Denial of service |

---

## 7. Verification

```
V-03.1-001   Extractors cannot execute arbitrary code
  Requirement  INV-03.1-01, NFR-SEC-007
  Method       UNIT + static analysis
  Procedure    Attempt to author extractors invoking file I/O, network access,
               process execution, imports, dynamic evaluation, and unbounded
               recursion.
  Acceptance   All rejected at rulepack load with a specific error.
               The evaluator exposes no such capability.
  Severity     BLOCKING
```

```
V-03.1-002   Every fact carries resolvable provenance
  Requirement  FR-EXT-002, G3
  Method       PROPERTY + CORPUS
  Procedure    For every fact with source `explicit`, resolve
               artifact[provenance.lines] and compare against
               provenance.excerpt.
  Acceptance   100% resolve to real text matching the excerpt exactly.
  Severity     BLOCKING
```

```
V-03.1-003   Extractor tests pass and are enforced at load
  Requirement  FR-LRN-013
  Method       UNIT (CI gate)
  Procedure    Run every extractor's declared tests. Introduce a rulepack
               with one failing test.
  Acceptance   All shipped extractor tests pass. A rulepack with a failing
               test is rejected at load.
  Severity     BLOCKING
```

```
V-03.1-004   Conflicts resolve to unknown, never to a winner
  Requirement  FR-EXT-007, DD-03.1-02, G2
  Method       UNIT + CORPUS
  Procedure    Construct two extractors emitting different values for one
               fact path on one device.
  Acceptance   Fact resolves default_unknown. Dependent controls UNKNOWN.
               Conflict reported. Zero instances of a value being chosen.
  Severity     BLOCKING
```

```
V-03.1-005   Empty collection is distinct from absent
  Requirement  §5
  Method       UNIT
  Procedure    (a) Config explicitly configuring an empty cipher list.
               (b) Config with no cipher configuration at all.
  Acceptance   (a) fact = [] with source explicit.
               (b) fact absent → default_known or default_unknown.
               Controls distinguish the two.
  Severity     MAJOR
```

```
V-03.1-006   Extraction is order-independent and deterministic
  Requirement  INV-03.1-02, G1, D6
  Method       PROPERTY
  Procedure    Extract from the full corpus 10 times with shuffled extractor
               ordering and varied concurrency.
  Acceptance   Identical fact sets: identical paths, values, provenance and
               collection element ordering.
  Severity     BLOCKING
```

```
V-03.1-007   Collection ordering is source order
  Requirement  INV-03.1-03
  Method       UNIT + CORPUS
  Procedure    Extract filter.rules[] from configs with 50+ ordered rules.
  Acceptance   Element order matches source order exactly for 100% of
               corpus configs. Rule positions preserved.
  Severity     BLOCKING
  Note         First-match evaluation makes ordering part of the security
               semantics.
```

```
V-03.1-008   Ranged and context scopes emit qualified instances
  Requirement  §3.4, DD-02.3-03
  Method       UNIT
  Procedure    Config with two VTY ranges having different transports;
               FortiOS config with two VDOMs.
  Acceptance   Separate qualified fact instances emitted. Zero collapse.
  Severity     BLOCKING
```

```
V-03.1-009   Unregistered fact paths are rejected
  Requirement  §5, TRD-03.3
  Method       UNIT
  Procedure    Load a rulepack emitting an unregistered fact path.
  Acceptance   Rejected at load with a specific error naming the path.
  Severity     MAJOR
```

```
V-03.1-010   Duration normalisation to seconds
  Requirement  PRD 05 §8, §3.3
  Method       CORPUS
  Procedure    Extract mgmt.session.idle_timeout_sec across all platforms
               expressing it in minutes, seconds, and minute/second pairs.
  Acceptance   All values in seconds. Cross-platform comparison correct
               for 100% of corpus devices.
  Severity     BLOCKING
```

```
V-03.1-011   Pathological patterns are rejected at ratification
  Requirement  §3.8
  Method       UNIT
  Procedure    Submit extractors with catastrophic-backtracking patterns
               against adversarial inputs.
  Acceptance   Rejected at ratification. Any that pass are bounded at
               execution and abort the node, not the assessment.
  Severity     MAJOR
```

```
V-03.1-012   Extraction performance
  Requirement  NFR-PERF-002
  Method       PERFORMANCE
  Procedure    10,000-line configuration, mature rulepack (≥ 180 extractors),
               reference profile.
  Acceptance   Parse plus extraction < 2 s.
  Severity     MAJOR
```

---

## 8. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should the expression language support user-defined lookup tables beyond the rulepack's own? | Shared tables (weak algorithm lists, default community names) reduce duplication, but cross-rulepack dependencies complicate versioning and export. Current design: rulepack-local, with shared tables as a future addition |
| Q2 | Should a conflict between a `certified` and a `local` extractor prefer the certified one? | Trust tier is a plausible tiebreak, but preferring either contradicts DD-03.1-02's reasoning. Current design: no winner; conflict raised. Revisit if conflicts prove common in practice |
| Q3 | Should extraction be incremental across campaigns for unchanged artifacts? | Substantial performance gain for large estates, but caching risks stale results if the knowledge base changes. Current design: full extraction, keyed cache only where the artifact hash *and* rulepack version are both unchanged |
