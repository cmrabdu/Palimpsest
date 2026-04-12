"""PDF page extraction — converts PDF to high-resolution images."""

import logging
from pathlib import Path

from pdf2image import convert_from_path
from PIL import Image

logger = logging.getLogger(__name__)


def extract_pages(pdf_path: str | Path, dpi: int = 400) -> list[Image.Image]:
    """Extract all pages from a PDF as grayscale PIL images.

    Args:
        pdf_path: Path to the input PDF file.
        dpi: Resolution for extraction (default 400).

    Returns:
        List of PIL Image objects, one per page.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    logger.info(f"Extracting pages from {pdf_path.name} at {dpi} DPI...")
    images = convert_from_path(
        str(pdf_path),
        dpi=dpi,
        grayscale=True,
        fmt="png",
    )
    logger.info(f"Extracted {len(images)} pages.")
    return images


def save_page_image(image: Image.Image, output_path: Path) -> Path:
    """Save a single page image to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(output_path), "PNG")
    return output_path
