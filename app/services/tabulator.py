from collections import defaultdict


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
        tl_text = tl.get("text", "").strip()
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

    return {
        "col_ids": col_ids,
        "rows": rows,
    }
