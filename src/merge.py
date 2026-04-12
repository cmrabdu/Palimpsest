"""Page merger and LaTeX document assembly."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

LATEX_PREAMBLE = r"""\documentclass[12pt,a4paper]{report}

% Encodage et langue
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[french]{babel}

% Maths
\usepackage{amsmath,amssymb,amsthm}
\usepackage{physics}      % \dv, \pdv, \vec, \norm, \abs...
\usepackage{siunitx}      % \SI{9.81}{\metre\per\second\squared}
\sisetup{output-decimal-marker={,}, locale=FR}

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
\usepackage{adjustbox}

% Flottants
\usepackage{float}
\usepackage{caption}
\usepackage{graphicx}

% Divers
\usepackage{xcolor}
\usepackage{enumitem}
\usepackage{hyperref}
\hypersetup{colorlinks=true, linkcolor=blue!70!black, urlcolor=blue}

% Numérotation des équations/figures/tableaux par chapitre
\numberwithin{equation}{chapter}
\numberwithin{figure}{chapter}
\numberwithin{table}{chapter}

"""


def merge_pages_latex(pages: list[str], title: str = "", author: str = "") -> str:
    """Assemble LaTeX body fragments into a complete compilable .tex document.

    Args:
        pages: List of LaTeX body strings (no preamble), one per page.
        title:  Document title.
        author: Optional author string.

    Returns:
        Complete LaTeX document as a string.
    """
    parts = [LATEX_PREAMBLE]

    # Title block
    if title:
        escaped_title = title.replace("_", r"\_").replace("&", r"\&")
        parts.append(f"\\title{{\\textbf{{{escaped_title}}}}}\n")
    else:
        parts.append("\\title{Document}\n")
    parts.append(f"\\author{{{author}}}\n" if author else "\\author{}\n")
    parts.append("\\date{}\n\n")

    parts.append("\\begin{document}\n\n")
    parts.append("\\maketitle\n")
    parts.append("\\tableofcontents\n")
    parts.append("\\newpage\n\n")

    for page in pages:
        stripped = page.strip()
        if stripped:
            parts.append(stripped)
            parts.append("\n\n")

    parts.append("\\end{document}\n")
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
