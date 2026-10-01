# TRD-01.1 · Artifact Intake, Correlation and Custody

---

## 1. Scope

Receipt of configuration artifacts from all three channels; hashing and custody
recording; decomposition of bundles; correlation of multiple artifacts into one
device record; detection of export completeness; collection-completeness
accounting against campaign scope.

**Out of scope:** parsing (TRD-02.1), platform identification (TRD-01.2), live
device connection (TRD-01.3).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-ING-001, 002 | Single and bulk intake, archives, directory trees |
| FR-ING-003…007 | Format acceptance; bundle decomposition |
| FR-ING-010, 011 | Correlation by hostname and serial with ambiguity escalation |
| FR-ING-012, 013 | Hash at receipt; custody record |
| FR-ING-014 | Export mode detection |
| FR-ING-015, 016 | Collection completeness; uncollected devices as findings |
| FR-ING-017 | Graceful handling of malformed input |
| FR-ING-018 | Supplier-redaction detection |
| G3 | Artifact identity is the root of every evidence chain |

---

## 3. Design

### 3.1 Intake pipeline

```
  input (file | stream | archive | collection result)
      │
      ├─► 1  size and quota check
      ├─► 2  hash at receipt          ◄── before any transformation
      ├─► 3  encoding normalisation   ── recorded, not silent
      ├─► 4  container detection      ── archive? bundle? single?
      │        └─► decompose ──► recurse from step 2 per member
      ├─► 5  artifact type classification
      ├─► 6  export mode detection
      ├─► 7  redaction detection
      ├─► 8  custody record write
      └─► 9  correlation into device record
```

**INV-01.1-01 — Hash before transform.** The content hash is computed on the
exact octet sequence received, before encoding normalisation or any other
processing. A hash computed after transformation cannot establish what was
supplied.

### 3.2 Encoding normalisation

Configurations arrive with inconsistent encodings. Normalisation is **recorded,
never silent**, because line numbers in evidence must map back to what the
supplier can see in their own file.

| Input condition | Action | Recorded |
|---|---|---|
| Valid UTF-8 | Pass through | — |
| UTF-8 BOM | Strip | `bom_stripped` |
| Valid Latin-1, invalid UTF-8 | Transcode | `transcoded_from: latin1` |
| Undecodable octets | Replace with U+FFFD, retain original offsets | `undecodable_bytes: [offsets]` |
| CRLF line endings | Normalise to LF | `line_endings: crlf` |
| Mixed line endings | Normalise to LF | `line_endings: mixed` ⚠ |
| No trailing newline | Leave | — |

**DD-01.1-01.** Line numbers are assigned **after** newline normalisation and are
1-indexed. Undecodable octets do not shift line numbering, because replacement is
1:1 at the octet level.

### 3.3 Artifact type classification

Classification is by content signature, not filename — filenames are unreliable
and supplier-controlled.

| Type | Signature |
|---|---|
| `running_config` | Configuration-shaped content, no diagnostic section markers |
| `show_version` | Version banner patterns per platform family |
| `show_inventory` | `NAME:`/`PID:`/`SN:` triples or equivalent |
| `tech_support_bundle` | Two or more recognised section delimiters |
| `cloud_policy` | Valid JSON matching a known provider policy shape |
| `archive` | Container magic bytes |
| `unknown` | No signature matched |

`unknown` is retained, not discarded — it may become classifiable once a platform
is taught (FR-FPR-006).

### 3.4 Bundle decomposition

`show tech-support` bundles are delimited by section markers. Decomposition
produces child artifacts, each independently hashed, each carrying
`parent_artifact` and the byte offset within the parent.

```
ART-004200  tech_support_bundle       sha256:aa11…
  ├─ ART-004201  running_config       offset 1_204   sha256:3f9a…
  ├─ ART-004202  show_version         offset 184_991 sha256:7c04…
  └─ ART-004203  show_inventory       offset 191_442 sha256:e281…
```

**INV-01.1-02.** A child artifact's line numbers are relative to the child. The
parent offset is retained so that a supplier can locate evidence in the bundle
they actually submitted.

### 3.5 Correlation

Multiple artifacts → one device record.

```
correlate(artifacts) →
  1  extract identity candidates from each artifact
       hostname   from config header or show_version
       serial     from show_inventory (chassis component)
       address    from collection metadata
  2  group by strongest available key, in order:
       chassis serial  >  collection address  >  hostname
  3  for each group, verify consistency across members
  4  emit device record, or escalate
```

**DD-01.1-02 — Serial outranks hostname.** Hostnames are frequently duplicated
across sites (`CORE-SW-01` in every branch) and are freely editable. Chassis
serial is unique and stable. Where both are available and disagree, serial wins
and the conflict is recorded.

Escalation conditions (FR-ING-011):

| Condition | Handling |
|---|---|
| Two artifacts, same hostname, different serial | Escalate — two devices or a renamed device |
| Two artifacts, same serial, different hostname | Auto-merge, record `hostname_changed` |
| Artifact with no identity signal | Hold unassigned; surface in the intake report |
| `show_inventory` with no matching config | Hold; device identification incomplete |

**Escalations block assessment of the affected device.** Assessing a
mis-correlated device produces findings attributed to the wrong hardware, which
is worse than not assessing it.

### 3.6 Export mode detection

FR-ING-014. A terse export is a diff against platform defaults; auditing it as a
complete state is a silent correctness failure.

Three independent signals, combined:

| Signal | Method |
|---|---|
| **Explicit marker** | Some platforms emit a verbosity indicator in the header |
| **Default-line presence** | Presence of ≥ N lines known to be default-valued for the platform and version. A verbose export contains them; a terse one does not |
| **Density comparison** | Line count relative to the corpus distribution for the same platform, version and rough device class |

```
detect_export_mode(artifact, platform, version) →
  if explicit_marker present         → verbose | terse   (confidence 1.0)
  else:
    d = count of known-default lines present
    if d ≥ threshold_verbose          → verbose (confidence 0.9)
    if d == 0 and density < p25       → terse   (confidence 0.8)
    otherwise                         → unknown
```

**DD-01.1-03.** `unknown` export mode is treated as `terse` for the purpose of
coverage warnings. Under-claiming coverage is safe; over-claiming is not (G2).

Output feeds the intake caveat and the report's coverage statement:

```
BR-RTR-014   terse export detected
             34 controls cannot be assessed on this device
             remedy: re-collect with `show running-config all`
```

### 3.7 Redaction detection

FR-ING-018. Suppliers frequently sanitise before handing over configurations,
which silently removes the evidence a control depends on.

Detected patterns: `<removed>`, `<redacted>`, `***`, `xxxxx` in credential
positions, structurally invalid hash values in known hash fields.

Redaction produces a **coverage warning, not a finding**. A redacted password is
not a compliant password — it is an unassessable one, and the affected facts
resolve to `default_unknown`.

### 3.8 Collection completeness

FR-ING-015, 016. Scope resolution produces the expected device set; intake
produces the received set.

```
completeness(campaign) →
  expected  = resolve_scope(campaign)
  received  = devices with ≥ 1 correlated artifact
  missing   = expected \ received
  for each m in missing: reason, owner
```

| Reason | Source |
|---|---|
| `no_response` | Collection attempted, device unreachable |
| `auth_failed` | Collection attempted, credentials rejected |
| `not_supplied` | No collection attempted, no upload received |
| `format_unrecognised` | Artifact received but unclassifiable |
| `correlation_blocked` | Artifact received but escalated |

Each missing device becomes an estate-level finding with a reason and an owner.

---

## 4. Interfaces

**Input**

```
IntakeRequest {
  campaign_id
  source: upload | collection | bundle_extraction
  payload: bytes | stream
  filename: string?
  supplied_by: user_ref?
  collection_metadata: { address, method, collector }?
}
```

**Output**

```
IntakeResult {
  artifact_id, content_hash, size_bytes
  artifact_type, export_mode, export_mode_confidence
  encoding_notes[]
  redaction_detected: bool
  device_correlation: assigned(device_id) | held(reason) | escalated(reason)
  children[]                       // bundle decomposition
  status: accepted | accepted_with_caveat | rejected
  caveat?: { code, message, controls_unassessable, remedy }
}
```

**Downstream contract:** TRD-01.2 receives `(artifact_id, normalised_content,
artifact_type)`. Line numbers referenced by any downstream subsystem are the
post-normalisation line numbers assigned here.

---

## 5. Edge cases

| Case | Handling |
|---|---|
| Archive bomb (high expansion ratio) | Expansion ratio and total size capped; reject with a specific code |
| Nested archives | Recurse to depth 3, then reject |
| Duplicate artifact (identical hash, same campaign) | Deduplicate; record both custody entries against one artifact |
| Same device supplied twice, different content | Both retained; latest by receipt time is assessed; the earlier is retained as evidence and flagged |
| Configuration exceeding 500,000 lines | Streamed, not fully buffered; NFR-PERF-003 |
| Config containing a section marker as literal text (banner) | Bundle decomposition requires the marker at line start plus a following section body; ambiguous cases are not decomposed and are flagged |
| Zero-byte artifact | Rejected with a distinct code, not silently accepted as empty configuration |
| Artifact that is a diff or patch | Classified `unknown`; explicitly not assessed |

**The banner case is real.** A device banner containing text resembling a
`show tech-support` delimiter will mis-split a bundle. The two-signal requirement
(line-start marker plus plausible section body) mitigates it; ambiguity is
surfaced rather than guessed.

---

## 6. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Mis-correlation | Consistency check across artifacts | Escalate; block assessment of that device |
| Export mode misdetected as verbose | Corpus calibration; coverage anomaly | Coverage over-claimed — **G2 risk.** Mitigated by DD-01.1-03 |
| Undetected redaction | Facts resolve `default_unknown` anyway | Coverage lowered; no false pass |
| Bundle mis-split | Downstream classification mismatch | Section flagged; treated as one `unknown` artifact |
| Encoding corruption | Replacement-character count | Recorded; parse coverage falls; visible in report |
| One artifact fails in a bulk job | Per-artifact isolation | Job continues (FR-ING-017); failure recorded |

---

## 7. Verification

```
V-01.1-001   Hash is computed on received octets, before transformation
  Requirement  FR-ING-012, INV-01.1-01
  Method       UNIT
  Procedure    Submit an artifact with CRLF endings and a BOM. Compare the
               recorded hash against an externally computed hash of the raw file.
  Acceptance   Exact match. Hash is unaffected by normalisation.
  Severity     BLOCKING
```

```
V-01.1-002   Bulk intake isolates per-artifact failure
  Requirement  FR-ING-017
  Method       INTEGRATION
  Procedure    Submit 100 artifacts of which 7 are malformed
               (truncated, zero-byte, undecodable, archive bomb,
                nested depth 4, invalid JSON, unclassifiable).
  Acceptance   93 accepted, 7 rejected with distinct codes,
               job completes, no partial-state corruption.
  Severity     BLOCKING
```

```
V-01.1-003   Correlation prefers serial over hostname
  Requirement  FR-ING-011, DD-01.1-02
  Method       UNIT
  Procedure    Two artifact sets sharing hostname CORE-SW-01 with distinct
               chassis serials.
  Acceptance   Two device records emitted; conflict recorded; neither merged.
  Severity     MAJOR
```

```
V-01.1-004   Ambiguous correlation blocks assessment
  Requirement  FR-ING-011
  Method       INTEGRATION
  Procedure    Submit an artifact set that escalates. Attempt assessment.
  Acceptance   Assessment refused for that device with reason
               `correlation_blocked`. Device appears in completeness report
               as missing. No findings produced.
  Severity     BLOCKING
```

```
V-01.1-005   Serial numbers are extracted and reach the device record
  Requirement  FR-ING-010, FR-RPT-002
  Method       CORPUS
  Procedure    For all corpus devices supplying show_inventory, verify
               chassis serial present in the device record.
  Acceptance   ≥ 98% extraction rate where the artifact is present.
               100% of failures reported as `NOT DETERMINED`, never omitted.
  Severity     BLOCKING
```

```
V-01.1-006   Export mode detection accuracy
  Requirement  FR-ING-014
  Method       CORPUS
  Procedure    Labelled corpus subset: 20 terse, 20 verbose, per platform.
  Acceptance   Terse recall ≥ 95%. Verbose misclassified as terse is
               acceptable; terse misclassified as verbose ≤ 2%.
  Severity     MAJOR
  Note         Asymmetric threshold is deliberate — see DD-01.1-03.
```

```
V-01.1-007   Bundle decomposition preserves evidence traceability
  Requirement  FR-ING-007, INV-01.1-02
  Method       UNIT + CORPUS
  Procedure    Decompose show-tech bundles. For each child artifact, verify
               parent offset + child line offset resolves to the identical
               text in the original bundle.
  Acceptance   100% of child line references resolve correctly.
  Severity     BLOCKING
```

```
V-01.1-008   Banner text resembling a section marker does not mis-split
  Requirement  Edge case §5
  Method       UNIT
  Procedure    Configuration with a banner containing a literal
               show-tech delimiter string.
  Acceptance   Not decomposed, or decomposed correctly. Flagged either way.
               No silent mis-split.
  Severity     MAJOR
```

```
V-01.1-009   Collection completeness accounts for every in-scope device
  Requirement  FR-ING-015, 016
  Method       INTEGRATION
  Procedure    Campaign scoped to 50 devices; supply artifacts for 43.
  Acceptance   received = 43, missing = 7, each with a reason and an owner.
               Sum equals scope exactly. Seven estate findings produced.
  Severity     BLOCKING
```

```
V-01.1-010   Intake is deterministic
  Requirement  G1, NFR-REL-001
  Method       PROPERTY
  Procedure    Submit the same 200-artifact set 10 times, varying submission
               order and concurrency.
  Acceptance   Identical artifact hashes, identical device correlation,
               identical completeness figures. Artifact IDs may differ;
               nothing derived from them may.
  Severity     BLOCKING
```

```
V-01.1-011   Redaction detection lowers coverage without producing a pass
  Requirement  FR-ING-018, G2
  Method       INTEGRATION
  Procedure    Corpus config with credentials replaced by `<removed>`.
  Acceptance   Affected facts resolve default_unknown; dependent controls
               return UNKNOWN. Zero PASS verdicts on redacted facts.
  Severity     BLOCKING
```

```
V-01.1-012   Intake throughput
  Requirement  NFR-PERF-004
  Method       PERFORMANCE
  Procedure    500 artifacts, mean 8,000 lines, on the reference profile
               (8 cores, 16 GB).
  Acceptance   ≥ 100 artifacts/minute through intake and correlation.
  Severity     MINOR
```

---

## 8. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should a device supplied twice with differing content in one campaign be assessed twice, or once with the later artifact? | Twice gives visibility into mid-campaign change but complicates the per-device report, which the PRD mandates as singular. Current design: assess the later, retain and flag the earlier |
| Q2 | Should export-mode density calibration be per platform, or per platform *and* device class? | Per-class is more accurate but requires class labelling that may be unavailable. Current design: per platform, with class as a future refinement |
| Q3 | How long are `unknown`-type artifacts retained before review? | Retention costs storage; discarding loses the FR-FPR-006 retrospective-assessment benefit. Current design: retained for the campaign's retention period |
