<div align="center">

# STEM-Pipe

### Scanned STEM PDFs → Beautiful LaTeX Documents

**Transform scanned university physics, mechanics, and fluid dynamics courses into clean, structured, formula-perfect documents.**

[Getting Started](#getting-started) · [How It Works](#how-it-works) · [Web Interface](#web-interface) · [Cost Estimate](#cost-estimate) · [API Reference](#api-reference)

---

</div>

## The Problem

You have scanned PDFs of university courses from the 80s — dense physics, differential equations, triple integrals, tensor notation. They're **image-only**: no text layer, no copy-paste, no way to feed them to an AI for studying. OCR tools like Tesseract choke on mathematical notation.

## The Solution

STEM-Pipe is a fully automated pipeline that:

1. **Extracts** each page as a high-resolution image
2. **Preprocesses** images (deskew, binarize, denoise)
3. **OCRs** with Mathpix — the gold standard for STEM formula recognition
4. **Rewrites & Verifies** with Claude Opus, cross-referencing the original image to catch and correct OCR errors using physics domain knowledge
5. **Merges** pages into a clean, structured document with proper sections, LaTeX formulas, and accumulated context

```
┌─────────┐     ┌──────────────┐     ┌─────────┐     ┌───────────────────┐     ┌────────────┐
│  PDF     │────▶│ Preprocessing│────▶│ Mathpix │────▶│ Claude Opus       │────▶│ Final Doc  │
│ (scanned)│     │ OpenCV       │     │ OCR     │     │ Image + OCR text  │     │ .md / .tex │
└─────────┘     └──────────────┘     └─────────┘     │ → verify & rewrite│     └────────────┘
                                                      └───────────────────┘
```

## Key Features

- **Formula-aware OCR** — Mathpix handles `∂`, `∫∫∫`, `∇×`, tensor indices, Greek letters
- **Physics-aware verification** — Claude checks dimensional consistency, corrects `ξ` vs `ε`, validates equation structure
- **Cross-reference mode** — Claude sees both the original image AND the OCR text, catching divergences
- **Inter-page context** — Variables, notation conventions, and section structure carry across pages
- **Fault-tolerant** — Page-by-page caching; resume interrupted runs from where they stopped
- **Web interface** — Drop a PDF, watch it process, download the result
- **Export** — Markdown+LaTeX (for LLMs/Obsidian) or compiled PDF (via Pandoc)

## How It Works

### Pipeline Architecture

```
stem-pipe/
├── config.yaml              # API keys & settings
├── pipeline.py              # CLI entry point
├── server.py                # Web interface (FastAPI)
├── src/
│   ├── extract.py           # PDF → high-res images (pdf2image)
│   ├── preprocess.py        # OpenCV: binarize, deskew, denoise
│   ├── ocr_mathpix.py       # Mathpix API extraction
│   ├── rewrite.py           # Claude Opus verification & restructuring
│   ├── context.py           # Inter-page context accumulator
│   ├── merge.py             # Page fusion → final document
│   └── export.py            # Pandoc → PDF compilation
├── web/
│   └── index.html           # Single-page web UI
├── .cache/                  # Page-level cache (auto-generated)
└── output/                  # Final documents (auto-generated)
```

### Step-by-Step

#### 1. PDF → Images (`src/extract.py`)
- Uses `pdf2image` (poppler backend) at **400 DPI**
- Grayscale extraction for consistency
- Each page saved as PNG in cache

#### 2. Preprocessing (`src/preprocess.py`)
- **Adaptive binarization** — handles uneven lighting from phone scans
- **Deskew** — auto-detects and corrects page rotation (common with CamScanner)
- **Denoise** — optional, for particularly noisy scans
- Processed images stored alongside originals in cache

#### 3. STEM OCR (`src/ocr_mathpix.py`)
- Sends preprocessed images to **Mathpix API**
- Returns Markdown with LaTeX inline (`$...$`) and display (`$$...$$`)
- Handles tables, section headers, numbered equations
- Batch processing with rate limiting

#### 4. Verification & Rewrite (`src/rewrite.py`)
- Sends to **Claude Opus**:
  - The **original page image** (for visual cross-reference)
  - The **Mathpix OCR output** (raw text to verify/improve)
  - The **inter-page context** (variables, conventions, current section)
- Claude:
  - Verifies formulas against the image
  - Corrects OCR errors using physics domain knowledge
  - Structures content with proper headings, numbered equations
  - Updates the inter-page context register

#### 5. Merge & Export (`src/merge.py`, `src/export.py`)
- Concatenates all rewritten pages in order
- Generates table of contents from detected sections
- Optionally compiles to PDF via Pandoc + LaTeX template

### Inter-Page Context System

A YAML-based context register persists across pages:

```yaml
document_title: "Mécanique des Fluides — Cours L3"
current_chapter: "3. Équations de Navier-Stokes"
current_section: "3.2 Forme intégrale"
variables:
  ρ: "masse volumique du fluide [kg/m³]"
  μ: "viscosité dynamique [Pa·s]"
  u: "champ de vitesse [m/s]"
  p: "pression [Pa]"
notation:
  - "Indices Einstein pour la sommation"
  - "Vecteurs en gras"
  - "Dérivée partielle: ∂/∂t"
page_number: 47
```

This ensures Claude understands `ρ` on page 50 even if it was only defined on page 3.

## Getting Started

### Prerequisites

- Python 3.11+
- [Poppler](https://poppler.freedesktop.org/) (`brew install poppler` on macOS)
- [Pandoc](https://pandoc.org/) + TeX Live (optional, for PDF export)

### Installation

```bash
git clone https://github.com/cmrabdu/stem-pipe.git
cd stem-pipe
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Copy and fill in your API keys
cp config.example.yaml config.yaml
```

### CLI Usage

```bash
# Process a single PDF
python pipeline.py cours_mecaflu.pdf

# Specify output format
python pipeline.py cours_mecaflu.pdf --format both

# Process with PDF export
python pipeline.py cours_mecaflu.pdf --pdf

# Reprocess only failed/missing pages
python pipeline.py cours_mecaflu.pdf --resume
```

### Web Interface

```bash
python server.py
# → http://localhost:8000
```

Drop your PDF, watch real-time progress per page, download when done.

## Web Interface

<div align="center">

```
┌──────────────────────────────────────────────────┐
│  STEM-Pipe                                       │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │                                          │    │
│  │     Drop PDF here or click to upload     │    │
│  │                                          │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  cours_mecaflu.pdf — 147 pages                   │
│  ████████████████░░░░░░░░░░  62% (91/147)        │
│                                                  │
│  Page 91: Rewriting with Claude...               │
│                                                  │
│  [Download .md]  [Download .pdf]  [View]         │
└──────────────────────────────────────────────────┘
```

</div>

Features:
- **Real-time progress** via WebSocket
- **Page preview** — see each page as it's processed
- **Error handling** — retry individual failed pages
- **History** — list of previously processed documents

## Cost Estimate

Based on Claude Opus ($5/$25 per M tokens) and Mathpix (~$0.01/page):

| Pages | Mathpix | Claude Opus | Total |
|-------|---------|-------------|-------|
| 50    | $0.50   | $4.50       | **~$5** |
| 100   | $1.00   | $9.00       | **~$10** |
| 300   | $3.00   | $27.00      | **~$30** |
| 1000  | $10.00  | $90.00      | **~$100** |

## Configuration

See [`config.example.yaml`](config.example.yaml) for all options. Key settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `extraction.dpi` | 400 | Image resolution (300–600) |
| `rewrite.model` | `claude-opus-4-20250514` | Claude model for rewriting |
| `rewrite.send_source_image` | true | Cross-reference image + OCR |
| `rewrite.language` | `fr` | Document language |
| `concurrency.extraction_batch_size` | 5 | Parallel OCR pages |
| `cache.enabled` | true | Resume interrupted runs |

## API Reference

### Python API

```python
from stem_pipe import Pipeline

pipe = Pipeline("config.yaml")
result = pipe.process("cours_mecaflu.pdf")

# Access individual pages
for page in result.pages:
    print(page.number, page.markdown[:100])

# Export
result.save_markdown("output/cours.md")
result.save_pdf("output/cours.pdf")  # requires pandoc
```

## License

MIT

---

<div align="center">

**Built for students, by a student.**

*Because knowledge trapped in image PDFs helps no one.*

</div>
