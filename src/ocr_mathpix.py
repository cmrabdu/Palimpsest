"""Mathpix OCR — STEM-specialized formula and text extraction."""

import base64
import io
import logging
from pathlib import Path

import httpx
from PIL import Image

logger = logging.getLogger(__name__)

MATHPIX_API_URL = "https://api.mathpix.com/v3/text"


def image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64-encoded PNG string."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


async def ocr_page(
    image: Image.Image,
    app_id: str,
    app_key: str,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Send a single page image to Mathpix and get Markdown+LaTeX back.

    Args:
        image: Preprocessed page image.
        app_id: Mathpix application ID.
        app_key: Mathpix application key.
        client: Optional shared httpx client for connection reuse.

    Returns:
        Markdown string with LaTeX formulas.
    """
    b64 = image_to_base64(image)

    headers = {
        "app_id": app_id,
        "app_key": app_key,
        "Content-Type": "application/json",
    }

    payload = {
        "src": f"data:image/png;base64,{b64}",
        "formats": ["text"],
        "math_inline_delimiters": ["$", "$"],
        "math_display_delimiters": ["$$", "$$"],
        "rm_spaces": True,
        "include_line_data": False,
    }

    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=60)
        should_close = True

    try:
        response = await client.post(MATHPIX_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()

        if "error" in result:
            raise RuntimeError(f"Mathpix error: {result['error']}")

        text = result.get("text", "")
        confidence = result.get("confidence", 0)
        logger.debug(f"Mathpix OCR done — confidence: {confidence:.2f}, length: {len(text)} chars")
        return text

    finally:
        if should_close:
            await client.aclose()


async def ocr_batch(
    images: list[Image.Image],
    app_id: str,
    app_key: str,
    batch_size: int = 5,
) -> list[str]:
    """Process multiple pages through Mathpix with controlled concurrency.

    Args:
        images: List of preprocessed page images.
        app_id: Mathpix application ID.
        app_key: Mathpix application key.
        batch_size: Number of concurrent requests.

    Returns:
        List of Markdown strings, one per page.
    """
    import asyncio

    results: list[str] = [""] * len(images)
    semaphore = asyncio.Semaphore(batch_size)

    async with httpx.AsyncClient(timeout=60) as client:

        async def _process(idx: int, img: Image.Image):
            async with semaphore:
                logger.info(f"OCR page {idx + 1}/{len(images)}...")
                results[idx] = await ocr_page(img, app_id, app_key, client)

        await asyncio.gather(*[_process(i, img) for i, img in enumerate(images)])

    return results
