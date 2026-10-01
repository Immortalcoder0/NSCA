# 10 · Reporting

> The per-device PDF is the **mandated deliverable** of the problem statement. It
> is what an assessor actually hands over, and it is the artifact the entire
> system exists to produce. Everything else is supporting infrastructure.

---

## 1. What the problem statement requires

> *"Actionable Intelligence & PDF Reporting: A comprehensive, **single PDF report
> for each device**, covering:*
> - *Device Identification: Including **serial numbers and hardware details***
> - *Compliance Findings: Clear 'Pass/Fail' results with **risk severity
>   assessments***
> - *Remediation Paths: **Device-specific, step-by-step CLI command sequences***
> *...customised based on the device's **specific model and software version**"*

Four things follow, and three of them are frequently missed:

| Requirement | Consequence |
|---|---|
| **Single PDF per device** | The atomic deliverable is per-device, not an estate dashboard. Estate reporting is additive, never a substitute |
| **Serial numbers and hardware details** | Serial numbers are **not in the running configuration**. They come from `show version` / `show inventory`. This forces multi-artifact ingestion |
| **Risk severity assessments** | Not a static label — severity must be assessed, which implies context |
| **Customised to model and software version** | Remediation content must be keyed on version range, because IOS 12, IOS 15 and IOS-XE 17 differ |

---

## 2. Per-device report specification

Eight sections. Every one earns its place.

### Section 1 — Cover and identification

```
╔══════════════════════════════════════════════════════════════════╗
║  NETWORK SECURITY COMPLIANCE AUDIT REPORT                        ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  CORE-SW-01                                                      ║
║  Cisco Catalyst 9300-48P · IOS-XE 16.12.04                       ║
║                                                                  ║
║  Serial numbers                                                  ║
║    Chassis          FCW2140L0GH                                  ║
║    Line card 1      FOC2138Y0K2                                  ║
║    Line card 2      FOC2138Y0M9                                  ║
║    Power supply 1   ART2137F0PL                                  ║
║                                                                  ║
║  Role               Distribution switch                          ║
║  Exposure           Internal  (derived from topology)            ║
║  Location           DC-Mumbai / Rack B12                         ║
║                                                                  ║
║  ─────────────────────────────────────────────────────────────   ║
║  Campaign           Q3-2026 Core Infrastructure Audit            ║
║  Assessed           12 September 2026, 14:22 IST                 ║
║  Assessor           P. Sharma, Lead Assessor                     ║
║                                                                  ║
║  Frameworks                                                      ║
║    CIS Cisco IOS Benchmark          v4.1.0                       ║
║    NIST SP 800-53                   Rev 5                        ║
║    DISA STIG Cisco IOS-XE Router    2026-01 (Rel 13)             ║
║    ISO/IEC 27001                    2022                         ║
║                                                                  ║
║  Configuration source                                            ║
║    running-config.txt   sha256:3f9a…c21b   verbose export        ║
║    show-version.txt     sha256:7c04…19af                         ║
║    show-inventory.txt   sha256:e281…b30c                         ║
║    Collected 11 Sep 2026 by live collection · operator svc-audit ║
║                                                                  ║
║  Engine v2.4.0 · Rulepack cisco_iosxe@7.2.1 (Certified)          ║
║  Report hash 9a41…7f2e                                           ║
╚══════════════════════════════════════════════════════════════════╝
```

**If serial numbers cannot be determined, the section states so explicitly:**

```
  Serial numbers       NOT DETERMINED
    `show inventory` output was not supplied for this device.
    Supply it to complete device identification.
```

Silently omitting a mandated section is worse than declaring the gap.

---

### Section 2 — Executive summary

```
COMPLIANCE POSTURE

  Compliance          78%      112 pass / 143 determined
  Coverage            92%      143 determined / 155 applicable
  Meaningful passes   64%      72 of 112 configured, 40 vacuous

  Security posture    61%      compliance adjusted for exposure,
                               known vulnerabilities, unaudited surface

  ┌──────────────────────────────────────────────────┐
  │ ████████████████████████░░░░░░░  PASS       112  │
  │ ██████░░░░░░░░░░░░░░░░░░░░░░░░░  FAIL        31  │
  │ ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░  UNKNOWN     12  │
  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  N/A         14  │
  └──────────────────────────────────────────────────┘

  Severity     Critical  3    High  11    Medium  14    Low  3

──────────────────────────────────────────────────────────────────
TOP 5 PRIORITY REMEDIATIONS
Ranked by attack-path contribution, not by severity label.
Resolving these five makes 23 of 31 findings unreachable.

  1  F-000518  Remove 0.0.0.0/0 from group `Partners`      1 cmd · safe
  2  F-000412  Disable Telnet on VTY lines           3 cmds · lockout-risk
  3  F-000603  Replace type 7 credential            2 cmds · svc-affecting
  4  F-000701  Configure remote logging                    2 cmds · safe
  5  F-000455  Set session idle timeout                    2 cmds · safe
```

The **top-five block is the most important element of the report.** It is the
only part many readers will act on.

---

### Section 3 — Findings

One entry per finding, ordered by effective severity within attack-path
contribution.

```
──────────────────────────────────────────────────────────────────
NSCA-MGMT-002    Plaintext management protocols must be disabled
                                                             FAIL
Severity   HIGH → CRITICAL
           Elevated: this device terminates an external circuit

Frameworks CIS-IOS-1.2.4 · NIST AC-17, SC-8
           STIG V-216644 (CAT I) · ISO 27001 A.9.4.2

EVIDENCE   running-config.txt, lines 141–145

    141 │ line vty 0 4
    142 │  login local
  ▸ 143 │  transport input telnet ssh          ← Telnet permitted
    144 │  exec-timeout 0 0
    145 │ !

  Facts    mgmt.protocols.telnet.enabled = true
           source: explicit · extractor: cisco_iosxe.vty.transport_input@7

IMPACT     Credentials transit the network in cleartext. Any party able
           to observe traffic between the management station and this
           device obtains privilege-15 credentials.

           This finding is an enabling link in attack path AP-003.

REMEDIATION → see R-000412, Section 5
──────────────────────────────────────────────────────────────────
```

**Every finding shows the configuration excerpt with the relevant line
highlighted.** *"If I cannot point at the line, it is an opinion."*

Framework conflicts are stated where they occur:

```
NSCA-MGMT-004    Session idle timeout                        FAIL
  Device value              600 s
  CIS-IOS-1.1.5 requires  ≤ 600 s   → PASS
  STIG V-216620 requires  ≤ 300 s   → FAIL
  Applied: STIG (stricter)          → FAIL
  ⚠ Framework conflict; reported against the stricter requirement.
```

---

### Section 4 — Emergent findings

Findings arising from relationships rather than individual statements. They carry
a **counterexample** instead of a highlighted line.

```
──────────────────────────────────────────────────────────────────
NSCA-GRAPH-004   Management plane reachable from untrusted zone
                                                             FAIL
Severity   CRITICAL

⚠ No individual configuration statement on any device involved is
  non-compliant. This violation is emergent from the combination.

COUNTEREXAMPLE
  203.0.113.5:44210  →  10.0.0.1:22  TCP    is permitted

  zone[external]
    → EDGE-FW-01 interface Gi0/1
    → rule `outside-in` line 14              (EDGE-FW-01:1204)
    → address group `Trusted-Admins`
    → nested group `Partners`
    → member 0.0.0.0/0                       ← over-broad
    → CORE-SW-01 interface Vlan1
    → management plane

CONTRIBUTING DEVICES   EDGE-FW-01 · CORE-SW-01
──────────────────────────────────────────────────────────────────
```

---

### Section 5 — Remediation playbook

Version-specific, dependency-ordered, safety-classified.

```
──────────────────────────────────────────────────────────────────
REMEDIATION PLAYBOOK
Target: CORE-SW-01 · Cisco IOS-XE 16.12.04

Commands below are specific to this model and software version.

STEP 1  Configure central authentication            IMPACT: SAFE
  aaa new-model
  aaa authentication login default group tacacs+ local
  Addresses F-000603 · prerequisite for Step 4
  Rollback: no aaa new-model

STEP 2  Restrict management transports              IMPACT: SAFE
  line vty 0 15
  Rollback: n/a — enters configuration context only

STEP 3  Disable plaintext transports        IMPACT: LOCKOUT RISK
   transport input ssh
  ⚠ Terminates all active Telnet sessions, including yours if you
    are currently connected over Telnet.
  ⚠ Verify SSH access before applying.
  Addresses F-000412
  Rollback:  transport input telnet ssh

STEP 4  Remove reversible credential     IMPACT: SERVICE-AFFECTING
  no username admin password 7 0822455D0A16
  username admin privilege 15 algorithm-type scrypt secret <NEW>
  ⚠ Requires Step 1 verified working.
  Addresses F-000603
  Rollback:  username admin privilege 15 password 7 0822455D0A16

──────────────────────────────────────────────────────────────────
LOCKOUT ANALYSIS

  Assessor source            10.20.5.44
  Proposed management ACL    10.0.0.0/8, 10.20.0.0/16
  Result                     ✅ PERMITTED — access retained

  ⚠ If applying from a different source, verify inclusion first.

──────────────────────────────────────────────────────────────────
DRY RUN — modelled outcome, not applied

  Compliance   78% → 94%
  Coverage     92% → 92%   (unchanged)

  Resolved     14 findings
  ⚠ NEWLY FAILING (1)
     NSCA-AUTH-009 · Local fallback account must exist
     Step 4 removes the only local account. If TACACS becomes
     unreachable, the device will be unreachable.
     → Create a local emergency account before Step 4.
──────────────────────────────────────────────────────────────────
```

**The dry-run section is what converts a sceptical administrator.** No audit
report has ever warned them that a recommended fix would break something else.

---

### Section 6 — Unassessed

The section no competing product contains, and the one that makes the rest of the
report credible.

```
──────────────────────────────────────────────────────────────────
UNASSESSED

12 controls could not be determined (7.7% of applicable controls).

  ▸ 8 — required facts absent, platform default unverified
        NSCA-CRYPTO-003  crypto.ssh.ciphers
        NSCA-CRYPTO-004  crypto.ssh.macs
        ...
        Cause: this platform's cipher defaults are undocumented for
        IOS-XE 16.12. Explicit configuration would resolve this.

  ▸ 3 — configuration export incomplete
        Cause: `show running-config` omits settings at default.
        Resolution: re-collect with `show running-config all`.

  ▸ 1 — parse gap
        `crypto ikev2 policy` block not covered by any extractor.
        → queued for training.

UNAUDITED CAPABILITIES

  ▸ Embedded web management, TCP/8443
    Outside the scope of all four selected frameworks. Not assessed
    by any control.
    Properties observed: listens · authenticates · mutates
    → 6 management-plane controls downgraded to PASS (PARTIAL)

──────────────────────────────────────────────────────────────────
⚠ COVERAGE STATEMENT
  This assessment determined 92% of applicable controls. It is not a
  statement that the remaining 8% are compliant. An unexamined
  control is not a passing control.
──────────────────────────────────────────────────────────────────
```

---

### Section 7 — Assessor notes

Attributable, timestamped annotations, and the adjudication record.

```
2026-09-19  p.sharma
  Finding F-000418 disputed by r.kulkarni on grounds of network
  isolation. Compensating control REFUTED by platform verification —
  Gi0/8 bridges VLAN 250 and VLAN 40. Dispute rejected; finding stands.

2026-09-20  p.sharma
  Finding F-000455 accepted as risk, expiring 2027-03-31. Legacy NMS
  dependency, replacement under project NET-2291.
```

---

### Section 8 — Appendix

```
A · Complete fact inventory with provenance (84 facts)
B · Control results in full (155 controls)
C · Knowledge base versions
      engine            v2.4.0
      rulepack          cisco_iosxe@7.2.1        Certified
      control pack      nsca-core@3.1.0
      CIS               cisco_ios_15@4.1.0
      STIG              cisco_iosxe_router@2026-01
      NIST              800-53@Rev5
      schema registry   v1.8.0
D · Chain of custody
E · Reproducibility manifest
```

#### The reproducibility manifest

```yaml
report_id:   RPT-2026Q3-CORE-SW-01-001
generated:   2026-09-12T14:22:31Z
inputs:
  - { artifact: running-config.txt, sha256: 3f9a...c21b }
  - { artifact: show-version.txt,   sha256: 7c04...19af }
  - { artifact: show-inventory.txt, sha256: e281...b30c }
knowledge_base:
  engine: v2.4.0
  rulepacks:     [ { id: cisco_iosxe, version: 7.2.1, tier: certified } ]
  control_packs: [ { id: nsca-core,   version: 3.1.0 } ]
  frameworks:
    - { id: cis,  benchmark: cisco_ios_15,        version: 4.1.0 }
    - { id: stig, benchmark: cisco_iosxe_router,  release: 2026-01 }
    - { id: nist, catalog: 800-53, revision: Rev5 }
  schema_registry: v1.8.0
report_hash: 9a41...7f2e

statement: >
  Re-executing with identical inputs and knowledge base versions will
  produce a byte-identical report.
```

---

## 3. The estate report

Additive to — never a substitute for — the per-device PDFs.

```
ESTATE COMPLIANCE REPORT
Campaign Q3-2026 Core Infrastructure Audit

1 · COLLECTION COMPLETENESS
    In scope                412
    Collected               389   (94.4%)
    Not collected            23
      • 14  no response                    owner NOC-Mumbai
      •  6  credentials expired            owner IAM team
      •  3  format unrecognised            → training queued
    ⚠ This audit does not cover 5.6% of defined scope.

    Export quality
       342  verbose (complete)
        47  terse — 34 controls unassessable on these devices

2 · POSTURE
    Compliance    81%      Coverage      89%
    Meaningful    67%      Security      64%

    By platform
       Cisco IOS-XE     142 devices    84%    coverage 94%
       Juniper JunOS     88 devices    79%    coverage 91%
       FortiOS           71 devices    83%    coverage 88%
       PAN-OS            44 devices    88%    coverage 92%
       Arista EOS        41 devices    76%    coverage 90%
       MikroTik           3 devices    62%    coverage 71%  ⚠ local rulepack

3 · SYSTEMIC FINDINGS
    SF-004  NSCA-MGMT-007 fails identically on 31 of 40 branch routers.
            All share an identical management ACL block; all commissioned
            2024-03 to 2025-11.
            Assessment: build-template defect, not 31 independent errors.
            → Correct the template, then remediate the 31.

4 · ATTACK PATHS
    3 chains reach the core management plane from external zones.
    Breaking 6 findings eliminates all 3 chains and makes 187 of 241
    findings unreachable.

5 · UNAUDITED SURFACE
    7 devices expose management capabilities outside all selected
    frameworks. 23 controls downgraded to PASS (PARTIAL).

6 · KNOWN VULNERABILITIES
    4 devices run firmware with published critical vulnerabilities.
    Not covered by any selected framework — this is the compliance /
    security divergence.

7 · REMEDIATION STATUS
    Open 241 · Assigned 198 · Accepted risk 12 (2 expiring < 30 days)
    Verified closed 34 · Regressed since Q2 3

8 · COMPARISON WITH Q2-2026
    Q2 78%  →  Q3 81%
      +5 pp  verified remediations (34 findings)
      −3 pp  benchmark updated STIG 2025-10 → 2026-01
      +1 pp  scope change (12 devices decommissioned)
```

**Section 8 is the one no competing product provides.** *"You got worse"* and
*"the bar moved"* are different facts.

---

## 4. Machine-readable exports

| Format | Purpose | Requirement |
|---|---|---|
| **JSON** | Full findings with evidence, provenance, mappings | MUST |
| **CSV** | Ticketing and spreadsheet workflows | MUST |
| **NIST OSCAL** | Standards-native assessment-results interchange | SHOULD |
| **DOCX** | Editable report for assessor customisation | SHOULD |
| **Patch bundle** | Signed remediation sequences for the network team's own change process | MAY |

### 4.1 Patch bundle

```
remediation-CORE-SW-01-2026Q3.bundle
├── manifest.yaml         device, campaign, findings addressed, hashes
├── signature.sig
├── steps.txt             ordered commands, annotated with impact
├── rollback.txt          reverse sequence
├── prerequisites.md      what must be verified first
└── verification.md       how to confirm the fix
```

**The platform never applies this.** It is a document for the network team's own
change process. Assessor independence is architectural
([04 §6](04-system-architecture.md)).

---

## 5. Report generation requirements

| # | Requirement |
|---|---|
| RPT-1 | Generation **MUST** be deterministic — identical inputs produce byte-identical output |
| RPT-2 | No content may be recomputed at render time; the report renders stored assessment results |
| RPT-3 | Issued reports are immutable; corrections are issued as **linked amendments** |
| RPT-4 | Every report states the trust tier of every rulepack used |
| RPT-5 | Findings derived from **provisional** rulepacks **MUST NOT** appear in an issued report |
| RPT-6 | Reports **MUST** state every framework and version evaluated against |
| RPT-7 | Reports **MUST** be generatable entirely offline |
| RPT-8 | Every excerpt **MUST** reproduce the configuration verbatim, with line numbers |
| RPT-9 | Secrets appearing in evidence excerpts **MUST** be masked, with masking noted |
| RPT-10 | Reports **MUST** be legible in monochrome print — severity must never be conveyed by colour alone |

**RPT-9 is easy to miss.** A finding about a reversible password must show enough
of the line to be verifiable, without reproducing the credential:

```
  ▸ 6 │ username admin privilege 15 password 7 08224••••••
                                                    ↑ masked
```

---

## 6. Design principles

| # | Principle | Rationale |
|---|---|---|
| 1 | Lead with what to do, not what is wrong | Readers act on the first page or not at all |
| 2 | Every finding carries verifiable evidence | Defensibility under challenge |
| 3 | State coverage as prominently as compliance | Compliance without coverage is meaningless |
| 4 | Declare what was not assessed | An unexamined control is not a passing control |
| 5 | Remediation is safe before it is correct | The administrator's deepest fear |
| 6 | Report root causes, not symptom counts | Thirty-one findings, one build template |
| 7 | Separate posture movement from standard movement | A number that cannot be explained cannot be defended |
| 8 | The report must stand alone | The reader may have no access to the platform |
