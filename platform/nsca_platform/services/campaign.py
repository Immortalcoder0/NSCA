"""Campaign state machine (FR-CMP-005) and scope resolution — backend-02 §4.

Response dict shapes match what `api/campaigns.py`'s M0 stub already
returned (`id`, `name`, `status`, `scope`, `frameworks`, `owner`, `window`,
`knowledge_pin`) — 15-api-specification.md §2 shows a literal *request*
body for `POST /campaigns` but no literal response body, so the M0 stub's
fabricated response shape is what Frontend Track 1 built against
(backend-02 M1 task instructions: "Keep the response JSON shapes
byte-identical ... only the data source changes"). Internally the DB
column is `state` (matching 14-data-model.md's field name); the API
response key stays `status` to avoid a breaking frontend change.

Every state-changing function here writes its audit log entry in the same
transaction as the state change (backend-02 §2.3) via `audit.log.record`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from nsca_platform.audit import log as audit_log
from nsca_platform.db.models.artifact import artifact as artifact_table
from nsca_platform.db.models.campaign import campaign as campaign_table
from nsca_platform.db.models.device import device as device_table
from nsca_platform.services import knowledge_service
from nsca_platform.services.scope_filter import ScopeExpressionError
from nsca_platform.services.scope_filter import evaluate as evaluate_scope

STATE_ORDER = ["Draft", "Collecting", "Assessing", "Review", "Issued", "Closed"]

# Transitions reachable from each state via the dedicated endpoints
# (`scope/resolve` moves Draft -> Collecting implicitly once a scope
# exists; `issue` moves ... -> Issued; `close` moves Issued -> Closed).
# FR-CMP-005's chain is otherwise linear and forward-only.
_ISSUABLE_FROM = {"Draft", "Collecting", "Assessing", "Review"}


class CampaignStateError(Exception):
    """Raised on an invalid state transition (409 at the API layer)."""


class CampaignNotFound(Exception):
    pass


class UnknownFrameworkError(Exception):
    """Raised when a campaign requests a framework family that is neither
    one of the documented, recognised families (`cis`/`nist`/`stig`/`iso`,
    06-controls-and-frameworks.md §5) nor anything actually imported into
    `framework_item` (422 at the API layer). Phase 3 demo-rehearsal Bug 4:
    `POST /campaigns` previously accepted any string here — a genuinely
    made-up framework name (e.g. "totally_fake_framework_xyz") was
    accepted unconditionally, with zero cross-check against a real
    catalog."""


def _validate_frameworks(conn: Connection, frameworks: list[Any]) -> None:
    if not frameworks:
        return
    known = knowledge_service.known_framework_families(conn)
    for entry in frameworks:
        family = (entry or {}).get("framework") if isinstance(entry, dict) else entry
        if not family or str(family).strip().lower() not in known:
            raise UnknownFrameworkError(
                f"unknown framework family {family!r} — known families: {', '.join(sorted(known))}"
            )


def _next_public_id(conn: Connection, window_start: datetime | None) -> str:
    year = (window_start or datetime.now(UTC)).year
    quarter = ((window_start or datetime.now(UTC)).month - 1) // 3 + 1
    prefix = f"CMP-{year}Q{quarter}"
    existing = conn.execute(
        select(campaign_table.c.public_id).where(campaign_table.c.public_id.like(f"{prefix}-%"))
    ).fetchall()
    seq = len(existing) + 1
    return f"{prefix}-{seq:03d}"


def _row_to_response(row: Any) -> dict[str, Any]:
    window: dict[str, Any] = {}
    if row.window_start is not None:
        window["start"] = row.window_start.date().isoformat()
    if row.window_end is not None:
        window["end"] = row.window_end.date().isoformat()

    return {
        "id": row.public_id,
        "name": row.name,
        "status": row.state,
        "scope": row.scope_definition,
        "frameworks": row.frameworks,
        "owner": row.owner,
        "window": window,
        "knowledge_pin": row.knowledge_base_pin or {},
    }


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def create_campaign(conn: Connection, body: dict[str, Any], actor: str) -> dict[str, Any]:
    _validate_frameworks(conn, body.get("frameworks", []))
    window = body.get("window") or {}
    window_start = _parse_date(window.get("start"))
    window_end = _parse_date(window.get("end"))
    public_id = _next_public_id(conn, window_start)
    campaign_id = uuid.uuid4()

    conn.execute(
        campaign_table.insert().values(
            id=campaign_id,
            public_id=public_id,
            name=body["name"],
            scope_definition=body.get("scope", {}),
            frameworks=body.get("frameworks", []),
            owner=body.get("owner", ""),
            window_start=window_start,
            window_end=window_end,
            state="Draft",
            knowledge_base_pin=body.get("knowledge_pin"),
        )
    )
    audit_log.record(
        conn,
        actor=actor,
        action="campaign.create",
        entity_type="campaign",
        entity_id=public_id,
        details={"name": body["name"]},
    )
    return get_campaign(conn, public_id)


def list_campaigns(conn: Connection) -> dict[str, Any]:
    rows = conn.execute(select(campaign_table).order_by(campaign_table.c.created_at)).fetchall()
    return {"items": [_row_to_response(r) for r in rows], "next_cursor": None}


def _get_row(conn: Connection, public_id: str) -> Any:
    row = conn.execute(select(campaign_table).where(campaign_table.c.public_id == public_id)).first()
    if row is None:
        raise CampaignNotFound(public_id)
    return row


def get_campaign(conn: Connection, public_id: str) -> dict[str, Any]:
    return _row_to_response(_get_row(conn, public_id))


def update_campaign(conn: Connection, public_id: str, body: dict[str, Any], actor: str) -> dict[str, Any]:
    row = _get_row(conn, public_id)
    if row.state != "Draft":
        raise CampaignStateError(f"Cannot update campaign in state {row.state!r}; only Draft campaigns are editable")

    values: dict[str, Any] = {"updated_at": datetime.now(UTC)}
    if "name" in body:
        values["name"] = body["name"]
    if "scope" in body:
        values["scope_definition"] = body["scope"]
    if "frameworks" in body:
        _validate_frameworks(conn, body["frameworks"])
        values["frameworks"] = body["frameworks"]
    if "owner" in body:
        values["owner"] = body["owner"]
    if "window" in body:
        window = body["window"] or {}
        values["window_start"] = _parse_date(window.get("start"))
        values["window_end"] = _parse_date(window.get("end"))

    conn.execute(campaign_table.update().where(campaign_table.c.public_id == public_id).values(**values))
    audit_log.record(
        conn,
        actor=actor,
        action="campaign.update",
        entity_type="campaign",
        entity_id=public_id,
        details={"fields": sorted(body.keys())},
    )
    return get_campaign(conn, public_id)


def resolve_scope(conn: Connection, public_id: str, actor: str) -> dict[str, Any]:
    row = _get_row(conn, public_id)
    scope = row.scope_definition or {}
    scope_type = scope.get("type")

    devices: list[dict[str, Any]] = []
    if scope_type == "explicit":
        hostnames = scope.get("devices", [])
        found = conn.execute(select(device_table).where(device_table.c.hostname.in_(hostnames))).fetchall()
        devices = [_device_summary(d) for d in found]
    elif scope_type == "filter":
        expression = scope.get("expression", "")
        # Candidate pool: every device correlated into this campaign so
        # far via ingestion, plus (for a fully general filter) every known
        # device — a real inventory import (FR-CMP-003's "imported asset
        # inventory" reading) is out of M1 scope, so the candidate pool is
        # limited to devices this campaign has actually seen artifacts
        # for. Flagged as a judgment call: a campaign in `Draft` with no
        # artifacts yet will resolve to an empty scope until collection
        # starts, which is a reasonable reading but not the only one.
        candidate_ids = conn.execute(
            select(artifact_table.c.device_id)
            .where(artifact_table.c.campaign_id == row.id)
            .where(artifact_table.c.device_id.isnot(None))
            .distinct()
        ).fetchall()
        ids = [c[0] for c in candidate_ids]
        candidates = conn.execute(select(device_table).where(device_table.c.id.in_(ids))).fetchall() if ids else []
        for d in candidates:
            attrs = {"role": d.role, "platform": d.platform, "exposure": None, "location": d.location}
            try:
                if evaluate_scope(expression, attrs, str(d.id)):
                    devices.append(_device_summary(d))
            except ScopeExpressionError:
                raise
    else:
        raise ScopeExpressionError(f"Unsupported scope type: {scope_type!r}")

    scope_devices = [d["device"] for d in devices]
    new_state = row.state if row.state != "Draft" else "Collecting"
    conn.execute(
        campaign_table.update()
        .where(campaign_table.c.public_id == public_id)
        .values(scope_devices=scope_devices, state=new_state, updated_at=datetime.now(UTC))
    )
    audit_log.record(
        conn,
        actor=actor,
        action="campaign.scope_resolve",
        entity_type="campaign",
        entity_id=public_id,
        details={"device_count": len(devices)},
    )
    return {"campaign_id": public_id, "device_count": len(devices), "devices": devices}


def _device_summary(d: Any) -> dict[str, Any]:
    return {"device": d.hostname, "platform": d.platform, "role": d.role, "exposure": None}


def issue_campaign(conn: Connection, public_id: str, actor: str) -> dict[str, Any]:
    row = _get_row(conn, public_id)
    if row.state not in _ISSUABLE_FROM:
        raise CampaignStateError(f"Cannot issue campaign in state {row.state!r}")
    conn.execute(
        campaign_table.update()
        .where(campaign_table.c.public_id == public_id)
        .values(state="Issued", updated_at=datetime.now(UTC))
    )
    audit_log.record(
        conn, actor=actor, action="campaign.issue", entity_type="campaign", entity_id=public_id, details=None
    )
    return get_campaign(conn, public_id)


def close_campaign(conn: Connection, public_id: str, actor: str) -> dict[str, Any]:
    row = _get_row(conn, public_id)
    if row.state != "Issued":
        raise CampaignStateError(f"Cannot close campaign in state {row.state!r}; must be Issued first")
    conn.execute(
        campaign_table.update()
        .where(campaign_table.c.public_id == public_id)
        .values(state="Closed", updated_at=datetime.now(UTC))
    )
    audit_log.record(
        conn, actor=actor, action="campaign.close", entity_type="campaign", entity_id=public_id, details=None
    )
    return get_campaign(conn, public_id)


def completeness(conn: Connection, public_id: str) -> dict[str, Any]:
    """FR-ING-015/016: collection completeness against campaign scope.

    `in_scope_devices` is `len(scope_devices)` from the last
    `scope/resolve` (0 if scope has never been resolved). `outcomes` tallies
    the four ingestion outcome states (15-api-specification.md §3) over
    every artifact received for this campaign. `not_yet_collected` is
    in-scope hostnames with zero correlated artifacts — FR-ING-016 wants a
    reason/owner per missing device, which needs the finding-lifecycle
    machinery (M2); for M1 the hostname list itself is the real, DB-backed
    part.
    """

    row = _get_row(conn, public_id)
    scope_devices: list[str] = row.scope_devices or []

    artifacts = conn.execute(
        select(artifact_table.c.status, artifact_table.c.device_id).where(artifact_table.c.campaign_id == row.id)
    ).fetchall()

    outcomes = {"parsed": 0, "parsed_with_caveat": 0, "platform_not_taught": 0, "unidentified": 0}
    collected_device_ids: set[str] = set()
    for status, device_id in artifacts:
        if status in outcomes:
            outcomes[status] += 1
        if device_id is not None:
            collected_device_ids.add(str(device_id))

    collected_hostnames: set[str] = set()
    if collected_device_ids:
        rows = conn.execute(
            select(device_table.c.hostname).where(device_table.c.id.in_(collected_device_ids))
        ).fetchall()
        collected_hostnames = {r[0] for r in rows}

    missing = [h for h in scope_devices if h not in collected_hostnames]

    return {
        "campaign_id": public_id,
        "in_scope_devices": len(scope_devices),
        "collected": len(collected_hostnames),
        "outcomes": outcomes,
        "not_yet_collected": len(missing),
        "missing_devices": missing,
    }
