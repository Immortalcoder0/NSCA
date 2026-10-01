# Frontend Track 2 · Findings, Risk & Remediation

> Builder: Antigravity (Gemini) machine #2. The most visually complex track —
> custom SVG graph layout for attack paths is explicitly called out as a
> deliberate non-standard choice
> ([TECH-STACK.md §12](../TECH-STACK.md): dagre DAG layout, not
> force-directed, because attack paths must render deterministically and
> readably). Read [00-master-plan.md](00-master-plan.md) and
> [frontend-00-shared-foundations.md](frontend-00-shared-foundations.md)
> first.

---

## 1. Scope

**You own:** the finding workbench, finding detail, dispute + compensating
control verification, the attack path explorer, remediation playbook and
dry-run views. Routes under `frontend/src/findings/`,
`frontend/src/attack-paths/`, `frontend/src/remediation/`.

**You publish for Track 1 to consume:** `<FindingCard>` (a compact finding
summary/row usable both in the workbench and embedded in device detail) and
`<SystemicFindingBanner>` (per
[00-master-plan.md §5.5](00-master-plan.md)). Build these early enough in
Phase 1 that Track 1 isn't stuck on placeholders for long — treat publishing
them as an implicit milestone even though the workbench itself doesn't
strictly need `<FindingCard>` to be a separate exported component until you
factor it out.

### 1.1 Source material

- [12-ux-specification.md §5, §7–9](../docs/12-ux-specification.md) — device
  detail's finding block (shared shape with your workbench), the workbench,
  dispute, and attack path explorer mocks.
- [09-findings-lifecycle.md](../docs/09-findings-lifecycle.md) in full — the
  state machine, dispute types, compensating-control verification outcomes,
  systemic finding detection, and the prioritisation model your UI surfaces.
- [15-api-specification.md §5](../docs/15-api-specification.md) — findings
  endpoints and example payloads, including the REFUTED dispute example your
  dispute screen must reproduce.
- [10-reporting.md §5, §2 Section 5](../docs/10-reporting.md) — the
  remediation playbook content shape (also used by Backend Track B's PDF —
  your on-screen version and the PDF should agree on structure even though
  they're rendered by different code).

---

## 2. Screen-by-screen notes

### 2.1 Finding workbench

Default grouping is **by control**, not by device — this is stated
explicitly in the UX spec as deliberate ("that is how an assessor thinks and
how systemic patterns become visible") and is the opposite of what a naive
implementation would default to. Group-by toggle: control / device / attack
path / systemic. Bulk selection with bulk actions (assign, confirm, export)
— use `DataTable`'s virtualisation from `shared/`, since an assessor works
with hundreds of findings at once (U8, A7 in the API principles).

Systemic groups render your `<SystemicFindingBanner>` inline at the top of
the group (`ⓘ SYSTEMIC — build-template defect`, with "Adjudicate all 31" /
"Assign all" bulk actions scoped to the cluster) — implement bulk-adjudicate
as N individual `POST /findings/{id}/adjudicate` calls behind one optimistic
UI action (or a single `POST /findings/bulk` call per
[15-api-specification.md §5](../docs/15-api-specification.md) if the payload
supports cluster-scoped bulk transitions — check the bulk endpoint's schema
once Track B publishes it and prefer it over N calls if it exists).

### 2.2 Finding detail

This is where `EvidenceExcerpt` (from `shared/`) does its primary job:
evidence expanded by default on load, never requiring a click to reveal — U1
again. For graph-derived findings, `EvidenceExcerpt`'s counterexample variant
renders the packet + rule chain instead of highlighted lines
([09-findings-lifecycle.md §3.2](../docs/09-findings-lifecycle.md)'s example)
— this is the same rendering need as the dispute screen's REFUTED case and
the attack path explorer's per-link evidence, so factor the
packet/rule-chain renderer as a sub-component of `EvidenceExcerpt` usable
independently, not three separate implementations.

Actions: Confirm, Dispute, Accept risk (role-gated to Lead Assessor via
`<RequireRole>` from `shared/`, FR-ADM-003-equivalent for risk acceptance),
Assign. Risk acceptance form must make `expires_at` a required field in the
UI, not just rely on the API's 422 — show the validation before submission,
matching the product's stated position that "omitting `expires_at` is how
findings disappear" ([15-api-specification.md §5](../docs/15-api-specification.md)).

### 2.3 Dispute and compensating-control verification

Reproduce [12-ux-specification.md §8](../docs/12-ux-specification.md)
closely: claim text, then a **verification** block with three possible
outcomes — REFUTED (counterexample + rule chain + assumptions +
confidence), CONFIRMED (recommend risk acceptance with a pre-filled expiry
suggestion), UNVERIFIABLE (reason, manual verification required). These are
three visually distinct states, not a boolean — do not collapse UNVERIFIABLE
into either of the other two. The assumptions line ("Based on 389 of 412
devices; 23 uncollected") must always render when present — it's what keeps
a REFUTED verdict honest about its own scope.

Adjudication radio group (uphold / reject / accept as risk) plus a required
rationale field, submitted via `POST /findings/{id}/adjudicate`.

### 2.4 Attack path explorer

The one screen on this track requiring genuine graph-layout work. Use
`dagre` for a layered DAG layout (top-to-bottom or left-to-right chain, per
the mock) plus custom SVG rendering — not a force-directed layout library,
per the tech stack's explicit rejection (non-deterministic, unreadable for
linear chains). Each link in the chain renders its contributing finding
(severity-badged, using `SeverityBadge` from `shared/`) and links back to
finding detail. The "breaking any single link breaks the chain" summary plus
"lowest cost: remediate this one, N findings become unreachable" callout is
the payoff element — make it visually the first thing read, per U4 ("lead
with action").

For the estate-level rollup (multiple attack paths, per
[12-ux-specification.md §4](../docs/12-ux-specification.md)'s "3 attack
paths reach the core management plane · Breaking 6 findings eliminates all
3" banner) — this is `<SystemicFindingBanner>`'s sibling summary component,
build it alongside.

### 2.5 Remediation playbook and dry run

Ordered step list with impact classification (`safe` /
`service_affecting` / `lockout_risk`) rendered with distinct visual
treatment per class — a lockout-risk step must be unmistakable, matching the
product's stated goal that "no audit report has ever warned a network
engineer that a recommended fix would lock them out"
([02-personas-and-journeys.md §6.3](../docs/02-personas-and-journeys.md)).
Each step shows its rollback command and any `depends_on_step` relationship
(render as "must precede/follow step N," not just a numbered list that
implies but doesn't state ordering rationale).

Dry-run section: before/after compliance and coverage, resolved findings
count, and — critically — any **newly failing** control, rendered as a
warning block, not folded into the resolved-findings success message. This
is the single UI element the product's own materials identify as "the
feature most likely to convert a sceptic to an advocate" — do not let it be
visually subordinate to the headline compliance-improvement number.

---

## 3. Milestones

**M1 — Finding workbench (Phase 1 start)**
Grouped/filtered/virtualised list against mock data, bulk selection and bulk
actions, `<FindingCard>` factored out and exported for Track 1.

**M2 — Finding detail + dispute**
Full evidence rendering (including counterexample variant), all finding
actions, the three-outcome dispute/verification screen reproducing the
REFUTED example exactly.

**M3 — Attack path explorer**
dagre-based layered layout, per-link evidence, chain summary and lowest-cost
callout; `<SystemicFindingBanner>` published for Track 1.

**M4 — Remediation playbook + dry run**
Ordered, impact-classified steps with rollback and dependency rendering;
dry-run before/after with newly-failing warning treatment.

**M5 — Integration (Phase 2)**
Real API data end to end; verify the attack-path layout renders correctly
against a real multi-device estate graph, not just the fixture chain.

---

## 4. Testing and accessibility obligations

Full keyboard navigation through bulk selection and the dispute
adjudication form (NFR-USE-008). Verify `VerdictBadge`/`SeverityBadge` are
used consistently (no ad hoc colour usage introduced on this track's
screens — an `axe` pass plus a manual monochrome-printout check on finding
detail and the workbench, echoing the report's own monochrome requirement).
Component test for the dagre layout specifically: given a fixed chain input,
assert deterministic node positions (a flaky graph layout undermines the
same determinism story the backend is built to prove).

---

## 5. Open questions to flag back

- Confirm with Backend Track B whether `POST /findings/bulk` supports
  cluster-scoped systemic adjudication in one call, or whether the
  workbench's "adjudicate all 31" must be implemented as N sequential calls
  client-side — affects both your implementation and the optimistic-UI
  design for that action.
- `<FindingCard>` / `<SystemicFindingBanner>` prop contracts should be
  drafted and shared with Track 1 as early as possible in Phase 1 — don't
  wait until M1/M3 are "done" to write the interface down; a rough draft
  early prevents Track 1 from building a placeholder shape that has to be
  restructured later.
