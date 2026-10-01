# 00 · Master Implementation Plan

> NSCA — AI-Driven Multi-Vendor Network Security Compliance Auditor
> SIH26155 · NTRO. Companion to the PRD ([`../docs/`](../docs/README.md)) and the
> TRD set ([`../trd/`](../trd/README.md)), which remain the source of truth for
> *what* is being built and *how* each subsystem works. **This plan does not
> restate their content.** Its job is the thing they deliberately don't cover:
> who builds what, in what order, against what shared contracts, so that five
> independent build tracks can work concurrently without colliding.

---

## 1. How to use this plan set

Seven documents, each self-contained enough to hand to one build track with no
other context beyond the PRD/TRD/architecture docs already in this repo.

| Doc | Track | Builder |
|---|---|---|
| [00-master-plan.md](00-master-plan.md) | Coordination | Everyone reads this first |
| [backend-01-assessment-engine.md](backend-01-assessment-engine.md) | Backend Track A | Claude Code (Sonnet) #1 |
| [backend-02-platform-learning-reporting-api.md](backend-02-platform-learning-reporting-api.md) | Backend Track B | Claude Code (Sonnet) #2 |
| [frontend-00-shared-foundations.md](frontend-00-shared-foundations.md) | Frontend Track 0 | Whichever Antigravity machine starts first — built once, then frozen |
| [frontend-01-ingestion-campaigns-estate.md](frontend-01-ingestion-campaigns-estate.md) | Frontend Track 1 | Antigravity (Gemini) #1 |
| [frontend-02-findings-risk-remediation.md](frontend-02-findings-risk-remediation.md) | Frontend Track 2 | Antigravity (Gemini) #2 |
| [frontend-03-training-knowledge-reports-admin.md](frontend-03-training-knowledge-reports-admin.md) | Frontend Track 3 | Antigravity (Gemini) #3 |

Every track plan has the same internal shape: scope and boundary, what it
depends on, what it must publish for others, file/module layout, milestone
sequence with a definition of done per milestone, testing obligations, and an
open-questions list. Each references exact PRD/TRD sections rather than
re-deriving them — **read the cited doc before writing the code it covers.**

---

## 2. Why five tracks, split this way

The product's own architecture document draws two boundaries that this plan
inherits rather than invents:

```
04-system-architecture.md §2, layered view
┌────────────────────────────────────────────────────────────┐
│  PRESENTATION                                    ← FRONTEND │
├────────────────────────────────────────────────────────────┤
│  APPLICATION SERVICES                                       │
│  Campaign mgmt · Collection orchestration · Finding         │
│  lifecycle · Adjudication · Remediation planning ·          │  ← BACKEND
│  Report generation · RBAC                                   │    TRACK B
├────────────────────────────────────────────────────────────┤
│  ASSESSMENT ENGINE   ← fully deterministic, no model calls  │  ← BACKEND
│  Ingest → Fingerprint → Parse → Extract → Graph →           │    TRACK A
│  Evaluate → Risk                                             │
├────────────────────────────────────────────────────────────┤
│  LEARNING SUBSYSTEM  ← model-assisted, human-ratified        │  ← BACKEND
│  Grammar inference · Template mining · Candidate proposal ·  │    TRACK B
│  Confirmation UI backend · Rule synthesis · Validation ·      │
│  Ratification                                                │
└────────────────────────────────────────────────────────────┘
```

**Backend Track A is the Assessment Engine box, verbatim** — pipeline stages
1–7 (Ingest, Fingerprint, Parse, Extract, Graph, Evaluate, Risk). It is a pure,
deterministic Python library with no database, no HTTP, no model calls, and no
knowledge of campaigns or users. This is not a convenience split — it is the
same boundary the product's own CI gates enforce (`gate_g1_determinism`,
"no import from `nsca.learning`" — [TECH-STACK.md §16](../TECH-STACK.md)), so
building it as a separately importable package makes the guarantee structural
from day one instead of retrofitted later.

**Backend Track B is everything else on the server**: Application Services
(Campaign/Finding/Dispute/Risk-acceptance lifecycle, RBAC), the Learning
Subsystem in full, Remediation planning, Report generation, the database, the
job queue, and the entire REST API surface ([15-api-specification.md](../docs/15-api-specification.md)).
It depends on Track A as a library dependency, never the reverse.

**Frontend is one product, three vertical slices** of the screen inventory in
[12-ux-specification.md §2](../docs/12-ux-specification.md), plus a shared
foundation built once:

```
Screen inventory (12-ux-specification.md §2)          Owner
──────────────────────────────────────────────────    ──────────
Campaigns (list/detail/comparison)                     Track 1
Ingestion dashboard                                    Track 1
Estate (device grid, device detail)                    Track 1
  ↳ embeds Finding cards, systemic-finding banner       from Track 2
Findings (workbench, detail, dispute)                  Track 2
Attack path explorer                                    Track 2
Remediation playbook / dry run views                    Track 2
Training Studio (queue, question flow, ratification)    Track 3
Knowledge (rulepacks, control packs, frameworks)         Track 3
Reports (library, viewer)                                Track 3
Administration (users, credentials, status)              Track 3
Design system, shell, routing, auth, API client, types   Track 0 (bootstrap)
```

Track 1 owns the highest-traffic entry points (demo beat 1 — bulk ingestion).
Track 2 owns the most visually complex work (custom SVG graph layout for
attack paths — [TECH-STACK.md §12](../TECH-STACK.md)). Track 3 owns the
product's signature feature (Training Studio — demo beat 2) plus the
lowest-interdependency screens (Knowledge, Reports, Admin), which makes it the
safest place to put work with the most PRD surface area (28 learning
requirements) and the least urgency to be first.

---

## 3. Repository layout

The repo (`nsca/`) is currently empty except for `docs/`, `trd/`, and the three
root documents. Every track builds inside this single repository, in its own
top-level package, so import boundaries are enforced by directory structure
and CI, not by convention.

```
nsca/
├── docs/                       existing PRD — do not edit except to fix an error
├── trd/                        existing TRD — do not edit except to fix an error
├── plans/                      this plan set
├── engine/                     BACKEND TRACK A — pure Python library
│   ├── pyproject.toml
│   └── nsca_engine/
│       ├── api.py              ← the ONLY module platform/ may import
│       ├── ingest/
│       ├── fingerprint/
│       ├── parse/               grammar engine, effective-config resolution
│       ├── extract/              extractor runtime, provenance/defaults
│       ├── schema/               schema registry (loads knowledge/schema/*.yaml)
│       ├── graph/                construction, reachability, counterexamples
│       ├── controls/             expression language, evaluation, coverage
│       ├── risk/                 exposure, attack paths, anomaly, systemic
│       ├── collection/           read-only transport driver (CommandId enum)
│       └── tests/                fixtures, corpus runner, metamorphic harness
├── platform/                   BACKEND TRACK B — FastAPI app, worker, DB
│   ├── pyproject.toml
│   └── nsca_platform/
│       ├── api/                  FastAPI routers, one file per API-spec section
│       ├── services/             campaign, finding lifecycle, dispute, risk-acceptance
│       ├── learning/              grammar inference, mining, proposal, synthesis
│       ├── remediation/           planner, safety, dry-run
│       ├── reporting/             document model, PDF/DOCX/JSON/CSV/OSCAL renderers
│       ├── knowledge_import/      STIG/CIS/NIST/ISO import, rulepack import/export
│       ├── db/                    SQLAlchemy Core models, Alembic migrations
│       ├── auth/                  RBAC, sessions, credential vault
│       ├── jobs/                  Postgres SKIP LOCKED queue, workers
│       ├── audit/                 hash-chained audit log
│       └── tests/
├── knowledge/                   SHARED DATA — not owned by any track's code,
│   ├── schema/                   but both backend tracks read/write it at runtime
│   ├── rulepacks/                 (see §5.4 — this is content, not source code)
│   ├── control_packs/
│   └── frameworks/
├── frontend/                    FRONTEND TRACKS 0–3 — one React app
│   ├── package.json
│   └── src/
│       ├── shared/                Track 0 — frozen after Phase 0, see its plan
│       ├── campaigns/ estate/ ingestion/         Track 1
│       ├── findings/ attack-paths/ remediation/  Track 2
│       ├── training/ knowledge/ reports/ admin/  Track 3
│       └── app/                   router, top-level shell (Track 0)
├── docker-compose.yml            profiles: standard · air-gapped · workstation
├── .github/workflows/            CI — see §7
└── README.md                     setup + air-gapped install instructions
```

**Rule:** a track may only write inside its own top-level directory (`engine/`,
`platform/`, `frontend/src/<its slices>`) plus `plans/<its own doc>.md` for
notes. Cross-cutting changes (a new field on a shared contract) are proposed as
a diff to the relevant contract section of this file and called out loudly in
the proposing track's own plan doc under "Open questions," not made silently.

---

## 4. Phase plan

Phases are dependency-ordered, not calendar-dated — map them onto your actual
deadline. The critical path is **Phase 0**: every other phase's parallelism
depends on Phase 0 finishing fast and being genuinely frozen afterward.

### Phase 0 — Foundations & contracts (short; blocks everything else)

| Owner | Deliverable |
|---|---|
| Backend Track A | `engine/nsca_engine/api.py` skeleton — the two entry-point function signatures (§5.1) with typed dataclasses, raising `NotImplementedError`, plus the schema registry loader reading `knowledge/schema/*.yaml` |
| Backend Track B | Repo scaffold, `docker-compose.yml` (3 profiles), Postgres + Alembic wired up, FastAPI skeleton with **every route from [15-api-specification.md](../docs/15-api-specification.md) stubbed** returning realistic mock JSON matching the spec's examples, OpenAPI schema publishing at `/api/v1/openapi.json`, auth stub (one hardcoded role-switchable dev user) |
| Frontend Track 0 | Design system, routing shell, API client generated against Track B's stub OpenAPI schema, shared TS types, verdict/severity visual language — see [frontend-00](frontend-00-shared-foundations.md) |
| All | Agree the exact contract in §5 of this document is frozen. Any change after this point is a versioned addendum, not a silent edit |

**Definition of done for Phase 0:** a frontend developer can run
`docker compose up` and click through every screen in the UX spec against
mock data with zero backend logic implemented. This is what unblocks Tracks
1–3 to start real UI work on day one instead of waiting on the engine.

### Phase 1 — Core build (parallel, the bulk of the schedule)

Each track builds against the frozen Phase 0 contracts. Backend Track A works
entirely against fixtures and the corpus — it does not need Track B's API or
database to make progress, and should not wait for it. Backend Track B builds
the real logic behind its stub endpoints, initially against fixture
`AssessmentResult` objects hand-built from PRD examples (e.g. the
[00-product-overview.md §9](../docs/05-security-baseline-model.md) worked
example) rather than waiting for Track A's real pipeline. Frontend tracks build
against the real, evolving API — the contract shape doesn't change, only
whether the response is mocked or real.

### Phase 2 — Integration

- Track B swaps its fixture-based worker for a real call into
  `nsca_engine.api.assess_device` / `assess_campaign`.
- Frontend points at the real backend end-to-end; mock service workers are
  removed.
- Corpus regression, metamorphic, and determinism CI gates run for the first
  time against the full pipeline (they run against Track A alone from Phase 1
  onward, but only exercise the whole system here).
- Cross-track integration points from §6 are resolved and merged.

### Phase 3 — Demo readiness

- The three demonstration beats from
  [17-traceability-matrix.md §5](../docs/17-traceability-matrix.md) are
  rehearsed end-to-end, offline, with a timer:
  1. Bulk ingestion across platforms including cloud JSON, offline, in seconds
  2. Teaching an untaught platform live (MikroTik or equivalent), 0% → ≥70% coverage
  3. The per-device PDF — serials, evidence, version-specific remediation with
     a lockout warning, and the unassessed section
- Performance validated against [13-nonfunctional-requirements.md §NFR-PERF](../docs/13-nonfunctional-requirements.md).
- README with air-gapped install instructions finalised.
- [DECK.md](../DECK.md) (5-slide technical presentation) and the 2-page
  architecture document reconciled against what was actually built, not what
  was planned.
- Run the verification checklist in
  [17-traceability-matrix.md §9](../docs/17-traceability-matrix.md) top to bottom.

---

## 5. The cross-track contracts

These are the only interfaces that must be agreed before parallel work is
safe. Everything else is internal to a track.

### 5.1 The engine contract (Backend Track A → Backend Track B)

Two entry points, both pure functions: same inputs, same output, forever.
Full detail and rationale in
[backend-01-assessment-engine.md §4](backend-01-assessment-engine.md) and
[backend-02 §3](backend-02-platform-learning-reporting-api.md); reproduced
here because both tracks must treat it as fixed.

```python
# engine/nsca_engine/api.py

@dataclass(frozen=True, slots=True)
class RawArtifact:
    id: str                       # platform-assigned artifact id, opaque to the engine
    filename: str
    content: bytes
    artifact_type_hint: ArtifactType | None   # from custody metadata, not trusted
    received_from: str

@dataclass(frozen=True, slots=True)
class KnowledgeBase:
    schema_registry: SchemaRegistry
    rulepacks: tuple[Rulepack, ...]
    control_packs: tuple[ControlPack, ...]
    pin: KnowledgeBasePin          # engine version + every content version, for the manifest

def assess_device(
    artifacts: tuple[RawArtifact, ...],
    knowledge_base: KnowledgeBase,
    assessed_at: datetime,         # D2 — time is an input, never read internally
) -> DeviceAssessment: ...

def assess_campaign(
    device_assessments: tuple[DeviceAssessment, ...],
    knowledge_base: KnowledgeBase,
) -> CampaignAssessment: ...
```

`DeviceAssessment` carries: fingerprint result, `facts: tuple[Fact, ...]` (full
Security Baseline Model instance with provenance —
[14-data-model.md §2](../docs/14-data-model.md)), `unmatched_constructs`,
this device's graph contribution (nodes/edges), per-control findings with
verdict/evidence/coverage inputs (severity is **base**, not yet
exposure-weighted), and `grammar_coverage`.

`CampaignAssessment` carries: the merged estate graph, exposure-weighted
(**effective**) severities, `attack_paths`, `peer_anomalies`,
`systemic_findings`, and scope-contamination annotations — everything that
requires seeing more than one device at once (FR-GRF-004, FR-RSK-006,
FR-RSK-008).

**Why two calls instead of one:** Track B's worker assesses devices
independently and in parallel (`multiprocessing.Pool(8)`,
[TECH-STACK.md §3](../TECH-STACK.md)) as artifacts complete correlation, then
runs the campaign-wide pass once every in-scope device that will be collected
has been assessed or the collection window closes. Splitting the contract this
way is what makes that scheduling possible without the engine knowing
anything about jobs, campaigns, or partial collection.

**Non-negotiable properties of this contract** (enforced by the CI gates in
§7, owned by whichever track's code is being gated):

- No argument or return value contains a database handle, an HTTP object, a
  file path, or a model client.
- Calling either function twice with identical arguments returns
  byte-for-byte identical results (`==` on the dataclasses, and identical
  `repr()`), from any process, any run — see D1–D8 in
  [TRD-00 §7](../trd/TRD-00-conventions-and-verification.md).
- `engine/` has zero import of anything under `platform/`. `platform/` may
  only import `nsca_engine.api` (never reach into `nsca_engine.parse`,
  `.graph`, etc. directly) — this keeps the contract from eroding into an
  informal grab-bag of internals.

### 5.2 The REST API contract (Backend Track B → all Frontend tracks)

[15-api-specification.md](../docs/15-api-specification.md) *is* the contract,
verbatim, including every example JSON payload shown there. Track B does not
redesign it; frontend tracks do not invent endpoints it doesn't define. If a
screen genuinely needs a field or endpoint the spec doesn't have, that's a
Phase 0/1 addendum proposed in writing (§3's rule), not an ad hoc addition on
either side.

Track B publishes the live OpenAPI schema at `/api/v1/openapi.json` from
Phase 0 onward (stub responses, real shapes). Frontend Track 0 generates
TypeScript types from it once in Phase 0 and re-generates on every contract
change — see [frontend-00 §3](frontend-00-shared-foundations.md).

### 5.3 Shared frontend contracts (Track 0 → Tracks 1–3)

Design tokens, the verdict/severity visual language
([12-ux-specification.md §10](../docs/12-ux-specification.md)), the
`EvidenceExcerpt`, `VerdictBadge`, `SeverityBadge`, `CoverageBar` primitives,
the API client, generated types, the route shell and auth guard. Full list in
[frontend-00 §2](frontend-00-shared-foundations.md). Frozen at the end of
Phase 0; additive changes only afterward, and any track needing one asks
Track 0 (or, if Track 0 has disbanded into another track by then, whichever
track currently owns `frontend/src/shared/`) rather than forking it.

### 5.4 Knowledge base content (shared data, not code)

`knowledge/` holds rulepacks, control packs, schema registry entries, and
framework packs as YAML/JSON files — declarative content per
[NFR-SEC-007](../docs/13-nonfunctional-requirements.md), never code. Both
backend tracks read it: Track A's `SchemaRegistry`/`Rulepack`/`ControlPack`
loaders consume it to build the `KnowledgeBase` object passed into `assess_*`;
Track B's learning subsystem and knowledge-import pipeline **write** new
versions of it (rule synthesis, framework import). Track A never writes to
`knowledge/`; Track B never bypasses Track A's loader to interpret rulepack
YAML itself — both tracks parsing the same format independently is exactly the
kind of drift the versioned-data-not-code design exists to prevent.

The YAML shapes for rulepacks, control packs, and schema entries are already
fully specified with worked examples in
[07-vendor-rulepacks.md §2–7](../docs/07-vendor-rulepacks.md),
[06-controls-and-frameworks.md §3](../docs/06-controls-and-frameworks.md), and
[05-security-baseline-model.md §7](../docs/05-security-baseline-model.md).
Track A implements the reader; Track B implements the writer (rule synthesis
output, framework import output); neither redefines the format.

### 5.5 Named integration points inside the frontend

Two UX-spec screens are owned by one track but embed a component whose natural
owner is another:

| Component | Appears on | Built by | Consumed by |
|---|---|---|---|
| `<FindingCard>` / finding summary row | Device detail (Estate, Track 1) and Finding workbench (Track 2) | Track 2 | Track 1 imports it from `frontend/src/findings/components/` |
| `<SystemicFindingBanner>` | Estate view banner (Track 1) and Findings workbench grouping (Track 2) | Track 2 | Track 1 imports it |

Track 1 should build a minimal inline placeholder for both in early Phase 1
(so its screens are demoable standalone) and swap to Track 2's real component
once published — same pattern as the backend's fixture-then-real approach in
Phase 1 → 2.

---

## 6. Definition of done

A track's Phase 1 work is done when its own plan doc's milestone checklist is
complete **and**:

- All tests it owns pass in CI (unit/property for both backend tracks;
  component tests + a11y checks for frontend).
- No import-boundary violation (§5.1's rule, §7's gate).
- Every UI screen it owns matches its UX-spec mock at the level of: correct
  states shown (§10.1 verdict treatment, §10.2 severity, §10.3 trust
  indicators), keyboard-navigable, WCAG 2.1 AA contrast.

The **product** is release-ready when every item in
[17-traceability-matrix.md §9](../docs/17-traceability-matrix.md) is checked
and the 14 BLOCKING verification criteria enumerated in
[TRD-11.3](../trd/TRD-11.3-acceptance-criteria.md) pass, including at minimum
the five load-bearing ones from [trd/README.md](../trd/README.md):

| ID | Claim | Owner |
|---|---|---|
| V-10.1-001 | Byte-identical output for identical inputs | Backend A (engine determinism) + Backend B (report determinism, pikepdf) |
| V-05.2-004 | A missing fact yields UNKNOWN, never PASS | Backend A |
| V-08.3-002 | A polarity-inverting rule cannot be saved without explicit confirmation | Backend B |
| V-11.2-001 | Semantics-preserving mutation produces identical facts | Backend A |
| V-11.3-009 | A new platform reaches ≥70% coverage with no code change or redeployment | Backend B (learning) + Backend A (engine consumes the resulting rulepack unchanged) |

---

## 7. CI and quality gates

Backend Track A and Track B each own the gates over their own code; both are
wired into one GitHub Actions pipeline from Phase 0.

| Gate | Checks | Fails the build if |
|---|---|---|
| `gate_g1_determinism` | AST-walks `engine/nsca_engine/` | Any import of `random`, `time.time`, `datetime.now`, `uuid4`, or anything from `platform/` |
| `gate_g4_independence` | AST-walks `engine/nsca_engine/collection/` and `platform/nsca_platform/api/` | Any `collect()` call site not passing a `CommandId` member; any signature accepting a raw `str` command; any API route accepting a device-write operation |
| `gate_determinism_golden_set` | Runs 20 golden campaigns through the full pipeline twice | Report hashes differ between runs |
| `gate_import_boundary` | Static import check | `platform/` imports anything under `nsca_engine.*` other than `nsca_engine.api`; `engine/` imports anything under `platform/` |
| Lint/type | `ruff`, `mypy --strict` on `engine/` and `platform/nsca_platform/{services,learning}` | Any violation |
| Frontend | `eslint`, `tsc --noEmit`, `axe` a11y check on changed routes | Any violation |

Full detail on the first three (they are specified, not invented, in
[TECH-STACK.md §16](../TECH-STACK.md)) belongs to Backend Track B, which owns
the CI pipeline definition; Backend Track A is responsible for its own code
passing them.

---

## 8. Risk register

Carried over from [00-product-overview.md §8](../docs/00-product-overview.md),
with an owning track and a plan-level mitigation added.

| # | Risk | Owner | Plan-level mitigation |
|---|---|---|---|
| R1 | Grammar inference fails on structurally hostile formats (PAN-OS, FortiOS) | Backend A | Prove grammar inference against 5 real formats in Phase 1 before the learning UI (Backend B / Frontend 3) is built around it; keep the "assisted grammar authoring" fallback path from [08-learning-system.md §3.3](../docs/08-learning-system.md) in scope, not deferred |
| R2 | The Security Baseline Model is designed wrongly and everything downstream inherits the error | Backend A | Schema registry is loaded from `knowledge/schema/*.yaml`, versioned from Phase 0 — validate it against real configs from ≥4 platforms before Phase 1 extractor work begins, per [05-security-baseline-model.md](../docs/05-security-baseline-model.md)'s own instruction |
| R3 | An administrator teaches an inverted polarity | Backend B | Polarity confirmation is a distinct, non-optional field in the `TrainingAnswer` API model (`422` if absent when required — [TECH-STACK.md §4](../TECH-STACK.md)); build this validation in Phase 1, not as a later hardening pass |
| R4 | Coverage honesty reads as weakness in the demo | All (framing) | Coverage score is a first-class UI element from Track 0's design system, not a Track 3 afterthought — bake it into shared components before individual screens are built |
| R5 | CIS/ISO licensing — cannot redistribute text | Backend B | `FRAMEWORK_ITEM.text_redistributable` is a DB constraint, not a UI convention (DM-9, [14-data-model.md §7](../docs/14-data-model.md)) — enforce at the import layer in Phase 1 |
| R6 | Attack-path analysis demonstrates poorly on unrealistic topologies | Backend A + whoever builds the corpus | Build the synthetic reference estate (multi-device, known reachability properties) as a Phase 1 deliverable, not a demo-week scramble |
| R7 | Provenance lost when facts are extracted by a model | Backend B (learning) | Enforced by the contract itself — rule synthesis output is a deterministic rule (§5.4); the model never writes a fact directly |

---

## 9. What not to build

Reiterating [00-product-overview.md §5.2](../docs/00-product-overview.md) so
no track scope-creeps into it under time pressure: no capability to push
configuration to a device, no real-time monitoring, no firmware binary
analysis, no active vulnerability probing, no traffic-based intrusion
detection, no configuration backup/change-management system. If a track's plan
seems to be growing one of these, stop and re-read
[04-system-architecture.md §11](../docs/04-system-architecture.md).
