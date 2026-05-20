# Palimpsest — audit (v0.2.0)

Internal punch list. Items marked ✅ are landed in this audit pass; ⏭ are deferred.

## Security

| # | Finding | Severity | Action |
|---|---------|----------|--------|
| S1 | `/api/upload` reads entire body into memory before size check — a 10 GB POST OOMs the server. | High | ✅ Added `PALIMPSEST_MAX_UPLOAD_MB` env var (default 60), reject before reading the bytes. |
| S2 | MIME type only checked by extension. Non-PDF with `.pdf` extension causes `pdf2image` to crash with 500. | Medium | ✅ Magic-byte check `%PDF-`. |
| S3 | WebSocket endpoint accepts any `Origin` (CSWSH possible). | Medium | ✅ Optional `PALIMPSEST_ALLOWED_ORIGINS` env var; if set, rejects unknown origins. |
| S4 | `/api/upload` has no auth and burns paid API credits per request. | Medium | ✅ Optional `PALIMPSEST_API_TOKEN` env var; if set, `/api/upload` requires `X-Palimpsest-Token` header. |
| S5 | `/api/jobs/{id}/download` indexes user-controlled `job_id`. | Low | ✓ Already safe: `job_id` is a server-issued UUID slice; only matches keys in the in-memory `jobs` dict. |

## Correctness / robustness

| # | Finding | Severity | Action |
|---|---------|----------|--------|
| C1 | `WebSocketDisconnect` cleanup calls `list.remove()` on a socket that may already be gone → ValueError 500. | Low | ✅ Wrapped in `try/except ValueError`. |
| C2 | `export.py` iterates `["/Library/TeX/texbin/xelatex", ..., "xelatex"]` through `shutil.which`; on Linux/Docker the absolute paths return `None` *and* fall back. Works, but inefficient. | Low | ✅ Check absolute paths via `Path().is_file()` first, then `shutil.which` for plain names. |
| C3 | `uploads/` is never garbage-collected; PDFs pile up forever. | Medium | ✅ `_purge_old_uploads()` on startup — removes files older than 7 days. |
| C4 | `_load_jobs_db` runs at import time before logging is configured. | Cosmetic | ⏭ Acceptable — errors return `{}` and don't crash. |
| C5 | `pipeline.py` reads `gen_pdf` config flag but **always** generates a PDF. | Cosmetic | ✅ Removed the dead read. |

## Dead / misleading configuration

`config.example.yaml` declares fields that are never read:

| Field | Read? |
|-------|-------|
| `preprocessing.enabled` | ❌ |
| `rewrite.language` | ❌ |
| `rewrite.output_style` | ❌ |
| `output.format` | ❌ |
| `output.generate_pdf` | ❌ (always on) |

✅ Removed all five; documented only what the pipeline actually honors, plus the new `output.include_palimpsest_blurb` toggle.

## Tests

No `tests/` directory existed.

✅ Added `tests/test_sanitize.py` and `tests/test_merge.py` — covers fence stripping, banned-macro neutering, paragraph-env conversion, section-number stripping, slugify, title escaping, end-to-end document assembly.

## Documentation gaps

- ✅ README now lists `poppler-utils` as a required system dependency (it backs `pdf2image`).
- ✅ README documents the new env vars (`PALIMPSEST_API_TOKEN`, `PALIMPSEST_ALLOWED_ORIGINS`, `PALIMPSEST_MAX_UPLOAD_MB`).

## Deferred (intentionally)

- `pyproject.toml` migration — `requirements.txt` is fine for the current scope.
- Replacing CDN React+Babel with a build step — would force the project into a Node toolchain; the runtime cost is negligible for student usage.
- Rate-limiting middleware — covered functionally by the optional API-token gate.
