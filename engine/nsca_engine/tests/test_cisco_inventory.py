"""Chassis-serial extraction (Phase 3 demo rehearsal finding 7, §9 checklist
item 5) — `extract/cisco_inventory.py` plus its wiring into `assess_device`
(multi-artifact) and `nsca_engine.api.extract_chassis_serial`.

Confirms real regex-based parsing over realistic `show inventory`/`show
version` text (never fabricated), and that a device assessed from BOTH a
running-config and a show-inventory/show-version artifact ends up with real
`FingerprintResult.serials` and real `device.serials[i].*` `Fact`s carrying
genuine per-entry provenance (artifact id + line numbers).
"""

from __future__ import annotations

from nsca_engine.api import ArtifactType, RawArtifact, assess_device, extract_chassis_serial
from nsca_engine.extract import cisco_inventory
from nsca_engine.tests.helpers import ASSESSED_AT, WORKED_EXAMPLE_CONFIG, build_knowledge_base
from nsca_engine.types import ProvenanceSource

# The exact realistic show-inventory sample from the task brief (also
# matches the shape the Phase 3 rehearsal's hand-written fixture used):
# padded PID/VID columns, blank line between entries.
SHOW_INVENTORY_TEXT = (
    'NAME: "1", DESCR: "WS-C3850-24T-E"\n'
    "PID: WS-C3850-24T-E   , VID: V04  , SN: FCW2140L0GH\n"
    "\n"
    'NAME: "StackPort1", DESCR: "StackPort1"\n'
    "PID: STACK-T1-50CM    , VID: V01  , SN: FOC2138Y0K2\n"
    "\n"
    'NAME: "Power Supply 1", DESCR: "Power Supply 1"\n'
    "PID: PWR-C1-350WAC     , VID: V01  , SN: ART2137F0PL\n"
)

SHOW_VERSION_TEXT = (
    "Cisco IOS Software, C3850 Software\n"
    "cisco WS-C3850-24T-E (MIPS) processor\n"
    "Processor board ID FCW2140L0GH\n"
    "5 Gigabit Ethernet interfaces\n"
    "uptime is 3 weeks, 2 days, 1 hour, 4 minutes\n"
    "512K bytes of non-volatile configuration memory.\n"
)


def _artifact(content: str, artifact_id: str, filename: str, hint=None) -> RawArtifact:
    return RawArtifact(
        id=artifact_id, filename=filename, content=content.encode("utf-8"),
        artifact_type_hint=hint, received_from="test",
    )


# ---------------------------------------------------------------------------
# Content sniffing
# ---------------------------------------------------------------------------


def test_looks_like_show_inventory_true_for_real_inventory_text():
    assert cisco_inventory.looks_like_show_inventory(SHOW_INVENTORY_TEXT)


def test_looks_like_show_inventory_false_for_running_config():
    assert not cisco_inventory.looks_like_show_inventory(WORKED_EXAMPLE_CONFIG)


def test_looks_like_show_version_true_for_real_show_version_text():
    assert cisco_inventory.looks_like_show_version(SHOW_VERSION_TEXT)


def test_looks_like_show_version_false_for_running_config():
    assert not cisco_inventory.looks_like_show_version(WORKED_EXAMPLE_CONFIG)


# ---------------------------------------------------------------------------
# extract_show_inventory — real regex parse, real provenance
# ---------------------------------------------------------------------------


def test_extract_show_inventory_finds_all_three_entries():
    result = cisco_inventory.extract_show_inventory(SHOW_INVENTORY_TEXT, "ART-INV")
    assert [s.serial for s in result.serials] == ["FCW2140L0GH", "FOC2138Y0K2", "ART2137F0PL"]
    assert [s.component for s in result.serials] == [
        "WS-C3850-24T-E", "StackPort1", "Power Supply 1",
    ]


def test_extract_show_inventory_facts_carry_real_line_provenance():
    result = cisco_inventory.extract_show_inventory(SHOW_INVENTORY_TEXT, "ART-INV")
    serial_facts = [f for f in result.facts if f.path == "device.serials[0].serial"]
    assert len(serial_facts) == 1
    f = serial_facts[0]
    assert f.value == "FCW2140L0GH"
    assert f.provenance.source == ProvenanceSource.EXPLICIT
    assert f.provenance.artifact_id == "ART-INV"
    # Line 1 (NAME/DESCR header) through line 2 (PID/VID/SN) — real lines
    # from the actual text, not fabricated.
    assert f.provenance.lines == (1, 2)
    assert "SN: FCW2140L0GH" in f.provenance.excerpt
    assert f.provenance.extractor == "cisco_ios.show_inventory.serial@v1"

    component_facts = [f for f in result.facts if f.path == "device.serials[0].component"]
    assert component_facts[0].value == "WS-C3850-24T-E"


def test_extract_show_inventory_entry_with_no_sn_line_contributes_nothing():
    text = 'NAME: "Empty Slot", DESCR: "Empty Slot"\n'  # no PID/VID/SN line follows
    result = cisco_inventory.extract_show_inventory(text, "ART-INV")
    assert result.serials == ()
    assert result.facts == ()


def test_extract_show_inventory_empty_text_returns_empty():
    result = cisco_inventory.extract_show_inventory("", "ART-INV")
    assert result.serials == ()
    assert result.facts == ()


# ---------------------------------------------------------------------------
# extract_show_version_serial — chassis-only fallback
# ---------------------------------------------------------------------------


def test_extract_show_version_serial_finds_chassis_serial():
    result = cisco_inventory.extract_show_version_serial(SHOW_VERSION_TEXT, "ART-VER")
    assert result.serials == (cisco_inventory.DeviceSerial(component="Chassis", serial="FCW2140L0GH"),)
    f = next(f for f in result.facts if f.path == "device.serials[0].serial")
    assert f.provenance.artifact_id == "ART-VER"
    assert f.provenance.lines == (3,)
    assert f.provenance.source == ProvenanceSource.EXPLICIT


def test_extract_show_version_serial_absent_returns_empty():
    result = cisco_inventory.extract_show_version_serial(WORKED_EXAMPLE_CONFIG, "ART-VER")
    assert result.serials == ()
    assert result.facts == ()


# ---------------------------------------------------------------------------
# extract_chassis_serial — narrow api.py entry point (no KnowledgeBase needed)
# ---------------------------------------------------------------------------


def test_extract_chassis_serial_from_show_inventory_bytes():
    assert extract_chassis_serial(SHOW_INVENTORY_TEXT.encode("utf-8")) == "FCW2140L0GH"


def test_extract_chassis_serial_from_show_version_bytes():
    assert extract_chassis_serial(SHOW_VERSION_TEXT.encode("utf-8")) == "FCW2140L0GH"


def test_extract_chassis_serial_none_for_running_config():
    assert extract_chassis_serial(WORKED_EXAMPLE_CONFIG.encode("utf-8")) is None


# ---------------------------------------------------------------------------
# End-to-end: assess_device over BOTH a running-config and a show-inventory
# artifact for the same device (the exact Beat 3 / FR-ING-010 scenario).
# ---------------------------------------------------------------------------


def test_assess_device_with_no_inventory_artifact_has_empty_serials():
    """Honesty check (G2): a device assessed from only its running-config —
    no show version/inventory supplied — must NOT fabricate a serial."""

    kb = build_knowledge_base()
    artifact = _artifact(WORKED_EXAMPLE_CONFIG, "ART-CFG", "running-config.txt")
    assessment = assess_device((artifact,), kb, ASSESSED_AT)
    assert assessment.fingerprint.serials == ()
    assert not any(f.path.startswith("device.serials[") for f in assessment.facts)


def test_assess_device_extracts_serials_from_secondary_show_inventory_artifact():
    """The exact bug the rehearsal found: a real show-inventory artifact
    supplied ALONGSIDE a running-config for the same device must produce
    real serials in the DeviceAssessment — not "NOT DETERMINED"."""

    kb = build_knowledge_base()
    config_artifact = _artifact(WORKED_EXAMPLE_CONFIG, "ART-CFG", "running-config.txt")
    inventory_artifact = _artifact(SHOW_INVENTORY_TEXT, "ART-INV", "show-inventory.txt")
    # Ordered exactly like the platform's `_collect_real_artifacts` (sorted
    # by filename: "running-config.txt" < "show-inventory.txt") — the
    # config is `artifacts[0]` (primary/fingerprinted), the inventory text
    # is a secondary artifact `assess_device` must still consult.
    assessment = assess_device((config_artifact, inventory_artifact), kb, ASSESSED_AT)

    assert [s.serial for s in assessment.fingerprint.serials] == [
        "FCW2140L0GH", "FOC2138Y0K2", "ART2137F0PL",
    ]

    serial_facts_by_path = {f.path: f for f in assessment.facts if f.path.startswith("device.serials[")}
    chassis_serial_fact = serial_facts_by_path["device.serials[0].serial"]
    assert chassis_serial_fact.value == "FCW2140L0GH"
    assert chassis_serial_fact.provenance.artifact_id == "ART-INV"
    assert chassis_serial_fact.provenance.lines  # non-empty — a real citation
    assert chassis_serial_fact.provenance.source == ProvenanceSource.EXPLICIT


def test_assess_device_falls_back_to_show_version_when_no_inventory_supplied():
    kb = build_knowledge_base()
    config_artifact = _artifact(WORKED_EXAMPLE_CONFIG, "ART-CFG", "running-config.txt")
    version_artifact = _artifact(SHOW_VERSION_TEXT, "ART-VER", "show-version.txt")
    assessment = assess_device((config_artifact, version_artifact), kb, ASSESSED_AT)

    assert assessment.fingerprint.serials == (
        cisco_inventory.DeviceSerial(component="Chassis", serial="FCW2140L0GH"),
    )


def test_assess_device_prefers_inventory_over_version_when_both_supplied():
    """`show inventory` is the more granular, authoritative source
    (05-security-baseline-model.md §4.1) — when both are present for one
    device, its multi-component breakdown wins over `show version`'s single
    chassis-only line, rather than merging/duplicating the chassis entry."""

    kb = build_knowledge_base()
    config_artifact = _artifact(WORKED_EXAMPLE_CONFIG, "ART-CFG", "running-config.txt")
    version_artifact = _artifact(SHOW_VERSION_TEXT, "ART-VER", "show-version.txt")
    inventory_artifact = _artifact(SHOW_INVENTORY_TEXT, "ART-INV", "show-inventory.txt")
    assessment = assess_device(
        (config_artifact, version_artifact, inventory_artifact), kb, ASSESSED_AT,
    )

    assert len(assessment.fingerprint.serials) == 3
    assert assessment.fingerprint.serials[0].serial == "FCW2140L0GH"


def test_assess_device_respects_explicit_artifact_type_hint():
    """When Backend Track B *does* know the artifact type (a real
    `ArtifactType.SHOW_INVENTORY` hint), it must be trusted directly rather
    than re-sniffed — sniffing is the documented fallback, not the only
    path."""

    kb = build_knowledge_base()
    config_artifact = _artifact(WORKED_EXAMPLE_CONFIG, "ART-CFG", "running-config.txt")
    inventory_artifact = _artifact(
        SHOW_INVENTORY_TEXT, "ART-INV", "whatever.txt", hint=ArtifactType.SHOW_INVENTORY,
    )
    assessment = assess_device((config_artifact, inventory_artifact), kb, ASSESSED_AT)
    assert len(assessment.fingerprint.serials) == 3
