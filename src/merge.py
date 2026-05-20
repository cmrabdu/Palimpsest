"""Page merger and LaTeX document assembly."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from .sanitize import sanitize_title

logger = logging.getLogger(__name__)


LATEX_PREAMBLE = r"""\documentclass[12pt,a4paper]{report}

% Encodage et langue — compatible xelatex ET pdflatex (Overleaf)
\usepackage{iftex}
\ifXeTeX
  \usepackage{fontspec}
\else\ifLuaTeX
  \usepackage{fontspec}
\else
  \usepackage[utf8]{inputenc}
  \usepackage[T1]{fontenc}
\fi\fi
\usepackage[french]{babel}

% Maths
\usepackage{amsmath,amssymb,amsthm}
\usepackage{mathtools}    % extensions amsmath : \coloneqq, \prescript, etc.
\usepackage{siunitx}      % \SI{9.81}{\metre\per\second\squared}
\sisetup{output-decimal-marker={,}, locale=FR}
% Délimiteurs redimensionnables (\abs{x} → |x|, \norm{v} → ‖v‖)
\DeclarePairedDelimiter\abs{\lvert}{\rvert}
\DeclarePairedDelimiter\norm{\lVert}{\rVert}

% Environnements sémantiques
\theoremstyle{definition}
\newtheorem{definition}{Définition}[chapter]
\theoremstyle{plain}
\newtheorem{theorem}{Théorème}[chapter]
\theoremstyle{remark}
\newtheorem{remark}{Remarque}[chapter]
\newtheorem{example}{Exemple}[chapter]

% Mise en page
\usepackage[margin=2.5cm]{geometry}
\usepackage{microtype}

% Graphiques / schémas
\usepackage{tikz}
\usetikzlibrary{arrows.meta, calc, decorations.markings, angles, quotes, patterns}

% Tableaux — tabularx pour auto-fit à la largeur de page
\usepackage{booktabs}
\usepackage{array}
\usepackage{tabularx}
\usepackage{longtable}
\IfFileExists{adjustbox.sty}{\usepackage{adjustbox}}{%
  % adjustbox absent (BasicTeX) — provide a no-op stub so prompts that wrap
  % a tabular in \begin{adjustbox}{max width=\textwidth}...\end{adjustbox}
  % still compile.
  \newenvironment{adjustbox}[1]{}{}%
}

% Flottants
\usepackage{float}
\usepackage{caption}
\usepackage{graphicx}

% Divers
\usepackage{xcolor}
\usepackage{enumitem}
\usepackage{hyperref}
\hypersetup{colorlinks=true, linkcolor=blue!70!black, urlcolor=blue!70!black}

% Numérotation des équations/figures/tableaux par chapitre
\numberwithin{equation}{chapter}
\numberwithin{figure}{chapter}
\numberwithin{table}{chapter}

% Métadonnées Palimpsest
\newcommand{\palimpsestversion}{vol. iii}
"""


# Default Palimpsest cover-page blurb. Inserted on the titlepage before the
# table of contents. The text is intentionally generic — we do not assume
# the source is a physics course, and the wording stays in English so the
# blurb reads the same regardless of the document's working language.
PALIMPSEST_BLURB = (
    r"This document is a clean retranscription of a hard-to-read original "
    r"source. The text, equations and figures have been recovered and "
    r"restructured with \textbf{Palimpsest}, an open-source tool combining "
    r"OCR, LLM context tracking and OpenCV-based visual recognition, built "
    r"by Abdullah Camur."
)

PALIMPSEST_URL = "https://github.com/cmrabdu/Palimpsest"


def _titlepage(
    title: str,
    subtitle: str = "",
    author: str = "",
    include_blurb: bool = True,
) -> str:
    """Build a clean titlepage block with the Palimpsest blurb."""
    safe_title = sanitize_title(title) or "Document"
    safe_subtitle = sanitize_title(subtitle)
    safe_author = sanitize_title(author)

    lines: list[str] = []
    lines.append(r"\begin{titlepage}")
    lines.append(r"\centering")
    lines.append(r"\vspace*{2cm}")
    lines.append(r"{\Large\itshape Clean retranscription\par}")
    lines.append(r"\vspace{1.5cm}")
    lines.append(r"{\Huge\bfseries " + safe_title + r"\par}")
    if safe_subtitle:
        lines.append(r"\vspace{0.6cm}")
        lines.append(r"{\Large\itshape " + safe_subtitle + r"\par}")
    lines.append(r"\vspace{2.5cm}")
    if safe_author:
        lines.append(r"{\large " + safe_author + r"\par}")
        lines.append(r"\vspace{0.4cm}")
    lines.append(r"{\small " + date.today().strftime("%d %B %Y") + r"\par}")

    if include_blurb:
        lines.append(r"\vfill")
        lines.append(r"\begin{minipage}{0.78\textwidth}")
        lines.append(r"\small\itshape")
        lines.append(PALIMPSEST_BLURB)
        lines.append(r"\par\vspace{0.6em}")
        lines.append(
            r"\normalfont\small Software: \textbf{Palimpsest} "
            r"\textendash{} \url{" + PALIMPSEST_URL + r"}"
        )
        lines.append(r"\end{minipage}")

    lines.append(r"\vspace{1cm}")
    lines.append(r"\end{titlepage}")
    return "\n".join(lines) + "\n\n"


def merge_pages_latex(
    pages: list[str],
    title: str = "",
    author: str = "",
    subtitle: str = "",
    include_blurb: bool = True,
) -> str:
    """Assemble LaTeX body fragments into a complete compilable .tex document.

    Args:
        pages:    List of LaTeX body strings (no preamble), one per page.
        title:    Document title.
        author:   Optional author string (use empty to omit).
        subtitle: Optional subtitle (typically the detected discipline).
        include_blurb: If True, insert the Palimpsest blurb on the titlepage.

    Returns:
        Complete LaTeX document as a string.
    """
    parts = [LATEX_PREAMBLE]

    # Drive \title / \author / \date — kept in case downstream tools want them,
    # though we render our own titlepage rather than calling \maketitle.
    parts.append(f"\\title{{{sanitize_title(title) or 'Document'}}}\n")
    parts.append(f"\\author{{{sanitize_title(author)}}}\n")
    parts.append(f"\\date{{{date.today().isoformat()}}}\n\n")

    parts.append(r"\begin{document}" + "\n\n")

    # Custom titlepage (replaces \maketitle)
    parts.append(_titlepage(title, subtitle, author, include_blurb))

    parts.append(r"\tableofcontents" + "\n")
    parts.append(r"\newpage" + "\n\n")

    for page in pages:
        stripped = (page or "").strip()
        if stripped:
            parts.append(stripped)
            parts.append("\n\n")

    parts.append(r"\end{document}" + "\n")
    return "".join(parts)


def save_latex(content: str, output_path: Path) -> Path:
    """Save LaTeX content to a .tex file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    logger.info(f"Saved LaTeX: {output_path} ({len(content)} chars)")
    return output_path


# ── Legacy Markdown helpers (kept for compatibility) ────

def merge_pages(pages: list[str], title: str = "") -> str:
    """Merge page strings into a single document (Markdown fallback)."""
    parts = []
    if title:
        parts.append(f"# {title}\n")
    for i, page in enumerate(pages):
        if not page.strip():
            continue
        parts.append(page)
        if i < len(pages) - 1:
            parts.append("\n---\n")
    return "\n\n".join(parts)


def save_markdown(content: str, output_path: Path) -> Path:
    """Save Markdown content to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    logger.info(f"Saved Markdown: {output_path} ({len(content)} chars)")
    return output_path
