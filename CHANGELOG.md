# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
