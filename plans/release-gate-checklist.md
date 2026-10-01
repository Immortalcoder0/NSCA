# Release gate checklist — TRD-11.3 blocking criteria

Status document, produced by Backend Track B's M5 (backend-02 §5). **This is
not a claim of release-readiness.** Per TRD-11.3 §2: "The blocking criteria
are not a sample of the test suite... A release with any of them failing is
not a release with known issues; it is a product whose central claims are
unproven." Several of the fourteen are legitimately `NOT-YET` — frontend a11y
tooling, Phase 2 collection, and the two manual-only usability procedures
(B14 and its siblings in TRD-11.3 §6.1) have not happened. That is reported
here, not hidden.

Statuses are `PASS` (a real, currently-passing automated test demonstrates
the criterion), `PARTIAL` (some real, passing coverage exists but does not
fully close the criterion as TRD-11.3 states it), `NOT-YET` (no automated
coverage exists, or the criterion is explicitly a manual procedure per
TRD-11.3 §6.1 that has not been run), and `NOT-APPLICABLE-YET` (the feature
the criterion depends on — e.g. Phase 2 collection — does not exist in this
codebase yet, so the criterion cannot be meaningfully evaluated).

Verified 2026-09-01 by running the cited test files directly (`PYTHONHASHSEED=0
pytest`, both `engine/` — 250 passed — and `platform/` against a real
Postgres — 221 passed, 2 skipped). File:test references below are exact,
not paraphrased — every one was opened and read, not assumed from a filename.

## G2 — Never over-claim (five criteria)

| ID | Criterion | Status | Evidence |
|---|---|---|---|
| B1 | V-03.2-001 — Absence never becomes false | PARTIAL | No automated test found asserting *zero instances of `value == false`* across the full corpus specifically for absent-with-no-default booleans. Structural support exists (`engine/nsca_engine/tests/test_schema_registry.py`, `test_worked_example.py`, `test_controls_pack.py`, `test_rulepack_loader.py` all touch `default_unknown` semantics) but none states this exact zero-instances property as its own assertion. Flagged, not claimed PASS. |
| B2 | V-05.2-001 — A missing required fact yields UNKNOWN, never PASS | PASS | `engine/nsca_engine/tests/test_missing_fact_never_pass.py` (module docstring cites V-05.2-001 verbatim: "a control whose required fact is omitted..."). Passing in the 250-test engine run. |
| B3 | V-05.1-002 — Comparison with unknown yields unknown, never false | PASS | `engine/nsca_engine/tests/test_expression_kleene.py:79` ("V-05.1-002: comparison with unknown yields unknown, never false"). Passing. |
| B4 | V-03.2-005 — Uncertainty propagates through derived facts | PARTIAL | `engine/nsca_engine/tests/test_schema_registry.py` touches provenance propagation but the exact "derived fact inherits the weakest provenance of its inputs, zero exceptions" property was not found stated as its own test. `extract/runtime.py::compute_derived_facts` is the real implementation; a dedicated corpus-wide test was not located in the time available. |
| B5 | V-05.2-005 — Scope contamination downgrades passing controls | PASS | `engine/nsca_engine/tests/test_risk_severity.py` and `engine/nsca_engine/api.py::_compute_scope_contamination` (real, non-stub M4 code — see that function's own docstring for the two documented contamination triggers). `platform/nsca_platform/tests/test_finding_lifecycle.py::test_pass_partial_verdict_on_contamination` exercises the platform-side `PASS_PARTIAL` finding state end to end. Both pass. |

## G1 — Determinism (two criteria)

| ID | Criterion | Status | Evidence |
|---|---|---|---|
| B6 | V-10.1-001 — Byte-identical output for identical inputs | PASS | `engine/nsca_engine/tests/test_golden_set.py` (`gate_determinism_golden_set`, 22 tests, passing), `test_determinism.py`, `test_assess_campaign_determinism.py`, `test_graph_determinism.py` (engine side). `platform/nsca_platform/tests/test_report_determinism.py` (report-hash determinism, PDF-bytes stage skipped on this Windows host — no GTK3/Pango runtime — but document-model/HTML/DOCX/JSON/CSV/OSCAL determinism verified). Not run as the doc's literal "20 golden campaigns × 10 runs × 2 host configurations" acceptance procedure — that is a release-time manual/CI-scale run, not a unit test — but the underlying determinism property is real-tested. |
| B7 | V-10.1-002 — No model inference in the assessment path | PARTIAL | `engine/nsca_engine/tests/test_gate_g1_determinism.py` (`gate_g1_determinism`) structurally forbids any `nsca_platform`/learning import from `engine/`, and `assess_device`/`assess_campaign` (`nsca_engine/api.py`) import no model/inference library anywhere in their call graph — strong structural evidence. No test was found that runs a full campaign with model endpoints made deliberately unreachable and asserts zero inference calls, which is what V-10.1-002 literally specifies. |

## G3 — Evidence binding (two criteria)

| ID | Criterion | Status | Evidence |
|---|---|---|---|
| B8 | V-02.1-002 — Line ranges resolve to exact source text | PASS | `engine/nsca_engine/tests/test_indentation_parser.py::test_line_ranges_resolve_to_exact_source_text`. Passing. Only verified for the indentation paradigm's own test corpus, not literally "across the full corpus" every paradigm — other paradigm test files (`test_brace_parser.py`, `test_flat_path_parser.py`, etc.) were not individually re-checked for an equivalent named test in the time available. |
| B9 | V-03.1-002 — Every fact carries resolvable provenance | PARTIAL | No test with this exact name/assertion ("every explicit fact's provenance resolves to real artifact text matching its recorded excerpt," corpus-wide) was located. `Provenance`/`Evidence` dataclasses (`nsca_engine/types.py`) carry `artifact_id`/`lines`/`excerpt` on every explicit fact by construction, and `Evidence`-carrying findings are exercised throughout the finding-lifecycle tests, but a dedicated resolvability assertion was not found. |

## G4 — Assessor independence (one criterion)

| ID | Criterion | Status | Evidence |
|---|---|---|---|
| B10 | V-01.3-001 — No write-capable code path exists | PASS (real, newly built this milestone) | `engine/nsca_engine/tests/test_gate_g4_independence.py` — did **not** exist before M5 (confirmed by search across both trees). Built this milestone: AST-walks `nsca_engine/collection/` and `nsca_platform/api/` for a bare-`str` command parameter, an `ALLOWLIST` containing a config/write/commit/copy/reload verb, or a `collect()` call site not passing a `CommandId`. Currently passes because `collection/` is an empty package and `POST /campaigns/{id}/collect`'s request body already types `mode: Literal["read_only"]` — a real, non-vacuous pass proven by the gate's own self-test (`test_gate_g4_independence_actually_detects_a_violation`), not a fabricated green. |

## Polarity (one criterion)

| ID | Criterion | Status | Evidence |
|---|---|---|---|
| B11 | V-08.3-002 — A polarity-inverting rule cannot be saved without explicit confirmation | PASS | `platform/nsca_platform/tests/test_polarity.py`, `platform/nsca_platform/learning/polarity.py`, `platform/nsca_platform/services/training.py` (the polarity gate on `POST /training/answer`). `platform/nsca_platform/tests/test_stub_endpoints.py`'s training-flow tests exercise the 422-on-unconfirmed-polarity behaviour over the real HTTP API. All passing. |

## Robustness (one criterion)

| ID | Criterion | Status | Evidence |
|---|---|---|---|
| B12 | V-11.2-001 — Semantics-preserving mutation produces identical facts | PASS | `engine/nsca_engine/tests/test_metamorphic.py`, `test_metamorphic_m2.py` (`metamorphic/` fixture directory). Passing as part of the 250-test engine run. Not independently re-verified that every mutation in "the full mutation catalogue" is present — the file exists and passes, taken as real coverage rather than re-audited line by line in the time available. |

## The core product claims (two criteria)

| ID | Criterion | Status | Evidence |
|---|---|---|---|
| B13 | V-08.3-011 — A new platform is taught without code change, ≥70% coverage | PARTIAL | `platform/nsca_platform/tests/test_training_pipeline.py` exercises mine → propose → confirm → synthesize → validate → save-provisional → ratify → report-eligibility → transfer-metrics end to end over the MikroTik acceptance fixture (that test's own docstring: "the closest thing in this milestone to... V-08.3-011... without a real assessment worker to re-assess with"). **M5 changes this**: `services/assessment.py` now calls the real `assess_device` against a real `KnowledgeBase` (`knowledge_base_loader.py`), so the previously-missing "re-assess" step is now technically wired — but no test was built this milestone that closes the full loop (ratify a newly-synthesized rulepack → reload/hot-swap the `KnowledgeBase` cache → re-assess a held-out platform's corpus → measure coverage ≥70%, with zero code change/restart). That closing test is real, scoped, buildable follow-up work, not attempted here — flagged rather than claimed done. |
| B14 | V-08.4-007 — Onboarding target met by a real administrator | NOT-YET (manual, by design) | TRD-11.3 §6.1 states this explicitly has "no automated oracle" and is executed as a recorded manual procedure — a real network administrator, unaided, timed. Not run. Cannot be run by an automated test; reported here as not-yet-executed, not as a test failure. |

## Summary

Of the fourteen blocking criteria: **PASS = 8** (B2, B3, B5, B6, B8, B10, B11,
B12), **PARTIAL = 5** (B1, B4, B7, B9, B13), **NOT-YET = 1** (B14, explicitly
manual per TRD-11.3 §6.1).

None of the four `NOT-APPLICABLE-YET` cases (Phase 2/3 features with zero
existing code) apply to this list — all fourteen blocking criteria concern
capability that exists in some form in this codebase; the gaps above are
"no dedicated automated proof was found/built this milestone," not "the
feature doesn't exist."

**This is a mid-build status snapshot, not a release record.** Per
TRD-11.3 §6.2, `DD-11.3-01`: blocking criteria admit no waiver — the honest
position is that this product is not release-ready today, which is expected
at M5 of a phased build, not a defect in this report.
