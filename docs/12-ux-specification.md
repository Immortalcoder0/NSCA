# 12 · UX Specification

> Screen inventory and interaction design. The problem statement calls
> specifically for *"a user-friendly, robust software platform"*, *"a dashboard
> for uploading single or bulk configuration files"*, and *"a dedicated,
> intuitive GUI"* for training.

---

## 1. Design principles

| # | Principle | Consequence |
|---|---|---|
| U1 | **Evidence is always one click away** | Any finding expands to the configuration excerpt with lines highlighted |
| U2 | **Confirm, do not author** | The user never writes a pattern, expression, or query |
| U3 | **State uncertainty visually** | UNKNOWN is a distinct visual state, never styled like a pass |
| U4 | **Lead with action** | Every view opens with *what to do*, not *what is wrong* |
| U5 | **Progress must be legible** | Long operations show what remains and what each step achieves |
| U6 | **Destructive and irreversible actions are gated** | Issuing a campaign, ratifying a rule, accepting risk |
| U7 | **Severity is never colour alone** | Accessibility, and reports must print in monochrome |
| U8 | **Bulk by default** | An assessor works with hundreds of devices, not one |

---

## 2. Screen inventory

```
┌─ Campaigns ──────────────────────────────────────────────┐
│  ├─ Campaign list                                        │
│  ├─ Campaign detail  ── scope · collection · progress    │
│  └─ Campaign comparison                                  │
├─ Estate ─────────────────────────────────────────────────┤
│  ├─ Device grid                                          │
│  ├─ Device detail  ── findings · evidence · remediation  │
│  └─ Attack path explorer                                 │
├─ Findings ───────────────────────────────────────────────┤
│  ├─ Finding workbench  (triage, assign, adjudicate)      │
│  └─ Finding detail                                       │
├─ Training Studio ────────────────────────────────────────┤
│  ├─ Learning queue                                       │
│  ├─ Question flow                                        │
│  └─ Rule review & ratification                           │
├─ Knowledge ──────────────────────────────────────────────┤
│  ├─ Rulepacks                                            │
│  ├─ Control packs & frameworks                           │
│  ├─ Framework update review                              │
│  └─ Coverage manifests                                   │
├─ Reports ────────────────────────────────────────────────┤
│  ├─ Report library                                       │
│  └─ Report viewer                                        │
└─ Administration ─────────────────────────────────────────┘
   ├─ Users & roles
   ├─ Collection credentials
   └─ System status & knowledge freshness
```

---

## 3. Ingestion dashboard

Explicitly required: *"A dashboard for uploading single or bulk configuration
files from any network device."*

```
┌──────────────────────────────────────────────────────────────────┐
│  INGEST · Campaign Q3-2026 Core Infrastructure Audit             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│    ┌──────────────────────────────────────────────────────┐      │
│    │                                                      │      │
│    │        Drop configuration files or archives here     │      │
│    │                                                      │      │
│    │   Text · XML · JSON · .zip · .tar.gz · show tech     │      │
│    │                                                      │      │
│    │              [ Browse ]    [ Collect from devices ]  │      │
│    └──────────────────────────────────────────────────────┘      │
│                                                                  │
│  PROCESSING · 389 artifacts                                      │
│  ████████████████████████████░░░░  84%   327 / 389               │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ ✓ CORE-SW-01      Cisco IOS-XE 16.12.4    3 artifacts      │  │
│  │                   running-config · version · inventory     │  │
│  │ ✓ EDGE-FW-01      PAN-OS 10.2.3           1 artifact       │  │
│  │ ⚠ BR-RTR-014      Cisco IOS 15.2          terse export     │  │
│  │                   → 34 controls unassessable               │  │
│  │ ⚠ RTR-Pune-02     RouterOS 7.11.2         NOT TAUGHT       │  │
│  │                   → 9 training questions prepared          │  │
│  │ ✗ unknown-04.cfg  unidentified            grammar 43%      │  │
│  │                   → assisted grammar authoring required    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  COLLECTION COMPLETENESS                                         │
│  389 of 412 in scope (94.4%) · 23 missing → [ View ]             │
└──────────────────────────────────────────────────────────────────┘
```

**Design notes**

- Four outcome states, visually distinct: parsed · parsed with caveat · not
  taught · unidentifiable. Never a binary success/failure
- Multi-artifact devices show which artifacts were correlated — the user must be
  able to see that serial numbers came from `show inventory`
- "Not taught" is an **invitation**, not an error — it links directly into the
  Training Studio with questions already prepared
- Collection completeness is present on the ingestion screen, not buried in a
  report

---

## 4. Estate view

```
┌──────────────────────────────────────────────────────────────────┐
│  ESTATE · Q3-2026                             389 of 412 devices │
├──────────────────────────────────────────────────────────────────┤
│  Compliance 81%   Coverage 89%   Meaningful 67%   Security 64%   │
│                                                                  │
│  ▸ 3 attack paths reach the core management plane                │
│    Breaking 6 findings eliminates all 3.        [ Explore ]      │
│                                                                  │
│  ▸ Systemic finding SF-004 · 31 of 40 branch routers             │
│    Build-template defect, not 31 independent errors  [ View ]    │
│                                                                  │
│  Filter  platform ▾  exposure ▾  coverage ▾  status ▾  [search]  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Device        Platform      Compl  Cover  Crit  Status     │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │ EDGE-FW-01    PAN-OS 10.2    68%    94%    4    ▲ external │  │
│  │ CORE-SW-01    IOS-XE 16.12   78%    92%    3               │  │
│  │ BR-RTR-014    IOS 15.2       71%    61%    2    ⚠ terse    │  │
│  │ RTR-Pune-02   RouterOS 7.11  62%    71%    1    ⓘ local RP │  │
│  │ MGMT-SW-04    IOS 15.2       —      0%     —    ✗ missing  │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

**Coverage is a first-class column.** A device at 100% compliance and 40%
coverage must never look better than one at 85% compliance and 95% coverage.
Sorting by compliance alone is misleading, so the default sort is by critical
findings weighted by exposure.

Row annotations carry meaning: `⚠ terse` (incomplete export), `ⓘ local RP`
(non-certified rulepack), `✗ missing` (in scope, not collected).

---

## 5. Device detail

```
┌──────────────────────────────────────────────────────────────────┐
│  CORE-SW-01   Cisco Catalyst 9300-48P · IOS-XE 16.12.04          │
│  SN FCW2140L0GH  ·  Distribution  ·  Internal                    │
│  Rulepack cisco_iosxe@7.2.1 (Certified)                          │
├──────────────────────────────────────────────────────────────────┤
│  Compliance 78%   Coverage 92%   Meaningful 64%                  │
│                                                                  │
│  ── FIX THESE FIRST ─────────────────────────────────────────    │
│  Resolving 5 findings makes 23 of 31 unreachable.                │
│    1  Remove 0.0.0.0/0 from group Partners      1 cmd · safe     │
│    2  Disable Telnet on VTY lines           3 cmds · ⚠ lockout   │
│    3  Replace type 7 credential          2 cmds · svc-affecting  │
│                            [ View full playbook ]  [ Dry run ]   │
│                                                                  │
│  [ Findings 31 ] [ Passing 112 ] [ Unknown 12 ] [ N/A 14 ]       │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ ▼ NSCA-MGMT-002  Plaintext management protocols     FAIL   │  │
│  │   HIGH → CRITICAL · external circuit                       │  │
│  │   CIS-IOS-1.2.4 · NIST AC-17 · STIG V-216644 · ISO A.9.4.2 │  │
│  │                                                            │  │
│  │   EVIDENCE  running-config.txt                             │  │
│  │     141 │ line vty 0 4                                     │  │
│  │     142 │  login local                                     │  │
│  │   ▸ 143 │  transport input telnet ssh                      │  │
│  │     144 │  exec-timeout 0 0                                │  │
│  │                                                            │  │
│  │   [ Remediate ]  [ Dispute ]  [ Accept risk ]  [ Assign ]  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ⚠ UNAUDITED CAPABILITY                                          │
│    Embedded web management TCP/8443 — outside all selected       │
│    frameworks. 6 controls downgraded to PASS (PARTIAL).          │
│                                              [ Assess this ]     │
└──────────────────────────────────────────────────────────────────┘
```

Evidence is inline and expanded by default on the first finding. The user should
never have to hunt for the proof.

---

## 6. Training Studio

The screen the problem statement names explicitly. It must be usable by a network
engineer with no programming experience.

### 6.1 Queue

```
┌──────────────────────────────────────────────────────────────────┐
│  TRAINING STUDIO                                                 │
├──────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ MikroTik RouterOS 7.11.2               NOT TAUGHT          │  │
│  │ 3 devices · coverage 0% · 70 controls undetermined         │  │
│  │ Grammar inferred · 98.4% line coverage                     │  │
│  │ 9 questions · est. 8 minutes                    [ Begin ]  │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │ Cisco IOS-XE 16.12                     PARTIAL             │  │
│  │ 142 devices · coverage 92%                                 │  │
│  │ 2 gaps: `crypto ikev2 policy`, `service-template`          │  │
│  │ 2 questions · est. 2 minutes                    [ Begin ]  │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │ unknown-04.cfg                         UNIDENTIFIED        │  │
│  │ Grammar inference 43% — unreliable                         │  │
│  │                             [ Assisted grammar authoring ] │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 6.2 Question flow

```
┌──────────────────────────────────────────────────────────────────┐
│  MikroTik RouterOS          Question 1 of 9      ●○○○○○○○○       │
│                                       Coverage 0% ──► ?          │
├──────────────────────────────────────────────────────────────────┤
│  Section  /ip service                                            │
│  Pattern  set <service> disabled=<yes|no> [port=<n>]             │
│                                                                  │
│  From RTR-Pune-02.rsc — 6 matching lines                         │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  14 │ set telnet  disabled=no   port=23                    │  │
│  │  15 │ set ftp     disabled=no   port=21                    │  │
│  │  16 │ set www     disabled=no   port=80                    │  │
│  │  17 │ set ssh     disabled=no   port=22                    │  │
│  │  19 │ set api     disabled=yes                             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ── OUR READING ─────────────────────────────────────────────    │
│  This appears to enable or disable management services.          │
│                                                                  │
│      telnet   →  Telnet service            ENABLED               │
│      ssh      →  SSH service               ENABLED               │
│      www      →  HTTP management           ENABLED               │
│      ftp      →  FTP service               ENABLED               │
│      api      →  API service               disabled              │
│                                                                  │
│  ┌── ⚠ POLARITY CHECK ────────────────────────────────────────┐  │
│  │ "disabled=no" is being read as the service being ON.       │  │
│  │ Is that correct?                                           │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Confirming resolves 8 controls.                                 │
│                                                                  │
│  [ ✓ Confirm ]  [ ⇄ Polarity inverted ]                          │
│  [ ✎ Edit mapping ]  [ ✗ Not compliance-relevant ]  [ Skip ]     │
└──────────────────────────────────────────────────────────────────┘
```

**Design notes**

- **Real lines from their own device**, with line numbers. Concrete beats
  abstract; they recognise their equipment
- **Polarity is a separate visual block** with its own question, because it is
  the highest-consequence error class in the system
- **The impact of answering is stated before answering** — motivation and
  legibility
- *"Not compliance-relevant"* is a first-class answer. Forcing a mapping produces
  bad rules; the negative answer is itself useful information
- Progress dots and time estimate: nine questions is tractable, unknown length is
  not
- No regular expression is ever shown to the user

### 6.3 Result

```
┌──────────────────────────────────────────────────────────────────┐
│  ✓ TRAINING COMPLETE · MikroTik RouterOS                         │
├──────────────────────────────────────────────────────────────────┤
│                    BEFORE          AFTER                         │
│    Coverage           0%             71%                         │
│    Determined          0             21                          │
│    Unknown            70             20                          │
│                                                                  │
│    5 confirmations · 8 min 12 s                                  │
│                                                                  │
│  Rules created  4        status: PROVISIONAL                     │
│  ⚠ Requires ratification by a second user before findings        │
│    appear in an issued report.        [ Request ratification ]   │
│                                                                  │
│  20 controls remain undetermined.     [ Continue training ]      │
└──────────────────────────────────────────────────────────────────┘
```

The **before/after coverage figure with a timer** is the product's central claim
made visible.

### 6.4 Ratification

```
┌──────────────────────────────────────────────────────────────────┐
│  RATIFY  mikrotik_routeros.ip_service.enabled@1                  │
├──────────────────────────────────────────────────────────────────┤
│  Taught by  r.kulkarni   14 Sep 2026 10:22                       │
│  From       RTR-Pune-02.rsc · 5 examples confirmed               │
│                                                                  │
│  Reads      /ip service → set <svc> disabled=<yes|no>            │
│  Produces   mgmt.protocols.{telnet,ssh,http,ftp,api}.enabled     │
│  Polarity   INVERTED (disabled=no → enabled=true)  ✓ confirmed   │
│                                                                  │
│  VALIDATION                                                      │
│    Self-match          6 lines in source artifact          ✓     │
│    Cross-platform      0 matches on other platforms        ✓     │
│    Conflicts           none                                ✓     │
│    Regression          412 existing tests pass             ✓     │
│    Metamorphic         1,000 mutations, facts stable       ✓     │
│    Coverage effect     +71 pp on 3 devices                       │
│                                                                  │
│  ⚠ You did not author this rule. Review before ratifying.        │
│                          [ Ratify ]  [ Reject ]  [ Comment ]     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 7. Finding workbench

Bulk triage. An assessor faces hundreds of findings and must work at volume.

```
┌──────────────────────────────────────────────────────────────────┐
│  FINDINGS · Q3-2026                       241 open · 34 verified │
├──────────────────────────────────────────────────────────────────┤
│  Filter  severity ▾  state ▾  control ▾  platform ▾  path ▾      │
│  Group by  ● control   ○ device   ○ attack path   ○ systemic     │
│                                                                  │
│  ▼ NSCA-MGMT-007 · Management access source restriction     31   │
│    ⓘ SYSTEMIC — build-template defect                            │
│      All 31 share an identical management ACL block.             │
│      [ Adjudicate all 31 ]  [ Assign all ]  [ View root cause ]  │
│                                                                  │
│    ☐ BR-RTR-001   FAIL  HIGH   New                               │
│    ☐ BR-RTR-002   FAIL  HIGH   New                               │
│    ☐ BR-RTR-003   FAIL  HIGH   Disputed  ← compensating control  │
│    …                                                             │
│                                                                  │
│  ▼ NSCA-MGMT-002 · Plaintext management protocols            12  │
│  ▶ NSCA-CRYPTO-003 · Weak SSH ciphers                         8  │
│                                                                  │
│  Selected 31   [ Assign ▾ ]  [ Confirm ]  [ Export ]             │
└──────────────────────────────────────────────────────────────────┘
```

**Grouping by control rather than by device is the default**, because that is how
an assessor thinks and how systemic patterns become visible.

---

## 8. Dispute and compensating control verification

```
┌──────────────────────────────────────────────────────────────────┐
│  DISPUTE · F-2026Q3-000418 · MGMT-SW-04 · NSCA-MGMT-002          │
├──────────────────────────────────────────────────────────────────┤
│  Raised by r.kulkarni · 18 Sep 2026                              │
│  Type      Compensating control                                  │
│                                                                  │
│  Claim                                                           │
│    "Telnet is enabled, but this device is on an isolated OOB     │
│     management network and unreachable from any user network."   │
│                                                                  │
│  ── PLATFORM VERIFICATION ───────────────────────────────────    │
│                                                                  │
│    ❌ REFUTED                                                    │
│                                                                  │
│    MGMT-SW-04 interface Gi0/8 bridges VLAN 250 and VLAN 40       │
│    (user network).                                               │
│                                                                  │
│    Counterexample   10.40.7.19 → 10.250.0.11:23 TCP permitted    │
│    Rule chain       SW-Core-02 acl[user-out]:22 → permit         │
│                                                    [ View path ] │
│                                                                  │
│    Assumptions                                                   │
│      Based on 389 of 412 devices. 23 uncollected; additional     │
│      paths through those devices cannot be excluded.             │
│      Confidence: medium                                          │
│                                                                  │
│  ADJUDICATION                                                    │
│    ( ) Uphold dispute — withdraw finding                         │
│    (•) Reject dispute — finding stands                           │
│    ( ) Accept as risk                                            │
│    Rationale ┌──────────────────────────────────────────────┐    │
│              │ Isolation claim refuted by Gi0/8 bridge.     │    │
│              └──────────────────────────────────────────────┘    │
│                                            [ Record decision ]   │
└──────────────────────────────────────────────────────────────────┘
```

This screen converts an adversarial email exchange into a shared, evidenced
discovery — and it is the interaction most likely to change the
auditor/administrator relationship.

---

## 9. Attack path explorer

```
┌──────────────────────────────────────────────────────────────────┐
│  ATTACK PATH AP-003                                              │
│  External untrusted zone → core management plane                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   [external]                                                     │
│       │  203.0.113.5:44210                                       │
│       ▼                                                          │
│   EDGE-FW-01 Gi0/1                                               │
│       │  rule outside-in:14  permit          ◀── F-000518 HIGH   │
│       ▼                                                          │
│   group Trusted-Admins → Partners → 0.0.0.0/0                    │
│       │                                                          │
│       ▼                                                          │
│   CORE-SW-01 Vlan1 :22                       ◀── F-000412 CRIT   │
│       │  reversible credential               ◀── F-000603 HIGH   │
│       ▼                                                          │
│   [management plane]                                             │
│                                                                  │
│  Breaking any single link breaks the chain.                      │
│  Lowest cost: F-000518 — 1 command, impact SAFE   [ Remediate ]  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 10. Visual language

### 10.1 Verdict states

| Verdict | Treatment |
|---|---|
| PASS | Filled check, neutral weight |
| PASS (PARTIAL) | Check with warning overlay — visually distinct from PASS |
| PASS (vacuous) | Hollow check — distinguishable at a glance |
| FAIL | Solid marker, weighted by severity |
| UNKNOWN | **Question mark on a distinct background.** Never resembles a pass |
| NOT_APPLICABLE | Greyed dash, de-emphasised |

**U3 restated:** the failure mode this product exists to prevent is UNKNOWN being
mistaken for PASS. It must be impossible to confuse them visually, at any size,
in monochrome.

### 10.2 Severity

Never colour alone (U7). Every severity carries a shape or glyph as well as a
hue, and reports must remain legible printed in black and white.

### 10.3 Trust indicators

Findings from non-certified rulepacks carry a persistent marker throughout the
interface, not only in the report.

---

## 11. Accessibility

| Requirement |
|---|
| Contrast meets WCAG 2.1 AA |
| No information conveyed by colour alone |
| Full keyboard navigation, including the Training Studio question flow |
| Screen-reader labels on all verdict states and severity indicators |
| Configuration excerpts rendered as accessible text, not images |
| Reports legible in monochrome print |
