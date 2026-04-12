# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
