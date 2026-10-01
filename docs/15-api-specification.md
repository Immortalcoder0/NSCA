# 15 · API Specification

> The external interface surface. Every capability available in the interface is
> available through the API, with one absolute exception: **there is no endpoint
> that can modify an audited device, because no such capability exists anywhere
> in the system.**

---

## 1. Principles

| # | Principle |
|---|---|
| A1 | Every operation is authenticated and authorised by role |
| A2 | Every state-changing call is recorded in the audit log with the acting identity |
| A3 | No endpoint exposes device modification — enforced by the absence of the capability, not by permission checks |
| A4 | Long-running operations are asynchronous and return a job reference |
| A5 | Responses carry provenance — findings always include evidence references |
| A6 | The API is versioned; breaking changes require a new version path |
| A7 | Bulk is first-class; an assessor works with hundreds of devices |

Base path: `/api/v1`

---

## 2. Campaigns

```
POST   /campaigns                     create
GET    /campaigns                     list, filterable
GET    /campaigns/{id}                detail including knowledge pin
PATCH  /campaigns/{id}                update while Draft
POST   /campaigns/{id}/scope/resolve  resolve scope to a device list
POST   /campaigns/{id}/issue          transition to Issued (Lead Assessor only)
POST   /campaigns/{id}/close          transition to Closed
GET    /campaigns/{id}/completeness   collection completeness report
GET    /campaigns/{id}/compare/{other} delta with decomposition
```

**Create:**

```json
{
  "name": "Q3-2026 Core Infrastructure Audit",
  "scope": {
    "type": "filter",
    "expression": "exposure == 'internet_facing' or (role == 'access' and sample(0.10))"
  },
  "frameworks": [
    { "framework": "cis",  "benchmark": "cisco_ios_15", "version": "4.1.0" },
    { "framework": "nist", "catalog": "800-53", "revision": "Rev5" },
    { "framework": "stig", "release": "2026-01" }
  ],
  "owner": "p.sharma",
  "window": { "start": "2026-09-01", "end": "2026-09-30" }
}
```

**Comparison response** — the delta decomposition:

```json
{
  "from": "Q2-2026", "to": "Q3-2026",
  "compliance": { "from": 0.78, "to": 0.81 },
  "decomposition": [
    { "cause": "verified_remediation",  "delta":  0.05, "findings": 34 },
    { "cause": "framework_version_change", "delta": -0.03,
      "detail": "STIG 2025-10 → 2026-01: 14 added, 6 tightened" },
    { "cause": "scope_change", "delta": 0.01, "detail": "12 devices decommissioned" },
    { "cause": "configuration_regression", "delta": 0.00, "findings": 0 }
  ]
}
```

---

## 3. Ingestion

```
POST   /campaigns/{id}/artifacts            upload one or many (multipart)
POST   /campaigns/{id}/artifacts/bundle     archive or show-tech bundle
POST   /campaigns/{id}/collect              start read-only live collection
GET    /jobs/{id}                           job status
GET    /artifacts/{id}                      metadata and custody
GET    /artifacts/{id}/content              raw content (secrets masked by role)
```

**Upload response:**

```json
{
  "job_id": "job-2026-004821",
  "accepted": 389,
  "results": [
    { "artifact_id": "ART-004121", "filename": "CORE-SW-01/running-config.txt",
      "sha256": "3f9a...c21b", "device": "CORE-SW-01",
      "platform": "cisco_iosxe", "os_version": "16.12.04",
      "artifact_type": "running_config", "export_mode": "verbose",
      "status": "parsed" },

    { "artifact_id": "ART-004155", "filename": "BR-RTR-014.cfg",
      "platform": "cisco_ios", "export_mode": "terse",
      "status": "parsed_with_caveat",
      "caveat": { "code": "TERSE_EXPORT",
                  "message": "Settings at platform defaults are not present",
                  "controls_unassessable": 34,
                  "remedy": "Re-collect with `show running-config all`" } },

    { "artifact_id": "ART-004180", "filename": "RTR-Pune-02.rsc",
      "platform": "mikrotik_routeros", "os_version": "7.11.2",
      "status": "platform_not_taught",
      "grammar_coverage": 0.984,
      "training": { "questions_prepared": 9, "estimated_minutes": 8,
                    "url": "/api/v1/training/queue/mikrotik_routeros" } },

    { "artifact_id": "ART-004191", "filename": "unknown-04.cfg",
      "status": "unidentified", "grammar_coverage": 0.43,
      "message": "Grammar inference unreliable; assisted authoring required" }
  ]
}
```

**Four outcome states, never a binary.** `platform_not_taught` is an invitation
carrying a direct link into training, not an error.

**Collection** — note the enforced read-only declaration:

```json
{
  "targets": [{ "host": "10.0.0.5", "credential_ref": "cred-audit-ios" }],
  "artifacts": ["running_config", "show_version", "show_inventory"],
  "mode": "read_only"
}
```

`mode` accepts only `read_only`. Any other value is rejected — the write path
does not exist.

---

## 4. Assessment

```
POST   /campaigns/{id}/assess           run assessment
GET    /assessments/{id}                summary and scores
GET    /assessments/{id}/facts          full Security Baseline Model instance
GET    /assessments/{id}/facts/{path}   single fact with provenance
GET    /assessments/{id}/unmatched      constructs routed to learning
```

**Assessment summary:**

```json
{
  "id": "ASM-2026Q3-004121",
  "device": "CORE-SW-01",
  "platform": "cisco_iosxe", "os_version": "16.12.04",
  "serials": [{ "component": "chassis", "serial": "FCW2140L0GH" }],
  "scores": {
    "compliance": 0.78, "coverage": 0.92,
    "meaningful_ratio": 0.64, "security": 0.61
  },
  "counts": { "pass": 112, "fail": 31, "unknown": 12,
              "not_applicable": 14, "pass_partial": 6 },
  "rulepacks_used": [
    { "id": "cisco_iosxe", "version": "7.2.1", "trust_tier": "certified" }
  ],
  "grammar_coverage": 0.998,
  "unaudited_capabilities": [
    { "path": "services.web_mgmt_8443", "port": 8443,
      "properties": ["listens", "authenticates", "mutates"],
      "controls_contaminated": 6 }
  ]
}
```

**Fact with provenance:**

```json
{
  "path": "mgmt.protocols.telnet.enabled",
  "value": true,
  "provenance": {
    "source": "explicit",
    "artifact": "ART-004121",
    "artifact_hash": "3f9a...c21b",
    "lines": [143],
    "excerpt": " transport input telnet ssh",
    "extractor": "cisco_iosxe.vty.transport_input@7",
    "rulepack": "cisco_iosxe@7.2.1",
    "trust_tier": "certified",
    "confidence": 1.0
  }
}
```

---

## 5. Findings

```
GET    /campaigns/{id}/findings              list, filter, group
GET    /findings/{id}                        detail with evidence
POST   /findings/{id}/confirm
POST   /findings/{id}/assign
POST   /findings/{id}/dispute
POST   /findings/{id}/adjudicate             Lead Assessor
POST   /findings/{id}/accept-risk            Lead Assessor
POST   /findings/{id}/mark-remediated
POST   /findings/{id}/verify                 triggers re-assessment
GET    /findings/{id}/history                full transition log
GET    /findings/{id}/remediation            plan with dry run
POST   /findings/bulk                        bulk state transitions
GET    /campaigns/{id}/attack-paths
GET    /campaigns/{id}/systemic
```

**Query parameters:** `verdict`, `severity`, `state`, `control`, `platform`,
`device`, `attack_path`, `trust_tier`, `group_by`

**Finding with evidence:**

```json
{
  "id": "F-2026Q3-000412",
  "control": "NSCA-MGMT-002",
  "verdict": "FAIL",
  "severity": { "base": "high", "effective": "critical",
                "reason": "device.exposure == internet_facing" },
  "evidence": [{
    "artifact": "ART-004121",
    "lines": [141, 145], "highlight": [143],
    "excerpt": "line vty 0 4\n login local\n transport input telnet ssh\n exec-timeout 0 0\n!",
    "facts": ["mgmt.protocols.telnet.enabled"]
  }],
  "frameworks": [
    { "framework": "cis",  "id": "CIS-IOS-1.2.4", "version": "4.1.0" },
    { "framework": "nist", "id": "AC-17", "revision": "Rev5" },
    { "framework": "stig", "id": "V-216644", "release": "2026-01",
      "category": "CAT I" },
    { "framework": "iso",  "id": "A.9.4.2" }
  ],
  "attack_paths": ["AP-003"],
  "rulepack_trust_tier": "certified",
  "state": "Confirmed"
}
```

**Dispute with compensating control** — the response carries machine
verification:

```json
{
  "dispute_id": "D-000118",
  "type": "compensating_control",
  "claim": "Device is on an isolated OOB management network",
  "verification": {
    "result": "REFUTED",
    "counterexample": {
      "packet": { "src": "10.40.7.19", "dst": "10.250.0.11",
                  "dport": 23, "protocol": "tcp" },
      "path": [
        { "node": "MGMT-SW-04:Gi0/8", "note": "bridges VLAN 250 and VLAN 40" },
        { "node": "SW-Core-02:acl[user-out]:22", "action": "permit" }
      ]
    },
    "assumptions": ["Based on 389 of 412 devices; 23 uncollected"],
    "confidence": "medium"
  }
}
```

**Risk acceptance requires an expiry:**

```json
{
  "expires_at": "2027-03-31",
  "justification": "Isolated OOB network; legacy NMS requires Telnet. Replacement under NET-2291.",
  "compensating_control": { "claim": "Network isolation of 10.250.0.0/24" }
}
```

Omitting `expires_at` returns `422`. Indefinite acceptance is how findings
disappear.

---

## 6. Training

```
GET    /training/queue                        platforms and gaps awaiting training
GET    /training/queue/{platform}             prepared questions
GET    /training/queue/{platform}/next        next question by information gain
POST   /training/answer                       confirm, correct, or reject
GET    /training/rules?status=provisional     rules awaiting ratification
POST   /training/rules/{id}/ratify            second user
POST   /training/rules/{id}/reject
GET    /training/metrics                      the learning curve
```

**Next question:**

```json
{
  "question_id": "Q-mikrotik-001",
  "position": 1, "total": 9,
  "section": "/ip service",
  "pattern": "set <service> disabled=<yes|no> [port=<n>]",
  "examples": [
    { "line": 14, "text": "set telnet disabled=no port=23" },
    { "line": 17, "text": "set ssh disabled=no port=22" }
  ],
  "proposal": {
    "description": "This appears to enable or disable management services",
    "mappings": [
      { "token": "telnet", "fact": "mgmt.protocols.telnet.enabled", "value": true },
      { "token": "ssh",    "fact": "mgmt.protocols.ssh.enabled",    "value": true }
    ],
    "polarity": {
      "inverted": true,
      "explanation": "'disabled=no' is read as the service being ON",
      "requires_explicit_confirmation": true
    },
    "confidence": 0.91
  },
  "impact": { "facts_resolved": 5, "controls_unlocked": 8,
              "coverage_before": 0.0, "coverage_after_estimate": 0.31 }
}
```

**Answer:**

```json
{
  "question_id": "Q-mikrotik-001",
  "response": "confirm",
  "polarity_confirmed": true
}
```

`response` ∈ `confirm` · `polarity_inverted` · `edit` · `not_relevant` · `skip`

Answering with `confirm` while `requires_explicit_confirmation` is true and
`polarity_confirmed` is absent returns `422`.

**Learning metrics — the product's central claim, as data:**

```json
{
  "platforms": [
    { "order": 1, "platform": "cisco_ios",  "confirmations_to_70pct": 47,
      "wall_clock_minutes": 41, "proposal_acceptance_rate": 0.52 },
    { "order": 6, "platform": "mikrotik_routeros", "confirmations_to_70pct": 8,
      "wall_clock_minutes": 8, "proposal_acceptance_rate": 0.89,
      "polarity_correction_rate": 0.0 }
  ],
  "trend": "declining"
}
```

---

## 7. Knowledge base

```
GET    /knowledge/rulepacks
GET    /knowledge/rulepacks/{id}/coverage
POST   /knowledge/rulepacks/import          signed bundle
GET    /knowledge/rulepacks/{id}/export     signed bundle
GET    /knowledge/controls
GET    /knowledge/frameworks
GET    /knowledge/frameworks/{id}/coverage  automation coverage manifest
POST   /knowledge/frameworks/import
POST   /knowledge/frameworks/{id}/preview   estate impact dry run
POST   /knowledge/frameworks/{id}/ratify
GET    /knowledge/schema
POST   /knowledge/schema/register           register a new fact definition
GET    /knowledge/freshness
```

**Automation coverage manifest:**

```json
{
  "framework": "cis", "benchmark": "cisco_ios_15", "version": "4.1.0",
  "total_recommendations": 187,
  "automated": 154,
  "manual_only": 21,
  "data_unavailable": 7,
  "not_implemented": 5,
  "automation_rate": 0.82,
  "manual_only_items": [
    { "id": "CIS-IOS-1.9.1", "reason": "Physical security cannot be determined from configuration" }
  ]
}
```

**Framework update preview:**

```json
{
  "from": "2025-10", "to": "2026-01",
  "content_changes": { "added": 6, "modified": 4, "withdrawn": 2 },
  "estate_impact": {
    "campaign": "Q3-2026",
    "new_findings": 6, "affected_devices": 41,
    "severity_changes": [
      { "control": "NSCA-MGMT-004", "from": "CAT II", "to": "CAT I", "devices": 2 }
    ],
    "findings_closed": 2,
    "compliance_delta": -0.03
  }
}
```

---

## 8. Reports

```
POST   /campaigns/{id}/reports/generate
GET    /reports/{id}
GET    /reports/{id}/download?format=pdf|docx|json|csv|oscal
GET    /reports/{id}/manifest
POST   /reports/{id}/verify                 re-execute and compare
POST   /reports/{id}/amend
GET    /campaigns/{id}/reports/estate
GET    /campaigns/{id}/export               complete self-contained archive
```

**Verification response:**

```json
{
  "report_id": "RPT-2026Q3-CORE-SW-01-001",
  "result": "MATCH",
  "original_hash": "9a41...7f2e",
  "recomputed_hash": "9a41...7f2e",
  "knowledge_base_identical": true
}
```

If `result` is `MISMATCH` with `knowledge_base_identical: true`, that is a
**determinism defect** and is reported as such, not as a content change.

---

## 9. Administration

```
GET    /admin/users            POST /admin/users
GET    /admin/roles
GET    /admin/credentials      POST /admin/credentials
GET    /admin/audit-log        filterable, append-only
GET    /admin/audit-log/verify hash-chain integrity check
GET    /admin/health
GET    /admin/status
```

Credential material is never returned by any endpoint under any role.

**Audit log verification:**

```json
{ "entries_checked": 184221, "chain_intact": true, "first_break": null }
```

---

## 10. Conventions

| Concern | Convention |
|---|---|
| Auth | Bearer token or mTLS; MFA at session establishment |
| Errors | `{ code, message, detail, remediation }` — machine-readable code plus human guidance |
| Pagination | Cursor-based; `limit`, `cursor`, `next_cursor` |
| Async | `202 Accepted` with `job_id`; poll `/jobs/{id}` |
| Idempotency | `Idempotency-Key` on all POST |
| Rate limiting | Per-identity, with `Retry-After` |
| Versioning | Path-based; breaking changes require a new version |

### Status codes

| Code | Use |
|---|---|
| 200 / 201 / 202 | Success, created, accepted-async |
| 400 | Malformed request |
| 401 / 403 | Unauthenticated / insufficient role |
| 404 | Not found |
| 409 | State conflict — e.g. modifying an issued campaign |
| 422 | Semantically invalid — e.g. risk acceptance without expiry, polarity unconfirmed |
| 429 | Rate limited |

**422 carries product meaning here.** Several invariants are enforced as
validation rather than as convention: mandatory risk-acceptance expiry, explicit
polarity confirmation, ratifier distinct from author, and `mode: read_only` on
collection.

---

## 11. Webhooks

```
campaign.state_changed
assessment.completed
finding.state_changed
finding.risk_acceptance_expiring     ← 30 days before expiry
finding.regressed                    ← passed previously, now failing
training.rule_awaiting_ratification
knowledge.update_available
report.issued
```

Payloads carry identifiers and state only, never configuration content.

`finding.regressed` is the highest-value notification: a finding that returns
after a verified remediation indicates a process failure, not merely a
configuration defect.
