"""Webhooks — 15-api-specification.md §11.

Note: §11 documents outbound *event types* NSCA dispatches
(`campaign.state_changed`, `finding.regressed`, etc.) and their payload
shape — it defines no inbound REST endpoints. Per backend-02
§4 module layout ("§11 — dispatch, not receipt"), this module is where
outbound dispatch logic will live in a later milestone (job enqueued
alongside the same-transaction audit-log write, §2.3), not a router
receiving webhook calls.

No routes are registered here at M0; `EVENT_TYPES` and `dispatch()` are a
placeholder for the dispatch service that later milestones fill in, kept in
this module (rather than omitted) so the module inventory in backend-02 §4
is satisfied without inventing an endpoint the spec doesn't define.
"""

from __future__ import annotations

from typing import Any

EVENT_TYPES: tuple[str, ...] = (
    "campaign.state_changed",
    "assessment.completed",
    "finding.state_changed",
    "finding.risk_acceptance_expiring",
    "finding.regressed",
    "training.rule_awaiting_ratification",
    "knowledge.update_available",
    "report.issued",
)


def dispatch(event_type: str, payload: dict[str, Any]) -> None:
    """Placeholder for outbound webhook dispatch (M2+).

    Payloads carry identifiers and state only, never configuration content
    (§11). Not implemented at M0.
    """
    raise NotImplementedError("webhook dispatch is not implemented until a later milestone")
