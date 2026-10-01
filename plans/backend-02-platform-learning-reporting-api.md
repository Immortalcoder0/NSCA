# Backend Track B · Platform, Learning, Risk-Adjacent Workflows, Reporting & API

> Builder: Claude Code (Sonnet), backend engineer #2.
> Package: `platform/nsca_platform/`. This is everything in
> [04-system-architecture.md §2](../docs/04-system-architecture.md)'s
> Application Services and Learning Subsystem boxes, plus the entire REST API
> surface. Read [00-master-plan.md](00-master-plan.md) first for the
> repo layout and the engine contract you consume.

---

## 1. Scope and boundary

**You own:** the database, the job queue, authentication/RBAC, the full API
surface ([15-api-specification.md](../docs/15-api-specification.md)), campaign
and finding lifecycle, dispute/adjudication, risk acceptance, the Learning
Subsystem (grammar inference through ratification), knowledge-base import
(rulepack import/export, STIG/CIS/NIST/ISO framework import), the remediation
planner, report generation, the hash-chained audit log, and determinism
enforcement of everything you render (PDF metadata, etc.).

**You do not own:** anything in [Backend Track A](backend-01-assessment-engine.md)'s
engine — parsing, extraction, control evaluation, graph/reachability, attack
paths, or exposure weighting. You call it as a library.

### 1.1 TRD reading list, in build order

```
TRD-00   Conventions and Verification            — read first
TRD-02.2 Grammar Inference
TRD-05.3 Framework Import and Mapping
TRD-07.1 Remediation Planner, Safety and Dry Run
TRD-08.1 Template Mining and Question Selection
TRD-08.2 Candidate Proposal and Polarity
TRD-08.3 Rule Synthesis and Validation Gates
TRD-08.4 Cross-Platform Transfer and Metrics
TRD-09.1 Report Generation Pipeline
TRD-10.1 Determinism Enforcement            — your part: report/PDF, CI gates
TRD-10.2 Custody and Hash-Chained Audit Log
TRD-11.1 Test Strategy                       — you coordinate this across both backend tracks
TRD-11.3 Acceptance Criteria and Coverage Assertion — you own the release-gate checklist
```

Also required: [02-personas-and-journeys.md](../docs/02-personas-and-journeys.md)
in full (it is the shape of every workflow you're building — Priya's audit
lifecycle §5, Rahul's teaching journey §6, Vikram's ratification §7),
[08-learning-system.md](../docs/08-learning-system.md) in full,
[09-findings-lifecycle.md](../docs/09-findings-lifecycle.md) in full,
[10-reporting.md](../docs/10-reporting.md) in full,
[11-audit-integrity.md](../docs/11-audit-integrity.md) in full,
[14-data-model.md](../docs/14-data-model.md) in full (you own the physical
schema for all of it), [15-api-specification.md](../docs/15-api-specification.md)
in full (you implement all of it, unmodified).

---

## 2. Design constraints

### 2.1 The engine is a black box you call, not a library you reach into

You import exactly one module: `nsca_engine.api`. If you find yourself
wanting `nsca_engine.parse.grammar` directly, that need belongs in the engine
contract — propose the addition to Backend Track A rather than reaching past
`api.py`. `gate_import_boundary` enforces this.

### 2.2 Rulepacks and control packs are content, not your data model

The YAML you read and write under `knowledge/` (§5.4 of
[00-master-plan.md](00-master-plan.md)) must exactly match the shapes
specified in [07-vendor-rulepacks.md](../docs/07-vendor-rulepacks.md) and
[06-controls-and-frameworks.md §3](../docs/06-controls-and-frameworks.md) —
these are the same files Track A's `SchemaRegistry`/`Rulepack` loaders parse.
Rule synthesis output (§4.3 below) must be a file your own writer produces
that Track A's reader — which you did not write — can load without
modification. Treat "can Track A's loader parse what I just wrote" as a
literal integration test, not an assumption.

### 2.3 Every state-changing endpoint writes the audit log

Per [11-audit-integrity.md §7](../docs/11-audit-integrity.md) and API
principle A2 — this is not a middleware you bolt on later. Design the audit
log write as part of the same service-layer function that performs the state
change (same transaction), from the first endpoint you build, so it is
structurally impossible to add a ninth endpoint that forgets it.

### 2.4 422 carries product meaning

[TECH-STACK.md §4](../TECH-STACK.md) and
[15-api-specification.md §10](../docs/15-api-specification.md) are explicit:
risk-acceptance without `expires_at`, polarity confirmation absent when
required, a ratifier equal to the author, `mode` other than `read_only` on
collection — these are Pydantic validators, not service-layer `if` checks
that might get skipped by a future code path. Write them as model validators
(`@model_validator`) on the request schema itself, the way
[TECH-STACK.md §4](../TECH-STACK.md) shows for `TrainingAnswer` and
`CollectionRequest`.

### 2.5 Determinism extends to what you render

WeasyPrint stamps `/CreationDate` from the clock and a random `/ID`. You must
normalise this with `pikepdf` using the recorded generation time from the
assessment, exactly as shown in
[TECH-STACK.md §11](../TECH-STACK.md) — otherwise the byte-identical claim
(FR-RPT-020, V-10.1-001) is false the moment a report is regenerated, and
nobody will notice until someone tries to verify one.

---

## 3. The engine contract you consume

Identical to [backend-01 §4](backend-01-assessment-engine.md) — do not
duplicate a second copy of these dataclasses in your own codebase; import
`nsca_engine.api` types directly wherever you need to reference
`DeviceAssessment`/`CampaignAssessment` shapes, and map them onto your own
SQLAlchemy models in a single `db/mappers.py` module rather than scattering
the mapping across services.

```python
from nsca_engine.api import assess_device, assess_campaign, KnowledgeBase, RawArtifact
```

Your worker's job, at a high level:

```
1. Load campaign's correlated device artifacts (bytes) from the artifact store
2. Load current KnowledgeBase (schema registry + rulepacks + control packs)
3. For each device (parallel, multiprocessing.Pool(8)):
     result = assess_device(artifacts, knowledge_base, assessed_at)
     persist result → fact, finding, graph_node/edge tables
4. Once all in-scope devices are assessed (or collection window closed):
     campaign_result = assess_campaign(all device results, knowledge_base)
     persist → attack_path, systemic_finding, effective severities
5. Remediation planner runs per FAIL finding (your code, §4.4)
6. Report generator runs per device + estate (your code, §4.6)
```

Until Track A's `assess_device`/`assess_campaign` are real, build and test
this worker against **fixture** `DeviceAssessment`/`CampaignAssessment`
objects you hand-construct from the worked examples in
[05-security-baseline-model.md §9](../docs/05-security-baseline-model.md) and
[09-findings-lifecycle.md §3](../docs/09-findings-lifecycle.md) — do not block
Phase 1 work on Track A's completion. Swap the fixture for the real call in
Phase 2 (see [00-master-plan.md §4](00-master-plan.md)).

---

## 4. Module layout and subsystem notes

```
platform/nsca_platform/
├── api/                        one router module per API-spec section
│   ├── campaigns.py             §2
│   ├── ingestion.py              §3
│   ├── assessment.py             §4
│   ├── findings.py               §5
│   ├── training.py               §6
│   ├── knowledge.py              §7
│   ├── reports.py                §8
│   ├── admin.py                  §9
│   └── webhooks.py               §11 — dispatch, not receipt
├── services/
│   ├── campaign.py               state machine FR-CMP-005, scope resolution
│   ├── finding_lifecycle.py       state machine §4 of 09-findings-lifecycle.md
│   ├── dispute.py                 adjudication, compensating-control verification
│   │                              (calls nsca_engine.api graph/reachability query)
│   ├── risk_acceptance.py         mandatory expiry, auto-reopen job
│   └── verification.py            re-collect → re-assess → compare, §8 of 09
├── learning/                    §4.3 below
│   ├── grammar_inference.py       TRD-02.2 — statistical, no model
│   ├── template_mining.py         TRD-08.1
│   ├── candidate_proposal.py      TRD-08.2 — model-assisted, Ollama client
│   ├── polarity.py                explicit confirmation gate
│   ├── rule_synthesis.py          TRD-08.3 — writes knowledge/rulepacks/*.yaml
│   ├── validation_gates.py        self-match, corpus-scope, conflict, regression,
│   │                              metamorphic, coverage-delta
│   ├── ratification.py            two-person rule
│   └── transfer_metrics.py        TRD-08.4 — the learning-curve data
├── remediation/                 §4.4 below
│   ├── planner.py
│   ├── lockout.py                 evaluates operator source against proposed ACL
│   │                              (calls nsca_engine graph query)
│   └── dry_run.py
├── reporting/                   §4.6 below
│   ├── document_model.py          shared model feeding PDF/DOCX
│   ├── pdf.py                     WeasyPrint + Jinja2 + pikepdf
│   ├── docx.py                    python-docx
│   ├── exports.py                 JSON, CSV, OSCAL
│   └── determinism.py             pikepdf metadata normalisation
├── knowledge_import/            §4.5 below
│   ├── stig_xccdf.py              direct XML parse
│   ├── nist_oscal.py              direct JSON parse
│   ├── cis_pdf.py                  assisted extraction, model + ratification
│   ├── iso_identifiers.py          identifiers only — NFR-CMP-002
│   ├── rulepack_bundle.py          import/export, signature verification
│   └── preview.py                  estate-impact dry run before ratify
├── db/
│   ├── models/                    one module per data-model entity group
│   │   ├── campaign.py device.py artifact.py assessment.py finding.py
│   │   ├── lifecycle.py           dispute, risk_acceptance, remediation_plan, verification
│   │   ├── knowledge.py            rulepack, extractor, default, fact_definition, control,
│   │   │                          framework_item — metadata only; content stays in knowledge/
│   │   ├── graph.py                graph_node/edge, attack_path, systemic_finding
│   │   └── admin.py                user, role, audit_log_entry, collection_credential, report
│   ├── mappers.py                  nsca_engine.api dataclass ↔ SQLAlchemy model
│   └── migrations/                 Alembic
├── auth/                          RBAC (5 roles, FR-ADM-002), sessions, credential vault
├── jobs/                          Postgres SKIP LOCKED queue + worker entrypoints
├── audit/                         hash-chained append-only log (§2.3)
└── tests/
```

### 4.1 Database — key decisions already made for you

Per [TECH-STACK.md §5](../TECH-STACK.md), don't re-litigate these:

- **PostgreSQL only**, even for the single-node workstation profile. No
  SQLite dual-backend.
- **SQLAlchemy Core, not the ORM** — explicit SQL for the append-only rules,
  JSONB queries, and the `SKIP LOCKED` queue.
- **JSONB for facts**, with `value jsonb NULL` meaning ⊥, never confusable
  with `false`. Reproduce the exact table shape from
  [TECH-STACK.md §5](../TECH-STACK.md).
- Constraints enforce invariants at the DB layer, not just in service code:
  `two_person_rule` CHECK constraint (`ratified_by IS NULL OR ratified_by <>
  taught_by`), append-only RULEs on `audit_log` (`ON UPDATE/DELETE DO
  INSTEAD NOTHING`). Write these as part of the first migration that creates
  each table, not as a follow-up hardening migration.
- Job queue is a Postgres table with `FOR UPDATE SKIP LOCKED`, no Redis, no
  Celery.
- Artifact bytes live in a content-addressed filesystem
  (`artifacts/<sha256[:2]>/<sha256[2:4]>/<sha256>`, write-once, `0400`), not
  in the database and not in MinIO/S3.

### 4.2 API — build order within `api/`

Follow the dependency order implied by the journeys, not the document order:
`campaigns.py` and `ingestion.py` first (nothing else works without a
campaign and artifacts), then `assessment.py` (even against the fixture
engine calls from §3), then `findings.py`, then `training.py` (unblocks
Frontend Track 3 early — it's the highest-value demo screen), then
`knowledge.py`, `reports.py`, `admin.py`, `webhooks.py` last.

Every endpoint's response shape must match the JSON examples in
[15-api-specification.md](../docs/15-api-specification.md) exactly, field for
field — Frontend tracks are building against those exact shapes from Phase 0.
If a field is missing from your DB model to satisfy an example, that's a
schema gap to fix, not a reason to change the response shape.

### 4.3 Learning subsystem — the product's hardest requirement

Build the pipeline in the order it runs, and get each stage demonstrably
correct in isolation before wiring the next:

1. **Grammar inference** (TRD-02.2) — purely statistical. Test it against
   the MikroTik worked example in
   [08-learning-system.md §3.2](../docs/08-learning-system.md); you should
   reproduce `coverage: 98.4%` on that exact input. On low coverage, refuse
   and report the coverage figure rather than guessing (§3.3 of that doc) —
   this refusal path is itself a test case, not an unhandled branch.
2. **Template mining** (TRD-08.1) — corpus-wide positional variability, not
   per-line (this is why Drain3 was rejected — see
   [TECH-STACK.md §9](../TECH-STACK.md); a token is a slot because it varies
   *across occurrences of the same skeleton*, not because it merely looks
   like a value).
3. **Relevance filtering + information-gain ordering** — score against the
   fact vocabulary your loaded controls actually require. Target: the
   MikroTik example collapses to 9 ordered questions
   ([08-learning-system.md §4](../docs/08-learning-system.md)) — use this as
   your acceptance fixture.
4. **Candidate proposal** (TRD-08.2) — lexical priors + structural analogy +
   value-shape, with the model (Ollama + Qwen2.5-7B-Instruct,
   JSON-schema-constrained so it can only select from registered fact paths —
   [TECH-STACK.md §9](../TECH-STACK.md)) refining. **Redact secrets before
   any model invocation** (FR-LRN-028) — write the redaction step as
   something that runs unconditionally before the Ollama client call, not as
   a configurable option.
5. **Polarity** — always its own explicit confirmable field, never inferred
   silently. This is the one place in the whole product where a bug produces
   a confident wrong answer instead of an honest UNKNOWN — treat the
   validation gate for it (§2.4 above, `V-08.3-002`) as release-blocking from
   the day you write it, not something to harden before ship.
6. **Rule synthesis** (TRD-08.3) — writes a rulepack YAML file. Run it
   through Track A's real loader as an integration test the moment both
   sides exist (§2.2).
7. **Validation gates** — self-match, corpus-scope, conflict, type,
   regression, metamorphic, coverage-delta. All six must run before a
   provisional rule is even saved, not just before ratification.
8. **Ratification** — two-person rule enforced at the DB layer (§4.1).
   Provisional rules' findings must be excluded from issued reports (DM-5) —
   enforce this as a filter in the report generator (§4.6), not as a
   convention the learning module promises to uphold.
9. **Transfer metrics** (TRD-08.4) — record confirmations-to-70%,
   acceptance rate, polarity-correction rate, wall-clock time, from the
   *first* platform you teach, including your own team's onboarding of the
   platforms shipped in the box (§1 of
   [07-vendor-rulepacks.md](../docs/07-vendor-rulepacks.md): there is no
   separate mechanism for shipped vs. taught rulepacks — build the certified
   rulepacks through this same pipeline, and the learning curve data starts
   accumulating immediately). This metric is the product's central claim; if
   you build it last and skip it under time pressure, the demo has nothing to
   show for "Scalability & Adaptation."

### 4.4 Remediation planner (TRD-07.1)

Version-specific (`(control, platform, version_range)` keyed — you read this
from the control pack's `remediation` block, not from a separate table),
dependency-ordered, impact-classified. The lockout check needs a live query
against the graph — call `nsca_engine.api`'s reachability query with the
assessor's own source address against the proposed management ACL model; do
not approximate this in your own code, since a wrong lockout check is worse
than no lockout check. Dry-run re-evaluates using Track A's evaluation
function against the *modelled* post-remediation fact set — build a
`apply_remediation_to_facts(facts, plan) -> facts` transform in your own code
(this is data manipulation, not engine logic) and then call
`nsca_engine.api`'s per-device evaluation path (expose whatever narrower
entry point you need for this — propose it as a contract addition if
`assess_device` doesn't already decompose cleanly enough to reuse just the
evaluation stage).

### 4.5 Knowledge import

STIG XCCDF and NIST OSCAL are direct, fully machine-readable parses — build
these first, they unblock a large, real control library fast
([06-controls-and-frameworks.md §5](../docs/06-controls-and-frameworks.md)
says begin here). CIS PDF extraction is assisted (model proposes a formal
control from the PDF's consistent per-recommendation template; a human
ratifies) — same confirm-don't-author shape as the learning subsystem, and it
also populates the defaults table from CIS's documented "Default Value"
sections, which directly reduces `default_unknown` facts once Track A's
extractors run. ISO is identifier-only, enforced by
`FRAMEWORK_ITEM.text_redistributable = false` at the DB layer (DM-9) — do not
store or render ISO clause text anywhere, including in test fixtures, or the
constraint you're supposed to be enforcing gets violated by your own test
data.

### 4.6 Reporting (TRD-09.1)

One document model feeds PDF and DOCX, per
[TECH-STACK.md §11](../TECH-STACK.md) — build `document_model.py` first as a
pure data-transform from `(DeviceAssessment, CampaignAssessment, findings,
remediation plans)` to a structured document tree, then two thin renderers.
This is what keeps the two formats from diverging (FR-RPT-019's requirement
implicitly depends on it). Report generation must not recompute anything
(RPT-2, [10-reporting.md §5](../docs/10-reporting.md)) — it renders stored
assessment results only; if a report screen needs a number the stored
assessment doesn't have, that's a gap in what you persisted in step 3–4 of
§3's worker pipeline, not something to compute at render time.

Build the per-device PDF's eight sections in the order given in
[10-reporting.md §2](../docs/10-reporting.md) — Section 1 (cover/ID) and
Section 6 (Unassessed) are the two sections a competing tool is least likely
to have, and both are cheap relative to their evidentiary value; do not let
them slip to "if time permits."

---

## 5. Milestones

**M0 — Scaffold (Phase 0)**
Repo/Docker/Postgres/Alembic/FastAPI skeleton with every endpoint in
[15-api-specification.md](../docs/15-api-specification.md) stubbed, returning
the spec's own example payloads verbatim (hardcoded). OpenAPI schema live at
`/api/v1/openapi.json`. One dev auth user, role-switchable via a header, so
frontend can test RBAC-gated UI without a real login flow yet. Done when: a
frontend developer can complete every UX-spec journey against mock data.

**M1 — Campaign, ingestion, artifact custody (Phase 1)**
Real DB models + migrations for `CAMPAIGN`, `DEVICE`, `ARTIFACT`; real
custody/correlation persistence (calling Track A's `ingest`/`fingerprint`
logic via the fixture-then-real pattern from §3); collection completeness
reporting (FR-ING-015/016). Done when: bulk upload of a real multi-platform
directory produces the four outcome states from
[15-api-specification.md §3](../docs/15-api-specification.md)'s example
verbatim.

**M2 — Assessment worker + finding lifecycle (Phase 1)**
The worker pipeline from §3, against fixtures. Full finding state machine
([09-findings-lifecycle.md §4](../docs/09-findings-lifecycle.md)), dispute +
machine-verified compensating controls (calling Track A's reachability
query), risk acceptance with mandatory expiry and auto-reopen. Done when: the
MGMT-SW-04 REFUTED dispute example
([09-findings-lifecycle.md §6.1](../docs/09-findings-lifecycle.md)) is
reproduced end to end.

**M3 — Learning subsystem (Phase 1, can run parallel to M2)**
Full pipeline from §4.3, at minimum reproducing the MikroTik 9-question,
71%-coverage example. Ratification and provisional-exclusion-from-reports
enforced. Done when: `V-08.3-002` (polarity gate) and the coverage-curve
metric recording both pass, and a rulepack your synthesis code wrote loads
successfully in Track A's real loader.

**M4 — Remediation, reporting, knowledge import (Phase 1 → 2)**
Remediation planner with lockout detection and dry run; per-device PDF (all
8 sections) and estate report; STIG/NIST import; rulepack export/import.
Done when: the CORE-SW-01 report example in
[10-reporting.md §2](../docs/10-reporting.md) is reproduced byte-for-byte
across two separate generation runs (V-10.1-001, your half of it).

**M5 — Integration, audit log, release gates (Phase 2)**
Swap fixture engine calls for real `nsca_engine.api` calls. Hash-chained
audit log complete and verified (`/admin/audit-log/verify`). Own and run the
CI pipeline from [00-master-plan.md §7](00-master-plan.md). Compile the
[TRD-11.3](../trd/TRD-11.3-acceptance-criteria.md) BLOCKING-criteria checklist
and track it to green. Done when: [00-master-plan.md §6](00-master-plan.md)'s
five headline verification criteria all pass in CI.

---

## 6. Testing obligations

You additionally own, beyond your own module tests:

- The **golden-set CI gate** (`gate_determinism_golden_set`) — you author the
  20 golden campaigns and the CI job that runs them twice and diffs report
  hashes.
- **Coordinating TRD-11.1's test strategy** across both backend tracks — this
  doesn't mean writing Track A's tests, it means making sure the shared
  pieces (corpus location, fixture format, CI wiring) are consistent so
  neither track invents a second incompatible test-data format.
- **INTEGRATION** tests across the engine boundary specifically: for every
  contract dataclass in `nsca_engine.api`, a round-trip test that constructs
  one, passes it through your mapper into the DB, reads it back, and asserts
  equality.
- **MANUAL** verification procedures for the two things that cannot be
  automated: the air-gapped install (README walkthrough with network
  disabled), and the two-person ratification UX (someone other than the rule
  author must actually click Ratify).

---

## 7. Open questions to flag back

- Ollama/local-inference deployment: confirm whether the hackathon demo
  environment can run the inference container, or whether the demo relies on
  the heuristic-only degraded mode (INV-08.2-03) — this changes what "done"
  looks like for the candidate-proposal milestone and should be settled
  before M3, not discovered during it.
- Corpus/golden-set data: same open question as Backend Track A's §8 — you
  additionally need the 20 golden campaigns for the determinism gate; agree
  with Track A whether these are a shared artifact both tracks pull from one
  location.
- Whether `assess_device`'s decomposition is granular enough to reuse just
  the evaluation stage for remediation dry-run (§4.4) without re-running
  parse/extract — raise this with Backend Track A as soon as you reach M4; it
  may need a third, narrower engine entry point added to the contract.
