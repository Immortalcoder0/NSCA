"""Demo data seeding — real dataflow only.

Exercises the exact same service-layer functions a human clicking through
the app would trigger (create campaign -> upload real artifacts -> resolve
scope -> assess -> issue -> generate report -> seed a training queue entry)
rather than inserting rows directly or fabricating response shapes. This
exists for two reasons: (1) a one-click way to populate the app for a demo,
and (2) practical resilience against the shared dev database's known reset
risk (flagged in nsca/plans/phase3-demo-rehearsal.md's "mid-session
incident") — re-running this after a reset restores a working demo state
in one call.

Uses real fixture configs already checked into the engine's own test
corpus (`nsca/engine/nsca_engine/tests/fixtures/`) rather than inventing
new content — the same files Backend Track A's own tests and the Phase 3
rehearsal used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.engine import Connection

from nsca_platform.learning.template_mining import RequiredControlLike
from nsca_platform.services import assessment as assessment_service
from nsca_platform.services import campaign as campaign_service
from nsca_platform.services import ingestion as ingestion_service
from nsca_platform.services import report_service
from nsca_platform.services import training as training_service
from nsca_platform.tests.fixtures.mikrotik import (
    build_required_controls,
    build_unmatched_constructs,
)

# nsca/platform/nsca_platform/services/demo_seed.py -> parents[3] is nsca/
_ENGINE_FIXTURES = Path(__file__).resolve().parents[3] / "engine" / "nsca_engine" / "tests" / "fixtures"

# Every upload is named "<HOSTNAME>/<file>" so ingestion's path-based
# correlation fallback (`_heuristic_correlate`) resolves a real,
# predictable hostname regardless of whether that platform's config syntax
# matches one of the two content-based regexes — most non-Cisco/MikroTik
# platforms don't (see `_HOSTNAME_PATTERNS` in `services/ingestion.py`),
# which is itself a real, narrower gap this seed sidesteps rather than
# papers over (flagged, not silently worked around in production code).
_DEVICES: tuple[tuple[str, str, str], ...] = (
    ("CORE-SW-01", "ap003/core_sw_01.cfg", "running-config.txt"),
    ("EDGE-FW-01", "ap003/edge_fw_01.cfg", "running-config.txt"),
    ("JNPR-SET-01", "juniper_set.conf", "config.txt"),
    ("JNPR-BRACE-01", "juniper_brace.conf", "config.txt"),
    ("FGT-FW-01", "fortios.conf", "config.txt"),
    ("PANOS-FW-01", "panos.xml", "config.xml"),
    ("CLOUD-FW-01", "cloud_fw.json", "policy.json"),
    ("MT-RTR-01", "routeros.rsc", "export.rsc"),
)

_TRAINING_DEMO_PLATFORM = "routeros"


def _read_fixture(relative_path: str) -> bytes:
    return (_ENGINE_FIXTURES / relative_path).read_bytes()


def _build_upload_files() -> list[tuple[str, bytes]]:
    files: list[tuple[str, bytes]] = []
    for hostname, fixture_rel, artifact_name in _DEVICES:
        content = _read_fixture(fixture_rel)
        if hostname == "MT-RTR-01":
            # The shipped RouterOS fixture has no `/system identity` line
            # (a real, separately-flagged gap in that fixture) — the
            # directory-path fallback already gives it a hostname, this
            # just also exercises the content-based MikroTik regex path.
            content += b"\n/system identity\nset name=MT-RTR-01\n"
        files.append((f"{hostname}/{artifact_name}", content))
    return files


def _seed_training_queue(conn: Connection) -> int:
    existing = training_service.queue_for_platform(conn, _TRAINING_DEMO_PLATFORM)
    if existing:
        return 0
    controls_fixture = build_required_controls()
    controls = [RequiredControlLike(c.control_id, c.requires_facts) for c in controls_fixture]
    fact_candidates = [(f, "boolean") for c in controls_fixture for f in c.requires_facts]
    unmatched = build_unmatched_constructs()
    created = training_service.seed_questions_for_platform(
        conn, platform=_TRAINING_DEMO_PLATFORM, unmatched=unmatched,
        controls=controls, fact_candidates=fact_candidates,
    )
    return len(created)


def run(conn: Connection, actor: str) -> dict[str, Any]:
    """Runs the full seed sequence in one DB transaction (the caller
    commits). Returns a summary of what was created for the response body
    — not the full nested payloads, which the frontend already has real
    hooks to fetch once it refetches its query cache."""

    campaign = campaign_service.create_campaign(
        conn,
        {
            "name": "Demo Walkthrough",
            "scope": {"type": "explicit", "devices": [d[0] for d in _DEVICES]},
            "frameworks": [
                {"framework": "cis", "version": "4.1.0"},
                {"framework": "nist", "version": "Rev5"},
            ],
            "owner": actor,
            "window": {"start": "2026-09-01", "end": "2026-09-30"},
        },
        actor,
    )
    campaign_id = campaign["id"]

    upload_result = ingestion_service.upload_artifacts(conn, campaign_id, _build_upload_files(), actor)
    scope_result = campaign_service.resolve_scope(conn, campaign_id, actor)
    assess_result = assessment_service.run_assessment(conn, campaign_id, actor)
    campaign_service.issue_campaign(conn, campaign_id, actor)

    report = report_service.generate_report(
        conn, campaign_id, "CORE-SW-01", mode="issued", actor=actor,
    )

    training_questions_seeded = _seed_training_queue(conn)

    return {
        "campaign_id": campaign_id,
        "devices_uploaded": len(_DEVICES),
        "artifact_outcomes": [r.get("status") for r in upload_result.get("results", [])],
        "devices_assessed": scope_result.get("device_count", 0),
        "assessment_job": assess_result.get("job_id"),
        "report_id": report.get("id") or report.get("report_id"),
        "training_platform_seeded": _TRAINING_DEMO_PLATFORM if training_questions_seeded else None,
        "training_questions_seeded": training_questions_seeded,
    }
