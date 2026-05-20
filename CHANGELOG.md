# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Palimpsest cover blurb is now in English** — reads the same regardless of the document's working language.

### Added
- **`tests/`** — `pytest` suite covering the sanitizer (fence stripping, banned macro neutering, section-number rules, idempotency) and the document assembler. 31 tests, runs in <100 ms.
- **Runtime hardening** (audit pass):
  - `PALIMPSEST_API_TOKEN` env var → optional bearer-style auth on `/api/upload`.
  - `PALIMPSEST_MAX_UPLOAD_MB` → hard size cap (default 60 MB) checked against `Content-Length` *and* enforced while streaming.
  - `PALIMPSEST_ALLOWED_ORIGINS` → CSV allowlist on the WebSocket `Origin` header (defeats CSWSH).
  - `PALIMPSEST_UPLOAD_RETENTION_DAYS` → auto-purges old uploads at server start.
  - Magic-byte (`%PDF-`) check on every upload — rejects extension-only PDFs before they reach `pdf2image`.
- `AUDIT.md` documenting the security / correctness pass.

### Fixed
- WebSocket disconnect no longer 500s when the socket has already been removed (`list.remove` → `try/except ValueError`).
- `src/export.py` LaTeX-engine discovery: absolute paths via `Path.is_file()` first, then `shutil.which()` for `xelatex` / `pdflatex` on `$PATH` (Linux / Docker).
- Dropped dead config flags from `config.example.yaml` (`preprocessing.enabled`, `rewrite.language`, `rewrite.output_style`, `output.format`, `output.generate_pdf`) — only fields the pipeline actually reads remain.
- Removed dead `gen_pdf` read in `pipeline.py` (PDF was always generated regardless).

## [0.2.0] — 2026-05-20

### Added
- **Brand kit** — full logo / mark / favicon / banner / OG-image set under `web/brand/`, served via `/brand/...` and showcased at `/brand.html`.
- **Palimpsest cover page** — every compiled `.tex` / `.pdf` now opens with a clean titlepage carrying the detected title, subtitle (discipline), author, and a generic Palimpsest blurb with a link to the project repo. Toggle via `output.include_palimpsest_blurb` in `config.yaml`.
- **LaTeX sanitizer** (`src/sanitize.py`) — per-page post-pass that scrubs the patterns most likely to break Overleaf compilation: leaking ```` ```latex ```` fences, forbidden physics-package macros (`\dv`, `\pdv`, `\qty`), `\begin{paragraph}{...}` environment misuse, `$$..$$` display blocks, orphan `tikzpicture` blocks, bare leading-dash lists, leading numeric prefixes in section titles, unbalanced `$`.
- **Document metadata extraction** — prompts now require the LLM to emit `document_title`, `document_subtitle`, `discipline`, and `author` (when visible) as part of the YAML context block on page 1; values flow into the cover page.
- **Slugged output filenames** — output `.tex` / `.pdf` use a clean ASCII slug of the detected title instead of the raw upload filename.
- **Resilient preamble** — `adjustbox` is now loaded with `\IfFileExists` + a no-op stub, so PDF compile works on minimal LaTeX installs.

### Changed
- Tightened the rewrite system prompts (Anthropic + OpenAI, both with and without image): explicit ban on ```` ``` ```` fences, `\maketitle`, `\tableofcontents`, `\begin{document}`, and `\begin{paragraph}` environments; clarified the YAML metadata fields.
- `merge.py` now renders a custom `\begin{titlepage}` block in place of `\maketitle` and routes all user-supplied strings through `sanitize_title()` (full LaTeX-special escaping, not just `_` / `&`).

## [0.1.1]

### Changed
- **Complete UI redesign** — "workshop × terminal" high-fidelity design across `/` and `/jobs.html`. Paper-and-ink left half (dropzone + specimen config) seamed to a terminal right half (stage chips, weighted progress bar, live `pipeline.log` tail, output buttons). The archive register becomes a ledger with stamped masthead, stats cards, filter pills, and live polling.
- React-based front-end (CDN React 18 + Babel standalone) replaces the previous vanilla DOM rendering. Shared component library in `web/assets/components.jsx`; pages compose `Workshop`, `MobileWorkshop`, and `JobsPage`.
- Konami code switches between *ink-blue* and *parchment* themes (was dark/parchemin).
- Workshop URL accepts `?job=<id>` to resume tracking an in-flight pipeline; the archive's "view live" button links here.
- Stage chips map server progress events to four columns — `preprocess → ocr → rewrite → compile` — with weighted overall progress (0-25% / 25-55% / 55-95% / 95-100%).

### Fixed
- `/api/jobs/list` and `/api/jobs/latest` were being shadowed by `/api/jobs/{job_id}` due to FastAPI route declaration order. Declared the literal-path routes first so they match correctly.

### Added
- `app.mount("/assets", StaticFiles(...))` to serve the new CSS/JSX bundles.
- File-picker `clear` action on the dropzone (X button beside the staged-file row).

### Added
- Persistent job history — all jobs saved to `.cache/jobs_history.json`, survives server restarts
- New `/api/jobs/list` endpoint — list all jobs (newest first), filterable by status
- New `/api/jobs/latest` endpoint — returns the most recent job
- New `web/jobs.html` page — history view with stats cards, status filter, filename search, and download buttons for completed jobs
- Favicon: `web/favicon.svg` — dark background, bold blue `P`, `//` accent, served via `/favicon.svg` route
- `web/index.html` full UI redesign: Inter + JetBrains Mono (Google Fonts), CSS custom properties, film-grain overlay, ambient radial glow, scanner sweep animation on upload zone, inline SVG document icon with math content, shimmer progress bar, pulse status dot, slideUp/slideDown entry animations, toast notification system
- Easter egg 1: logo click ×5 → console LaTeX poem + toast notification
- Easter egg 2: Konami code (↑↑↓↓←→←→BA) → toggles Mode Parchemin (parchment palette + serif font)
- Easter egg 3: HTML comment at top of `index.html` (`\documentclass[mystique]{palimpsest}`)
- Credits footer on all pages: Made with ❤️ by @cmrabdu, GitHub link, cmrabdu.com link
- Header "Historique" link to `/jobs.html`
- `timestamp` field on all job records (ISO 8601 UTC)
- `job_id` field included in all persisted job records

### Fixed
- **xelatex crash** (`inputenc`+`fontenc` incompatible with xelatex) — replaced with `iftex` conditional: xelatex/LuaTeX use `fontspec`, pdflatex uses `inputenc`+`fontenc`. LaTeX output now compiles correctly with both xelatex (server) and pdflatex (Overleaf)
- **Anthropic 400 error** (image >5MB) — images now saved as JPEG quality=85 with iterative halving if still >4MB
- **PDF button serving `.tex`** — removed fallback that silently served `.tex` as PDF; now returns honest JSON error and disables PDF button in UI when compilation failed
- **Docker missing LaTeX packages** — added `texlive-science` to Dockerfile (provides `siunitx.sty`, required for `\si{}`)
- **`physics` package removed** — replaced `\usepackage{physics}` with `mathtools` + manual `\DeclarePairedDelimiter` for `\abs`/`\norm` (avoids definition conflicts with modern amsmath)

## [0.1.0] - 2026-04-12

### Added
- Core pipeline: scanned PDF → LaTeX → compiled PDF
- Vision-direct mode: LLM performs OCR directly from page images (no Mathpix needed)
- Optional Mathpix OCR integration for maximum accuracy on complex formulas
- Multi-provider support: OpenAI (o4-mini, gpt-4.1, gpt-4o, o1, gpt-4.1-mini, gpt-4.1-nano) and Anthropic (Claude Opus, Claude Sonnet)
- OpenCV preprocessing: adaptive binarization, Hough-based deskew, denoising
- Inter-page context accumulator (variables, notation, section structure carry across pages)
- Page-level caching with resume support for interrupted runs
- xelatex PDF compilation with full academic preamble (amsmath, physics, tikz, siunitx, etc.)
- FastAPI web interface with WebSocket real-time progress
- CLI with `--no-mathpix`, `--model`, `--pdf` flags
- Retry with exponential backoff on API errors
- Dark-themed single-page web UI

[Unreleased]: https://github.com/cmrabdu/Palimpsest/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/cmrabdu/Palimpsest/releases/tag/v0.1.0
