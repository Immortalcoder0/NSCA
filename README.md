# NSCA — AI-Driven Multi-Vendor Network Security Compliance Auditor

SIH26155 · NTRO. See [`docs/00-product-overview.md`](docs/00-product-overview.md)
for the full product rationale, [`ARCHITECTURE.md`](ARCHITECTURE.md) for the
2-page technical architecture, and [`DECK.md`](DECK.md) for the 5-slide
technical presentation.

## What NSCA is

Network devices are computers whose entire behaviour is one text configuration
file, and organisations are required to harden thousands of them against
published benchmarks (CIS, NIST SP 800-53, DISA STIG, ISO/IEC 27001) — but no
single tool can read configuration syntax from every vendor, and every
existing tool requires an engineer and a release cycle to add a new one. NSCA
separates *reading* a configuration (vendor-specific, taught by an
administrator through a GUI in minutes, no code) from *judging* it
(vendor-neutral, written once against a normalised Security Baseline Model).
It ingests single or bulk device configurations — CLI exports, cloud policy
JSON, `show tech` bundles — normalises them, evaluates them against
user-selected frameworks, and produces one audit-grade PDF per device with
serial numbers, evidence line numbers, and version-specific remediation. It
never reports something it could not determine as compliant, and it is
designed to run with zero network connectivity, because its intended
deployment is critical national infrastructure where shipping a router
configuration to an external API is an intelligence loss, not a policy
violation.

## Repository layout

```
nsca/
├── docs/          PRD — product requirements, one file per subsystem
├── trd/           TRD — technical/verification requirements
├── plans/         build plans, one per track, plus the release-gate checklist
├── engine/        Backend Track A — nsca_engine, pure deterministic Python library
│                  (ingest → fingerprint → parse → extract → graph → evaluate → risk)
├── platform/      Backend Track B — nsca_platform, FastAPI app, worker, DB,
│                  learning subsystem, reporting, REST API
├── knowledge/     shared DATA (not code): rulepacks, control packs, schema,
│                  frameworks — YAML, read by both backend tracks
├── frontend/      one React app, built in vertical slices (ingestion/estate,
│                  findings/risk/remediation, training/knowledge/reports/admin)
├── docker-compose.yml   profiles: standard · air-gapped · workstation
└── ARCHITECTURE.md, DECK.md   the two capped deliverables
```

Full rationale for this split (why two backend tracks, why `engine/` never
imports `platform/`) is in [`plans/00-master-plan.md`](plans/00-master-plan.md)
§2–3.

## Standard setup

**Prerequisite:** Docker and Docker Compose, *or* Python 3.11+ and Node 18+
for a manual install.

### Docker Compose (documented path — currently broken, see note)

```bash
docker compose --profile standard up --build
```

This is intended to bring up Postgres, the FastAPI app (`web`), a worker, and
a local Ollama container for the learning subsystem's optional model
refinement. **As verified while writing this README, the build currently
fails**: `platform/Dockerfile` only `COPY`s `nsca_platform`, but
`nsca_platform`'s `pyproject.toml` depends on `nsca_engine`, which is a
workspace-local package (Backend Track A) that is not published to any
package index. `pip install -e .` inside the image therefore fails with
`No matching distribution found for nsca_engine`. This is not a hypothetical
— reproduced directly:

```
ERROR: Could not find a version that satisfies the requirement nsca_engine>=0.0.1 (from nsca-platform)
ERROR: No matching distribution found for nsca_engine>=0.0.1
```

Until `platform/Dockerfile` is fixed to `COPY ../engine` (or the repo grows a
workspace tool per the `pyproject.toml` comment), use the manual install below
for `web`/`worker` and reserve Docker for `db`.

### Manual (currently-working) setup

```bash
# 1. Database (or use `docker compose up db` for just Postgres)
docker compose up -d db

# 2. Engine (Backend Track A) — pure library, install first
cd engine
python -m venv .venv && source .venv/Scripts/activate   # Git Bash on Windows
pip install -e ".[dev]"

# 3. Platform (Backend Track B) — depends on engine by local path
cd ../platform
pip install -e ../engine
pip install -e ".[dev]"
export DATABASE_URL="postgresql+psycopg://nsca:nsca@localhost:5432/nsca"
alembic upgrade head
python -m uvicorn nsca_platform.main:app --reload

# 4. Frontend
cd ../frontend
npm install
npm run dev
```

This exact sequence (steps 2–3, against a real Postgres container) was run
while writing this README and works: `pip install -e ../engine` then
`pip install -e ".[dev]"` succeed, and `import nsca_engine, nsca_platform`
resolves cleanly. See `platform/pyproject.toml`'s own comment block for why
the two-step install is necessary (no workspace tool yet).

Dev auth: every request is a single hardcoded user; send `X-Dev-Role` to pick
one of the 5 RBAC roles. See `platform/README.md`.

## Air-gapped installation

NSCA's assessment path is architecturally air-gapped: `engine/` performs zero
network I/O (enforced by a CI gate that AST-walks the package and fails the
build on any import of a networking primitive), Postgres runs locally, and
the learning subsystem's only optional network dependency — a local Ollama
call for refining a heuristic proposal — is gated behind a reachability probe
that fails closed to heuristic-only operation, and the code explicitly
**refuses** hosted/external inference (`InferenceMode.HOSTED` raises
`PermissionError` unconditionally, citing NFR-DEP-001) rather than silently
allowing it. None of this is a promise about "someday" — it is enforced in
`platform/nsca_platform/learning/candidate_proposal.py` today.

Be precise about what "air-gapped install" means here, because *install* and
*run* are different claims:

- **Runtime is air-gapped.** Once built/installed, nothing in the assessment
  pipeline calls out. `docker-compose.yml`'s `air-gapped` profile
  (`db` + `web` + `worker`, no `inference` container) exists specifically to
  make that structural — the Ollama container simply isn't present, so there
  is nothing to reach even by mistake. `docker compose --profile air-gapped
  config` parses cleanly (verified).
- **Build/install is not air-gapped today, and needs one online pass.**
  Every Python dependency (FastAPI, SQLAlchemy, WeasyPrint, lxml, etc.) is
  fetched from PyPI at `pip install` time; `platform/Dockerfile` also runs
  `apt-get update && apt-get install` for WeasyPrint's native
  Pango/Cairo/GDK-pixbuf libraries. Nothing in this repository vendors
  wheels or an apt mirror. The honest procedure for a genuinely disconnected
  target is: build the Docker images (or populate a `pip download -d
  wheelhouse/` cache and an offline apt mirror) on a connected machine,
  transfer the images/wheelhouse to the air-gapped environment, then run
  entirely offline from there. No such wheelhouse or pre-built image is
  checked into this repo yet — that packaging step is unbuilt, not merely
  undocumented.
- **The Docker build is currently broken regardless of network access**, per
  the note above (`nsca_engine` not resolvable inside the image) — so today,
  "air-gapped install via Docker" cannot be validated end-to-end even with
  connectivity, until that `COPY`/dependency issue is fixed. The manual
  venv install (§ above) does not have this problem, because it installs
  `engine/` from the local path directly, and was verified working in this
  environment.
- **No prior end-to-end boot of the `air-gapped` profile was found recorded
  anywhere in the repo** (`plans/release-gate-checklist.md` covers test
  status, not a deployment boot log). Treat "the air-gapped profile boots
  cleanly" as unverified until someone runs it after fixing the Dockerfile.

## Running tests

```bash
# Engine (Backend Track A) — no database needed
cd engine && PYTHONHASHSEED=0 python -m pytest
# → 248 passed, 2 deselected (perf tests; run with `pytest -m perf`)

# Platform (Backend Track B) — needs DATABASE_URL pointed at a real Postgres
cd platform && DATABASE_URL="postgresql+psycopg://nsca:nsca@localhost:5432/nsca" \
  PYTHONHASHSEED=0 python -m pytest
# → 221 passed, 2 skipped

# Frontend
cd frontend && npm test
# → 93 passed (23 test files)
```

All three counts above were reproduced while writing this README (engine and
frontend from a clean run; platform against a real local Postgres container),
not copied from a prior report.

## Known limitations

Honest, as of 2026-09-01 — see [`plans/release-gate-checklist.md`](plans/release-gate-checklist.md)
for the full 14-criterion breakdown (8 PASS, 5 PARTIAL, 1 explicitly manual
and not yet run).

- **Live collection (Netmiko/NAPALM) is not implemented.** `engine/nsca_engine/collection/`
  is an empty package (just `__init__.py`). The `POST /campaigns/{id}/collect`
  API route exists and types its request body (`mode: Literal["read_only"]`),
  but there is no transport driver behind it yet. Ingestion today is
  file/bulk/archive/cloud-JSON only.
- **PDF generation is unverified on Windows dev hosts.** WeasyPrint requires
  native Pango/Cairo/GDK-pixbuf libraries (GTK stack) that are not installed
  by default on Windows. `reporting/pdf.py` has a `weasyprint_available()`
  probe and tests skip gracefully when it's absent — confirmed on this host,
  where the PDF-bytes stage of the determinism tests is skipped while the
  underlying document-model/HTML/DOCX/JSON/CSV/OSCAL determinism is still
  verified. The Docker image installs the required libraries, but full PDF
  byte-level generation has not been verified end-to-end in this repo (the
  Docker build itself is currently broken — see above).
- **The 200-real-configuration corpus requirement (TRD-00 §8.2: ≥5 platforms,
  ≥3 structural paradigms, ≥60% real production) is unmet.** The current
  corpus (`engine/nsca_engine/tests/corpus/`) has 34 files across 5 known
  platforms plus 2 untaught ones — a documented starting seed, not the
  target. See `corpus/README.md` for full provenance and a known parity bug
  it surfaced: the 4 sampled PAN-OS files are real `set`-format syntax, but
  the current `panos.yaml` rulepack is wired to the `xml` paradigm, so they
  will not parse under today's rulepack/paradigm assignment.
- **Rulepack/control-pack coverage is early-stage, not the target scale.**
  7 rulepacks (one per structural paradigm: indentation, flat-path, brace,
  block-keyword, XML, path-header, cloud JSON) with 43 extractors total, and
  36 controls across two control packs. Earlier planning material referenced
  a target of roughly 200 extractors at full vendor/OS-version maturity —
  that is a target, not where the corpus stands today.
- **Several API endpoints carry stub/TODO markers** across `platform/nsca_platform/api/`
  — not every route is backed by full production logic yet.
- **The B14 onboarding-time criterion (a real administrator, unaided, timed
  to ≥70% coverage) has not been run.** It has no automated oracle by design
  (TRD-11.3 §6.1) and requires a live manual session.
- **`docker-compose.yml`'s `standard`/`air-gapped` profiles do not currently
  build** — see the Docker note above. `workstation` shares the same
  Dockerfile and therefore the same defect.
