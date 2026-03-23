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


def _fmt_indian(n: float) -> str:
    """Format a number with Indian numeral grouping (12,34,567.89)."""
    s = f"{n:.2f}"
    integer_part, decimal_part = s.split(".")
    negative = integer_part.startswith("-")
    if negative:
        integer_part = integer_part[1:]
    if len(integer_part) <= 3:
        formatted = integer_part
    else:
        last3 = integer_part[-3:]
        rest = integer_part[:-3]
        groups = []
        while rest:
            groups.append(rest[-2:])
            rest = rest[:-2]
        groups.reverse()
        formatted = ",".join(groups) + "," + last3
    return ("-" if negative else "") + formatted + "." + decimal_part


PORTFOLIO_HEADERS = ["Instrument", "Current Value", "% of Portfolio"]
_NUM_RE = re.compile(r"[^\d.]")

# Patterns for detecting columns by header text (case-insensitive substring match)
_HEADER_PATTERNS = {
    "name": ["symbol", "instrument", "stock", "scrip"],
    "qty": ["qty", "quantity"],
    "ltp": ["ltp", "last traded", "last price", "current price"],
    "present_value": ["present value", "current value", "market value", "mkt value"],
}


def _parse_number(text: str) -> str:
    """Strip non-numeric chars (except dot) and return cleaned number string."""
    cleaned = _NUM_RE.sub("", text)
    # Handle multiple dots — keep only the last one as decimal
    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    return cleaned


def _detect_columns(header_cells: list[str]) -> dict[str, int]:
    """Map logical column names to indices by matching header text."""
    cols = {}
    for i, cell in enumerate(header_cells):
        text = cell.strip().lower()
        for key, patterns in _HEADER_PATTERNS.items():
            if any(p in text for p in patterns):
                cols[key] = i
                break
    return cols


def validate_table(table_data: dict) -> dict:
    """Validate table with flexible column detection.

    Supported modes (detected from headers):
      Mode A: name + qty + ltp  → current_value = qty * ltp
      Mode B: name + present_value → current_value used directly

    Extra columns (Buy avg., Buy value, etc.) are ignored.
    Returns the table_data with added "errors", "valid", "mode", "col_map".
    """
    errors = []
    rows = table_data.get("rows", [])

    # Find header row and detect columns
    header_row = next((r for r in rows if r["is_header"]), None)
    col_map = _detect_columns(header_row["cells"]) if header_row else {}

    # Determine mode
    has_name = "name" in col_map
    has_qty_ltp = "qty" in col_map and "ltp" in col_map
    has_pv = "present_value" in col_map

    if has_name and has_pv:
        mode = "present_value"
    elif has_name and has_qty_ltp:
        mode = "qty_ltp"
    else:
        missing = []
        if not has_name:
            missing.append("Symbol/Instrument")
        if not has_pv and not has_qty_ltp:
            missing.append("(Qty + LTP) or Present Value")
        errors.append(f"Could not detect required columns. Missing: {', '.join(missing)}")
        mode = None

    num_cols = len(table_data["col_ids"]) if table_data["col_ids"] else 0

    validated_rows = []
    for row in rows:
        cells = row["cells"]

        if row["is_header"]:
            validated_rows.append(row)
            continue

        if len(cells) != num_cols:
            row["row_errors"] = [f"Expected {num_cols} cells, got {len(cells)}"]
            validated_rows.append(row)
            continue

        if mode is None:
            validated_rows.append(row)
            continue

        row_errors = []
        name_idx = col_map["name"]
        instrument = cells[name_idx].strip()
        if not instrument:
            row_errors.append("Instrument/Symbol is empty")

        if mode == "qty_ltp":
            for key, label in [("qty", "Qty."), ("ltp", "LTP")]:
                idx = col_map[key]
                raw = cells[idx].strip()
                parsed = _parse_number(raw)
                if not parsed:
                    row_errors.append(f"{label}: '{raw}' is not a valid number")
                else:
                    cells[idx] = parsed
        else:  # present_value
            idx = col_map["present_value"]
            raw = cells[idx].strip()
            parsed = _parse_number(raw)
            if not parsed:
                row_errors.append(f"Present Value: '{raw}' is not a valid number")
            else:
                cells[idx] = parsed

        row["cells"] = cells
        if row_errors:
            row["row_errors"] = row_errors
        validated_rows.append(row)

    # Build display headers from original header row
    if header_row:
        table_data["headers"] = header_row["cells"]
    else:
        table_data["headers"] = [f"Col {i}" for i in range(num_cols)]

    table_data["rows"] = validated_rows
    table_data["mode"] = mode
    table_data["col_map"] = col_map
    table_data["errors"] = errors
    table_data["valid"] = mode is not None and len(errors) == 0 and all(
        "row_errors" not in r for r in validated_rows if not r["is_header"]
    )
    return table_data


def compute_portfolio(table_data: dict, cash: float) -> dict:
    """Compute portfolio summary from a validated table and cash amount.

    Mode qty_ltp:      current_value = qty * ltp
    Mode present_value: current_value read directly
    """
    rows = []
    total_instrument_value = 0.0
    mode = table_data["mode"]
    col_map = table_data["col_map"]

    for row in table_data["rows"]:
        if row["is_header"]:
            continue
        cells = row["cells"]
        instrument = cells[col_map["name"]]

        if mode == "qty_ltp":
            qty = float(cells[col_map["qty"]])
            ltp = float(cells[col_map["ltp"]])
            current_value = round(qty * ltp, 2)
        else:  # present_value
            current_value = round(float(cells[col_map["present_value"]]), 2)

        total_instrument_value += current_value
        rows.append({"instrument": instrument, "current_value": current_value})

    portfolio_value = total_instrument_value + cash

    # Compute percentages
    portfolio_rows = []
    for r in rows:
        pct = round((r["current_value"] / portfolio_value) * 100, 2) if portfolio_value else 0.0
        portfolio_rows.append([
            r["instrument"],
            _fmt_indian(r["current_value"]),
            f"{pct:.2f}%",
        ])

    # Append cash row
    cash_pct = round((cash / portfolio_value) * 100, 2) if portfolio_value else 0.0
    portfolio_rows.append(["Cash", _fmt_indian(cash), f"{cash_pct:.2f}%"])

    # Raw data for rebalancing (instrument -> current_value)
    instruments_raw = {r["instrument"]: r["current_value"] for r in rows}

    return {
        "headers": PORTFOLIO_HEADERS,
        "rows": portfolio_rows,
        "portfolio_value": _fmt_indian(portfolio_value),
        "portfolio_value_raw": portfolio_value,
        "cash_raw": cash,
        "instruments_raw": instruments_raw,
    }


def rebalance(portfolio: dict, targets: dict[str, int]) -> dict:
    """Compute rebalancing actions given target percentages.

    Args:
        portfolio: output from compute_portfolio (with raw fields)
        targets: {instrument_name: ideal_percentage} e.g. {"ARTSON": 10, "MSPL": 5}

    Returns dict with:
        "actions": list of {instrument, current_value, target_value, delta, action}
        "rebalanced_rows": updated portfolio rows
        "shortfall": float (0 if sufficient cash)
        "error": str or None
    """
    pv = portfolio["portfolio_value_raw"]
    cash = portfolio["cash_raw"]
    instruments = dict(portfolio["instruments_raw"])  # copy

    # Compute deltas: target_value - current_value
    actions = []
    for instrument, ideal_pct in targets.items():
        current_value = instruments.get(instrument, 0.0)
        target_value = round(pv * ideal_pct / 100, 2)
        delta = round(target_value - current_value, 2)
        actions.append({
            "instrument": instrument,
            "current_value": current_value,
            "current_value_fmt": _fmt_indian(current_value),
            "target_value": target_value,
            "target_value_fmt": _fmt_indian(target_value),
            "delta": delta,
            "delta_fmt": _fmt_indian(abs(delta)),
            "action": "Sell" if delta < 0 else "Buy" if delta > 0 else "Hold",
        })

    # Order: sells first, then buys
    sells = [a for a in actions if a["delta"] < 0]
    buys = [a for a in actions if a["delta"] > 0]
    holds = [a for a in actions if a["delta"] == 0]

    # Simulate: apply sells first to increase cash
    sim_cash = cash
    for a in sells:
        sim_cash += abs(a["delta"])

    # Check if cash is sufficient for all buys
    total_buy = sum(a["delta"] for a in buys)
    if total_buy > sim_cash:
        shortfall = round(total_buy - sim_cash, 2)
        return {
            "actions": sells + buys + holds,
            "rebalanced_rows": None,
            "shortfall": shortfall,
            "error": f"Insufficient cash. Short by {_fmt_indian(shortfall)}. Reduce targets or sell more.",
        }

    # Apply changes
    new_cash = sim_cash
    for a in buys:
        new_cash -= a["delta"]
    new_cash = round(new_cash, 2)

    # Update instrument values
    for a in sells + buys:
        instruments[a["instrument"]] = a["target_value"]

    # Build rebalanced portfolio rows
    new_pv = sum(instruments.values()) + new_cash
    rebalanced_rows = []
    for name, value in instruments.items():
        pct = round((value / new_pv) * 100, 2) if new_pv else 0.0
        rebalanced_rows.append([name, _fmt_indian(value), f"{pct:.2f}%"])

    cash_pct = round((new_cash / new_pv) * 100, 2) if new_pv else 0.0
    rebalanced_rows.append(["Cash", _fmt_indian(new_cash), f"{cash_pct:.2f}%"])

    return {
        "actions": sells + buys + holds,
        "rebalanced_rows": rebalanced_rows,
        "portfolio_value": _fmt_indian(new_pv),
        "shortfall": 0,
        "error": None,
    }
