# TRD-07.1 · Remediation Planner, Safety and Dry Run

---

## 1. Scope

Production of remediation as a **safety-checked, dependency-ordered playbook**
rather than a command list: version-specific selection, ordering, impact
classification, lockout detection, rollback, and dry-run re-evaluation.

**Out of scope:** applying remediation — the platform is architecturally
incapable of it (G4, TRD-01.3).

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-REM-001…003 | Device-specific, version-keyed selection, refusal where absent |
| FR-REM-004 | Dependency ordering |
| FR-REM-005 | Impact classification |
| FR-REM-006 | Lockout detection |
| FR-REM-007 | Rollback per step |
| FR-REM-008, 009 | Dry run and newly-failing detection |
| FR-REM-010 | Never applied |
| FR-RPT-006 | Customised to model and software version |

---

## 3. Design

### 3.1 The governing principle

> **Remediation must be safe before it is correct.**

Every competing tool emits fix commands. None checks whether running them severs
the administrator's own session or breaks something else. The single most common
real-world disaster in network hardening is tightening a management access list
and instantly losing access to a device in another city.

An administrator who is locked out once by a tool's advice will never use it
again — and will tell colleagues. This subsystem exists to make that impossible.

### 3.2 Version-specific selection

FR-REM-002. Selection is keyed on `⟨control, platform, os_version_range⟩`.

```yaml
remediation:
  cisco_ios:
    version_range: ">=15.0 <16.0"
    steps: [...]
  cisco_iosxe:
    version_range: ">=16.0"
    steps: [...]                        # includes `ip http secure-server`
```

**INV-07.1-01 — No matching version range means refusal, not approximation.**

```
NSCA-MGMT-002 · Remediation unavailable
  No remediation content exists for cisco_nxos 9.3.
  → The finding stands. Remediation must be determined manually.
```

Emitting a Cisco IOS command sequence on an NX-OS device produces commands that
fail, or worse, commands that succeed and do something different. Refusal is the
only honest option, and it mirrors DD-05.3-03 for framework content.

Where version precision is insufficient to select unambiguously (TRD-01.2
INV-01.2-01), remediation is likewise withheld.

### 3.3 Impact classification

Every step carries one of three classes:

| Class | Meaning |
|---|---|
| `safe` | No traffic or session impact |
| `service_affecting` | May interrupt traffic or a dependent service |
| `lockout_risk` | **May sever administrative access, including the operator's own** |

**DD-07.1-01 — Classification is authored on the control, not inferred.** A
command's impact depends on operational context an algorithm cannot see. The
control author declares it, and the declaration is reviewed at ratification.

Any step touching management transports, management ACLs, AAA configuration, SSH
keys or local accounts is `lockout_risk` by default; downgrading it requires an
explicit justification recorded in the control.

### 3.4 Dependency ordering

FR-REM-004. Steps are ordered so that prerequisites are satisfied first.

```yaml
steps:
  - id: 1
    cmd: "aaa authentication login default group tacacs+ local"
    impact: safe
  - id: 4
    cmd: "no username admin password 7 0822455D0A16"
    impact: service_affecting
    depends_on: [1]
    requires_verified: true
```

**INV-07.1-02 — `requires_verified` steps are gated on confirmation, not merely
ordered after.** Configuring central authentication *before* removing the local
account is necessary but not sufficient — the central server must be *reachable
and working*. The playbook therefore inserts a verification checkpoint:

```
STEP 1  aaa authentication login default group tacacs+ local     SAFE

  ⏸ VERIFY BEFORE CONTINUING
     Confirm you can authenticate via TACACS+ in a second session.
     Step 4 removes the only local account. If TACACS+ is unreachable
     after Step 4, the device becomes unreachable.

STEP 4  no username admin password 7 …                SERVICE-AFFECTING
```

Ordering is a topological sort over `depends_on`. Cycles are a control-authoring
defect and are rejected at load.

**Cross-finding dependencies** are supported: remediation for one finding may
depend on another finding's remediation. The planner merges playbooks across
findings on the same device and orders them globally.

### 3.5 Lockout detection

FR-REM-006. The distinguishing capability.

```
lockout_check(plan, device, operator_source) →
  simulated = apply(plan, device.facts)          # model only, never the device

  for each management path P in simulated:
      if P.source_restriction.configured:
          if operator_source ∉ P.allowed_sources:
              → LOCKOUT: operator would be denied

  if no management path remains enabled:
      → LOCKOUT: all management access removed

  if central auth configured with no local fallback
     and central server unreachable per the graph:
      → LOCKOUT: authentication would fail
```

Three distinct lockout modes, all real:

1. **Source denied** — the tightened ACL excludes the operator's address
2. **All transports disabled** — every management protocol turned off, none
   enabled to replace them
3. **Authentication orphaned** — local fallback removed while the central server
   is unreachable

```
LOCKOUT ANALYSIS

  Operator source            10.20.5.44
  Proposed management ACL    10.0.0.0/8, 10.20.0.0/16
  Result                     ✅ PERMITTED — access retained

  ⚠ If applying from a different source, verify inclusion first.
```

Or:

```
  Operator source            192.168.44.10
  Proposed management ACL    10.0.0.0/8
  Result                     ❌ LOCKOUT — your source would be denied

  ⛔ Step 3 blocked. Add 192.168.44.10/32 to the permitted sources,
     or apply from within 10.0.0.0/8.
```

**INV-07.1-03 — A detected lockout blocks the step in the playbook.** It is not a
warning buried in text. The step is marked blocked and the playbook states it
cannot be executed as written.

**DD-07.1-02 — Operator source is required input, and its absence is stated.**
Where the operator's source address is unknown, lockout analysis reports
`INDETERMINATE` rather than `PERMITTED`. Silence must not read as safety.

### 3.6 Dry run

FR-REM-008, 009. Apply the plan **to the model**, re-evaluate, report the delta.

```
dry_run(plan, device) →
  facts'   = apply_to_facts(plan, device.facts)
  verdicts'= evaluate(facts', control_pack)          # full re-evaluation
  return ⟨ before, after, resolved[], newly_failing[] ⟩
```

```
DRY RUN — modelled outcome, not applied

  Compliance   78% → 94%
  Coverage     92% → 92%   (unchanged)

  Resolved     14 findings
  ⚠ NEWLY FAILING (1)
     NSCA-AUTH-009 · Local fallback account must exist
     Step 4 removes the only local account. If TACACS+ becomes
     unreachable, the device will be unreachable.
     → Create a local emergency account before Step 4.
```

**INV-07.1-04 — Newly-failing detection is mandatory output, never optional.**
Fixing control A while breaking control B is common and is precisely what an
administrator needs to know before a maintenance window.

**DD-07.1-03 — Dry run mutates facts, not text.** The plan is translated into
fact-level effects declared on the control, and evaluation runs over the modified
fact set. Simulating by editing configuration text and re-parsing would be more
faithful but would require the planner to generate syntactically perfect
configuration — a much larger and more fragile problem.

Consequence, stated honestly: **the dry run models the intended effect of the
commands, not the device's actual response to them.** A command that fails to
apply on the real device will not be predicted. The report says so.

Coverage must not change during a dry run. If it does, the fact-effect
declaration is wrong — a control-authoring defect surfaced by V-07.1-007.

### 3.7 Rollback

Every step declares a rollback sequence restoring the prior state.

**INV-07.1-05 — Rollback is generated from the observed prior state, not from
the control's generic template.** Restoring `transport input telnet ssh` is only
correct if that was the value before. The planner substitutes the device's actual
prior configuration into the rollback.

Where the prior state is unknown (fact provenance `default_unknown`), rollback is
marked incomplete and says so.

### 3.8 Patch bundle export

FR-REM-011, optional. Signed, ordered commands for the network team's own change
process.

```
remediation-CORE-SW-01-2026Q3.bundle
├── manifest.yaml       device, campaign, findings addressed, hashes
├── signature.sig
├── steps.txt           ordered, annotated with impact
├── rollback.txt        reverse sequence
├── prerequisites.md    verification checkpoints
└── verification.md     how to confirm the fix
```

**INV-07.1-06 — The bundle is a document.** No code path exists from a bundle to
a device (G4). It is signed so that the network team can verify it was produced
by the audit platform and not altered in transit.

---

## 4. Interfaces

```
plan(findings[], device, operator_source?) → RemediationPlan {
  steps[]: { id, command, impact, reason, depends_on[], requires_verified,
             rollback, addresses_findings[] }
  lockout_analysis: ⟨result, operator_source, blocked_steps[]⟩
  dry_run: ⟨before, after, resolved[], newly_failing[]⟩
  unavailable[]: ⟨finding, reason⟩
  checkpoints[]: ⟨after_step, instruction⟩
}
```

---

## 5. Edge cases

| Case | Handling |
|---|---|
| Two findings whose remediations conflict | Conflict reported; neither auto-resolved; assessor decides |
| Remediation whose prerequisite is itself unavailable | Whole chain marked unavailable with the root reason |
| Device with no management path currently enabled | Lockout analysis reports the device is already unreachable by the modelled paths |
| Operator source inside a range being removed | Lockout detected — the common real case |
| Dry run where a step's fact effects are undeclared | Step excluded from the dry run; noted as unmodelled |
| Finding with verdict UNKNOWN | No remediation — you cannot fix what you could not determine |
| Rollback for a step whose prior state is `default_unknown` | Rollback marked incomplete, stated |
| Cross-device remediation (a fix on device B resolves a finding on A) | Supported; steps grouped per device and the dependency stated |

**The UNKNOWN case is worth stating.** Offering remediation for an undetermined
control would imply a defect that was never established — and would encourage
changing a working configuration on speculation.

---

## 6. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Lockout not detected | V-07.1-003 | **Administrator locked out of production.** The failure this subsystem exists to prevent |
| Wrong version's commands emitted | V-07.1-001 | Commands fail, or succeed with different meaning |
| Newly-failing control missed | V-07.1-006 | Administrator fixes A, breaks B, discovers it after the window |
| Rollback from a generic template | V-07.1-008 | Rollback restores the wrong state |
| Dry run changes coverage | V-07.1-007 | Fact-effect declaration is wrong |
| Bundle treated as executable | V-07.1-009 | G4 compromise |

---

## 7. Verification

```
V-07.1-001   Remediation is version-specific, and absent content is refused
  Requirement  FR-REM-002, FR-REM-003, INV-07.1-01
  Method       UNIT + CORPUS
  Procedure    Generate plans for the same control on IOS 15.2, IOS-XE 17.3
               and NX-OS 9.3 (no content authored).
  Acceptance   Different, correct command sequences for the first two.
               Explicit refusal for the third. Zero approximated sequences.
  Severity     BLOCKING
```

```
V-07.1-002   Dependency ordering is topologically correct
  Requirement  FR-REM-004
  Method       PROPERTY
  Procedure    Plans with declared dependencies, including cross-finding
               chains, in shuffled input order.
  Acceptance   Every step follows all its dependencies in all orderings.
               Cycles rejected at control-pack load.
  Severity     BLOCKING
```

```
V-07.1-003   Lockout detection catches all three modes
  Requirement  FR-REM-006, INV-07.1-03
  Method       INTEGRATION
  Procedure    (a) ACL excluding the operator source.
               (b) Plan disabling every management transport.
               (c) Local fallback removed with an unreachable AAA server.
  Acceptance   All three detected. Offending steps marked blocked.
               Playbook states it cannot be executed as written.
               Zero cases reported as PERMITTED.
  Severity     BLOCKING
  Note         This is the capability that earns an administrator's trust.
```

```
V-07.1-004   Unknown operator source yields INDETERMINATE, not PERMITTED
  Requirement  DD-07.1-02
  Method       UNIT
  Procedure    Generate a plan with a management-ACL step and no operator
               source supplied.
  Acceptance   Lockout analysis reports INDETERMINATE with the reason.
               Zero PERMITTED results. Report states the check was not
               performed.
  Severity     BLOCKING
```

```
V-07.1-005   Verification checkpoints precede irreversible steps
  Requirement  INV-07.1-02
  Method       UNIT
  Procedure    Plan configuring central authentication then removing the
               local account.
  Acceptance   A checkpoint appears between them instructing the operator to
               verify central authentication in a second session, and stating
               the consequence of proceeding without it.
  Severity     BLOCKING
```

```
V-07.1-006   Dry run detects newly-failing controls
  Requirement  FR-REM-009, INV-07.1-04
  Method       INTEGRATION
  Procedure    Plan whose steps resolve one control and break another.
  Acceptance   newly_failing names the broken control with an explanation
               and a mitigating instruction. Zero silent breakages.
  Severity     BLOCKING
```

```
V-07.1-007   Dry run does not change coverage
  Requirement  §3.6
  Method       PROPERTY + CORPUS
  Procedure    Dry-run every generated plan across the corpus.
  Acceptance   Coverage identical before and after in 100% of cases.
               Any change indicates a defective fact-effect declaration and
               fails the run.
  Severity     BLOCKING
```

```
V-07.1-008   Rollback restores observed prior state
  Requirement  INV-07.1-05
  Method       UNIT + CORPUS
  Procedure    Generate rollbacks for steps whose prior values differ from
               the control's generic template.
  Acceptance   Rollback contains the device's actual prior value.
               Where prior state is default_unknown, rollback is marked
               incomplete. Zero generic-template rollbacks presented as
               complete.
  Severity     MAJOR
```

```
V-07.1-009   No code path applies remediation
  Requirement  FR-REM-010, INV-07.1-06, G4
  Method       UNIT + static analysis
  Procedure    Enumerate all consumers of RemediationPlan and of the patch
               bundle.
  Acceptance   All consumers are document generators. Zero paths reach the
               collection transport. CI blocks introduction of one.
  Severity     BLOCKING
```

```
V-07.1-010   No remediation is offered for UNKNOWN findings
  Requirement  §5
  Method       CORPUS
  Procedure    Generate plans across the corpus.
  Acceptance   Zero remediation steps attached to UNKNOWN verdicts.
  Severity     MAJOR
```

```
V-07.1-011   Planning is deterministic
  Requirement  G1, D6
  Method       PROPERTY
  Procedure    Generate plans for all corpus findings 10 times with shuffled
               finding ordering.
  Acceptance   Identical step sequences, identical ordering, identical
               lockout results and dry-run outcomes.
  Severity     BLOCKING
```

```
V-07.1-012   Dry-run limitation is stated in output
  Requirement  DD-07.1-03
  Method       MANUAL
  Procedure    Inspect generated playbooks and reports.
  Acceptance   Output states that the dry run models the intended effect of
               the commands, not the device's actual response, and that
               command application is not verified.
  Severity     MAJOR
```

---

## 8. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should lockout analysis consider out-of-band console access as a mitigating factor? | Console access genuinely reduces lockout severity, but its presence cannot be established from configuration and assuming it would weaken the check. Current design: not considered; console availability is noted as an operator responsibility |
| Q2 | Should the planner generate configuration text and re-parse for a higher-fidelity dry run? | More faithful, but requires generating syntactically perfect configuration for every platform — a large, fragile problem that would gate the feature on parser-quality-in-reverse. Current design: fact-level effects, with the limitation stated |
| Q3 | Should cross-device remediation plans be merged into one estate-level playbook? | Convenient for large systemic remediations, but obscures per-device change control, which most organisations require. Current design: per device, with cross-device dependencies stated |
