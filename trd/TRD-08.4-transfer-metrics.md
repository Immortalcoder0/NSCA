# TRD-08.4 · Cross-Platform Transfer and Learning Metrics

---

## 1. Scope

The mechanism by which teaching platform *N* is cheaper than teaching platform
*N−1*, and the measurement that proves it.

> The declining confirmation curve is the **measurable answer** to the problem
> statement's demand for *"Scalability & Adaptation"*. It is the product's
> central claim, and it cannot be fabricated because the platform records every
> confirmation as it happens.

---

## 2. Requirements satisfied

| PRD | How |
|---|---|
| FR-LRN-020 | Cross-platform transfer |
| FR-LRN-021 | Confirmation counts recorded, enabling the effort curve |
| FR-LRN-022, 023 | Rulepack export, import, verification, trust tiers |
| NFR-OBS-005 | Learning effort metrics |
| NFR-USE-003 | ≤ 15 minute onboarding target |

---

## 3. Transfer

### 3.1 What actually transfers

Not model weights. Three accumulating stores of inspectable data:

| Store | Contents | Grows with |
|---|---|---|
| **Synonym index** | fact path → observed token forms across platforms | Every confirmed mapping |
| **Structural index** | fact path → enclosing-path shapes it has been extracted from | Every confirmed mapping |
| **Polarity index** | negation indicator → observed inversion behaviour | Every polarity confirmation |

```
synonym_index["mgmt.protocols.telnet.enabled"] =
  { cisco_ios:   ["transport input telnet"],
    fortios:     ["admin-telnet"],
    juniper:     ["system services telnet"],
    panos:       ["disable-telnet"],
    mikrotik:    ["telnet"] }
```

**DD-08.4-01 — Transfer is retrieval, not inference.** Proposal quality improves
because the indices contain more observed forms to match against, not because a
model has been adapted. This keeps every audit-integrity property intact: the
indices are inspectable, versioned, attributable and revertible.

### 3.2 Why transfer works in this domain

> Networking vocabulary is standardised even where syntax is not. Every vendor
> writes `telnet`, `ssh`, `snmp`, `ntp`, `radius` — they have no choice, because
> these are interoperability protocols defined in published RFCs. Vendors
> differentiate on syntax, never on protocol names.

**The vocabulary shared across all these dialects is precisely the
security-relevant vocabulary.** This is the structural property that makes the
learning curve possible, and it is why the effect is real rather than an artefact
of measurement.

### 3.3 Transfer in proposal generation

```
lexical_score(token, fact) =
      base score (TRD-08.2 §3.1)
    + transfer_bonus(token, synonym_index[fact])

transfer_bonus = f( number of distinct platforms on which a similar
                    token produced this fact )
```

Diminishing returns: the fifth platform confirming that `telnet` means telnet
adds little. The curve therefore flattens rather than declining indefinitely,
which is itself a check on the measurement's honesty (§5.3).

### 3.4 Polarity transfer

The polarity index is safety-critical. Having observed that `disabled=` inverts
on RouterOS, `disable` inverts on FortiOS, and `no ` inverts on Cisco, the
detector's indicator list is empirically grounded rather than hand-maintained.

**INV-08.4-01 — Transfer never suppresses polarity confirmation.** Regardless of
how confident the index is, a negation-bearing template still requires explicit
confirmation (TRD-08.2 INV-08.2-01). Transfer improves the *proposal*; it never
removes the *checkpoint*.

---

## 4. Rulepack portability

### 4.1 Export

FR-LRN-022. Signed bundle:

```
mikrotik_routeros-1.0.0.rpk
├── manifest.yaml        platform, version, checksums, schema additions
├── signature.sig
├── fingerprint.yaml
├── grammar.yaml
├── extractors/          one file per extractor, with frozen tests
├── defaults.yaml
├── inheritance.yaml
├── quirks.yaml
└── provenance.yaml      authorship, ratification, corpus statistics
```

One organisation teaches a platform once; others import the result. **Platform
knowledge compounds across deployments rather than being relearned everywhere.**

This is only possible because knowledge is data. Model weights cannot be exported
as a fraction, cannot be inspected before import, and cannot carry provenance.

### 4.2 Import

FR-LRN-023. An imported rulepack is **never trusted on its signature alone**.

```
import(bundle) →
  1  verify signature and checksums
  2  reconcile schema additions against the local registry
  3  run all frozen tests
  4  run Gate 2 (corpus scope) against the LOCAL corpus
  5  detect conflicts with local rulepacks
  6  assign trust tier = verified_community
  7  require ratification before use in issued reports
```

**DD-08.4-02 — Step 4 is mandatory on import.** A rule validated against the
author's corpus may be over-broad against a different estate containing platforms
the author never had. Local validation is the only way to know.

**Schema reconciliation** (step 2) is the subtle part: an imported rulepack may
emit fact paths the local registry lacks. Those registrations are imported as
provisional and must be ratified alongside the rulepack, or the rulepack is
rejected.

### 4.3 Trust tiers

| Tier | Validation behind it | Issued reports |
|---|---|---|
| `certified` | Vendor-team authored, large corpus, full regression, cross-checked against a reference implementation | Yes |
| `verified_community` | Signature verified, tests pass locally, local corpus validated — but not independently corpus-validated at scale | Yes, tier stated |
| `local` | Taught here, two-person ratified | Yes, tier stated |
| `provisional` | Taught, not ratified | **No** |

Every report states the tier of every rulepack used (PRD 11 §8).

---

## 5. Metrics

### 5.1 What is recorded

NFR-OBS-005. Recorded per platform, per teaching session, from the first platform
onward — because the curve cannot be reconstructed retrospectively.

| Metric | Definition |
|---|---|
| `confirmations_to_70pct` | Confirmations required to reach 70% control coverage |
| `wall_clock_minutes` | Elapsed administrator time |
| `proposal_acceptance_rate` | Proposals confirmed unchanged / proposals presented |
| `edit_rate` | Proposals requiring mapping correction |
| `polarity_correction_rate` | Polarity proposals corrected / polarity proposals made |
| `not_relevant_rate` | Templates marked irrelevant / templates presented |
| `questions_to_first_finding` | Confirmations before the first real finding appears |
| `teaching_order` | Position of this platform in the sequence taught |

### 5.2 The curve

```
Confirmations required to reach 70% coverage

  1  Cisco IOS        ████████████████████████  47
  2  Juniper JunOS    ███████████████           31
  3  FortiOS          ███████████               22
  4  PAN-OS           ███████                   14
  5  Arista EOS       █████                     11
  6  MikroTik         ████                       8
  7  SONiC            ███                        6
```

**INV-08.4-02 — Teaching order is recorded and the curve is plotted in that
order.** Plotting by platform name, alphabetically, or by any other ordering
would destroy the claim being made. The x-axis is *order taught*, not platform
identity.

### 5.3 Honest measurement

The curve is a claim about the system, so the measurement must resist flattering
itself.

| Confound | Control |
|---|---|
| Later platforms happen to be simpler | Report per-platform construct count and grammar complexity alongside |
| Administrator gets better with practice | Record which administrator taught each platform; report separately where they differ |
| Coverage target gamed by choosing easy facts | Fixed 70% control-coverage target, not fact count |
| Diminishing returns mistaken for a defect | Expected and stated — §3.3 predicts flattening |
| Corpus for later platforms is larger | Report corpus size per platform |

**DD-08.4-03 — Confounds are reported alongside the curve, not adjusted away.**
An adjusted curve is a modelling claim; a raw curve with its confounds stated is
evidence. The second is more defensible and more honest.

### 5.4 Polarity correction rate as a safety signal

**INV-08.4-03 — A rising polarity correction rate is a release-blocking
signal.**

The rate measures how often the polarity detector proposes the wrong inversion.
Rising means the negation-indicator heuristics are degrading against newer
platforms — and polarity errors produce systematic false PASS verdicts across an
entire platform.

| Rate | Interpretation |
|---|---|
| < 5% | Healthy |
| 5–15% | Investigate the indicator list |
| > 15% | **Release-blocking.** The detector is unreliable |

This is the one metric that is a safety instrument rather than a performance
indicator.

### 5.5 Time-estimate calibration

Observed answer times calibrate the estimate shown in the Training Studio
("9 questions · est. 8 minutes"). Calibration is per deployment; a stated
estimate that is consistently wrong erodes trust in everything else the interface
says.

---

## 6. Interfaces

```
transfer_context(fact, target_platform) → ⟨synonyms[], structures[], polarity_priors[]⟩
export(rulepack) → SignedBundle
import(bundle) → ImportResult { tier, tests_passed, corpus_validation,
                                schema_additions[], conflicts[] }
metrics(platform?) → LearningMetrics
curve() → [ ⟨order, platform, confirmations, minutes, acceptance_rate,
             construct_count, corpus_size, administrator⟩ ]
```

---

## 7. Edge cases

| Case | Handling |
|---|---|
| First platform ever taught | No transfer available; proposals are heuristic-only; recorded as the baseline |
| Platform sharing a family with a taught one (IOS after IOS-XE) | High transfer; recorded and flagged so the curve is not over-read |
| Imported rulepack for an already-taught platform | Conflict detection; administrator chooses; both retained versioned |
| Imported bundle whose schema additions conflict with local registrations | Rejected; reconciliation required before import |
| Platform taught, then its rulepack reverted | Metrics retain the original session; revert recorded separately |
| Teaching abandoned before 70% coverage | Session recorded as incomplete; excluded from the curve, counted separately |
| Two administrators teaching the same platform | Both sessions recorded; the curve uses the completing session, with the collaboration noted |

**The same-family case matters for honesty.** Teaching IOS-XE immediately after
IOS will show a dramatic drop that owes more to family similarity than to
transfer. The metric records the relationship so the curve is not over-claimed.

---

## 8. Failure modes

| Failure | Detection | Degradation |
|---|---|---|
| Curve plotted by platform rather than teaching order | V-08.4-004 | The claim being made becomes meaningless |
| Confounds hidden by adjustment | V-08.4-005 | Curve becomes a modelling claim, not evidence |
| Polarity correction rate not tracked | V-08.4-006 | The one safety metric is invisible |
| Imported rulepack not locally validated | V-08.4-002 | Over-broad rules corrupt local facts |
| Transfer suppressing polarity confirmation | V-08.4-003 | The highest-consequence checkpoint bypassed |
| Metrics reconstructed retrospectively | Session records | Curve unverifiable; must be recorded live |

---

## 9. Verification

```
V-08.4-001   Transfer measurably improves proposal quality
  Requirement  FR-LRN-020
  Method       CORPUS
  Procedure    Teach five held-out platforms in sequence. For each, record
               proposal_acceptance_rate. Repeat with the transfer indices
               cleared between platforms.
  Acceptance   Acceptance rate is higher with transfer enabled for platforms
               3 onward, by a margin exceeding measurement noise.
  Severity     MAJOR
  Note         This isolates transfer from platform difficulty.
```

```
V-08.4-002   Imported rulepacks are validated against the local corpus
  Requirement  FR-LRN-023, DD-08.4-02
  Method       INTEGRATION
  Procedure    Import a bundle containing a rule that is correct on the
               author's corpus but over-broad against the local one.
  Acceptance   Gate 2 fails on import. Rulepack rejected or the offending
               rule quarantined. Zero acceptance on signature alone.
  Severity     BLOCKING
```

```
V-08.4-003   Transfer never suppresses polarity confirmation
  Requirement  INV-08.4-01
  Method       UNIT
  Procedure    Teach a sixth platform where the polarity index strongly
               predicts the inversion.
  Acceptance   Explicit polarity confirmation still required. Zero
               auto-confirmations regardless of index confidence.
  Severity     BLOCKING
```

```
V-08.4-004   The curve is plotted by teaching order
  Requirement  INV-08.4-02, FR-LRN-021
  Method       INTEGRATION
  Procedure    Teach five platforms; retrieve the curve.
  Acceptance   x-axis is teaching order. Each point carries platform,
               confirmations, minutes, acceptance rate, construct count,
               corpus size and administrator.
  Severity     BLOCKING
```

```
V-08.4-005   Confounds are reported, not adjusted away
  Requirement  DD-08.4-03
  Method       INTEGRATION
  Procedure    Retrieve the curve after teaching platforms of differing
               complexity by different administrators.
  Acceptance   Construct count, corpus size and administrator reported per
               point. Same-family relationships flagged. Zero adjusted or
               normalised figures presented as raw.
  Severity     MAJOR
```

```
V-08.4-006   Polarity correction rate is tracked and gates release
  Requirement  INV-08.4-03
  Method       INTEGRATION
  Procedure    Teach platforms with deliberately seeded polarity mis-
               proposals to drive the rate above 15%.
  Acceptance   Rate computed and surfaced. Above 15% raises a
               release-blocking signal, not merely a dashboard value.
  Severity     BLOCKING
```

```
V-08.4-007   Onboarding target is met on a held-out platform
  Requirement  NFR-USE-003
  Method       MANUAL
  Procedure    A network administrator unfamiliar with the tool teaches the
               untaught holdout platform, unaided, timed.
  Acceptance   ≥ 70% coverage in ≤ 15 minutes of administrator time.
               Zero expression syntax encountered.
  Severity     BLOCKING
  Note         Requires a genuinely fresh holdout (TRD-00 §8.1). Teaching it
               during earlier testing invalidates the gate.
```

```
V-08.4-008   Export and import round-trip preserves behaviour
  Requirement  FR-LRN-022, FR-LRN-023
  Method       INTEGRATION
  Procedure    Export a ratified rulepack; import into a clean deployment;
               assess the same artifacts.
  Acceptance   Byte-identical facts and findings. Tier recorded as
               verified_community. Schema additions reconciled.
  Severity     BLOCKING
```

```
V-08.4-009   Tampered bundles are rejected
  Requirement  FR-LRN-023, NFR-SEC-008
  Method       UNIT
  Procedure    Modify an extractor, a test, and a checksum in a signed bundle.
  Acceptance   All three rejected at import with the specific failure named.
  Severity     BLOCKING
```

```
V-08.4-010   Metrics are recorded live, not reconstructed
  Requirement  NFR-OBS-005
  Method       INTEGRATION
  Procedure    Complete a teaching session; inspect the stored session record.
  Acceptance   Every confirmation carries its own timestamp, question rank,
               proposal source and outcome. The curve is derivable from
               records alone, with no recomputation from current state.
  Severity     MAJOR
```

```
V-08.4-011   Incomplete sessions are excluded from the curve
  Requirement  §7
  Method       UNIT
  Procedure    Abandon a teaching session at 40% coverage.
  Acceptance   Session recorded as incomplete. Excluded from the curve.
               Counted separately in abandonment statistics.
  Severity     MINOR
```

---

## 10. Open questions

| # | Question | Trade-off |
|---|---|---|
| Q1 | Should transfer indices be shareable between deployments alongside rulepacks? | Sharing would accelerate onboarding everywhere and strengthen the polarity index against rare vendors, but observation-sharing raises data-governance questions and is impossible air-gapped. Current design: local indices; imported rulepacks contribute their observed forms |
| Q2 | Should the 70% coverage target be platform-specific? | Some platforms cannot reach 70% because their rulepack cannot produce enough facts, making the target unreachable through no fault of the learner. Current design: fixed 70% with per-platform producible-fact ceiling reported alongside |
| Q3 | Should the polarity indicator list be shipped as updatable content? | Content updates keep it current as new vendors appear, but a safety-critical list delivered as content could be weakened by an import. Current design: shipped with the engine, extended locally with attribution, never overwritten by an import |
