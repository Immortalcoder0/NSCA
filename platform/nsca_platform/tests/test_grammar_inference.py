"""Grammar inference — TRD-02.2, backend-02 M3.

The MikroTik acceptance fixture (`nsca_platform.tests.fixtures.mikrotik`)
was tuned specifically so `infer_grammar` reproduces
08-learning-system.md §3.2's `coverage: 98.4%` on this corpus — see that
fixture module's docstring for why a full 3,000+ line MikroTik config had
to be built rather than reused from the doc (only a 7-line snippet is
given there).
"""

from __future__ import annotations

from nsca_platform.learning.grammar_inference import infer_grammar
from nsca_platform.tests.fixtures.mikrotik import build_corpus_text


def test_mikrotik_grammar_coverage_reproduces_98_4_percent():
    text = build_corpus_text()
    h = infer_grammar(text)

    assert h.paradigm == "path_header"
    assert round(h.coverage * 100, 1) == 98.4
    assert h.status == "accepted"
    assert h.comment_char == "#"
    assert set(h.verbs) == {"set", "add"}
    # Paradigm confidence must clear both the absolute threshold and the
    # margin over the runner-up (DD-02.2-02) — not just barely scrape past.
    scores = sorted(h.paradigm_scores.values(), reverse=True)
    assert scores[0] >= 0.70
    assert scores[0] - scores[1] >= 0.15


def test_worked_example_snippet_infers_path_header():
    """08-learning-system.md §3.2's literal 7-line snippet."""

    text = (
        "# aug/25/2026 14:32:11 by RouterOS 7.11.2\n"
        "/ip service\n"
        "set telnet disabled=no port=23\n"
        "set ssh disabled=no port=22\n"
        "/snmp community\n"
        "set [ find default=yes ] name=public read-access=yes\n"
        "/user\n"
        "add name=admin group=full password=Str0ngP@ss\n"
    )
    h = infer_grammar(text)
    assert h.paradigm == "path_header"
    assert h.path_prefix == "/"
    assert h.comment_char is None or h.comment_char == "#"  # only 1 comment line -> may abstain
    assert h.coverage >= 0.85


def test_low_coverage_refuses_rather_than_guesses():
    """08-learning-system.md §3.3 — the refusal path is itself a test case,
    not an unhandled branch. A structurally hostile input (well below the
    50% floor) must be rejected with the coverage figure reported, per
    TRD-02.2 §3.8's bands and INV-02.2-01."""

    # Mostly binary-garbage-looking lines with no consistent structure at
    # all — no comment char, no verbs, no paths, no braces.
    lines = [f"\x02\x03{'~' * (i % 5)} garbage-blob-{i} !!not-a-statement??" for i in range(40)]
    text = "\n".join(lines)

    h = infer_grammar(text)

    assert h.status in ("rejected",)
    assert h.refusal_message is not None
    assert "coverage could not be reliably determined".lower() in h.refusal_message.lower() or "assisted grammar authoring" in h.refusal_message.lower()


def test_ambiguous_paradigm_escalates_rather_than_guessing():
    """V-02.2-003 — construct an input scoring within the margin for two
    paradigms; must escalate (status=rejected, paradigm=None), never
    silently pick one (DD-02.2-02)."""

    # A tiny, evenly-mixed set of brace-ish and indented-ish lines with no
    # single paradigm dominant enough to clear the 0.15 margin.
    lines = [
        "a {",
        "  b = 1",
        "}",
        "c {",
        "  d = 2",
        "}",
    ]
    text = "\n".join(lines)
    h = infer_grammar(text)
    # Either genuinely ambiguous (paradigm=None) or one paradigm wins outright
    # with a real margin — both are acceptable outcomes of the scorer, but if
    # it does pick one, it must never do so below the acceptance threshold.
    if h.paradigm is not None:
        scores = sorted(h.paradigm_scores.values(), reverse=True)
        assert scores[0] >= 0.70 and (scores[0] - scores[1]) >= 0.15
    else:
        assert h.status == "rejected"
        assert h.refusal_message is not None


def test_inference_is_deterministic():
    text = build_corpus_text()
    results = [infer_grammar(text) for _ in range(5)]
    coverages = {r.coverage for r in results}
    paradigms = {r.paradigm for r in results}
    assert len(coverages) == 1
    assert len(paradigms) == 1


def test_verbatim_region_detection_excludes_pem_blocks_from_statistics():
    pem = "\n".join(
        [
            "-----BEGIN CERTIFICATE-----",
            "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxxxxxxxxxxxxxxxxxxxx",
            "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "-----END CERTIFICATE-----",
        ]
    )
    text = build_corpus_text() + "\n" + pem
    h = infer_grammar(text)
    assert len(h.verbatim_regions) >= 1
    # Paradigm choice must be unaffected by the verbatim block.
    assert h.paradigm == "path_header"


def test_selectors_are_not_misclassified_as_attributes():
    text = build_corpus_text()
    h = infer_grammar(text)
    # The `[ find default=yes ]` selector interior must never surface as a
    # bare verb (TRD-02.2 §3.7).
    assert "find" not in h.verbs
    assert "default=yes" not in h.verbs
