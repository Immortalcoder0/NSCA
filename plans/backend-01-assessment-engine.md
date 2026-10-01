# Backend Track A · The Assessment Engine

> Builder: Claude Code (Sonnet), backend engineer #1.
> Package: `engine/nsca_engine/`. Deterministic, model-free, offline. This is
> the "compiler" from [04-system-architecture.md §1](../docs/04-system-architecture.md):
> reading (stages 1–4) and judging (stages 5–7) a device's configuration.
> Read [00-master-plan.md](00-master-plan.md) first — it defines the contract
> this document builds to and the repo layout this package lives in.

---

## 1. Scope and boundary

**You own:** pipeline stages 1–7 — Ingest (artifact correlation/custody
logic, not orchestration), Fingerprint, Parse, Extract, Graph, Evaluate, Risk
— plus the Schema Registry loader and the read-only collection driver.

**You do not own:** any database, any HTTP endpoint, any job scheduling, the
learning subsystem (grammar inference is the one exception — see §2.3),
remediation planning, report rendering, or anything requiring a model. That is
[Backend Track B](backend-02-platform-learning-reporting-api.md).

**Your code has no dependency on Track B's code, ever.** Track B depends on
you, via the single module `nsca_engine/api.py`. If you find yourself wanting
to import anything from `platform/`, stop — the thing you need either belongs
in your own package or should be passed in as a function argument.

### 1.1 TRD reading list, in build order

```
TRD-00   Conventions and Verification            — read first, in full
TRD-01.1 Artifact Intake, Correlation, Custody
TRD-01.2 Platform Fingerprinting
TRD-01.3 Read-Only Collection                     — driver only; §2.4 below
TRD-02.1 Grammar Engine and Parse Tree
TRD-02.3 Effective Configuration Resolution
TRD-03.1 Extractor Runtime
TRD-03.2 Provenance and Defaults Resolution
TRD-03.3 Schema Registry
TRD-04.1 Graph Construction and Exposure
TRD-04.2 Reachability and Counterexamples
TRD-05.1 Assertion Expression Language
TRD-05.2 Evaluation, Verdicts and Coverage
TRD-06.1 Exposure and Severity Weighting
TRD-06.2 Attack Path Computation
TRD-06.3 Peer Anomaly and Systemic Findings
TRD-11.2 Metamorphic Testing                      — read alongside 02.1
```

Also required reading before writing any extractor or control-evaluation
code: [05-security-baseline-model.md](../docs/05-security-baseline-model.md)
in full (it says so itself — design the schema on paper against real configs
before writing pipeline code) and
[07-vendor-rulepacks.md](../docs/07-vendor-rulepacks.md) (the format you are
reading). [06-controls-and-frameworks.md §3](../docs/06-controls-and-frameworks.md)
for the control specification you evaluate against.

### 1.2 What "grammar inference" being split means

[TRD-02.2 Grammar Inference](../trd/TRD-02.2-grammar-inference.md) belongs to
Backend Track B, not you — the TRD set's own suggested reading order groups it
with the learning system, not the pipeline
([trd/README.md](../trd/README.md)). Practically: you build the **grammar
engine** (TRD-02.1) that consumes a grammar definition and produces a parse
tree, generically over any grammar. Track B builds the **inference** step that
statistically *proposes* a grammar definition for an unrecognised format. The
proposed grammar, once accepted, is just another grammar definition your
engine consumes — you should never need to know whether a grammar came from a
mature rulepack or was inferred five minutes ago. If your grammar engine's
input contract has any special case for "inferred" grammars, that's a design
smell — remove it.

### 1.3 What "risk" living in the engine means

Unlike a typical layered backend, exposure weighting, attack-path computation,
and peer anomaly/systemic detection (TRD-06.x) live in your package, not
Track B's. This follows the architecture document's own box boundary
(§2 of [00-master-plan.md](00-master-plan.md)) — these are pure, deterministic
computations over facts and the graph, with no database and no model
involvement, and they naturally complete the "Risk" stage of the 9-stage
pipeline. Remediation (stage 8) and Reporting (stage 9) are Track B's, because
they need campaign/device records, users, and document rendering that your
package deliberately has no concept of.

### 1.4 Two scopes of computation

Some of what you build operates on one device in isolation; some requires
seeing every device in a campaign at once. Keep this distinction sharp in your
module boundaries — it is exactly the split behind the two engine entry
points in §4.

| Per-device (stages 1–6) | Campaign-wide (stage 7, parts of 4/5) |
|---|---|
| Ingest custody/correlation for one device's artifacts | Estate graph merge across devices |
| Fingerprint | Multi-device reachability (FR-GRF-004) |
| Parse, effective-config resolution | Attack path computation |
| Extract | Peer anomaly (needs siblings of the same platform) |
| Per-device control evaluation, coverage, vacuity, scope contamination | Systemic findings (needs the whole fleet) |
| Single-device graph contribution (nodes/edges) | Exposure classification (needs estate position) |

---

## 2. Design constraints that shape every module

These are not suggestions — they are what the CI gates in
[00-master-plan.md §7](00-master-plan.md) test for, and they are cheaper to
build in from the start than to retrofit.

### 2.1 Determinism (D1–D8, [TRD-00 §7](../trd/TRD-00-conventions-and-verification.md))

- No `random`, no `time.time()`/`datetime.now()`, no `uuid4()`, anywhere in
  `nsca_engine/`. Assessment time is the `assessed_at` parameter, full stop.
- No dict/set iteration whose order isn't explicitly controlled. `for f in
  sorted(fact_set, key=...)`, always. Set `PYTHONHASHSEED=0` in every
  container/test environment you specify.
- No floats in scoring. Use `fractions.Fraction` for every ratio
  (compliance, coverage, meaningful_ratio). This is D5 in TRD-00 and it is
  the single most commonly-regressed rule in a codebase that otherwise looks
  correct — write a lint rule or a pre-commit check for it if you can.
- Parallel-safe by construction: if you ever parallelise inside a single
  `assess_device` call (you should not need to — Track B parallelises across
  devices, not within one), any aggregation must sort before reducing (D7).

### 2.2 No model, ever

`nsca_engine/` must not import any model client library, must not make an
HTTP call, must not read a file outside of the `KnowledgeBase` object handed
to it. This is what `gate_g1_determinism` checks by AST walk — write your
code so the gate is trivially satisfied, not so it barely passes.

### 2.3 Evidence binding (G3) is not optional plumbing

Every `Fact` must carry a real `provenance` with artifact id and line numbers
it can point to. If you are tempted to synthesize a fact without provenance
"just for now," don't — `DM-4` ("a finding whose control has a missing
required fact cannot be PASS") depends on provenance being present and
honest from the first line of extractor code you write, not bolted on later.

### 2.4 The collection driver is a type-level guarantee, not a check

```python
# engine/nsca_engine/collection/driver.py

class CommandId(StrEnum):
    SHOW_RUNNING_CONFIG = auto()
    SHOW_VERSION = auto()
    SHOW_INVENTORY = auto()

def collect(target: Target, cmd: CommandId) -> RawArtifact: ...
#                          ^^^^^^^^^^^^^^^ never `str` — a caller cannot
#                          express a command that isn't in this enum.
```

No function anywhere under `collection/` may accept a bare `str` as a
command. `gate_g4_independence` asserts this by signature inspection — see
[TECH-STACK.md §10](../TECH-STACK.md) for the full rationale. Netmiko (plus
Paramiko for mandatory host-key verification) sits underneath this wrapper;
nothing above the wrapper ever touches Netmiko directly.

---

## 3. Module layout

```
engine/
├── pyproject.toml            no runtime dependency may perform I/O except
│                              collection/ (network) and schema loading at
│                              KnowledgeBase construction time (disk read,
│                              happens once, outside the assess_* calls)
└── nsca_engine/
    ├── api.py                 the public contract — §4
    ├── types.py                Fact, Provenance, Finding, Verdict, etc.
    ├── ingest/
    │   ├── correlate.py         hostname/serial correlation, ambiguity flags
    │   ├── custody.py            hashing, custody metadata attachment
    │   └── completeness.py       export-mode (verbose/terse) detection
    ├── fingerprint/
    │   ├── signatures.py         weighted signature matching
    │   └── confidence.py
    ├── parse/
    │   ├── grammar.py            generic grammar engine — TRD-02.1
    │   ├── paradigms/            one module per structural paradigm
    │   │   ├── indentation.py    Cisco-family, Arista
    │   │   ├── flat_path.py      Juniper set-format
    │   │   ├── brace.py          Juniper curly-format
    │   │   ├── block_keyword.py  FortiOS
    │   │   ├── xml.py            PAN-OS (lxml, sourceline-preserving)
    │   │   └── path_header.py    MikroTik RouterOS
    │   └── effective_config.py    inheritance/override resolution — TRD-02.3
    ├── extract/
    │   ├── runtime.py             extractor execution — TRD-03.1
    │   ├── provenance.py          source classification, defaults — TRD-03.2
    │   └── capability_surface.py  fleet-inferred platform capability (FR-EXT-006)
    ├── schema/
    │   └── registry.py            loads knowledge/schema/*.yaml — TRD-03.3
    ├── graph/
    │   ├── build.py                per-device contribution + estate merge — TRD-04.1
    │   ├── reachability.py         multi-device queries, counterexamples — TRD-04.2
    │   └── exposure.py             device exposure classification
    ├── controls/
    │   ├── expression.py           Lark grammar + Kleene evaluator — TRD-05.1
    │   ├── evaluate.py              verdicts, coverage, vacuity, contamination — TRD-05.2
    │   └── rulepack_loader.py       reads knowledge/rulepacks, knowledge/control_packs
    ├── risk/
    │   ├── severity.py              exposure-weighted effective severity — TRD-06.1
    │   ├── attack_paths.py          chain computation, weakest-link — TRD-06.2
    │   └── anomaly.py               peer anomaly + systemic clustering — TRD-06.3
    ├── collection/
    │   └── driver.py                CommandId-gated Netmiko/Paramiko wrapper
    └── tests/
        ├── fixtures/                 hand-written minimal configs, per TRD-00 §8
        ├── corpus/                   real sanitised configs, ≥5 platforms — TRD-00 §8.2
        ├── metamorphic/               mutation harness — TRD-11.2
        └── golden/                   20 golden campaigns for the CI hash-comparison gate
```

---

## 4. The public contract (`api.py`)

This is reproduced from [00-master-plan.md §5.1](00-master-plan.md) — treat
that copy as authoritative if the two ever disagree, and fix the disagreement
immediately rather than picking one.

```python
@dataclass(frozen=True, slots=True)
class RawArtifact:
    id: str
    filename: str
    content: bytes
    artifact_type_hint: ArtifactType | None
    received_from: str

@dataclass(frozen=True, slots=True)
class KnowledgeBase:
    schema_registry: SchemaRegistry
    rulepacks: tuple[Rulepack, ...]
    control_packs: tuple[ControlPack, ...]
    pin: KnowledgeBasePin

def assess_device(
    artifacts: tuple[RawArtifact, ...],
    knowledge_base: KnowledgeBase,
    assessed_at: datetime,
) -> DeviceAssessment: ...

def assess_campaign(
    device_assessments: tuple[DeviceAssessment, ...],
    knowledge_base: KnowledgeBase,
) -> CampaignAssessment: ...
```

Build `assess_device` first — it is independently useful and independently
testable against fixtures/corpus without `assess_campaign` existing at all.
`assess_campaign` cannot be meaningfully tested until you have several real
`DeviceAssessment` objects to feed it, so it naturally lands later in your
milestone sequence (§6, M4).

### 4.1 `DeviceAssessment` — what it must contain

Everything [14-data-model.md §2](../docs/14-data-model.md)'s `ASSESSMENT`,
`FACT`, and (per-device) `FINDING` entities need, minus anything that is
Track B's to attach (owner, due date, lifecycle state, dispute, campaign id):

```python
@dataclass(frozen=True, slots=True)
class DeviceAssessment:
    fingerprint: FingerprintResult          # vendor, platform, os_version, model, serials, confidence
    facts: tuple[Fact, ...]                  # full SBM instance, each with Provenance
    unmatched_constructs: tuple[UnmatchedConstruct, ...]   # → Track B's learning queue
    graph_contribution: GraphFragment        # this device's nodes/edges only
    findings: tuple[DeviceFinding, ...]      # verdict, evidence, base severity, coverage inputs
    grammar_coverage: Fraction
    scores: DeviceScores                     # compliance, coverage, meaningful_ratio — all Fraction
```

`DeviceFinding.severity` here is **base** severity only — exposure-weighted
**effective** severity is computed in `assess_campaign`, because exposure is a
graph-position property of the whole estate, not a single device's own facts
([05-security-baseline-model.md §4.1](../docs/05-security-baseline-model.md):
`device.exposure` is "computed from the graph, not read from configuration").

### 4.2 `CampaignAssessment` — what it must contain

```python
@dataclass(frozen=True, slots=True)
class CampaignAssessment:
    graph: Graph                              # merged estate graph
    effective_severities: Mapping[FindingKey, Severity]
    scope_contamination: tuple[ContaminationNote, ...]
    attack_paths: tuple[AttackPath, ...]
    peer_anomalies: tuple[PeerAnomaly, ...]
    systemic_findings: tuple[SystemicFindingCandidate, ...]
```

---

## 5. Notes on the harder subsystems

### 5.1 The grammar engine (TRD-02.1)

Build the shared parse-tree contract before any paradigm-specific parser:
every node needs a hierarchical path, a verb, attributes, and — critically —
`line_start`/`line_end` into the *original* artifact bytes, materialised on
demand rather than stored per node
([TECH-STACK.md §3](../TECH-STACK.md) shows the `__slots__` dataclass with an
offset/length pair instead of copied text — follow that shape; it is what
keeps 500,000-line configs tractable, NFR-PERF-003). Get one paradigm
(indentation — Cisco) fully working end-to-end through extraction and
evaluation before starting the second; the paradigms are structurally
different enough that a design that only works for one of them is a common
failure mode.

For PAN-OS specifically, use `lxml`, not `xmltodict` — the latter discards
`sourceline`, which makes evidence binding on XML platforms impossible. This
is called out as "the single most commonly-missed dependency decision in this
problem space" in [TECH-STACK.md §6](../TECH-STACK.md); don't rediscover it
the hard way.

### 5.2 Effective configuration resolution (TRD-02.3)

This is the subsystem most likely to make the tool "confidently wrong on
exactly the enterprise configurations that matter most" if under-built
([04-system-architecture.md §4.3](../docs/04-system-architecture.md)). Do not
treat it as a later refinement pass — build the Cisco overlapping-`line vty`
case and at least one PAN-OS or Juniper inheritance case into your corpus and
fixtures from the start (TRD-00 §8.2 requires ≥10 inheritance-bearing
configurations in the corpus). Every fact derived from a non-local layer must
record which layer produced it (`provenance.layer`) — an auditor will ask.

### 5.3 The expression language (TRD-05.1)

Three-valued (Kleene) logic is the one piece of this subsystem that cannot be
gotten from an off-the-shelf library — see
[TECH-STACK.md §7](../TECH-STACK.md) for why CEL, Rego, and JSONLogic were all
rejected. `true and ⊥ = ⊥` is not an edge case to handle later; write the
exhaustive truth-table test (V-05.1-001 style) as one of your first tests in
this module, before building out the full grammar. Use Lark only to generate
the parser from the EBNF grammar; write the Kleene evaluator by hand.

### 5.4 UNKNOWN is structural, not a code path you remember to add

The mechanism is: a control declares `requires_facts`; if any listed fact's
provenance is `default_unknown` (or the fact is simply absent), the verdict is
UNKNOWN, unconditionally, before any assertion is even evaluated. Implement
this as a pre-check in `controls/evaluate.py` that runs before the expression
evaluator is invoked at all — do not implement it as "the expression evaluator
happens to produce UNKNOWN when it hits a null." The former is structural and
impossible to bypass by a future change to the expression language; the
latter is exactly the kind of implementer's-discretion bug that TRD-00 §6 (G2)
exists to rule out. This single check is what `V-05.2-004` verifies.

### 5.5 Metamorphic testing (TRD-11.2)

This is your highest-leverage test investment and should not be deferred to
"once things work." Build the mutation catalogue (block reordering, object
renaming, whitespace alteration, command abbreviation/expansion, comment
insertion, line-ending changes, equivalent-syntax substitution) alongside the
first paradigm's parser, and run it in CI nightly from Phase 1 onward. It
finds defects no hand-written test would — that is the entire point.

---

## 6. Milestones

Each milestone's "done" criterion is independently verifiable without Track B
existing yet — that is deliberate, so you are never blocked waiting on them.

**M0 — Contracts and schema (Phase 0)**
`api.py` skeleton with real dataclasses (not `NotImplementedError` stubs
beyond the function bodies), `SchemaRegistry` loader reading a first-draft
`knowledge/schema/*.yaml` covering the ten top-level domains from
[05-security-baseline-model.md §4](../docs/05-security-baseline-model.md).
Done when: the schema loads, validates against JSON Schema, and a unit test
constructs a `Fact` for every provenance source classification.

**M1 — One platform, end to end (early Phase 1)**
Cisco IOS: fingerprint → indentation-paradigm parse → extract → evaluate,
against the worked example in
[05-security-baseline-model.md §9](../docs/05-security-baseline-model.md) and
its expected facts. Done when: that worked example's exact fact list is
reproduced, including the `default_unknown` case, and ≥20 controls from
[06-controls-and-frameworks.md §3](../docs/06-controls-and-frameworks.md)'s
family evaluate correctly across PASS/FAIL/UNKNOWN/NOT_APPLICABLE.

**M2 — Grammar breadth (Phase 1)**
Add the remaining five paradigms (flat-path, brace, block-keyword, XML,
path-header) plus cloud JSON. Done when: corpus coverage meets
[TRD-00 §8.2](../trd/TRD-00-conventions-and-verification.md)'s minimums (5
platforms, ≥3 structural paradigms, 200 configurations) and metamorphic tests
pass on all of them.

**M3 — Graph and reachability (Phase 1)**
`assess_device`'s per-device graph contribution, then multi-device merge and
reachability queries against a synthetic reference estate (R6 in the risk
register). Done when: the canonical counterexample from
[04-system-architecture.md §4.5](../docs/04-system-architecture.md) (the
`Trusted-Admins` → `Partners` → `0.0.0.0/0` case) is reproduced exactly,
including the rule chain.

**M4 — Campaign-wide risk (Phase 1 → 2)**
`assess_campaign` complete: exposure weighting, attack paths, peer anomaly,
systemic clustering. Done when: the AP-003 example from
[09-findings-lifecycle.md §11.2](../docs/09-findings-lifecycle.md) is
reproduced end-to-end from raw artifacts, and a systemic-finding cluster is
correctly detected on a corpus subset with ≥30 near-identical branch-router
configs (construct this fixture set deliberately if the real corpus doesn't
have it).

**M5 — Performance and determinism hardening (Phase 2)**
Meet NFR-PERF-001/002/003/006 on real hardware; the 20-golden-campaign
double-run hash comparison passes in CI; `mypy --strict` and `ruff` clean.
Done when: `gate_determinism_golden_set` and `gate_g1_determinism` are green
and have been green for the last 10 consecutive commits (not just once by
luck of test ordering).

---

## 7. Testing obligations

Per [TRD-00 §4](../trd/TRD-00-conventions-and-verification.md) and
[TECH-STACK.md §13](../TECH-STACK.md):

- **UNIT** — every extractor, every paradigm parser, the expression evaluator.
- **PROPERTY** (Hypothesis) — this is load-bearing, not optional. At minimum:
  "a control whose required fact is omitted never evaluates to PASS" (the
  literal property behind V-05.2-004), and exhaustive Kleene truth tables.
- **METAMORPHIC** — §5.5.
- **CORPUS** — full corpus re-run on every knowledge-base change; any verdict
  flip without a corresponding content change is a defect, not a surprise to
  investigate later.
- **DIFFERENTIAL** — cross-check against OpenSCAP or CIS-CAT Lite on
  overlapping controls where feasible; this is what makes "false positive
  rate < 2%" a measured claim instead of an assertion.

Do not wait until M5 to wire Hypothesis and the metamorphic harness into CI —
add them in M0/M1 so every subsequent milestone is protected by them, not just
tested by them retroactively.

---

## 8. Open questions to flag back (do not silently resolve)

- Exact precedence/interaction of `default_inferred` under "strict" vs
  "standard" assessment mode ([05-security-baseline-model.md §3.1](../docs/05-security-baseline-model.md))
  — confirm which mode is the product default before M1's control library
  depends on the answer.
- Whether `assess_campaign`'s peer-anomaly threshold and systemic-clustering
  threshold are engine-internal constants or `KnowledgeBase`-supplied
  configuration — TRD-06.3 should specify this; if it doesn't, propose a
  default and record it here.
- Corpus sourcing/sanitisation ownership — TRD-00 §8.2 sets requirements but
  someone has to go get 200 real configurations across 5 platforms. Flag this
  early; it is the single most likely schedule risk for this track that has
  nothing to do with code.
- **Resolved (M1):** TRD-05.1 and §5.4 of this doc disagreed on whether a
  Kleene-decidable expression (`false or ⊥ = true`) should be allowed to
  override a missing-required-fact UNKNOWN. Decision: §5.4's unconditional
  pre-check wins — a control with any missing `requires_facts` entry is
  UNKNOWN before the expression evaluator runs, full stop, no
  Kleene-decidability exception. This is the more conservative auditing
  stance and matches V-05.2-004 literally. `controls/evaluate.py` implements
  this; TRD-05.1 should be amended to note the exception if anyone revisits
  it.
