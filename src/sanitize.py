"""LaTeX post-pass sanitizer.

Scrubs known Overleaf-breaking patterns out of LLM-generated LaTeX
fragments before they are merged into the final document. Every
transform is conservative: we keep the source text, only rewrite
constructs that we know would refuse to compile.

Public entry point:
    sanitize_latex(body: str) -> tuple[str, list[str]]

Returns the cleaned body and a list of human-readable notes describing
the transforms that fired (useful for logs / debugging).
"""

from __future__ import annotations

import re

__all__ = ["sanitize_latex", "sanitize_title", "slugify"]


# ── Title / filename helpers ────────────────────────────

_LATEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&":  r"\&",
    "%":  r"\%",
    "$":  r"\$",
    "#":  r"\#",
    "_":  r"\_",
    "{":  r"\{",
    "}":  r"\}",
    "~":  r"\textasciitilde{}",
    "^":  r"\textasciicircum{}",
}


def sanitize_title(text: str) -> str:
    """Escape LaTeX specials in a string destined for \\title{} / \\author{}.

    Order matters: backslashes first so we do not re-escape the escapes.
    """
    if not text:
        return ""
    out = text
    # Backslash first
    out = out.replace("\\", _LATEX_SPECIALS["\\"])
    for ch, repl in _LATEX_SPECIALS.items():
        if ch == "\\":
            continue
        out = out.replace(ch, repl)
    return out.strip()


def slugify(text: str, fallback: str = "document") -> str:
    """Produce a safe ASCII filename slug from arbitrary text."""
    if not text:
        return fallback
    # Decompose accented chars to ASCII when possible
    import unicodedata
    norm = unicodedata.normalize("NFKD", text)
    norm = norm.encode("ascii", "ignore").decode("ascii")
    # Replace non-alphanumeric with hyphens, squeeze repeats
    norm = re.sub(r"[^A-Za-z0-9]+", "-", norm).strip("-").lower()
    return norm or fallback


# ── Body sanitization ───────────────────────────────────

# Fenced code blocks the model sometimes leaks
_FENCE_OPEN = re.compile(r"^\s*```(?:la?tex|tex)?\s*\n?", re.MULTILINE)
_FENCE_CLOSE = re.compile(r"\n?\s*```\s*$", re.MULTILINE)

# physics-package commands we explicitly forbid
_BANNED_PHYSICS = re.compile(r"\\(?:dv|pdv|qty)\b\s*(?=[{(])")

# \begin{paragraph}{Titre}...\end{paragraph}  →  \paragraph{Titre} ...
_PARAGRAPH_ENV = re.compile(
    r"\\begin\{paragraph\}\s*\{([^}]*)\}\s*(.*?)\s*\\end\{paragraph\}",
    re.DOTALL,
)

# Leading numbering inside \section / \subsection / \subsubsection / \chapter titles
# Catches "3.4 Foo", "4) Foo", "1. Foo", "II — Foo", etc. — but NOT when the
# number is part of the real title ("Loi de Mariotte 1 atm").
_SECTION_NUM = re.compile(
    r"(\\(?:chapter|section|subsection|subsubsection)\*?\{)"
    r"\s*"
    r"(?:"
        r"\d+(?:[.\-]\d+)+\s+"             # multi-level "3.4 "
        r"|\d+[).\-:]\s+"                  # single  "3. " / "3) " / "3- " / "3: "
        r"|[IVXLCDM]{1,4}[.\-:)]\s+"        # roman   "III. "
    r")",
)

# Orphan tikzpicture (banned in our preamble usage rules)
_TIKZ_BLOCK = re.compile(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", re.DOTALL)

# Bare `- foo` lines outside an itemize environment are illegal in babel-french
# (they trigger « LaTeX Error: There's no line here to end. »). Heuristic: replace
# isolated leading "- " on a line with "$\bullet$ " — only outside math.
_BARE_DASH_LINE = re.compile(r"^(\s*)[-–—]\s+(?=\S)", re.MULTILINE)

# Stray pandoc-style fenced math blocks ($$ ... $$ across multiple lines)
# We just normalise them to \[ ... \]
_DOLLAR_DISPLAY = re.compile(r"\$\$\s*(.*?)\s*\$\$", re.DOTALL)

# Unicode quotes that babel sometimes refuses
_SMART_QUOTES = {
    "“": "``", "”": "''", "„": ",,", "‟": "``",
    "‘": "`",  "’": "'",  "‚": ",", "‛": "`",
}


def sanitize_latex(body: str) -> tuple[str, list[str]]:
    """Return a cleaned LaTeX body and a list of transformation notes."""
    notes: list[str] = []
    text = body or ""

    # 1. Strip leading/trailing markdown fences
    if _FENCE_OPEN.search(text) or _FENCE_CLOSE.search(text):
        text = _FENCE_OPEN.sub("", text)
        text = _FENCE_CLOSE.sub("", text)
        notes.append("stripped markdown fences")

    # 2. Smart quotes → LaTeX equivalents
    for src, repl in _SMART_QUOTES.items():
        if src in text:
            text = text.replace(src, repl)
    # don't note this; very common, not interesting

    # 3. Banned physics-package commands → keep the source intact for the human
    #    but disable the command so xelatex doesn't die. We comment it out.
    if _BANNED_PHYSICS.search(text):
        text = _BANNED_PHYSICS.sub(r"% [palimpsest:banned-cmd] \g<0>", text)
        notes.append("commented banned physics-package macros")

    # 4. \begin{paragraph}{...}...\end{paragraph} → \paragraph{...} ...
    if _PARAGRAPH_ENV.search(text):
        text = _PARAGRAPH_ENV.sub(r"\\paragraph{\1} \2", text)
        notes.append("converted paragraph environment to command")

    # 5. Strip numeric prefixes from section titles ("3.4 Foo" → "Foo")
    if _SECTION_NUM.search(text):
        text = _SECTION_NUM.sub(r"\1", text)
        notes.append("stripped numeric prefix from section titles")

    # 6. Orphan tikzpicture → fbox placeholder
    if _TIKZ_BLOCK.search(text):
        text = _TIKZ_BLOCK.sub(
            r"\\fbox{\\parbox{0.85\\textwidth}{"
            r"\\textbf{[Figure — schéma TikZ retiré]} \\\\ \\smallskip "
            r"\\textit{Le schéma original n'a pas pu être généré automatiquement.}}}",
            text,
        )
        notes.append("replaced inline tikzpicture with fbox placeholder")

    # 7. $$ ... $$  →  \[ ... \]
    if _DOLLAR_DISPLAY.search(text):
        text = _DOLLAR_DISPLAY.sub(r"\\[ \1 \\]", text)
        notes.append("normalized $$..$$ to \\[..\\]")

    # 8. Bare dashes at line start → bullet
    if _BARE_DASH_LINE.search(text):
        text = _BARE_DASH_LINE.sub(r"\1$\\bullet$~", text)
        notes.append("replaced bare leading dashes with bullets")

    # 9. Final balance check — count $ outside escapes. If odd, append one.
    raw_dollars = len(re.findall(r"(?<!\\)\$", text))
    if raw_dollars % 2 == 1:
        text += "$"
        notes.append("appended trailing $ to balance inline math")

    return text, notes
