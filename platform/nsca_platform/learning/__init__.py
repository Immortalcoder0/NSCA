"""The Learning Subsystem — 08-learning-system.md, backend-02 §4.3, M3.

Pipeline order (08-learning-system.md §2), each module below implementing
one stage:

    grammar_inference   -> template_mining -> candidate_proposal -> polarity
    -> rule_synthesis (+ validation_gates) -> ratification -> transfer_metrics

Nothing in this package imports anything from `nsca_engine` except
`nsca_engine.types.UnmatchedConstruct` (the shape unmatched constructs
arrive in) and, for the rule-synthesis <-> real-loader integration test
only, `nsca_engine.controls.rulepack_loader` — per backend-02 §2.2, the one
place Track B is told to reach past `nsca_engine.api` directly.
"""

from __future__ import annotations
