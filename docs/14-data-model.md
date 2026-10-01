# 14 · Data Model

> Entities and their relationships. This is a conceptual model, not a physical
> schema — it defines what must be represented and how the pieces relate.

---

## 1. Entity overview

```
                        ┌──────────────┐
                        │   CAMPAIGN   │
                        └──────┬───────┘
                               │ 1:N
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
  ┌───────────┐        ┌──────────────┐       ┌──────────────┐
  │  DEVICE   │◄───────│  ASSESSMENT  │──────►│    REPORT    │
  └─────┬─────┘  1:N   └──────┬───────┘  1:N  └──────────────┘
        │                     │
        │ 1:N                 │ 1:N
        ▼                     ▼
  ┌───────────┐        ┌──────────────┐
  │ ARTIFACT  │        │   FINDING    │
  └───────────┘        └──────┬───────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
       ┌────────────┐  ┌────────────┐  ┌──────────────┐
       │  EVIDENCE  │  │  DISPUTE   │  │ REMEDIATION  │
       └────────────┘  └────────────┘  └──────────────┘

  KNOWLEDGE BASE (versioned, campaign-pinned)
  ┌──────────┐ ┌─────────────┐ ┌──────────┐ ┌───────────────┐
  │ RULEPACK │ │ CONTROL PACK│ │  SCHEMA  │ │FRAMEWORK PACK │
  └────┬─────┘ └──────┬──────┘ │ REGISTRY │ └───────┬───────┘
       │              │        └────┬─────┘         │
       ▼              ▼             ▼               ▼
  ┌───────────┐ ┌───────────┐ ┌──────────┐  ┌──────────────┐
  │ EXTRACTOR │ │  CONTROL  │ │   FACT   │  │FRAMEWORK ITEM│
  └───────────┘ └───────────┘ │DEFINITION│  └──────────────┘
                              └──────────┘
```

---

## 2. Assessment entities

### CAMPAIGN

The audit engagement. Everything is anchored to one.

| Field | Type | Notes |
|---|---|---|
| `id` | identifier | |
| `name` | string | |
| `scope_definition` | object | Explicit list, inventory reference, or filter expression |
| `scope_devices[]` | ref[] | Resolved device list |
| `sampling_method` | object | Recorded if scope is sampled |
| `frameworks[]` | object[] | `{framework, version}` — **pinned** |
| `owner` | ref(User) | |
| `window_start`, `window_end` | timestamp | |
| `state` | enum | `Draft`, `Collecting`, `Assessing`, `Review`, `Issued`, `Closed` |
| `knowledge_base_pin` | object | Exact versions of engine, schema, rulepacks, control packs, framework packs |
| `previous_campaign` | ref(Campaign) | For delta comparison |

**Invariant:** once `state = Issued`, assessment results and `knowledge_base_pin`
are immutable.

---

### DEVICE

| Field | Type | Notes |
|---|---|---|
| `id` | identifier | Stable across campaigns |
| `hostname` | string | |
| `platform` | ref(Platform) | |
| `os_version` | version | |
| `model` | string | |
| `serials[]` | object[] | `{component, serial}` |
| `role` | enum | |
| `exposure` | enum | **Derived from graph**, per campaign |
| `location` | string | |
| `first_seen`, `last_assessed` | timestamp | |

Device identity persists across campaigns; assessments do not.

---

### ARTIFACT

Evidence. Immutable from receipt.

| Field | Type | Notes |
|---|---|---|
| `id` | identifier | |
| `device` | ref(Device) | Null until correlated |
| `campaign` | ref(Campaign) | |
| `filename` | string | |
| `content_hash` | sha256 | Computed at receipt, before processing |
| `size_bytes` | integer | |
| `artifact_type` | enum | `running_config`, `show_version`, `show_inventory`, `cloud_policy`, `tech_support_bundle`, `unknown` |
| `export_mode` | enum | `verbose`, `terse`, `unknown` |
| `received_at` | timestamp | |
| `received_from` | enum | `upload`, `live_collection`, `bundle_extraction` |
| `supplied_by` | ref(User) | For manual upload |
| `collector` | string | For live collection |
| `source_address` | string | |
| `collection_method` | string | |
| `parent_artifact` | ref(Artifact) | When extracted from a bundle |

**Invariants:** never modified in place; re-collection creates a new artifact.

---

### ASSESSMENT

One execution of the pipeline against one device in one campaign.

| Field | Type | Notes |
|---|---|---|
| `id` | identifier | |
| `campaign`, `device` | ref | |
| `artifacts[]` | ref[] | Everything correlated into this assessment |
| `executed_at` | timestamp | |
| `fingerprint_confidence` | float | |
| `grammar_coverage` | float | Proportion of lines parsed |
| `facts[]` | Fact[] | The Security Baseline Model instance |
| `compliance_score`, `coverage_score`, `meaningful_ratio`, `security_score` | ratio | Stored as exact fractions |
| `counts` | object | `{pass, fail, unknown, not_applicable, partial}` |
| `rulepacks_used[]` | object[] | `{rulepack, version, trust_tier}` |
| `unmatched_constructs[]` | object[] | Routed to the learning queue |

---

### FACT

The atomic unit of the Security Baseline Model. Detailed in
[05-security-baseline-model.md](05-security-baseline-model.md).

| Field | Type | Notes |
|---|---|---|
| `assessment` | ref | |
| `path` | string | Dotted namespace address |
| `value` | any | Typed per the schema registry |
| `provenance.source` | enum | `explicit`, `default_known`, `default_inferred`, `inherited`, `default_unknown`, `not_applicable`, `derived` |
| `provenance.artifact` | ref(Artifact) | |
| `provenance.lines[]` | integer[] | |
| `provenance.excerpt` | string | |
| `provenance.extractor` | ref | Extractor and version |
| `provenance.layer` | string | Populated when `inherited` |
| `provenance.depends_on[]` | string[] | Populated when `derived` |
| `provenance.confidence` | float | |

**Invariant:** a derived fact's provenance is the **weakest** of its inputs.
Uncertainty propagates.

---

### FINDING

| Field | Type | Notes |
|---|---|---|
| `id` | identifier | |
| `campaign`, `device`, `assessment` | ref | |
| `control` | ref(Control) | |
| `verdict` | enum | `PASS`, `FAIL`, `UNKNOWN`, `NOT_APPLICABLE`, `PASS_PARTIAL` |
| `pass_quality` | enum | `meaningful`, `vacuous` — when verdict is PASS |
| `unknown_reason` | enum | `facts_missing`, `default_unknown`, `parse_gap`, `export_incomplete`, `data_not_collected` |
| `severity_base`, `severity_effective` | enum | |
| `severity_reason` | string | Why it was modified |
| `evidence[]` | Evidence[] | |
| `framework_refs[]` | object[] | `{framework, id, version}` |
| `attack_paths[]` | ref[] | |
| `contamination_reason` | string | When `PASS_PARTIAL` |
| `rulepack_trust_tier` | enum | Propagated for reporting |
| `state` | enum | See [09](09-findings-lifecycle.md) |
| `owner`, `due_date` | | |
| `identity_key` | string | `(device, control)` — enables cross-campaign tracking |

**`identity_key`** is what makes recurrence, regression and ageing computable
across campaigns.

---

### EVIDENCE

| Field | Type |
|---|---|
| `artifact` | ref(Artifact) |
| `lines[]` | integer[] |
| `highlight_lines[]` | integer[] |
| `excerpt` | string — verbatim, with secrets masked |
| `facts[]` | ref(Fact)[] |
| `counterexample` | object — for graph findings |

The `counterexample` object:

```yaml
packet: { src, sport, dst, dport, protocol }
path:
  - { node, device, artifact_lines, action, note }
```

---

## 3. Lifecycle entities

### FINDING_TRANSITION

Append-only.

| Field | Type |
|---|---|
| `finding` | ref |
| `from_state`, `to_state` | enum |
| `actor` | ref(User) |
| `at` | timestamp |
| `reason` | string |

---

### DISPUTE

| Field | Type | Notes |
|---|---|---|
| `finding` | ref | |
| `raised_by`, `raised_at` | | |
| `type` | enum | `false_positive`, `compensating_control`, `not_applicable`, `accepted_risk`, `already_remediated` |
| `claim` | string | |
| `verification` | object | See below |
| `adjudicated_by`, `adjudicated_at` | | |
| `decision` | enum | `upheld`, `rejected`, `converted_to_risk_acceptance` |
| `rationale` | string | |

**`verification`** — machine verification of a claimed compensating control:

| Field | Type |
|---|---|
| `result` | enum — `CONFIRMED`, `REFUTED`, `UNVERIFIABLE` |
| `counterexample` | object — when REFUTED |
| `assumptions[]` | string[] |
| `confidence` | enum |
| `devices_considered`, `devices_missing` | integer |

---

### RISK_ACCEPTANCE

| Field | Type | Notes |
|---|---|---|
| `finding` | ref | |
| `accepted_by` | ref(User) | **Must be a Lead Assessor** |
| `accepted_at`, `expires_at` | timestamp | **Expiry mandatory** |
| `justification` | string | |
| `compensating_control` | object | Claim plus verification result |
| `auto_reopened_at` | timestamp | Set when expiry triggers |

---

### REMEDIATION_PLAN

| Field | Type |
|---|---|
| `finding` | ref |
| `platform`, `version_range` | |
| `steps[]` | Step[] |
| `lockout_analysis` | object |
| `dry_run_result` | object |
| `prerequisites[]` | ref(Control)[] |

**Step:**

| Field | Type |
|---|---|
| `order` | integer |
| `command` | string |
| `impact` | enum — `safe`, `service_affecting`, `lockout_risk` |
| `reason` | string |
| `rollback` | string |
| `depends_on_step` | integer |

**`dry_run_result`:**

| Field | Type |
|---|---|
| `compliance_before`, `compliance_after` | ratio |
| `findings_resolved[]` | ref[] |
| `findings_newly_failing[]` | ref[] |

---

### VERIFICATION

| Field | Type | Notes |
|---|---|---|
| `finding` | ref | |
| `artifact_before`, `artifact_after` | ref | |
| `verdict_before`, `verdict_after` | enum | |
| `knowledge_base_identical` | boolean | **Must be true for the comparison to be valid** |
| `result` | enum | `verified`, `not_remediated`, `now_unknown` |

---

## 4. Knowledge base entities

All are versioned, signable, diffable and revertible.

### RULEPACK

| Field | Type |
|---|---|
| `id`, `version` | |
| `platform` | ref(Platform) |
| `trust_tier` | enum — `certified`, `verified_community`, `local`, `provisional` |
| `fingerprint_signatures[]` | |
| `grammar` | object |
| `extractors[]` | ref[] |
| `defaults[]` | Default[] |
| `inheritance_rules` | object |
| `quirks` | object |
| `signature` | |
| `authored_by`, `ratified_by`, `ratified_at` | |
| `corpus_statistics` | object |

### EXTRACTOR

| Field | Type |
|---|---|
| `id`, `version` | |
| `rulepack` | ref |
| `scope` | object |
| `match_pattern` | string |
| `emits[]` | object[] — `{fact_path, value_expression}` |
| `tests[]` | Test[] — frozen from confirmed examples |
| `status` | enum — `provisional`, `ratified`, `deprecated` |
| `taught_by`, `taught_at`, `source_artifact`, `confirmed_examples` | |

### DEFAULT

| Field | Type |
|---|---|
| `rulepack` | ref |
| `fact_path` | string |
| `version_range` | string |
| `value` | any |
| `condition` | string — optional |
| `source` | string — e.g. *"CIS Benchmark Default Value"* |

### FACT_DEFINITION (schema registry)

| Field | Type |
|---|---|
| `path`, `type`, `category`, `description` | |
| `properties` | object — universal security properties |
| `enumeration_values[]` | — for closed enums |
| `registered_by`, `registered_at`, `introduced_by_platform` | |

### CONTROL

| Field | Type |
|---|---|
| `id`, `version`, `title`, `description`, `family` | |
| `severity_base`, `materiality` | |
| `applies_to` | object |
| `requires_facts[]` | string[] |
| `assert_expression` | string |
| `vacuity_expression` | string |
| `risk_modifiers[]` | object[] |
| `remediation_templates[]` | ref[] |
| `tests[]` | |

### FRAMEWORK_ITEM

| Field | Type |
|---|---|
| `framework` | enum — `cis`, `nist`, `stig`, `iso` |
| `benchmark`, `version` | |
| `item_id` | string — e.g. `V-216644` |
| `title`, `severity` | |
| `stated_audit_procedure` | string |
| `satisfied_by[]` | ref(Control)[] |
| `equivalence_rationale` | string |
| `automation_status` | enum — `automated`, `manual_only`, `data_unavailable`, `not_implemented` |
| `text_redistributable` | boolean — **false for CIS and ISO** |

**`text_redistributable`** enforces the licensing constraint at the data layer:
where false, only the identifier is stored and rendered.

---

## 5. Graph entities

Constructed per campaign, not persisted as primary data.

**GRAPH_NODE** — `{campaign, node_type, identifier, device, attributes, source_facts[]}`

Node types: `device`, `interface`, `zone`, `acl`, `acl_rule`, `address_object`,
`service_object`, `user`, `route`, `vlan`, `vrf`, `service`

**GRAPH_EDGE** — `{campaign, from_node, to_node, edge_type, attributes}`

Edge types: `applied_to`, `member_of`, `permits`, `denies`, `references`,
`in_zone`, `routes_to`, `authenticates_via`, `inherits_from`

### ATTACK_PATH

| Field | Type |
|---|---|
| `id`, `campaign` | |
| `source_zone`, `target_asset` | |
| `links[]` | object[] — `{finding, node, role}` |
| `weakest_link` | ref(Finding) |
| `remediation_cost` | object |
| `findings_made_unreachable[]` | ref[] |

### SYSTEMIC_FINDING

| Field | Type |
|---|---|
| `id`, `campaign`, `control` | |
| `affected_devices[]` | ref[] |
| `evidence_pattern` | string — the normalised common pattern |
| `root_cause_hypothesis` | string |
| `commissioning_window` | object — correlating evidence |

---

## 6. Administration entities

### USER
`{id, identity, display_name, roles[], active}`

### ROLE
`Assessor` · `Lead Assessor` · `Network Administrator` · `Platform Administrator`
· `Read-only`

### AUDIT_LOG_ENTRY

Append-only, not editable through the application.

| Field | Type |
|---|---|
| `at`, `actor`, `action`, `entity_type`, `entity_id` | |
| `details` | object |
| `previous_entry_hash` | sha256 — **hash-chained for tamper evidence** |

The hash chain means audit history cannot be silently rewritten — a hash chain
used for the reason hash chains exist.

### COLLECTION_CREDENTIAL

| Field | Type | Notes |
|---|---|---|
| `id`, `name`, `platform_scope` | | |
| `encrypted_material` | | **Never retrievable through any interface** |
| `read_only_verified` | boolean | Deployment prerequisite check |

### REPORT

| Field | Type |
|---|---|
| `id`, `campaign`, `device`, `report_type` | |
| `generated_at`, `generated_by` | |
| `content_hash`, `reproducibility_manifest` | |
| `state` | enum — `draft`, `issued`, `superseded` |
| `amends` | ref(Report) — for amendments |

---

## 7. Key invariants

| # | Invariant | Enforced where |
|---|---|---|
| DM-1 | An artifact is never modified after receipt | Storage layer |
| DM-2 | An issued campaign's results and knowledge pin are immutable | Application layer |
| DM-3 | A derived fact's provenance is the weakest of its inputs | Extraction |
| DM-4 | A finding whose control has a missing required fact **cannot** be PASS | Control engine |
| DM-5 | A finding from a provisional rulepack cannot appear in an issued report | Report generation |
| DM-6 | Rulepack ratifier ≠ rulepack author | Application layer |
| DM-7 | Risk acceptance requires a non-null expiry | Data constraint |
| DM-8 | Audit log entries are append-only and hash-chained | Storage layer |
| DM-9 | Framework items with `text_redistributable = false` store identifiers only | Import layer |
| DM-10 | Verification is valid only when the knowledge base is identical between assessments | Verification logic |

---

## 8. Sizing

| Entity | Per 1,000-device campaign |
|---|---|
| Artifacts | ~3,000 (multi-artifact per device) |
| Facts | ~80,000 (≈80 per device) |
| Findings | ~155,000 (≈155 controls per device) |
| Evidence records | ~30,000 (failing and partial findings) |
| Graph nodes | ~50,000 |
| Graph edges | ~200,000 |
| Artifact storage | ~1–5 GB |

At five years of quarterly campaigns on a 1,000-device estate: roughly 3 million
findings and 60 GB of artifacts. Well within relational and object storage
capabilities, but it means findings require indexing on
`(campaign, device, control)` and `identity_key`, and artifacts belong in object
storage rather than in the database.
