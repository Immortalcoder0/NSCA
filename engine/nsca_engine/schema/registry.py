"""The Schema Registry — loads `knowledge/schema/*.yaml` and exposes a
lookup API over fact definitions (TRD-03.3, 05-security-baseline-model.md §7).

This module is the **one allowed disk-I/O point** for schema content in the
whole engine (backend-01 §3: "no runtime dependency may perform I/O except
... schema loading at KnowledgeBase construction time"). The read happens
once, in ``SchemaRegistry.load``, at construction time — never inside
``assess_device``/``assess_campaign``. Everything downstream of construction
is a pure in-memory lookup.

M0 scope: a first-draft loader and validator covering the ten top-level
domains from 05-security-baseline-model.md §4. Registration workflow
(provisional → ratify → active, TRD-03.3 §3.5), naming-gate denylist
(§3.6), algorithm canonicalisation (§3.3), and unaudited-surface detection
(§3.8) are Phase 1 concerns layered on top of this loader — not built here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
import yaml

# ---------------------------------------------------------------------------
# The JSON Schema meta-shape a domain schema *file* (knowledge/schema/*.yaml)
# must conform to. This validates structure, not the semantic naming rules
# from TRD-03.3 §3.6 (vendor-denylist, similarity check) — those require a
# registry-wide view and are Phase 1 work.
# ---------------------------------------------------------------------------

_FACT_TYPES = (
    "boolean",
    "integer",
    "string",
    "enum",
    "cidr",
    "version",
    "algorithm",
    "ref",
    "object",
    # list<T> — open pattern, validated separately below rather than via
    # a fixed enum member per T.
)

_DOMAIN_SCHEMA_FILE_META_SCHEMA: Mapping[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["domain", "schema_version", "fact_definitions"],
    "additionalProperties": False,
    "properties": {
        "domain": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "schema_version": {"type": "string", "minLength": 1},
        "fact_definitions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["path", "type", "category", "description"],
                "additionalProperties": False,
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "type": {"type": "string", "minLength": 1},
                    "category": {"type": "string", "minLength": 1},
                    "description": {"type": "string"},
                    "properties": {
                        "type": "object",
                        "additionalProperties": {"type": "boolean"},
                    },
                    "status": {
                        "type": "string",
                        "enum": ["provisional", "ratified", "active", "deprecated"],
                    },
                    "registered_by": {"type": "string"},
                    "registered_at": {"type": "string"},
                    "introduced_by_platform": {"type": "string"},
                    "closed": {"type": "boolean"},
                    "values": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


@dataclass(frozen=True, slots=True)
class FactDefinition:
    """One registered fact path (TRD-03.3 §3.2). ``properties`` is the
    universal security-property set (05-security-baseline-model.md §6) —
    kept as a plain, sorted-key mapping rather than a dedicated dataclass
    because the property set is deliberately open-ended per-fact metadata,
    not a fixed record every fact populates identically.
    """

    path: str
    type: str
    category: str
    description: str
    domain: str
    status: str = "active"
    properties: Mapping[str, bool] | None = None
    registered_by: str | None = None
    registered_at: str | None = None
    introduced_by_platform: str | None = None
    closed: bool | None = None
    values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.properties is None:
            object.__setattr__(self, "properties", {})


class SchemaRegistryError(ValueError):
    """Raised when a domain schema file fails to load or validate."""


class SchemaRegistry:
    """Loads and indexes every ``knowledge/schema/*.yaml`` domain file.

    Construction is the one place this class touches disk. Every other
    method is a pure lookup over the structures built at construction time.
    """

    def __init__(self, domains: Mapping[str, tuple[FactDefinition, ...]]) -> None:
        # Store domains and the flat path index sorted, so any iteration a
        # caller performs over registry contents is deterministic (D6) even
        # if they iterate the mapping directly.
        self._domains: dict[str, tuple[FactDefinition, ...]] = dict(
            sorted(domains.items())
        )
        by_path: dict[str, FactDefinition] = {}
        for defs in self._domains.values():
            for fd in defs:
                by_path[fd.path] = fd
        self._by_path: dict[str, FactDefinition] = dict(sorted(by_path.items()))

    @classmethod
    def load(cls, schema_dir: str | Path) -> SchemaRegistry:
        """Load every ``*.yaml`` file directly under ``schema_dir``.

        ``schema_dir`` is passed in by the caller (never hardcoded) so the
        engine has zero knowledge of where the repo's ``knowledge/`` tree
        lives — that path belongs to whoever constructs the
        ``KnowledgeBase`` (backend-01 §5.4: Track A reads, never assumes a
        layout beyond "a directory of YAML files").
        """

        schema_dir = Path(schema_dir)
        if not schema_dir.is_dir():
            raise SchemaRegistryError(f"schema directory not found: {schema_dir}")

        domains: dict[str, tuple[FactDefinition, ...]] = {}
        # sorted() makes file-load order deterministic regardless of
        # filesystem enumeration order (D6).
        for file_path in sorted(schema_dir.glob("*.yaml")):
            domain_name, fact_defs = cls._load_file(file_path)
            if domain_name in domains:
                raise SchemaRegistryError(
                    f"domain '{domain_name}' declared in more than one file "
                    f"(duplicate: {file_path})"
                )
            domains[domain_name] = fact_defs

        if not domains:
            raise SchemaRegistryError(f"no schema YAML files found in {schema_dir}")

        return cls(domains)

    @staticmethod
    def _load_file(file_path: Path) -> tuple[str, tuple[FactDefinition, ...]]:
        try:
            raw_text = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SchemaRegistryError(f"could not read {file_path}: {exc}") from exc

        try:
            # safe_load only — this is imported content (TECH-STACK.md §6):
            # arbitrary-code-executing YAML loaders are never acceptable
            # here, even for first-party schema files.
            document = yaml.safe_load(raw_text)
        except yaml.YAMLError as exc:
            raise SchemaRegistryError(f"invalid YAML in {file_path}: {exc}") from exc

        if document is None:
            raise SchemaRegistryError(f"empty schema file: {file_path}")

        try:
            jsonschema.validate(
                instance=document, schema=_DOMAIN_SCHEMA_FILE_META_SCHEMA
            )
        except jsonschema.ValidationError as exc:
            raise SchemaRegistryError(
                f"{file_path} does not conform to the domain schema file shape: "
                f"{exc.message} (at {'/'.join(str(p) for p in exc.absolute_path)})"
            ) from exc

        domain_name = document["domain"]
        fact_defs: list[FactDefinition] = []
        for entry in document["fact_definitions"]:
            fact_type = entry["type"]
            if not (fact_type in _FACT_TYPES or fact_type.startswith("list<")):
                raise SchemaRegistryError(
                    f"{file_path}: fact '{entry['path']}' has unrecognised type "
                    f"'{fact_type}' (expected one of {_FACT_TYPES} or 'list<T>')"
                )
            if not entry["path"].startswith(f"{domain_name}."):
                raise SchemaRegistryError(
                    f"{file_path}: fact path '{entry['path']}' does not start "
                    f"with its declared domain prefix '{domain_name}.' "
                    "(TRD-03.3 §3.6 category-prefix gate)"
                )
            fact_defs.append(
                FactDefinition(
                    path=entry["path"],
                    type=fact_type,
                    category=entry["category"],
                    description=entry.get("description", ""),
                    domain=domain_name,
                    status=entry.get("status", "active"),
                    properties=dict(entry.get("properties", {})),
                    registered_by=entry.get("registered_by"),
                    registered_at=entry.get("registered_at"),
                    introduced_by_platform=entry.get("introduced_by_platform"),
                    closed=entry.get("closed"),
                    values=tuple(entry.get("values", ())),
                )
            )

        # Sort by path so in-domain iteration is deterministic (D6),
        # independent of the order the YAML author happened to write them.
        fact_defs.sort(key=lambda fd: fd.path)
        return domain_name, tuple(fact_defs)

    # -- Lookup API ---------------------------------------------------

    @property
    def domains(self) -> tuple[str, ...]:
        """Sorted tuple of every loaded domain name."""

        return tuple(self._domains.keys())

    def fact_definitions_for_domain(self, domain: str) -> tuple[FactDefinition, ...]:
        return self._domains.get(domain, ())

    def get_fact_definition(self, path: str) -> FactDefinition | None:
        """Resolve a dotted fact path to its registered definition, or
        ``None`` if unregistered.

        Note: real fact *instances* commonly carry array indices
        (``auth.local_users[0].name``) or open-enum segments
        (``mgmt.protocols.winbox.enabled``) that a static registry entry
        represents structurally (``auth.local_users[].name``,
        ``mgmt.protocols.<name>.enabled``). Resolving instantiated paths to
        their template entry is extractor-runtime/TRD-03.1 territory, not
        this M0 loader's job — this method does exact-path lookup only.
        """

        return self._by_path.get(path)

    def __len__(self) -> int:
        return len(self._by_path)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"SchemaRegistry(domains={self.domains!r}, "
            f"fact_count={len(self._by_path)})"
        )
