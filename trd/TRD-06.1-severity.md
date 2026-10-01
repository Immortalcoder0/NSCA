# TRD-06.1 · Exposure and Severity Weighting

---

## 1. Scope

Computation of effective severity from base severity and device context, and the
separation of **compliance posture** from **security posture**.

**Out of scope:** exposure classification itself (TRD-04.1 §3.6); attack path
ranking (TRD-06.2).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-RSK-001 | Base and effective severity |
| FR-RSK-002 | Exposure-modulated severity |
| FR-RSK-009 | Version-based vulnerability correlation |
| FR-RSK-010 | Compliance posture versus security posture |

---

## 3. Design

### 3.1 Why static severity is insufficient

A flat list of 400 findings sorted by a label assigned by a standards body is not
actionable. The administrator reads the first ten and closes it.

Weak SSH configuration on an internet-facing edge firewall and the identical
finding on an isolated lab switch carry the same benchmark severity and
completely different real risk. A report that cannot distinguish them wastes the
one afternoon the administrator has.

### 3.2 Severity model

```
severity ∈ { informational, low, medium, high, critical }    // ordinal
```

```
effective(finding, device) =
    clamp( base + Σ modifier_deltas , informational, critical )
```

Modifiers are declared on the control (PRD 06 §3):

```yaml
risk_modifiers:
  - { if: "device.exposure == internet_facing", severity: critical }
  - { if: "device.exposure == isolated",        severity: medium   }
```

**DD-06.1-01 — Modifiers set an absolute level, not a delta.** Deltas compose
unpredictably when several modifiers fire; absolute assignment is auditable and
explainable. Where multiple modifiers match, the **highest** resulting severity
wins, and all matching modifiers are recorded.

**INV-06.1-01 — Every effective severity records its basis.** A finding whose
severity differs from its base must state why:

```
Severity  HIGH → CRITICAL
          Elevated: this device terminates an external circuit
```

Without the reason, an administrator cannot evaluate whether the escalation is
warranted, and an unexplained escalation reads as arbitrary.

### 3.3 Modifier evaluation under uncertainty

Modifier conditions are expressions (TRD-05.1) and may evaluate to `⊥`.

```
if modifier condition == ⊥  →  modifier does not fire
                               finding records "severity_context_incomplete"
```

**DD-06.1-02 — An unevaluable modifier does not fire, and the finding says so.**
Firing on unknown would inflate severity on speculation; suppressing it silently
would hide that context was missing. The finding is reported at base severity
with a note that context could not be established.

Exception: where exposure itself is ambiguous, TRD-04.1 §3.6 already resolves to
the **more severe** classification. That asymmetry is deliberate and is applied
before severity weighting, so this rule does not undo it.

### 3.4 Materiality

Distinct from severity, and an audit concept rather than a technical one.

| Materiality | Meaning |
|---|---|
| `material` | Affects the audit conclusion; must be reported |
| `informational` | Recorded but does not affect the conclusion |

**DD-06.1-03 — Materiality is a control property, not a computed one.** It
reflects a professional judgement about whether a class of finding bears on the
assessment conclusion, and that judgement belongs to whoever authored the
control, not to a runtime formula.

### 3.5 Compliance posture versus security posture

FR-RSK-010. The uncomfortable truth of the compliance industry:

> A device can pass 100% of a benchmark while running firmware with a known
> unauthenticated remote code execution flaw. Perfect green report, fully
> compromised device.

And the converse: a device fails *"SSH idle timeout must be 5 minutes"* while
sitting on an isolated management network nothing can reach. Technically true
finding, practically noise.

Most tools conflate these because compliance is what they can measure.

```
compliance_posture = PASS / determined                    (TRD-05.2)

security_posture   = compliance_posture
                     − vulnerability_penalty
                     − unaudited_surface_penalty
                     + isolation_credit
```

| Component | Basis |
|---|---|
| `vulnerability_penalty` | Known vulnerabilities affecting the identified firmware (TRD-01.2 §3.6), weighted by severity and exposure |
| `unaudited_surface_penalty` | Capabilities present but assessed by no control (TRD-03.3 §3.8), weighted by their security properties |
| `isolation_credit` | Findings on devices with `exposure == isolated` contribute less to the deficit |

**INV-06.1-02 — Divergence must be explained, never merely displayed.**

```
Compliance posture   94%
Security posture     61%

Divergence explained
  • 2 devices run firmware with published critical vulnerabilities,
    not covered by any selected framework
  • 7 devices expose unaudited management capabilities
  • 12 findings are on isolated devices with negligible exposure
```

**DD-06.1-04 — Security posture is a reported indicator, never a compliance
verdict.** It is a judgement aid, not a conformance statement. It is presented
alongside compliance, never in place of it, and it is never exported as though it
were a framework result.

This distinction matters because an assessor may be contractually required to
report conformance to a specific framework. Security posture informs their
professional opinion; it does not substitute for the mandated figure.

### 3.6 Vulnerability correlation

Version-based lookup runs at fingerprinting (TRD-01.2 §3.6) and produces findings
independent of any control. They therefore:

- **Do not** contribute to compliance posture — no framework asserts them
- **Do** contribute to security posture
- **Do** carry the offline index age in their evidence

```
⚠ RouterOS 6.42 — CVE-2018-14847
  Authentication bypass. Publicly exploited.
  Vulnerability data current as of 2026-08-14 (43 days old).
  Not covered by any selected framework.
```

**INV-06.1-03 — Vulnerability findings state the index age.** Offline data with
an unstated age is a false assurance: the report must say what it could not have
known.

### 3.7 Determinism

Severity computation is a pure function of `⟨finding, device_context, control⟩`.
No clock (D2) — an accepted risk approaching expiry does not change severity;
that is a lifecycle state, not a risk property. No randomness (D3).

---

## 4. Interfaces

```
weight(finding, device_context, control) → WeightedFinding

WeightedFinding {
  severity_base, severity_effective
  modifiers_fired[]: ⟨condition, resulting_severity⟩
  severity_reason: string | ⊥
  severity_context_incomplete: bool
  materiality
}

posture(campaign) → ⟨compliance, security, divergence_components[]⟩
```

---

## 5. Edge cases

| Case | Handling |
|---|---|
| Device exposure `unknown` | No exposure modifier fires; base severity; `severity_context_incomplete` set |
| Several modifiers matching with different severities | Highest wins; all recorded |
| Modifier lowering severity below `informational` | Clamped |
| Vulnerability with no severity in the index | Treated as `high`; index gap recorded |
| Security posture where every finding is on isolated devices | May exceed compliance posture; permitted and explained |
| Campaign with no vulnerability index loaded | Vulnerability penalty zero; **absence stated in the report** |
| Control with no `risk_modifiers` | Effective equals base; no reason emitted |

**The missing-index case is worth stating explicitly.** A security posture
computed with no vulnerability data looks identical to one computed with clean
data. The report must distinguish *"no known vulnerabilities"* from *"we have no
vulnerability data"*.

---

## 6. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Severity escalation with no recorded reason | V-06.1-002 | Appears arbitrary; assessor cannot evaluate it |
| Modifier firing on an unknown condition | V-06.1-003 | Severity inflated on speculation |
| Security posture exported as a compliance figure | V-06.1-006 | Misrepresents conformance — a professional risk for the assessor |
| Vulnerability index age omitted | V-06.1-005 | False assurance about currency |
| Missing index indistinguishable from clean result | V-06.1-007 | Silent gap |
| Non-deterministic severity | V-06.1-008 | G1 violation |

---

## 7. Verification

```
V-06.1-001   Exposure-modulated severity is correct
  Requirement  FR-RSK-002
  Method       INTEGRATION
  Procedure    Identical finding on four devices classified internet_facing,
               dmz, internal and isolated.
  Acceptance   Severities differ per the control's declared modifiers.
               Highest-matching modifier wins where several fire.
  Severity     MAJOR
```

```
V-06.1-002   Every escalation records its basis
  Requirement  INV-06.1-01
  Method       CORPUS
  Procedure    Assess the corpus; inspect every finding where
               effective ≠ base.
  Acceptance   100% carry a non-empty severity_reason naming the modifier
               that fired. Zero unexplained escalations.
  Severity     BLOCKING
```

```
V-06.1-003   Unevaluable modifiers do not fire
  Requirement  DD-06.1-02
  Method       UNIT
  Procedure    Finding whose modifier condition references a fact with
               provenance default_unknown.
  Acceptance   Modifier does not fire. Severity equals base.
               severity_context_incomplete is set and surfaced in the report.
  Severity     BLOCKING
```

```
V-06.1-004   Compliance and security posture are computed separately
  Requirement  FR-RSK-010
  Method       INTEGRATION
  Procedure    Campaign containing devices with known vulnerabilities,
               unaudited surface and isolated non-compliance.
  Acceptance   Both figures reported. Divergence components enumerated and
               summing to the difference.
  Severity     MAJOR
```

```
V-06.1-005   Vulnerability findings state the index age
  Requirement  INV-06.1-03
  Method       CORPUS
  Procedure    Assess devices with known-vulnerable firmware.
  Acceptance   100% of vulnerability findings carry the index date and age
               in days. Age > 90 days raises a warning.
  Severity     MAJOR
```

```
V-06.1-006   Security posture is never exported as a framework result
  Requirement  DD-06.1-04
  Method       INTEGRATION
  Procedure    Export findings as JSON, CSV and OSCAL.
  Acceptance   Security posture appears as a distinct indicator field.
               Zero occurrences within framework conformance structures.
               OSCAL output contains only compliance-derived results.
  Severity     BLOCKING
```

```
V-06.1-007   Absent vulnerability data is distinguished from clean results
  Requirement  §5
  Method       INTEGRATION
  Procedure    Assess a campaign with no vulnerability index loaded.
  Acceptance   Report states that vulnerability data was unavailable.
               Security posture omits the component rather than treating it
               as zero-risk. Zero implications of "no known vulnerabilities".
  Severity     BLOCKING
```

```
V-06.1-008   Severity computation is deterministic and clock-independent
  Requirement  G1, D2, D3
  Method       PROPERTY
  Procedure    Weight all corpus findings 10 times with the system clock
               advanced by one year between runs.
  Acceptance   Identical effective severities, modifiers fired and reasons.
  Severity     BLOCKING
```

```
V-06.1-009   Materiality is authored, not computed
  Requirement  DD-06.1-03
  Method       UNIT
  Procedure    Inspect materiality across the control library and across
               weighted findings.
  Acceptance   Materiality on a finding always equals the control's declared
               value. Zero runtime modification.
  Severity     MINOR
```

---

## 8. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should the security posture formula's weights be configurable per organisation? | Configurability makes the figure meaningful to a given risk appetite but destroys comparability between deployments and complicates reproducibility. Current design: fixed weights, published, with components reported separately so an organisation can re-weight downstream |
| Q2 | Should isolation credit apply at all, given that isolation claims are frequently refuted (TRD-04.2 §3.7)? | Crediting unverified isolation is exactly the error compensating-control verification exists to catch. Current design: credit applies only where exposure is graph-derived as `isolated`, never from an asserted claim |
| Q3 | Should vulnerability severity use the published score, or be re-weighted by exposure like control findings? | Exposure re-weighting is more useful operationally; published scores are more defensible. Current design: published severity as the base, exposure applied as a modifier, both shown |
