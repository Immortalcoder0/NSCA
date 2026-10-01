# 13 · Non-Functional Requirements

---

## NFR-PERF · Performance and scale

| ID | Requirement |
|---|---|
| NFR-PERF-001 | The system **MUST** assess **500 devices in under 5 minutes** on commodity hardware (8 cores, 16 GB), fully offline |
| NFR-PERF-002 | Single-device assessment **MUST** complete in under 2 seconds for a configuration of 10,000 lines |
| NFR-PERF-003 | The system **MUST** handle individual configurations up to **500,000 lines** (large firewall policy sets) without failure |
| NFR-PERF-004 | Bulk ingestion **MUST** process at least 100 artifacts per minute including parsing and extraction |
| NFR-PERF-005 | Per-device PDF generation **MUST** complete in under 5 seconds |
| NFR-PERF-006 | Graph construction and reachability analysis **MUST** complete in under 60 seconds for an estate of 1,000 devices |
| NFR-PERF-007 | Template mining for the training queue **MUST** complete in under 30 seconds for a 10,000-line configuration |
| NFR-PERF-008 | Interface response for finding navigation **MUST** be under 500 ms at the 95th percentile |
| NFR-PERF-009 | The system **MUST** support estates of at least **10,000 devices** and campaign histories of at least 5 years |
| NFR-PERF-010 | A failure on one artifact **MUST NOT** abort a bulk job; failures are recorded and the job continues |

### Rationale

NFR-PERF-001 is a direct consequence of removing models from the assessment path.
An architecture that invokes a model per device cannot approach this figure, and
the contrast is a legitimate and measurable product claim.

NFR-PERF-003 is not hypothetical — large enterprise firewall policy exports
routinely exceed 100,000 lines, and a tool that fails on them fails on precisely
the devices that matter most.

---

## NFR-SEC · Security

| ID | Requirement |
|---|---|
| NFR-SEC-001 | The system **MUST** be architecturally incapable of modifying an audited device |
| NFR-SEC-002 | Live collection **MUST** use a read-only command allowlist enforced in the collection driver, not by convention or configuration |
| NFR-SEC-003 | Collection credentials **MUST** be encrypted at rest and **MUST NOT** be retrievable through any interface or API |
| NFR-SEC-004 | Configuration artifacts **MUST** be encrypted at rest |
| NFR-SEC-005 | The system **MUST NOT** transmit configuration content to any external service during assessment |
| NFR-SEC-006 | Where model assistance is used, secrets, credentials and hashes **MUST** be redacted before transmission, and a local inference mode **MUST** be available |
| NFR-SEC-007 | Rulepacks and control packs **MUST** be declarative data incapable of arbitrary code execution |
| NFR-SEC-008 | Imported knowledge bundles **MUST** be cryptographically signed and verified before use |
| NFR-SEC-009 | The system **MUST NOT** treat text within configuration files as instructions under any circumstances |
| NFR-SEC-010 | Secrets appearing in evidence excerpts **MUST** be masked in reports, with masking indicated |
| NFR-SEC-011 | All authentication **MUST** support multi-factor, and the system **SHOULD** integrate with enterprise identity providers |
| NFR-SEC-012 | The audit log **MUST** be append-only and not editable through the application |
| NFR-SEC-013 | The system **MUST** enforce role-based access control on every operation, including API access |
| NFR-SEC-014 | Session management **MUST** enforce configurable idle and absolute timeouts |
| NFR-SEC-015 | The system **MUST** be deployable such that no inbound network access to audited devices is possible from the platform |

### On NFR-SEC-007

This is not defensive over-engineering. Rulepacks are **importable content** —
one organisation teaches a platform and exports the result for others. If a
rulepack could execute code, importing a community rulepack would be a remote
code execution vector, and the portability that makes the learning system
valuable would become its most dangerous property.

---

## NFR-DEP · Deployment

| ID | Requirement |
|---|---|
| NFR-DEP-001 | The system **MUST** operate fully in an air-gapped environment with no external connectivity |
| NFR-DEP-002 | Knowledge base updates **MUST** be deliverable as signed offline bundles via physical media |
| NFR-DEP-003 | The system **MUST** be deployable as containers on standard Linux hosts |
| NFR-DEP-004 | The system **MUST** support a single-node deployment for assessor workstation use, with identical engine behaviour |
| NFR-DEP-005 | Installation **MUST NOT** require internet access at any stage |
| NFR-DEP-006 | The system **MUST** report knowledge base freshness — current versus available versions, and the age of offline vulnerability data |
| NFR-DEP-007 | Backup and restore **MUST** preserve reproducibility: artifacts, knowledge base versions, and audit logs |
| NFR-DEP-008 | Upgrades **MUST NOT** retroactively alter issued campaigns |

### On NFR-DEP-001

The intended deployment is critical national infrastructure. Networks are
classified or air-gapped. A configuration file is a complete map of a network's
defences — transmitting one to an external service is not a policy violation, it
is an intelligence loss.

Any capability that cannot function offline is either optional or wrongly
designed.

---

## NFR-REL · Reliability and correctness

| ID | Requirement |
|---|---|
| NFR-REL-001 | Assessment **MUST** be deterministic: identical inputs and knowledge base versions produce byte-identical results |
| NFR-REL-002 | The system **MUST** support verification mode — re-executing a historical campaign and confirming the result matches its manifest |
| NFR-REL-003 | Every extractor **MUST** ship with regression tests; the full suite **MUST** pass before a rulepack version is accepted |
| NFR-REL-004 | Every control **MUST** ship with fixture-based tests covering PASS, FAIL, UNKNOWN and NOT_APPLICABLE outcomes |
| NFR-REL-005 | The system **MUST** support **metamorphic validation** — semantics-preserving mutations of configurations must produce identical facts |
| NFR-REL-006 | The corpus regression suite **MUST** be re-run on every knowledge base change, and any verdict that changes without an explanatory content change **MUST** be treated as a defect |
| NFR-REL-007 | False positive rate on the validated corpus **MUST** be below 2% |
| NFR-REL-008 | Cross-validation against at least one independent reference implementation **SHOULD** be performed on overlapping controls |
| NFR-REL-009 | Partial failure **MUST** degrade gracefully: an unparseable artifact yields UNKNOWN verdicts and a coverage reduction, never a fabricated pass |

### On NFR-REL-005

Metamorphic validation is the highest-value correctness gate because it finds
defects no hand-written test would catch — you would never have thought to write
the test case that exposes them.

Mutations applied: block reordering, object renaming, whitespace alteration,
command abbreviation and expansion, comment insertion, line-ending changes,
equivalent-syntax substitution. Any resulting change in extracted facts is a
parser defect.

---

## NFR-USE · Usability

| ID | Requirement |
|---|---|
| NFR-USE-001 | The training interface **MUST** be operable by a network administrator with no programming experience |
| NFR-USE-002 | The user **MUST NOT** be required to author regular expressions, expressions, or queries at any point |
| NFR-USE-003 | Onboarding an unseen platform to ≥ 70% coverage **MUST** be achievable in under 15 minutes of administrator time |
| NFR-USE-004 | Every finding **MUST** be traceable to its evidence in one interaction |
| NFR-USE-005 | UNKNOWN **MUST** be visually distinct from PASS at any display size and in monochrome |
| NFR-USE-006 | Severity **MUST NOT** be conveyed by colour alone |
| NFR-USE-007 | The interface **MUST** meet WCAG 2.1 AA contrast requirements |
| NFR-USE-008 | The interface **MUST** be fully keyboard navigable, including the training question flow |
| NFR-USE-009 | Long-running operations **MUST** show progress, remaining work, and the effect of completion |
| NFR-USE-010 | Reports **MUST** be comprehensible without access to the platform |

---

## NFR-MNT · Maintainability

| ID | Requirement |
|---|---|
| NFR-MNT-001 | Adding a platform **MUST** require no code change — rulepack data only |
| NFR-MNT-002 | Adding a framework **MUST** require no code change — control pack and mapping data only |
| NFR-MNT-003 | Adding a schema fact **MUST** require no code change — registry entry only |
| NFR-MNT-004 | All knowledge artifacts **MUST** be versioned, diffable, signable and revertible |
| NFR-MNT-005 | Knowledge base updates **MUST** be previewable with quantified estate impact before ratification |
| NFR-MNT-006 | Historical campaigns **MUST** remain pinned to the knowledge base versions they used |
| NFR-MNT-007 | The system **MUST** report per-rulepack coverage: facts producible, corpus line coverage, extractor and test counts |
| NFR-MNT-008 | The system **MUST** report per-framework automation coverage: automated, manual-only, data-unavailable, not implemented |

### On NFR-MNT-001 to 003

These three requirements are the operational statement of the problem statement's
*"without requiring backend code modifications for every update."* They are
testable: adding a platform, a framework, or a fact must be achievable by an
operator with no access to source code and no deployment.

---

## NFR-DAT · Data management

| ID | Requirement |
|---|---|
| NFR-DAT-001 | Ingested artifacts **MUST** be immutable from receipt |
| NFR-DAT-002 | Retention **MUST** be configurable per campaign, consistent with audit record retention obligations |
| NFR-DAT-003 | Deleting artifacts **MUST** warn that reproducibility of dependent reports is destroyed, and **MUST** record the deletion |
| NFR-DAT-004 | The system **MUST** support export of a complete campaign — artifacts, findings, reports, manifest — as a self-contained archive |
| NFR-DAT-005 | The system **MUST** support full-text search across artifacts and findings |
| NFR-DAT-006 | Personal data **MUST** be limited to what is necessary for attribution |

### On NFR-DAT-003

There is a genuine tension between data minimisation and audit reproducibility.
Deleting a configuration artifact destroys the ability to reproduce every finding
derived from it. The platform's position is to make this trade-off explicit and
recorded rather than silently resolving it in either direction.

---

## NFR-OBS · Observability

| ID | Requirement |
|---|---|
| NFR-OBS-001 | The system **MUST** log all assessment operations with timing and outcome |
| NFR-OBS-002 | Parse failures and unmatched constructs **MUST** be recorded with sufficient context to drive training |
| NFR-OBS-003 | The system **MUST** expose health and readiness endpoints |
| NFR-OBS-004 | Coverage trends **MUST** be observable over time, per platform and per estate |
| NFR-OBS-005 | Learning effort metrics **MUST** be recorded: confirmations per platform, proposal acceptance rate, polarity correction rate, wall-clock onboarding time |
| NFR-OBS-006 | Operational logs **MUST NOT** contain configuration content or credentials |

### On NFR-OBS-005

These metrics are not operational telemetry. They are **evidence for the
product's central claim** — that the system accumulates transferable knowledge.
The declining confirmation curve across successive platforms is the measurable
answer to *"Scalability & Adaptation"*, and it can only be produced if the
platform records it from the first platform onward.

---

## NFR-CMP · Compliance and licensing

| ID | Requirement |
|---|---|
| NFR-CMP-001 | The system **MUST NOT** redistribute CIS Benchmark document text; control identifiers may be cited |
| NFR-CMP-002 | The system **MUST NOT** redistribute ISO/IEC 27001 text; control identifiers may be cited |
| NFR-CMP-003 | DISA STIG content **MAY** be redistributed in accordance with its terms |
| NFR-CMP-004 | NIST SP 800-53 OSCAL content **MAY** be redistributed |
| NFR-CMP-005 | Every framework mapping **MUST** record the source and version of the content it derives from |
| NFR-CMP-006 | Third-party licence obligations **MUST** be documented and satisfied in distribution |

### On NFR-CMP-001 and 002

This constrains the product in a way worth stating plainly rather than
discovering later. **ISO/IEC 27001 support is a mapping table of control
identifiers and nothing more** — the standard's text cannot be lawfully
reproduced. CIS content is free to use but restricted in redistribution.

Getting this right is itself a credibility signal: anyone familiar with the
standards landscape will notice, and anyone unfamiliar loses nothing.

---

## Summary of the constraints that shape the architecture

| Constraint | Architectural consequence |
|---|---|
| Offline operation (NFR-DEP-001) | No model in the assessment path; local inference for learning |
| Determinism (NFR-REL-001) | No model, no clock, no randomness in evaluation |
| Assessor independence (NFR-SEC-001) | No write path to devices exists, at any layer |
| Declarative knowledge (NFR-SEC-007) | Rulepacks are data; the expression language is restricted |
| No-code extensibility (NFR-MNT-001–003) | Three runtime-extensible knowledge layers |
| Performance at scale (NFR-PERF-001) | Deterministic engine; work is parsing and evaluation, not inference |
| Never over-claim (NFR-REL-009) | UNKNOWN is structural, produced by the `requires_facts` mechanism |
