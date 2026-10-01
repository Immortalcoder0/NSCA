# NSCA — AI-Driven Multi-Vendor Network Security Compliance Auditor
### Architecture Document · SIH26155 · NTRO

---

## 1. Problem and design thesis

Network devices are computers whose entire behaviour is one text file. Checking
one against one benchmark takes a trained auditor 30–90 minutes; organisations
have thousands. Existing tools work only for vendors somebody already programmed
in, and adding a vendor requires an engineer and a release cycle.

The obvious solution — send the config to a language model and ask for findings —
fails five ways that matter to an auditor: it is **non-deterministic** (same file,
different answers), it **hallucinates line numbers**, it is **unauditable**, it
**cannot run air-gapped** (fatal for NCIIPC-scope networks, where a config is a
map of the network's defences), and it **cannot scale** to 10,000 devices.

Our thesis:

> **Separate reading from judging. AI authors the reader; a deterministic engine
> delivers the verdict.**

```
        READING                              JUDGING
  vendor-specific · changes           vendor-neutral · written once
  with every firmware release         never mentions a vendor

  Cisco IOS  ─┐
  JunOS      ─┤
  FortiOS    ─┼──► Security Baseline Model ──► Controls ──► Findings
  PAN-OS XML ─┤      (facts + provenance)          │
  AWS/Azure  ─┤              │                     ▼
  MikroTik   ─┘              ▼             CIS · NIST · STIG · ISO
       ▲              Configuration Graph
       │
  AI + administrator teach this side
```

All difficulty and churn sit on the left. The right side is
`mgmt.protocols.telnet.enabled == false` — true of a Cisco switch, a MikroTik
router, and a device not yet invented. Four consequences:

1. **Teaching a vendor costs nothing in audit logic.** Every existing control
   starts working the moment facts appear.
2. **Zero model calls at assessment time** → deterministic, offline, fast, and
   structurally immune to prompt injection via config comments.
3. **Adding a framework is the same machinery reversed** — vendor syntax and
   human-language standards are both ambiguous inputs to a formal core.
4. **The system degrades honestly** — see §4.

---

## 2. Pipeline

```
INGEST → FINGERPRINT → PARSE → EXTRACT → GRAPH → EVALUATE → RISK → REMEDIATE → REPORT
```

| Stage | Function |
|---|---|
| **Ingest** | Files, bulk archives, `show tech` bundles, **cloud policy JSON (AWS/Azure/GCP)**. Correlates `running-config` + `show version` + `show inventory` into one device record — **serial numbers are not in the running config**. Live collection (Netmiko/NAPALM) is API-contracted only; the transport driver isn't built yet |
| **Fingerprint** | Vendor, platform, OS version, model, serials. CVE lookup runs here — real findings at **0% parse coverage** on an unknown platform |
| **Parse** | Six structural paradigms (indentation, flat-path, brace, block-keyword, XML, path-header) plus native JSON. Resolves **effective configuration** — PAN-OS device-group merge, Juniper `apply-groups`, overlapping `line vty` ranges |
| **Extract** | Rulepack extractors → schema facts, each carrying provenance: artifact, line numbers, extractor version |
| **Graph** | Objects and relationships across the estate. Catches emergent violations where *no single line is non-compliant* — a permit-any rule bound to an internet-facing interface, a group transitively containing `0.0.0.0/0` |
| **Evaluate** | Controls assert over facts. Four verdicts (§4) |
| **Risk** | Exposure-weighted severity; attack-path ranking; peer anomaly |
| **Remediate** | Version-specific CLI, dependency-ordered, **lockout-checked**, with rollback and dry-run |
| **Report** | One PDF per device + estate report + JSON/CSV/OSCAL |

---

## 3. Three knowledge layers — why "no code change" is literally true

| Layer | Holds | Extended by |
|---|---|---|
| **Rulepacks** | How to *read* a platform: fingerprints, grammar, extractors, version-keyed defaults, inheritance rules — 7 rulepacks today (one per paradigm below), 43 extractors total, en route to a much larger target as coverage matures | Learning loop |
| **Schema registry** | What concepts *exist* | New capability discovery |
| **Control packs** | What is *required*, plus framework mappings | Framework import |

The PS says *"new vendors, **standards**, and OS versions."* All three layers are
runtime-extensible data — versioned, signed, diffable, revertible. Most
implementations consider only the first.

### The learning loop

When an unrecognised format arrives, the system does not fail and does not need a
programmer:

1. **Grammar inference** (statistical, no model) recovers structure — comment
   character, paradigm, statement shape, verbs. *Syntax is inferable; semantics
   is not.*
2. **Template mining** collapses 4,000 lines → ~120 templates → ~15 relevant →
   **9 questions**, ordered by information gain.
3. **Proposal** from lexical priors (`telnet`/`ssh`/`snmp` are RFC-mandated
   shared vocabulary), structural analogy, value-shape. A model refines
   heuristically when reachable; **a human confirms** either way.
4. **Polarity** (`disabled=no` → `enabled=true`) requires separate explicit
   confirmation — inverting it certifies a wide-open device as compliant, the
   one error class that degrades toward *false confidence*.
5. **Synthesis** produces a deterministic rule, gated on six checks (self-match,
   cross-platform scope, conflict, type, regression, metamorphic stability).
6. **Confirmed examples become frozen regression tests** — annotation and test
   suite are the same artifact.
7. **Two-person ratification** before use in an issued report.

Target: teach a platform to ≥70% coverage in minutes, no code, no redeployment,
with each platform cheaper to teach than the last (`transfer_metrics` records
`confirmations_to_70pct` per session, in teaching order, as the evidence). The
mechanism is real and unit-tested; a recorded multi-platform curve from this
codebase, closing the full ratify→re-assess→measure loop, is not yet built
(release-gate-checklist B13, PARTIAL) — cite the live demo's own number, not a
pre-printed one.

---

## 4. What makes it trustworthy

**Four verdicts, not two.** `PASS · FAIL · UNKNOWN · NOT_APPLICABLE`. Every
control declares `requires_facts`; a missing or default-unknown fact returns
**UNKNOWN automatically** — it is structural, not an implementer's choice. A
**coverage score** accompanies every compliance figure.

> Competing tools silently convert *"couldn't parse"* into *"no violation found"* —
> a green report on a device never actually read.

**Passes have stated scope.** An unassessed capability (MikroTik's Winbox on
8291) downgrades every passing management control to `PASS (PARTIAL)`. *The
danger in audit tooling is not the failures it reports — it is the passes.*

**Evidence binding.** Every finding cites artifact and line numbers with the
excerpt, secrets masked. Graph findings emit a concrete counterexample packet and
rule chain.

**Determinism.** Identical inputs + pinned knowledge base → byte-identical
report, hash-verified. Enforced by construction: no model, no clock, no
randomness, no float in scoring.

**Assessor independence.** No code path exists that modifies a device —
compile-time command allowlist, verified by CI. Remediation is a document.

---

## 5. Deliverable mapping

| PS requirement | Implementation |
|---|---|
| Unified ingestion, single + bulk, any device | §2 — including cloud JSON, listed twice in the PS and usually skipped |
| AI training module, low-code GUI | §3 — confirm-don't-author; no regex ever shown |
| Multi-framework engine (CIS/NIST/STIG/ISO) | Two-tier model: evaluate once natively, report in four vocabularies. STIG imports as XCCDF XML; CIS/ISO cite identifiers only (licensing) |
| Per-device PDF: serials, severity, version-specific CLI | §2 — multi-artifact ingestion makes serials possible |
| Vendor-agnostic scalability, no code modification | §3 — three data layers |

**Stack:** Python/FastAPI · PostgreSQL · declarative rulepacks and control packs
(no executable content — imported packs would otherwise be an RCE vector) ·
React · WeasyPrint (native Pango/Cairo; needs the GTK stack, absent by default
on Windows) · local inference (Ollama), optional — the learning subsystem
proposes heuristically with no model reachable, and hosted/external inference
is refused in code (`InferenceMode.HOSTED` raises), not just policy.

**Verification:** 14 release-blocking criteria (`plans/release-gate-checklist.md`):
8 pass, 5 partial (real coverage exists but doesn't close the criterion
exactly as stated), 1 not-yet (B14 — a manual, unaided-administrator timing
procedure). None waived; a partial is reported as partial, not rounded up.
