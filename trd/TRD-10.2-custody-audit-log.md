# TRD-10.2 · Custody and Hash-Chained Audit Log

---

## 1. Scope

Artifact custody and immutability; the append-only, hash-chained audit log;
attribution of every action affecting an assessment or its adjudication;
retention and its tension with reproducibility.

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-ING-012, 013 | Hash at receipt; custody metadata |
| FR-INT-004 | Immutable artifact storage |
| FR-INT-005, 006 | Complete, append-only audit log |
| NFR-SEC-012 | Not editable through the application |
| NFR-DAT-001…003 | Immutability, retention, deletion warnings |
| PRD 14 DM-8 | Hash-chained log entries |

---

## 3. Artifact custody

### 3.1 Immutability

```
INV-10.2-01  An artifact is never modified after receipt.
INV-10.2-02  The content hash is computed on received octets, before any
             transformation (TRD-01.1 INV-01.1-01).
INV-10.2-03  Re-collection creates a new artifact; it never overwrites.
```

INV-10.2-03 is what makes remediation verification possible (PRD 09 §8): the
before and after artifacts both exist, both hashed, and the verification record
cites both.

### 3.2 Custody record

```yaml
artifact:
  id:             ART-2026Q3-004121
  sha256:         3f9a...c21b
  size_bytes:     184221
  received_at:    2026-09-11T09:14:22Z
  received_from:  live_collection
  collector:      svc-audit@nsca
  source_address: 10.0.0.5
  method:         ssh_readonly
  host_key_fingerprint: SHA256:8Kf2...
  commands_executed: [show_running_config, show_version, show_inventory]
  supplied_by:    null
  campaign:       Q3-2026-Core
  parent_artifact: null
  immutable:      true
```

`commands_executed` records **allowlist identifiers**, providing an auditable
record that only read-only operations occurred (TRD-01.3 INV-01.3-01).

For manually supplied artifacts, `supplied_by` is populated and collection fields
are null. Disputes about *"that is not what our configuration said"* are settled
by hash comparison against what was supplied.

### 3.3 Storage

| Property | Requirement |
|---|---|
| Write-once | Enforced at the storage layer, not by application convention |
| Encrypted at rest | NFR-SEC-004 |
| Integrity verified on read | Hash re-checked; mismatch is a hard error, never a silent read |
| Content-addressed | Deduplication across campaigns where hashes match |

**Deduplication is by hash, but custody records are not deduplicated.** Two
campaigns receiving the identical file share one stored object and retain two
custody records.

---

## 4. The audit log

### 4.1 Scope of logging

Every action affecting an assessment or its adjudication:

| Category | Examples |
|---|---|
| Campaign | created, scoped, issued, closed |
| Artifact | ingested, correlated, deleted |
| Assessment | executed, re-executed |
| Learning | rule taught, ratified, rejected, reverted; schema registered |
| Findings | confirmed, assigned, disputed, adjudicated, risk accepted, verified |
| Reports | generated, issued, amended |
| Knowledge | content imported, previewed, ratified |
| Administration | user created, role changed, credential registered |

**Not logged:** configuration content, credential material (NFR-OBS-006). The log
records *that* an action occurred and *by whom*, never the sensitive payload.

### 4.2 Entry structure

```yaml
entry:
  sequence:       184221                      # monotonic, gapless
  at:             2026-09-19T11:02:14Z
  actor:          r.kulkarni
  actor_type:     user | service | system
  action:         finding.disputed
  entity_type:    finding
  entity_id:      F-2026Q3-000418
  campaign:       Q3-2026-Core
  details:        { dispute_type: compensating_control }
  previous_hash:  8b12...4de7
  entry_hash:     c904...1a3f
```

```
entry_hash = H( sequence ‖ at ‖ actor ‖ action ‖ entity_type ‖
                entity_id ‖ canonical(details) ‖ previous_hash )
```

**`canonical(details)`** is a deterministic serialisation — sorted keys, fixed
number formatting, fixed encoding. Without it, the same logical entry could
produce different hashes and the chain would be unverifiable (D6, D8).

### 4.3 The hash chain

**INV-10.2-04 — The log is append-only and hash-chained.** Each entry commits to
its predecessor, so altering or removing any historical entry invalidates every
subsequent hash.

```
E₀ ← E₁ ← E₂ ← ... ← Eₙ
      each Eᵢ.previous_hash = Eᵢ₋₁.entry_hash
```

Verification walks the chain and reports the first break:

```
GET /admin/audit-log/verify
{ "entries_checked": 184221, "chain_intact": true, "first_break": null }
```

**DD-10.2-01 — This is a hash chain used for the reason hash chains exist.** It
provides tamper evidence for an append-only record. It is not a distributed
ledger, there is no consensus mechanism, and no blockchain is involved.

Worth stating plainly: the problem statement's theme is *"Blockchain &
Cybersecurity"*, but the description never mentions blockchain. A hash-chained
audit log is the appropriate and sufficient application of the underlying idea; a
bolted-on distributed ledger would be neither.

### 4.4 Non-editability

**INV-10.2-05 — The application exposes no write path to historical entries.**

| Layer | Enforcement |
|---|---|
| API | No update or delete endpoint for log entries |
| Application | Append-only interface; no ORM mutation path |
| Storage | Insert-only permissions for the application role |
| Verification | Chain check detects out-of-band modification |

An operator with database access can still alter rows — no application prevents
that. What the chain guarantees is that such alteration **cannot go unnoticed**,
which is the achievable and meaningful property.

### 4.5 Sequence integrity

Sequence numbers are monotonic and gapless. A gap indicates either a deleted
entry or a failed append that was not rolled back — both are integrity events and
are reported by the verification endpoint alongside chain breaks.

### 4.6 Anchoring

Periodically, the current head hash is written to the campaign record and
included in every issued report's manifest.

```
audit_log_head: c904...1a3f  as of 2026-09-30T23:59:59Z
```

This bounds the window in which undetected tampering could occur: any alteration
of entries predating an anchored head is detectable by comparing against the
anchor held in an already-issued report.

---

## 5. Attribution

**INV-10.2-06 — Every state transition records actor, timestamp and reason.**

Two transitions carry additional constraints, enforced as data constraints rather
than convention:

| Transition | Constraint |
|---|---|
| Rulepack ratification | `ratifier ≠ author` (FR-ADM-004) |
| Risk acceptance | `expires_at` non-null (FR-FND-008) |

Both appear in the log with the constraint's satisfaction visible, so an
assessor reviewing the log can confirm the control operated rather than trusting
that it did.

Service and system actors are distinguished from users: an automatic reopening of
an expired risk acceptance is logged as `actor_type: system` with the triggering
rule identified.

---

## 6. Retention and its tension

NFR-DAT-002, 003.

**Deleting artifacts destroys the reproducibility of every report derived from
them.** Retention policy and audit reproducibility pull in opposite directions,
and the platform's position is to make the trade-off explicit rather than
silently resolve it.

```
delete_artifacts(campaign) →
  affected = reports depending on these artifacts
  warn: "N issued reports will become UNVERIFIABLE"
  require explicit confirmation
  record the deletion in the audit log with actor and reason
  mark affected reports UNVERIFIABLE with the cause
```

**INV-10.2-07 — Audit log entries are never deleted by retention policy.** The
log is metadata: no configuration content, no credentials. It is small, and it is
the record of what was done. Artifacts may age out; the account of the audit does
not.

Reports themselves are also retained — a report remains valid and readable after
its artifacts are deleted. What is lost is the ability to *re-verify* it, and the
manifest says so.

---

## 7. Interfaces

```
store(artifact) → ArtifactRecord              # write-once
retrieve(artifact_id) → content               # hash verified on read
append(entry) → sequence                       # append-only
query(filters) → entries[]
verify_chain(from?, to?) → ⟨intact, first_break, entries_checked, gaps[]⟩
anchor() → head_hash
delete_artifacts(campaign, reason) → DeletionResult
```

---

## 8. Edge cases

| Case | Handling |
|---|---|
| Concurrent appends | Serialised; sequence assignment is atomic; chain remains linear |
| Append fails after hash computation | Transactional; no gap created; retried |
| Two campaigns receiving an identical file | One stored object, two custody records |
| Artifact hash mismatch on read | Hard error; storage integrity event; never a silent read |
| Log verification on a very large log | Incremental verification from the last verified anchor |
| Clock skew across nodes | Sequence, not timestamp, defines order; skew recorded |
| User deleted after acting | Attribution retains the identifier; the user record is soft-deleted |

**The deleted-user case matters for audit defensibility.** An audit trail
referencing a user who no longer exists must still resolve to a name — attribution
that dangles is not attribution.

---

## 9. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Historical entry altered out of band | Chain verification | Detected; first break located |
| Entry deleted out of band | Sequence gap plus chain break | Detected |
| Non-canonical detail serialisation | V-10.2-004 | Chain unverifiable — false tamper alarms |
| Configuration content leaked into the log | V-10.2-006 | Sensitive data in a widely-read record |
| Artifact modified in place | Write-once storage; hash on read | Hard error |
| Retention deleting log entries | V-10.2-008 | The account of the audit lost |

---

## 10. Verification

```
V-10.2-001   Artifacts are immutable and hash-verified on read
  Requirement  INV-10.2-01, FR-INT-004
  Method       UNIT + INTEGRATION
  Procedure    Attempt modification through every application path.
               Corrupt a stored object out of band and read it.
  Acceptance   Modification impossible through the application. Corrupted
               read raises a hard integrity error. Zero silent reads.
  Severity     BLOCKING
```

```
V-10.2-002   Re-collection creates a new artifact
  Requirement  INV-10.2-03
  Method       INTEGRATION
  Procedure    Collect from a device, remediate, re-collect for verification.
  Acceptance   Two artifacts with distinct ids and hashes. Verification
               record cites both. Zero overwrites.
  Severity     BLOCKING
```

```
V-10.2-003   The hash chain detects alteration and deletion
  Requirement  INV-10.2-04
  Method       INTEGRATION
  Procedure    Out of band: (a) modify an entry's details, (b) delete an
               entry, (c) reorder two entries. Run verification.
  Acceptance   All three detected. first_break identifies the earliest
               affected sequence. Deletion also reported as a sequence gap.
  Severity     BLOCKING
```

```
V-10.2-004   Detail serialisation is canonical
  Requirement  §4.2
  Method       PROPERTY
  Procedure    Append logically identical entries with details supplied in
               varied key order, number formats and encodings.
  Acceptance   Identical entry hashes. Zero false chain breaks.
  Severity     BLOCKING
```

```
V-10.2-005   No application write path to historical entries
  Requirement  INV-10.2-05, NFR-SEC-012
  Method       UNIT + static analysis
  Procedure    Enumerate all API endpoints and application data paths
               touching the log.
  Acceptance   Append and read only. Zero update or delete paths under any
               role, including Platform Administrator.
  Severity     BLOCKING
```

```
V-10.2-006   Sensitive content never enters the log
  Requirement  NFR-OBS-006
  Method       CORPUS
  Procedure    Execute full campaigns including teaching and collection.
               Scan every log entry for configuration content, credentials,
               community strings and key material.
  Acceptance   Zero occurrences.
  Severity     BLOCKING
```

```
V-10.2-007   Constrained transitions are enforced as data constraints
  Requirement  INV-10.2-06, FR-ADM-004, FR-FND-008
  Method       INTEGRATION
  Procedure    Attempt self-ratification and risk acceptance without expiry,
               via API with the UI bypassed.
  Acceptance   Both rejected with 422. Zero entries recording a violated
               constraint.
  Severity     BLOCKING
```

```
V-10.2-008   Retention never deletes audit log entries
  Requirement  INV-10.2-07
  Method       INTEGRATION
  Procedure    Apply an aggressive retention policy to a completed campaign.
  Acceptance   Artifacts removed. Log entries and reports retained. Affected
               reports marked UNVERIFIABLE with the cause. Deletion itself
               logged with actor and reason.
  Severity     BLOCKING
```

```
V-10.2-009   Sequence integrity
  Requirement  §4.5
  Method       PROPERTY
  Procedure    Append 100,000 entries under concurrency from 1 to 32 writers,
               including simulated append failures.
  Acceptance   Monotonic, gapless sequence. Linear chain. Zero gaps from
               failed appends.
  Severity     BLOCKING
```

```
V-10.2-010   Anchoring bounds the tamper window
  Requirement  §4.6
  Method       INTEGRATION
  Procedure    Issue a report, note the anchored head. Alter an entry
               predating the anchor. Verify against the anchor in the report.
  Acceptance   Alteration detected by anchor comparison, independent of the
               live chain.
  Severity     MAJOR
```

```
V-10.2-011   Custody records support dispute resolution
  Requirement  FR-ING-013
  Method       INTEGRATION
  Procedure    Supply an artifact manually; later supply a differing version
               claiming it is the same configuration.
  Acceptance   Both custody records retained with distinct hashes, suppliers
               and timestamps. The discrepancy is demonstrable from records
               alone.
  Severity     MAJOR
```

---

## 11. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should anchoring be to an external timestamping authority? | External anchoring would make tampering detectable even by an operator with full database access, but requires network egress — impossible in an air-gapped deployment, which is the primary target. Current design: internal anchoring in issued reports, with external anchoring available where connectivity exists |
| Q2 | Should the audit log be exportable independently of a campaign? | Useful for external audit of the auditors, but a full log export is a rich metadata disclosure. Current design: exportable per campaign with the campaign archive, full export restricted to Platform Administrator and itself logged |
| Q3 | Should artifact deduplication span campaigns given differing retention policies? | Deduplication saves substantial storage, but deleting under one campaign's policy must not remove an object another campaign still needs. Current design: content-addressed with reference counting; deletion removes the reference, and the object only when unreferenced |
