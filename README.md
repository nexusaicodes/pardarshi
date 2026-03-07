# Pardarshi

A web app for extracting portfolio tables from screenshots using OCR, computing portfolio breakdowns, and suggesting rebalancing actions.

Built with FastAPI and [surya](https://github.com/nexusaicodes/surya) for table extraction.

## Features

- **Table extraction** — Upload a screenshot of your holdings (e.g. from Kite/Zerodha) and extract structured table data via OCR
- **Portfolio computation** — Calculates current value per instrument (Qty x LTP) and percentage of total portfolio including cash
- **Rebalancing** — Set target allocation percentages and get buy/sell actions to reach them
- **Validation** — Expects a 4-column table (Instrument, Qty., Avg. cost, LTP) and flags malformed rows
- **Indian numeral formatting** — Values displayed with lakh/crore grouping (e.g. 12,34,567.89)

## Setup

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Running

```bash
uv run uvicorn app.main:app --reload
```

The app will be available at `http://localhost:8000`.

## Usage

### Web UI

1. Open `http://localhost:8000` in a browser
2. Upload a screenshot of your holdings table (PNG, JPG, TIFF, BMP, or WebP — max 1 MB)
3. Enter your cash balance
4. View the extracted table, portfolio breakdown, and optionally set rebalancing targets

### API

```bash
curl -X POST http://localhost:8000/api/extract \
  -F "file=@screenshot.png"
```

Returns the raw surya extraction result as JSON.

## Project Structure

```
app/
  main.py              # FastAPI app, lifespan (loads surya pipeline)
  config.py            # Upload limits, allowed extensions, OCR toggle
  dependencies.py      # Request-scoped pipeline dependency
  routers/
    ui.py              # HTML routes: /, /upload, /rebalance
    api.py             # JSON route: /api/extract
  services/
    extractor.py       # Runs surya pipeline on image bytes
    tabulator.py       # Table parsing, validation, portfolio math, rebalancing
    annotator.py       # Draws bounding box overlays on images
  templates/           # Jinja2 HTML templates
  static/              # CSS
tests/
  test_tabulator.py    # Unit tests for table parsing and validation
  test_rebalance_route.py
```

## Tests

```bash
uv run pytest
```
