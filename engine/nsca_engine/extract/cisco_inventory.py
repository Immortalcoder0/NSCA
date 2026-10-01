"""Cisco IOS chassis-serial extraction from `show inventory`/`show version`
command output (05-security-baseline-model.md §4.1's `device.serials[]`,
FR-RPT-002/003, FR-ING-010).

**Why this is a separate module, not another declarative rulepack
extractor.** `show inventory`/`show version` output is command output, not
Cisco IOS *configuration* syntax — it has no `hostname`/`interface`/`!`
structure at all, so it cannot be fed through `parse/paradigms/indentation.py`
(the paradigm every Cisco IOS *config* artifact goes through) or through
`extract/runtime.py`'s declarative extractor DSL, which is built to walk a
`ParseTree` produced by that paradigm. This mirrors the precedent already set
by `extract/cisco_acl.py` (a small, code-based, platform-specific extractor
that walks its own input directly rather than forcing a mismatched grammar
onto it) — same reasoning, different input shape: line-oriented regex over
raw text rather than tree-walking.

Two real, distinct Cisco IOS output formats are handled, both regex-parsed
against actual text (never fabricated):

1. **`show inventory`** — the authoritative, multi-entry format. Repeating
   pairs of a `NAME: "...", DESCR: "..."` header line followed by a
   `PID: ..., VID: ..., SN: ...` line, one pair per physical component
   (chassis, line cards, power supplies, transceivers, ...):

   ```
   NAME: "1", DESCR: "WS-C3850-24T-E"
   PID: WS-C3850-24T-E   , VID: V04  , SN: FCW2140L0GH

   NAME: "StackPort1", DESCR: "StackPort1"
   PID: STACK-T1-50CM    , VID: V01  , SN: FOC2138Y0K2
   ```

2. **`show version`** — carries only the chassis serial, on a single
   `Processor board ID <serial>` line, no per-component breakdown. Used as a
   fallback only when no `show inventory` artifact was supplied for this
   device (inventory, when present, is authoritative and more granular).

Both artifact-type detection (`looks_like_*`) and extraction here are
content-sniffing based, deliberately: `RawArtifact.artifact_type_hint` is
frequently `None` in practice (Backend Track B's ingestion path does not
reliably classify/store `artifact_type` for every upload outcome — flagged
separately), so `assess_device` (api.py) tries the hint first and falls back
to sniffing the actual text, never guessing platform from the filename.

Scope, flagged rather than silently narrowed: Cisco IOS only. Other
platforms' equivalent commands (`show chassis hardware` on Junos, `get
system status` on FortiOS, ...) are not implemented here — a real, separate
extractor per platform, not attempted this milestone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from nsca_engine.types import DeviceSerial, Fact, Provenance, ProvenanceSource

_EXTRACTOR_INVENTORY = "cisco_ios.show_inventory.serial@v1"
_EXTRACTOR_VERSION = "cisco_ios.show_version.serial@v1"

# Tolerant of the real-world whitespace variance around the commas (some
# `show inventory` exports pad PID/VID with trailing spaces to align
# columns — the sample in the task/report reproduces this exactly).
# `re.MULTILINE` so `looks_like_*`'s whole-text `.search()` anchors `^`/`$`
# to each line, not just the start/end of the entire artifact — the
# per-line `extract_*` functions below match single-line strings either
# way, so this flag is a no-op for them.
_NAME_DESCR = re.compile(
    r'^NAME:\s*"(?P<name>[^"]*)"\s*,\s*DESCR:\s*"(?P<descr>[^"]*)"\s*$', re.MULTILINE
)
_PID_VID_SN = re.compile(
    r"^PID:\s*(?P<pid>\S*)\s*,\s*VID:\s*(?P<vid>\S*)\s*,\s*SN:\s*(?P<sn>\S+)\s*$", re.MULTILINE
)
_PROCESSOR_BOARD_ID = re.compile(r"^Processor board ID\s+(?P<sn>\S+)\s*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class InventoryExtraction:
    """Both output shapes `assess_device` needs: `DeviceSerial` pairs for
    `FingerprintResult.serials` (05-security-baseline-model.md §4.1's
    `{component, serial}` shape) and real `Fact`s (`device.serials[i].*`)
    carrying genuine per-entry provenance, for evidence citation
    (14-data-model.md §2 EVIDENCE entity) exactly like any other extracted
    fact."""

    serials: tuple[DeviceSerial, ...]
    facts: tuple[Fact, ...]


_EMPTY = InventoryExtraction(serials=(), facts=())


def looks_like_show_inventory(text: str) -> bool:
    """True only when both halves of at least one real NAME/DESCR + PID/VID/
    SN pair are present — a bare `SN:` mention elsewhere (e.g. inside a
    banner) is not enough to misclassify an artifact."""

    return bool(_NAME_DESCR.search(text)) and bool(_PID_VID_SN.search(text))


def looks_like_show_version(text: str) -> bool:
    lower = text.lower()
    return (
        "processor board id" in lower
        or "cisco ios software" in lower
        or "cisco ios-xe software" in lower
        or ("uptime is" in lower and "bytes of" in lower)
    )


def extract_show_inventory(text: str, artifact_id: str) -> InventoryExtraction:
    """Real line-by-line regex parse of `show inventory` text. A `NAME:`/
    `DESCR:` header is paired with the next `PID:`/`VID:`/`SN:` line that
    follows it (blank lines between them are tolerated, matching real
    `show inventory` formatting which separates entries with a blank line).
    A header with no following SN line — a real but serial-less slot, or a
    malformed/truncated capture — contributes no serial rather than a
    fabricated one (G2: never invent evidence that doesn't exist)."""

    lines = text.split("\n")
    serials: list[DeviceSerial] = []
    facts: list[Fact] = []
    idx = 0
    pending_name: str | None = None
    pending_descr: str | None = None
    pending_line: int | None = None

    for lineno, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped:
            continue

        m_name = _NAME_DESCR.match(stripped)
        if m_name:
            pending_name = m_name.group("name")
            pending_descr = m_name.group("descr")
            pending_line = lineno
            continue

        m_sn = _PID_VID_SN.match(stripped)
        if m_sn and pending_line is not None:
            sn = m_sn.group("sn")
            component = pending_descr or pending_name or f"component_{idx}"
            excerpt = f'NAME: "{pending_name}", DESCR: "{pending_descr}"\n{stripped}'
            lines_span = (
                (pending_line, lineno) if lineno != pending_line else (pending_line,)
            )
            serials.append(DeviceSerial(component=component, serial=sn))
            provenance = Provenance(
                source=ProvenanceSource.EXPLICIT,
                artifact_id=artifact_id,
                lines=lines_span,
                excerpt=excerpt,
                extractor=_EXTRACTOR_INVENTORY,
            )
            facts.append(
                Fact(
                    path=f"device.serials[{idx}].component", value=component,
                    type="string", provenance=provenance,
                )
            )
            facts.append(
                Fact(
                    path=f"device.serials[{idx}].serial", value=sn,
                    type="string", provenance=provenance,
                )
            )
            idx += 1
            pending_name = pending_descr = pending_line = None

    return InventoryExtraction(serials=tuple(serials), facts=tuple(facts))


def extract_show_version_serial(text: str, artifact_id: str) -> InventoryExtraction:
    """Fallback chassis-only serial from `show version`'s `Processor board
    ID <serial>` line — used only when no `show inventory` artifact exists
    for this device (see module docstring). Returns the empty extraction,
    never a guess, when the line isn't present."""

    for lineno, raw in enumerate(text.split("\n"), start=1):
        stripped = raw.strip()
        m = _PROCESSOR_BOARD_ID.match(stripped)
        if m:
            sn = m.group("sn")
            component = "Chassis"
            provenance = Provenance(
                source=ProvenanceSource.EXPLICIT,
                artifact_id=artifact_id,
                lines=(lineno,),
                excerpt=stripped,
                extractor=_EXTRACTOR_VERSION,
            )
            return InventoryExtraction(
                serials=(DeviceSerial(component=component, serial=sn),),
                facts=(
                    Fact(
                        path="device.serials[0].component", value=component,
                        type="string", provenance=provenance,
                    ),
                    Fact(
                        path="device.serials[0].serial", value=sn,
                        type="string", provenance=provenance,
                    ),
                ),
            )
    return _EMPTY
