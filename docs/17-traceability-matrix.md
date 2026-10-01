# 17 · Traceability Matrix

> Every requirement in the problem statement, mapped to the requirement that
> satisfies it and the document that specifies it. Read this to verify nothing
> in SIH26155 has been missed.

---

## 1. The five mandated platform features

The problem statement enumerates five. All are mandatory; none may be traded
away.

### F1 · Unified Ingestion Engine

> *"A dashboard for uploading single or bulk configuration files from any network
> device."*

| Element | Requirement | Document |
|---|---|---|
| Single-file upload | FR-ING-001 | [04 §4.1](04-system-architecture.md) |
| Bulk upload, archives, directories | FR-ING-002 | [12 §3](12-ux-specification.md) |
| All CLI structural paradigms | FR-ING-003, FR-PRS-001…006 | [07 §4](07-vendor-rulepacks.md) |
| XML exports (PAN-OS) | FR-ING-004 | [07 §4](07-vendor-rulepacks.md) |
| **Cloud policy JSON (AWS / Azure / GCP)** | FR-ING-005 | [04 §4.1](04-system-architecture.md) |
| SASE policy exports (Zscaler, Cato) | FR-ING-006 | [04 §4.1](04-system-architecture.md) |
| `show tech-support` bundles | FR-ING-007 | [07 §7.2](07-vendor-rulepacks.md) |
| **Live collection via Netmiko / NAPALM** | FR-ING-008, FR-ING-009 | [04 §4.1](04-system-architecture.md) |
| Dashboard UI | FR-UIX-001 | [12 §3](12-ux-specification.md) |

> **Note.** The vendor list in the problem statement names cloud-native firewalls
> and SASE platforms **twice**. These are not CLI configurations — they are
> structured API objects. A CLI-only implementation fails an explicitly listed
> requirement.

### F2 · AI-Powered Training Module

> *"A dedicated, intuitive GUI where administrators can 'train' the system to
> parse unseen vendor formats by mapping specific command outputs to compliance
> parameters."*

| Element | Requirement | Document |
|---|---|---|
| Triggered on unrecognised structure | FR-LRN-001 | [08 §1](08-learning-system.md) |
| Usable without programming skill | FR-LRN-002, NFR-USE-001/002 | [08 §6](08-learning-system.md) |
| Raw unrecognised lines presented | FR-LRN-003 | [08 §4.1](08-learning-system.md) |
| Manageable question count | FR-LRN-003…005 | [08 §4](08-learning-system.md) |
| Mapping to security categories | FR-LRN-008, FR-LRN-009 | [08 §6](08-learning-system.md) |
| **"Update internal heuristics"** | FR-LRN-019 | [08 §1](08-learning-system.md) |
| **No backend redeployment** | NFR-MNT-001…003 | [04 §5](04-system-architecture.md) |
| Dedicated GUI | FR-UIX-005…007 | [12 §6](12-ux-specification.md) |

> The problem statement's own word is **"heuristics"** — not weights, not
> retraining. This directly endorses the rulepacks-as-data design.

### F3 · Multi-Framework Compliance Engine

> *"A logic engine that evaluates configurations against user-selected benchmarks
> (CIS, NIST, STIGs, ISO)."*

| Element | Requirement | Document |
|---|---|---|
| Vendor-neutral evaluation | FR-CTL-001, FR-CTL-002 | [06 §2](06-controls-and-frameworks.md) |
| User-selected frameworks | FR-CTL-010, FR-UIX-009 | [06 §2](06-controls-and-frameworks.md) |
| CIS support | FR-CTL-010, NFR-CMP-001 | [06 §5](06-controls-and-frameworks.md) |
| NIST SP 800-53 support | FR-CTL-010 | [06 §5](06-controls-and-frameworks.md) |
| DISA STIG support | FR-CTL-010 | [06 §5](06-controls-and-frameworks.md) |
| ISO 27001 support | FR-CTL-010, NFR-CMP-002 | [06 §5](06-controls-and-frameworks.md) |
| Framework version pinning | FR-CTL-011 | [11 §10](11-audit-integrity.md) |
| Conflict resolution | FR-CTL-012 | [06 §9.4](06-controls-and-frameworks.md) |

> **Licensing constraint.** DISA STIG and NIST OSCAL content are freely
> redistributable. **CIS text redistribution is restricted; ISO/IEC 27001 text
> cannot be redistributed at all.** ISO support is a mapping of control
> identifiers. Stating this correctly is a credibility signal.

### F4 · Actionable Intelligence & PDF Reporting

> *"A comprehensive, single PDF report for each device."*

| Element | Requirement | Document |
|---|---|---|
| **Single PDF per device** | FR-RPT-001 | [10 §2](10-reporting.md) |
| Device identification | FR-RPT-002 | [10 §2.1](10-reporting.md) |
| **Serial numbers and hardware details** | FR-RPT-002, FR-RPT-003, FR-ING-010 | [10 §2.1](10-reporting.md) |
| Clear pass/fail results | FR-RPT-004 | [10 §2.3](10-reporting.md) |
| **Risk severity assessments** | FR-RSK-001, FR-RSK-002 | [09 §11](09-findings-lifecycle.md) |
| Device-specific CLI remediation | FR-RPT-005, FR-REM-001 | [10 §2.5](10-reporting.md) |
| **Customised to model and software version** | FR-RPT-006, FR-REM-002 | [06 §3](06-controls-and-frameworks.md) |

> **Two traps here.**
> **(a)** Serial numbers are **not in the running configuration.** They come from
> `show version` / `show inventory`. This forces multi-artifact ingestion
> (FR-ING-010) — a mandated report section is otherwise impossible to populate.
> **(b)** The mandated artifact is **per-device**. Estate-level reporting is
> additive, never a substitute.

### F5 · Vendor-Agnostic Scalability

> *"A modular architecture designed to support new vendors, standards, and OS
> versions without requiring manual code modifications for every update."*

| Element | Requirement | Document |
|---|---|---|
| New **vendors** as data | NFR-MNT-001, FR-LRN-019 | [07](07-vendor-rulepacks.md) |
| New **standards** as data | NFR-MNT-002 | [06 §5](06-controls-and-frameworks.md) |
| New **OS versions** as data | FR-REM-002, [07 §6](07-vendor-rulepacks.md) | [07 §6](07-vendor-rulepacks.md) |
| New **schema facts** as data | NFR-MNT-003, FR-EXT-010 | [05 §7](05-security-baseline-model.md) |
| Versioned, revertible, signable | NFR-MNT-004 | [11 §11](11-audit-integrity.md) |

> The word **"standards"** is easy to skim past. It requires the framework layer
> to be runtime-extensible too — not only vendors. **Three** knowledge layers,
> not one.

---

## 2. The suggested development workflow

| Problem statement suggestion | Treatment |
|---|---|
| *"Converting proprietary CLI outputs into a structured JSON/Schema model"* | The Security Baseline Model — [05](05-security-baseline-model.md) |
| *"Using Python libraries (e.g. **Netmiko or NAPALM**) for data collection"* | Read-only live collection — FR-ING-008/009 |
| *"Using NLP or pattern matching to identify keywords the system has not been pre-trained on"* | Template mining is pattern recognition; semantic mapping is NLP — [08 §4, §5](08-learning-system.md) |
| *"Generating dynamic PDFs ... customised based on the device's specific model and software version"* | Version-keyed remediation — FR-RPT-006, FR-REM-002 |

---

## 3. Background and core-challenge statements

| Statement | Where addressed |
|---|---|
| *"vast array of hardware from diverse vendors"* | Six structural paradigms plus grammar inference — [07 §4](07-vendor-rulepacks.md) |
| *"most common point of misconfiguration ... significant percentage of breaches"* | Attack-path analysis, breach chain — [01 §2.3](01-domain-primer.md), [09 §11](09-findings-lifecycle.md) |
| *"disabling insecure protocols (Telnet/HTTP)"* ★ | `mgmt.*` — [05 §4.2](05-security-baseline-model.md) |
| *"enforcing strong cryptographic suites"* ★ | `crypto.*` with algorithm canonicalisation — [05 §4.4](05-security-baseline-model.md) |
| *"configuring granular ACLs"* ★ | `filter.*` plus the configuration graph — [05 §4.8](05-security-baseline-model.md) |
| *"logging all administrative access"* ★ | `logging.*` — [05 §4.5](05-security-baseline-model.md) |
| *"expensive, vendor-locked enterprise management suites"* | Vendor-agnostic by construction; trust independence — [00 §1.5](00-product-overview.md) |
| *"lack a centralized 'Source of Truth'"* | Campaigns, history, repository, delta — [02 §4](02-personas-and-journeys.md) |
| *"Syntactic Diversity"* | The reading/judging separation — [04 §1](04-system-architecture.md) |
| *"Scalability & Adaptation"* | Learning curve as measured evidence — [08 §10](08-learning-system.md) |
| *"White Box networking (SONiC)"* | Grammar inference + property-derived controls — [06 §7](06-controls-and-frameworks.md) |
| *"Cloud-native security groups (AWS/Azure)"* | JSON ingestion — FR-ING-005 |
| *"traditional parsers fail ... cannot predict ... proprietary hardware"* | Learning subsystem — [08](08-learning-system.md) |
| *"support **any** network device configuration, regardless of vendor or market segment"* | Property-derived controls — [06 §7](06-controls-and-frameworks.md) |

★ = the four hardening families the problem statement names explicitly. All are
first-class schema domains.

---

## 4. Engine behaviour statements

| Statement | Where addressed |
|---|---|
| *"Normalization: map into a standardized, vendor-neutral schema (a 'Security Baseline Model')"* | [05](05-security-baseline-model.md) — the term is adopted verbatim |
| *"Deviation Analysis: compare against the chosen framework (e.g. checking if the parsed 'ssh_version' is '2')"* | FR-CTL-001…005, [06 §3](06-controls-and-frameworks.md) |
| *"Dynamic Adaptation (The 'Training' Loop)"* | [08](08-learning-system.md) in full |
| *"presented with the 'raw' unrecognized command lines"* | FR-LRN-003, real lines with line numbers — [12 §6.2](12-ux-specification.md) |
| *"user-friendly, low-code interface"* | Confirm-don't-author — FR-LRN-008, NFR-USE-002 |
| *"map these commands to specific security categories"* | Schema fact mapping with plain-language descriptions |
| *"'learning' to parse this new vendor's logic"* | Rule synthesis, validation, ratification — [08 §7, §8](08-learning-system.md) |

---

## 5. Deliverables

| Deliverable | Constraint | Note |
|---|---|---|
| Source Code Link | — | |
| README with setup instructions | — | Must include air-gapped installation |
| Architecture Document | **Max 2 pages** | Derived from [04](04-system-architecture.md) |
| Demo Video | **Max 2 minutes** | Approximately three beats; see below |
| Technical Presentation | **Max 5 slides** | |

> These caps are themselves a signal. The evaluator is asking for concision, and
> a submission that overruns reads as a team that cannot prioritise.

**Three demonstration beats that fit 120 seconds:**

1. **Bulk ingestion, offline** — hundreds of configurations across multiple
   platforms, including cloud JSON, assessed in seconds with no network
2. **Teaching an untaught platform live, with a timer** — coverage 0% → 71% in
   minutes, no code, no redeployment
3. **The per-device PDF** — serial numbers, evidence with line numbers,
   version-specific remediation with lockout warning, and the unassessed section

---

## 6. Context signals

| Signal | Reading | Consequence |
|---|---|---|
| Dataset field cites **nciipc.gov.in** | Deployment context is **critical national infrastructure** | Offline operation is a hard constraint — NFR-DEP-001 |
| Dataset field provides **helpdesk1@nciipc.gov.in** | A direct channel to the problem setter exists | Use it — most teams will not |
| Vendor list includes Huawei, Sangfor, Hillstone, Ruijie | Trust independence from vendor tooling | [00 §1.5](00-product-overview.md) |
| *"update its internal **heuristics**"* | Rule updates expected, not retraining | Endorses rulepacks-as-data |
| *"**Pattern Recognition** and NLP"* | Framework predates LLM assumptions | Mirror this vocabulary |
| *"'**Source of Truth**'"* in scare quotes | A system of record, not a scanner | Campaigns, history, delta — [02](02-personas-and-journeys.md) |
| *"Physical Infrastructure (Corning)"* | List padding to emphasise **"any"** | Property-derived controls — [06 §7](06-controls-and-frameworks.md) |
| Theme: *"Blockchain & Cybersecurity"* | **Blockchain is never mentioned in the description.** It is a filing category | Do not bolt one on. Hash-chained audit log ([14](14-data-model.md)) is appropriate and sufficient |

---

## 7. Capabilities beyond the problem statement

Additive. Each is justified against a statement in the text rather than invented
freely.

| Capability | Justification | Document |
|---|---|---|
| **UNKNOWN verdict + coverage score** | Without it, an unparseable device reports as compliant — defeating *"Source of Truth"* entirely. **The most important addition** | [09 §1](09-findings-lifecycle.md) |
| **Scope contamination** | A pass whose scope is unstated is a false assurance | [09 §2.2](09-findings-lifecycle.md) |
| **Attack-path prioritisation** | Serves *"Actionable Intelligence"* — 400 undifferentiated findings are not actionable | [09 §11](09-findings-lifecycle.md) |
| **Peer anomaly detection** | Serves *"Source of Truth"* and *"any vendor"* — produces findings on untaught platforms | [04 §4.7](04-system-architecture.md) |
| **Property-derived controls** | The only durable answer to *"regardless of vendor or market segment"* | [06 §7](06-controls-and-frameworks.md) |
| **Machine-verified compensating controls** | Serves the audit lifecycle the *"Source of Truth"* framing implies | [09 §6](09-findings-lifecycle.md) |
| **Benchmark drift decomposition** | A source of truth must distinguish posture change from standard change | [11 §10](11-audit-integrity.md) |
| **Remediation safety and dry run** | *"Remediation Paths"* that cause an outage are not actionable intelligence | [10 §2.5](10-reporting.md) |
| **Collection completeness** | An audit covering 94% of scope while presenting as complete is misleading | [02 §5](02-personas-and-journeys.md) |
| **Systemic findings** | Thirty-one findings with one root cause is one insight, not thirty-one | [09 §10](09-findings-lifecycle.md) |
| **Vacuous vs meaningful passes** | A compliance figure that counts absent features as secure is not a source of truth | [09 §2.1](09-findings-lifecycle.md) |

---

## 8. Requirement coverage summary

| Area | Requirements | Specification |
|---|---|---|
| Campaigns | 10 | [02](02-personas-and-journeys.md), [14](14-data-model.md) |
| Ingestion | 18 | [04 §4.1](04-system-architecture.md) |
| Fingerprinting | 6 | [07 §3](07-vendor-rulepacks.md) |
| Parsing | 14 | [07 §4](07-vendor-rulepacks.md), [08 §3](08-learning-system.md) |
| Extraction | 10 | [05](05-security-baseline-model.md), [07 §5](07-vendor-rulepacks.md) |
| Graph | 8 | [04 §4.5](04-system-architecture.md) |
| Control evaluation | 17 | [06](06-controls-and-frameworks.md) |
| Risk | 10 | [09 §11](09-findings-lifecycle.md) |
| Remediation | 11 | [10 §2.5](10-reporting.md) |
| Learning | 28 | [08](08-learning-system.md) |
| Findings | 16 | [09](09-findings-lifecycle.md) |
| Reporting | 21 | [10](10-reporting.md) |
| Integrity | 12 | [11](11-audit-integrity.md) |
| Interface | 12 | [12](12-ux-specification.md) |
| Administration | 10 | [13](13-nonfunctional-requirements.md) |
| API | 6 | [15](15-api-specification.md) |
| **Functional total** | **209** | |
| Non-functional | 71 | [13](13-nonfunctional-requirements.md) |

---

## 9. Verification checklist

Before submission, confirm each mandated element is demonstrable:

- [ ] Single **and** bulk upload, including **cloud JSON**, not CLI only
- [ ] Training GUI that **persists** and demonstrably changes the next run
- [ ] Framework selector across CIS / NIST / STIG / ISO with versions stated
- [ ] **One PDF per device**, not only an estate dashboard
- [ ] PDF contains **serial numbers** — proving multi-artifact ingestion works
- [ ] PDF shows pass/fail with **risk severity assessments**
- [ ] PDF shows **version-specific** CLI remediation
- [ ] A new platform added **without any code change or redeployment**
- [ ] A new **framework** added without code change
- [ ] Full assessment runs with **the network disconnected**
- [ ] Every finding cites artifact and **line numbers**
- [ ] UNKNOWN is visually **impossible to confuse** with PASS
- [ ] Netmiko/NAPALM collection demonstrable against a virtual lab
