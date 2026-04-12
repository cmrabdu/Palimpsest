"""Export LaTeX to PDF via xelatex/pdflatex."""

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Prefer xelatex (better Unicode/font support), fall back to pdflatex
_LATEX_BINS = ["/Library/TeX/texbin/xelatex", "/Library/TeX/texbin/pdflatex", "xelatex", "pdflatex"]


def _find_latex() -> str | None:
    for binary in _LATEX_BINS:
        if shutil.which(binary):
            return binary
    return None


def latex_to_pdf(tex_path: Path, output_path: Path) -> Path:
    """Compile a .tex file to PDF using xelatex (runs twice for TOC/refs).

    Args:
        tex_path:    Path to the input .tex file.
        output_path: Desired path for the output .pdf file.

    Returns:
        Path to the generated PDF.

    Raises:
        RuntimeError: If no LaTeX engine found or compilation fails.
    """
    engine = _find_latex()
    if engine is None:
        raise RuntimeError(
            "No LaTeX engine found. Install with: brew install --cask basictex"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Run in a temp dir to keep aux files away from the output folder
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        cmd = [
            engine,
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"-output-directory={tmp}",
            str(tex_path.resolve()),
        ]

        logger.info(f"Compiling LaTeX (pass 1/2): {tex_path.name}")
        r1 = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp)

        if r1.returncode != 0:
            # Filter the log to the most useful error lines
            error_lines = [
                l for l in r1.stdout.splitlines()
                if l.startswith("!") or "Error" in l or "error" in l
            ][:20]
            raise RuntimeError(
                f"LaTeX compilation failed:\n" + "\n".join(error_lines) +
                "\n\nFull log tail:\n" + "\n".join(r1.stdout.splitlines()[-30:])
            )

        # Second pass for TOC and cross-references
        logger.info(f"Compiling LaTeX (pass 2/2): {tex_path.name}")
        subprocess.run(cmd, capture_output=True, text=True, cwd=tmp)

        # Move the PDF to the final destination
        stem = tex_path.stem
        generated = tmp_path / f"{stem}.pdf"
        if not generated.exists():
            raise RuntimeError(f"PDF not found after compilation: {generated}")
        shutil.move(str(generated), str(output_path))

    logger.info(f"PDF generated: {output_path}")
    return output_path


# ── Legacy Pandoc helper (kept for compatibility) ───────

def check_pandoc() -> bool:
    return shutil.which("pandoc") is not None


def markdown_to_pdf(markdown_path: Path, output_path: Path) -> Path:
    """Convert Markdown+LaTeX file to PDF using Pandoc (legacy fallback)."""
    if not check_pandoc():
        raise RuntimeError("pandoc is not installed. Install with: brew install pandoc")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "pandoc", str(markdown_path),
        "-o", str(output_path),
        "--pdf-engine=xelatex",
        "-V", "geometry:margin=2.5cm",
        "-V", "fontsize=11pt",
        "-V", "documentclass=article",
        "-V", "lang=fr",
        "--toc", "--number-sections",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Pandoc failed:\n{result.stderr}")
    return output_path
