"""Phase 0 (M0) dev-only auth stand-in.

NOT REAL AUTH. There is exactly one hardcoded dev user. Its role for a given
request is selected by the `X-Dev-Role` request header so that a frontend
developer can exercise every RBAC-gated UI path (FR-ADM-002) without a real
login flow. This module is expected to be deleted wholesale in a later
milestone and replaced by `platform/nsca_platform/auth/` session/token
handling backed by the `admin.user` table — nothing downstream should import
`DevUser` by name outside of route dependencies.

Roles, per 03-functional-requirements.md FR-ADM-002 (verbatim names):
    Assessor, Lead Assessor, Network Administrator, Platform Administrator,
    Read-only
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fastapi import Depends, Header, HTTPException, status


class Role(str, Enum):
    ASSESSOR = "assessor"
    LEAD_ASSESSOR = "lead_assessor"
    NETWORK_ADMINISTRATOR = "network_administrator"
    PLATFORM_ADMINISTRATOR = "platform_administrator"
    READ_ONLY = "read_only"


# Display names exactly as FR-ADM-002 spells them, for API responses
# (e.g. GET /admin/roles) where the literal product wording matters.
ROLE_DISPLAY_NAMES: dict[Role, str] = {
    Role.ASSESSOR: "Assessor",
    Role.LEAD_ASSESSOR: "Lead Assessor",
    Role.NETWORK_ADMINISTRATOR: "Network Administrator",
    Role.PLATFORM_ADMINISTRATOR: "Platform Administrator",
    Role.READ_ONLY: "Read-only",
}

# Default role when the header is omitted. Chosen as the highest-privilege
# assessment role (rather than platform_administrator) so that most journeys
# in 02-personas-and-journeys.md work out of the box; a frontend dev must
# opt in to platform_administrator/network_administrator/read_only explicitly
# to exercise those narrower paths.
DEFAULT_DEV_ROLE = Role.LEAD_ASSESSOR

DEV_USER_ID = "dev-user-0001"
DEV_USER_NAME = "Dev User"
DEV_USER_EMAIL = "dev-user@example.invalid"


@dataclass(frozen=True, slots=True)
class DevUser:
    id: str
    name: str
    email: str
    role: Role

    @property
    def role_display(self) -> str:
        return ROLE_DISPLAY_NAMES[self.role]


def get_current_user(
    x_dev_role: str | None = Header(default=None, alias="X-Dev-Role"),
) -> DevUser:
    """FastAPI dependency injecting the single dev user, role-switched by header.

    Route handlers depend on this instead of any real session mechanism.
    Swapping this dependency for a real one in a later milestone should not
    require changing any route signature beyond the `Depends(...)` target.
    """
    if x_dev_role is None:
        role = DEFAULT_DEV_ROLE
    else:
        try:
            role = Role(x_dev_role.strip().lower())
        except ValueError as exc:
            valid = ", ".join(r.value for r in Role)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown X-Dev-Role '{x_dev_role}'. Valid values: {valid}",
            ) from exc

    return DevUser(id=DEV_USER_ID, name=DEV_USER_NAME, email=DEV_USER_EMAIL, role=role)


def require_role(*allowed: Role):
    """Dependency factory for role-gated endpoints (e.g. campaign issue,
    accept-risk — both Lead Assessor only per 15-api-specification.md §2/§5).
    """

    def _dependency(user: DevUser = Depends(get_current_user)) -> DevUser:
        if user.role not in allowed:
            allowed_names = ", ".join(ROLE_DISPLAY_NAMES[r] for r in allowed)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "insufficient_role",
                    "message": f"Requires one of: {allowed_names}",
                    "detail": f"Current dev role: {user.role_display}",
                    "remediation": "Set the X-Dev-Role header to an allowed role.",
                },
            )
        return user

    return _dependency
