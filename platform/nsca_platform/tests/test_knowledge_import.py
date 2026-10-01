"""STIG/NIST import round-trip + rulepack bundle export/import round-trip +
DM-9 constraint — backend-02 §4.5, M4.
"""

from __future__ import annotations

import io
import tempfile
import zipfile

import pytest
from sqlalchemy import select

from nsca_platform.knowledge_import import nist_oscal, rulepack_bundle, stig_xccdf
from nsca_platform.tests.conftest import requires_db

_XCCDF_SAMPLE = b"""<?xml version="1.0"?>
<Benchmark xmlns="http://checklists.nist.gov/xccdf/1.1" id="xccdf_mil.disa.stig_benchmark_CISCO_IOS_XE_ROUTER">
  <version>13</version>
  <Group id="V-216644">
    <title>SRG-NET-000131-RTR-000078</title>
    <Rule id="SV-216644r_rule" severity="high">
      <title>Plaintext management protocols must be disabled.</title>
      <check system="C-1"><check-content>Verify transport input does not include telnet.</check-content></check>
    </Rule>
  </Group>
  <Group id="V-216620">
    <Rule id="SV-216620r_rule" severity="medium">
      <title>Session idle timeout must be bounded.</title>
      <check><check-content>Verify exec-timeout is 300 seconds or less.</check-content></check>
    </Rule>
  </Group>
</Benchmark>"""

_OSCAL_SAMPLE = b"""{
  "catalog": {
    "metadata": {"title": "NIST SP 800-53", "version": "Rev5"},
    "groups": [
      {"id": "ac", "title": "Access Control", "controls": [
        {"id": "ac-17", "title": "Remote Access", "parts": [
          {"name": "statement", "prose": "The organization establishes remote access usage restrictions."}
        ], "controls": [
          {"id": "ac-17.1", "title": "Monitoring and Control"}
        ]}
      ]}
    ]
  }
}"""


# ---------------------------------------------------------------------------
# STIG XCCDF
# ---------------------------------------------------------------------------


def test_stig_xccdf_parses_group_rule_pairs():
    items = stig_xccdf.parse_xccdf(_XCCDF_SAMPLE, benchmark="cisco_iosxe_router")
    assert len(items) == 2
    v216644 = next(i for i in items if i.item_id == "V-216644")
    assert v216644.framework == "stig"
    assert v216644.benchmark == "cisco_iosxe_router"
    assert v216644.version == "13"
    assert v216644.severity == "CAT I"  # high -> CAT I
    assert v216644.title == "Plaintext management protocols must be disabled."
    assert "telnet" in v216644.stated_audit_procedure
    assert v216644.text_redistributable is True

    v216620 = next(i for i in items if i.item_id == "V-216620")
    assert v216620.severity == "CAT II"  # medium -> CAT II


def test_stig_xccdf_deterministic_order():
    items1 = stig_xccdf.parse_xccdf(_XCCDF_SAMPLE, benchmark="x")
    items2 = stig_xccdf.parse_xccdf(_XCCDF_SAMPLE, benchmark="x")
    assert items1 == items2
    assert [i.item_id for i in items1] == sorted(i.item_id for i in items1)


def test_stig_xccdf_refuses_malformed_xml():
    with pytest.raises(stig_xccdf.StigParseError):
        stig_xccdf.parse_xccdf(b"<not-xml")


def test_stig_xccdf_refuses_non_benchmark_root():
    with pytest.raises(stig_xccdf.StigParseError):
        stig_xccdf.parse_xccdf(b"<SomethingElse/>")


# ---------------------------------------------------------------------------
# NIST OSCAL
# ---------------------------------------------------------------------------


def test_nist_oscal_parses_nested_controls_and_enhancements():
    items = nist_oscal.parse_oscal_catalog(_OSCAL_SAMPLE)
    ids = {i.item_id for i in items}
    assert ids == {"AC-17", "AC-17.1"}
    ac17 = next(i for i in items if i.item_id == "AC-17")
    assert ac17.framework == "nist"
    assert ac17.version == "Rev5"
    assert "remote access" in ac17.stated_audit_procedure.lower()
    assert ac17.text_redistributable is True


def test_nist_oscal_derives_framework_family_from_catalog_title_not_hardcoded():
    # Phase 3 demo-rehearsal Bug 3: an OSCAL-formatted catalog titled "ISO"
    # was previously mislabelled `"framework": "nist"` unconditionally —
    # OSCAL is a *format*, not itself a framework family (see
    # nist_oscal.py's module/`_framework_family` docstrings).
    iso_titled = b"""{
      "catalog": {
        "metadata": {"title": "ISO/IEC 27001:2022 Annex A", "version": "2022"},
        "groups": [
          {"id": "a9", "title": "Access control", "controls": [
            {"id": "a.9.4.2", "title": "Secure log-on procedures"}
          ]}
        ]
      }
    }"""
    items = nist_oscal.parse_oscal_catalog(iso_titled)
    assert items
    assert all(i.framework == "iso" for i in items)

    # A genuinely NIST-titled catalog still labels "nist" (no regression).
    nist_items = nist_oscal.parse_oscal_catalog(_OSCAL_SAMPLE)
    assert all(i.framework == "nist" for i in nist_items)

    # An untitled/unrecognisable catalog falls back to "nist" — documented
    # default, not a silent mislabel of recognisable content.
    unlabeled = b'{"catalog": {"metadata": {}, "groups": [{"id": "g", "controls": [{"id": "x-1", "title": "t"}]}]}}'
    assert nist_oscal.parse_oscal_catalog(unlabeled)[0].framework == "nist"


def test_nist_oscal_refuses_malformed_json():
    with pytest.raises(nist_oscal.OscalParseError):
        nist_oscal.parse_oscal_catalog(b"{not json")


def test_nist_oscal_refuses_missing_catalog_key():
    with pytest.raises(nist_oscal.OscalParseError):
        nist_oscal.parse_oscal_catalog(b'{"not_a_catalog": {}}')


# ---------------------------------------------------------------------------
# Rulepack bundle export/import round-trip + signature verification
# ---------------------------------------------------------------------------

_RULEPACK_PATH = rulepack_bundle.DEFAULT_STAGING_DIR.parent / "cisco_ios.yaml"


def test_rulepack_bundle_round_trip():
    bundle = rulepack_bundle.export_bundle(_RULEPACK_PATH)
    with tempfile.TemporaryDirectory() as td:
        result = rulepack_bundle.import_bundle(bundle, staging_dir=td)
        assert result.platform == "cisco_ios"
        assert result.signature_verified is True
        assert result.trust_tier == "verified_community"
        from pathlib import Path

        assert Path(result.staged_path).read_text(encoding="utf-8") == _RULEPACK_PATH.read_text(encoding="utf-8")


def test_rulepack_bundle_rejects_tampered_content():
    bundle = rulepack_bundle.export_bundle(_RULEPACK_PATH)
    zin = zipfile.ZipFile(io.BytesIO(bundle))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zout:
        for name in zin.namelist():
            data = zin.read(name)
            if name == rulepack_bundle.RULEPACK_ENTRY_NAME:
                data += b"\n# tampered"
            zout.writestr(name, data)

    with pytest.raises(rulepack_bundle.SignatureVerificationError):
        rulepack_bundle.import_bundle(buf.getvalue())


def test_rulepack_bundle_rejects_missing_members():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("manifest.yaml", "platform: x\n")
    with pytest.raises(rulepack_bundle.BundleError):
        rulepack_bundle.import_bundle(buf.getvalue())


# ---------------------------------------------------------------------------
# DM-9 — text_redistributable enforced at the DB layer
# ---------------------------------------------------------------------------


@requires_db
def test_dm9_rejects_iso_text_at_the_db_layer(db_conn):
    from nsca_platform.db.models.knowledge import framework_item
    import uuid
    from sqlalchemy.exc import IntegrityError

    # Legal: text_redistributable = True (e.g. a STIG/NIST item) may carry title text.
    db_conn.execute(
        framework_item.insert().values(
            id=uuid.uuid4(), framework="stig", benchmark="b", version="1",
            item_id="V-000001", title="A legal title", text_redistributable=True,
        )
    )
    db_conn.commit()

    # Illegal: ISO (or CIS) item claiming text_redistributable=false MUST NOT
    # carry title/stated_audit_procedure/equivalence_rationale text — DM-9,
    # enforced by `framework_item_dm9_text_redistributable`.
    with pytest.raises(IntegrityError):
        db_conn.execute(
            framework_item.insert().values(
                id=uuid.uuid4(), framework="iso", benchmark="27001", version="2022",
                item_id="A.9.4.2", title="Restricted ISO clause text — must not be stored",
                text_redistributable=False,
            )
        )
        db_conn.commit()
    db_conn.rollback()

    # Legal: text_redistributable = False WITHOUT any text fields (identifiers only).
    db_conn.execute(
        framework_item.insert().values(
            id=uuid.uuid4(), framework="iso", benchmark="27001", version="2022",
            item_id="A.9.4.2", text_redistributable=False,
        )
    )
    db_conn.commit()

    rows = db_conn.execute(select(framework_item).where(framework_item.c.framework == "iso")).fetchall()
    assert len(rows) == 1
    assert rows[0].title is None
