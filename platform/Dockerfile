# Phase 0 (M0) scaffold image. Not yet optimised for the offline/air-gapped
# vendored-wheel policy in TECH-STACK.md §15/§18 — that hardening (vendoring
# wheels into the image, pinned lockfile) is a Phase 1+ concern once
# dependencies stop churning.
FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg (binary wheel used, but libpq headers still help
# in dev images) — kept minimal at M0. M4 adds WeasyPrint's native
# Pango/cairo/GDK-pixbuf/GObject dependency (TECH-STACK.md §11: "Fine in a
# container; pinned in the image" — this is that pinning). Without these,
# `import weasyprint` raises OSError at PDF-generation time (confirmed on a
# bare host with none of this installed — see reporting/pdf.py's
# `weasyprint_available()` probe and the M4 report's determinism-test notes).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY nsca_platform ./nsca_platform
COPY alembic.ini ./

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "nsca_platform.main:app", "--host", "0.0.0.0", "--port", "8000"]
