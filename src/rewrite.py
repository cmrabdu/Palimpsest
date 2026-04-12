"""Rewrite engine — supports Anthropic (Claude) and OpenAI (GPT/o-series) models."""

import base64
import io
import logging
import re
from enum import Enum

from PIL import Image

from .context import DocumentContext

logger = logging.getLogger(__name__)


# ── Shared ───────────────────────────────────────────────

SYSTEM_PROMPT = """\
Tu es un expert en physique, mécanique et mécanique des fluides. Tu reçois :
1. L'image originale d'une page scannée d'un cours universitaire
2. Le texte extrait par OCR (Mathpix) de cette même page
3. Le contexte accumulé des pages précédentes (variables, conventions, section courante)

Ta mission :
- **Vérifier** le texte OCR en le comparant visuellement à l'image originale
- **Corriger** toute erreur d'OCR (symboles grecs, indices/exposants, ∂ vs δ vs d, bornes d'intégrales)
- **Vérifier** la cohérence dimensionnelle des équations
- **Conserver** fidèlement tout le contenu — ne rien inventer, ne rien supprimer

RÈGLES DE FORMATAGE — output = corps LaTeX UNIQUEMENT (sans \\documentclass ni \\begin{document}) :
- Titres/sections : \\section{}, \\subsection{}, \\subsubsection{}
- Math inline : $...$
- Équations numérotées : \\begin{equation}\\label{eq:nom}...\\end{equation}
- Équations display non numérotées : \\begin{equation*}...\\end{equation*}
- Systèmes/alignements : \\begin{align}...\\end{align} ou \\begin{cases}...\\end{cases} dans equation
- Matrices : \\begin{pmatrix}...\\end{pmatrix}, \\begin{bmatrix}...\\end{bmatrix}
- Vecteurs : \\vec{F}, produit vectoriel \\times, norme \\|...\\|
- Dérivées : \\frac{d}{dt}, \\frac{\\partial}{\\partial x}, \\dot{x}, \\ddot{x}
- Schémas simples (repères, corps libres, diagrammes de forces) : \\begin{tikzpicture}...\\end{tikzpicture} dans \\begin{figure}[h]\\centering
- Figures impossibles à reproduire en TikZ : \\begin{figure}[h]\\centering\\fbox{\\textit{[Figure : description détaillée]}}\\end{figure}
- Tableaux : \\begin{table}[h]\\centering\\begin{tabular}...\\end{tabular}\\end{table}
- Texte normal : paragraphes LaTeX, \\textbf{} pour les définitions importantes

Format de sortie STRICT :
1. Le contenu LaTeX de la page
2. Séparé par une ligne contenant uniquement `%%CONTEXT_UPDATE%%`, un bloc YAML :
   - Nouvelles variables définies sur cette page
   - Changement de chapitre/section
   - Nouvelles conventions de notation

Ne pas inclure de commentaires méta. Juste le LaTeX + le bloc contexte."""

SYSTEM_PROMPT_NO_IMAGE = SYSTEM_PROMPT.replace(
    "1. L'image originale d'une page scannée d'un cours universitaire\n",
    ""
).replace(
    "- **Vérifier** le texte OCR en le comparant visuellement à l'image originale\n",
    "- **Vérifier** le texte OCR et corriger les erreurs probables\n",
).replace(
    "- **Corriger** toute erreur d'OCR",
    "- **Corriger** les erreurs probables d'OCR",
)

SYSTEM_PROMPT_VISION_DIRECT = """\
Tu es un expert en physique, mécanique et mécanique des fluides. Tu reçois :
1. L'image originale d'une page scannée d'un cours universitaire
2. Le contexte accumulé des pages précédentes (variables, conventions, section courante)

Ta mission — OCR + restructuration en une seule passe, output LaTeX :
- **Lire** l'intégralité du texte et des formules de l'image
- **Transcrire** fidèlement tout le contenu — ne rien inventer, ne rien supprimer
- **Corriger** les ambiguïtés visuelles : symboles grecs (ξ/ε, ν/v, μ/u, ρ/p), indices/exposants, ∂ vs δ vs d
- **Vérifier** la cohérence dimensionnelle des équations

RÈGLES DE FORMATAGE — output = corps LaTeX UNIQUEMENT (sans \\documentclass ni \\begin{document}) :
- Titres/sections : \\section{}, \\subsection{}, \\subsubsection{}
- Math inline : $...$
- Équations numérotées : \\begin{equation}\\label{eq:nom}...\\end{equation}
- Équations display non numérotées : \\begin{equation*}...\\end{equation*}
- Systèmes/alignements : \\begin{align}...\\end{align} ou \\begin{cases}...\\end{cases} dans equation
- Matrices : \\begin{pmatrix}...\\end{pmatrix}, \\begin{bmatrix}...\\end{bmatrix}
- Vecteurs : \\vec{F}, produit vectoriel \\times, norme \\|...\\|
- Dérivées : \\frac{d}{dt}, \\frac{\\partial}{\\partial x}, \\dot{x}, \\ddot{x}
- Schémas simples (repères, corps libres, diagrammes de forces) : \\begin{tikzpicture}...\\end{tikzpicture} dans \\begin{figure}[h]\\centering
- Figures impossibles à reproduire en TikZ : \\begin{figure}[h]\\centering\\fbox{\\textit{[Figure : description détaillée]}}\\end{figure}
- Tableaux : \\begin{table}[h]\\centering\\begin{tabular}...\\end{tabular}\\end{table}
- Texte normal : paragraphes LaTeX, \\textbf{} pour les définitions importantes

Format de sortie STRICT :
1. Le contenu LaTeX de la page
2. Séparé par une ligne contenant uniquement `%%CONTEXT_UPDATE%%`, un bloc YAML :
   - Nouvelles variables définies sur cette page
   - Changement de chapitre/section
   - Nouvelles conventions de notation

Ne pas inclure de commentaires méta. Juste le LaTeX + le bloc contexte."""


class Provider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


# ── Model → Provider mapping ────────────────────────────

PROVIDER_MAP: dict[str, Provider] = {
    # Anthropic
    "claude-opus-4-20250514": Provider.ANTHROPIC,
    "claude-sonnet-4-20250514": Provider.ANTHROPIC,
    # OpenAI
    "o1": Provider.OPENAI,
    "o4-mini": Provider.OPENAI,
    "gpt-4o": Provider.OPENAI,
    "gpt-4.1": Provider.OPENAI,
    "gpt-4.1-mini": Provider.OPENAI,
    "gpt-4.1-nano": Provider.OPENAI,
}


def detect_provider(model: str) -> Provider:
    """Auto-detect provider from model name."""
    if model in PROVIDER_MAP:
        return PROVIDER_MAP[model]
    if "claude" in model.lower():
        return Provider.ANTHROPIC
    return Provider.OPENAI


def image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64 PNG string."""
    buffer = io.BytesIO()
    if image.mode != "RGB":
        image = image.convert("RGB")
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def parse_response(full_text: str) -> tuple[str, str]:
    """Split rewritten LaTeX body from the context update YAML block."""
    # Strip markdown code fences if model wrapped output in ```latex ... ```
    text = re.sub(r"^```(?:latex|tex)?\s*\n", "", full_text.strip())
    text = re.sub(r"\n```\s*$", "", text)
    sep = "%%CONTEXT_UPDATE%%"
    if sep in text:
        parts = text.split(sep, 1)
        body = parts[0].strip()
        context_yaml = parts[1].strip()
        context_yaml = re.sub(r"^```ya?ml\s*", "", context_yaml)
        context_yaml = re.sub(r"\s*```$", "", context_yaml)
    else:
        body = text.strip()
        context_yaml = ""
    return body, context_yaml


# ── Anthropic (Claude) ──────────────────────────────────

async def _rewrite_anthropic(
    source_image: Image.Image | None,
    ocr_text: str,
    context: DocumentContext,
    api_key: str,
    model: str,
    send_image: bool,
    vision_direct: bool = False,
) -> tuple[str, str]:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)
    content = []

    # In vision_direct mode, image is mandatory (LLM does OCR)
    if (vision_direct or send_image) and source_image is not None:
        b64 = image_to_base64(source_image)
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        })

    context_block = context.to_yaml_block()
    if vision_direct:
        content.append({
            "type": "text",
            "text": f"## Contexte du document\n\n{context_block}",
        })
    else:
        content.append({
            "type": "text",
            "text": f"## Contexte du document\n\n{context_block}\n\n## Texte OCR extrait (Mathpix)\n\n{ocr_text}",
        })

    if vision_direct:
        sys_prompt = SYSTEM_PROMPT_VISION_DIRECT
    elif send_image and source_image:
        sys_prompt = SYSTEM_PROMPT
    else:
        sys_prompt = SYSTEM_PROMPT_NO_IMAGE

    response = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=[{
            "type": "text",
            "text": sys_prompt,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": content}],
    )

    usage = response.usage
    logger.info(
        f"Page {context.page_number} [{model}] — "
        f"in: {usage.input_tokens}, out: {usage.output_tokens}, "
        f"cache_read: {getattr(usage, 'cache_read_input_tokens', 0)}"
    )

    return parse_response(response.content[0].text)


# ── OpenAI (GPT / o-series) ─────────────────────────────

async def _rewrite_openai(
    source_image: Image.Image | None,
    ocr_text: str,
    context: DocumentContext,
    api_key: str,
    model: str,
    send_image: bool,
    vision_direct: bool = False,
) -> tuple[str, str]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=api_key,
        max_retries=5,
        timeout=120.0,
    )
    content = []

    # In vision_direct mode, image is mandatory (LLM does OCR)
    if (vision_direct or send_image) and source_image is not None:
        b64 = image_to_base64(source_image)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
        })

    context_block = context.to_yaml_block()
    if vision_direct:
        content.append({
            "type": "text",
            "text": f"## Contexte du document\n\n{context_block}",
        })
    else:
        content.append({
            "type": "text",
            "text": f"## Contexte du document\n\n{context_block}\n\n## Texte OCR extrait (Mathpix)\n\n{ocr_text}",
        })

    if vision_direct:
        sys_prompt = SYSTEM_PROMPT_VISION_DIRECT
    elif send_image and source_image:
        sys_prompt = SYSTEM_PROMPT
    else:
        sys_prompt = SYSTEM_PROMPT_NO_IMAGE

    # o-series models use "developer" role instead of "system"
    is_reasoning = model.startswith("o")
    system_role = "developer" if is_reasoning else "system"

    kwargs = {
        "model": model,
        "messages": [
            {"role": system_role, "content": sys_prompt},
            {"role": "user", "content": content},
        ],
    }

    # o-series: use max_completion_tokens; others: max_tokens
    if is_reasoning:
        kwargs["max_completion_tokens"] = 8192
    else:
        kwargs["max_tokens"] = 4096

    response = await client.chat.completions.create(**kwargs)

    usage = response.usage
    logger.info(
        f"Page {context.page_number} [{model}] — "
        f"in: {usage.prompt_tokens}, out: {usage.completion_tokens}"
    )

    return parse_response(response.choices[0].message.content)


# ── Public API ───────────────────────────────────────────

async def rewrite_page(
    source_image: Image.Image | None,
    ocr_text: str,
    context: DocumentContext,
    api_key: str,
    model: str = "o4-mini",
    send_image: bool = True,
    provider: Provider | None = None,
    vision_direct: bool = False,
) -> tuple[str, str]:
    """Rewrite a single page using any supported model.

    Args:
        source_image: Original page image (for visual cross-reference).
        ocr_text: Mathpix OCR output (Markdown+LaTeX). Ignored in vision_direct mode.
        context: Accumulated document context.
        api_key: API key for the chosen provider.
        model: Model name (auto-detects provider if not specified).
        send_image: Whether to include the source image.
        provider: Force a specific provider (auto-detected from model name if None).
        vision_direct: If True, skip Mathpix — the LLM reads the image directly.

    Returns:
        Tuple of (rewritten_markdown, context_update_yaml).
    """
    if provider is None:
        provider = detect_provider(model)

    if provider == Provider.ANTHROPIC:
        return await _rewrite_anthropic(source_image, ocr_text, context, api_key, model, send_image, vision_direct)
    else:
        return await _rewrite_openai(source_image, ocr_text, context, api_key, model, send_image, vision_direct)
