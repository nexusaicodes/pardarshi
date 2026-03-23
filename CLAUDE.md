# CLAUDE.md

## Project Overview

Pardarshi is a FastAPI web app that extracts stock portfolio tables from screenshots using the surya OCR pipeline, computes portfolio summaries, and suggests rebalancing trades.

## Tech Stack

- **Python 3.10+**, managed with **uv**
- **FastAPI** with Jinja2 templates (server-rendered HTML)
- **surya** (`surya-tabular-ocr` package from `nexusaicodes/surya` fork) for table extraction OCR
- **Pillow** for image handling
- **pytest** for tests, **httpx** as test client (dev dependency)

## Key Commands

- `uv sync` — install dependencies
- `uv run uvicorn app.main:app --reload` — run dev server
- `uv run pytest` — run tests

## Architecture

- The surya `TableExtractionPipeline` is loaded once at startup via FastAPI lifespan and stored on `app.state.pipeline`
- It is injected into routes via `Depends(get_pipeline)` from `app/dependencies.py`
- Table extraction uses flexible column detection from header names (case-insensitive substring match)
- Two modes: **qty_ltp** (Symbol + Qty + LTP → compute value) or **present_value** (Symbol + Present Value → use directly)
- Extra columns (Buy avg., Buy value, etc.) are ignored
- Validation in `tabulator.py` strips HTML tags, parses numbers, and flags bad rows
- Portfolio math: `current_value = qty * ltp` or direct from Present Value, percentage of `(sum(values) + cash)`
- Rebalancing: computes buy/sell deltas from target percentages, checks cash sufficiency

## File Layout

- `app/main.py` — app factory, lifespan, static/template mounting
- `app/config.py` — constants (MAX_UPLOAD_BYTES=1MB, ALLOWED_EXTENSIONS, OCR_ENABLED)
- `app/routers/ui.py` — HTML routes (GET /, POST /upload, POST /rebalance)
- `app/routers/api.py` — JSON route (POST /api/extract)
- `app/services/extractor.py` — thin wrapper around surya pipeline
- `app/services/tabulator.py` — table row building, validation, portfolio computation, rebalancing logic
- `app/services/annotator.py` — draws bounding box debug overlays on images

## Conventions

- Indian numeral formatting for currency values (lakh/crore grouping)
- Upload limit is 1 MB to keep files in-memory (no disk spill)
- Images only: png, jpg, jpeg, tiff, bmp, webp
