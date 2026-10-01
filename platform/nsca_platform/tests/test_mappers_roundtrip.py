"""INTEGRATION tests across the engine boundary — backend-02 §6.

"for every contract dataclass in `nsca_engine.api`, a round-trip test that
constructs one, passes it through your mapper into the DB, reads it back,
and asserts equality."

M1 touches two of those dataclasses for real (`RawArtifact` at the
ingestion boundary, `FingerprintResult` at the correlation boundary); a
third (`Fact`, feeding the `assessment`/`fact` tables) has its table shape
built in M1 but its producer (`assess_device`) is M2 — its round trip here
uses a hand-built fixture object, per backend-02 §3's fixture-then-real
pattern, exactly as the milestone notes allow.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from fractions import Fraction

import pytest
from sqlalchemy import select

from nsca_engine.api import RawArtifact
from nsca_engine.types import ArtifactType, DeviceSerial, Fact, FingerprintResult, Provenance, ProvenanceSource
from nsca_platform.db import mappers
from nsca_platform.db.models.artifact import artifact as artifact_table
from nsca_platform.db.models.assessment import assessment as assessment_table
from nsca_platform.db.models.assessment import fact as fact_table
from nsca_platform.db.models.campaign import campaign as campaign_table
from nsca_platform.db.models.device import device as device_table
from nsca_platform.tests.conftest import requires_db


@requires_db
def test_raw_artifact_roundtrip(db_conn) -> None:
    campaign_id = uuid.uuid4()
    db_conn.execute(
        campaign_table.insert().values(
            id=campaign_id,
            public_id="CMP-TEST-001",
            name="mapper roundtrip",
            scope_definition={},
            owner="tester",
        )
    )

    original = RawArtifact(
        id="ART-MAPPER-001",
        filename="core-sw-01/running-config.txt",
        content=b"hostname CORE-SW-01\n",
        artifact_type_hint=ArtifactType.RUNNING_CONFIG,
        received_from="upload",
    )

    row_values = mappers.raw_artifact_to_row(
        original,
        campaign_id=campaign_id,
        device_id=None,
        content_hash="deadbeef",
        storage_path="artifacts/de/ad/deadbeef",
    )
    db_conn.execute(artifact_table.insert().values(**row_values))

    persisted = db_conn.execute(
        select(artifact_table).where(artifact_table.c.public_id == "ART-MAPPER-001")
    ).mappings().first()
    assert persisted is not None

    restored = mappers.row_to_raw_artifact(persisted, content=original.content)

    assert restored.id == original.id
    assert restored.filename == original.filename
    assert restored.content == original.content
    assert restored.artifact_type_hint == original.artifact_type_hint
    assert restored.received_from == original.received_from


@requires_db
def test_fingerprint_result_roundtrip(db_conn) -> None:
    original = FingerprintResult(
        vendor="cisco",
        platform="cisco_iosxe",
        os_version="16.12.04",
        model="C9300-24T",
        serials=(DeviceSerial(component="chassis", serial="FCW2140L0GH"),),
        confidence=Fraction(97, 100),
    )

    row_values = mappers.fingerprint_to_device_row(original, hostname="CORE-SW-01")
    db_conn.execute(device_table.insert().values(**row_values))

    persisted = db_conn.execute(
        select(device_table).where(device_table.c.hostname == "CORE-SW-01")
    ).mappings().first()
    assert persisted is not None

    restored = mappers.row_to_fingerprint(persisted, vendor=original.vendor, confidence=original.confidence)

    assert restored.vendor == original.vendor
    assert restored.platform == original.platform
    assert restored.os_version == original.os_version
    assert restored.model == original.model
    assert restored.serials == original.serials
    assert restored.confidence == original.confidence


@requires_db
def test_fact_roundtrip_fixture(db_conn) -> None:
    """Fixture `Fact` object — M2's real `assess_device` doesn't exist yet
    (fixture-then-real pattern, backend-02 §3), but the `fact` table shape
    (TECH-STACK.md §5's `value jsonb NULL = unknown`) is M1 scope, so the
    mapper round trip is exercised now against a hand-built object."""

    campaign_id = uuid.uuid4()
    device_id = uuid.uuid4()
    db_conn.execute(
        campaign_table.insert().values(
            id=campaign_id, public_id="CMP-TEST-002", name="fact roundtrip", scope_definition={}, owner="tester"
        )
    )
    db_conn.execute(device_table.insert().values(id=device_id, hostname="FACT-TEST-DEV", serials=[]))
    assessment_id = uuid.uuid4()
    db_conn.execute(
        assessment_table.insert().values(
            id=assessment_id,
            public_id="ASM-TEST-001",
            campaign_id=campaign_id,
            device_id=device_id,
            executed_at=datetime.now(timezone.utc),
        )
    )

    original = Fact(
        path="mgmt.protocols.telnet.enabled",
        value=True,
        type="boolean",
        provenance=Provenance(
            source=ProvenanceSource.EXPLICIT,
            lines=(143,),
            excerpt=" transport input telnet ssh",
            extractor="cisco_iosxe.vty.transport_input@7",
            confidence=Fraction(1, 1),
        ),
    )

    row_values = mappers.fact_to_row(original, assessment_id=assessment_id, artifact_id=None)
    db_conn.execute(fact_table.insert().values(**row_values))

    persisted = (
        db_conn.execute(select(fact_table).where(fact_table.c.assessment_id == assessment_id))
        .mappings()
        .first()
    )
    assert persisted is not None
    assert persisted["value"] is True  # not confusable with SQL/JSON false

    restored = mappers.row_to_fact(persisted)
    assert restored.path == original.path
    assert restored.value == original.value
    assert restored.type == original.type
    assert restored.provenance.source == original.provenance.source
    assert restored.provenance.lines == original.provenance.lines
    assert restored.provenance.excerpt == original.provenance.excerpt
    assert restored.provenance.extractor == original.provenance.extractor


@requires_db
def test_fact_null_value_is_unknown_not_false(db_conn) -> None:
    """The load-bearing invariant from TECH-STACK.md §5: `value jsonb NULL`
    must round-trip as Python `None` (unknown/⊥), never coerce to `False`."""

    campaign_id = uuid.uuid4()
    device_id = uuid.uuid4()
    db_conn.execute(
        campaign_table.insert().values(
            id=campaign_id, public_id="CMP-TEST-003", name="null fact", scope_definition={}, owner="tester"
        )
    )
    db_conn.execute(device_table.insert().values(id=device_id, hostname="NULL-FACT-DEV", serials=[]))
    assessment_id = uuid.uuid4()
    db_conn.execute(
        assessment_table.insert().values(
            id=assessment_id,
            public_id="ASM-TEST-002",
            campaign_id=campaign_id,
            device_id=device_id,
            executed_at=datetime.now(timezone.utc),
        )
    )

    unknown_fact = Fact(
        path="mgmt.protocols.snmp.v3.enabled",
        value=None,
        type="boolean",
        provenance=Provenance(source=ProvenanceSource.DEFAULT_UNKNOWN),
    )
    row_values = mappers.fact_to_row(unknown_fact, assessment_id=assessment_id, artifact_id=None)
    db_conn.execute(fact_table.insert().values(**row_values))

    persisted = (
        db_conn.execute(select(fact_table).where(fact_table.c.assessment_id == assessment_id))
        .mappings()
        .first()
    )
    assert persisted["value"] is None
    assert persisted["value"] is not False

    restored = mappers.row_to_fact(persisted)
    assert restored.value is None


@requires_db
def test_unmatched_construct_roundtrip(db_conn) -> None:
    """M3 — the learning subsystem queue's engine-contract dataclass
    (`nsca_engine.types.UnmatchedConstruct`), fixture-then-real per
    backend-02 §3 (Track A's real extractor runtime is the producer;
    `tests/fixtures/mikrotik.py` hand-builds these from
    08-learning-system.md's worked examples for this milestone's tests)."""

    from nsca_engine.types import UnmatchedConstruct

    from nsca_platform.db.models.learning import unmatched_construct as unmatched_construct_table

    uc = UnmatchedConstruct(
        artifact_id="RTR-Pune-02.rsc",
        lines=(14,),
        excerpt="set telnet disabled=no port=23",
        parse_path=("/ip service",),
    )
    row_values = mappers.unmatched_construct_to_row(uc, platform="mikrotik_routeros")
    db_conn.execute(unmatched_construct_table.insert().values(**row_values))

    persisted = (
        db_conn.execute(
            select(unmatched_construct_table).where(unmatched_construct_table.c.artifact_id == "RTR-Pune-02.rsc")
        )
        .mappings()
        .first()
    )
    assert persisted["platform"] == "mikrotik_routeros"

    restored = mappers.row_to_unmatched_construct(persisted)
    assert restored == uc
