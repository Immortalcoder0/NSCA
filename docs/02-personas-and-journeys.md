# 02 · Personas and Journeys

---

## 1. Why this document exists

The problem statement names the user precisely: administrators managing hybrid
networks who *"lack a centralized 'Source of Truth' for compliance."* This is an
**audit** product. Every design decision in this specification serves the act of
auditing an estate and producing defensible evidence.

The most common failure mode in compliance tooling is building a *scanner* and
calling it an *audit platform*. A scanner answers one question — *"is this file
compliant right now?"* An auditor must answer six:

1. What is in scope, and did I actually cover it?
2. What did I find, and with what evidence?
3. What did I decide about each finding, and why?
4. What did the network team fix, and did I verify it?
5. How does this compare to last cycle, and why did it change?
6. Can I defend all of the above in twelve months?

---

## 2. Personas

### 2.1 Lead Assessor — *primary user*

**Priya, 34 · Senior Security Auditor · CISA certified**

Runs quarterly compliance audits across a 400-device estate spanning six vendors.
Reports to the CISO and answers to an external regulator. Strong on compliance
frameworks and audit methodology; competent but not expert on any individual
vendor's command line.

| | |
|---|---|
| **Goal** | Issue a defensible, complete, evidence-backed audit within the engagement window |
| **Measured on** | Coverage of scope, defensibility under challenge, findings actually remediated |
| **Frustrations** | Chasing network teams for configurations. Spreadsheet-based tracking. Being unable to prove a finding when challenged. Discovering after issuance that a device was never actually assessed |
| **Deepest fear** | Signing off an audit that later proves to have missed something material |
| **Says** | *"If I can't point at the line in the config, it isn't a finding — it's an opinion."* |

**What Priya needs that a scanner does not provide:** scope tracking, collection
completeness, evidence with line numbers, an adjudication trail, remediation
verification, and reproducibility months later.

---

### 2.2 Network Administrator — *primary collaborator, sceptical*

**Rahul, 41 · Principal Network Engineer**

Operates the estate. Knows Cisco IOS and FortiOS deeply, MikroTik from a previous
role. Has been handed audit reports before and found them full of items that
were irrelevant, already mitigated, or outright wrong. His trust is finite and
already partially spent.

| | |
|---|---|
| **Goal** | Not break production. Fix genuine problems. Not waste days on false positives |
| **Frustrations** | 400-item reports with no prioritisation. Findings with no evidence. Remediation advice that would sever his own management session. Auditors who don't understand the environment |
| **Deepest fear** | Applying a recommended fix at 2am and locking himself out of a device in another city |
| **Says** | *"Tell me which five things actually matter, and tell me the fix won't take the site down."* |

**What Rahul needs:** prioritisation by real risk, evidence he can verify
himself, remediation that is ordered and safety-checked, and the ability to
dispute a finding with a documented reason rather than an argument over email.

**Rahul is also the person who teaches the system unfamiliar platforms.** The
training interface must be usable by someone who administers devices and has
never written a line of code. This is a hard design constraint, not an aspiration.

---

### 2.3 Security Manager — *reporting consumer*

**Anjali, 47 · Head of Information Security**

Accountable for the organisation's security posture to the board and to
regulators. Does not read device configurations. Needs trend, exposure, and
assurance.

| | |
|---|---|
| **Goal** | Know the estate's true posture. Demonstrate improvement. Direct limited remediation budget at the highest-return items |
| **Frustrations** | A compliance percentage that means nothing. Not knowing whether a drop is real degradation or a changed benchmark. Numbers she cannot defend upward |
| **Says** | *"Is 78% good? Compared to what? And what happens if we only fix ten things?"* |

**What Anjali needs:** estate-level posture, systemic root-cause findings,
remediation burn-down, and the ability to distinguish *"we got worse"* from
*"the standard changed."*

---

### 2.4 Platform Administrator — *operator of the tool itself*

**Vikram, 29 · Security Engineering**

Deploys and maintains the platform. Manages rulepacks, imports framework updates,
administers users and access.

| | |
|---|---|
| **Goal** | Keep content current, keep the deployment secure and offline-capable, ensure taught knowledge is correct |
| **Frustrations** | Framework updates that silently change last quarter's results. No visibility into what the system can and cannot parse |
| **Says** | *"Before I ratify this STIG release, show me exactly which findings change."* |

---

## 3. Jobs to be done

Framed as outcomes rather than features.

| # | Job | Persona | Success looks like |
|---|---|---|---|
| J1 | Establish what is in scope and prove I covered it | Priya | Collection completeness report; uncollected devices tracked with owners |
| J2 | Assess devices consistently regardless of vendor | Priya | Same controls, same rigour, across six platforms |
| J3 | Produce evidence that survives challenge | Priya | Every finding cites artifact and line numbers |
| J4 | Know what the tool could *not* determine | Priya | Coverage score and explicit UNKNOWN list |
| J5 | Assess a device type the tool has never seen | Rahul | Taught in minutes through a GUI, no code |
| J6 | Know which findings actually matter | Rahul | Attack-path ranked priority list |
| J7 | Apply fixes without causing an outage | Rahul | Ordered playbook with lockout detection and rollback |
| J8 | Dispute a finding with a documented reason | Rahul | Compensating control claimed *and machine-verified* |
| J9 | Track remediation to closure | Priya, Anjali | Finding lifecycle with owners and verification |
| J10 | Compare cycles and explain movement | Anjali | Delta decomposed into config change vs benchmark change |
| J11 | Report posture upward credibly | Anjali | Estate report with systemic root-cause findings |
| J12 | Reproduce an audit months later | Priya | Reproducibility manifest; byte-identical re-run |
| J13 | Keep framework content current safely | Vikram | Update preview with quantified estate impact before ratification |

---

## 4. The audit lifecycle

The eight stages the product must cover. Competing tools cover only stage 3.

```
 1. SCOPE      define the estate and the engagement
 2. COLLECT    gather configurations; track what is missing
 3. ASSESS     normalise → evaluate → attach evidence
 4. TRIAGE     review, dispute, adjudicate, accept risk
 5. REPORT     per-device PDF and estate summary
 6. REMEDIATE  issue guidance, assign owners, track progress
 7. VERIFY     re-collect, confirm the fix, close the finding
 8. RETAIN     immutable, reproducible, defensible record
```

---

## 5. Journey: Priya runs a quarterly audit

### Stage 1 — Scope

Priya creates a campaign:

```
Campaign:   Q3-2026 Core Infrastructure Audit
Scope:      all internet-facing devices + 10% sample of access layer
            → 412 devices resolved from asset inventory
Frameworks: CIS v3.0.1 · NIST 800-53 Rev5 · DISA STIG 2026-01
Owner:      P. Sharma, Lead Assessor
Window:     01–30 September 2026
```

Everything downstream is anchored to this campaign. Reports are issued *as of* a
campaign; re-audits compare campaign to campaign.

**Pain removed:** scope currently lives in a spreadsheet and drifts from reality.

### Stage 2 — Collect

Configurations arrive three ways: bulk file upload from the network team, live
read-only collection where credentials exist, and JSON policy exports for
cloud-hosted firewalls.

Two days later, the platform reports:

```
Collection Completeness: 389 of 412 in-scope devices (94.4%)

  23 not collected
   • 14  no response to collection attempt      owner: NOC-Mumbai
   •  6  access denied, credentials expired     owner: IAM team
   •  3  configuration format unrecognised      → training queued

⚠ This audit does not cover 5.6% of defined scope.
```

**This is itself an audit finding.** An assessment that silently covers 94% and
presents as complete is misleading — and it is the specific failure that damages
an auditor professionally.

The platform additionally warns:

```
⚠ 47 devices supplied non-verbose exports. Settings at platform defaults are
  not visible. 34 controls cannot be assessed on these devices.
  Re-collect with `show running-config all` to raise coverage 61% → est. 94%.
```

**Pain removed:** currently an auditor has no way to know they were handed an
incomplete export.

### Stage 3 — Assess

389 devices are normalised and evaluated. Three of them are MikroTik RouterOS,
a platform the system has not been taught. They are handed to Rahul (§6).

Assessment completes in minutes and is fully offline.

### Stage 4 — Triage

Priya reviews. For each finding she can see the exact configuration lines, the
control, its framework mappings, and the severity as adjusted for that device's
exposure.

Rahul disputes eleven findings. Nine are resolved by the platform's own
verification of his claimed compensating controls (§6.4). Two require Priya's
judgement; she records her adjudication with a reason.

**Pain removed:** the dispute currently happens in email and dies in a
spreadsheet with no attribution.

### Stage 5 — Report

389 per-device PDFs are generated, plus an estate report. The estate report
surfaces something Priya would not have found manually:

> **Systemic finding:** 31 of 40 branch routers share an identical
> misconfiguration in their management ACL. This indicates a defect in the
> build template, not 31 independent errors.
> **Recommended action:** correct the build template; re-image or patch the 31.

**Pain removed:** manual auditing produces 31 findings; it does not produce the
insight that they have one cause.

### Stage 6 — Remediate

Findings are assigned owners and due dates. The network team receives ordered
remediation playbooks with impact classification and rollback commands.

### Stage 7 — Verify

Rahul reports 34 findings fixed. Priya triggers re-collection of those devices.
The platform re-assesses and confirms each specific finding now passes, attaching
the new evidence.

Two findings did **not** actually change. They are returned to `ASSIGNED` with a
note.

**Pain removed:** verification currently means taking the network team's word.

### Stage 8 — Retain

Everything is frozen: input artifact hashes, rulepack versions, framework
versions, engine version, every adjudication with its author and timestamp. The
audit can be reproduced byte-for-byte on demand.

### Next cycle — Explaining movement

Q4 compliance reads 71%, down from 78%. Before anyone panics, the platform
decomposes it:

```
Q3 78%  →  Q4 71%

  −4 pp   benchmark updated CIS v3.0.1 → v3.1.0
          (14 new controls added, 6 tightened)
  −5 pp   genuine configuration regressions across 7 devices
  +2 pp   verified remediations closed (11 findings)
```

> **"You got worse" and "the bar moved" are different facts. A source of truth
> must separate them.**

No competing product does this, and every organisation running quarterly audits
has been confused by it.

---

## 6. Journey: Rahul is asked to help

### 6.1 An unfamiliar platform arrives

Three MikroTik RouterOS devices are in scope. The platform has never seen
RouterOS. It does **not** report them as compliant. It reports:

```
RTR-Pune-02 · RouterOS 7.11.2 · Coverage 0%
  70 controls UNKNOWN · 0 PASS · 0 FAIL

⚠ Assessment not possible. Platform not yet taught.
   → 9 questions prepared. Estimated 8 minutes.
```

Two things already work before any teaching:

```
⚠ CVE-2018-14847 — RouterOS 6.42 on RTR-Nagpur-01
   Authentication bypass. Publicly exploited. Upgrade required.
   (Determined from version fingerprint alone — no parsing needed.)

⚠ Peer deviation — 3 of 40 RouterOS devices differ from their siblings on
   `/ip service`. No benchmark required; the estate's own majority behaviour
   is an implicit policy.
```

### 6.2 Teaching

Rahul opens the Training Studio. He is not shown 4,000 unrecognised lines. He is
shown **nine questions**, ordered so the first three deliver most of the coverage.

```
┌──────────────────────────────────────────────────────┐
│  Question 1 of 9          Section: /ip service       │
│  Pattern: set <service> disabled=<yes|no> [port=<n>] │
│                                                      │
│    set telnet disabled=no port=23                    │
│    set ssh    disabled=no port=22                    │
│    set www    disabled=no port=80                    │
│                                                      │
│  Proposed reading — please confirm:                  │
│    telnet → Telnet service        ENABLED            │
│    ssh    → SSH service           ENABLED            │
│    www    → HTTP management       ENABLED            │
│                                                      │
│  ⚠ "disabled=no" means the service IS ON. Correct?  │
│    [ Confirm ]   [ Inverted ]   [ Not relevant ]     │
└──────────────────────────────────────────────────────┘
```

He reads it in five seconds and clicks **Confirm**.

**He did not author anything. He verified a proposal.** Humans are fast and
accurate at *"is this right?"* and slow and unreliable at *"write the correct
rule."* The entire interaction design rests on that asymmetry — and it is what
allows a network engineer with no programming experience to teach a parser.

Eight minutes later:

```
BEFORE                 AFTER
Coverage    0%         Coverage   71%
UNKNOWN    70          PASS        9 · FAIL 12 · UNKNOWN 20
```

And real findings appear, each citing an exact line.

### 6.3 Receiving the report

Rahul's report does not open with 31 findings. It opens with:

> **Remediate these 5 and 23 of 31 findings become unreachable.**

Then, for each fix, an ordered playbook:

```
Step 1  aaa authentication login default group tacacs+ local
        impact: SAFE · must precede Step 4
Step 2  line vty 0 15                       impact: SAFE
Step 3   transport input ssh
        ⚠ LOCKOUT RISK — terminates active Telnet sessions
        rollback: transport input telnet ssh
Step 4  no username admin password 7 …
        impact: SERVICE-AFFECTING · requires Step 1 verified

DRY RUN  applying all steps: 78% → 94%
         ⚠ Step 4 would cause NSCA-AUTH-009 to fail
           (no local fallback if TACACS becomes unreachable)
```

**This is the single feature most likely to convert Rahul from sceptic to
advocate.** Nobody has ever handed him remediation advice that warned him about
locking himself out.

### 6.4 Disputing a finding

Rahul disputes: *"Telnet is enabled on MGMT-SW-04, but that device sits on an
isolated out-of-band management network. It is unreachable from anywhere else."*

Normally an auditor accepts this on faith. Instead:

```
Claimed compensating control:
  Device reachable only from OOB management network 10.250.0.0/24

Verification:  ❌ REFUTED
  MGMT-SW-04 interface Gi0/8 bridges VLAN 250 and VLAN 40 (user network).
  Counterexample: 10.40.7.19 → 10.250.0.11:23 TCP is permitted.

The claimed compensating control does not exist.
```

Rahul did not know about `Gi0/8`. Somebody added it during an incident eighteen
months ago and never removed it.

**The auditor asserts; the system checks.** This turns an adversarial exchange
into a shared discovery, and it is the mechanism most likely to end the
auditor-versus-administrator relationship that makes compliance fail in practice.

---

## 7. Journey: Vikram ratifies a framework update

```
Framework update available
  DISA STIG Cisco IOS-XE Router
  Current 2025-10 (Rel 12)  →  Available 2026-01 (Rel 13)

Changes
  +  6 new rules
  ~  4 rules modified (severity or check logic)
  −  2 rules withdrawn

Impact on your estate — dry run against Campaign Q3-2026
  +  6 new findings across 41 devices
  ~  2 findings change severity CAT II → CAT I
  −  2 findings would close

  [ Review changes ]   [ Ratify ]   [ Defer ]
```

Framework updates never silently alter results. Impact is quantified against the
real estate *before* adoption, and each campaign records exactly which content
version it used — which is what makes the Q4 delta decomposition in §5 possible.

---

## 8. Design principles derived from these journeys

| # | Principle | Derived from |
|---|---|---|
| P1 | Never report an undetermined result as compliant | Priya's deepest fear (J4) |
| P2 | Every finding cites artifact and line numbers | *"If I can't point at the line, it's an opinion"* (J3) |
| P3 | Prioritise by real risk, not by static label | Rahul will read the first ten items only (J6) |
| P4 | Remediation must be safe before it is correct | Rahul's deepest fear (J7) |
| P5 | Verification, not assertion | Compensating controls, remediation closure (J8, J9) |
| P6 | Confirm, do not author | Rahul is not a programmer (J5) |
| P7 | Audit the estate, not the inbox | Uncollected devices are findings (J1) |
| P8 | Separate movement in posture from movement in the standard | Anjali cannot defend a number she cannot explain (J10) |
| P9 | Everything is attributable and reproducible | Defensibility twelve months later (J12) |
| P10 | Report root causes, not symptom counts | 31 findings, one build template (J11) |
