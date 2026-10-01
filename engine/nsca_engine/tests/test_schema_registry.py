"""M0 unit tests (backend-01 §6): the schema registry loads and validates
`knowledge/schema/*.yaml`, and `Fact` supports every provenance source
classification from 05-security-baseline-model.md §3.1.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nsca_engine.schema.registry import SchemaRegistry, SchemaRegistryError
from nsca_engine.types import Fact, Provenance, ProvenanceSource

# knowledge/schema lives at repo_root/knowledge/schema; this test file is at
# engine/nsca_engine/tests/test_schema_registry.py, four levels down from
# repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_DIR = _REPO_ROOT / "knowledge" / "schema"

# The ten top-level domains from 05-security-baseline-model.md §4.
_EXPECTED_DOMAINS = {
    "device",
    "mgmt",
    "auth",
    "crypto",
    "logging",
    "time",
    "snmp",
    "filter",
    "topology",
    "services",
}


@pytest.fixture(scope="module")
def registry() -> SchemaRegistry:
    return SchemaRegistry.load(_SCHEMA_DIR)


def test_registry_loads_without_error(registry: SchemaRegistry) -> None:
    assert len(registry) > 0


def test_registry_covers_ten_top_level_domains(registry: SchemaRegistry) -> None:
    assert set(registry.domains) == _EXPECTED_DOMAINS


def test_domains_are_returned_sorted(registry: SchemaRegistry) -> None:
    assert list(registry.domains) == sorted(registry.domains)


def test_every_domain_has_at_least_one_fact_definition(
    registry: SchemaRegistry,
) -> None:
    for domain in registry.domains:
        defs = registry.fact_definitions_for_domain(domain)
        assert len(defs) > 0, f"domain '{domain}' has no fact definitions"


def test_known_fact_path_resolves(registry: SchemaRegistry) -> None:
    fd = registry.get_fact_definition("mgmt.protocols.telnet.enabled")
    assert fd is not None
    assert fd.type == "boolean"
    assert fd.domain == "mgmt"


def test_unknown_fact_path_resolves_to_none(registry: SchemaRegistry) -> None:
    assert registry.get_fact_definition("nonexistent.made.up.path") is None


def test_missing_schema_dir_raises() -> None:
    with pytest.raises(SchemaRegistryError):
        SchemaRegistry.load(_REPO_ROOT / "knowledge" / "does_not_exist")


def test_rejects_file_with_bad_shape(tmp_path: Path) -> None:
    bad = tmp_path / "broken.yaml"
    bad.write_text("domain: broken\n", encoding="utf-8")  # missing required fields
    with pytest.raises(SchemaRegistryError):
        SchemaRegistry.load(tmp_path)


def test_rejects_fact_path_outside_declared_domain(tmp_path: Path) -> None:
    bad = tmp_path / "broken.yaml"
    bad.write_text(
        """
domain: mgmt
schema_version: "0.1.0"
fact_definitions:
  - path: auth.oops.enabled
    type: boolean
    category: management_plane
    description: "wrong prefix"
""",
        encoding="utf-8",
    )
    with pytest.raises(SchemaRegistryError):
        SchemaRegistry.load(tmp_path)


# ---------------------------------------------------------------------------
# Fact / Provenance construction across every provenance source
# classification (05-security-baseline-model.md §3.1, 14-data-model.md §2).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("source", list(ProvenanceSource))
def test_fact_constructs_for_every_provenance_source(
    source: ProvenanceSource,
) -> None:
    provenance = Provenance(
        source=source,
        artifact_id="CORE-SW-01/running-config.txt" if source != ProvenanceSource.DERIVED else None,
        lines=(143,) if source == ProvenanceSource.EXPLICIT else (),
        layer="template_stack" if source == ProvenanceSource.INHERITED else None,
        depends_on=("auth.local_users[0].storage_type",)
        if source == ProvenanceSource.DERIVED
        else (),
    )
    fact = Fact(
        path="mgmt.protocols.telnet.enabled",
        value=True if source != ProvenanceSource.DEFAULT_UNKNOWN else None,
        type="boolean",
        provenance=provenance,
    )
    assert fact.provenance.source is source


def test_default_unknown_fact_has_null_value() -> None:
    """The worked example in 05-security-baseline-model.md §9:
    `crypto.ssh.ciphers` resolves default_unknown with value null, which
    forces UNKNOWN downstream rather than silently passing (SBM-3)."""

    fact = Fact(
        path="crypto.ssh.ciphers",
        value=None,
        type="list<algorithm>",
        provenance=Provenance(source=ProvenanceSource.DEFAULT_UNKNOWN),
    )
    assert fact.value is None
    assert fact.provenance.source is ProvenanceSource.DEFAULT_UNKNOWN


def test_derived_fact_provenance_records_dependencies() -> None:
    """05-security-baseline-model.md §5: a derived fact records which facts
    it depends on, and (by construction elsewhere, not enforced by the
    dataclass itself) inherits their weakest provenance."""

    fact = Fact(
        path="auth.local_users[0].reversible",
        value=True,
        type="boolean",
        provenance=Provenance(
            source=ProvenanceSource.DERIVED,
            depends_on=("auth.local_users[0].storage_type",),
        ),
    )
    assert fact.provenance.depends_on == ("auth.local_users[0].storage_type",)
