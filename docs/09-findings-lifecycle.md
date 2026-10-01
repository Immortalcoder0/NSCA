# 09 · Findings and Their Lifecycle

> A finding is not a static fact. It is an assertion that gets challenged,
> adjudicated, assigned, fixed, verified and closed — and every step of that must
> be attributable. This is the difference between an audit platform and a
> scanner.

---

## 1. The verdict model

Four verdicts. Most tools have two, and that is the root of their dishonesty.

| Verdict | Meaning | Counts toward compliance? |
|---|---|---|
| **PASS** | Checked; compliant | Yes — numerator and denominator |
| **FAIL** | Checked; violating | Yes — denominator only |
| **UNKNOWN** | Could not be determined | Denominator only; reduces coverage |
| **NOT_APPLICABLE** | The control does not apply to this platform or capability | Excluded entirely |

### 1.1 Why UNKNOWN must exist

Every competing tool silently converts *"I could not parse this"* into *"no
violation found."*

That manufactures false assurance on **precisely the devices it understands
least**. A green report on a device that was never actually read is worse than no
report, because it ends the investigation.

The architecture makes UNKNOWN automatic rather than optional: a control declares
the facts it requires, and if any is missing or carries `default_unknown`
provenance, the verdict is UNKNOWN. It cannot be bypassed by an implementer in a
hurry.

### 1.2 Why NOT_APPLICABLE must be distinct

- `UNKNOWN` — *"this device may or may not be secure in this respect and I could
  not tell."* A gap.
- `NOT_APPLICABLE` — *"this device has no such capability; the question is
  meaningless."* Not a gap.

A layer-2 access switch with no routing engine should not be scored against
routing-protocol authentication controls, and should not receive free credit for
them either. Conflating these corrupts the compliance figure in both directions.

### 1.3 Coverage score

```
                applicable controls determined
  coverage  =  ───────────────────────────────
                    applicable controls

  applicable = total − NOT_APPLICABLE
  determined = PASS + FAIL
```

Reported alongside compliance on every device and in every report:

```
Compliance   78%   (112 PASS / 143 determined)
Coverage     92%   (143 determined / 155 applicable)
```

> Compliance without coverage is meaningless. 100% compliance at 20% coverage is
> not a good result; it is an unfinished audit.

---

## 2. Pass quality

### 2.1 Meaningful versus vacuous

Two devices both pass the SNMP control:

- **Device A** passes because SNMPv3 is configured with authentication and
  privacy
- **Device B** passes because SNMP is simply not enabled

Identical green tick. Entirely different meaning — and **B's pass is fragile.**
Nothing constrains SNMP on B. The moment anyone enables it, the device becomes
non-compliant silently, and the last report said everything was fine.

```yaml
vacuity:
  meaningful_when: "snmp.enabled == true"
```

Reported as:

```
Compliance          94%
  meaningful        63%    ← feature present and securely configured
  vacuous           31%    ← feature absent or disabled
```

**Anticipated objection:** *"If SNMP is disabled, the device is secure. Why is
that a weaker pass?"*

**Answer:** it is not less secure today; it is **less assured tomorrow.** A
vacuous pass carries no configured control — only an absent feature. It tells you
nothing about what happens when the feature is enabled, and it will not warn you
when it is. The distinction is about the durability of the assurance, not the
current state.

### 2.2 Scope contamination

The most important safety property in the finding model.

**A capability the system cannot assess can render an existing PASS wrong without
ever producing a FAIL.**

```
NSCA-MGMT-002 · Plaintext management protocols disabled
   telnet = false ✓   http = false ✓   ftp = false ✓
   → PASS
```

Except the device also runs `winbox` on TCP/8291 — a second management path no
control contemplates. The conclusion *"management access on this device is
secure"* is **technically true and practically false.** You verified the doors you
knew about while a window stood open.

This is worse than a FAIL, because a FAIL gets remediated and this gets filed as
evidence of compliance.

**Therefore:** an unassessed capability in a control family downgrades every
passing control in that family.

```
NSCA-MGMT-002 → PASS (PARTIAL)
  ⚠ An unassessed management capability exists (winbox/8291).
    This control's conclusion covers only the protocols it evaluates.
```

Findings are **not independent**. Discovering something new re-opens questions
previously considered closed.

---

## 3. The finding object

```yaml
finding_id:   F-2026Q3-000412
campaign:     Q3-2026-Core
device:       CORE-SW-01

control:      NSCA-MGMT-002
title:        Plaintext management protocols must be disabled
verdict:      FAIL

severity:
  base:       high
  effective:  critical
  reason:     "device.exposure == internet_facing"

evidence:
  - artifact: CORE-SW-01/running-config.txt
    lines:    [141, 145]
    highlight: [143]
    excerpt: |
      141 │ line vty 0 4
      142 │  login local
      143 │  transport input telnet ssh      ← Telnet permitted
      144 │  exec-timeout 0 0
      145 │ !
    facts:
      - { path: mgmt.protocols.telnet.enabled, value: true,
          provenance: { source: explicit, extractor: cisco_ios.vty.transport_input@v7 } }

frameworks:
  - { framework: CIS,  id: CIS-IOS-1.2.4,  version: "4.1.0" }
  - { framework: NIST, id: AC-17,          revision: "Rev5" }
  - { framework: NIST, id: SC-8,           revision: "Rev5" }
  - { framework: STIG, id: V-216644,       release: "2026-01", category: "CAT I" }
  - { framework: ISO,  id: A.9.4.2 }

impact: >
  Credentials transit the network in cleartext. Any party able to observe
  traffic between the management station and this device obtains
  privilege-15 credentials.

attack_paths: [AP-003, AP-007]
attack_path_role: "enabling link in AP-003; removal breaks the chain"

remediation_ref: R-2026Q3-000412
rulepack_trust:  certified

state:        Confirmed
owner:        r.kulkarni
due:          2026-09-25
history:      [ ... ]
```

### 3.1 Evidence is mandatory

> **"If I cannot point at the line in the configuration, it is not a finding —
> it is an opinion."** — Lead Assessor persona

Every finding **MUST** carry artifact identity, line range, the surrounding
excerpt, and the specific facts with their provenance. A finding without evidence
cannot survive challenge and therefore has no value to an auditor.

### 3.2 Evidence for graph findings

Emergent findings cannot point at a single line, because no single line is wrong.
They emit a **counterexample** instead:

```yaml
finding_id: F-2026Q3-000518
control:    NSCA-GRAPH-004
title:      Management plane reachable from untrusted zone
verdict:    FAIL

counterexample:
  packet:  { src: 203.0.113.5, sport: 44210, dst: 10.0.0.1, dport: 22, proto: tcp }
  path:
    - { node: "zone[external]" }
    - { node: "interface[Gi0/1]",  device: EDGE-FW-01 }
    - { node: "rule[outside-in]:14", action: permit, artifact_lines: [1204] }
    - { node: "group[Trusted-Admins]" }
    - { node: "group[Partners]",   note: "nested membership" }
    - { node: "0.0.0.0/0",         note: "over-broad member" }
    - { node: "interface[Vlan1]",  device: CORE-SW-01 }
note: >
  No individual configuration statement on either device is non-compliant.
  The violation is emergent from the combination.
```

A concrete packet plus the exact rule chain is a categorically different class of
evidence from *"possible misconfiguration detected."*

---

## 4. The lifecycle state machine

```
                    ┌──────────────────────────────────────┐
                    │                                      │
    NEW ──► CONFIRMED ──► ASSIGNED ──► REMEDIATED ──► VERIFIED ──► CLOSED
     │           │            ▲             │             │
     │           │            │             │ (not        │
     │           │            └─────────────┘  confirmed) │
     │           │                                        │
     ├──► DISPUTED ──► adjudicated ──┬──► CONFIRMED       │
     │                               └──► WITHDRAWN ──────┤
     │                                                    │
     └──► RISK_ACCEPTED ──► (expiry) ──► reopens ─────────┘
```

| State | Meaning | Who |
|---|---|---|
| `New` | Produced by assessment, not yet triaged | System |
| `Confirmed` | Assessor accepts it as a genuine finding | Assessor |
| `Disputed` | Administrator challenges it with a stated reason | Administrator |
| `Withdrawn` | Adjudicated as not a genuine finding | Lead Assessor |
| `Risk Accepted` | Accepted with owner, justification, expiry, compensating control | Lead Assessor |
| `Assigned` | Allocated to an owner with a due date | Assessor |
| `Remediated` | Owner asserts the fix is applied | Administrator |
| `Verified` | Re-assessment confirms the control now passes | System |
| `Closed` | Finding resolved and evidence retained | System |

**Every transition records actor, timestamp and reason.** This is the audit trail
on which the assessor's own professional defensibility rests.

---

## 5. Dispute and adjudication

The adversarial relationship between auditors and administrators is the reason
compliance programmes fail in practice. Today the dispute happens in email and
dies in a spreadsheet with no attribution.

```yaml
dispute:
  finding:    F-2026Q3-000418
  raised_by:  r.kulkarni
  raised_at:  2026-09-18T11:02:00Z
  type:       compensating_control
  claim: >
    Telnet is enabled on MGMT-SW-04, but the device resides on an isolated
    out-of-band management network and is unreachable from any user network.
```

Dispute types:

| Type | Claim |
|---|---|
| `false_positive` | The tool misread the configuration |
| `compensating_control` | The risk is mitigated elsewhere |
| `not_applicable` | The control does not apply to this device |
| `accepted_risk` | Understood and formally accepted |
| `already_remediated` | Fixed after collection |

---

## 6. Machine-verified compensating controls

**This is the capability that changes the relationship between assessor and
administrator, and no competing product has it.**

Normally the assessor accepts the claim on faith and records it in a spreadsheet.
Instead, the platform checks it against the configuration graph.

### 6.1 Refuted

```
Claimed compensating control
  Device reachable only from OOB management network 10.250.0.0/24

Verification:  ❌ REFUTED

  MGMT-SW-04 interface Gi0/8 bridges VLAN 250 and VLAN 40 (user network).
  Counterexample:  10.40.7.19 → 10.250.0.11:23 TCP is permitted
  Rule chain:      SW-Core-02 acl[user-out]:22 → permit

  The claimed compensating control does not exist.

Assumptions
  • Based on 389 of 412 in-scope devices. 23 devices were not collected;
    additional paths through those devices cannot be excluded.
  Confidence: medium
```

The administrator did not know about `Gi0/8`. Somebody added it during an
incident eighteen months ago and never removed it.

**The auditor asserts; the system checks.** This converts an adversarial exchange
into a shared discovery.

### 6.2 Confirmed

```
Verification:  ✅ CONFIRMED

  No path exists from any non-management zone to 10.250.0.0/24 across the
  389 collected devices.

  → Recommend Risk Accepted with expiry 2027-03-31 and this verification
    attached as supporting evidence.
```

### 6.3 Unverifiable

```
Verification:  ⚠ UNVERIFIABLE

  The claim depends on physical network segmentation, which cannot be
  determined from configuration. Manual verification required.
```

**Three outcomes, never two.** The system states what it cannot determine here,
exactly as it does for control verdicts.

---

## 7. Risk acceptance

Real compliance programmes run on risk acceptance and compensating controls. A
tool that pretends every finding must be fixed was built by someone who has never
run one.

```yaml
risk_acceptance:
  finding:      F-2026Q3-000418
  accepted_by:  p.sharma            # must be a Lead Assessor
  accepted_at:  2026-09-20
  expires:      2027-03-31          # MANDATORY — no indefinite acceptance
  justification: >
    Device is on an isolated OOB management network. Legacy NMS requires
    Telnet. Replacement scheduled Q1 2027 under project NET-2291.
  compensating_control:
    claim:        "Network isolation of 10.250.0.0/24"
    verification: CONFIRMED
    verified_at:  2026-09-19
  review_required_by: p.sharma
```

**Rules:**

- Expiry is mandatory. Indefinite acceptance is how findings disappear
- On expiry the finding automatically returns to `Confirmed`
- Only a Lead Assessor may accept risk
- Reports distinguish **three** states — passing, failing, and accepted risk with
  days remaining — never two
- Accepted risks appear in the estate report as a tracked population with an
  ageing profile

---

## 8. Remediation verification

Closing the loop. Currently, verification means taking the network team's word.

```
1. Administrator marks F-2026Q3-000412 as Remediated
2. Assessor triggers re-collection of CORE-SW-01
3. Platform re-assesses using the same knowledge base version
4. Platform checks the specific control's verdict
```

| Outcome | Action |
|---|---|
| Control now PASS | → `Verified` → `Closed`, new evidence attached |
| Control still FAIL | → back to `Assigned` with a note and the new evidence |
| Control now UNKNOWN | → `Assigned` with a coverage warning — a fix must not be accepted on the basis of a device becoming unreadable |

That third row matters. If remediation coincides with a configuration export
becoming less complete, the finding must not silently close.

```yaml
verification:
  finding:        F-2026Q3-000412
  verified_at:    2026-09-27T09:14:00Z
  artifact_before: sha256:3f9a...c21b
  artifact_after:  sha256:8b12...4de7
  verdict_before:  FAIL
  verdict_after:   PASS
  evidence_after:
    lines: [143]
    excerpt: " transport input ssh"
  knowledge_base: identical      # required — otherwise the comparison is invalid
```

**The knowledge base must be identical between assessment and verification.**
Otherwise you cannot distinguish a genuine fix from a changed rule.

---

## 9. Cross-campaign tracking

Findings persist across campaigns by identity (device + control), enabling:

| Signal | Meaning |
|---|---|
| **Recurrence** | Closed in Q2, present again in Q3 — the fix did not hold |
| **Regression** | Passed in Q2, fails in Q3 — the configuration changed for the worse |
| **Ageing** | Open for N days across M campaigns |
| **Expiring acceptance** | Accepted risks approaching expiry |
| **Chronic** | Open across three or more consecutive campaigns |

```
Finding history · CORE-SW-01 / NSCA-MGMT-002

  Q1 2026   FAIL     new
  Q2 2026   FAIL     assigned, not remediated
  Q3 2026   PASS     verified 2026-09-27
  Q4 2026   FAIL     ⚠ REGRESSION — reintroduced after remediation
```

A regression after a verified fix is a far stronger signal than a new finding: it
indicates a process failure, not merely a configuration defect.

---

## 10. Systemic findings

An auditor's most valuable output is frequently *"you have one problem, not
thirty-one."*

When the same control fails identically across many structurally similar devices,
the estate report presents a single root cause:

```
SYSTEMIC FINDING  SF-2026Q3-004

  NSCA-MGMT-007 fails identically on 31 of 40 branch routers.
  All 31 share an identical management ACL block.
  All 31 were commissioned between 2024-03 and 2025-11.

  Assessment:  build-template defect, not 31 independent errors

  Recommended action
    1. Correct the build template
    2. Remediate the 31 affected devices
    3. Verify the 9 unaffected devices were built from a corrected template

  Affected: BR-RTR-001, BR-RTR-002, ... (31)
```

Detection: cluster failing findings by `(control, platform, normalised evidence
pattern)` and report clusters above a threshold as systemic.

---

## 11. Prioritisation

A flat list of 400 findings sorted by a static severity label is not actionable —
the administrator reads the first ten and closes it.

### 11.1 Effective severity

```
effective = base severity, modulated by risk_modifiers evaluated
            against device.exposure and capability context
```

### 11.2 Attack-path contribution

```
ATTACK PATH  AP-003
  External untrusted zone → core management plane

  Link 1  F-000412  Telnet enabled on EDGE-FW-01          critical
  Link 2  F-000518  Over-broad group in outside-in ACL    high
  Link 3  F-000603  Reversible credential on CORE-SW-01   high

  Breaking any single link breaks the chain.
  Lowest-cost link: F-000518 — one command, impact: safe
```

### 11.3 The headline

```
TOP 5 REMEDIATIONS
Resolving these 5 findings makes 23 of 31 findings unreachable.

  1  F-000518   Remove 0.0.0.0/0 from group Partners     1 cmd   safe
  2  F-000412   Disable Telnet on EDGE-FW-01             3 cmds  lockout-risk
  ...
```

This answers the question an administrator actually has — *"I have Thursday
afternoon, what do I fix?"* — rather than the question a scanner answers.

---

## 12. Compliance posture versus security posture

The uncomfortable truth of the compliance industry: **a device can pass 100% of a
benchmark and still be running firmware with a known unauthenticated remote code
execution flaw.** Perfect green report, fully compromised device.

And the converse: a device fails *"SSH idle timeout must be 5 minutes"* while
sitting on an isolated management network nothing can reach. Technically true
finding. Practically noise.

Most tools conflate these because compliance is what they can measure.

```
Compliance posture   94%   ← conformance to selected frameworks
Security posture     61%   ← compliance, adjusted for exposure,
                              known vulnerabilities, unaudited surface

Divergence explained
  • 2 devices run firmware with published critical vulnerabilities
    (not covered by any selected framework)
  • 7 devices expose unaudited management capabilities
  • 12 findings are on isolated devices with negligible exposure
```

A tool with a point of view, and one that costs nothing architecturally — the
model already holds everything required. It simply refuses to pretend one number
is the other.
