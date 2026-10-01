# 16 · Glossary

> Domain terms, product terms, and the distinctions that matter. Terms marked
> **[P]** are specific to this product; others are industry standard.

---

## Networking

**ACL — Access Control List**
An ordered set of rules on a device permitting or denying traffic by source,
destination, protocol and port. Evaluated top-down; the first match usually wins,
which is why rule *order* is security-relevant.

**AAA — Authentication, Authorisation, Accounting**
The framework governing who may log in, what they may do, and what is recorded.
On Cisco platforms, enabled by `aaa new-model`.

**Address object / object group**
A named collection of addresses referenced by ACL rules. Groups may contain other
groups. **Transitive expansion is essential** — a group named `Trusted-Admins`
may contain `0.0.0.0/0` three nestings down.

**Community string**
SNMP's password. `public` and `private` are factory defaults and universally
known.

**Effective configuration**
What a device *actually* does, after resolving inheritance, overrides and
overlapping scopes. **Not the same as the text of the configuration file** — see
*inheritance*.

**Firewall**
A policy enforcement point at a network boundary deciding what traffic may pass.

**Management plane**
The subsystem by which a device is administered — login, configuration,
monitoring. Distinct from the *control plane* (routing protocol exchange) and the
*data plane* (traffic forwarding). Roughly 60% of any hardening benchmark
concerns the management plane, and it is where breaches begin.

**Running configuration**
The device's live configuration state, dumped as text by `show running-config`
or equivalent. **The single artifact that defines a device's entire behaviour.**

**Router · Switch**
A router connects different networks; a switch connects machines within one. Both
are computers running an operating system.

**Serial number**
A hardware identifier. **Not present in the running configuration** — obtained
from `show version` or `show inventory`. This is why multi-artifact ingestion is
mandatory.

**SNMP — Simple Network Management Protocol**
A protocol for reading and writing device state. v1 and v2c authenticate with a
plaintext community string; v3 supports authentication and encryption.

**SSH · Telnet**
Remote login protocols. SSH is encrypted; **Telnet transmits credentials in
plaintext** and has been unacceptable since roughly 1995. It remains ubiquitous.

**Type 7 password**
Cisco's reversible password encoding — a Vigenère-style XOR with a publicly known
key. Not encryption. Decodable in seconds. Contrast **type 8** (PBKDF2) and
**type 9** (scrypt), which are properly hashed. Distinguishing these *is* a
compliance control.

**VTY line**
Virtual terminal lines — the configuration block governing remote login sessions.
`line vty 0 4` and `line vty 0 15` may both exist and overlap, with non-obvious
resolution rules.

**Zone**
A named trust boundary grouping interfaces. Used by firewalls to express policy
between security domains.

---

## Compliance and audit

**Benchmark**
A published set of hardening recommendations for a specific platform.

**CIS Benchmark**
Published by the Center for Internet Security. One document per platform,
100–200 numbered recommendations, each with rationale, audit procedure,
remediation and **documented default value**. Free with registration;
**redistribution of the text is restricted**.

**Compensating control**
A measure elsewhere that mitigates the risk of a finding, permitting acceptance
without direct remediation. In this product, a claimed compensating control is
**machine-verified against the configuration graph** rather than accepted on
assertion.

**DISA STIG**
Security Technical Implementation Guide, from the US Defense Information Systems
Agency. Prescriptive, platform-specific, and **distributed as machine-readable
XCCDF XML**. Freely available — the best import source.

**Finding**
An assertion that a device does or does not satisfy a control, supported by
evidence.

**ISO/IEC 27001**
International standard for information security management. Governance-level. A
**paid standard whose text cannot be redistributed** — identifiers only.

**Materiality**
Whether a finding is significant enough to affect an audit conclusion. An audit
concept, not a technical one.

**NIST SP 800-53**
A catalogue of ~1,000 security controls for US federal systems, organised into
families (AC, AU, IA, SC). **Policy-level, not device-level.** Published as OSCAL
JSON, freely available.

**OSCAL**
NIST's Open Security Controls Assessment Language — a machine-readable format for
control catalogues and assessment results.

**Remediation**
The specific commands that resolve a finding on a specific platform at a specific
software version.

**Risk acceptance**
A formal decision to tolerate a finding, with an owner, justification, **mandatory
expiry**, and a compensating control.

**XCCDF**
Extensible Configuration Checklist Description Format — the XML schema in which
STIGs are published.

---

## Product terms **[P]**

**Assessment**
One execution of the pipeline against one device in one campaign.

**Assessor independence**
The architectural property that the platform **cannot** modify an audited device.
Enforced by the absence of a write path, not by permissions. An audit tool that
can change what it audits is not an audit tool.

**Attack path**
An ordered chain of findings that together enable reachability from an untrusted
zone to a protected asset. Used to prioritise: *"remediate these six and 340 of
400 findings become unreachable."*

**Automation coverage manifest**
A published statement of what proportion of a benchmark the platform automates,
what requires manual assessment, what needs uncollected data, and what is
unimplemented. An assessor cannot sign off without it.

**Benchmark drift**
Change in a compliance figure caused by the *standard* changing rather than the
configuration. Reported separately: *"you got worse"* and *"the bar moved"* are
different facts.

**Campaign**
The audit engagement: scope, frameworks, owner, window, and pinned knowledge base
versions. Everything is anchored to one.

**Confirm-don't-author**
The interaction principle of the training system. The user validates a proposal
rather than writing a rule, because humans are fast and accurate at *"is this
right?"* and slow and unreliable at *"write the correct rule."*

**Contamination** — see *scope contamination*

**Counterexample**
For graph-derived findings, the concrete packet and rule chain demonstrating the
violation — since no single configuration line is wrong.

**Coverage score**
The proportion of applicable controls actually determined.
`(PASS + FAIL) / (total − NOT_APPLICABLE)`. **Compliance without coverage is
meaningless:** 100% compliance at 20% coverage is an unfinished audit.

**Derived fact**
A fact computed from other facts rather than extracted. Inherits the **weakest**
provenance of its inputs — uncertainty propagates rather than being laundered.

**Effective severity**
Base severity after contextual modification by device exposure.

**Exposure**
A device's position relative to untrusted networks, derived from the graph, not
read from configuration. Drives severity weighting.

**Extractor**
A declarative rule mapping parse-tree structure to a schema fact. The unit of
learning. Ships with tests frozen from confirmed examples.

**Fact**
The atomic unit of the Security Baseline Model: a schema path, a typed value, and
provenance.

**Grammar inference**
Statistical recovery of an unknown configuration format's structure — comment
character, hierarchy paradigm, statement shape, verbs — before any human is
involved. **Syntax is inferable; semantics is not.**

**Information gain ordering**
Ranking training questions by how many undetermined controls each answer would
resolve, so the first three questions deliver most of the coverage.

**Knowledge base**
The three runtime-extensible data layers: rulepacks (how to read), schema
registry (what exists), control packs (what is required).

**Learning curve**
Confirmations required per platform, plotted in the order platforms were taught.
A declining curve is evidence of **transferable** knowledge, and is the measurable
answer to *"Scalability & Adaptation."*

**Meaningful pass** — see *vacuous pass*

**Native control**
A vendor-neutral assertion over the Security Baseline Model. The evaluation
engine. Contrast **framework item**, which is the reporting vocabulary.

**Peer anomaly**
A device deviating from its structurally similar siblings. Requires **no semantic
understanding**, so it produces findings on platforms not yet taught. Recovers an
organisation's unwritten policy from its own estate.

**Polarity**
Whether a configuration statement asserts a capability positively (`transport
input telnet`) or negatively (`set admin-telnet disable`, `disabled=no`).
**Inverting it certifies a wide-open device as compliant** — the
highest-consequence error class in the system, and why it always requires
explicit confirmation.

**Property-derived control**
A control applying to any capability characterised by universal security
properties, rather than by category. Enables assessment of features that did not
exist when the control was written.

**Provenance**
The record of how a fact was determined: source classification, artifact, line
range, extractor, confidence. What makes a finding evidence rather than an
opinion.

**Provenance source classification**
`explicit` · `default_known` · `default_inferred` · `inherited` ·
`default_unknown` · `not_applicable` · `derived`.
**`default_unknown` forces UNKNOWN** — the mechanism by which silence never
becomes compliance.

**Provisional**
A taught rule not yet ratified. Usable for exploration; **findings excluded from
issued reports.** A finding derived from provisional parsing is not evidence.

**Reproducibility manifest**
Hashes of inputs plus versions of every knowledge component, sufficient to
re-execute an assessment exactly.

**Rulepack**
Everything needed to read one platform: fingerprint signatures, grammar,
extractors, version-keyed defaults table, inheritance rules, quirks. Declarative
data, never code — because rulepacks are importable, and executable content would
be a code execution vector.

**Scope contamination**
The downgrading of passing controls when a device exposes a capability no control
assesses. `PASS → PASS (PARTIAL)`. Findings are not independent: discovering
something new re-opens questions previously considered closed.

> The danger in audit tooling is not the failures it reports. It is the passes.

**Security Baseline Model (SBM)**
The vendor-neutral schema. The intermediate representation of the compiler.
Everything upstream converts into it; everything downstream reasons over it.

**Systemic finding**
The same defect across many devices, reported as one root cause with an affected
list. *"Thirty-one findings, one build template."*

**Template collapse**
Abstracting variable tokens so that thousands of unrecognised lines become tens
of distinct patterns — turning 4,000 lines into 9 questions.

**Trust tier**
How much validation sits behind a rulepack: `certified` · `verified_community` ·
`local` · `provisional`. Stated in every report.

**Two-person rule**
Rulepack ratification requires a different user from the author. The same control
the product recommends for network changes, applied to itself.

**Unaudited surface**
A capability present on a device that no loaded control evaluates. Reported as a
finding in its own right, and the trigger for scope contamination.

**Vacuous pass**
A pass because a feature is *absent*, as opposed to a **meaningful pass** where
the feature is present and securely configured. Not less secure today; **less
assured tomorrow** — nothing constrains the feature if anyone enables it.

**Verdict**
`PASS` · `FAIL` · `UNKNOWN` · `NOT_APPLICABLE` · `PASS (PARTIAL)`.
Most tools have two, and that is the root of their dishonesty.

---

## Distinctions that matter

| Often confused | Actually |
|---|---|
| **UNKNOWN** vs **NOT_APPLICABLE** | *"I could not determine this"* (a gap, lowers coverage) vs *"this capability does not exist here"* (excluded from the denominator). Conflating them corrupts the score in both directions |
| **Compliance** vs **coverage** | What proportion of *checked* controls passed vs what proportion of controls could be *checked at all* |
| **Compliance posture** vs **security posture** | Conformance to a document vs actual risk. A device can pass 100% of a benchmark while running firmware with a known critical vulnerability |
| **Meaningful** vs **vacuous** pass | Configured securely vs feature absent. Identical tick, different durability |
| **Configuration** vs **effective configuration** | The text vs what the device actually does after inheritance resolution |
| **Vendor** vs **platform** | Cisco is a vendor; IOS, IOS-XE, NX-OS and IOS-XR are four platforms with different syntax. Rulepacks are per platform |
| **Framework item** vs **native control** | The reporting vocabulary vs the evaluation engine |
| **Absent** vs **false** | A setting not present in a configuration is not necessarily disabled — it may be at a platform default. Treating absence as false silently passes every device that omits the setting |
| **Finding** vs **evidence** | The assertion vs the configuration lines that substantiate it. Without the second, the first is an opinion |
| **Learning** vs **training a model** | Accumulating inspectable, versioned, revertible, attributable data vs adjusting weights. Every audit-integrity property in this product depends on the former |
