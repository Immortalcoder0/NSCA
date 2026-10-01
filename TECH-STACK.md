# NSCA — Technology Stack

**What is used, for what, and why.**

Companion to [ARCHITECTURE.md](ARCHITECTURE.md), the [PRD](docs/README.md) and the
[TRD set](trd/README.md).

---

## 1. The five constraints that drive every choice

Nothing here is chosen on preference. Five hard requirements eliminate most of
the option space before taste enters:

| # | Constraint | Source | Eliminates |
|---|---|---|---|
| C1 | **Offline / air-gapped assessment** | NFR-DEP-001, NCIIPC deployment context | Any managed service, hosted API, cloud dependency at runtime |
| C2 | **Byte-identical determinism** | G1, FR-INT-001 | Unordered iteration in output paths, float scoring, clock-stamped artifacts |
| C3 | **Declarative content, no code execution** | NFR-SEC-007 — rulepacks are *imported* | Embedding a scripting language in the content format |
| C4 | **Three-valued logic (⊥ propagation)** | G2, FR-CTL-005 | Every off-the-shelf policy engine |
| C5 | **500 devices < 5 min; 500k-line configs** | NFR-PERF-001/003 | Naive object-per-line parsing |

A sixth, softer one: the problem statement explicitly names **Netmiko/NAPALM**.
Ignoring a stated hint from the evaluator is a needless cost.

---

## 2. Stack at a glance

| Purpose | Technology |
|---|---|
| Engine language | **Python 3.12** |
| API | **FastAPI + Pydantic v2**, uvicorn |
| Database | **PostgreSQL 16** (`psycopg` 3, SQLAlchemy 2.0 Core, Alembic) |
| Job queue | **PostgreSQL** `FOR UPDATE SKIP LOCKED` — *no Redis* |
| Artifact store | **Content-addressed filesystem**, encrypted — *no MinIO* |
| XML parsing | **lxml** (line numbers) |
| Regex | **`regex`** module (timeout support) |
| Content format | **YAML** (`ruamel.yaml`) + **JSON Schema** validation |
| Expression language | **Custom**, grammar via **Lark** |
| Graph | **Custom**, sorted adjacency |
| Template mining | **Custom** |
| Device collection | **Netmiko** (+ Paramiko for host keys) |
| PDF | **WeasyPrint** + **Jinja2** + **pikepdf** |
| Editable export | **python-docx** |
| Local inference | **Ollama** + Qwen2.5-7B-Instruct, JSON-schema-constrained |
| Signing / crypto | **`cryptography`** |
| Frontend | **React 19 + TypeScript + Vite + Tailwind + shadcn/ui** |
| Server state | **TanStack Query**; **TanStack Table** for the workbench |
| Graph layout | **dagre** + custom SVG |
| Testing | **pytest + Hypothesis** + custom metamorphic harness |
| Lint / types | **ruff**, **mypy** |
| Packaging | **Docker + Compose** |
| CI | **GitHub Actions** + three custom AST gates |

---

## 3. Engine and runtime

### Python 3.12

**Used for:** the entire backend — assessment pipeline, learning subsystem,
knowledge base, reporting, API.

**Why:**
- Netmiko and NAPALM are Python, and the PS names them
- The config-parsing ecosystem is Python: `lxml`, `ciscoconfparse2`, `hier_config`
- Local inference tooling is Python-native
- 3.12 specifically: faster interpreter, `__slots__`-friendly dataclasses, better error messages

**The honest performance position.** 500 devices × ~2 s ≈ 17 min single-threaded.
Devices are independent, so `multiprocessing.Pool(8)` brings that to ~2 min. That
meets NFR-PERF-001.

The genuine pressure point is C5's second half — **500,000-line firewall policy
exports**. Mitigations that are required, not optional:

```python
@dataclass(slots=True)
class Node:
    parent: int | None
    children: tuple[int, ...]
    path: tuple[str, ...]
    head: str
    attrs: Mapping[str, str]
    line_start: int
    line_end: int
    _offset: int          # raw text is an offset into the artifact,
    _length: int          # materialised on demand — never stored per node
```

`__slots__`, offset-based raw text, streaming parse, compiled patterns with a
literal-prefix pre-filter. If that ever proves insufficient, the parser inner
loop is the single place a Rust extension via PyO3 would pay — but starting there
is premature.

---

## 4. API layer

### FastAPI + Pydantic v2

**Used for:** the REST surface (PRD 15), request validation, OpenAPI generation.

**Why Pydantic matters here specifically:** several product invariants are best
enforced as *validation*, not convention. The PRD calls for HTTP 422 on exactly
these:

```python
class RiskAcceptanceRequest(BaseModel):
    expires_at: date                      # not Optional — FR-FND-008
    justification: str = Field(min_length=20)

class TrainingAnswer(BaseModel):
    response: Literal['confirm','polarity_inverted','edit','not_relevant','skip']
    polarity_confirmed: bool | None = None

    @model_validator(mode='after')
    def polarity_gate(self):
        if self.requires_polarity and self.polarity_confirmed is None:
            raise ValueError('polarity confirmation required')   # → 422
        return self

class CollectionRequest(BaseModel):
    mode: Literal['read_only']            # G4 — no other value is expressible
```

That last line is the point. `mode` isn't validated against a list of allowed
values — **the type has one inhabitant.** A client cannot express a write.

**Note on async:** the workload is CPU-bound, not IO-bound. Async endpoints buy
nothing for parsing and evaluation. Use sync route handlers and offload to
workers; reserve async for the collection paths where it genuinely helps.

---

## 5. Data layer

### PostgreSQL 16

**Used for:** campaigns, devices, facts, findings, lifecycle, knowledge base
metadata, audit log, job queue, full-text search.

**Three things earn it:**

**JSONB for facts.** The schema registry is runtime-extensible (NFR-MNT-003), so
facts cannot live in fixed columns. JSONB gives flexibility plus GIN indexing.

Critically, the ⊥ representation is structural:

```sql
CREATE TABLE fact (
  assessment_id uuid NOT NULL,
  path          text NOT NULL,
  value         jsonb,              -- NULL = ⊥, never confusable with false
  source        fact_source NOT NULL,
  artifact_id   uuid,
  line_start    int, line_end int,
  extractor     text,
  PRIMARY KEY (assessment_id, path)
);
```

**Constraints enforce invariants at the layer where they belong:**

```sql
-- FR-ADM-004: ratifier ≠ author is not a convention
ALTER TABLE extractor ADD CONSTRAINT two_person_rule
  CHECK (ratified_by IS NULL OR ratified_by <> taught_by);

-- FR-INT-006: the audit log is append-only, enforced by the database
CREATE RULE audit_no_update AS ON UPDATE TO audit_log DO INSTEAD NOTHING;
CREATE RULE audit_no_delete AS ON DELETE TO audit_log DO INSTEAD NOTHING;
```

**Full-text search** for the repository requirement (FR-UIX-011) without a second
system.

### Access layer — SQLAlchemy 2.0 Core, `psycopg` 3, Alembic

**SQLAlchemy Core, not the ORM.** You want explicit SQL for the append-only
rules, the JSONB queries, and the `SKIP LOCKED` queue. The ORM's identity map and
lazy loading fight both determinism and the write-once model.

`psycopg` 3 over `psycopg2`: better performance, native async where needed,
proper JSONB adaptation.

### On single-node deployment

NFR-DEP-004 requires an assessor-workstation profile. **Do not build a dual
SQLite/Postgres backend.** The JSONB→JSON1 gap produces subtly different
behaviour between deployments — which is a determinism hazard, not just an
inconvenience. Ship Postgres in the container even for single-node. One code
path, one behaviour.

### Job queue — PostgreSQL, not Redis

```sql
UPDATE job SET state='running', worker=$1
WHERE id = (
  SELECT id FROM job WHERE state='pending'
  ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1
) RETURNING *;
```

**Why not Celery + Redis:** the workload is low-frequency, long-running batch
jobs. Redis adds a component to an air-gapped deployment (C1), adds a second
place state can diverge, and buys nothing at this throughput. Postgres gives
transactional job state alongside the data it operates on.

### Artifact store — content-addressed filesystem

```
artifacts/3f/9a/3f9a...c21b        # sha256, write-once, 0400
```

**Why not MinIO/S3:** another container, another credential, another failure
mode, for zero benefit at 1–5 GB per campaign. Content addressing gives
deduplication and integrity verification for free. An S3 backend is a pluggable
option for organisations that require it.

---

## 6. Parsing

### lxml — for XML configurations

**Used for:** PAN-OS XML, any XML-format policy export.

**Why not `xmltodict`:** it discards source position. G3 (evidence binding)
requires every fact to cite line numbers, and a finding on a PAN-OS device with
no line reference is unusable as audit evidence.

```python
from lxml import etree
tree = etree.parse(f)
for el in tree.iter():
    el.sourceline          # ← this is why lxml, and only lxml
```

This is the single most commonly-missed dependency decision in this problem
space.

### `regex` — not the stdlib `re`

**Used for:** every extractor pattern.

**Why:** TRD-03.1 §3.8 requires bounded backtracking. Rulepacks are **imported
content**, so a catastrophic pattern in a community rulepack is a denial-of-service
vector against every importer. The stdlib `re` has no timeout parameter; the
`regex` module does:

```python
import regex
regex.match(pattern, text, timeout=0.05)   # per-node bound
```

Ratification-time analysis catches most pathological patterns; the runtime
timeout is the backstop.

### Custom parsers — the six paradigms

**Used for:** indentation (Cisco-family, Arista), flat-path (Juniper set), brace
(Juniper curly), block-keyword (FortiOS), path-header (MikroTik), plus native
JSON.

**Why custom rather than `ciscoconfparse2`:** the parse-tree contract
(TRD-02.1 §3.1) is shared by six paradigms and consumed by paradigm-agnostic
downstream code. Adapting an existing library to that contract costs more than
writing the structurer, which is ~200 lines per paradigm. `ciscoconfparse2` is
useful as a **reference implementation for differential testing**, not as a
dependency.

### Content format — YAML via `ruamel.yaml`, validated by JSON Schema

**Used for:** rulepacks, control packs, framework mappings, defaults tables.

**Why YAML:** human-readable, diffable, comment-bearing. A ratifier reviewing a
taught rule must be able to read it.

**Why `ruamel.yaml` over `PyYAML`:** rule synthesis *writes* YAML that humans then
review. `ruamel` round-trips comments and preserves ordering; PyYAML does not.

**Security, non-negotiable:** `YAML(typ='safe')` only. Rulepacks are imported
content; `yaml.load` with the default loader is arbitrary code execution.

**JSON Schema** (`jsonschema`) validates structure at load, before any content is
trusted.

---

## 7. Expression language — custom, grammar via Lark

**Used for:** control assertions, vacuity clauses, risk modifiers, applicability
conditions, extractor value expressions.

**Why not adopt one:**

| Candidate | Rejected because |
|---|---|
| **CEL** | `cel-python` immature; error semantics ≠ Kleene logic |
| **OPA / Rego** | External process; `undefined` semantics differ from ⊥; heavyweight for a language with no loops |
| **JSONLogic** | No quantifiers, no type system |
| **Embedded Python** | Violates C3 outright |

**None provide three-valued logic**, and C4 is non-negotiable — `true and ⊥ = ⊥`
is the cell that enforces G2 at the language level, and you cannot obtain it by
configuring someone else's evaluator.

**Scope:**

```
grammar (Lark EBNF)      ~80 lines
type checker             ~200 lines   ← validates against the schema registry
Kleene evaluator         ~300 lines
trace generation         ~100 lines
```

Roughly 700 lines for semantics you control and can test exhaustively.
V-05.1-001 (exhaustive truth tables) becomes a trivial parametrised test.

**Lark** is used only to generate the parser from an EBNF grammar. Earley/LALR
both work; the language is small enough that either is instant.

---

## 8. Graph — custom, sorted adjacency

**Used for:** configuration graph construction, reachability, counterexample
generation, exposure classification, attack paths.

**Why not networkx:** its iteration order derives from dict insertion, which you
would have to control at every call site anyway. TRD-04.1 §3.8 already specifies
sorted adjacency arrays for determinism — at which point you have written the
data structure, and networkx becomes a dependency you fight rather than use.

```python
class Graph:
    __slots__ = ('_nodes', '_adj')
    _adj: dict[int, tuple[Edge, ...]]     # sorted tuples, immutable
```

~300 lines. Deterministic traversal by construction (D6). Adequate at estate
scale: 50k nodes / 200k edges for 1,000 devices.

**networkx is a dev dependency only** — prototyping and visualisation, never in
the assessment path.

**Packet sets** for reachability use interval unions over the 5-tuple, not
decision diagrams. Simpler, deterministic, sufficient at policy sizes we handle;
revisit only if the TRD-04.2 budget is exhausted on real firewall policies.

---

## 9. Learning subsystem

### Template mining — custom

**Used for:** collapsing thousands of unrecognised lines into ~120 templates.

**Why not Drain3:** Drain3 infers variability *per line* against a parse tree of
prefixes. TRD-08.1 DD-08.1-01 requires **corpus-wide positional** variability — a
token is a slot because it varies across occurrences of the same skeleton, not
because it looks like a value. That distinction is what keeps `disabled` a
literal and `telnet` a slot, which is the difference between correct and useless
mappings.

~200 lines, informed by Drain3's approach.

### Local inference — Ollama + Qwen2.5-7B-Instruct

**Used for:** candidate mapping proposals only (TRD-08.2 §5). **Never in the
assessment path.**

**Why Ollama:** single binary, runs air-gapped, models ship as files, no Python
runtime coupling, and it supports JSON-schema-constrained output.

**Why a 7B model is enough:** the task is structured extraction against a
described schema with heuristic candidates already supplied — not open-ended
reasoning. Constrained decoding does most of the work.

**Schema-constrained generation is a safety mechanism, not a convenience:**

```python
{"format": {"type": "object", "properties": {
    "mappings": {"type": "array", "items": {"type": "object", "properties": {
        "fact_path": {"enum": [...registered paths only...]}   # ← cannot hallucinate
    }}}}}}
```

The model selects from registered fact paths. It is structurally incapable of
proposing one that does not exist.

**HTTP client:** `httpx`. **Redaction runs before any invocation** (FR-LRN-028) —
credentials, hashes, community strings, key material, structure-preserving.

**The inference container is optional.** `learning/` degrades to heuristic-only
proposals (INV-08.2-03); `assessment/` never touches it at all.

---

## 10. Device collection

### Netmiko (+ Paramiko)

**Used for:** read-only SSH collection from reachable devices.

**Why Netmiko:** named in the PS; broad platform support; handles paging
disable and prompt detection, which are the tedious parts.

**Why not NAPALM as primary:** NAPALM's value is a normalised *getter* API — but
normalisation is precisely what this platform does itself, in the rulepack layer.
Using NAPALM's normalisation would put a second, opaque, un-versioned
normalisation step ahead of ours. Netmiko gives raw command output, which is what
the pipeline expects. NAPALM remains available as an optional transport.

**Paramiko** underneath, with **host key verification mandatory** — a session
accepting an unknown key may be collecting from an impostor, and every finding
derived from it would be attributed to the wrong device.

**G4 enforcement lives in the wrapper, not in Netmiko:**

```python
class CommandId(StrEnum):                  # compile-time constant
    SHOW_RUNNING_CONFIG = auto()
    SHOW_VERSION = auto()
    SHOW_INVENTORY = auto()

def collect(target: Target, cmd: CommandId) -> Artifact: ...
#                          ^^^^^^^^^ never `str`
```

A caller cannot *express* an arbitrary command. CI asserts no signature in
`transport/` accepts a string command (V-01.3-001).

---

## 11. Reporting

### WeasyPrint + Jinja2 + pikepdf

**Used for:** per-device PDF, estate report.

**Why WeasyPrint:** HTML/CSS is dramatically faster to iterate than ReportLab's
imperative API, and the report has real layout requirements — evidence excerpts,
severity indicators, tables, print-safe monochrome.

**Jinja2** renders the document model (TRD-09.1 §3.2) to HTML. The same document
model feeds DOCX, so formats cannot diverge.

**pikepdf handles the determinism problem WeasyPrint creates.** WeasyPrint
stamps `/CreationDate` from the clock and generates a random `/ID` — your
byte-identical claim dies there, silently, unless you hash the output:

```python
pdf = pikepdf.open(buf)
pdf.docinfo['/CreationDate'] = deterministic_ts    # from the recorded input
pdf.docinfo['/Producer'] = f'NSCA {engine_version}'
pdf.trailer['/ID'] = [content_hash[:16], content_hash[:16]]
pdf.save(out, deterministic_id=False, normalize_content=True)
```

**Fonts must be embedded** — required for offline (C1) and it removes
font-version drift from the byte comparison.

**System dependencies:** WeasyPrint needs Pango/cairo. Fine in a container;
pinned in the image.

### python-docx

**Used for:** the editable export (FR-RPT-019). Renders from the same document
model.

---

## 12. Frontend

| Purpose | Technology |
|---|---|
| Framework | **React 19 + TypeScript** |
| Build | **Vite** |
| Styling | **Tailwind CSS** |
| Components | **shadcn/ui** (Radix primitives) |
| Server state | **TanStack Query** |
| Data tables | **TanStack Table** + virtualisation |
| Charts (UI) | **Recharts** |
| Charts (report) | **Custom SVG** — determinism |
| Graph layout | **dagre** + custom SVG |

**Why shadcn/ui:** Radix primitives give accessible behaviour (keyboard
navigation, focus management) which NFR-USE-007/008 require, and shadcn copies
components into your source rather than adding a runtime dependency you must
theme around.

**TanStack Table with virtualisation** for the finding workbench — an assessor
faces hundreds of findings and bulk-selects across them.

**Custom SVG for report charts, not Recharts.** Report output must be
byte-identical (FR-RPT-020) and legible in monochrome. A charting library's
label-placement heuristics are neither deterministic across versions nor
print-aware.

**dagre for attack-path layout, not a force-directed layout.** Force layouts are
non-deterministic and unreadable for chains. Attack paths are DAGs; a layered DAG
layout is both deterministic and easier to read.

**Config display is a custom renderer.** No syntax highlighter has grammars for
Cisco IOS or RouterOS, and you need precise control over line numbers, highlight
markers and secret masking anyway.

---

## 13. Testing

| Purpose | Technology |
|---|---|
| Test runner | **pytest** |
| Property-based | **Hypothesis** |
| Metamorphic | **Custom harness** (~300 lines) |
| Coverage | **pytest-cov** |
| Differential | Custom, against lab devices + OpenSCAP/CIS-CAT Lite |

**Hypothesis is load-bearing, not optional.** TRD-11.1's strategy is deliberately
property-heavy because this product's dangerous failures are silent. The
guarantees (G1–G4) are universally quantified statements, and property testing is
the only method that tests them as such:

```python
@given(control=controls(), omitted=facts())
def test_missing_fact_never_passes(control, omitted):
    facts = complete_fact_set(control) - {omitted}
    assert evaluate(control, facts).verdict != Verdict.PASS   # B2
```

**The metamorphic harness is custom** because the mutation catalogue is
grammar-aware — it must consult rulepack declarations for order-significant
constructs (TRD-11.2 DD-11.2-01). No general-purpose tool knows that.

---

## 14. Determinism-critical choices

These are the four places where a conventional choice silently breaks G1. Each is
a real trap, not a theoretical one.

| Trap | Wrong | Right |
|---|---|---|
| **Set iteration** | `for f in fact_set:` — order depends on `PYTHONHASHSEED`, random per process | `for f in sorted(fact_set, key=...)`, **and** `PYTHONHASHSEED=0` in the image |
| **Float scoring** | `112/143` → renders as `78%` or `79%` at boundaries, across platforms | `Fraction(112, 143)` — exact integer pair, rendered at fixed precision |
| **PDF metadata** | WeasyPrint stamps the clock and a random `/ID` | Normalise with pikepdf from the recorded generation time |
| **XML position** | `xmltodict` discards `sourceline` | `lxml` |

Enforced by CI (§16), not by discipline.

---

## 15. Infrastructure

### Docker + Compose

Three profiles from one file:

| Profile | Containers |
|---|---|
| **Standard** | web · worker · db · inference |
| **Air-gapped** | web · worker · db |
| **Workstation** | all-in-one |

**Deliberately absent:** Kubernetes (wrong scale, adds air-gap burden), Redis,
MinIO, a message broker, a separate search cluster, a service mesh.

### Air-gap inventory

Everything required at assessment time must ship in the image or as a signed
offline bundle:

| Item | Delivery |
|---|---|
| Python wheels | Vendored in the image; no install-time network |
| Fonts | Embedded in the image |
| Rulepacks, control packs | Shipped + signed offline bundles |
| Framework content (STIG XCCDF, NIST OSCAL) | Shipped + signed offline bundles |
| Vulnerability index | Offline snapshot, **age stated in every derived finding** |
| Inference model | Optional; Ollama model file, transferred by media |

**Nothing in `assessment/` may reach the network.** Verified by V-10.1-002.

---

## 16. CI and quality gates

**GitHub Actions**, with `ruff` (lint + format, replaces black/flake8/isort) and
`mypy` (strict on `assessment/` and `knowledge/`).

Three custom gates carry the guarantees. ~150 lines using the stdlib `ast`
module:

```python
def gate_g1_determinism():
    """No clock, no randomness, no model in assessment/."""
    # walk AST of every module under nsca/assessment/
    # fail on: import random | time.time | datetime.now | uuid4
    # fail on: any import from nsca.learning

def gate_g4_independence():
    """No write-capable path in transport/."""
    # assert every collect() call site passes a CommandId member
    # assert no signature in transport/ accepts `str` as a command
    # assert ALLOWLIST contains no config|write|commit|copy|reload verb

def gate_determinism_golden_set():
    """20 golden campaigns × 2 runs → compare report hashes."""
```

**The import-boundary check is the most valuable line in the whole CI config.**
`assessment/` must not import `learning/`. That one assertion makes *"no model in
the verdict path"* structural rather than a promise — and it's demonstrable to a
judge: *"here's the branch that introduces a model call, and here's the build
failing."*

---

## 17. Rejected alternatives

| Rejected | In favour of | Reason |
|---|---|---|
| Celery + Redis | Postgres `SKIP LOCKED` | One fewer air-gap component; transactional with the data |
| MinIO / S3 | Content-addressed filesystem | Unnecessary at 1–5 GB/campaign |
| SQLite for workstation | Postgres everywhere | Dual-backend behavioural drift is a determinism hazard |
| OPA / Rego | Custom evaluator | No Kleene logic; external process |
| CEL | Custom evaluator | Immature Python binding; wrong error semantics |
| networkx | Custom sorted adjacency | Dict-order iteration fights G1 |
| Drain3 | Custom miner | Per-line, not corpus-wide positional variability |
| xmltodict | lxml | No source line numbers → G3 unsatisfiable |
| stdlib `re` | `regex` | No timeout → unbounded backtracking on imported content |
| PyYAML | ruamel.yaml | Synthesis writes YAML humans review; comments must round-trip |
| ReportLab | WeasyPrint | Iteration speed on a layout-heavy document |
| Recharts in reports | Custom SVG | Non-deterministic layout; not print-aware |
| Force-directed graph | dagre DAG layout | Non-deterministic; unreadable for chains |
| NAPALM as primary | Netmiko | NAPALM normalises — we normalise; two layers is worse than one |
| Fine-tuned model | Rulepacks as data | Cannot audit, roll back, share, or train air-gapped |
| Kubernetes | Docker Compose | Wrong scale; adds air-gap burden |

---

## 18. Dependency policy

| Rule | Rationale |
|---|---|
| Pinned to exact versions, lockfile committed | A dependency bump can change output bytes — that is a determinism event |
| Vendored wheels in the image | No install-time network (C1) |
| Licence review before adoption | Distribution obligations must be satisfiable |
| No dependency in `assessment/` that performs I/O | G1 and C1 |
| No dependency that executes content it parses | C3 |

**Licences** across the core stack are permissive — BSD (lxml, WeasyPrint,
psycopg, Netmiko), MIT (FastAPI, Pydantic, ruamel.yaml, Lark, Hypothesis), MPL
(pikepdf), PostgreSQL licence. No copyleft obligations in the distributed
artifact.

**Framework content licensing is a separate and stricter matter** (NFR-CMP-001…005):
DISA STIG and NIST OSCAL are redistributable; **CIS text is restricted and ISO
27001 text cannot be redistributed at all** — identifiers only, enforced at the
data layer.

---

## 19. Summary — what each choice buys

| Choice | Buys |
|---|---|
| Python 3.12 | Ecosystem, PS-named libraries, team fit |
| PostgreSQL only | Invariants as constraints, one fewer component, one behaviour |
| Custom expression language | Kleene logic — the enforcement point for G2 |
| Custom graph | Determinism by construction |
| lxml | Evidence binding on XML platforms |
| `regex` with timeout | Safety against imported pathological patterns |
| pikepdf | The byte-identical claim actually holding |
| `Fraction` not float | No boundary-value score flips |
| Ollama, optional container | Air-gap operation; model genuinely removable |
| `CommandId` enum not `str` | G4 as a type, not a check |
| CI import-boundary gate | "No model in the verdict path" as structure, not promise |

> Every one of these traces to a constraint in §1. Nothing here is preference —
> which is the argument to make if a judge asks why the stack looks conservative.
