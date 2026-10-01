# 00 · Product Overview

---

## 1. The problem

### 1.1 In one sentence

Organisations are legally and contractually required to harden every network
device against published security benchmarks, but they cannot do so at scale
because every manufacturer speaks a different configuration language and no tool
can read them all.

### 1.2 The situation

A network device — a switch, a router, a firewall — is a computer whose entire
behaviour is defined by one large text file. That file determines who may log in,
what traffic passes, how sessions are encrypted, and where logs are sent. A
misconfigured device is the single most common entry point in a network breach.

Because these mistakes are well understood, standards bodies publish hardening
benchmarks: **CIS Benchmarks**, **NIST SP 800-53**, **DISA STIGs**, and
**ISO/IEC 27001**. Compliance with them is mandated for critical infrastructure,
regulated industries, and government networks.

Checking one device against one benchmark, properly, takes a trained auditor
**30 to 90 minutes**. A mid-sized organisation has 200–2,000 devices. A bank or a
government department has tens of thousands.

The arithmetic does not work. So the audit does not happen properly. It is
sampled, deferred, delegated to a junior analyst with a text search, or bought
from a consultancy as a PDF that is filed and never actioned.

### 1.3 Why existing tools do not close the gap

| Approach | Limitation |
|---|---|
| Manual checklist auditing | Does not scale. Inconsistent between assessors. Stale on completion |
| Commercial audit suites (e.g. Nipper) | Closed, expensive, fixed vendor list. A new vendor requires the supplier to add support |
| Host-oriented scanners (OpenSCAP) | Built for servers. Weak coverage of network devices |
| Network behaviour modellers (Batfish) | Excellent modelling, limited vendor coverage, no compliance framework support |
| Vendor management suites (Cisco DNA, Panorama) | Only that vendor's equipment. Useless in mixed estates — which is every estate |
| Ad-hoc scripts (Ansible, Nornir) | Only check what was already thought of. Do not discover |

The hole in the middle: **nothing handles arbitrary vendors, and every tool
requires a software engineer and a release cycle to add a new one.**

### 1.4 The two structural difficulties

**Syntactic diversity.** The same security requirement — "disable Telnet, permit
only SSH" — is expressed in six structurally different paradigms across six
platforms: indentation hierarchies, flat path statements, brace nesting, block
keywords, XML, and key-value pairs. A parser written for one is useless for the
others.

**Non-stationarity.** The landscape does not hold still. White-box switches
running open network operating systems, cloud-native security groups, and
AI-fabric hardware all arrive continuously. Any tool built on a hardcoded
library of vendor commands is obsolete on a rolling basis — not because it was
written badly, but because someone shipped new hardware.

### 1.5 The unstated driver

The problem statement originates with **NTRO**, and its reference material points
at **NCIIPC** — the National Critical Information Infrastructure Protection
Centre. The intended deployment is critical national infrastructure: power,
telecommunications, banking, transport, government.

Read the vendor list in the problem statement and note what is on it: Huawei,
Sangfor, Hillstone, Ruijie, alongside Cisco, Palo Alto and Zscaler. In a national
security context there is a requirement that goes unstated in the text but is
obvious in the context:

> **You cannot use a manufacturer's own management suite to audit that
> manufacturer's equipment when the manufacturer is not fully trusted.**

Critical infrastructure needs an *independent* auditor — one that reports on a
device from the outside, with no dependency on the vendor, and no dependency on
an external network. This reframes the product from a convenience tool into a
**trust-independence** tool, and it is the strongest justification for
vendor-agnosticism and offline operation.

---

## 2. Product vision

> **A single source of truth for network security compliance across any estate,
> any vendor, and any framework — that can be taught a new device type by a
> network administrator in minutes, and whose every finding is backed by evidence
> a regulator would accept.**

---

## 3. The central design thesis

Everything in this product follows from one architectural decision:

> **Separate reading from judging.**

```
        READING                              JUDGING
  vendor-specific · hard              vendor-neutral · stable
  changes with every firmware         written once, rarely changes

  Cisco IOS      ─┐
  Juniper JunOS  ─┤
  FortiOS        ─┼──►  Security Baseline Model  ──►  Controls ──► Findings
  PAN-OS XML     ─┤        (facts + provenance)
  AWS JSON       ─┤               │
  MikroTik       ─┘               ▼
       ▲                  Configuration Graph
       │
  AI + human teach this side
```

All the difficulty and all the churn live on the left. The right side never
mentions a vendor: `mgmt.protocols.telnet.enabled must be false` is true of a
Cisco switch, a MikroTik router, and a device that has not been invented yet.

**Four consequences:**

1. **Adding a vendor costs nothing in audit logic.** Teach the system to read a
   new platform and every existing control begins working on it immediately.
2. **AI is never in the decision path.** It helps *author* a parsing rule; the
   rule does the work thereafter. Verdicts are therefore deterministic,
   reproducible, fast, offline-capable, and structurally immune to prompt
   injection via configuration comments.
3. **Adding a framework is the same machinery pointed the other way.** Vendor
   syntax and human-language standards are both ambiguous inputs to a formal
   core.
4. **The system degrades honestly.** Anything it cannot determine is reported as
   undetermined, never as compliant.

---

## 4. Target users

The problem statement is explicit that this is an **audit** tool for
administrators who *"lack a centralized 'Source of Truth' for compliance."*
The product does not attempt to become a configuration management system, a
change pipeline, or a network monitoring platform.

| Persona | Role in the product |
|---|---|
| **Lead Assessor / Auditor** | Primary user. Defines scope, runs campaigns, adjudicates findings, issues reports |
| **Network Administrator** | Supplies configurations, teaches the system unfamiliar platforms, disputes findings, performs remediation |
| **Security Manager / CISO** | Consumes estate-level posture, tracks remediation, reports upward |
| **Platform Administrator** | Manages rulepacks, framework versions, users, and deployment |

Detailed personas and journeys: [02-personas-and-journeys.md](02-personas-and-journeys.md)

---

## 5. Scope

### 5.1 In scope

- Ingestion of device configurations as **files** (single and bulk), as
  **structured cloud policy objects** (JSON), and via **read-only live
  collection**
- Multi-artifact correlation (`running-config` + `show version` + `show inventory`)
  to produce complete device identification including serial numbers
- Normalisation into a vendor-neutral **Security Baseline Model**
- Evaluation against **CIS, NIST SP 800-53, DISA STIG, ISO/IEC 27001**
- An **interactive training interface** allowing administrators to teach the
  system unseen configuration formats without code changes
- **Per-device PDF audit reports** with device identification, pass/fail with
  severity, evidence, and version-specific remediation command sequences
- Estate-level dashboards, historical campaigns, and remediation tracking
- Finding lifecycle: dispute, risk acceptance, verification, closure
- Full offline / air-gapped operation

### 5.2 Explicitly out of scope

| Not building | Why |
|---|---|
| Applying configuration changes to devices | An audit tool that can modify what it audits is not an audit tool. Assessor independence is a hard architectural constraint |
| Real-time network monitoring / NMS | Different product category, not in the problem statement |
| Firmware binary analysis | A capability that leaves no trace in configuration cannot be found by configuration analysis. Out of scope and stated as such |
| Vulnerability scanning by network probing | Read-only configuration analysis only |
| Intrusion detection / traffic analysis | Different product category |
| Configuration backup / change management | Adjacent, but not the stated problem |

### 5.3 Deliberate design boundaries

- **The platform never pushes configuration.** Remediation is emitted as a
  document or a signed patch bundle for the network team's own change process.
- **The platform requires no internet connectivity** for assessment.
- **The platform never reports an undetermined result as compliant.**

---

## 6. Success criteria

### 6.1 Product success

| Metric | Target |
|---|---|
| Time to onboard a previously unseen vendor | **< 15 minutes** of administrator time to reach ≥ 70% control coverage |
| Determinism | 100% — identical inputs produce byte-identical reports, hash-verified |
| Assessment throughput | ≥ 500 devices in under 5 minutes on commodity hardware, fully offline |
| Benchmark automation coverage | ≥ 80% of config-determinable recommendations for supported platforms |
| False positive rate on validated corpus | < 2% |
| Evidence completeness | 100% of findings cite artifact and line numbers |

### 6.2 Learning-system success

The defining measurement of the product's central claim:

```
Administrator confirmations required to reach 70% coverage,
by order in which the platform was taught

  Platform 1   ████████████████████████  47
  Platform 2   ███████████████           31
  Platform 3   ███████████               22
  Platform 4   ███████                   14
  Platform 5   █████                     11
  Platform 6   ████                       8
  Platform 7   ███                        6
```

A downward curve is evidence that the system accumulates *transferable*
knowledge rather than merely storing patterns. This is the measurable answer to
the problem statement's demand for **Scalability & Adaptation**.

---

## 7. What makes this different

Six properties, all within the problem statement's stated scope.

### 7.1 "Unknown" is a verdict, and coverage is a headline number

Every competing tool silently converts *"I could not parse this"* into *"no
violation found."* That manufactures false assurance on precisely the devices it
understands least — a green report on a device that was never actually read.

This platform reports three verdicts: **PASS**, **FAIL**, **UNKNOWN** — and
publishes a **coverage score** stating what proportion of applicable controls
could actually be determined.

### 7.2 Passes have a stated scope

A newly discovered capability can render an existing pass technically true and
practically false. If a device exposes a management service that no control
assesses, every passing management-plane control is downgraded to
`PASS (PARTIAL)` with the reason attached.

> The danger in audit tooling is not the failures it reports. It is the passes.

### 7.3 Findings are ranked by attack-path contribution

A flat list of 400 findings sorted by a static severity label is not actionable.
The platform computes reachability chains and reports:
*"Remediate these six findings and 340 of 400 become unreachable."*

### 7.4 Compensating controls are machine-verified

When an administrator disputes a finding by claiming a compensating control
— *"that device is only reachable from the isolated management network"* — the
platform verifies the claim against the configuration graph rather than
accepting it on assertion, and states its confidence and assumptions.

### 7.5 The estate is audited, not just the files received

Devices in scope but not collected are themselves findings, with reasons and
owners. Systemic patterns are reported as one root cause rather than N symptoms:
*"31 of 40 branch routers share this misconfiguration — this is a build-template
defect, not 31 independent problems."*

### 7.6 Novel capabilities are assessed by what they do

When a platform introduces a concept present in no framework anywhere, category
matching fails by definition. The platform instead characterises capabilities by
universal security properties — *listens, authenticates, executes, mutates,
transports, persists, default-on* — and applies property-derived controls.

These properties were true of Telnet in 1985 and will be true of whatever ships
in 2032. It is the only durable answer to the problem statement's instruction
that the system work *"regardless of vendor or market segment."*

---

## 8. Principal risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Grammar inference fails on structurally hostile formats (PAN-OS inheritance, FortiOS nesting) | High | Prove on five real formats before committing. Fall back to assisted grammar authoring |
| R2 | The Security Baseline Model is designed wrongly and everything downstream inherits the error | High | Design the schema first, against real configs, before writing pipeline code |
| R3 | An administrator teaches an incorrect mapping, especially an inverted polarity | High | Corpus validation, conflict detection, explicit polarity confirmation, two-person ratification, full attribution and rollback |
| R4 | Coverage honesty is perceived as weakness against competitors claiming 100% | Medium | Frame explicitly: an unexamined device is not a safe device. Publish the automation coverage manifest |
| R5 | CIS licensing restricts redistribution; ISO 27001 text cannot be redistributed at all | Medium | Import STIG XCCDF directly (free, machine-readable). Cite CIS and ISO control identifiers without reproducing text |
| R6 | Attack-path analysis demonstrates poorly on unrealistic topologies | Medium | Build a realistic multi-device reference estate |
| R7 | Provenance is lost when facts are extracted by a language model | Medium | Model output is a *proposal*; the stored artifact is a deterministic rule which by construction matches specific lines |

---

## 9. Positioning statement

> A compliance tool tells you what does not match a document.
>
> This platform builds a model of what your network actually permits, and then
> asks it questions. *"Does this match CIS"* is only one of them.

And the property underneath everything:

> **The AI helps write the rules. The rules make the call. Nothing that determines
> pass or fail is probabilistic, and nothing that is unknown is ever reported as
> compliant.**
