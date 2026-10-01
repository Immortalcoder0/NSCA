"""FastAPI application entrypoint — Phase 0 (M0) scaffold.

Every router under `nsca_platform.api` is mounted under `/api/v1`, matching
the base path declared in 15-api-specification.md §1. The OpenAPI schema is
served at `/api/v1/openapi.json` (00-master-plan.md §4 Phase 0 / §5.2).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from nsca_platform.api import (
    admin,
    assessment,
    campaigns,
    findings,
    ingestion,
    knowledge,
    reports,
    training,
)

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"

app = FastAPI(
    title="NSCA Platform API",
    version="0.1.0",
    description=(
        "AI-driven multi-vendor network security compliance auditor — "
        "Backend Track B REST API (Phase 0 stub, see nsca/docs/15-api-specification.md)."
    ),
    openapi_url=f"{API_PREFIX}/openapi.json",
    docs_url=f"{API_PREFIX}/docs",
    redoc_url=f"{API_PREFIX}/redoc",
)

# Mounted in the dependency order backend-02 §4.2 specifies: campaigns and
# ingestion first, then assessment, findings, training, knowledge, reports,
# admin; webhooks last (and currently contributes no routes — see
# api/webhooks.py).
app.include_router(campaigns.router, prefix=API_PREFIX)
app.include_router(ingestion.router, prefix=API_PREFIX)
app.include_router(assessment.router, prefix=API_PREFIX)
app.include_router(findings.router, prefix=API_PREFIX)
app.include_router(training.router, prefix=API_PREFIX)
app.include_router(knowledge.router, prefix=API_PREFIX)
app.include_router(reports.router, prefix=API_PREFIX)
app.include_router(admin.router, prefix=API_PREFIX)


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    """Container/orchestrator liveness probe — not part of the API contract."""
    return {"status": "ok"}


@app.on_event("startup")
def _preload_knowledge_base() -> None:
    """M5: warm the `KnowledgeBase` cache at process startup rather than on
    the first request that needs it (`knowledge_base_loader.get_knowledge_base`
    does real disk I/O + rulepack/control-pack parsing — see that module's
    docstring). Best-effort: a missing/broken `nsca/knowledge/` directory
    must not prevent the API from starting (e.g. a unit-test process that
    never calls a real-engine code path at all) — every real call site
    (`services/ingestion.py`, `services/assessment.py`) calls
    `get_knowledge_base()` itself and falls back to its own documented
    heuristic/fixture path if this preload didn't happen or failed.
    """

    from nsca_platform.knowledge_base_loader import (
        KnowledgeBaseUnavailable,
        get_knowledge_base,
    )

    try:
        get_knowledge_base()
    except KnowledgeBaseUnavailable as exc:
        logger.warning("KnowledgeBase preload failed at startup: %s", exc)
