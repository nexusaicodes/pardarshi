import re
from collections import defaultdict

_TAG_RE = re.compile(r"<[^>]+>")


def _bbox_overlap(a, b):
    """Compute intersection area of two [x1, y1, x2, y2] bboxes."""
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    if x1 >= x2 or y1 >= y2:
        return 0.0
    return (x2 - x1) * (y2 - y1)


def _bbox_area(b):
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def build_table_rows(table: dict) -> list[dict]:
    """Build row-wise data from a table result.

    Returns a list of dicts, one per table in the result:
        {
            "col_ids": [0, 1, 2, ...],  # sorted column ids
            "header_row_ids": set of row_ids marked as header
            "rows": [
                {"row_id": 0, "is_header": True, "cells": ["col0 text", "col1 text", ...]},
                ...
            ]
        }
    Each row's "cells" list is ordered by col_id to match col_ids.
    """
    cells = table.get("cells", [])
    text_lines = table.get("text_lines", [])

    # Assign each text line to the cell with the greatest overlap
    cell_texts = defaultdict(list)  # (row_id, col_id) -> list of (x1, text)
    for tl in text_lines:
        tl_bbox = tl.get("bbox")
        tl_text = _TAG_RE.sub("", tl.get("text", "")).strip()
        if not tl_bbox or not tl_text:
            continue

        tl_area = _bbox_area(tl_bbox)
        if tl_area == 0:
            continue

        best_cell = None
        best_overlap = 0
        for cell in cells:
            c_bbox = cell.get("bbox")
            if not c_bbox:
                continue
            overlap = _bbox_overlap(tl_bbox, c_bbox)
            if overlap > best_overlap:
                best_overlap = overlap
                best_cell = cell

        # Only assign if at least 30% of the text line overlaps a cell
        if best_cell and best_overlap / tl_area >= 0.3:
            key = (best_cell["row_id"], best_cell["col_id"])
            # Store x1 for left-to-right ordering within a cell
            cell_texts[key].append((tl_bbox[0], tl_text))

    # Gather all col_ids and row_ids
    col_ids = sorted({c["col_id"] for c in cells})
    row_ids = sorted({c["row_id"] for c in cells})
    header_rows = {c["row_id"] for c in cells if c.get("is_header")}

    rows = []
    for rid in row_ids:
        cell_values = []
        for cid in col_ids:
            texts = cell_texts.get((rid, cid), [])
            # Sort by x position, then join
            texts.sort(key=lambda t: t[0])
            cell_values.append(" ".join(t[1] for t in texts))
        rows.append({
            "row_id": rid,
            "is_header": rid in header_rows,
            "cells": cell_values,
        })

    return validate_table({
        "col_ids": col_ids,
        "rows": rows,
    })


EXPECTED_HEADERS = ["Instrument", "Qty.", "Avg. cost", "LTP"]
PORTFOLIO_HEADERS = ["Instrument", "Current Value", "% of Portfolio"]
_NUM_RE = re.compile(r"[^\d.]")


def _parse_number(text: str) -> str:
    """Strip non-numeric chars (except dot) and return cleaned number string."""
    cleaned = _NUM_RE.sub("", text)
    # Handle multiple dots — keep only the last one as decimal
    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    return cleaned


def validate_table(table_data: dict) -> dict:
    """Validate and normalize table to expected 4-column schema.

    Expected: Instrument (text) | Qty. (number) | Avg. cost (decimal) | LTP (decimal)

    Returns the table_data with added "errors" list and "valid" bool.
    Rows that don't conform are flagged but kept.
    """
    errors = []
    rows = table_data.get("rows", [])

    # Check column count
    if table_data["col_ids"] and len(table_data["col_ids"]) != 4:
        errors.append(f"Expected 4 columns, got {len(table_data['col_ids'])}")

    validated_rows = []
    for row in rows:
        cells = row["cells"]

        # Skip header rows from validation but normalize their text
        if row["is_header"]:
            validated_rows.append(row)
            continue

        # Must have exactly 4 cells
        if len(cells) != 4:
            row["row_errors"] = [f"Expected 4 cells, got {len(cells)}"]
            validated_rows.append(row)
            continue

        row_errors = []

        # Col 0: Instrument — should be non-empty text
        instrument = cells[0].strip()
        if not instrument:
            row_errors.append("Instrument is empty")
        cells[0] = instrument

        # Cols 1-3: numeric values
        for i, col_name in enumerate(["Qty.", "Avg. cost", "LTP"], start=1):
            raw = cells[i].strip()
            parsed = _parse_number(raw)
            if not parsed:
                row_errors.append(f"{col_name}: '{raw}' is not a valid number")
            else:
                try:
                    cells[i] = parsed
                except ValueError:
                    row_errors.append(f"{col_name}: '{raw}' could not be parsed")

        row["cells"] = cells
        if row_errors:
            row["row_errors"] = row_errors
        validated_rows.append(row)

    table_data["rows"] = validated_rows
    table_data["headers"] = EXPECTED_HEADERS
    table_data["errors"] = errors
    table_data["valid"] = len(errors) == 0 and all(
        "row_errors" not in r for r in validated_rows if not r["is_header"]
    )
    return table_data


def compute_portfolio(table_data: dict, cash: float) -> dict:
    """Compute portfolio summary from a validated table and cash amount.

    For each instrument: current_value = Qty * LTP
    portfolio_value = sum(current_values) + cash
    Each row gets a % of portfolio_value.
    """
    rows = []
    total_instrument_value = 0.0

    for row in table_data["rows"]:
        if row["is_header"]:
            continue
        cells = row["cells"]
        instrument = cells[0]
        qty = float(cells[1])
        ltp = float(cells[3])
        current_value = round(qty * ltp, 2)
        total_instrument_value += current_value
        rows.append({"instrument": instrument, "current_value": current_value})

    portfolio_value = total_instrument_value + cash

    # Compute percentages
    portfolio_rows = []
    for r in rows:
        pct = round((r["current_value"] / portfolio_value) * 100, 2) if portfolio_value else 0.0
        portfolio_rows.append([
            r["instrument"],
            f"{r['current_value']:,.2f}",
            f"{pct:.2f}%",
        ])

    # Append cash row
    cash_pct = round((cash / portfolio_value) * 100, 2) if portfolio_value else 0.0
    portfolio_rows.append(["Cash", f"{cash:,.2f}", f"{cash_pct:.2f}%"])

    return {
        "headers": PORTFOLIO_HEADERS,
        "rows": portfolio_rows,
        "portfolio_value": f"{portfolio_value:,.2f}",
    }
