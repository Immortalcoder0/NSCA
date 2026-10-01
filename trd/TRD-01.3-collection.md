# TRD-01.3 · Read-Only Collection

---

## 1. Scope

Retrieval of configuration artifacts directly from reachable devices over SSH,
and the architectural enforcement of **assessor independence (G4)** — the
guarantee that no code path exists by which the platform can modify an audited
device.

The problem statement suggests Netmiko/NAPALM for data collection; this TRD
specifies the capability those libraries provide and the constraints imposed
upon it.

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-ING-008 | Read-only live collection over SSH |
| FR-ING-009 | Architectural, not conventional, enforcement of read-only |
| FR-ING-013 | Collection custody metadata |
| NFR-SEC-002 | Compile-time command allowlist |
| NFR-SEC-003 | Credential handling |
| NFR-SEC-015 | Deployable with no inbound path to devices |
| G4 | Assessor independence |

---

## 3. Design

### 3.1 The central constraint

> **G4 is verified by absence, not by permission.**

A permission check that denies write operations can be misconfigured, bypassed by
a defect, or removed by a well-meaning change. An architecture in which the
capability *does not exist* cannot fail in those ways.

Three enforcement layers, in order of strength:

| Layer | Mechanism | Bypassable by |
|---|---|---|
| **L1 — Absence** | No function in the codebase issues a configuration-mode command or a write RPC | Adding such a function — detected by CI (V-01.3-002) |
| **L2 — Allowlist** | Commands are drawn from a compile-time constant set; the transport rejects anything else | Modifying the constant — detected by CI |
| **L3 — Device-side** | Collection accounts are provisioned read-only on the device | Operator misconfiguration — checked at credential registration |

L3 is outside the platform's control, so it is **verified, not assumed**:
credential registration performs a probe confirming the account cannot enter
configuration mode, and records `read_only_verified`.

**DD-01.3-01.** Collection with an unverified credential is permitted but
recorded, and the resulting artifacts carry `collection_privilege: unverified`.
This surfaces in the report because an over-privileged collection account is
itself a compliance weakness on the audited estate.

### 3.2 Command allowlist

```
ALLOWLIST : platform → set of command templates      // compile-time constant

cisco_ios / cisco_iosxe:
    show running-config
    show running-config all
    show version
    show inventory
    show tech-support          (bounded)
juniper_junos:
    show configuration | display set
    show configuration | display inheritance defaults
    show version
    show chassis hardware
fortios:
    show full-configuration
    get system status
    get hardware status
panos:
    show config running          (XML API, read verb only)
    show system info
mikrotik_routeros:
    /export verbose
    /system resource print
    /system routerboard print
arista_eos:
    show running-config all
    show version
    show inventory
```

**INV-01.3-01.** The transport layer accepts only an allowlist entry identifier
and bound parameters. It does not accept a command string. A caller therefore
*cannot express* an arbitrary command, regardless of intent or defect.

```
collect(target, command_id ∈ ALLOWLIST[platform], params) → artifact
```

Not:

```
collect(target, command_string)          ← this signature does not exist
```

This is the single most important design decision in this TRD. A string-accepting
interface makes G4 a matter of validation; an identifier-accepting interface
makes it a matter of type.

### 3.3 Session discipline

```
1  connect            SSH, host key verified against a pinned store
2  disable paging     platform-specific, from the allowlist
3  for each command_id:
       execute, capture, bound by output size and timeout
4  disconnect
```

Prohibited at every point:

- Entering configuration mode (`configure terminal`, `configure`, `edit`)
- Any write, commit, save, copy, or reload verb
- Interactive prompts requiring confirmation
- File transfer in either direction
- Shell escape

**Host key verification is mandatory and non-optional.** A collection session
that accepts an unknown host key may be collecting from an impostor, and every
finding derived from that artifact would be attributed to the wrong device.
First-contact keys are recorded and require assessor confirmation.

### 3.4 Credential handling

| Property | Requirement |
|---|---|
| Storage | Encrypted at rest with a key not stored alongside the ciphertext |
| Retrieval | **No interface or API returns credential material under any role** (NFR-SEC-003) |
| Scope | Bound to a platform set and an address range |
| Use | Decrypted in memory for the session duration only |
| Rotation | Supported without re-registration of targets |
| Logging | Credential identifiers are logged; material never is (NFR-OBS-006) |

### 3.5 Output bounding

Devices can emit unbounded output — `show tech-support` on a large chassis
exceeds hundreds of megabytes.

| Bound | Default | On breach |
|---|---|---|
| Per-command output size | 64 MB | Truncate, mark artifact `truncated`, record byte count |
| Per-command timeout | 300 s | Abort command, retain partial output marked `truncated` |
| Per-session duration | 900 s | Abort session, retain completed artifacts |

**INV-01.3-02.** A truncated artifact is marked as such and its export mode is
forced to `unknown`, which under DD-01.1-03 is treated as `terse`. Truncation
therefore lowers coverage rather than producing facts from an incomplete file
(G2).

### 3.6 Concurrency and estate impact

Collection touches production devices. Aggressive parallelism can degrade
management-plane responsiveness on the equipment being audited — an audit that
causes an incident is a failed audit.

| Control | Default |
|---|---|
| Global concurrent sessions | 20 |
| Per-device concurrent sessions | 1 |
| Inter-command delay | 100 ms |
| Retry on failure | 2, exponential backoff |
| Maintenance window | Optional; collection confined to a declared window |

**DD-01.3-02.** Defaults are deliberately conservative. An assessor may raise
them; the value used is recorded in the campaign so that a later performance
complaint can be correlated.

### 3.7 Custody metadata

Every collected artifact records:

```
collection_metadata {
  target_address, resolved_hostname
  platform_expected                  // from the target definition
  credential_ref                     // identifier only
  read_only_verified: bool
  collection_privilege: verified | unverified
  host_key_fingerprint, host_key_status: pinned | first_contact_confirmed
  commands_executed[]: command_id
  started_at, completed_at
  truncated: bool
  collector_identity
}
```

`commands_executed[]` records identifiers, providing an auditable record that
only allowlisted operations occurred.

### 3.8 Air-gapped deployments

In an air-gapped environment collection is typically unavailable, and file upload
is the sole channel. The collection subsystem is therefore **optional at
deployment** and its absence must not degrade any other capability.

**INV-01.3-03.** No assessment capability depends on collection. Every function
of the platform is reachable through file upload alone.

---

## 4. Interfaces

**Input**

```
CollectionRequest {
  campaign_id
  targets[]: {
     address, credential_ref
     platform_hint?                  // optimises command selection
  }
  artifacts[]: artifact_type          // requested types
  mode: "read_only"                   // only accepted value
  window?: { start, end }
  concurrency_override?
}
```

`mode` accepts exactly one value. Any other is rejected at the API boundary
(HTTP 422). The field exists so that the constraint is explicit in the contract
and visible in the API documentation, not because an alternative exists.

**Output:** per-target `CollectionResult`, each successful artifact entering
TRD-01.1 intake at step 2 (hash) with `received_from: live_collection`.

Failure reasons map directly to completeness reasons (TRD-01.1 §3.8):
`unreachable → no_response`, `auth_failed → auth_failed`,
`platform_mismatch → format_unrecognised`.

---

## 5. Edge cases

| Case | Handling |
|---|---|
| Device prompts for confirmation | Session aborts. No key is sent — a confirmation prompt implies a non-read operation was somehow reached |
| Paging not disabled, `--More--` appears | Detected; session aborts; artifact discarded as unreliable |
| Platform hint wrong; allowlist command invalid on the device | Command fails cleanly; recorded as `platform_mismatch` |
| Device reachable but heavily loaded, response slow | Timeout, partial artifact marked truncated |
| Jump host / bastion required | Supported as a declared proxy in the target definition; the proxy hop is recorded in custody |
| Device requires MFA for login | Not supported for automated collection. Recorded as `auth_unsupported`; the device falls back to file upload |
| Two targets resolve to the same device | Deduplicated by chassis serial at correlation (TRD-01.1) |
| Device in a maintenance window that expires mid-session | Session completes; overrun recorded |

**The MFA case matters operationally.** Devices with the strongest authentication
are frequently the ones that cannot be collected automatically — meaning the
best-secured devices are the most likely to appear in the missing list. This is
worth stating in the estate report rather than leaving as an unexplained gap.

---

## 6. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Write capability introduced by a code change | CI static analysis (V-01.3-002) | **Build fails.** Cannot reach release |
| Over-privileged collection account | Registration probe | Recorded; artifacts flagged; surfaced as an estate finding |
| Host key mismatch | Verification against the pinned store | Session refused; alerted — possible interception |
| Truncated output | Size or timeout bound | Artifact marked; export mode forced `unknown`; coverage falls |
| Collection degrades a production device | Operator report | Conservative defaults (DD-01.3-02); concurrency recorded per campaign |
| Credential material leaked to logs | Log scanning in CI | Build fails |

---

## 7. Verification

```
V-01.3-001   No write-capable code path exists
  Requirement  FR-ING-009, NFR-SEC-001, G4
  Method       UNIT + static analysis
  Procedure    Enumerate every call site of the transport layer. Assert each
               passes a command_id drawn from the compile-time ALLOWLIST
               constant. Assert no signature accepts a free-form command string.
  Acceptance   Zero call sites accepting arbitrary strings. Zero allowlist
               entries containing a configuration-mode, write, commit, copy,
               or reload verb.
  Severity     BLOCKING
```

```
V-01.3-002   CI blocks introduction of a write capability
  Requirement  G4
  Method       INTEGRATION (CI gate)
  Procedure    Introduce a branch adding `configure terminal` to the allowlist,
               and a second adding a string-accepting transport function.
  Acceptance   Both fail the build with an explicit G4 violation message.
  Severity     BLOCKING
  Note         This verifies the guarantee is enforced going forward, not
               merely satisfied today.
```

```
V-01.3-003   Transport rejects non-allowlisted operations
  Requirement  NFR-SEC-002, INV-01.3-01
  Method       UNIT
  Procedure    Attempt collection with a fabricated command_id, and with a
               command_id valid for a different platform.
  Acceptance   Both rejected before any connection is opened. No session
               established.
  Severity     BLOCKING
```

```
V-01.3-004   Read-only privilege is verified, not assumed
  Requirement  DD-01.3-01
  Method       INTEGRATION
  Procedure    Register two credentials against a lab device — one read-only,
               one privileged. Run the registration probe.
  Acceptance   read_only_verified true and false respectively. Artifacts from
               the privileged credential carry
               collection_privilege: unverified and produce an estate finding.
  Severity     MAJOR
```

```
V-01.3-005   Credential material is unretrievable
  Requirement  NFR-SEC-003
  Method       INTEGRATION + PROPERTY
  Procedure    Exercise every API endpoint and every UI view under every role,
               including Platform Administrator. Scan all responses, logs and
               error payloads for credential material.
  Acceptance   Zero occurrences.
  Severity     BLOCKING
```

```
V-01.3-006   Host key verification is enforced
  Requirement  §3.3
  Method       INTEGRATION
  Procedure    Collect from a lab device, then change its host key and
               collect again.
  Acceptance   Second attempt refused with a host-key-mismatch error.
               No artifact produced. Alert raised.
  Severity     BLOCKING
```

```
V-01.3-007   Truncation lowers coverage rather than producing facts
  Requirement  INV-01.3-02, G2
  Method       INTEGRATION
  Procedure    Collect with the size bound set below the device's actual
               configuration size.
  Acceptance   Artifact marked truncated; export_mode forced unknown;
               dependent controls return UNKNOWN. Zero PASS verdicts derived
               from the truncated region.
  Severity     BLOCKING
```

```
V-01.3-008   Confirmation prompt aborts the session
  Requirement  §5
  Method       UNIT (simulated device)
  Procedure    Simulated device emitting a confirmation prompt.
  Acceptance   Session aborts. No further bytes transmitted. Artifact
               discarded. Incident recorded.
  Severity     BLOCKING
```

```
V-01.3-009   No capability depends on collection
  Requirement  INV-01.3-03, NFR-DEP-001
  Method       INTEGRATION
  Procedure    Deploy with the collection subsystem absent. Execute a full
               campaign end to end via file upload only.
  Acceptance   All capabilities function. No degraded behaviour beyond the
               absence of live collection itself.
  Severity     BLOCKING
```

```
V-01.3-010   Custody metadata is complete and auditable
  Requirement  FR-ING-013
  Method       INTEGRATION
  Procedure    Collect from 10 lab devices.
  Acceptance   Every artifact records address, credential reference,
               host key fingerprint, commands_executed identifiers,
               timestamps and collector identity. commands_executed contains
               only allowlist identifiers.
  Severity     MAJOR
```

```
V-01.3-011   Concurrency limits are honoured
  Requirement  DD-01.3-02
  Method       PERFORMANCE
  Procedure    Collect from 200 simulated targets at default settings.
  Acceptance   Concurrent sessions never exceed 20 globally or 1 per device.
               The concurrency value used is recorded in the campaign.
  Severity     MINOR
```

---

## 8. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should collection be a separately deployable component that can be omitted entirely at install? | Physical separation strengthens G4 in air-gapped deployments and reduces attack surface, but complicates packaging. Current design: optional at deployment; INV-01.3-03 guarantees nothing depends on it |
| Q2 | Should the platform support MFA-gated collection via an operator-assisted flow? | Would cover well-secured devices that currently fall to file upload, but introduces an interactive path into an otherwise automated subsystem. Current design: unsupported; the gap is reported |
| Q3 | Should `show tech-support` be collected by default? | It supplies serials and version in one operation, satisfying FR-RPT-002 cleanly, but is large and slow and loads the device. Current design: individual commands by default; bundle on request |
