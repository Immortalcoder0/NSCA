# Frontend Track 3 · Training Studio, Knowledge, Reports & Administration

> Builder: Antigravity (Gemini) machine #3. Owns the product's signature
> screen — the Training Studio is demo beat 2
> ([17-traceability-matrix.md §5](../docs/17-traceability-matrix.md)) and the
> screen the problem statement names explicitly. Also owns the largest
> low-interdependency surface (Knowledge, Reports, Admin), which makes this
> track the natural place to absorb spare capacity if the other two frontend
> tracks finish early. Read [00-master-plan.md](00-master-plan.md) and
> [frontend-00-shared-foundations.md](frontend-00-shared-foundations.md)
> first.

---

## 1. Scope

**You own:** Training Studio (queue, question flow, result, ratification),
Knowledge (rulepacks, control packs & frameworks, framework update review,
coverage manifests), Reports (library, viewer), Administration (users &
roles, collection credentials, system status & knowledge freshness). Routes
under `frontend/src/training/`, `frontend/src/knowledge/`,
`frontend/src/reports/`, `frontend/src/admin/`.

**You depend on nothing from Tracks 1–2** — this is the most self-contained
of the three frontend tracks. It has no embedded cross-track components to
build or consume, which is deliberate: it is the safest place for the
largest single requirement area (28 FR-LRN requirements — more than any other
functional area in [03-functional-requirements.md](../docs/03-functional-requirements.md))
to live without becoming an integration bottleneck for the other two tracks.

### 1.1 Source material

- [12-ux-specification.md §6](../docs/12-ux-specification.md) in full — the
  Training Studio's four sub-screens (queue, question flow, result,
  ratification), the mock you are implementing closely.
- [08-learning-system.md](../docs/08-learning-system.md) in full — the
  interaction design principle (§6.1: "confirm, do not author") that every
  decision on this screen should be checked against.
- [02-personas-and-journeys.md §6–7](../docs/02-personas-and-journeys.md) —
  Rahul's teaching journey and Vikram's framework-ratification journey, the
  exact numbers and copy your states should resemble.
- [15-api-specification.md §6–9](../docs/15-api-specification.md) — training,
  knowledge, reports, and admin endpoints with full example payloads.
- [10-reporting.md §2](../docs/10-reporting.md) — the report viewer's content
  model (you are rendering the same document model Backend Track B's PDF
  renderer produces, in HTML — not regenerating it independently).

---

## 2. Screen-by-screen notes

### 2.1 Training Studio — queue

Reproduce [12-ux-specification.md §6.1](../docs/12-ux-specification.md):
one card per platform-with-gaps, showing device count, current coverage,
grammar inference coverage where relevant, question count and time
estimate, and a `[Begin]` action. Three visually distinct card states —
`NOT TAUGHT`, `PARTIAL`, `UNIDENTIFIED` — the last of which has no `[Begin]`
action at all, only `[Assisted grammar authoring]`, since below-threshold
grammar inference must not offer a path that pretends teaching is possible
yet ([08-learning-system.md §3.3](../docs/08-learning-system.md)).

### 2.2 Training Studio — question flow

This is the screen the product's own materials describe as the centrepiece
of the demo. Build it to match
[12-ux-specification.md §6.2](../docs/12-ux-specification.md) precisely, not
approximately:

- **One question at a time**, progress dots + position (`Question 1 of 9`)
  + time estimate, sourced from `GET /training/queue/{platform}/next`.
- **Real lines from the operator's own device**, with line numbers —
  render through `EvidenceExcerpt` from `shared/` for consistency with every
  other evidence view in the product, even though this is "proposed"
  evidence rather than a finding's evidence.
- **"Our reading"** block: proposed mappings rendered as plain-language
  statements (`telnet → Telnet service ENABLED`), never as a regular
  expression or any code-shaped artifact — NFR-USE-002 is absolute here, and
  it's worth a dedicated visual review pass specifically checking that
  nothing on this screen looks like syntax a non-programmer would find
  intimidating.
- **The polarity check is its own visually separate block**, with its own
  warning treatment, whenever `proposal.polarity.requires_explicit_confirmation`
  is true. The `[Confirm]` action must be disabled (or must route to a
  second, mandatory polarity-specific confirmation step) until
  `polarity_confirmed` is explicitly set — this mirrors the API's own 422
  validation ([TECH-STACK.md §4](../TECH-STACK.md)'s `TrainingAnswer` model)
  and should never let a user submit a confirm response that the API would
  reject; treat this as a client-side rule with equal severity to the
  server-side one, not a lesser copy of it.
- **Impact stated before answering** ("Confirming resolves 8 controls") —
  render from `impact.controls_unlocked` in the API response, not computed
  client-side.
- Five response options exactly as specified: Confirm, Polarity inverted,
  Edit mapping, Not compliance-relevant, Skip — "not compliance-relevant"
  is a first-class button, not a secondary/ghost action buried under the
  others; it is explicitly called out as useful information in its own
  right, not a fallback.

### 2.3 Training Studio — result and ratification

Result screen: before/after coverage with the elapsed-time figure
prominently displayed (`5 confirmations · 8 min 12 s`) — this is literally
the product's central claim rendered as UI, per
[12-ux-specification.md §6.3](../docs/12-ux-specification.md); don't let it
be a small footnote below the numbers.

Ratification screen ([12-ux-specification.md §6.4](../docs/12-ux-specification.md)):
render the full validation-gate checklist (self-match, cross-platform,
conflicts, regression, metamorphic, coverage effect) as an explicit
pass/fail list, not a summary sentence — an assessor reviewing this before
ratifying needs to see each gate individually. `[Ratify]` must be role-gated
via `<RequireRole>` and — separately — must be disabled if the current user
is the rule's author, matching the two-person rule
(`ratified_by ≠ taught_by`, DM-6) at the UI layer as well as relying on the
API's own rejection; show *why* it's disabled ("you taught this rule; a
different user must ratify it"), don't just grey it out silently.

### 2.4 Knowledge — rulepacks, controls, frameworks

Rulepack list/detail: version, trust tier (`TrustTierBadge` from `shared/`),
coverage (facts producible, corpus line coverage, extractor/test counts —
reproduce [07-vendor-rulepacks.md §10](../docs/07-vendor-rulepacks.md)'s
coverage report shape), authorship. Import/export actions for signed
bundles.

Control packs & frameworks: browsable list with framework/version selection
(feeds campaign creation on Track 1's side — same selector component if
practical, coordinate the shape early rather than duplicating a
framework-picker independently).

**Automation coverage manifest** — reproduce
[15-api-specification.md §7](../docs/15-api-specification.md)'s example
exactly: total/automated/manual-only/data-unavailable/not-implemented counts,
with the manual-only items list and reasons visible, not collapsed behind a
tooltip. This is explicitly "the first thing a serious auditor will ask for"
per [06-controls-and-frameworks.md §6](../docs/06-controls-and-frameworks.md)
— treat it as a primary screen, not a details tab.

**Framework update review**: reproduce Vikram's journey
([02-personas-and-journeys.md §7](../docs/02-personas-and-journeys.md)) —
current vs. available version, content changes (added/modified/withdrawn),
estate-impact dry run (new findings, severity changes, findings that would
close), with `[Review changes]` / `[Ratify]` / `[Defer]` actions. This is a
second instance of the same "preview before you commit to a knowledge-base
change" pattern as rulepack ratification — consider factoring a shared
`<ImpactPreview>` component within this track's own code (not `shared/`,
since only this track uses it) rather than building two independent
implementations.

### 2.5 Reports — library and viewer

Library: filterable list of issued reports (per device / estate / by
campaign), download actions per format (`pdf`, `docx`, `json`, `csv`,
`oscal` — per [15-api-specification.md §8](../docs/15-api-specification.md)).

Viewer: renders the same eight-section document model Backend Track B's PDF
generator produces ([10-reporting.md §2](../docs/10-reporting.md)) as an
HTML view — cover/identification, executive summary, findings, emergent
findings, remediation playbook, **unassessed** (§2.6 below), assessor notes,
appendix. Use `EvidenceExcerpt` for every finding's evidence, exactly as
Track 2 does on finding detail — these are the same underlying evidence
objects rendered in two contexts, and they should look identical modulo
layout, not like two different products.

**Section 6, Unassessed, is not optional and not secondary.** Render it with
the same visual weight as the findings section — it is explicitly the
section identified as making "the rest of the report credible" and the one
"no competing product contains"
([10-reporting.md §2, Section 6](../docs/10-reporting.md)). Include the
closing coverage statement verbatim: *"This assessment determined N% of
applicable controls. It is not a statement that the remaining % are
compliant."*

A `[Verify]` action (`POST /reports/{id}/verify`) that re-executes and
compares hashes, rendering the three possible outcomes (MATCH / MISMATCH
with differing knowledge base / MISMATCH with identical knowledge base) —
the last of which is a **defect**, and should render as a loud, differently
styled alert, not the same visual treatment as an expected content-drift
mismatch.

### 2.6 Administration

Users & roles: list, role assignment (five roles from FR-ADM-002), backed by
`/admin/users` and `/admin/roles`. Collection credentials: create/list only
— **the UI must not have any code path that displays previously-entered
credential material**, matching NFR-SEC-003/`FR-ADM-006` at the client layer
as well as relying on the API never returning it; this is a case where
double-enforcing a security property client-side is worth the redundancy.

System status & knowledge freshness (`GET /knowledge/freshness`,
`/admin/health`, `/admin/status`): current vs. available content versions,
offline vulnerability-data age (render the "43 days old" style freshness
statement per [11-audit-integrity.md §13.3](../docs/11-audit-integrity.md) —
don't just show a date, show the staleness in the same words the report
itself uses, since a user should recognise the same fact whether they see it
on this screen or in a report).

Hash-chain audit log viewer (`GET /admin/audit-log`,
`/admin/audit-log/verify`): filterable log view plus a verify action showing
`entries_checked` / `chain_intact` / `first_break`.

---

## 3. Milestones

**M1 — Training Studio queue + question flow (Phase 1 start, highest priority on this track)**
Full question-flow interaction against mock data, including the polarity
block and all five response options. This is the demo's second beat — treat
it as this track's critical path, ahead of Knowledge/Reports/Admin.

**M2 — Training Studio result + ratification**
Before/after coverage display with elapsed time; full validation-gate
checklist; two-person-rule UI enforcement.

**M3 — Knowledge**
Rulepack list/detail with coverage reporting; automation coverage manifest;
framework update review with estate-impact preview.

**M4 — Reports**
Library + viewer reproducing all eight document sections, with Unassessed
given full visual weight; verify action with the three-outcome rendering.

**M5 — Administration**
Users/roles, credentials (write-only), system status/freshness, audit log
viewer with chain verification.

**M6 — Integration (Phase 2)**
Real API data end to end; rehearse the full teaching demo (0% → ≥70%
coverage, timed) against a real untaught-platform corpus entry, offline.

---

## 4. Testing and accessibility obligations

Full keyboard navigation through the entire question-flow sequence
(NFR-USE-008 names this explicitly) — this is worth a dedicated
keyboard-only walkthrough test, not just a general a11y linter pass, since
it's the one interaction flow the spec calls out by name. Verify the
polarity-block client-side gate actually blocks submission (component test
with `requires_explicit_confirmation: true` and no `polarity_confirmed`
value). Verify the credential-material-never-displayed property with a test
that asserts no component in the credentials screens ever renders a field
matching the encrypted-material shape, even if the (stub) API accidentally
returns one — treat this as an assertion about your own rendering code, not
just trust in the backend's contract.

---

## 5. Open questions to flag back

- Confirm whether the Training Studio demo will run against Backend Track
  B's real Ollama-backed candidate proposal or the heuristic-only degraded
  mode (same open question Backend Track B raised in its own plan,
  [backend-02 §7](backend-02-platform-learning-reporting-api.md)) — the
  question-flow UI should handle both identically (the API response shape
  doesn't change, only proposal quality/confidence), but the rehearsed demo
  script (M6) needs to know which one it's rehearsing against.
- Framework-selector component: check with Track 1 (§5 of
  [frontend-01](frontend-01-ingestion-campaigns-estate.md)) whether campaign
  creation's framework picker and this track's framework browsing list can
  share one component — likely yes, low risk, but worth a short sync rather
  than two independent implementations of the same CIS/NIST/STIG/ISO
  version-selection UI.
