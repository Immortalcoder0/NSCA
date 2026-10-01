"""Shared test helpers: builds a `KnowledgeBase` from the real
`knowledge/rulepacks/cisco_ios.yaml` + `knowledge/control_packs/
nsca_native.yaml` content, and the two Cisco IOS fixture configs M1's tests
run against.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from nsca_engine.api import ControlPack, KnowledgeBase, KnowledgeBasePin, Rulepack
from nsca_engine.controls.rulepack_loader import load_control_pack, load_rulepack
from nsca_engine.schema.registry import SchemaRegistry

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO_ROOT / "knowledge" / "schema"
RULEPACK_PATH = REPO_ROOT / "knowledge" / "rulepacks" / "cisco_ios.yaml"
CONTROL_PACK_PATH = REPO_ROOT / "knowledge" / "control_packs" / "nsca_native.yaml"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# M2 (backend-01 §6) — the five remaining structural paradigms plus cloud
# JSON, one rulepack path per new platform.
M2_RULEPACK_PATHS = {
    "juniper_junos_set": REPO_ROOT / "knowledge" / "rulepacks" / "juniper_set.yaml",
    "juniper_junos_curly": REPO_ROOT / "knowledge" / "rulepacks" / "juniper_brace.yaml",
    "fortios": REPO_ROOT / "knowledge" / "rulepacks" / "fortios.yaml",
    "panos": REPO_ROOT / "knowledge" / "rulepacks" / "panos.yaml",
    "routeros": REPO_ROOT / "knowledge" / "rulepacks" / "routeros.yaml",
    "cloud_generic_fw": REPO_ROOT / "knowledge" / "rulepacks" / "cloud_fw.yaml",
}
M2_CONTROL_PACK_PATH = REPO_ROOT / "knowledge" / "control_packs" / "nsca_native_m2.yaml"

# One hand-written fixture config per M2 platform (TRD-00 §8 fixture class).
M2_FIXTURES = {
    "juniper_junos_set": FIXTURES_DIR / "juniper_set.conf",
    "juniper_junos_curly": FIXTURES_DIR / "juniper_brace.conf",
    "fortios": FIXTURES_DIR / "fortios.conf",
    "panos": FIXTURES_DIR / "panos.xml",
    "routeros": FIXTURES_DIR / "routeros.rsc",
    "cloud_generic_fw": FIXTURES_DIR / "cloud_fw.json",
}

ASSESSED_AT = datetime(2026, 8, 28, 12, 0, 0, tzinfo=UTC)


def build_knowledge_base_m2() -> KnowledgeBase:
    """A `KnowledgeBase` carrying every M1+M2 rulepack and both native
    control packs — used by the M2 paradigm-breadth smoke/metamorphic tests
    (backend-01 M2 §6: "corpus coverage meets TRD-00 §8.2's minimums (5
    platforms, >=3 structural paradigms...)"). Kept separate from
    `build_knowledge_base()` (Cisco-only) so the M1 tests that assert
    specific fingerprint-margin behaviour against a single loaded rulepack
    are unaffected by M2 additions.
    """

    schema_registry = SchemaRegistry.load(SCHEMA_DIR)

    loaded_rp_cisco = load_rulepack(RULEPACK_PATH)
    loaded_m2 = {platform: load_rulepack(p) for platform, p in M2_RULEPACK_PATHS.items()}

    rulepacks = [
        Rulepack(
            platform="cisco_ios", version=loaded_rp_cisco.version,
            trust_tier=loaded_rp_cisco.trust_tier, extractors=(), loaded=loaded_rp_cisco,
        )
    ]
    rulepack_versions = [f"cisco_ios@{loaded_rp_cisco.version}"]
    for platform, lrp in sorted(loaded_m2.items()):
        rulepacks.append(
            Rulepack(
                platform=platform, version=lrp.version, trust_tier=lrp.trust_tier,
                extractors=(), loaded=lrp,
            )
        )
        rulepack_versions.append(f"{platform}@{lrp.version}")

    loaded_cp = load_control_pack(CONTROL_PACK_PATH)
    loaded_cp_m2 = load_control_pack(M2_CONTROL_PACK_PATH)

    return KnowledgeBase(
        schema_registry=schema_registry,
        rulepacks=tuple(rulepacks),
        control_packs=(
            ControlPack(
                id="nsca_native", version=loaded_cp.version,
                control_ids=tuple(c.control_id for c in loaded_cp.controls),
                loaded=loaded_cp,
            ),
            ControlPack(
                id="nsca_native_m2", version=loaded_cp_m2.version,
                control_ids=tuple(c.control_id for c in loaded_cp_m2.controls),
                loaded=loaded_cp_m2,
            ),
        ),
        pin=KnowledgeBasePin(
            engine_version="0.1.0-m2", schema_registry_version="0.1.0",
            rulepack_versions=tuple(sorted(rulepack_versions)),
            control_pack_versions=(
                f"nsca_native@{loaded_cp.version}", f"nsca_native_m2@{loaded_cp_m2.version}",
            ),
        ),
    )


def build_knowledge_base() -> KnowledgeBase:
    schema_registry = SchemaRegistry.load(SCHEMA_DIR)
    loaded_rp = load_rulepack(RULEPACK_PATH)
    loaded_cp = load_control_pack(CONTROL_PACK_PATH)
    return KnowledgeBase(
        schema_registry=schema_registry,
        rulepacks=(
            Rulepack(
                platform="cisco_ios", version=loaded_rp.version,
                trust_tier=loaded_rp.trust_tier, extractors=(), loaded=loaded_rp,
            ),
        ),
        control_packs=(
            ControlPack(
                id="nsca_native", version=loaded_cp.version,
                control_ids=tuple(c.control_id for c in loaded_cp.controls),
                loaded=loaded_cp,
            ),
        ),
        pin=KnowledgeBasePin(
            engine_version="0.1.0-m1", schema_registry_version="0.1.0",
            rulepack_versions=(f"cisco_ios@{loaded_rp.version}",),
            control_pack_versions=(f"nsca_native@{loaded_cp.version}",),
        ),
    )


# ---------------------------------------------------------------------------
# The 05-security-baseline-model.md §9 worked example, reproduced with line
# numbers matching the document exactly: username at line 6, `transport
# input` at line 21, `exec-timeout` at line 22, `snmp-server community` at
# line 24.
# ---------------------------------------------------------------------------

WORKED_EXAMPLE_CONFIG = (
    "!\n"
    "version 15.2\n"
    "service password-encryption\n"
    "hostname CORE-SW-01\n"
    "!\n"
    "username admin privilege 15 password 7 0822455D0A16\n"
    "!\n"
    "aaa new-model\n"
    "aaa authentication login default group tacacs+ local\n"
    "!\n"
    "ip domain-name corp.example.com\n"
    "ip ssh version 2\n"
    "!\n"
    "interface GigabitEthernet0/1\n"
    " description Uplink to Router\n"
    " switchport mode trunk\n"
    " no shutdown\n"
    "!\n"
    "line vty 0 4\n"
    " login local\n"
    " transport input telnet ssh\n"
    " exec-timeout 0 0\n"
    "!\n"
    "snmp-server community public RO\n"
    "!\n"
    "end\n"
)

# A richer, still-Cisco-IOS fixture exercising every extractor in the M1
# rulepack, used to reach a verdict spread across PASS/FAIL/UNKNOWN/
# NOT_APPLICABLE over the >=20-control native pack.
RICH_CONTROLS_CONFIG = (
    "!\n"
    "version 15.2\n"
    "service password-encryption\n"
    "hostname CORE-SW-01\n"
    "!\n"
    "username admin privilege 15 password 7 0822455D0A16\n"
    "!\n"
    "aaa new-model\n"
    "aaa authentication login default group tacacs+ local\n"
    "!\n"
    "ip domain-name corp.example.com\n"
    "ip ssh version 2\n"
    "no ip http server\n"
    "!\n"
    "line vty 0 4\n"
    " login local\n"
    " transport input telnet ssh\n"
    " exec-timeout 0 0\n"
    "!\n"
    "snmp-server community public RO\n"
    "!\n"
    "logging host 10.0.0.200\n"
    "service timestamps log datetime localtime\n"
    "ntp server 10.0.0.201\n"
    "!\n"
    "end\n"
)


def make_artifact(content: str, artifact_id: str = "ART-001"):
    from nsca_engine.api import ArtifactType, RawArtifact

    return RawArtifact(
        id=artifact_id, filename="running-config.txt", content=content.encode("utf-8"),
        artifact_type_hint=ArtifactType.RUNNING_CONFIG, received_from="test",
    )
