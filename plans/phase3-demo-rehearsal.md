# Phase 3 — Demo Rehearsal (SIH26155)

> Rehearsal against the **real** running platform (`http://localhost:8000`, FastAPI,
> real Postgres via docker `nsca-test-db` on `15432`). Every result below was produced
> by an actual HTTP call in this session — no result is inferred from reading code
> alone unless explicitly labelled "verified by code audit." Where something failed,
> it is reported as a failure, not smoothed over.
>
> API build under test: `openapi.json` self-describes as *"Backend Track B REST API
> (Phase 0 stub, see nsca/docs/15-api-specification.md)"*, version `0.1.0`. That
> "Phase 0 stub" label matters — several endpoints below are confirmed non-functional
> placeholders, not integration bugs in otherwise-real logic.
>
> **Mid-session incident.** Partway through the rehearsal (between Beat 1/2's first
> pass and the redo below), the live Postgres data was silently wiped: campaign IDs
> reset from `CMP-2026Q3-004` back to `CMP-2026Q3-001` with entirely different seed
> content, all artifacts/training rules/ratifications created so far vanished, and a
> moment later the DB was empty even of that new seed content. The `nsca-test-db`
> docker container itself never restarted (continuous uptime throughout). This means
> some other process touched the same `DATABASE_URL` mid-session (e.g. a test suite
> run against the shared dev DB, or a migration). **This is itself a demo-readiness
> risk**: state assembled during a rehearsal (uploaded artifacts, taught platforms,
> issued reports) is not safe from concurrent resets on this shared dev database. All
> three beats below were re-run to completion *after* this incident, against fresh
> IDs, so every number quoted is from the final, currently-live state — except where
> explicitly marked as "first pass, pre-reset."

---

## Beat 1 — Bulk ingestion, offline, multiple platforms including cloud JSON

**Setup.** Built a 48-file bulk batch from real fixtures:
- `nsca/engine/nsca_engine/tests/fixtures/branch_routers.py`'s `branch_router_fleet()`
  generator → 40 Cisco IOS branch-router configs (`BR-RTR-001..040.cfg`)
- `ap003/core_sw_01.cfg`, `ap003/edge_fw_01.cfg` (Cisco IOS)
- `juniper_brace.conf`, `juniper_set.conf` (Juniper, two dialects)
- `fortios.conf` (FortiOS)
- `panos.xml` (PAN-OS)
- `routeros.rsc` (MikroTik RouterOS)
- `cloud_fw.json` (cloud policy JSON — the explicit "twice-named" requirement)

**Run.** Fresh campaign `CMP-2026Q3-001` (`Phase3 Demo Rehearsal - Bulk Ingestion
v2`), single `POST /campaigns/{id}/artifacts` multipart call with all 48 files:

```
curl $(for f in *; do printf -- "-F files=@%s " "$f"; done) \
  http://localhost:8000/api/v1/campaigns/CMP-2026Q3-001/artifacts
```

**Result:** `HTTP 201`, wall-clock **0.59 s** (first pass, pre-reset, on a
differently-numbered campaign: 1.08 s for the same 48 files — both well under
"seconds" for the whole batch).

```json
{"accepted": 48, "job_id": "job-..."}
```

Classification breakdown:

| platform | count | status |
|---|---|---|
| cisco_ios | 42 | parsed_with_caveat (terse export) |
| cloud_generic_fw | 1 | platform_not_taught |
| fortios | 1 | platform_not_taught |
| juniper_junos_curly | 1 | platform_not_taught |
| juniper_junos_set | 1 | platform_not_taught |
| routeros | 1 | platform_not_taught |
| panos | 1 | platform_not_taught |

`cloud_fw.json` was correctly fingerprinted as `cloud_generic_fw` (not dumped into
`unidentified`) — the cloud-JSON recognition path works structurally.

**Offline claim — verified by code audit, not a literal network-disconnect test.**
Grepped both `nsca/engine/nsca_engine` and `nsca/platform/nsca_platform` for
`requests.`/`httpx.`/`urllib.request`/`aiohttp` outbound calls. The engine has zero
hits. The platform has exactly one file with network calls:
`nsca_platform/learning/candidate_proposal.py`, which only ever calls
`http://localhost:11434` (a local Ollama instance) and only from the **training**
candidate-proposal path (`services/training.py`), never from ingestion or
assessment. I did not physically disconnect the network adapter (would also have
cut my own access to the sandbox), so this is code-audit-verified, not
empirically disconnect-tested.

**Real defects found while running this beat (not previously known):**

1. **`grammar_coverage` is wrong for MikroTik, always reporting `0.0`.**
   `nsca_platform/services/ingestion.py`'s `_grammar_coverage()` looks up
   `_KNOWN_LINE_PREFIXES` by platform id, but that dict is keyed
   `"mikrotik_routeros"` while the real engine fingerprinter (used for
   `routeros.rsc`) returns the canonical id `"routeros"` — the same id
   `nsca/knowledge/rulepacks/routeros.yaml` and the training queue use. The key
   mismatch means the lookup always misses and returns `0.0`, even though the
   fixture's lines actually match the known RouteOS grammar almost completely
   (per `08-learning-system.md`'s own worked example, ~98.4%). Reproduced twice
   (both bulk-upload runs, before and after the DB reset).
2. **`questions_prepared: 9, estimated_minutes: 8` are hardcoded placeholders**
   in the upload response for every `platform_not_taught` result, regardless of
   platform or content — confirmed by the code's own comment at
   `ingestion.py:400-406` ("a placeholder count until the learning subsystem...
   flagged as a fixture value, not hardcoded per artifact"). All six
   `platform_not_taught` results in this batch (cloud, fortios, 2× juniper,
   routeros, panos) carry identical `9`/`8` values — not independently computed.

---

## Beat 2 — Teaching an untaught platform live, timed, 0% → ≥71% coverage

**Baseline (0%).** `GET /knowledge/rulepacks` → only `cisco_iosxe` registered.
`GET /training/queue` → `routeros` gap `platform_not_taught`, 9/9 questions
unanswered. Ran `POST /campaigns/{id}/assess` before teaching: **42 assessments
produced, none for the MikroTik artifact** — it is not assessed at all pre-teaching
(a true 0%, not just a low score).

**Seed.** Re-ran the project's own seed script (re-seeding was necessary after the
mid-session DB reset):

```
cd nsca/platform
DATABASE_URL="postgresql+psycopg://nsca:nsca@localhost:15432/nsca" \
  .venv/Scripts/python seed_training_queue.py
# seeded 9 training questions for platform='routeros'
```

**Answer all 9, timed.** `POST /training/answer` for `Q-routeros-001..009`, response
`"confirm"` (`polarity_confirmed: true` on Q1, which correctly required it —
`disabled=no` → enabled, the doc's own polarity-inversion example), each also
carrying `taught_by` + `source_artifact` (both required together for rule synthesis
to trigger inline — this is **not documented** in `15-api-specification.md`'s
`POST /training/answer` example body, which shows only
`question_id`/`response`/`polarity_confirmed`; a user following the spec literally
would answer all 9 questions and get zero synthesized rules).

**Timing:** 9/9 answered in **2–3 seconds** of API round-trip time (measured twice,
reproducibly). This measures API mechanics only, not a human reviewing each
question — the doc's own worked example (`08-learning-system.md` §9) quotes
8 min 12 s end-to-end for a human doing this with real judgement per question.

**Result of answering:** 16 provisional extractor rules synthesized from the
confirmed mappings in questions 1, 2 (questions 3, 5–9 had empty `mappings` in
their proposals and correctly produced no rule — expected, not a bug).

**Real defect — unhandled 500 on `Q-routeros-004`, reproduced twice.**
Answering `Q-routeros-004` (`/user group` section, tokens `full`/`read`) crashes
with a bare `500 Internal Server Error` (`Internal Server Error`, no detail). Root
cause, isolated by calling `training_service.submit_answer()` directly against the
same live DB:

```
nsca_platform.learning.ratification.GatesNotPassed:
  cannot save user_group.full.auth_local_groups_full_access_policy_present:
  validation gates did not all pass
```

`GatesNotPassed` is the *intended* outcome per `08-learning-system.md` §7.1 ("On
failure: Reject") — but `api/training.py`'s `submit_answer` only catches
`QuestionNotFound` and a string-matched polarity error; every other exception,
including this expected/designed rejection, falls through to FastAPI's default
handler and becomes an undifferentiated 500. A live demo hitting this question
would show a raw crash instead of the graceful "this proposal didn't pass
validation" the design calls for.

**Ratification.** All 16 provisional rules ratified via
`POST /training/rules/{id}/ratify` (`X-Dev-Role: platform_administrator`), all
returned `200`, all moved to `status: "ratified"`.

**Critical gap — ratified rules do not change the next run. Confirmed twice.**
After full ratification:

| Check | Result |
|---|---|
| `GET /knowledge/rulepacks` | still only `cisco_iosxe` — `routeros` never appears |
| `GET /training/queue` | `routeros` gap still `platform_not_taught` |
| `GET /training/metrics` | `{"platforms": [], "trend": "declining"}` — no `routeros` entry, no `confirmations_to_70pct` |
| `POST /campaigns/{id}/assess` (re-run) | still only 42 assessments (cisco_ios); the MikroTik artifact is **still never assessed** |

**This is the single most significant finding of the whole rehearsal.** The
question → confirm → synthesize → validate-gates → ratify pipeline is real and
persists real data in Postgres (16 genuinely ratified rules, verifiable by
re-querying `GET /training/rules`). But there is currently no live code path that
turns those ratified rules into (a) a registered rulepack, (b) an updated queue
gap-status, (c) a transfer-metrics entry, or — most importantly — (d) an actual
assessable platform on the next `/assess` run. **The demo beat "coverage 0% →
≥71%" is not achievable end-to-end via the live running system in its current
build.** The UI/API mechanics for teaching genuinely work; the loop that closes
back into "next assessment run reflects it" does not.

**Also found:** `GET /knowledge/rulepacks/{id}/coverage` returns an identical
hardcoded payload (`controls_covered: 154, controls_total: 187, coverage_rate:
0.82`) for **any** rulepack id, including a nonsense id
(`totally_fake_platform_xyz`) — confirmed non-functional stub, not a real lookup.

---

## Beat 3 — The per-device PDF report

**Setup.** Fresh campaign `CMP-2026Q3-002` (`Phase3 Demo Rehearsal - Beat3 PDF
Report`), CIS 4.1.0 + NIST 800-53 Rev5 + STIG 2026-01 selected. Uploaded two
artifacts under a directory-per-device path (`FR-ING-010`'s multi-artifact
correlation):

- `CORE-SW-01/running-config.txt` — real fixture (`ap003/core_sw_01.cfg`, has
  `transport input telnet ssh` etc.)
- `CORE-SW-01/show-version.txt` — hand-written realistic `show version` +
  `show inventory` output, including `Processor board ID FCW2140L0GH` and
  `SN: FCW2140L0GH` / `SN: FOC2138Y0K2` / `SN: ART2137F0PL` (matching the exact
  serials the codebase's own report-model test fixture,
  `nsca_platform/tests/fixtures/core_sw_01.py`, uses for this same device)

Both artifacts correlated to a single device `CORE-SW-01` (1 assessment produced
from 2 artifacts — multi-artifact correlation itself works). Assessed, issued the
campaign, generated the report:

```
POST /campaigns/CMP-2026Q3-002/reports/generate?device=CORE-SW-01&mode=issued
→ {"report_id": "RPT-2026Q3-002-CORE-SW-01-f3b65590", "status": "done"}
```

**PDF rendering — not available on this machine, confirmed cleanly, not a code
defect.** `GET /reports/{id}` → `"formats_available": ["csv", "docx", "json",
"oscal"]` — `pdf` is absent from the list *before* any download is even attempted.
`GET /reports/{id}/download?format=pdf` → `404`,
`{"detail":"... has no stored 'pdf' rendering"}`. This matches the known
WeasyPrint/GTK-on-Windows gap flagged at platform M4. I did not find any evidence
of a crash-on-render (which would suggest a code bug); the renderer appears to
never register `pdf` as available on this host at all, consistent with a missing
native dependency rather than a runtime failure. **PDF rendering itself is
genuinely untested on this machine** — verified via the JSON/DOCX document model
instead, per the task's own fallback instruction.

**DOCX generated successfully** (39 KB, real content, downloaded and inspected
directly with `python-docx`). Checked against the six required elements:

| Requirement | Result | Evidence |
|---|---|---|
| Serial numbers | **FAIL** | Report literally states: *"Serial numbers: NOT DETERMINED — `show inventory` output was not supplied for this device. Supply it to complete device identification."* — despite a realistic show-inventory artifact being supplied. Traced to `nsca_platform/services/ingestion.py` (lines ~140–145), whose own comment admits: *"chassis serial is not extracted anywhere in this package yet... `IdentityCandidate` here has `chassis_serial=None`... flagged, not silently pretended to be serial-aware."* Multi-artifact upload/correlation works (both files did attach to `CORE-SW-01`); serial **extraction** from that content is simply unimplemented. |
| Evidence with line numbers | **PASS** | Real per-finding evidence, e.g. `ART-94BEB9 > 9 \| aaa authentication login default group tacacs+ local`, `> 22 \| transport input ssh`, `> 23 \| exec-timeout 5 0`, `> 12 \| ip ssh version 2`. |
| Risk severity assessments | **PASS** | Every finding carries a severity marker (`[!!] CRITICAL`, `[!] HIGH`, `[~] MEDIUM`, `[-] LOW`) next to its verdict. |
| Version-specific CLI remediation | **FAIL** | Report's Remediation Playbook section reads verbatim: *"No remediation plan has been generated for this device."* — despite 4 real FAIL findings. Independently queried `GET /findings/{id}/remediation` directly for three different FAIL findings (`NSCA-LOG-001`, `NSCA-MGMT-005`, `NSCA-MGMT-006`) — **all three returned byte-identical stub content** (`"disable telnet"` / `"enable ssh v2 only"`, `lockout_risk: false`), regardless of which control was actually failing. Confirmed non-functional stub, not real per-finding remediation. |
| Lockout warning on ≥1 step | **FAIL** | Follows directly from the above — the remediation stub always returns `lockout_risk: false` / `"no_lockout_detected"`, so a lockout warning can never be produced through the live path. **Contrast:** the codebase's own unit-test fixture (`nsca_platform/tests/fixtures/core_sw_01.py`) proves the real `remediation.planner` / `remediation.lockout` / `remediation.dry_run` modules genuinely work and do produce a lockout-flagged, version-specific plan (e.g. *"Disable Telnet on VTY lines"* flagged `lockout_risk`) — that logic is just never invoked from the live `/reports/generate` or `/findings/{id}/remediation` endpoints. |
| Section 6 "Unassessed" + verbatim closing statement | **PASS** | Real section present: *"UNASSESSED — 12 controls could not be determined (33% of applicable controls)."* followed by *"COVERAGE STATEMENT — This assessment determined 45% of applicable controls. It is not a statement that the remainder are compliant. An unexamined control is not a passing control."* The mandated closing sentence ("An unexamined control is not a passing control") is reproduced verbatim; the lead-in uses "remainder" rather than "the remaining X%" (a paraphrase, not a defect). |

---

## §9 Verification checklist (traceability matrix)

Each item below was actually exercised against the live system this session unless
marked otherwise.

1. **Single and bulk upload, including cloud JSON, not CLI only** — **PASS.**
   Bulk: 48 files / 8 platform families in one `POST .../artifacts` call, `cloud_fw.json`
   correctly classified as `cloud_generic_fw`. Single: 2-file directory-per-device
   upload in Beat 3.

2. **Training GUI that persists and demonstrably changes the next run** — **FAIL.**
   Persists: yes, 16 ratified rules verified still present in Postgres after
   ratification. Demonstrably changes the next run: no — confirmed twice that
   `/campaigns/{id}/assess` re-run after full ratification still produces zero
   assessments for the taught platform, and `/knowledge/rulepacks`,
   `/training/queue`, `/training/metrics` never reflect the newly-ratified rulepack.

3. **Framework selector across CIS / NIST / STIG / ISO with versions stated** —
   **PARTIAL.** CIS 4.1.0 / NIST 800-53 Rev5 / STIG 2026-01 all selectable with
   versions on campaign creation and echoed back correctly. ISO: a campaign
   *accepts* an arbitrary `{"framework": "iso", ...}` entry with no validation
   against any real backing catalog (tried this — it was accepted unconditionally),
   which suggests campaign framework selection is not actually validated against a
   knowledge base at all in this build, for any framework family.

4. **One PDF per device, not only an estate dashboard** — **PARTIAL.**
   Architecture confirmed correct: `POST /campaigns/{id}/reports/generate?device=X`
   produced a genuine per-device report distinct from
   `GET /campaigns/{id}/reports/estate` (checked — the estate endpoint returns only
   an aggregate `devices_included` count, no per-device content). Actual PDF
   **rendering** is NOT-VERIFIABLE-HERE (native library unavailable on this
   Windows sandbox; confirmed cleanly, not a code defect — see Beat 3).

5. **PDF contains serial numbers, proving multi-artifact ingestion works** —
   **FAIL.** Multi-artifact correlation itself works (two artifacts attached to
   one device). Serial extraction does not — confirmed empty in the live report,
   traced to an explicitly-acknowledged gap in `ingestion.py`.

6. **PDF shows pass/fail with risk severity assessments** — **PASS** (verified via
   DOCX substitute; real severities and verdicts per finding).

7. **PDF shows version-specific CLI remediation** — **FAIL.** Report says no
   remediation plan was generated; the standalone remediation endpoint returns
   identical stub content for every finding regardless of control.

8. **A new platform added without any code change or redeployment** — **PARTIAL.**
   The teaching workflow itself required zero code changes or redeploys (question
   seeding, answering, synthesis, and ratification are all real HTTP/DB
   operations). But per item 2, the platform never becomes actually assessable —
   so "added" is true only in the narrow sense that rules exist in the DB, not in
   the product sense that the platform can now be audited.

9. **A new framework added without code change** — **PARTIAL.**
   `POST /knowledge/frameworks/import` accepts a real OSCAL catalog and reports
   success — tried this live with a minimal valid OSCAL catalog wrapping an "ISO"
   title, got `201` with `"items_imported": 1`. But two problems observed: (a) the
   response mislabels the imported framework as `"framework": "nist"` regardless of
   the catalog's actual content/title, and (b) `GET /knowledge/frameworks`
   afterward shows no new entry at all — the import doesn't appear to register
   anywhere queryable, and (per item 3) campaign framework selection doesn't
   validate against it either way.

10. **Full assessment runs with the network disconnected** — **PARTIAL /
    verified by code audit only.** No outbound `requests`/`httpx`/`urllib`/`aiohttp`
    calls exist anywhere in the engine; the platform's only network call is a
    localhost-only Ollama call confined to the training-proposal path, never
    invoked by ingestion or assessment. Did not physically disconnect the network
    adapter in this session (would have severed my own access to the sandbox), so
    this is a static-analysis conclusion, not an empirical one.

11. **Every finding cites artifact and line numbers** — **PARTIAL/FAIL** as
    literally stated. Findings backed by an explicit "true" fact (e.g.
    `NSCA-MGMT-002`, `NSCA-MGMT-004`, `NSCA-MGMT-007`) do cite real
    artifact-id + line-number evidence. But several genuine FAIL-verdict findings
    in the same live report (`NSCA-AUTH-001`, `NSCA-LOG-001`, `NSCA-MGMT-005`,
    `NSCA-MGMT-006` — all absence-based facts, e.g. "no central auth configured")
    have empty evidence (`artifact: null` or `""`, `lines: []`). "Every finding"
    is not currently true for this class of finding.

12. **UNKNOWN is visually impossible to confuse with PASS** — **PARTIAL /
    NOT-VERIFIABLE-HERE for the visual/UI claim.** At the data level this holds:
    UNKNOWN items never appear in the `findings` array alongside PASS/FAIL/
    NOT_APPLICABLE verdicts at all — they only surface via the assessment's
    `counts.unknown` total and the separate "Unassessed" control-id list, so they
    structurally cannot be rendered as an indistinguishable PASS row. The actual
    visual/color/icon treatment is a frontend concern I did not drive in this
    session (task scope was the backend demo beats + checklist), so the UI-level
    guarantee itself is unverified here.

13. **Netmiko/NAPALM collection demonstrable against a virtual lab** —
    **NOT-VERIFIABLE-HERE.** No virtual lab exists in this sandbox. Did confirm
    `POST /campaigns/{id}/collect` exists and correctly rejects
    `"mode": "read_write"` with `422` (Pydantic literal validation — only
    `"read_only"` is accepted, matching the spec's absolute constraint). A
    `"mode": "read_only"` request against a nonexistent host (`10.0.0.5`) returned
    an async job that "completed" instantly with `{"accepted": 389}` — the number
    389 is suspiciously identical to `15-api-specification.md`'s own worked
    example, suggesting this path is itself a stub rather than a genuine
    Netmiko/NAPALM connection attempt (which should have failed or timed out
    against a real nonexistent host). Real collection against actual hardware
    cannot be verified either way in this environment.

### Tally

| Result | Count | Items |
|---|---|---|
| PASS | 2 | 1, 6 |
| PARTIAL | 7 | 3, 4, 8, 9, 10, 11, 12 |
| FAIL | 3 | 2, 5, 7 |
| NOT-VERIFIABLE-HERE | 1 | 13 |

(Item 11's PARTIAL leans toward FAIL as literally worded — "every finding" is
demonstrably not true; kept as PARTIAL because the majority of fact-backed
findings do cite real evidence correctly.)

---

## Summary of genuinely new findings (not previously known from milestone docs)

1. **Mid-session live-DB reset** — all campaigns/artifacts/rules disappeared once,
   IDs re-cycled from 1, while the Postgres container itself never restarted.
   Demo-day risk: rehearsed state on the shared dev DB is not durable against
   concurrent resets.
2. **`grammar_coverage` always `0.0` for MikroTik** due to a platform-id key
   mismatch (`"mikrotik_routeros"` in the lookup table vs. `"routeros"` from the
   real fingerprinter) — reproducible.
3. **`questions_prepared`/`estimated_minutes` are hardcoded placeholders** in the
   ingestion response, not real per-artifact numbers (self-documented in code).
4. **`POST /training/answer` crashes with an unhandled 500** on at least one real
   question (`Q-routeros-004`) whose synthesized rule fails a validation gate —
   the designed "reject gracefully" path isn't caught by the API layer.
   Reproducible.
5. **Ratified training rules are not wired to `/knowledge/rulepacks`,
   `/training/queue`, `/training/metrics`, or `/campaigns/{id}/assess`** — the
   single biggest gap found. Teaching mechanically works and persists; it does not
   change what the next assessment run can see.
6. **`GET /knowledge/rulepacks/{id}/coverage` is a non-functional stub** —
   identical output for any id, including nonexistent ones.
7. **Chassis-serial extraction is unimplemented** in ingestion (self-documented in
   code) — confirmed live: a realistic show-inventory artifact does not produce
   serials in the generated report.
8. **`GET /findings/{id}/remediation` is a non-functional stub** — identical
   `"disable telnet"/"enable ssh v2 only"`, `lockout_risk: false` output regardless
   of which finding/control is queried. The real remediation/lockout/dry-run
   modules exist and work (proven by the codebase's own unit-test fixture) but are
   not wired into any live endpoint.
9. **`POST /knowledge/frameworks/import` mislabels imported catalogs** (an ISO-
   titled OSCAL catalog came back tagged `"framework": "nist"`) and imported
   content does not appear in `GET /knowledge/frameworks` afterward.
10. **Campaign framework selection accepts arbitrary unvalidated framework
    strings** — no cross-check against any real framework catalog, for CIS, NIST,
    STIG, or ISO alike.
11. Several genuine FAIL-verdict findings (all from absence-based facts, e.g. "no
    central authentication configured") carry no evidence/line-number citation at
    all, unlike presence-based FAIL/PASS findings which do.
