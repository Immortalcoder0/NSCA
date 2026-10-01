# 03 · Functional Requirements

> **Convention:** **MUST** = mandatory · **SHOULD** = strongly expected, omission
> requires justification · **MAY** = optional.
> Every requirement is intended to be independently testable.
> Traceability to the problem statement: [17-traceability-matrix.md](17-traceability-matrix.md)

---

## FR-CMP · Campaigns and scope

| ID | Requirement |
|---|---|
| FR-CMP-001 | The system **MUST** support creating an audit **campaign** with a name, scope definition, selected frameworks and versions, owner, and assessment window |
| FR-CMP-002 | Every assessment, finding, and report **MUST** be associated with exactly one campaign |
| FR-CMP-003 | Scope **MUST** be definable as an explicit device list, an imported asset inventory, or a filter expression over device attributes (role, exposure, platform, location) |
| FR-CMP-004 | The system **MUST** support sampling within scope (e.g. "all internet-facing devices plus 10% of access layer") and record the sampling method used |
| FR-CMP-005 | A campaign **MUST** progress through explicit states: `Draft → Collecting → Assessing → Review → Issued → Closed` |
| FR-CMP-006 | Once a campaign is `Issued`, its assessment results **MUST** become immutable |
| FR-CMP-007 | The system **MUST** support comparing two campaigns and reporting the delta |
| FR-CMP-008 | Campaign delta **MUST** decompose movement into: configuration change, framework version change, scope change, and coverage change |
| FR-CMP-009 | The system **MUST** record which knowledge base versions (rulepacks, control packs, framework releases, engine) a campaign executed against |
| FR-CMP-010 | The system **SHOULD** support campaign templates for recurring audit cycles |

---

## FR-ING · Ingestion

| ID | Requirement |
|---|---|
| FR-ING-001 | The system **MUST** accept single-file upload of a device configuration |
| FR-ING-002 | The system **MUST** accept bulk upload — multiple files, directory structures, and archives |
| FR-ING-003 | The system **MUST** accept plain-text CLI configurations in all supported structural paradigms |
| FR-ING-004 | The system **MUST** accept XML configuration exports (e.g. PAN-OS) |
| FR-ING-005 | The system **MUST** accept structured cloud policy objects as JSON — AWS security groups and NACLs, Azure NSGs, GCP firewall rules |
| FR-ING-006 | The system **SHOULD** accept SASE / cloud-delivered policy exports (e.g. Zscaler, Cato) |
| FR-ING-007 | The system **MUST** accept `show tech-support` style diagnostic bundles and decompose them into constituent artifacts |
| FR-ING-008 | The system **MUST** support read-only live collection from reachable devices over SSH |
| FR-ING-009 | Live collection **MUST NOT** be capable of issuing any configuration-modifying command. This **MUST** be enforced architecturally, not by convention |
| FR-ING-010 | The system **MUST** correlate multiple artifacts belonging to one device (`running-config`, `show version`, `show inventory`) into a single device record |
| FR-ING-011 | Correlation **MUST** use hostname and/or serial number, and **MUST** flag ambiguous or conflicting correlations for human resolution |
| FR-ING-012 | Every ingested artifact **MUST** be hashed at receipt and stored immutably |
| FR-ING-013 | Every artifact **MUST** record chain-of-custody metadata: supplier, timestamp, source device, collection method |
| FR-ING-014 | The system **MUST** detect whether a supplied configuration is a verbose (complete) or terse (non-default-only) export, and report the consequence for coverage |
| FR-ING-015 | The system **MUST** report **collection completeness** against campaign scope: devices in scope, devices collected, devices missing |
| FR-ING-016 | Each uncollected in-scope device **MUST** be recorded with a reason and an owner, and **MUST** appear as a finding in the estate report |
| FR-ING-017 | The system **MUST** handle malformed input gracefully — truncation, mixed encodings, CRLF, non-UTF8 — without aborting a bulk job |
| FR-ING-018 | The system **SHOULD** detect and flag configurations in which secrets appear to have been redacted by the supplier |

---

## FR-FPR · Fingerprinting

| ID | Requirement |
|---|---|
| FR-FPR-001 | The system **MUST** determine vendor, platform, operating system version, model and serial numbers where determinable |
| FR-FPR-002 | Fingerprinting **MUST** distinguish platforms within a vendor (Cisco IOS vs IOS-XE vs NX-OS vs IOS-XR) |
| FR-FPR-003 | Fingerprinting **MUST** produce a confidence score and **MUST** surface low-confidence identifications for confirmation |
| FR-FPR-004 | The system **MUST** distinguish three outcomes: known platform, identifiable but untaught, wholly unknown |
| FR-FPR-005 | The system **MUST** perform version-based vulnerability lookup using the fingerprint alone, without requiring successful parsing |
| FR-FPR-006 | When a platform is later taught, previously ingested artifacts of that platform **MUST** become retrospectively assessable |

---

## FR-PRS · Parsing

| ID | Requirement |
|---|---|
| FR-PRS-001 | The system **MUST** parse indentation-hierarchy configurations (Cisco-family, Arista) |
| FR-PRS-002 | The system **MUST** parse flat path-statement configurations (Juniper set-format) |
| FR-PRS-003 | The system **MUST** parse brace-nested configurations (Juniper curly-format) |
| FR-PRS-004 | The system **MUST** parse block-keyword configurations (FortiOS `config`/`end`, `edit`/`next`) |
| FR-PRS-005 | The system **MUST** parse XML configurations (PAN-OS) |
| FR-PRS-006 | The system **MUST** parse path-header key-value configurations (MikroTik RouterOS) |
| FR-PRS-007 | The system **MUST** parse natively structured cloud policy objects |
| FR-PRS-008 | The parser **MUST** produce a typed tree in which every node retains its source line range |
| FR-PRS-009 | The system **MUST** compute the **effective configuration**, resolving inheritance and override — PAN-OS device-group/template merge, Juniper `apply-groups`, Cisco overlapping `line vty` ranges, FortiOS VDOM scoping |
| FR-PRS-010 | Any fact derived from an inherited layer **MUST** record which layer produced it |
| FR-PRS-011 | The system **MUST** handle command abbreviation where a platform emits abbreviated forms |
| FR-PRS-012 | For an unknown platform, the system **MUST** attempt automatic **grammar inference** — comment character, hierarchy paradigm, statement shape, verb set |
| FR-PRS-013 | Grammar inference **MUST** report its coverage: proportion of input lines successfully assigned to a grammar production |
| FR-PRS-014 | Lines not covered by any grammar production **MUST** be retained and routed to the learning queue, never silently discarded |

---

## FR-EXT · Fact extraction

| ID | Requirement |
|---|---|
| FR-EXT-001 | The system **MUST** convert parse-tree nodes into facts conforming to the Security Baseline Model |
| FR-EXT-002 | Every fact **MUST** carry provenance: source classification, artifact identifier, line range, extractor identifier and version, confidence |
| FR-EXT-003 | The system **MUST** support the provenance source classifications: `explicit`, `default_known`, `default_inferred`, `inherited`, `default_unknown`, `not_applicable` |
| FR-EXT-004 | Facts absent from configuration **MUST** be resolved against a version-keyed defaults table where one exists |
| FR-EXT-005 | Where no default is known, the fact **MUST** be classified `default_unknown` and **MUST NOT** be assigned a value |
| FR-EXT-006 | The system **MUST** infer platform capability surface from the fleet: a setting expressed by any device of a platform establishes that the concept exists on that platform |
| FR-EXT-007 | The system **MUST** detect and report conflicts where two extractors produce different values for the same fact on the same device |
| FR-EXT-008 | Extraction **MUST** be deterministic and **MUST NOT** invoke any model at assessment time |
| FR-EXT-009 | Parse-tree constructs matched by no extractor **MUST** be routed to the learning queue with their frequency and section context |
| FR-EXT-010 | The system **MUST** support extensible fact paths so that a newly discovered capability can be represented without a schema code change |

---

## FR-GRF · Configuration graph

| ID | Requirement |
|---|---|
| FR-GRF-001 | The system **MUST** construct a graph of configuration objects and their relationships across all devices in a campaign |
| FR-GRF-002 | The graph **MUST** represent at minimum: devices, interfaces, zones, access rules, address objects, service objects, users, routes |
| FR-GRF-003 | The system **MUST** transitively expand nested object groups and detect over-broad membership (e.g. a group transitively containing `0.0.0.0/0`) |
| FR-GRF-004 | The system **MUST** support reachability queries across the graph, including multi-device paths |
| FR-GRF-005 | Every graph-derived finding **MUST** emit a concrete **counterexample** — a specific source, destination, port and protocol — together with the rule chain that permits it |
| FR-GRF-006 | The system **MUST** compute a device **exposure classification** from graph position |
| FR-GRF-007 | The system **MUST** detect emergent violations in which no individual configuration statement is non-compliant |
| FR-GRF-008 | The graph **MUST** be usable to verify claimed compensating controls (see FR-FND-011) |

---

## FR-CTL · Control evaluation

| ID | Requirement |
|---|---|
| FR-CTL-001 | The system **MUST** evaluate **native controls** — vendor-neutral assertions over the Security Baseline Model |
| FR-CTL-002 | Native controls **MUST** be stored as declarative data, not code, and **MUST** be addable without redeployment |
| FR-CTL-003 | Every control **MUST** declare the facts it requires |
| FR-CTL-004 | The system **MUST** produce four verdicts: `PASS`, `FAIL`, `UNKNOWN`, `NOT_APPLICABLE` |
| FR-CTL-005 | A control whose required facts are missing or classified `default_unknown` **MUST** return `UNKNOWN`. It **MUST NOT** return `PASS` |
| FR-CTL-006 | `NOT_APPLICABLE` **MUST** be excluded from the compliance denominator |
| FR-CTL-007 | The system **MUST** compute a **coverage score** per device: proportion of applicable controls actually determined |
| FR-CTL-008 | The system **MUST** classify each `PASS` as **meaningful** (feature present and securely configured) or **vacuous** (feature absent or disabled) and report both figures |
| FR-CTL-009 | Where a device exposes a capability assessed by no control in a family, every `PASS` in that family **MUST** be downgraded to `PASS (PARTIAL)` with the reason recorded |
| FR-CTL-010 | The system **MUST** support evaluation against multiple frameworks simultaneously, with each control result reported under every mapped framework identifier |
| FR-CTL-011 | The system **MUST** record the exact framework version used for each evaluation |
| FR-CTL-012 | Where two selected frameworks impose conflicting requirements, the system **MUST** apply the stricter and **MUST** report the conflict |
| FR-CTL-013 | Controls **MUST** support applicability clauses restricting them by platform family, version range, or device capability |
| FR-CTL-014 | The system **MUST** support **property-derived controls** applying to any capability characterised by universal security properties (listens, authenticates, executes, mutates, transports, persists, default-on) |
| FR-CTL-015 | The system **MUST** publish an **automation coverage manifest** per framework: total recommendations, automated, requiring manual assessment, requiring uncollected data, not yet implemented |
| FR-CTL-016 | For each framework item, the system **SHOULD** record the equivalence rationale between the framework's stated audit procedure and the platform's automated check |
| FR-CTL-017 | Control evaluation **MUST** be deterministic and **MUST NOT** invoke any model |

---

## FR-RSK · Risk and prioritisation

| ID | Requirement |
|---|---|
| FR-RSK-001 | Every finding **MUST** carry a base severity from its control and an effective severity after contextual modification |
| FR-RSK-002 | Effective severity **MUST** be modulated by device exposure derived from the graph |
| FR-RSK-003 | The system **MUST** compute **attack paths** — ordered chains of findings that together enable reachability from an untrusted zone to a protected asset |
| FR-RSK-004 | The system **MUST** identify, for each attack path, the lowest-cost finding whose remediation breaks the chain |
| FR-RSK-005 | The system **MUST** produce a prioritised remediation list stating how many findings become unreachable if the listed items are resolved |
| FR-RSK-006 | The system **MUST** perform **peer anomaly detection** — identifying devices whose configuration deviates from structurally similar peers |
| FR-RSK-007 | Peer anomaly detection **MUST** function without semantic understanding, so that it produces findings on platforms not yet taught |
| FR-RSK-008 | The system **MUST** identify **systemic findings** — the same defect across many devices — and report them as a single root cause with an affected-device list |
| FR-RSK-009 | The system **MUST** perform version-based vulnerability correlation and report known vulnerabilities affecting the identified firmware |
| FR-RSK-010 | The system **MUST** distinguish and separately report **compliance posture** and **security posture**, and explain divergence between them |

---

## FR-REM · Remediation

| ID | Requirement |
|---|---|
| FR-REM-001 | Every `FAIL` finding **MUST** produce device-specific remediation as an executable command sequence in that platform's syntax |
| FR-REM-002 | Remediation **MUST** be selected by `(control, platform, os_version_range)` |
| FR-REM-003 | Where no remediation exists for the specific version, the system **MUST** state this rather than emit an approximate sequence |
| FR-REM-004 | Remediation steps **MUST** be ordered to respect dependencies (e.g. central authentication configured and verified before local fallback removal) |
| FR-REM-005 | Each step **MUST** carry an impact classification: `safe`, `service-affecting`, `lockout-risk` |
| FR-REM-006 | The system **MUST** perform **lockout detection** — evaluating whether a proposed management access restriction would deny the assessor's or administrator's own source address — and **MUST** block or prominently warn |
| FR-REM-007 | Each step **MUST** provide a rollback command sequence |
| FR-REM-008 | The system **MUST** provide a **dry run** applying remediation to the model, re-evaluating, and reporting the resulting compliance and coverage change |
| FR-REM-009 | The dry run **MUST** identify any control that would newly fail as a consequence of the remediation |
| FR-REM-010 | The system **MUST NOT** apply remediation to any device under any circumstances |
| FR-REM-011 | The system **MAY** export a signed remediation patch bundle for the network team's own change process |

---

## FR-LRN · Learning subsystem

| ID | Requirement |
|---|---|
| FR-LRN-001 | When an unrecognised configuration structure is encountered, the system **MUST** open an interactive training workflow rather than failing or silently ignoring it |
| FR-LRN-002 | The training interface **MUST** be usable by a network administrator with no programming experience |
| FR-LRN-003 | The system **MUST** collapse unrecognised lines into templates by abstracting variable tokens, so that thousands of lines produce tens of questions |
| FR-LRN-004 | The system **MUST** rank templates by relevance to the fact set required by loaded controls, and **MUST** suppress compliance-irrelevant templates |
| FR-LRN-005 | The system **MUST** order questions by expected information gain — how many undetermined controls each would resolve |
| FR-LRN-006 | The system **MUST** propose candidate mappings before asking, using lexical similarity to known facts, structural analogy to known platforms, and value-shape analysis |
| FR-LRN-007 | The system **MUST** detect negated keys and **MUST** surface polarity as an explicit, separately confirmable statement |
| FR-LRN-008 | The interaction **MUST** be confirmation-oriented: the administrator confirms, corrects, or rejects a proposal rather than authoring a rule |
| FR-LRN-009 | Confirmation **MUST** synthesise a deterministic extraction rule |
| FR-LRN-010 | Before a synthesised rule is accepted, the system **MUST** run it against the source artifact and display every line it matches |
| FR-LRN-011 | Before acceptance, the system **MUST** run the rule against the whole corpus and reject or require narrowing if it matches artifacts of other platforms |
| FR-LRN-012 | Before acceptance, the system **MUST** detect conflicts with existing rules producing the same fact |
| FR-LRN-013 | Confirmed examples **MUST** be frozen as regression tests attached to the rule |
| FR-LRN-014 | A synthesised rule **MUST** be marked `provisional` until ratified |
| FR-LRN-015 | Rulepack changes **MUST** require ratification by a second authorised user before use in an issued report (two-person rule) |
| FR-LRN-016 | Findings derived from provisional rules **MUST** be flagged and **MUST** be excluded from issued reports |
| FR-LRN-017 | Every taught rule **MUST** record who taught it, who ratified it, when, and against which examples |
| FR-LRN-018 | Rulepacks **MUST** be versioned and revertible |
| FR-LRN-019 | Learning **MUST** be represented as data. The system **MUST NOT** require model retraining or weight updates to support a new platform |
| FR-LRN-020 | The system **MUST** apply cross-platform transfer, using knowledge from previously taught platforms to improve proposals for new ones |
| FR-LRN-021 | The system **MUST** record and report the number of human confirmations required per platform, enabling a learning-effort curve |
| FR-LRN-022 | Rulepacks **MUST** be exportable and importable as signed bundles |
| FR-LRN-023 | Imported rulepacks **MUST** be verified, marked with their trust tier, and validated against the local corpus before use |
| FR-LRN-024 | Rulepacks **MUST** be declarative data and **MUST NOT** be capable of arbitrary code execution |
| FR-LRN-025 | The system **MUST** support the same training workflow for authoring platform rulepacks shipped with the product — there **MUST NOT** be a separate authoring mechanism |
| FR-LRN-026 | When a discovered capability matches no existing control, the system **MUST** report it as **unaudited surface** and **SHOULD** propose applicable property-derived controls |
| FR-LRN-027 | Where model assistance is used, a **local inference** mode **MUST** be available so that no configuration content leaves the deployment |
| FR-LRN-028 | Content sent to any model **MUST** have secrets, hashes and credentials redacted first |

---

## FR-FND · Findings and lifecycle

| ID | Requirement |
|---|---|
| FR-FND-001 | Every finding **MUST** reference the control, verdict, effective severity, evidence, and framework mappings |
| FR-FND-002 | Evidence **MUST** identify the artifact and the specific line range, and **MUST** include the surrounding configuration excerpt |
| FR-FND-003 | Findings **MUST** progress through explicit states: `New → Confirmed → Assigned → Remediated → Verified → Closed`, with `Disputed` and `Risk Accepted` branches |
| FR-FND-004 | Every state transition **MUST** record actor, timestamp and reason |
| FR-FND-005 | A finding **MUST** be assignable to an owner with a due date |
| FR-FND-006 | An administrator **MUST** be able to dispute a finding with a stated reason |
| FR-FND-007 | Disputes **MUST** be adjudicated by an authorised assessor, with the decision and rationale recorded |
| FR-FND-008 | The system **MUST** support **risk acceptance** with an owner, justification, expiry date, and required compensating control |
| FR-FND-009 | An accepted risk **MUST** automatically reopen on expiry |
| FR-FND-010 | Reports **MUST** distinguish passing, failing, and accepted-risk states rather than collapsing accepted risk into either |
| FR-FND-011 | Where a compensating control is claimed, the system **MUST** attempt to **verify it against the configuration graph** and report `CONFIRMED`, `REFUTED` (with counterexample), or `UNVERIFIABLE` (with reason) |
| FR-FND-012 | Compensating control verification **MUST** state its assumptions, including the effect of uncollected devices |
| FR-FND-013 | The system **MUST** support remediation verification: re-collect, re-assess, and confirm that the specific finding now passes |
| FR-FND-014 | A finding claimed as remediated but not confirmed by re-assessment **MUST** return to `Assigned` with a note |
| FR-FND-015 | Assessors **MUST** be able to attach attributable, timestamped notes to any finding |
| FR-FND-016 | The system **MUST** track findings across campaigns so that recurrence, regression and closure are visible |

---

## FR-RPT · Reporting

| ID | Requirement |
|---|---|
| FR-RPT-001 | The system **MUST** generate a single comprehensive PDF report per device |
| FR-RPT-002 | The report **MUST** include device identification: hostname, vendor, platform, model, **serial numbers**, OS version, role and exposure |
| FR-RPT-003 | Where serial numbers cannot be determined, the report **MUST** state this explicitly rather than omit the section |
| FR-RPT-004 | The report **MUST** present clear pass/fail results with risk severity assessments |
| FR-RPT-005 | The report **MUST** present device-specific, step-by-step CLI remediation sequences |
| FR-RPT-006 | Remediation content **MUST** be customised to the device's specific model and software version |
| FR-RPT-007 | Every finding in the report **MUST** show its evidence excerpt with line numbers |
| FR-RPT-008 | The report **MUST** include compliance score, **coverage score**, and meaningful-versus-vacuous pass breakdown |
| FR-RPT-009 | The report **MUST** include a prioritised top-N remediation list ranked by attack-path contribution |
| FR-RPT-010 | The report **MUST** include an **unassessed** section listing every UNKNOWN with its reason, and every unaudited capability |
| FR-RPT-011 | The report **MUST** state every framework and framework version evaluated against |
| FR-RPT-012 | The report **MUST** state the trust tier of every rulepack used |
| FR-RPT-013 | The report **MUST** carry a reproducibility manifest — hashes of inputs and versions of all knowledge base components |
| FR-RPT-014 | The system **MUST** generate an estate-level report covering collection completeness, posture distribution, systemic findings, and remediation progress |
| FR-RPT-015 | The estate report **MUST** report systemic findings as a single root cause with an affected-device list |
| FR-RPT-016 | The system **MUST** support campaign comparison reporting with delta decomposition |
| FR-RPT-017 | The system **MUST** export findings in machine-readable form (JSON, CSV) |
| FR-RPT-018 | The system **SHOULD** export assessment results in NIST OSCAL assessment-results format |
| FR-RPT-019 | The system **SHOULD** export an editable document format in addition to PDF |
| FR-RPT-020 | Report generation **MUST** be deterministic — identical inputs produce byte-identical documents |
| FR-RPT-021 | Issued reports **MUST** be immutable; corrections **MUST** be issued as linked amendments |

---

## FR-INT · Audit integrity

| ID | Requirement |
|---|---|
| FR-INT-001 | The system **MUST** produce byte-identical findings for identical inputs and knowledge base versions |
| FR-INT-002 | Every report **MUST** carry a reproducibility manifest sufficient to re-execute the assessment exactly |
| FR-INT-003 | The system **MUST** support re-executing a historical campaign and verifying that the result matches its manifest |
| FR-INT-004 | All ingested artifacts **MUST** be stored immutably with their receipt hash |
| FR-INT-005 | The system **MUST** maintain a complete, attributable audit log of every user action affecting an assessment or its adjudication |
| FR-INT-006 | The audit log **MUST** be append-only and **MUST NOT** be editable through the application |
| FR-INT-007 | The system **MUST** be architecturally incapable of modifying an audited device |
| FR-INT-008 | Assessment **MUST** complete with no external network access |
| FR-INT-009 | The system **MUST NOT** treat text within configuration files as instructions under any circumstances |
| FR-INT-010 | Knowledge base updates **MUST** be reviewable, with quantified impact against the existing estate, before ratification |
| FR-INT-011 | The system **MUST** record which framework version each campaign used, enabling separation of posture change from standard change |
| FR-INT-012 | Offline knowledge base bundles **MUST** be signed and verified on import |

---

## FR-UIX · User interface

| ID | Requirement |
|---|---|
| FR-UIX-001 | The system **MUST** provide a dashboard for uploading single or bulk configuration files |
| FR-UIX-002 | The system **MUST** provide an estate view showing all devices in a campaign with posture, coverage and status |
| FR-UIX-003 | The system **MUST** provide a device detail view with findings, evidence, remediation and history |
| FR-UIX-004 | Clicking a finding **MUST** display the underlying configuration excerpt with the relevant lines highlighted |
| FR-UIX-005 | The system **MUST** provide a dedicated **Training Studio** for teaching unseen platform formats |
| FR-UIX-006 | The Training Studio **MUST** present questions one at a time, ordered by information gain, with progress and estimated completion |
| FR-UIX-007 | The Training Studio **MUST** show the effect of each confirmation on coverage before and after |
| FR-UIX-008 | The system **MUST** provide a finding workbench supporting triage, assignment, dispute and adjudication in bulk |
| FR-UIX-009 | The system **MUST** provide framework selection at campaign level |
| FR-UIX-010 | The system **MUST** provide rulepack administration showing version, trust tier, coverage and authorship |
| FR-UIX-011 | The system **MUST** provide full-text search across the artifact and finding repository |
| FR-UIX-012 | The system **SHOULD** provide graph visualisation for attack paths and reachability counterexamples |

---

## FR-ADM · Administration

| ID | Requirement |
|---|---|
| FR-ADM-001 | The system **MUST** enforce role-based access control |
| FR-ADM-002 | The system **MUST** define at minimum the roles: Assessor, Lead Assessor, Network Administrator, Platform Administrator, Read-only |
| FR-ADM-003 | Only Lead Assessors **MUST** be able to issue a campaign |
| FR-ADM-004 | Rulepack ratification **MUST** require a different user from the one who authored the change |
| FR-ADM-005 | The system **MUST** support secure authentication, and **SHOULD** support enterprise identity integration |
| FR-ADM-006 | Collection credentials **MUST** be stored encrypted and **MUST NOT** be retrievable through the interface |
| FR-ADM-007 | The system **MUST** support importing framework content releases and previewing their estate impact before ratification |
| FR-ADM-008 | The system **MUST** report knowledge base freshness — current versus available content versions |
| FR-ADM-009 | The system **MUST** support data retention policies for artifacts and campaigns consistent with audit record requirements |
| FR-ADM-010 | The system **MUST** operate fully in an air-gapped deployment, with knowledge base updates delivered as signed offline bundles |

---

## FR-API · Interface surface

| ID | Requirement |
|---|---|
| FR-API-001 | The system **MUST** expose an authenticated API covering campaign, ingestion, assessment, findings and reporting |
| FR-API-002 | The API **MUST** support bulk artifact submission |
| FR-API-003 | The API **MUST** support retrieval of findings in machine-readable form |
| FR-API-004 | The API **MUST NOT** expose any capability to modify an audited device |
| FR-API-005 | The API **SHOULD** support webhook notification on campaign and finding state transitions |
| FR-API-006 | All API actions **MUST** be recorded in the audit log with the acting identity |

---

## Requirement summary

| Area | Count | Notes |
|---|---|---|
| Campaigns | 10 | Audit engagement model |
| Ingestion | 18 | Includes cloud JSON and multi-artifact correlation |
| Fingerprinting | 6 | Includes pre-parse vulnerability lookup |
| Parsing | 14 | Six structural paradigms plus grammar inference |
| Extraction | 10 | Provenance model is the core |
| Graph | 8 | Counterexamples are mandatory |
| Control evaluation | 17 | Four verdicts, coverage, vacuity, contamination |
| Risk | 10 | Attack paths, peer anomaly, systemic findings |
| Remediation | 11 | Safety before correctness |
| Learning | 28 | The largest area — the problem statement's hardest demand |
| Findings | 16 | Full audit lifecycle |
| Reporting | 21 | The mandated deliverable |
| Integrity | 12 | Defensibility |
| Interface | 12 | |
| Administration | 10 | |
| API | 6 | |
| **Total** | **209** | |
