<div align="center">

# Palimpsest

**Turn your professors' ancient scanned PDFs into clean, modern LaTeX documents.**

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-yellow.svg)](https://python.org)

[Getting Started](#getting-started) · [How It Works](#how-it-works) · [Web UI](#web-interface) · [Cost](#cost-estimate) · [Changelog](CHANGELOG.md)

</div>

---

## Why?

I'm a student. My professors are great at teaching, but their course materials are… stuck in the past. We're talking **scanned photocopies of handwritten notes from the 80s** — pages photographed with CamScanner, image-only PDFs with no text layer, no copy-paste, no search. Dense physics, statics, fluid dynamics, differential equations, tensor notation — all locked in blurry images.

I tried the usual OCR tools. Tesseract chokes on `∂²u/∂x²`. Google Docs mangling integrals. Nothing works for STEM content.

So I built **Palimpsest** — a simple tool that takes these old scanned PDFs and rewrites them as proper, structured, beautifully typeset LaTeX documents. Drop a PDF, get a clean `.tex` and compiled `.pdf` back. That's it.

This is a **free, open-source tool made by a student, for students.** No profit, no startup, no catch. Just a way to make old knowledge accessible again.

> **palimpsest** */ˈpalɪmp.sɛst/* — a manuscript page that has been scraped clean and written over, so that traces of the original text show through. That's exactly what this tool does: it reads through the noise and rewrites the content cleanly.

---

## What It Does

```
 Scanned PDF               Palimpsest                Clean LaTeX + PDF
┌─────────────┐    ┌─────────────────────┐    ┌──────────────────────┐
│ ░░▒▒▓▓██░░  │    │  Extract pages      │    │ \section{Statique}   │
│ blurry scan │───▶│  Preprocess (OpenCV) │───▶│ \begin{equation}     │
│ no text layer│    │  OCR via AI vision   │    │   \vec{F} = m\vec{a} │
│ ∂²u/∂x² = ? │    │  Rewrite to LaTeX   │    │ \end{equation}       │
└─────────────┘    │  Compile with xelatex│    │ Proper figures, TOC  │
                   └─────────────────────┘    └──────────────────────┘
```

### Features

- **AI-powered OCR** — uses vision models (OpenAI, Anthropic) to read formulas directly from images
- **LaTeX output** — proper `\section{}`, `\begin{equation}`, `\begin{tikzpicture}` — not some Markdown approximation
- **Inter-page memory** — variables and notation defined on page 3 are remembered on page 50
- **Fault-tolerant** — page-by-page caching; resume interrupted runs from where they stopped
- **Web interface** — drag & drop a PDF, watch real-time progress, download the result
- **Job history** — all jobs are persisted to disk; retrieve previous documents even after a page refresh
- **Multi-model** — supports 8 models across OpenAI and Anthropic (o4-mini is the sweet spot)
- **No Mathpix needed** — vision-direct mode lets the LLM do OCR straight from images (free, no signup)
- **Optional Mathpix** — for maximum formula accuracy on particularly rough scans
- **Overleaf compatible** — output `.tex` uses `iftex` conditional: compiles with both xelatex and pdflatex

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **Poppler** — for PDF-to-image extraction
- **BasicTeX** or **TeX Live** — for compiling LaTeX to PDF

```bash
# macOS
brew install poppler
brew install --cask basictex

# Ubuntu / Debian
sudo apt install poppler-utils texlive-latex-extra texlive-lang-french
```

### Installation

```bash
git clone https://github.com/cmrabdu/Palimpsest.git
cd Palimpsest
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Configuration

```bash
cp config.example.yaml config.yaml
```

Open `config.yaml` and add your API key. You only need **one** provider:

| Provider | Key needed | Best model | Cost |
|----------|-----------|------------|------|
| OpenAI | `api_keys.openai.api_key` | **o4-mini** (recommended) | ~$0.04/page |
| Anthropic | `api_keys.anthropic.api_key` | claude-opus-4-20250514 | ~$0.15/page |

### Usage

#### Web interface (recommended)

```bash
python server.py
# → open http://localhost:8000
```

Drop your PDF, pick a model, hit Start. Watch page-by-page progress in real time. Download the compiled PDF when done.

- **`/`** — Upload a PDF and track real-time processing
- **`/jobs.html`** — History of all processed documents (with download links)



#### Command line

```bash
# Basic usage (vision-direct mode, o4-mini)
python pipeline.py lecture_notes.pdf

# Use a different model
python pipeline.py lecture_notes.pdf --model gpt-4.1

# Use Mathpix OCR instead of vision-direct
python pipeline.py lecture_notes.pdf --engine mathpix
```

---

## How It Works

### Pipeline

1. **Extract** — `pdf2image` converts each page at 400 DPI
2. **Preprocess** — OpenCV applies adaptive binarization, deskew (Hough transform), and denoising
3. **OCR** — the AI vision model reads the page image directly and produces LaTeX
4. **Context** — a YAML register tracks variables, notation, and section structure across pages
5. **Merge** — all pages are assembled into a single `.tex` document with a full academic preamble
6. **Compile** — `xelatex` produces a clean PDF with table of contents

### Project Structure

```
Palimpsest/
├── pipeline.py              # CLI entry point
├── server.py                # FastAPI web server
├── config.example.yaml      # Configuration template
├── requirements.txt         # Python dependencies
├── VERSION                  # Semver version file
├── CHANGELOG.md             # Release history
├── Dockerfile               # Container build (includes texlive-science)
├── docker-compose.yml       # Service configuration
├── src/
│   ├── extract.py           # PDF → images (pdf2image + poppler)
│   ├── preprocess.py        # OpenCV: binarize, deskew, denoise
│   ├── ocr_mathpix.py       # Optional Mathpix API
│   ├── rewrite.py           # AI rewrite engine (OpenAI / Anthropic)
│   ├── context.py           # Inter-page context accumulator
│   ├── merge.py             # LaTeX document assembly
│   └── export.py            # xelatex PDF compilation
├── web/
│   ├── index.html           # Main upload & progress UI
│   ├── jobs.html            # Job history & download page
│   └── favicon.svg          # App icon
└── .cache/
    └── jobs_history.json    # Persistent job records (auto-created)
```

### Supported Models

| Provider | Model | Notes |
|----------|-------|-------|
| OpenAI | **o4-mini** | Best value — recommended default |
| OpenAI | gpt-4.1 | High quality, higher cost |
| OpenAI | gpt-4o | Good balance |
| OpenAI | gpt-4.1-mini | Budget option |
| OpenAI | gpt-4.1-nano | Cheapest, lower quality |
| OpenAI | o1 | Reasoning model |
| Anthropic | claude-opus-4-20250514 | Best quality overall |
| Anthropic | claude-sonnet-4-20250514 | Good quality, moderate cost |

---

## Cost Estimate

Using **o4-mini** (vision-direct, no Mathpix):

| Pages | Estimated cost |
|-------|---------------|
| 15 | ~$0.60 |
| 50 | ~$2.00 |
| 100 | ~$4.00 |
| 300 | ~$12.00 |

Costs vary based on page complexity and image size. Vision-direct mode avoids Mathpix fees entirely.

---

## Configuration Reference

See [`config.example.yaml`](config.example.yaml) for all options.

| Setting | Default | Description |
|---------|---------|-------------|
| `extraction.dpi` | 400 | Image resolution (300–600) |
| `extraction.engine` | `vision` | `vision` (free) or `mathpix` |
| `rewrite.model` | `o4-mini` | AI model for OCR + rewrite |
| `rewrite.send_source_image` | `true` | Send page image for cross-reference |
| `rewrite.language` | `fr` | Document language |
| `cache.enabled` | `true` | Resume interrupted runs |

---

## Roadmap

- [ ] Batch API support for lower cost on large documents
- [ ] Smart model routing (fast model for simple pages, powerful model for complex ones)
- [ ] Improved TikZ generation for mechanical diagrams
- [x] GitHub Actions CI/CD for self-hosted deployment
- [ ] Multi-language support (currently optimized for French STEM)
- [ ] Better error recovery for LaTeX compilation failures
- [ ] Persistent job storage with database backend (currently JSON flat file)
- [ ] Authentication for the hosted instance

---

## Contributing

This is a student project and contributions are welcome! If you're also stuck with terrible scanned PDFs, feel free to open an issue or submit a PR.

## License

[MIT](LICENSE) — do whatever you want with it.

---

<div align="center">

**Built for students, by a student.**

*Because knowledge trapped in image PDFs helps no one.*

Made with ❤️ by [Abdullah Camur](https://cmrabdu.com) · [@cmrabdu](https://github.com/cmrabdu)

</div>
