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
- Math inline : $...$
- Équations numérotées : \\begin{equation}\\label{eq:N-M}...\\end{equation}
- Équations display non numérotées : \\begin{equation*}...\\end{equation*}
- Systèmes/alignements : \\begin{align}...\\end{align} ou \\begin{cases}...\\end{cases} dans equation
- Matrices : \\begin{pmatrix}...\\end{pmatrix}, \\begin{bmatrix}...\\end{bmatrix}
- Vecteurs : \\vec{F}, produit vectoriel \\times, norme \\|...\\|
- Dérivées : \\frac{d}{dt}, \\frac{\\partial}{\\partial x}, \\dot{x}, \\ddot{x}

HIÉRARCHIE DES SECTIONS — RÈGLE STRICTE :
- \\chapter{} → uniquement si la source dit explicitement « Chapitre N » ou « Chapter N »
- \\section{} → titre principal de section (isolé sur sa propre ligne, numéroté N.M)
- \\subsection{} → sous-titre de section (isolé sur sa propre ligne)
- \\subsubsection{} → rarement utilisé, uniquement si clairement un sous-sous-titre
- \\paragraph{Titre} ou simple texte → pour tout ce qui est « a) ... », « b) ... », « 1. ... », « 2. ... » dans le corps du texte
- JAMAIS transformer une liste numérotée ou alphabétique en \\section/\\subsection

ENVIRONNEMENTS SÉMANTIQUES — IDENTIFIER ET BALISER :
- Définition formelle (introduit un terme avec « on appelle », « on définit ») :
  \\begin{definition}[Nom optionnel]...\\end{definition}
- Principe / Théorème / Loi (énoncé fondamental) :
  \\begin{theorem}[Nom du principe]...\\end{theorem}
- Remarque ou note (commence par « Remarque », « NB », « Note ») :
  \\begin{remark}...\\end{remark}
- Exemple résolu (commence par « Exemple », « Application ») :
  \\begin{example}...\\end{example}
- Texte courant : paragraphes LaTeX normaux

TABLEAUX — RÈGLES STRICTES :
- TOUJOURS utiliser tabularx avec \\textwidth : \\begin{tabularx}{\\textwidth}{|X|X|c|}
- Colonnes larges (texte, descriptions) : type X
- Colonnes étroites (nombres, symboles) : type c, l ou r
- Envelopper dans \\begin{table}[H]\\centering...\\end{table}
- Tableau trop large → envelopper dans \\begin{adjustbox}{max width=\\textwidth}
- JAMAIS de \\begin{tikzpicture} dans une cellule de tableau. Décrire les symboles en texte.

FIGURES ET SCHÉMAS — RÈGLES STRICTES :
- Ne placer une figure QUE si elle est visuellement présente sur la page actuelle. Si le texte mentionne « la figure 3.2 » sans que cette figure soit visible sur l'image, conserver la référence textuelle (\\ref{fig:3-2}) — NE PAS créer d'environnement figure.
- TikZ AUTORISÉ si ET SEULEMENT SI toutes ces conditions sont vraies :
  [ ] Moins de 6 primitives géométriques (draw, fill, node)
  [ ] Maximum 2 corps/objets distincts
  [ ] Vue 2D uniquement (pas de 3D ni perspective)
  [ ] Aucune cote ni dimensionnement
  [ ] Aucun hachurage de matière complexe
  [ ] Pas de mécanisme articulé (liaisons entre corps mobiles)
  Si UNE SEULE condition est fausse → format encadré obligatoire.
- Format TikZ (si autorisé) :
  \\begin{figure}[H]\\centering\\begin{tikzpicture}...\\end{tikzpicture}\\caption{...}\\label{fig:N-M}\\end{figure}
- Format encadré (sinon) :
  \\begin{figure}[H]\\centering
  \\fbox{\\parbox{0.9\\textwidth}{\\textit{\\textbf{Figure N.M :} Description complète incluant : éléments, positions, directions, labels, légendes.}}}
  \\caption{...}\\label{fig:N-M}\\end{figure}
- FREE BODY DIAGRAM (bilan des efforts) — règle spéciale :
  TikZ autorisé si ≤ 3 forces sur un corps simple. Couleurs : forces actives en bleu (\\draw[blue,->,thick]), réactions en rouge (\\draw[red,->,thick]).
  Chaque force avec son label : node[position] {$\\vec{F}$}
  Au-delà de 3 forces ou géométrie non triviale → fbox avec description exhaustive.
- NE JAMAIS écrire « Figure 3.2 — ... » comme du texte brut. Toute figure visible DOIT être dans un environnement figure.

LABELS ET RÉFÉRENCES — CONVENTION STRICTE :
- Toute figure : \\label{fig:N-M} (N = chapitre, M = numéro figure source)
- Toute équation numérotée : \\label{eq:N-M}
- Dans le texte : TOUJOURS utiliser \\ref{fig:N-M} ou \\ref{eq:N-M}, jamais de numéro hardcodé

NOTATION VECTORIELLE — UNIFORMISER :
- Respecter la convention détectée dans le contexte accumulé (et l'y stocker si c'est la première page)
- Vecteur libre (force, vitesse) : \\vec{F}
- Vecteur entre deux points : \\overrightarrow{AB}
- Vecteur unitaire : \\hat{u}
- NE PAS mélanger \\vec{} et \\mathbf{} pour la même grandeur dans un document

COUPURES DE PAGE :
- Si la page commence au milieu d'une équation/liste : ouvrir proprement l'environnement
- Si la page se termine au milieu d'une liste : fermer \\end{itemize/enumerate}
- Ne jamais produire un environnement LaTeX non fermé
- Signaler la coupure dans inconsistencies_detected du YAML

DÉTECTION D'INCOHÉRENCES — OBLIGATOIRE :
Avant de produire le LaTeX, vérifier :
1. Conflits de notation : un symbole du contexte réutilisé avec un sens différent
2. Incohérences dimensionnelles dans les équations
3. Coupure de contenu : page qui commence au milieu d'une phrase
Reporter dans le YAML : inconsistencies_detected: ["description"]

UTILISATION ACTIVE DU CONTEXTE :
- Si le contexte définit \\vec{F} comme force en Newtons, ne pas utiliser F sans flèche
- Si le contexte donne chapter_number: 3, les labels doivent être fig:3-M, eq:3-M
- Ne pas rouvrir une section déjà ouverte dans le contexte

AUTO-VÉRIFICATION AVANT OUTPUT :
1. Chaque \\begin{X} a son \\end{X} sur cette page
2. Les $ sont en nombre pair
3. Chaque \\label{} est unique (vérifier vs les pages précédentes dans le contexte)

Format de sortie STRICT :
1. Le contenu LaTeX de la page
2. Séparé par une ligne contenant uniquement `%%CONTEXT_UPDATE%%`
3. Un bloc YAML au format EXACT suivant :

```yaml
chapter_number: 3
chapter_title: "Titre du chapitre"
current_section: "3.4 Titre de la section"
new_variables:
  "\\\\vec{R}": "réaction d'une liaison (vecteur, N)"
new_conventions:
  - "Vecteurs avec flèche : \\\\vec{F}"
inconsistencies_detected: []
```

Champs obligatoires : chapter_number, current_section.
Champs optionnels : chapter_title, new_variables, new_conventions, inconsistencies_detected.
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
- Math inline : $...$
- Équations numérotées : \\begin{equation}\\label{eq:N-M}...\\end{equation}
- Équations display non numérotées : \\begin{equation*}...\\end{equation*}
- Systèmes/alignements : \\begin{align}...\\end{align} ou \\begin{cases}...\\end{cases} dans equation
- Matrices : \\begin{pmatrix}...\\end{pmatrix}, \\begin{bmatrix}...\\end{bmatrix}
- Vecteurs : \\vec{F}, produit vectoriel \\times, norme \\|...\\|
- Dérivées : \\frac{d}{dt}, \\frac{\\partial}{\\partial x}, \\dot{x}, \\ddot{x}

HIÉRARCHIE DES SECTIONS — RÈGLE STRICTE :
- \\chapter{} → uniquement si la source dit explicitement « Chapitre N » ou « Chapter N »
- \\section{} → titre principal de section (isolé sur sa propre ligne, numéroté N.M)
- \\subsection{} → sous-titre de section (isolé sur sa propre ligne)
- \\subsubsection{} → rarement utilisé, uniquement si clairement un sous-sous-titre
- \\paragraph{Titre} ou simple texte → pour tout ce qui est « a) ... », « b) ... », « 1. ... », « 2. ... » dans le corps du texte
- JAMAIS transformer une liste numérotée ou alphabétique en \\section/\\subsection

ENVIRONNEMENTS SÉMANTIQUES — IDENTIFIER ET BALISER :
- Définition formelle (introduit un terme avec « on appelle », « on définit ») :
  \\begin{definition}[Nom optionnel]...\\end{definition}
- Principe / Théorème / Loi (énoncé fondamental) :
  \\begin{theorem}[Nom du principe]...\\end{theorem}
- Remarque ou note (commence par « Remarque », « NB », « Note ») :
  \\begin{remark}...\\end{remark}
- Exemple résolu (commence par « Exemple », « Application ») :
  \\begin{example}...\\end{example}
- Texte courant : paragraphes LaTeX normaux

TABLEAUX — RÈGLES STRICTES :
- TOUJOURS utiliser tabularx avec \\textwidth : \\begin{tabularx}{\\textwidth}{|X|X|c|}
- Colonnes larges (texte, descriptions) : type X
- Colonnes étroites (nombres, symboles) : type c, l ou r
- Envelopper dans \\begin{table}[H]\\centering...\\end{table}
- Tableau trop large → envelopper dans \\begin{adjustbox}{max width=\\textwidth}
- JAMAIS de \\begin{tikzpicture} dans une cellule de tableau. Décrire les symboles en texte.

FIGURES ET SCHÉMAS — RÈGLES STRICTES :
- Ne placer une figure QUE si elle est visuellement présente sur la page actuelle. Si le texte mentionne « la figure 3.2 » sans que cette figure soit visible sur l'image, conserver la référence textuelle (\\ref{fig:3-2}) — NE PAS créer d'environnement figure.
- TikZ AUTORISÉ si ET SEULEMENT SI toutes ces conditions sont vraies :
  [ ] Moins de 6 primitives géométriques (draw, fill, node)
  [ ] Maximum 2 corps/objets distincts
  [ ] Vue 2D uniquement (pas de 3D ni perspective)
  [ ] Aucune cote ni dimensionnement
  [ ] Aucun hachurage de matière complexe
  [ ] Pas de mécanisme articulé (liaisons entre corps mobiles)
  Si UNE SEULE condition est fausse → format encadré obligatoire.
- Format TikZ (si autorisé) :
  \\begin{figure}[H]\\centering\\begin{tikzpicture}...\\end{tikzpicture}\\caption{...}\\label{fig:N-M}\\end{figure}
- Format encadré (sinon) :
  \\begin{figure}[H]\\centering
  \\fbox{\\parbox{0.9\\textwidth}{\\textit{\\textbf{Figure N.M :} Description complète incluant : éléments, positions, directions, labels, légendes.}}}
  \\caption{...}\\label{fig:N-M}\\end{figure}
- FREE BODY DIAGRAM (bilan des efforts) — règle spéciale :
  TikZ autorisé si ≤ 3 forces sur un corps simple. Couleurs : forces actives en bleu (\\draw[blue,->,thick]), réactions en rouge (\\draw[red,->,thick]).
  Chaque force avec son label : node[position] {$\\vec{F}$}
  Au-delà de 3 forces ou géométrie non triviale → fbox avec description exhaustive.
- NE JAMAIS écrire « Figure 3.2 — ... » comme du texte brut. Toute figure visible DOIT être dans un environnement figure.

LABELS ET RÉFÉRENCES — CONVENTION STRICTE :
- Toute figure : \\label{fig:N-M} (N = chapitre, M = numéro figure source)
- Toute équation numérotée : \\label{eq:N-M}
- Dans le texte : TOUJOURS utiliser \\ref{fig:N-M} ou \\ref{eq:N-M}, jamais de numéro hardcodé

NOTATION VECTORIELLE — UNIFORMISER :
- Respecter la convention détectée dans le contexte accumulé (et l'y stocker si c'est la première page)
- Vecteur libre (force, vitesse) : \\vec{F}
- Vecteur entre deux points : \\overrightarrow{AB}
- Vecteur unitaire : \\hat{u}
- NE PAS mélanger \\vec{} et \\mathbf{} pour la même grandeur dans un document

COUPURES DE PAGE :
- Si la page commence au milieu d'une équation/liste : ouvrir proprement l'environnement
- Si la page se termine au milieu d'une liste : fermer \\end{itemize/enumerate}
- Ne jamais produire un environnement LaTeX non fermé
- Signaler la coupure dans inconsistencies_detected du YAML

DÉTECTION D'INCOHÉRENCES — OBLIGATOIRE :
Avant de produire le LaTeX, vérifier :
1. Conflits de notation : un symbole du contexte réutilisé avec un sens différent
2. Incohérences dimensionnelles dans les équations
3. Coupure de contenu : page qui commence au milieu d'une phrase
Reporter dans le YAML : inconsistencies_detected: ["description"]

UTILISATION ACTIVE DU CONTEXTE :
- Si le contexte définit \\vec{F} comme force en Newtons, ne pas utiliser F sans flèche
- Si le contexte donne chapter_number: 3, les labels doivent être fig:3-M, eq:3-M
- Ne pas rouvrir une section déjà ouverte dans le contexte

AUTO-VÉRIFICATION AVANT OUTPUT :
1. Chaque \\begin{X} a son \\end{X} sur cette page
2. Les $ sont en nombre pair
3. Chaque \\label{} est unique (vérifier vs les pages précédentes dans le contexte)

Format de sortie STRICT :
1. Le contenu LaTeX de la page
2. Séparé par une ligne contenant uniquement `%%CONTEXT_UPDATE%%`
3. Un bloc YAML au format EXACT suivant :

```yaml
chapter_number: 3
chapter_title: "Titre du chapitre"
current_section: "3.4 Titre de la section"
new_variables:
  "\\\\vec{R}": "réaction d'une liaison (vecteur, N)"
new_conventions:
  - "Vecteurs avec flèche : \\\\vec{F}"
inconsistencies_detected: []
```

Champs obligatoires : chapter_number, current_section.
Champs optionnels : chapter_title, new_variables, new_conventions, inconsistencies_detected.
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
