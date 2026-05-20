"""Tests for the LaTeX sanitizer post-pass.

Run with:  python -m pytest tests/ -v
"""

from src.sanitize import sanitize_latex, sanitize_title, slugify


# ── Fence stripping ─────────────────────────────────────

def test_strips_leading_latex_fence():
    body = "```latex\n\\section{Foo}\nhello\n```"
    out, notes = sanitize_latex(body)
    assert "```" not in out
    assert "\\section{Foo}" in out
    assert "stripped markdown fences" in notes


def test_strips_bare_fence():
    body = "```\n\\section{Foo}\n```"
    out, _ = sanitize_latex(body)
    assert "```" not in out


# ── Banned physics-package macros ───────────────────────

def test_neuters_dv_pdv_qty():
    body = "\\dv{x}{t} et \\pdv{u}{x} et \\qty{5}{m}"
    out, notes = sanitize_latex(body)
    assert "\\dv{" not in out.replace("% [palimpsest:banned-cmd] \\dv{", "")
    assert "[palimpsest:banned-cmd]" in out
    assert "commented banned physics-package macros" in notes


def test_does_not_neuter_abs_norm():
    # \abs and \norm are declared in the preamble — keep them
    body = "\\abs{x} et \\norm{v}"
    out, _ = sanitize_latex(body)
    assert "\\abs{x}" in out
    assert "\\norm{v}" in out


# ── Paragraph environment misuse ────────────────────────

def test_paragraph_env_becomes_command():
    body = "\\begin{paragraph}{Intro}\nle texte ici.\n\\end{paragraph}"
    out, notes = sanitize_latex(body)
    assert "\\paragraph{Intro}" in out
    assert "\\begin{paragraph}" not in out
    assert "converted paragraph environment to command" in notes


# ── Section number stripping ────────────────────────────

def test_strips_multi_level_numbers():
    out, _ = sanitize_latex("\\section{3.4 Le solide}")
    assert out == "\\section{Le solide}"


def test_strips_single_number_dot():
    out, _ = sanitize_latex("\\section{4. Tableaux}")
    assert out == "\\section{Tableaux}"


def test_strips_roman():
    out, _ = sanitize_latex("\\subsection{II. Cas pratique}")
    assert out == "\\subsection{Cas pratique}"


def test_preserves_titles_with_numbers_not_at_start():
    out, _ = sanitize_latex("\\section{Loi de Mariotte}")
    assert out == "\\section{Loi de Mariotte}"


def test_preserves_number_units_in_title():
    out, _ = sanitize_latex("\\section{1 atm de pression}")
    assert out == "\\section{1 atm de pression}"


# ── Display math ────────────────────────────────────────

def test_double_dollar_becomes_bracket():
    out, _ = sanitize_latex("inline $x$ and $$y = mx + b$$ done")
    assert "$$" not in out
    assert "\\[ y = mx + b \\]" in out


# ── Bare dash lists ─────────────────────────────────────

def test_bare_dash_becomes_bullet():
    body = "- premier\n- deuxième\n- troisième"
    out, _ = sanitize_latex(body)
    assert "- premier" not in out
    assert "$\\bullet$" in out


# ── TikZ removal ────────────────────────────────────────

def test_orphan_tikzpicture_replaced():
    body = "before \\begin{tikzpicture}\\draw(0,0)--(1,1);\\end{tikzpicture} after"
    out, notes = sanitize_latex(body)
    assert "tikzpicture" not in out
    assert "schéma TikZ retiré" in out
    assert "replaced inline tikzpicture with fbox placeholder" in notes


# ── Dollar balance ──────────────────────────────────────

def test_appends_closing_dollar_when_odd():
    body = "Une équation $x = 1 sans fermer"
    out, notes = sanitize_latex(body)
    assert out.endswith("$")
    assert "appended trailing $ to balance inline math" in notes


def test_even_dollars_left_alone():
    body = "Une équation $x = 1$ propre"
    out, notes = sanitize_latex(body)
    assert out == body
    assert "appended trailing $" not in " ".join(notes)


# ── Title escaping ──────────────────────────────────────

def test_sanitize_title_escapes_specials():
    assert sanitize_title("a & b") == "a \\& b"
    assert sanitize_title("100%") == "100\\%"
    assert sanitize_title("file_name") == "file\\_name"
    assert sanitize_title("$cash") == "\\$cash"
    assert sanitize_title("a#1") == "a\\#1"
    assert sanitize_title("a~b^c") == "a\\textasciitilde{}b\\textasciicircum{}c"


def test_sanitize_title_handles_empty():
    assert sanitize_title("") == ""
    assert sanitize_title(None) == ""  # type: ignore[arg-type]


def test_sanitize_title_handles_backslash():
    # Backslash first so it doesn't double-escape the escapes
    assert "\\textbackslash" in sanitize_title("a\\b")


# ── Slugify ─────────────────────────────────────────────

def test_slugify_ascii():
    assert slugify("Hello World") == "hello-world"


def test_slugify_accents():
    assert slugify("Mécanique du solide") == "mecanique-du-solide"


def test_slugify_punctuation():
    assert slugify("Statique — chap 4: Le solide") == "statique-chap-4-le-solide"


def test_slugify_fallback():
    assert slugify("") == "document"
    assert slugify("!!!", fallback="x") == "x"
    assert slugify("   ") == "document"


# ── Idempotency ─────────────────────────────────────────

def test_sanitize_is_idempotent_on_clean_input():
    body = "\\section{Introduction}\nDu texte propre avec $x = 1$ équation."
    out1, n1 = sanitize_latex(body)
    out2, n2 = sanitize_latex(out1)
    assert out1 == out2
    assert n1 == [] and n2 == []
