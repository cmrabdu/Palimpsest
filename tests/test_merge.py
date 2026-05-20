"""Tests for the document assembler."""

from src.merge import merge_pages_latex, _titlepage, PALIMPSEST_URL


def test_merge_includes_titlepage():
    doc = merge_pages_latex(
        ["\\section{Intro}\nbody"],
        title="Statique",
        subtitle="Mécanique",
        author="Prof. X",
    )
    assert "\\begin{titlepage}" in doc
    assert "Statique" in doc
    assert "Mécanique" in doc
    assert "Prof. X" in doc
    assert "Palimpsest" in doc
    assert PALIMPSEST_URL in doc


def test_merge_blurb_can_be_disabled():
    doc = merge_pages_latex(
        ["body"],
        title="Test",
        include_blurb=False,
    )
    assert "open-source tool combining OCR" not in doc
    assert "\\begin{titlepage}" in doc  # titlepage still rendered


def test_merge_renders_each_page():
    pages = ["\\section{A}\nfirst", "\\section{B}\nsecond", ""]
    doc = merge_pages_latex(pages, title="T")
    assert "\\section{A}" in doc
    assert "\\section{B}" in doc
    # empty pages are skipped silently
    assert doc.count("\\section{") == 2


def test_merge_escapes_special_chars_in_title():
    doc = merge_pages_latex(["body"], title="Statique & Cinematique", author="A_B")
    # Specials must be escaped where they end up rendered
    assert "Statique \\& Cinematique" in doc
    assert "A\\_B" in doc


def test_merge_falls_back_to_default_title():
    doc = merge_pages_latex(["body"], title="")
    assert "\\title{Document}" in doc


def test_titlepage_omits_author_when_empty():
    page = _titlepage("Title", "", "", include_blurb=False)
    # The author line is conditional on a non-empty author
    assert "{\\large " not in page  # no author block rendered


def test_titlepage_includes_subtitle():
    page = _titlepage("Title", "Subtitle here", "", include_blurb=False)
    assert "Subtitle here" in page


def test_end_document_present():
    doc = merge_pages_latex(["body"], title="T")
    assert "\\end{document}" in doc
    # And only once
    assert doc.count("\\end{document}") == 1
