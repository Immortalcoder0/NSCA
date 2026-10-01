# Frontend Track 1 · Ingestion, Campaigns & Estate

> Builder: Antigravity (Gemini) machine #1. This is the product's front door
> — the ingestion dashboard is demo beat 1
> ([17-traceability-matrix.md §5](../docs/17-traceability-matrix.md)). Read
> [00-master-plan.md](00-master-plan.md) and
> [frontend-00-shared-foundations.md](frontend-00-shared-foundations.md)
> first; build against `shared/` once its M0–M3 are done, don't modify it.

---

## 1. Scope

**You own:** Campaign list/detail/comparison, the ingestion dashboard
(upload, bulk, collect), the estate device grid, device detail, collection
completeness. Routes live under `frontend/src/campaigns/`,
`frontend/src/ingestion/`, `frontend/src/estate/`.

**You embed but do not own:** finding summaries and the systemic-finding
banner on device detail / estate view — these are Track 2's components
(`<FindingCard>`, `<SystemicFindingBanner>`), per
[00-master-plan.md §5.5](00-master-plan.md). Build a minimal inline
placeholder first so your screens are demoable standalone; swap to Track 2's
real component once it's published.

### 1.1 Source material

- [12-ux-specification.md §3–5](../docs/12-ux-specification.md) — the three
  screen mocks you are implementing, with design notes.
- [02-personas-and-journeys.md §5, stages 1–2](../docs/02-personas-and-journeys.md) —
  Priya's scope/collect journey, the exact copy and numbers your empty/error
  states should resemble.
- [15-api-specification.md §2–3](../docs/15-api-specification.md) — campaigns
  and ingestion endpoints, with full example payloads.
- [FR-CMP-*, FR-ING-*, FR-UIX-001/002/003](../docs/03-functional-requirements.md) —
  the requirement IDs your acceptance tests should cite.

---

## 2. Screen-by-screen notes

### 2.1 Campaign list / detail / comparison

State machine to render, not just a status string:
`Draft → Collecting → Assessing → Review → Issued → Closed`
(FR-CMP-005). Once `Issued`, the UI must make immutability visible, not just
enforced server-side — grey out or hide any action that would attempt to
modify results, per the state, rather than showing them and relying on a 409
response to explain why they failed.

Campaign creation form maps directly to
[15-api-specification.md §2](../docs/15-api-specification.md)'s create
payload — scope as filter expression / explicit list / inventory import,
framework + version selection (multi-select, since FR-CTL-010 requires
simultaneous multi-framework evaluation), owner, window. Scope resolution
(`POST /campaigns/{id}/scope/resolve`) should run and show the resolved
device count before the campaign moves past `Draft` — Priya's journey opens
with "412 devices resolved from asset inventory," not a blind count.

Comparison view renders the delta-decomposition response verbatim
([15-api-specification.md §2](../docs/15-api-specification.md)'s example):
separate visual treatment per `cause` (`verified_remediation`,
`framework_version_change`, `scope_change`, `configuration_regression`) — do
not collapse this into a single net percentage, since the entire point (P8 in
[02-personas-and-journeys.md §8](../docs/02-personas-and-journeys.md)) is that
"you got worse" and "the bar moved" must be visually separable at a glance.

### 2.2 Ingestion dashboard

Build [12-ux-specification.md §3](../docs/12-ux-specification.md)'s mock
close to literally: dropzone (files, archives, `show tech` bundles — accept
attribute should reflect FR-ING-002/007), a **Collect from devices** action
alongside upload (FR-ING-008, opens a target/credential picker calling
`POST /campaigns/{id}/collect` with `mode: "read_only"` hardcoded client-side
— there is no UI path to express anything else, matching the API's own
`Literal['read_only']` type), and a live results list.

**Four outcome states per artifact, never a binary success/failure** — this
is U-principle territory, not a nice-to-have: `parsed` /
`parsed_with_caveat` / `platform_not_taught` / `unidentified`, exactly per
[15-api-specification.md §3](../docs/15-api-specification.md)'s example
response. `platform_not_taught` renders as an **invitation** with a direct
link into the Training Studio (`/training/queue/{platform}`, Track 3's
route) carrying the prepared question count and estimate — not as an error
state. Multi-artifact devices must visibly show which artifacts correlated
into one device record (the UX mock's "3 artifacts · running-config ·
version · inventory" line) — this is the UI proof that serial numbers came
from `show inventory`, which is otherwise invisible and easy to disbelieve.

Progress uses `ProgressPanel` from `shared/` per U5 — show what remains, not
just a percentage (poll `GET /jobs/{id}`).

Collection completeness (`GET /campaigns/{id}/completeness`) is a first-class
block on this screen, not a separate report — reproduce the
"389 of 412 (94.4%) · 23 missing" treatment with owners per missing device
(FR-ING-016), since an audit that silently covers 94% and presents as
complete is itself the failure mode this screen exists to prevent
(§2 stage 2 of the personas doc).

### 2.3 Estate view

`DataTable` (from `shared/`) with **coverage as a first-class column**,
never subordinate to compliance — the UX spec is explicit that a device at
100% compliance / 40% coverage must not visually outrank one at 85%/95%.
Default sort is by critical findings weighted by exposure, not by compliance
percentage — implement this as the actual default `sort` param sent to
`GET /campaigns/{id}/findings`-adjacent estate query, not just a client-side
reorder that resets on refresh.

Row annotations (`⚠ terse`, `ⓘ local RP`, `✗ missing`) come from
`export_mode`, `rulepack_trust_tier` (use `TrustTierBadge` from `shared/`),
and collection status fields already on the device/artifact response —
don't invent new iconography beyond what
[12-ux-specification.md §4](../docs/12-ux-specification.md) specifies.

Estate-level banners — "3 attack paths reach the core management plane" and
the systemic-finding callout — are Track 2's `<SystemicFindingBanner>` /
attack-path summary component (§1's embedding note). Placeholder first,
real component once available.

### 2.4 Device detail

Header block matches
[12-ux-specification.md §5](../docs/12-ux-specification.md): device identity,
rulepack + trust tier, compliance/coverage/meaningful-ratio scores. The
"FIX THESE FIRST" block is attack-path-ranked remediation summary — this is
Track 2/Backend-B-sourced data (`GET /findings/{id}/remediation` +
attack-path contribution), rendered here as a summary strip with a link into
the full playbook (Track 2's route). Findings/Passing/Unknown/N/A tab counts
and the finding list itself use Track 2's `<FindingCard>` — see §1.

The "UNAUDITED CAPABILITY" callout (unaudited surface, scope contamination)
is device-scoped data your own route can fetch directly
(`unaudited_capabilities` field on the assessment summary,
[15-api-specification.md §4](../docs/15-api-specification.md)'s example) — no
need to route this through Track 2.

---

## 3. Milestones

**M1 — Campaign CRUD + list/detail against mock data (Phase 1 start)**
Full campaign lifecycle UI against Track B's Phase 0 stub responses.
Comparison view renders the example delta payload correctly, including the
per-cause visual separation.

**M2 — Ingestion dashboard**
All four outcome states rendered distinctly; collection-completeness block;
drag-and-drop bulk upload with per-file progress; **Collect from devices**
flow with the hardcoded `read_only` mode.

**M3 — Estate grid + device detail**
Coverage-first column ordering and default sort; row annotations; device
detail header and score block; placeholder `<FindingCard>`/
`<SystemicFindingBanner>` wired to real API shape so swapping to Track 2's
real components later is a one-line import change, not a rewrite.

**M4 — Integration (Phase 2)**
Swap placeholders for Track 2's real components; swap mock API responses for
Track B's real ones; verify against a real multi-platform bulk upload
end-to-end, offline.

---

## 4. Testing and accessibility obligations

Component tests for the four-outcome-state ingestion result renderer
specifically (this is the single highest-value UI correctness point on this
track — a competing tool's failure mode is exactly "silently binary"), and
for the coverage-first sort default. Full keyboard navigation through the
upload flow and the campaign creation form (NFR-USE-008). Verify the
"platform not taught" invitation link actually deep-links into Track 3's
training queue with the right platform pre-selected once that route exists.

---

## 5. Open questions to flag back

- Exact shape of the scope-filter-expression builder (free text like
  `exposure == 'internet_facing' or (role == 'access' and sample(0.10))`
  per the API example, vs. a structured builder UI) — the API accepts a raw
  expression string; decide whether Phase 1 ships a textarea with syntax
  help or a full visual builder, and record the decision here so Track 3
  (which has a related expression-adjacent need in framework/coverage views)
  can reuse the same input pattern if applicable.
- Confirm with Track 2 the exact prop contract for `<FindingCard>` /
  `<SystemicFindingBanner>` as soon as Track 2 has a draft, so your
  placeholder's shape doesn't need a structural rewrite at integration time.
