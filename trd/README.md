# NSCA — Technical Requirements Documents

**Verified TRD set.** Each document specifies *how* a subsystem is built, and
carries explicit **verification criteria** stating how conformance is proven.

Companion to the PRD in [`../docs/`](../docs/README.md), which specifies *what*
is built and *why*.

---

## Relationship to the PRD

```
  PRD (docs/)                       TRD (trd/)
  ───────────                       ──────────
  What and why                      How, and how it is proven
  FR-* / NFR-*  requirements   ──►  design + V-* verification criteria
  User-facing behaviour             Algorithms, formats, interfaces
  Stable                            Revised as implementation learns
```

**Every FR and NFR in the PRD is traced to at least one TRD and at least one
verification criterion.** Coverage is asserted in
[TRD-11.3](TRD-11.3-acceptance-criteria.md).

---

## Document index

### Foundations
| ID | Document |
|---|---|
| 00 | [Conventions and Verification Framework](TRD-00-conventions-and-verification.md) |

### Ingestion
| ID | Document |
|---|---|
| 01.1 | [Artifact Intake, Correlation and Custody](TRD-01.1-artifact-intake.md) |
| 01.2 | [Platform Fingerprinting](TRD-01.2-fingerprinting.md) |
| 01.3 | [Read-Only Collection](TRD-01.3-collection.md) |

### Parsing
| ID | Document |
|---|---|
| 02.1 | [Grammar Engine and Parse Tree](TRD-02.1-grammar-engine.md) |
| 02.2 | [Grammar Inference](TRD-02.2-grammar-inference.md) |
| 02.3 | [Effective Configuration Resolution](TRD-02.3-effective-config.md) |

### Extraction
| ID | Document |
|---|---|
| 03.1 | [Extractor Runtime](TRD-03.1-extractor-runtime.md) |
| 03.2 | [Provenance and Defaults Resolution](TRD-03.2-provenance-defaults.md) |
| 03.3 | [Schema Registry](TRD-03.3-schema-registry.md) |

### Graph
| ID | Document |
|---|---|
| 04.1 | [Graph Construction and Exposure](TRD-04.1-graph-construction.md) |
| 04.2 | [Reachability and Counterexamples](TRD-04.2-reachability.md) |

### Control engine
| ID | Document |
|---|---|
| 05.1 | [Assertion Expression Language](TRD-05.1-expression-language.md) |
| 05.2 | [Evaluation, Verdicts and Coverage](TRD-05.2-evaluation.md) |
| 05.3 | [Framework Import and Mapping](TRD-05.3-framework-mapping.md) |

### Risk
| ID | Document |
|---|---|
| 06.1 | [Exposure and Severity Weighting](TRD-06.1-severity.md) |
| 06.2 | [Attack Path Computation](TRD-06.2-attack-paths.md) |
| 06.3 | [Peer Anomaly and Systemic Findings](TRD-06.3-anomaly-systemic.md) |

### Remediation
| ID | Document |
|---|---|
| 07.1 | [Remediation Planner, Safety and Dry Run](TRD-07.1-remediation-planner.md) |

### Learning
| ID | Document |
|---|---|
| 08.1 | [Template Mining and Question Selection](TRD-08.1-template-mining.md) |
| 08.2 | [Candidate Proposal and Polarity](TRD-08.2-candidate-proposal.md) |
| 08.3 | [Rule Synthesis and Validation Gates](TRD-08.3-rule-synthesis.md) |
| 08.4 | [Cross-Platform Transfer and Metrics](TRD-08.4-transfer-metrics.md) |

### Reporting and integrity
| ID | Document |
|---|---|
| 09.1 | [Report Generation Pipeline](TRD-09.1-report-pipeline.md) |
| 10.1 | [Determinism Enforcement](TRD-10.1-determinism.md) |
| 10.2 | [Custody and Hash-Chained Audit Log](TRD-10.2-custody-audit-log.md) |

### Verification
| ID | Document |
|---|---|
| 11.1 | [Test Strategy](TRD-11.1-test-strategy.md) |
| 11.2 | [Metamorphic Testing](TRD-11.2-metamorphic-testing.md) |
| 11.3 | [Acceptance Criteria and Coverage Assertion](TRD-11.3-acceptance-criteria.md) |

---

## The five verification criteria that matter most

If everything else were dropped, these five prove the product's central claims:

| ID | Claim proven | TRD |
|---|---|---|
| **V-10.1-001** | Byte-identical output for identical inputs | [10.1](TRD-10.1-determinism.md) |
| **V-05.2-004** | A missing fact yields UNKNOWN, never PASS | [05.2](TRD-05.2-evaluation.md) |
| **V-08.3-002** | A rule inverting polarity cannot be saved without explicit confirmation | [08.3](TRD-08.3-rule-synthesis.md) |
| **V-11.2-001** | Semantics-preserving mutation produces identical facts | [11.2](TRD-11.2-metamorphic-testing.md) |
| **V-11.3-009** | A new platform reaches ≥70% coverage with no code change or redeployment | [11.3](TRD-11.3-acceptance-criteria.md) |

---

## Reading order

**Implementing the pipeline:** `00 → 01.1 → 01.2 → 02.1 → 02.3 → 03.1 → 03.2 → 05.1 → 05.2`

**Implementing the learning system:** `00 → 02.2 → 08.1 → 08.2 → 08.3 → 08.4`

**Implementing analysis:** `04.1 → 04.2 → 06.1 → 06.2 → 06.3 → 07.1`

**Establishing quality gates:** `11.1 → 11.2 → 10.1 → 11.3`
