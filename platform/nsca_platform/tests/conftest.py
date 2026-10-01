"""Shared test fixtures — M1.

Per the M1 task instructions: DB-dependent tests must be structured to
skip gracefully (with a clear reason) when no Postgres is reachable,
rather than turning the whole suite red or silently switching to SQLite
(TECH-STACK.md §5 forbids a SQLite dual-backend in the production code
path — that constraint extends to not inventing a second backend just for
tests either).

`db_conn` creates the real schema via `metadata.create_all()` against
whatever `DATABASE_URL` points at (docker-compose's `db` service by
default) and truncates every table before each test that uses it, so
tests are isolated without needing to run Alembic migrations on every
test session.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from nsca_platform.db.engine import connect, database_available, get_engine
from nsca_platform.db.models import metadata

DB_AVAILABLE = database_available()

requires_db = pytest.mark.skipif(
    not DB_AVAILABLE,
    reason=(
        "No reachable Postgres at DATABASE_URL (default "
        "postgresql+psycopg://nsca:nsca@localhost:5432/nsca). Start it with "
        "`docker compose -f nsca/docker-compose.yml up -d db` to run this test."
    ),
)


@pytest.fixture(scope="session", autouse=True)
def _artifact_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("artifacts")
    import os

    os.environ["NSCA_ARTIFACT_ROOT"] = str(root)
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture(scope="session")
def _schema() -> None:
    if not DB_AVAILABLE:
        pytest.skip("No reachable Postgres for schema setup.")
    metadata.create_all(get_engine())


@pytest.fixture()
def db_conn(_schema: None):
    with connect() as conn:
        yield conn
        conn.rollback()
        # Truncate everything so each test starts from an empty DB,
        # without needing a fresh container per test.
        with connect() as cleanup:
            for table in reversed(metadata.sorted_tables):
                cleanup.execute(table.delete())
            cleanup.commit()
