# 06 · Controls and Frameworks

> How the platform decides what "compliant" means, where that knowledge comes
> from, and how one evaluation satisfies four different standards.

---

## 1. The core insight

Read what a CIS recommendation actually says:

> **CIS Cisco IOS 1.2.4** — Set `transport input ssh` for `line vty`

Now strip the Cisco vocabulary out and ask what it is *really* saying:

> **Management access must be encrypted. Plaintext management protocols must be
> disabled.**

That is not a Cisco idea. It is a universal security principle that CIS wrote
down in Cisco syntax because they were writing a Cisco document. The same
principle appears — differently worded — in the Juniper benchmark, the FortiOS
benchmark, and the Arista STIG.

> **A vendor benchmark is a universal principle plus a vendor-specific
> instantiation.**

The architecture already separates those two things. The instantiation lives in
the **rulepack**; the principle lives in the **control**.

Therefore:

> **You do not write audit rules per vendor. You write them once, against
> meaning. The vendor-specific work is teaching the system to *see* — and that is
> the part the learning subsystem makes cheap.**

---

## 2. The two-tier control model

`CIS-IOS-1.2.4` is vendor-specific by construction. So how does it coexist with
controls that mention no vendor?

Two tiers, with a mapping between them.

```
   FRAMEWORK ITEMS                          NATIVE CONTROLS
   vendor-specific · imported               vendor-neutral · evaluated

   CIS-IOS-1.2.4          ─┐
   CIS-JUNIPER-4.2.1      ─┤
   CIS-FORTIOS-2.1.6      ─┤
   STIG V-216644  (IOS)   ─┼──►  NSCA-MGMT-002  ──►  mgmt.protocols.telnet.enabled
   STIG V-220987  (JunOS) ─┤     "Plaintext management       == false
   NIST AC-17, SC-8       ─┤      protocols disabled"
   ISO A.9.4.2            ─┘
```

**Framework items are the reporting vocabulary. Native controls are the
evaluation engine.**

You evaluate once, natively, against the schema. You then report the result in
whichever vocabulary the assessor selected. Seven framework items, one
evaluation.

This is why multi-framework support costs almost nothing once the architecture is
right — and why a report can legitimately state:

> *This single misconfiguration violates CIS 1.2.4, NIST AC-17 and SC-8,
> DISA STIG V-216644, and ISO 27001 A.9.4.2.*

### 2.1 How cleanly does the mapping work?

Approximately:

| Relationship | Share | Example |
|---|---|---|
| Framework item → universal native control | ~70% | *"Disable Telnet"* — true of every platform ever built |
| → native control with conditional applicability | ~20% | *"Authenticate OSPF"* — only if the device runs OSPF |
| → platform-specific native control | ~10% | *"Do not use type 7 passwords"* — a Cisco-only encoding |

> These proportions are **estimates for planning**, derived from inspection of
> published benchmarks. They should be measured against real imported content
> and corrected.

---

## 3. The native control specification

```yaml
control_id:    NSCA-MGMT-002
title:         Plaintext management protocols must be disabled
description:   >
  Management protocols that transmit credentials or session data without
  encryption expose administrative credentials to any party able to observe
  network traffic.
family:        management_plane
severity_base: high
materiality:   material

# ── Applicability ────────────────────────────────────────────────
applies_to:
  platform_family: "*"
  requires_capability: [management_access]
  version_range: "*"

# ── What it needs ────────────────────────────────────────────────
requires_facts:
  - mgmt.protocols.telnet.enabled
  - mgmt.protocols.http.enabled
  - mgmt.protocols.ftp.enabled

# ── The assertion ────────────────────────────────────────────────
assert: >
  mgmt.protocols.telnet.enabled == false and
  mgmt.protocols.http.enabled   == false and
  mgmt.protocols.ftp.enabled    == false

# ── Vacuity classification ───────────────────────────────────────
vacuity:
  meaningful_when: "mgmt.protocols.ssh.enabled == true"
  # A pass with no management access at all is vacuous, not secure

# ── Framework mapping ────────────────────────────────────────────
maps_to:
  cis:
    - { id: CIS-IOS-1.2.4,      benchmark: cisco_ios_15,  version: "4.1.0" }
    - { id: CIS-JUNIPER-4.2.1,  benchmark: juniper_junos, version: "2.1.0" }
  nist:
    - { id: AC-17, revision: "Rev5" }
    - { id: SC-8,  revision: "Rev5" }
  stig:
    - { id: V-216644, benchmark: cisco_ios_xe_router, release: "2026-01" }
  iso:
    - { id: A.9.4.2 }

# ── Contextual risk ──────────────────────────────────────────────
risk_modifiers:
  - { if: "device.exposure == internet_facing", severity: critical }
  - { if: "device.exposure == isolated",        severity: medium   }

# ── Remediation ──────────────────────────────────────────────────
remediation:
  cisco_ios:
    version_range: ">=15.0 <16.0"
    steps:
      - { cmd: "line vty 0 15",        impact: safe }
      - { cmd: " transport input ssh", impact: lockout-risk,
          reason: "Terminates all active Telnet sessions, possibly the operator's" }
      - { cmd: "no ip http server",    impact: safe }
    rollback: ["line vty 0 15", " transport input telnet ssh", "ip http server"]
    prerequisites: [NSCA-MGMT-001]     # SSH must be working first

  mikrotik_routeros:
    version_range: "*"
    steps:
      - { cmd: "/ip service set telnet disabled=yes", impact: lockout-risk }
      - { cmd: "/ip service set www disabled=yes",    impact: safe }
      - { cmd: "/ip service set ftp disabled=yes",    impact: safe }
    rollback: ["/ip service set telnet disabled=no"]

references:
  - "RFC 4251 — SSH Protocol Architecture"
  - "NIST SP 800-53 Rev5 AC-17(2)"
```

### 3.1 Why each section exists

| Section | Purpose |
|---|---|
| `applies_to` | Produces `NOT_APPLICABLE` rather than a false failure on platforms lacking the capability |
| `requires_facts` | **The mechanism that produces UNKNOWN automatically.** If any listed fact is missing or `default_unknown`, the control returns UNKNOWN. Coverage scoring is a consequence of the architecture, not a separate feature |
| `assert` | The judgment. Deterministic expression over schema facts. No vendor terms |
| `vacuity` | Distinguishes *"securely configured"* from *"feature absent"* |
| `maps_to` | Multi-framework reporting, with **version pinning on every mapping** |
| `risk_modifiers` | Contextual severity, so a report can be prioritised rather than merely sorted |
| `remediation` | Keyed by platform **and version range**, with impact class, rollback and prerequisites |

### 3.2 The assertion language

Assertions are evaluated by a restricted expression engine over the fact set.

**Constraints:**

- **No arbitrary code execution.** Control packs are importable content; if they
  could execute code, importing a community control pack would be a remote code
  execution vector
- **Total functions only.** No unbounded loops or recursion
- **Three-valued logic.** An assertion referencing a missing fact evaluates to
  UNKNOWN, not FALSE. `unknown AND false = false`; `unknown AND true = unknown`
- **Deterministic.** No clock, no randomness, no I/O

Supported operations: comparison, boolean logic, set membership, list
quantifiers (`any`, `all`, `none`, `count`), string matching against declared
patterns, and version-range comparison.

```
# examples
snmp.communities | none(c => c.is_default)
auth.local_users | none(u => u.privilege_level >= 15 and u.reversible)
crypto.ssh.ciphers | all(c => c in ALLOWED_CIPHERS)
mgmt.session.idle_timeout_sec > 0 and mgmt.session.idle_timeout_sec <= 600
filter.objects | none(o => "0.0.0.0/0" in o.expanded and o.name in MGMT_GROUPS)
```

---

## 4. The control library

Organised by family. The four families the problem statement explicitly names
are marked ★.

| Family | Approx. controls | Coverage |
|---|---|---|
| ★ `management_plane` | 45 | Protocols, sessions, timeouts, source restriction, banners |
| `authentication` | 40 | Local accounts, central auth, password policy, privilege |
| ★ `cryptography` | 30 | SSH/TLS/IPsec algorithms, certificates, key strength |
| ★ `logging_audit` | 25 | Remote logging, command accounting, timestamps |
| `time_sync` | 8 | NTP presence, authentication, redundancy |
| `snmp` | 15 | Versions, communities, v3 configuration, write access |
| ★ `access_control` | 40 | Rule hygiene, over-broad rules, shadowing, logging, defaults |
| `control_plane` | 25 | Routing protocol authentication, discovery protocols, source routing |
| `data_plane` | 20 | Port security, unused interfaces, layer-2 protections |
| `platform_hardening` | 15 | Unused services, firmware currency, boot integrity |
| `property_derived` | 12 | Applied to any capability by its universal properties (§7) |
| **Total** | **≈275** | |

---

## 5. Where framework content comes from

Four sources. They differ enormously in machine-readability, and the difference
drives the import strategy.

| Source | Format | Machine-readable | Licensing | Role |
|---|---|---|---|---|
| **DISA STIG** | XCCDF XML | **Fully** | Freely redistributable | **Primary import source** |
| **CIS Benchmark** | PDF, consistent template | Structured but not native | Free with registration; **text redistribution restricted** | Assisted extraction; identifiers cited, text not reproduced |
| **NIST SP 800-53** | OSCAL JSON | **Fully** | Public domain | Catalogue for abstract mapping |
| **ISO/IEC 27001** | Paid standard | No | **Cannot be redistributed** | Control identifiers only |

### 5.1 Import pipeline

```
  DISA STIG XCCDF ──► direct parse ──────────────────┐
                      rule id, severity, check, fix  │
                                                     │
  CIS Benchmark PDF ─► structured extraction ────────┤
                      (assisted, human-ratified)     ├──► framework items
                      recommendation, rationale,     │         │
                      audit, remediation, DEFAULT    │         │ map
                                                     │         ▼
  NIST OSCAL JSON ──► direct parse ──────────────────┤   native controls
                      control catalogue              │         │
                                                     │         │ evaluate
  ISO 27001 ────────► identifier list only ──────────┘         ▼
                                                            verdicts
```

**Three practical notes:**

**STIGs are the best import.** They are XML. Parse them directly and obtain a
large, structured, authoritative control set per platform at no content-authoring
cost. Begin here.

**CIS PDFs extract well despite being PDFs**, because every recommendation
follows an identical template — you are parsing a form, not free prose. This is
the natural place for model-assisted extraction with human ratification: the
model proposes a formal control, an assessor confirms it. **The same
confirm-don't-author pattern as the parsing loop, pointed at the other side of
the bridge.**

**CIS benchmarks document default values explicitly.** Every recommendation has a
"Default Value" section. Importing a benchmark therefore also populates the
platform's defaults table — which directly reduces `default_unknown` facts and
raises coverage.

### 5.2 The symmetry

This is the cleanest statement of the architecture:

> **The system is a bridge between two kinds of ambiguity — messy machine syntax
> on one side, messy human prose on the other — with something formal and
> deterministic in between. AI assists with both translations. Neither
> translation is trusted without human ratification. The formal core is the only
> thing anyone has to trust.**

A consequence: adding a whole new *framework* — a sectoral regulation, an RBI
circular, an internal corporate policy — is the same machinery as adding a new
vendor, pointed the other way. This is why the problem statement's phrase
*"support new vendors, **standards**, and OS versions"* is satisfiable.

---

## 6. The automation coverage manifest

The first thing a serious auditor will ask for, and almost no tool provides it.

```
CIS Cisco IOS 15 Benchmark v4.1.0 — Automation Coverage

  Total recommendations                          187
  ───────────────────────────────────────────────────
  Automated from configuration                   154   (82%)
  Requires manual assessment                      21   (11%)
      • physical security of the device
      • documented change management process
      • periodic personnel authorisation review
  Requires data not collected                      7   (4%)
      • needs `show crypto pki certificates`
      • needs `show logging` runtime state
  Not yet implemented                              5   (3%)
      → tracked in backlog, visible to the user
```

**Two reasons this is mandatory:**

**An auditor cannot sign off without it.** If they state *"assessed against
CIS"* and the tool silently skipped 33 recommendations, that is a professional
problem for *them*. Publishing coverage protects the person using the product.

**It is honest about a real limit.** Some benchmark recommendations are genuinely
not configuration-determinable — *"ensure the device is physically secured"*
cannot be established from a text file by anyone. Distinguishing automatable from
procedural is audit maturity, not weakness.

### 6.1 Equivalence rationale

CIS states an audit procedure. The platform checks a normalised fact. Are those
equivalent? Record the reasoning:

```yaml
framework_item: CIS-IOS-1.2.4
stated_audit:   "show run | sec vty → verify transport input ssh"
platform_check: >
  mgmt.protocols.telnet.enabled == false and
  mgmt.protocols.http.enabled == false
equivalence: >
  Our extractor parses all `line vty` blocks including overlapping ranges,
  resolving effective transport per line. This is strictly broader than the
  stated procedure, which inspects only the first matching block.
reviewed_by: p.sharma
reviewed_at: 2026-08-30
```

That paragraph is what an assessor points at when a client challenges a finding.
Cheap to produce, and precisely the rigour that separates an audit product from a
scanner.

---

## 7. Property-derived controls

For capabilities that fit no framework anywhere.

Catalogue-based controls ask *"which known category does this belong to?"* —
which fails on anything genuinely new, by definition. Property-derived controls
ask **"what does it do?"** — and the answer set is small, finite and universal.

```yaml
control_id:    NSCA-PROP-001
title:         Network-listening capabilities must be source-restricted
family:        property_derived
severity_base: high

applies_to:
  any_service_where: "properties.listens == true"

requires_facts:
  - services.<name>.enabled
  - mgmt.source_restriction.configured

assert: >
  services[svc].enabled == false or
  mgmt.source_restriction.configured == true

maps_to:
  nist: [{ id: AC-17, revision: "Rev5" }, { id: SC-7, revision: "Rev5" }]
  # no CIS or STIG mapping — this capability predates no framework
```

### 7.1 Worked example

A white-box switch runs a container runtime. Zero benchmark coverage exists
anywhere on Earth.

| Property | Value | Control triggered | Finding |
|---|---|---|---|
| `executes` | true | NSCA-PROP-003 | Image source must be verified; execution must be logged |
| `transports` | true | NSCA-PROP-005 | Registry connection must be authenticated and encrypted |
| `mutates` | true | NSCA-PROP-004 | Must require authentication and produce an audit record |
| `default_on` | true | NSCA-PROP-007 | Must be explicitly justified or disabled |

Four legitimate findings, derived not from knowing what a container is, but from
knowing what it *does*.

### 7.2 Where property values come from

Three sources, cheapest first:

1. **Observable evidence.** A port number implies `listens`. A `password=` or
   `key=` attribute implies `authenticates`. A registry URL implies `transports`
2. **Cross-platform lexical transfer.** Tokens like `port`, `community`,
   `secret`, `key` carry property signals independent of the feature's identity
3. **One human question** — and an easy one. Not *"write a security control"* but
   eight yes/no questions about what a feature does. Anyone who administers the
   platform can answer in thirty seconds

### 7.3 Novelty routing

| Distance from known categories | Route |
|---|---|
| Close | Generalise existing controls in that family (the Winbox case) |
| Far, but properties inferable | Apply property-derived controls |
| Far, properties unclear | Escalate to a human; report as **unassessed risk surface** |

The third outcome is not a failure. It is the honest output, and it is more than
any competing tool produces — everyone else's coverage of a novel capability is a
*silent* zero. This is a loud, tracked, prioritised zero.

---

## 8. Scope contamination

The most important safety property in the control model, and the reason it is
specified here rather than treated as a reporting nicety.

**A novel capability can render an existing PASS wrong without ever producing a
FAIL.**

```
NSCA-MGMT-002 · Plaintext management protocols disabled
   mgmt.protocols.telnet.enabled = false   ✓
   mgmt.protocols.http.enabled   = false   ✓
   mgmt.protocols.ftp.enabled    = false   ✓
   → PASS
```

Except the device also runs:

```
set winbox disabled=no port=8291
```

Winbox is a *second management path* the control never contemplated. The
control's conclusion — *"management access on this device is secure"* — is
**technically true and practically false.** You verified the doors you knew about
while a window stood open.

This is worse than a FAIL, because a FAIL gets fixed and this gets filed as
evidence of compliance.

**Therefore:** when a capability in a control family has an empty `assessed_by[]`,
every passing control in that family is downgraded:

```
NSCA-MGMT-002 → PASS (PARTIAL)
  ⚠ An unassessed management capability exists on this device (winbox/8291).
    This control's conclusion covers only the protocols it evaluates.
```

Findings are therefore **not independent**. Discovering something new re-opens
questions previously considered closed, and the system propagates that backwards.

> A tool that knows the limits of its own conclusions is a fundamentally
> different class of product from one that does not.

---

## 9. Framework versioning and drift

### 9.1 The version matrix

A "rulebook" for a platform is not one artifact. It is a matrix:

```
                  CIS v4.0   CIS v4.1   STIG 2025-10   STIG 2026-01
  IOS 12.x            ✓          ✓            —              —
  IOS 15.x            ✓          ✓            ✓              ✓
  IOS-XE 16.x         —          ✓            ✓              ✓
  IOS-XE 17.x         —          ✓            ✓              ✓
  NX-OS 9.x           —          —            ✓              ✓
```

Resolution logic answers: *given IOS-XE 16.12.4 and "CIS latest", what applies?*

**Where no content exists for a platform/version combination, the system refuses
and states this.** It does not silently approximate with the nearest benchmark.
An approximate audit that looks defensible is worse than an honest refusal.

### 9.2 Update workflow

Framework releases never silently change results:

```
Framework update available
  DISA STIG Cisco IOS-XE Router
  Current 2025-10 (Rel 12)  →  Available 2026-01 (Rel 13)

Content changes
  +  6 new rules
  ~  4 rules modified (severity or check logic)
  −  2 rules withdrawn

Estate impact — dry run against Campaign Q3-2026
  +  6 new findings across 41 devices
  ~  2 findings change severity CAT II → CAT I
  −  2 findings would close

  [ Review ]   [ Ratify ]   [ Defer ]
```

### 9.3 Benchmark drift decomposition

Because every campaign records the exact content version it ran against, a
period-over-period comparison can separate two entirely different phenomena:

```
Q3 2026: 78%   →   Q4 2026: 71%

  −4 pp   benchmark updated CIS v3.0.1 → v3.1.0
          (14 controls added, 6 tightened)
  −5 pp   genuine configuration regressions across 7 devices
  +2 pp   verified remediations closed (11 findings)
```

> **"You got worse" and "the bar moved" are different facts. A source of truth
> must separate them.**

Every organisation running periodic audits has been confused by this, and no
competing product addresses it.

### 9.4 Conflict between frameworks

Selecting CIS and STIG simultaneously will produce disagreements — one requires a
10-minute idle timeout, the other 5.

**Policy:** apply the stricter requirement, and report the conflict explicitly:

```
NSCA-MGMT-004 · Session idle timeout
  Device value:  600 s
  CIS-IOS-1.1.5 requires ≤ 600 s   → PASS
  STIG V-216620 requires ≤ 300 s   → FAIL
  Applied: STIG (stricter)          → FAIL

  ⚠ Framework conflict. Reported against the stricter requirement.
```

---

## 10. Validating the control library itself

Everything above assumes the controls are *correct*. Nothing guarantees that, and
a wrong control produces confident, wrong verdicts indefinitely. Four defences:

| Defence | What it catches |
|---|---|
| **Control unit tests** | Each control ships with fact-set fixtures and expected verdicts, including UNKNOWN and NOT_APPLICABLE cases |
| **Corpus regression** | The whole corpus is re-evaluated on every control change; any verdict that flips without an explanatory change is a defect |
| **Cross-validation** | Run OpenSCAP, CIS-CAT Lite or an equivalent reference implementation on the same configurations and compare on overlapping controls. Agreement with an independent implementation is evidence; a self-declared accuracy claim is not |
| **Expert review** | Control assertions and remediation ordering reviewed by a practising network security auditor. Their corrections encode tacit knowledge no document contains |

---

## 11. Summary

For any platform, the "rulebook" is five artifacts, not one:

1. **The rulepack** — how to read the platform ([07](07-vendor-rulepacks.md))
2. **Native controls** — vendor-neutral assertions over the schema. The
   evaluation engine
3. **Framework items** — imported from STIG XML directly, CIS PDFs via assisted
   extraction, NIST OSCAL for mapping, ISO as identifiers only. The *reporting
   vocabulary*, mapped onto native controls
4. **The binding layer** — remediation keyed on `(control, platform,
   version_range)`, plus applicability and not-applicable declarations
5. **The coverage manifest** — exactly what fraction of each benchmark is
   automated, what is procedural, and what is outstanding

And the unifying idea:

> **Known platforms are not a different mechanism. They are the same mechanism
> with the work already done, validated and certified — which is why teaching a
> new platform produces something structurally identical to what ships in the
> box.**
