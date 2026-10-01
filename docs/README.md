# NSCA — Network Security Compliance Auditor

**Product Requirements Documentation**

> Working name: **NSCA**. Referred to throughout as "the platform" or "the system."
> Built for **SIH 2026 · Problem Statement SIH26155** · National Technical Research Organisation (NTRO)

---

## What this is

A complete product specification for an AI-augmented, vendor-agnostic network
security compliance auditing platform. These documents describe **what is being
built and why**, not how to code it.

The platform ingests configuration files from any network device — regardless of
manufacturer, operating system, or whether the device even has a command line —
normalizes them into a single vendor-neutral model of security posture, evaluates
that model against CIS / NIST / DISA STIG / ISO 27001, and produces defensible
per-device audit reports with evidence and version-specific remediation.

When it encounters a format it has never seen, it does not fail and it does not
require a software engineer. It asks an administrator a small number of targeted
questions, converts the answers into permanent parsing rules, and continues.

---

## Document index

| # | Document | What it covers |
|---|---|---|
| — | [README.md](README.md) | This file — index and conventions |
| 00 | [Product Overview](00-product-overview.md) | Vision, problem, users, scope, non-goals, success criteria |
| 01 | [Domain Primer](01-domain-primer.md) | Networking and compliance background for team members new to the domain |
| 02 | [Personas & Journeys](02-personas-and-journeys.md) | Who uses this, their jobs, and the full audit lifecycle |
| 03 | [Functional Requirements](03-functional-requirements.md) | Numbered, testable requirements — the contract |
| 04 | [System Architecture](04-system-architecture.md) | Components, pipeline, data flow, deployment topology |
| 05 | [Security Baseline Model](05-security-baseline-model.md) | The vendor-neutral schema — the heart of the system |
| 06 | [Controls & Frameworks](06-controls-and-frameworks.md) | Control model, framework mapping, benchmark import, coverage |
| 07 | [Vendor Rulepacks](07-vendor-rulepacks.md) | How platforms are read — fingerprints, grammars, extractors, defaults |
| 08 | [Learning System](08-learning-system.md) | The training loop — how new vendors are taught |
| 09 | [Findings & Lifecycle](09-findings-lifecycle.md) | Verdicts, evidence, state machine, risk acceptance |
| 10 | [Reporting](10-reporting.md) | Per-device PDF, estate reports, machine-readable exports |
| 11 | [Audit Integrity](11-audit-integrity.md) | Reproducibility, provenance, trust tiers, independence |
| 12 | [UX Specification](12-ux-specification.md) | Screen inventory and key interaction flows |
| 13 | [Non-Functional Requirements](13-nonfunctional-requirements.md) | Performance, scale, security, air-gap operation |
| 14 | [Data Model](14-data-model.md) | Entities and relationships |
| 15 | [API Specification](15-api-specification.md) | External interface surface |
| 16 | [Glossary](16-glossary.md) | Domain and product terminology |
| 17 | [Traceability Matrix](17-traceability-matrix.md) | Every PS requirement mapped to a requirement and a component |

---

## Suggested reading order

**If you are new to the domain (networking, compliance):**
`01 → 00 → 02 → 05 → 06 → 03`

**If you are implementing:**
`00 → 04 → 05 → 06 → 07 → 08 → 09 → 03`

**If you are writing the pitch, deck, or architecture document:**
`00 → 02 → 11 → 17`

**If you are reviewing against the problem statement:**
`17 → 03`

---

## Conventions used across these documents

### Requirement identifiers

```
FR-<AREA>-<NNN>     Functional requirement
NFR-<AREA>-<NNN>    Non-functional requirement
```

Areas: `ING` ingestion · `FPR` fingerprinting · `PRS` parsing · `EXT` extraction ·
`GRF` graph · `CTL` control evaluation · `RSK` risk · `REM` remediation ·
`RPT` reporting · `LRN` learning · `FND` findings · `CMP` campaign ·
`INT` integrity · `UIX` interface · `API` interface · `ADM` administration ·
`PERF` performance · `SEC` security · `DEP` deployment

### Requirement strength

| Word | Meaning |
|---|---|
| **MUST** | Mandatory. The product is incomplete without it |
| **SHOULD** | Strongly expected. Omission requires explicit justification |
| **MAY** | Optional. Included when capacity allows |

### Identifier formats used by the product itself

```
NSCA-<FAMILY>-<NNN>          Native control        e.g. NSCA-MGMT-002
<platform>.<area>.<name>     Extractor             e.g. cisco_ios.vty.transport_input
<domain>.<path>.<field>      Schema fact           e.g. mgmt.protocols.telnet.enabled
```

---

## The one-paragraph summary

> Every competing approach treats a configuration file as text to be searched, or
> as a prompt to be answered. This platform treats it as **source code to be
> compiled** — parsed into a structure, lowered into a vendor-neutral
> intermediate representation, and analysed by a deterministic engine.
> Artificial intelligence is used to *author the compiler*, never to *deliver the
> verdict*. The result is an audit that is reproducible, evidence-bound,
> offline-capable, and honest about what it could not determine.

---

## Status

| Document | Status |
|---|---|
| 00–17 | Draft v1.0 — complete specification, pending implementation feedback |

Changes to these documents should be made by editing the relevant file and
updating the traceability matrix (17) if requirements change.
