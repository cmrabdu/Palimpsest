"""STEM-Pipe — Main pipeline orchestrator."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Callable

import yaml
from PIL import Image
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn

from src.context import DocumentContext
from src.extract import extract_pages, save_page_image
from src.export import latex_to_pdf
from src.merge import merge_pages_latex, save_latex
from src.ocr_mathpix import ocr_page
from src.preprocess import preprocess
from src.rewrite import rewrite_page, detect_provider, Provider

import httpx

console = Console()
logger = logging.getLogger("stem_pipe")


# ── Cache helpers ────────────────────────────────────────

def _cache_dir(base: Path, pdf_name: str) -> Path:
    return base / pdf_name


def _cache_path(cache: Path, page: int, stage: str) -> Path:
    return cache / f"page_{page:04d}_{stage}"


def _load_cached(path: Path) -> str | None:
    if path.with_suffix(".md").exists():
        return path.with_suffix(".md").read_text(encoding="utf-8")
    return None


def _save_cached(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".md").write_text(content, encoding="utf-8")


# ── Pipeline ─────────────────────────────────────────────

async def run_pipeline(
    pdf_path: str,
    config_path: str = "config.yaml",
    on_progress: Callable[[int, int, str], None] | None = None,
) -> Path:
    """Run the full STEM-Pipe pipeline on a PDF.

    Args:
        pdf_path: Path to the input scanned PDF.
        config_path: Path to configuration YAML.
        on_progress: Optional callback(page, total, stage) for UI updates.

    Returns:
        Path to the final output Markdown file.
    """
    pdf = Path(pdf_path)
    config = yaml.safe_load(Path(config_path).read_text())

    # Config values
    dpi = config.get("extraction", {}).get("dpi", 400)
    extraction_engine = config.get("extraction", {}).get("engine", "mathpix")
    vision_direct = extraction_engine == "vision"

    # Mathpix keys (only needed if not in vision_direct mode)
    mathpix_id = config.get("api_keys", {}).get("mathpix", {}).get("app_id", "")
    mathpix_key = config.get("api_keys", {}).get("mathpix", {}).get("app_key", "")
    model = config.get("rewrite", {}).get("model", "o4-mini")
    provider = detect_provider(model)

    # Resolve the correct API key for the chosen model's provider
    if provider == Provider.ANTHROPIC:
        rewrite_api_key = config["api_keys"]["anthropic"]["api_key"]
    else:
        rewrite_api_key = config["api_keys"]["openai"]["api_key"]
    send_image = config.get("rewrite", {}).get("send_source_image", True)
    language = config.get("rewrite", {}).get("language", "fr")
    do_deskew = config.get("preprocessing", {}).get("deskew", True)
    do_binarize = config.get("preprocessing", {}).get("binarize", True)
    do_denoise = config.get("preprocessing", {}).get("denoise", False)
    batch_size = config.get("concurrency", {}).get("extraction_batch_size", 5)
    cache_enabled = config.get("cache", {}).get("enabled", True)
    do_merge = config.get("output", {}).get("merge_pages", True)
    gen_pdf = config.get("output", {}).get("generate_pdf", False)

    _base = Path(__file__).resolve().parent
    cache_base = _base / config.get("cache", {}).get("directory", ".cache")
    cache = _cache_dir(cache_base, pdf.stem)
    cache.mkdir(parents=True, exist_ok=True)
    output_dir = _base / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    def progress(page: int, total: int, stage: str):
        if on_progress:
            on_progress(page, total, stage)

    # ── Step 1: Extract pages ──────────────────────────
    console.print(f"\n[bold cyan]▸ Extracting pages[/] from {pdf.name} at {dpi} DPI...")
    images = await asyncio.to_thread(extract_pages, pdf, dpi)
    total = len(images)
    console.print(f"  {total} pages extracted.\n")

    # ── Step 2 & 3: Preprocess + OCR (batched, or skip if vision_direct) ─
    ocr_results: list[str] = [""] * total
    preprocessed_images: list[Image.Image] = [None] * total  # type: ignore

    if vision_direct:
        console.print("[bold cyan]▸ Preprocessing[/] (vision direct — no Mathpix)...\n")
        for idx, img in enumerate(images):
            progress(idx + 1, total, "preprocessing")
            processed = await asyncio.to_thread(preprocess, img, do_deskew, do_binarize, do_denoise)
            preprocessed_images[idx] = processed
            if cache_enabled:
                img_path = _cache_path(cache, idx, "preprocessed").with_suffix(".png")
                await asyncio.to_thread(save_page_image, processed, img_path)
    else:
        console.print("[bold cyan]▸ Preprocessing & OCR[/] (Mathpix)...\n")
        semaphore = asyncio.Semaphore(batch_size)

        async with httpx.AsyncClient(timeout=60) as http_client:

            async def _extract_one(idx: int, img: Image.Image):
                # Check cache
                cached = _load_cached(_cache_path(cache, idx, "ocr")) if cache_enabled else None
                if cached is not None:
                    ocr_results[idx] = cached
                    # Load preprocessed image from cache if available
                    img_path = _cache_path(cache, idx, "preprocessed").with_suffix(".png")
                    if img_path.exists():
                        preprocessed_images[idx] = Image.open(img_path)
                    else:
                        preprocessed_images[idx] = await asyncio.to_thread(preprocess, img, do_deskew, do_binarize, do_denoise)
                    progress(idx + 1, total, "ocr (cached)")
                    return

                async with semaphore:
                    progress(idx + 1, total, "preprocessing")
                    processed = await asyncio.to_thread(preprocess, img, do_deskew, do_binarize, do_denoise)
                    preprocessed_images[idx] = processed

                    # Save preprocessed image
                    if cache_enabled:
                        img_path = _cache_path(cache, idx, "preprocessed").with_suffix(".png")
                        save_page_image(processed, img_path)

                    progress(idx + 1, total, "ocr")
                    text = await ocr_page(processed, mathpix_id, mathpix_key, http_client)
                    ocr_results[idx] = text

                    if cache_enabled:
                        _save_cached(_cache_path(cache, idx, "ocr"), text)

            await asyncio.gather(*[_extract_one(i, img) for i, img in enumerate(images)])

    # ── Step 4: Rewrite with LLM (sequential for context) ─
    mode_label = "vision direct OCR + restructuring" if vision_direct else "verification + restructuring"
    console.print(f"\n[bold cyan]▸ Rewriting with {model}[/] ({mode_label})...\n")
    context = DocumentContext()

    # Load context from cache if resuming
    ctx_cache = cache / "context.json"
    rewritten: list[str] = [""] * total

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress_bar:
        task = progress_bar.add_task("Rewriting", total=total)

        for idx in range(total):
            context.page_number = idx + 1

            # Check cache
            cached = _load_cached(_cache_path(cache, idx, "rewrite")) if cache_enabled else None
            if cached is not None:
                rewritten[idx] = cached
                progress_bar.advance(task)
                progress(idx + 1, total, "rewrite (cached)")
                continue

            progress(idx + 1, total, "rewrite")

            # Use original (non-binarized) image for Claude — better for visual reference
            source_img = images[idx]

            max_retries = config.get("concurrency", {}).get("max_retries", 3)
            retry_delay = config.get("concurrency", {}).get("retry_delay", 2)
            last_err = None
            for attempt in range(max_retries):
                try:
                    markdown, ctx_yaml = await rewrite_page(
                        source_image=source_img,
                        ocr_text=ocr_results[idx],
                        context=context,
                        api_key=rewrite_api_key,
                        model=model,
                        send_image=send_image,
                        vision_direct=vision_direct,
                    )
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    logger.warning(f"Page {idx+1} rewrite attempt {attempt+1}/{max_retries} failed: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))

            if last_err is not None:
                raise last_err

            rewritten[idx] = markdown

            # Update context
            if ctx_yaml:
                context.update_from_claude_response(ctx_yaml)

            # Cache
            if cache_enabled:
                _save_cached(_cache_path(cache, idx, "rewrite"), markdown)
                ctx_cache.write_text(
                    json.dumps({
                        "document_title": context.document_title,
                        "current_chapter": context.current_chapter,
                        "current_section": context.current_section,
                        "variables": context.variables,
                        "notation_conventions": context.notation_conventions,
                        "page_number": context.page_number,
                    }, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            progress_bar.advance(task)

    # ── Step 5: Merge & export ────────────────────────
    console.print("\n[bold cyan]▸ Assembling LaTeX document[/]...")
    title = context.document_title or pdf.stem.replace("_", " ").title()

    if do_merge:
        final_tex = merge_pages_latex(rewritten, title=title)
        tex_path = save_latex(final_tex, output_dir / f"{pdf.stem}.tex")
        console.print(f"  [green]✓[/] LaTeX: {tex_path}")

        # Always compile to PDF
        console.print("[bold cyan]▸ Compiling PDF[/] (xelatex)...")
        try:
            pdf_out = latex_to_pdf(tex_path, output_dir / f"{pdf.stem}.pdf")
            console.print(f"  [green]✓[/] PDF: {pdf_out}")
            final_output = pdf_out
        except RuntimeError as e:
            console.print(f"  [yellow]⚠[/] PDF compilation failed — returning .tex: {e}")
            final_output = tex_path
    else:
        # Save individual pages as .tex fragments
        for idx, page in enumerate(rewritten):
            save_latex(page, output_dir / pdf.stem / f"page_{idx + 1:04d}.tex")
        final_output = output_dir / pdf.stem

    console.print(f"\n[bold green]✓ Done![/] Output: {final_output}\n")
    return final_output


# ── CLI ──────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="STEM-Pipe — Transform scanned STEM PDFs into structured LaTeX documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("pdf", help="Path to the scanned PDF file")
    parser.add_argument("-c", "--config", default="config.yaml", help="Config file (default: config.yaml)")
    parser.add_argument("--format", choices=["markdown", "latex", "both"], default=None, help="Output format override")
    parser.add_argument("--pdf", dest="gen_pdf", action="store_true", help="Also generate PDF output")
    parser.add_argument("--no-mathpix", action="store_true", help="Vision direct mode — LLM does OCR, no Mathpix needed")
    parser.add_argument("--model", default=None, help="Override rewrite model (e.g. o4-mini, gpt-4.1, claude-opus-4-20250514)")
    parser.add_argument("--resume", action="store_true", help="Resume from cache (default if cache exists)")
    parser.add_argument("--no-cache", action="store_true", help="Ignore cache, reprocess everything")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Apply CLI overrides to config
    config = yaml.safe_load(Path(args.config).read_text())
    if args.no_cache:
        config.setdefault("cache", {})["enabled"] = False
    if args.gen_pdf:
        config.setdefault("output", {})["generate_pdf"] = True
    if args.format:
        config.setdefault("output", {})["format"] = args.format
    if args.no_mathpix:
        config.setdefault("extraction", {})["engine"] = "vision"
    if args.model:
        config.setdefault("rewrite", {})["model"] = args.model

    # Write temp config with overrides
    tmp_config = Path(".cache/_cli_config.yaml")
    tmp_config.parent.mkdir(parents=True, exist_ok=True)
    tmp_config.write_text(yaml.dump(config))

    asyncio.run(run_pipeline(args.pdf, str(tmp_config)))


if __name__ == "__main__":
    main()
