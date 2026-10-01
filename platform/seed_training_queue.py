"""One-off seed script (not a test, not shipped) — Frontend Track 3
integration seeding.

The real `POST /training/*` API surface has no endpoint that populates
`training_question` rows: `services/training.seed_questions_for_platform`
(the mine -> propose -> persist pipeline) is only ever invoked from
platform test code today (see
`nsca_platform/tests/test_training_pipeline.py`), not wired into the
ingestion HTTP path yet. To give the frontend's Training Studio queue a
real (non-mock) "platform not taught" entry to render against, this script
calls that same real service function directly against the live dev DB,
using the project's own MikroTik RouterOS acceptance fixture
(`nsca_platform/tests/fixtures/mikrotik.py` — the fixture
08-learning-system.md's "9 questions" / "98.4% coverage" worked example is
built from). Platform id is `routeros`, matching the real
`nsca/knowledge/rulepacks/routeros.yaml` rulepack's `platform:` field
(that rulepack is NOT loaded into this DB's `knowledge/rulepacks` table —
only `cisco_iosxe` is — which is exactly what makes `routeros` a genuine,
reproducible "not taught" queue entry rather than a fabricated one).

Reproduce by running (server must NOT be holding an exclusive lock —
reads/writes go through the same Postgres the running uvicorn process
uses):

    cd nsca/platform
    DATABASE_URL="postgresql+psycopg://nsca:nsca@localhost:15432/nsca" \
      .venv/Scripts/python seed_training_queue.py
"""

from __future__ import annotations

from nsca_platform.db.engine import connect
from nsca_platform.learning.template_mining import RequiredControlLike
from nsca_platform.services import training as training_service
from nsca_platform.tests.fixtures.mikrotik import (
    build_required_controls,
    build_unmatched_constructs,
)

PLATFORM = "routeros"


def main() -> None:
    controls_fixture = build_required_controls()
    controls = [RequiredControlLike(c.control_id, c.requires_facts) for c in controls_fixture]
    fact_candidates = [(f, "boolean") for c in controls_fixture for f in c.requires_facts]
    unmatched = build_unmatched_constructs()

    with connect() as conn:
        existing = training_service.queue_for_platform(conn, PLATFORM)
        if existing:
            print(f"platform {PLATFORM!r} already has {len(existing)} question(s) queued — skipping seed")
            return
        created = training_service.seed_questions_for_platform(
            conn,
            platform=PLATFORM,
            unmatched=unmatched,
            controls=controls,
            fact_candidates=fact_candidates,
        )
        conn.commit()
        print(f"seeded {len(created)} training questions for platform={PLATFORM!r}")
        for c in created:
            print(f"  {c['id']}  rank={c['rank']}  section={c.get('section')}")


if __name__ == "__main__":
    main()
