# 04 · System Architecture

---

## 1. Architectural thesis

> **Treat a configuration file as source code to be compiled, not as text to be
> searched or a prompt to be answered.**

A compiler takes source in many possible dialects, parses it into a structure,
lowers it into an intermediate representation, analyses that representation, and
emits output. Identical input produces identical output, always. Nobody would
accept a compiler that changed its mind between runs.

A network configuration is source code. The platform is a compiler for it.

```
  source          front end            IR              analysis        back end
 ─────────      ─────────────      ──────────       ────────────     ──────────
 config    →    lex · parse   →    Security    →    controls    →    report
 files          normalise          Baseline         graph            remediation
                                   Model            risk             exports
```

**Where machine learning sits:** in *authoring the front end*, never in producing
the output. When the system meets an unfamiliar dialect, AI helps a human turn
those lines into a **deterministic extraction rule**. That rule is tested,
versioned, ratified, and used deterministically for ever after.

At assessment time there are **zero model invocations**.

---

## 2. Layered view

```
┌──────────────────────────────────────────────────────────────────────┐
│  PRESENTATION                                                        │
│  Campaign console · Fleet view · Device detail · Training Studio     │
│  Finding workbench · Report viewer · Rulepack admin                  │
└──────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│  APPLICATION SERVICES                                                │
│  Campaign mgmt · Collection orchestration · Finding lifecycle        │
│  Adjudication · Remediation planning · Report generation · RBAC      │
└──────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│  ASSESSMENT ENGINE            ← fully deterministic, no model calls  │
│  Ingest → Fingerprint → Parse → Extract → Graph → Evaluate → Risk    │
└──────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│  LEARNING SUBSYSTEM           ← model-assisted, human-ratified       │
│  Grammar inference · Template mining · Candidate proposal            │
│  Confirmation UI · Rule synthesis · Validation · Ratification        │
└──────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│  KNOWLEDGE BASE               ← data, not code                       │
│  Rulepacks · Schema registry · Native controls · Framework maps      │
│  Defaults tables · Remediation templates                             │
└──────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│  PERSISTENCE                                                         │
│  Relational store · Artifact store · Search index · Job queue        │
└──────────────────────────────────────────────────────────────────────┘
```

**The critical boundary is between the Assessment Engine and the Learning
Subsystem.** They never run concurrently on the same request. Learning produces
knowledge-base artifacts; assessment consumes them. Nothing probabilistic ever
touches a verdict.

---

## 3. The assessment pipeline

```
   ┌──────────────┐
   │ 1 INGEST     │  files · cloud JSON · live collection
   └──────┬───────┘  multi-artifact correlation, custody, completeness
          ▼
   ┌──────────────┐
   │ 2 FINGERPRINT│  vendor · platform · OS version · model · serials
   └──────┬───────┘  → CVE lookup possible here, before any parsing
          ▼
   ┌──────────────┐
   │ 3 PARSE      │  grammar → parse tree → effective config resolution
   └──────┬───────┘  (unknown platform → grammar inference)
          ▼
   ┌──────────────┐
   │ 4 EXTRACT    │  parse tree → facts, each carrying provenance
   └──────┬───────┘  unmatched constructs → learning queue
          ▼
   ┌──────────────┐
   │ 5 GRAPH      │  objects and relationships across the estate
   └──────┬───────┘
          ▼
   ┌──────────────┐
   │ 6 EVALUATE   │  native controls → PASS · FAIL · UNKNOWN · N/A
   └──────┬───────┘  coverage · vacuity · scope contamination
          ▼
   ┌──────────────┐
   │ 7 RISK       │  exposure weighting · attack paths · peer anomaly
   └──────┬───────┘
          ▼
   ┌──────────────┐
   │ 8 REMEDIATE  │  ordered · version-specific · safety-checked · dry-run
   └──────┬───────┘
          ▼
   ┌──────────────┐
   │ 9 REPORT     │  per-device PDF · estate report · OSCAL · patch bundle
   └──────────────┘
```

Stages 1–9 are pure functions of `(artifacts, knowledge base version)`. This is
what makes reproducibility provable rather than aspirational.

---

## 4. Stage detail

### 4.1 Ingest

Three input channels, one internal representation.

| Channel | Formats |
|---|---|
| **File upload** | Text configs (all CLI dialects), XML (PAN-OS), JSON, archives, `show tech-support` bundles |
| **Cloud policy import** | AWS security groups & NACLs, Azure NSGs, GCP firewall rules, SASE policy exports |
| **Live collection** | Read-only SSH via Netmiko/NAPALM against reachable devices |

**Multi-artifact correlation is mandatory.** The report must contain serial
numbers and hardware details, and those are not in the running configuration:

```
Device CORE-SW-01
 ├─ running-config      security settings
 ├─ show version        OS version, model, uptime
 ├─ show inventory      chassis, line card and PSU serials
 └─ show tech           all of the above, if supplied as one bundle
```

Artifacts are correlated by hostname or serial and merged into one device record.
Every artifact is hashed at receipt and recorded with its custody metadata: who
supplied it, when, from which device, by which method.

**Export completeness detection.** Most platforms offer a terse export
(non-default settings only) and a verbose one. A terse export is a *diff against
defaults*; auditing it as though it were a complete state is a silent correctness
failure. The stage detects and reports which was supplied.

### 4.2 Fingerprint

Weighted signature matching produces `(vendor, platform, os_version, model,
serials[])` with a confidence score. Three outcomes:

| Outcome | Consequence |
|---|---|
| **Known platform** | Parse with the loaded rulepack |
| **Identifiable, untaught** | Grammar inference + learning queue. **CVE lookup works immediately** |
| **Wholly unknown** | Grammar inference from scratch |

The middle case matters: version-based vulnerability checking requires only the
fingerprint. A real finding is produced at 0% parse coverage on a platform never
previously seen.

> **One vendor is not one platform.** Cisco alone ships IOS, IOS-XE, NX-OS and
> IOS-XR — four different operating systems with different syntax. Rulepacks are
> keyed per platform, never per vendor.

### 4.3 Parse

Produces a typed parse tree in which every line is a node with a hierarchical
path, a verb, and attributes.

Supported structural paradigms:

| Paradigm | Example platforms |
|---|---|
| Indentation hierarchy | Cisco IOS, IOS-XE, NX-OS, Arista EOS |
| Flat path statements | Juniper set-format |
| Brace nesting | Juniper curly-format |
| Block keywords (`config`/`end`, `edit`/`next`) | FortiOS |
| XML | PAN-OS |
| Path headers with key-value pairs | MikroTik RouterOS |
| Native structured | AWS/Azure/GCP JSON |

**Effective configuration resolution** runs here. The text is not the truth:

- PAN-OS: shared → device-group → template stack → local override merge
- Juniper: `groups` and `apply-groups` expansion
- Cisco: overlapping `line vty` range resolution
- FortiOS: VDOM scoping

Facts derived from an inherited layer record which layer they came from, because
an auditor will be asked.

For unknown platforms, **grammar inference** operates statistically: detect the
comment character, the hierarchy paradigm, the statement shape, and recurring
verbs. See [08-learning-system.md](08-learning-system.md).

> Syntax is inferable automatically. Semantics is not. That boundary is the
> correct handoff point to a human.

### 4.4 Extract

Rulepack extractors convert parse-tree nodes into **facts** in the Security
Baseline Model. Every fact carries provenance:

```yaml
path:  mgmt.protocols.telnet.enabled
value: true
provenance:
  source:     explicit          # see the provenance model below
  artifact:   CORE-SW-01/running-config.txt
  lines:      [143]
  extractor:  cisco_ios.vty.transport_input@v7
  confidence: 1.0
```

**The provenance `source` field resolves the absence problem**, which is the most
dangerous ambiguity in configuration auditing:

| Source | Meaning | Trust |
|---|---|---|
| `explicit` | Written at line N | Full |
| `default_known` | Absent; verified default for this platform + version | Full |
| `default_inferred` | Absent; sibling devices express it, so probably default, value unverified | Partial |
| `inherited` | From a named parent layer | Full; cite the layer |
| `default_unknown` | Absent, default unknown | **None → forces UNKNOWN** |
| `not_applicable` | Platform has no such concept | No finding |

That penultimate row is the architectural guarantee: **on an unfamiliar platform,
silence produces uncertainty, never a pass.**

Constructs that no extractor matches are routed to the learning queue rather than
discarded.

### 4.5 Graph

Facts alone give line-level checks. The graph gives relationships — and
relationships are where real breaches live.

```
Nodes    Device · Interface · Zone · ACL · ACLRule · AddressObject
         ServiceObject · User · Route · VLAN · VRF · Service

Edges    applied_to · member_of · permits · references · in_zone
         routes_to · authenticates_via · inherits_from
```

Enables findings no single line reveals:

- A permit-any rule — harmless alone, critical once applied to an interface in
  the internet-facing zone
- An address group named `Trusted-Admins` transitively containing `0.0.0.0/0`
  three nestings down
- Device A blocks a path; Device B routes around it. Neither device is
  individually non-compliant — the estate is

Graph findings emit a **counterexample**, not an assertion:

> `203.0.113.5:44210 → 10.0.0.1:22 TCP` permitted via rule `outside-in` line 14,
> because group `Trusted-Admins` → group `Partners` → `0.0.0.0/0`

The graph also computes **device exposure**, consumed by risk weighting, and
serves **compensating control verification** during triage.

### 4.6 Evaluate

Native controls — vendor-neutral assertions over the schema — produce four
outcomes:

| Verdict | Meaning |
|---|---|
| **PASS** | Checked, compliant |
| **FAIL** | Checked, violating |
| **UNKNOWN** | Could not determine |
| **NOT_APPLICABLE** | Control does not apply to this platform or capability |

`NOT_APPLICABLE` is excluded from the compliance denominator. It is neither a
pass nor a failure, and conflating it with either corrupts the score in both
directions.

Three refinements computed here:

**Coverage score** — proportion of applicable controls actually determined.
Falls out of the architecture: a control whose required facts are missing or
`default_unknown` returns UNKNOWN automatically.

**Vacuity classification** — a pass because a feature is securely configured is
not the same as a pass because the feature is absent. The latter is *fragile*:
nothing constrains it if anyone enables it. Reported as
*"94% compliant; 31% of passes vacuous; configured posture 63%."*

**Scope contamination** — if a device exposes an unassessed capability in a
control family, every passing control in that family is downgraded to
`PASS (PARTIAL)` with the reason attached.

> The danger in audit tooling is not the failures it reports. It is the passes.

### 4.7 Risk

- **Exposure weighting** — severity modulated by the device's graph-derived
  position. Weak SSH on an internet-facing edge firewall is critical; the same
  finding on an isolated lab switch is medium.
- **Attack-path ranking** — compute reachability chains and report
  *"remediate these six and 340 of 400 become unreachable."*
- **Peer anomaly** — devices differing from their own siblings. Requires **no
  semantic understanding**, so it produces findings on platforms not yet taught.

### 4.8 Remediate

Output is a **safety-checked playbook**, not a command list:

- **Version-specific** — keyed on `(control, platform, version_range)`
- **Dependency-ordered** — configure the new authentication server *before*
  removing the local fallback account, never the reverse
- **Lockout-detected** — evaluate the assessor's own source address against the
  proposed management ACL in the model; block the step if it would be denied
- **Impact-classified** — `safe` / `service-affecting` / `lockout-risk`
- **Rollback provided** per step
- **Dry-run** — apply to the model, re-evaluate, report before/after and flag any
  control newly broken by the fix

The platform **never applies** remediation. See §6.

### 4.9 Report

Per-device PDF (the mandated artifact), estate report, and machine-readable
exports. Full specification in [10-reporting.md](10-reporting.md).

---

## 5. The knowledge base — three extensible layers

What makes *"support new vendors, standards, and OS versions without manual code
modifications"* literally true rather than aspirational.

| Layer | Contains | Extended by |
|---|---|---|
| **Rulepacks** | How to *read* a platform: fingerprints, grammar, extractors, defaults table, inheritance rules, quirks | Learning subsystem |
| **Schema registry** | What concepts *exist* — fact paths, types, categories | Novel capability discovery |
| **Control packs** | What is *required* — native controls, framework mappings, remediation templates | Framework import, or generalisation |

The problem statement says *"vendors, **standards**, and OS versions."* All three
layers must be runtime-extensible. Most implementations consider only the first.

**All three are versioned, diffable, signed, exportable and revertible** — which
is the reason knowledge is stored as data rather than as model weights. Weights
cannot be audited, cannot be partially rolled back, and cannot be shared as a
fraction.

---

## 6. Architectural constraints

These are non-negotiable and shape the design.

### C1 · Assessor independence

**The platform MUST be architecturally incapable of modifying a device.**
Collection is read-only; remediation is emitted as a document or a signed patch
bundle for the network team's own change process. An audit tool that can change
what it audits is not an audit tool.

### C2 · Offline operation

**Assessment MUST complete with no external network access.** The intended
deployment is critical national infrastructure. A tool requiring an external API
is not merely unusable there — using it would itself be a security incident.

Any model-assisted capability must offer a local-inference mode, and the entire
assessment path must function with the knowledge base already loaded.

### C3 · Determinism

Identical `(artifacts, knowledge base version)` MUST produce byte-identical
findings. No randomness, no wall-clock dependence, no model invocation in the
assessment path.

### C4 · Evidence binding

Every fact and every finding MUST trace to specific artifact lines. A finding
without evidence is an opinion.

### C5 · Never over-claim

The system MUST NOT report an undetermined result as compliant. UNKNOWN is a
first-class verdict and coverage is a headline metric.

### C6 · Injection resistance

Configuration files contain free-text comments and banner messages. A pipeline
that feeds raw configuration to a model and asks it for a verdict makes every one
of those strings an instruction. This platform is **structurally immune**:
comments are lexed as comments, and no model participates in a verdict.

---

## 7. Deployment topology

### 7.1 Standard on-premises

```
┌─────────────────────────────────────────────────────┐
│  Web UI  ──►  API  ──►  Application services        │
│                          │                          │
│                          ├─► Assessment workers     │
│                          ├─► Collection workers     │
│                          └─► Report workers         │
│                                                     │
│  Relational store · Artifact store · Search · Queue │
│                                                     │
│  Optional: local inference service (learning only)  │
└─────────────────────────────────────────────────────┘
```

Deployed as containers. No external dependency at assessment time.

### 7.2 Air-gapped

Identical, minus the collection workers where devices are unreachable. Knowledge
base updates — framework releases, rulepacks — arrive as **signed offline
bundles** transferred by physical media, verified on import, and reviewed before
ratification.

### 7.3 Assessor workstation

Single-node deployment for field assessment. Same engine, same knowledge base,
same reports.

---

## 8. Component responsibilities

| Component | Owns | Must not |
|---|---|---|
| **Ingestion** | Artifact receipt, custody, correlation, completeness | Interpret configuration content |
| **Fingerprint** | Platform identity and confidence | Extract security facts |
| **Parser** | Structure and effective-config resolution | Assign semantic meaning |
| **Extractor** | Parse tree → facts with provenance | Judge compliance |
| **Graph builder** | Objects, relationships, exposure | Judge compliance |
| **Control engine** | Verdicts, coverage, vacuity, contamination | Invoke any model |
| **Risk engine** | Exposure weighting, attack paths, anomaly | Alter verdicts |
| **Remediation planner** | Ordering, safety, rollback, dry-run | Apply anything to a device |
| **Report generator** | Documents and exports | Recompute verdicts |
| **Learning subsystem** | Proposals, synthesis, validation | Participate in assessment |
| **Knowledge base** | Versioned rulepacks, schema, controls | Contain executable code |

That final row is a real constraint: **rulepacks are declarative data, not
scripts.** A rulepack that could execute arbitrary code would make an imported
community rulepack a remote code execution vector.

---

## 9. Data flow for a single device

```
artifacts (n)
    │  hash, custody, correlate
    ▼
device record  ──► fingerprint ──► (platform, version, serials)
    │                                     │
    │                                     ├──► CVE lookup ──► findings
    ▼                                     │
parse tree ◄──────── rulepack grammar ◄───┘
    │
    │  effective config resolution
    ▼
facts[] with provenance ◄──── extractors ────► unmatched[] ──► learning queue
    │
    ├──────────────► graph nodes/edges ──► exposure, reachability
    │                                            │
    ▼                                            ▼
native controls ──► verdicts[] ──► risk weighting ──► ranked findings[]
                         │                                   │
                    coverage, vacuity,                        ▼
                    contamination                    remediation playbook
                         │                                   │
                         └───────────────┬───────────────────┘
                                         ▼
                              per-device report · exports
```

---

## 10. Technology posture

Specific library choices belong to implementation, but the architecture
constrains the shape:

| Concern | Requirement |
|---|---|
| Assessment engine | Must run offline, deterministically, without a model runtime |
| Knowledge base | Declarative, versioned, signable, diffable — not code |
| Policy evaluation | Expression language over facts; auditable, no arbitrary execution |
| Graph | In-process graph analysis; estate-scale, not web-scale |
| Reporting | Deterministic document generation; identical input, identical bytes |
| Model assistance | Pluggable; local inference mandatory, hosted optional |
| Persistence | Relational for entities; object store for artifacts; full-text search for the repository |
| Jobs | Queue-backed workers for bulk assessment, collection and reporting |

---

## 11. What the architecture deliberately refuses

| Refused | Reason |
|---|---|
| A model in the verdict path | Non-determinism, hallucination, injection exposure, offline failure, cost at scale |
| Fine-tuning per vendor | Cannot audit, cannot roll back one lesson, cannot share a fraction, cannot train air-gapped |
| Executable rulepacks | Imported community content would become a code execution vector |
| Write access to devices | Destroys assessor independence |
| Silent defaults on unknown platforms | Manufactures false assurance — the precise failure this product exists to prevent |
| Approximating a missing benchmark version | An approximate audit that looks defensible is worse than an honest refusal |
