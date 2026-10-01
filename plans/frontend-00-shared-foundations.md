# Frontend Track 0 · Shared Foundations

> Builder: whichever Antigravity (Gemini) machine starts first. This track is
> small and short by design — it exists to unblock Tracks 1–3, not to build
> product screens. **Finish this before the other three tracks build real UI
> against it**, and freeze it afterward (§5). Read
> [00-master-plan.md](00-master-plan.md) first.

---

## 1. Why this exists

Three independent machines are about to build screens that all need to look
like one product, talk to one API, and treat verdicts/severity identically —
[12-ux-specification.md §1](../docs/12-ux-specification.md)'s design
principles (especially U3: "UNKNOWN is a distinct visual state, never styled
like a pass," and U7: "severity is never colour alone") are product
guarantees, not per-screen decisions. If each track invents its own badge
component, the demo will visibly disagree with itself on the one distinction
the entire product exists to get right. This track builds that vocabulary
once.

It also does the mechanical work that would otherwise be duplicated three
times: talking to the API, generating types from it, and standing up the
app shell all three tracks' routes plug into.

---

## 2. What you must produce

### 2.1 Project setup

React 19 + TypeScript + Vite + Tailwind CSS + shadcn/ui (Radix primitives —
chosen specifically for the accessible keyboard/focus behaviour
NFR-USE-007/008 require, and because shadcn copies components into the
source tree rather than adding a themed runtime dependency —
[TECH-STACK.md §12](../TECH-STACK.md)). TanStack Query for server state.
TanStack Table (virtualised) is also a shared dependency, even though only
Tracks 1 and 2 use it directly for large tables — install and configure it
here so both tracks start from one virtualisation setup, not two.

```
frontend/
├── package.json
├── vite.config.ts
├── tailwind.config.ts        design tokens — §2.3
└── src/
    ├── app/
    │   ├── router.tsx          top-level routes, lazy-loaded per track
    │   ├── shell.tsx            nav shell — §2.4
    │   └── auth-guard.tsx       RBAC route guard — §2.5
    ├── shared/
    │   ├── api/
    │   │   ├── client.ts        fetch wrapper, auth header, error shape
    │   │   ├── types.gen.ts     generated from OpenAPI — §2.2, regenerate, don't hand-edit
    │   │   └── hooks/            one TanStack Query hook module per API-spec section
    │   ├── components/
    │   │   ├── VerdictBadge.tsx     §2.3
    │   │   ├── SeverityBadge.tsx     §2.3
    │   │   ├── CoverageBar.tsx        §2.3
    │   │   ├── TrustTierBadge.tsx     §2.3
    │   │   ├── EvidenceExcerpt.tsx     §2.6 — the config-line viewer
    │   │   ├── ProgressPanel.tsx       U5 — long-running operation progress
    │   │   ├── DataTable.tsx            TanStack Table + virtualisation wrapper
    │   │   └── FileDropzone.tsx
    │   ├── theme/
    │   │   └── tokens.ts         colour/shape tokens — §2.3
    │   └── types/
    │       └── domain.ts          hand-written types not in the OpenAPI schema
    │                              (UI-only state, e.g. wizard step enums)
    └── (campaigns/ findings/ training/ etc. — Tracks 1–3, not yours)
```

### 2.2 API client and generated types

Track B publishes a live OpenAPI schema at `/api/v1/openapi.json` from Phase
0 (see [backend-02 §5, M0](backend-02-platform-learning-reporting-api.md)),
initially backed by stub responses matching
[15-api-specification.md](../docs/15-api-specification.md)'s own examples.
Generate `shared/api/types.gen.ts` from it (`openapi-typescript` or
equivalent) and commit a script (`npm run gen:api`) that regenerates it — run
this script every time Track B's schema changes, and re-run it as one of the
first things in Phase 2 when stub responses become real ones.

Write one TanStack Query hook per resource, matching the API spec's grouping
(`useCampaigns`, `useCampaign(id)`, `useFindings(campaignId, filters)`,
`useTrainingQueue()`, etc.) — Tracks 1–3 should never call `fetch` directly,
only these hooks, so that auth headers, error shapes, and cache invalidation
are consistent everywhere. You don't need to write every hook every other
track will ever need up front — write the ones for Phase 0's stub endpoints,
and let each track add hooks for its own resources under `shared/api/hooks/`
as it needs them (this directory is the one part of `shared/` that stays open
for addition after freeze — see §5).

### 2.3 Design tokens and the verdict/severity visual language

This is the highest-value thing this track produces. Implement
[12-ux-specification.md §10](../docs/12-ux-specification.md) exactly:

```
Verdict treatment (§10.1)
  PASS              filled check, neutral weight
  PASS (PARTIAL)    check + warning overlay — visually distinct from plain PASS
  PASS (vacuous)    hollow check — distinguishable at a glance from filled
  FAIL              solid marker, weight scales with severity
  UNKNOWN           question mark on a distinct background — must be
                     impossible to confuse with PASS at any size, in monochrome
  NOT_APPLICABLE    greyed dash, de-emphasised

Severity (§10.2)     never colour alone — pair every hue with a shape/glyph;
                     must remain legible in monochrome print (reports reuse
                     these tokens — see coordination note below)

Trust tier (§10.3)    findings from non-certified rulepacks carry a persistent
                     marker everywhere they appear, not only in reports
```

Build `VerdictBadge`, `SeverityBadge`, `TrustTierBadge`, and `CoverageBar` as
the literal, only implementation of this language — no track should ever
write its own verdict-to-colour mapping. Run an automated contrast check
(WCAG 2.1 AA, NFR-USE-007) on every token combination as part of this track's
own tests, not left to each consuming screen to verify independently.

**Coordination note:** Backend Track B's report renderer
([backend-02 §4.6](backend-02-platform-learning-reporting-api.md)) needs the
*same* visual language in monochrome print (custom SVG, per
[TECH-STACK.md §12](../TECH-STACK.md), not this React component tree — PDFs
don't render React). You cannot share code across that boundary, but you can
and should share the token *definitions* (which glyph means which severity,
which treatment means which verdict) — export `theme/tokens.ts` in a form
simple enough (a plain JSON/TS object of glyph+colour+label per state) that
Backend Track B's report module can read the same source of truth when
building its SVG legends, rather than a human re-deriving it from a
screenshot. Flag this file's location to Backend Track B once it exists.

### 2.4 App shell and routing

Top nav matching the seven sections from
[12-ux-specification.md §2](../docs/12-ux-specification.md): Campaigns,
Estate, Findings, Training Studio, Knowledge, Reports, Administration. Each
top-level route is lazy-loaded and owned by exactly one track (see the
ownership table in [00-master-plan.md §2](00-master-plan.md)) — your job is
the shell and the route tree's top level, not the pages themselves.

```tsx
// app/router.tsx — illustrative, not prescriptive of the exact router lib
const routes = [
  { path: '/campaigns/*', lazy: () => import('../campaigns/routes') },   // Track 1
  { path: '/estate/*',     lazy: () => import('../estate/routes') },      // Track 1
  { path: '/findings/*',   lazy: () => import('../findings/routes') },    // Track 2
  { path: '/training/*',   lazy: () => import('../training/routes') },    // Track 3
  { path: '/knowledge/*',  lazy: () => import('../knowledge/routes') },   // Track 3
  { path: '/reports/*',    lazy: () => import('../reports/routes') },     // Track 3
  { path: '/admin/*',      lazy: () => import('../admin/routes') },       // Track 3
];
```

Each track exports a `routes.tsx` from its own top-level directory; you wire
it into this table once it exists (a one-line addition — this is deliberately
the only place the three tracks' code is referenced from outside their own
directory).

### 2.5 Auth and RBAC guard

Five roles from FR-ADM-002: Assessor, Lead Assessor, Network Administrator,
Platform Administrator, Read-only. Build a route/component-level guard
(`<RequireRole roles={['LeadAssessor']}>`) that every track uses to gate
destructive actions (U6: "issuing a campaign, ratifying a rule, accepting
risk" are all role-gated per FR-ADM-003/FR-ADM-004 and
[09-findings-lifecycle.md §7](../docs/09-findings-lifecycle.md)). Against
Track B's Phase 0 stub, the dev auth user's role should be switchable via a
UI control (not just a header, so every track's developer can self-test
role-gating without touching backend code).

### 2.6 `EvidenceExcerpt` — the one component that appears everywhere

Per U1 ("evidence is always one click away") this component is used by
Track 1 (device detail), Track 2 (finding detail, dispute), and Track 3
(report viewer, training question flow's "real lines from their own device").
Build it once, here:

- Renders a configuration excerpt with line numbers, one or more highlighted
  lines, and secret masking indicated (never a syntax highlighter — no
  grammar exists for Cisco IOS or RouterOS; this is a plain, precise text
  renderer per [TECH-STACK.md §12](../TECH-STACK.md)).
- Accessible as real text, not an image (§11 of the UX spec).
- Accepts a `counterexample` variant for graph findings (packet + rule chain,
  [12-ux-specification.md §8](../docs/12-ux-specification.md)'s dispute
  screen and the attack-path explorer both need this shape).

---

## 3. Milestones

**M0 — Scaffold and tokens (must complete before Tracks 1–3 start UI work)**
Project builds, routes to a blank shell per section, design tokens and the
four badge/bar components exist with Storybook-style visual checks (or an
equivalent lightweight preview) covering every verdict/severity/trust-tier
combination. Done when: someone unfamiliar with the UX spec can look at the
six verdict states side by side and correctly identify which one is UNKNOWN
without reading a label, in a black-and-white printout.

**M1 — API client + generated types**
Live against Track B's Phase 0 stub OpenAPI schema. Hooks for every Phase 0
stub endpoint. Done when: a throwaway test page can list campaigns, list
findings, and show the training queue using only `shared/api/hooks`.

**M2 — Shell, routing, auth guard**
Nav shell with all seven sections wired to placeholder pages; role-switchable
dev auth; `<RequireRole>` guard with a unit test per role combination. Done
when: Tracks 1–3 can each drop a `routes.tsx` into their directory and see it
appear in the nav with zero changes to shared code.

**M3 — `EvidenceExcerpt` and remaining shared components**
`DataTable` (virtualised), `FileDropzone`, `ProgressPanel`. Done when: all
four are demonstrated against representative fixture data covering the edge
cases each consuming track will hit (a 500-line excerpt, a table with 10,000
rows, an upload of 400 files).

**Freeze point** — once M0–M3 are done, this track's job is finished. If it's
the same machine that finds itself with spare time, it should move on to
being folded into whichever of Tracks 1–3 needs the most help (frontend-03 is
the largest by requirement count, per
[00-master-plan.md §2](00-master-plan.md)) rather than continuing to expand
`shared/`.

---

## 4. Testing obligations

Component tests for every shared component (React Testing Library),
automated contrast checks (`axe` or equivalent) on the token set, and one
integration test per API hook against Track B's stub. This is small,
foundational surface — keep it rigorously tested, since a bug here is a bug
in three tracks' UIs simultaneously.

---

## 5. The freeze rule

After M3, `frontend/src/shared/**` is additive-only:

- Tracks 1–3 may **add** new hooks under `shared/api/hooks/` for their own
  resources.
- Tracks 1–3 may **not** modify `VerdictBadge`, `SeverityBadge`,
  `EvidenceExcerpt`, the token definitions, the router shell, or the auth
  guard without raising it as a written proposal (per
  [00-master-plan.md §3](00-master-plan.md)'s rule) — these are the contract
  every other track's visual correctness depends on.
- If a track genuinely needs a new shared primitive (the `<FindingCard>` /
  `<SystemicFindingBanner>` case from
  [00-master-plan.md §5.5](00-master-plan.md)), it's built by whichever track
  is its natural owner and exported for the other to import — it does not
  need to live under `shared/` to be shared; a component can be imported
  across `frontend/src/findings/` → `frontend/src/estate/` directly.

---

## 6. Open questions to flag back

- Confirm the exact API type-generation tool (`openapi-typescript` vs. an
  alternative) works cleanly against FastAPI's generated schema before
  committing to it in Phase 0 — this blocks every other track if it doesn't.
- The monochrome-print token sharing note in §2.3 depends on Backend Track B
  reading a file from the frontend package, which is an unusual
  cross-language dependency direction — confirm with Backend Track B whether
  they'd rather receive a small JSON export of the token set instead of
  reading TypeScript directly, and adjust the export format accordingly.
