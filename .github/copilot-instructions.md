# Project Guidelines — Palimpsest (stem-pipe)

STEM PDF → LaTeX pipeline. Scanned/handwritten STEM documents are processed through OCR + LLM rewriting into clean, compilable LaTeX with proper math typesetting.

## Architecture

Sequential pipeline with inter-page context accumulation:

```
PDF → [Extract] → [Preprocess] → [OCR] → [Rewrite] → [Merge] → [Compile]
         ↓            ↓             ↓          ↓           ↓          ↓
     pdf2image     OpenCV       Mathpix    Claude/GPT   LaTeX      xelatex
     400 DPI      deskew,      or vision   per-page    assembly    2-pass
                  binarize     direct      + context
```

Two entry points:
- `pipeline.py` — CLI orchestrator (async, sequential per page)
- `server.py` — FastAPI web server with WebSocket progress streaming

### Key modules (`src/`)

| Module | Role |
|--------|------|
| `extract.py` | PDF → PIL Images (grayscale, configurable DPI) |
| `preprocess.py` | OpenCV: deskew (Hough), adaptive binarize, denoise |
| `ocr_mathpix.py` | Mathpix HTTP API integration |
| `rewrite.py` | LLM dispatch — `_rewrite_anthropic()` / `_rewrite_openai()` |
| `context.py` | `DocumentContext` dataclass — tracks variables, notation, sections across pages |
| `merge.py` | LaTeX preamble assembly + page concatenation |
| `export.py` | `xelatex` subprocess wrapper (2-pass compilation) |

### Data flow directories

- `.cache/<pdf_stem>/` — per-page stage results (`page_XXXX_{preprocessed,ocr,rewrite}`), enables `--resume`
- `uploads/` — temporary uploaded PDFs (cleaned after job completion)
- `output/` — final `.tex` + `.pdf` deliverables

## Build and Test

```bash
# Setup
pip install -r requirements.txt
cp config.example.yaml config.yaml   # then fill API keys
# macOS extras:
brew install poppler && brew install --cask basictex

# CLI
python pipeline.py document.pdf                          # defaults: o4-mini, vision-direct
python pipeline.py document.pdf --model claude-opus-4-20250514 --pdf --resume -v

# Web
python server.py   # → http://localhost:8000
```

No test suite yet. Validation is done by running the pipeline on sample PDFs.

## Conventions

- **Language**: French is hardcoded in system prompts and LaTeX preamble (`babel[french]`). UI is also French.
- **Provider abstraction**: `detect_provider(model)` routes to Anthropic or OpenAI client. Same public API `rewrite_page()`, different internal dispatch.
- **LLM output format**: LaTeX body fragment + `%%CONTEXT_UPDATE%%` separator + YAML context update block.
- **Config resolution**: `config.example.yaml` → `config.yaml` → CLI args (later overrides earlier).
- **Async pattern**: CLI uses `asyncio.run()`, server uses `asyncio.create_task()` for background jobs.
- **Retry**: Exponential backoff (3 retries, 2s base delay, doubles each time) on all API calls.
- **Cache keys**: `page_XXXX_<stage>.md` — zero-padded page numbers, one file per stage per page.

## Pitfalls

- **API keys in `config.yaml`**: plaintext, ensure it stays in `.gitignore`. Never commit real keys.
- **LaTeX engine required for PDF output**: `xelatex` must be on PATH (searches `/Library/TeX/texbin/` on macOS). Without it, only `.tex` is produced.
- **Special chars in filenames**: `&`, `_`, `%` in PDF names can break LaTeX output. Escaped in `merge_pages_latex()` but not everywhere.
- **Context growth**: `DocumentContext` grows unbounded across pages — very large PDFs (1000+) may cause token overflow.
- **Mathpix rate limits**: ~1000 pages/month on free tier. Use `--no-mathpix` (vision-direct) to bypass.

## Reference

See [README.md](../README.md) for full setup guide, cost estimates, and roadmap.
See [config.example.yaml](../config.example.yaml) for all configuration options with inline docs.
