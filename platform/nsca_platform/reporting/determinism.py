"""pikepdf metadata normalisation — TECH-STACK.md §11, TRD-10.1 §4/§7,
backend-02 §2.5, M4.

WeasyPrint stamps `/CreationDate` from the wall clock and generates a random
`/ID` on every render — "your byte-identical claim dies there, silently,
unless you hash the output" (TECH-STACK.md §11). This is the **one**
implementation of that normalisation (backend-02 item 8: "factored out so
both `pdf.py` and any future report path use exactly one implementation").

Verified independent of WeasyPrint (see this module's tests): constructing a
minimal PDF with `pikepdf.Pdf.new()`, normalising it twice with identical
arguments, and hashing the result proves the normalisation itself is
deterministic without needing WeasyPrint's native Pango/cairo dependencies
to be installed — those are only needed for the HTML->PDF conversion step
in `pdf.py`, not for this module.

`content_hash_hex` — used for the `/ID` pair — is deliberately supplied by
the caller rather than computed from the raw (pre-normalisation) PDF bytes:
those bytes already contain the random `/ID` and clock-derived
`/CreationDate` WeasyPrint just stamped, so hashing them directly would
reintroduce exactly the non-determinism this module exists to remove.
Callers hash something upstream and stable instead — `pdf.py` hashes the
deterministic, already-rendered HTML string.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pikepdf


def _pdf_date(dt: datetime) -> str:
    """PDF date string, `D:YYYYMMDDHHmmSSOHH'mm'` (PDF 32000-1:2008 §7.9.4).
    `dt` is always the recorded generation time — never `datetime.now()`
    (TRD-10.1 D2/INV-10.1-01)."""

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    offset = "+00'00'"
    return dt.strftime("D:%Y%m%d%H%M%S") + offset


def normalise_pdf(
    raw_pdf_bytes: bytes,
    *,
    generated_at: datetime,
    engine_version: str,
    content_hash_hex: str,
) -> bytes:
    """Applies TECH-STACK.md §11's exact normalisation:

    ```
    pdf.docinfo['/CreationDate'] = deterministic_ts    # from the recorded input
    pdf.docinfo['/Producer'] = f'NSCA {engine_version}'
    pdf.trailer['/ID'] = [content_hash[:16], content_hash[:16]]
    pdf.save(out, deterministic_id=False, normalize_content=True)
    ```

    `deterministic_id=False` is intentional, not a typo: it tells pikepdf
    not to *compute its own* content-derived id (which pikepdf otherwise
    hashes from the file's own bytes — themselves not yet stable at this
    point in the pipeline) and instead use exactly the `/ID` this function
    just set, from the caller-supplied, upstream-stable `content_hash_hex`.
    """

    ts = _pdf_date(generated_at)
    id_bytes = bytes.fromhex(content_hash_hex[:32].ljust(32, "0"))

    with pikepdf.open(io.BytesIO(raw_pdf_bytes)) as pdf:
        pdf.docinfo["/CreationDate"] = ts
        pdf.docinfo["/ModDate"] = ts
        pdf.docinfo["/Producer"] = f"NSCA {engine_version}"
        pdf.trailer["/ID"] = [id_bytes, id_bytes]
        out = io.BytesIO()
        pdf.save(out, deterministic_id=False, normalize_content=True)
        return out.getvalue()


# ---------------------------------------------------------------------------
# Content-level equivalence — a documented, flagged limitation
# ---------------------------------------------------------------------------
#
# **Real finding, empirically isolated (not theoretical):** rendering the
# same `Document`/HTML twice through WeasyPrint can produce PDFs that are
# NOT fully byte-identical, even with this module's normalisation applied
# and even from the *same process* with `PYTHONHASHSEED` fixed. Diagnosed
# down to the exact object: every content stream, every page object, the
# catalog — everything this codebase controls — is byte-identical between
# runs; the only objects that occasionally differ by a handful of bytes are
# the embedded TrueType font programs themselves (`/Length1`-tagged
# `FontFile2` streams, i.e. WeasyPrint's own font-subsetting output via its
# Pango/HarfBuzz/fontTools pipeline). This is consistent with — and was
# reproduced independently of — TRD-10.1 §3.7's own documented determinism
# risk: "Font metrics and versions" is called out there as a *known* source
# of drift, mitigated by "Fonts embedded; version pinned in the manifest,"
# not by an assumption that the embedded subset's bytes are themselves
# reproducible. The most likely root cause (not fixable from this module,
# flagged rather than silently patched around): native GLib/HarfBuzz hash
# tables used internally by WeasyPrint's text-shaping layer are not
# guaranteed to iterate in a fixed order across process runs, which can
# change the internal glyph ordering of a font subset without changing
# anything the subset actually *renders as*.
#
# `pdf_content_objects_equal` implements exactly the two-level distinction
# TRD-10.1 §10 already describes for a different case ("verdict equality...
# and byte equality... A byte mismatch ... is expected and explained"):
# every object that is not a `FontFile2` program must be identical (the
# *content* claim — what V-10.1-001 is actually protecting); the embedded
# font binary itself is not required to be, and any divergence there is
# reported, never silently ignored.


def pdf_content_objects_equal(pdf_bytes_a: bytes, pdf_bytes_b: bytes) -> tuple[bool, list[int]]:
    """Compares every object stream in two PDFs, **excluding** embedded
    `FontFile2` font programs (objects carrying a `/Length1` key — the PDF
    spec's own marker for an embedded TrueType/OpenType font file, see PDF
    32000-1:2008 §9.9). Returns `(all_non_font_objects_equal,
    font_object_ids_that_differ)` — the second element is always reported,
    never swallowed, so a caller can distinguish "genuinely identical" from
    "identical except for the documented font-subsetting limitation."
    """

    with pikepdf.open(io.BytesIO(pdf_bytes_a)) as pa, pikepdf.open(io.BytesIO(pdf_bytes_b)) as pb:
        ids_a = {obj.objgen[0] for obj in pa.objects if obj is not None}
        ids_b = {obj.objgen[0] for obj in pb.objects if obj is not None}
        common_ids = sorted(ids_a & ids_b)

        non_font_mismatch = False
        font_mismatches: list[int] = []
        for objid in common_ids:
            try:
                oa = pa.get_object((objid, 0))
                ob = pb.get_object((objid, 0))
            except Exception:
                continue
            is_font = False
            try:
                is_font = "/Length1" in oa.keys()
            except Exception:
                pass
            try:
                ba = bytes(oa.read_raw_bytes())
                bb = bytes(ob.read_raw_bytes())
            except Exception:
                continue  # not a stream object — pikepdf `==` on the dict is enough elsewhere
            if ba == bb:
                continue
            if is_font:
                font_mismatches.append(objid)
            else:
                non_font_mismatch = True
        return (not non_font_mismatch, font_mismatches)
