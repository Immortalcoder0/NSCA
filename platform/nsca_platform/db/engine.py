"""Postgres connection wiring — M1.

Per backend-02 §4.1 / TECH-STACK.md §5: PostgreSQL only, no SQLite
dual-backend in the production code path. `DATABASE_URL` matches what
docker-compose sets (`postgresql+psycopg://nsca:nsca@db:5432/nsca` inside
the compose network); the default here targets the same credentials on
`localhost`, matching the port docker-compose publishes
(`nsca/docker-compose.yml`'s `db` service, `5432:5432`), for running the
app or tests directly on a dev workstation against a docker-compose'd `db`.
"""

from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

DEFAULT_DATABASE_URL = "postgresql+psycopg://nsca:nsca@localhost:5432/nsca"


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(
        get_database_url(),
        future=True,
        pool_pre_ping=True,
        # Short connect timeout so `database_available()` (used to decide
        # whether to skip DB-dependent tests) fails fast on an unreachable
        # host/port instead of hanging on the OS-level TCP timeout.
        connect_args={"connect_timeout": 3},
    )


def reset_engine_cache() -> None:
    """Test-only: forces `get_engine()` to rebuild, e.g. after changing
    `DATABASE_URL` mid-process."""

    get_engine.cache_clear()


def database_available() -> bool:
    """Best-effort reachability probe, used by tests to skip DB-dependent
    cases gracefully (per backend-02 M1 task instructions) rather than
    failing the whole suite when no Postgres is reachable in the sandbox.
    """

    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return True
    except Exception:
        return False


def connect() -> Connection:
    """One connection, one transaction per call site — callers use this as
    a context manager (`with connect() as conn: ...`) and commit/rollback
    explicitly, matching SQLAlchemy Core's explicit-transaction style
    (backend-02 §4.1: "SQLAlchemy Core, not the ORM").
    """

    return get_engine().connect()
