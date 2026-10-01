# nsca_platform — Backend Track B

Phase 0 (M0) scaffold only. See `../nsca/plans/backend-02-platform-learning-reporting-api.md`.

## Dev quickstart

```bash
cd platform
python -m venv .venv
. .venv/Scripts/activate   # Windows Git Bash: source .venv/Scripts/activate
pip install -e ".[dev]"
python -m uvicorn nsca_platform.main:app --reload
```

OpenAPI schema: `http://127.0.0.1:8000/api/v1/openapi.json`

## Dev auth

Every request is treated as authenticated as a single hardcoded dev user.
Send the header `X-Dev-Role` to switch which of the 5 RBAC roles
(FR-ADM-002) that user is acting as for the request:

```
X-Dev-Role: assessor | lead_assessor | network_administrator | platform_administrator | read_only
```

Defaults to `lead_assessor` if the header is absent, so unauthenticated
frontend dev traffic sees the highest-privilege stub behaviour by default.
This is explicitly not real authentication — see `nsca_platform/auth/dev_auth.py`.

## Tests

```bash
pytest
```
