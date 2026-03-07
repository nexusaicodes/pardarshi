import base64
import copy
from io import BytesIO

from PIL import Image

Image.MAX_IMAGE_PIXELS = 10_000_000  # ~10 megapixels; prevents decompression bombs

from surya.debug.draw import draw_bboxes_on_image


def annotate_image(image_bytes: bytes, result: dict) -> str:
    """Draw bounding boxes on the image and return a base64 data URI."""
    image = Image.open(BytesIO(image_bytes)).convert("RGB")

    tables = result.get("tables", [])
    if not tables:
        return _to_data_uri(image)

    # Draw all tables' annotations on the same image.
    # For pipeline results, each table is a cropped region. We annotate each
    # table independently and tile them vertically below the original.
    annotated_tables = []
    for table in tables:
        rows = [cell["bbox"] for cell in table.get("rows", [])]
        cols = [cell["bbox"] for cell in table.get("cols", [])]
        cells = [cell["bbox"] for cell in table.get("cells", [])]
        row_labels = [f"Row {r.get('row_id', i)}" for i, r in enumerate(table.get("rows", []))]
        col_labels = [f"Col {c.get('col_id', i)}" for i, c in enumerate(table.get("cols", []))]

        # Rows + Cols overlay
        rc_img = copy.deepcopy(image)
        if rows:
            rc_img = draw_bboxes_on_image(rows, rc_img, labels=row_labels, label_font_size=20, color="blue")
        if cols:
            rc_img = draw_bboxes_on_image(cols, rc_img, labels=col_labels, label_font_size=20, color="red")

        # Cells overlay
        cell_img = copy.deepcopy(image)
        if cells:
            cell_img = draw_bboxes_on_image(cells, cell_img, color="green")

        annotated_tables.append(("Rows & Columns", rc_img))
        annotated_tables.append(("Cells", cell_img))

    if not annotated_tables:
        return _to_data_uri(image)

    # Stack all annotated images vertically
    total_width = max(img.width for _, img in annotated_tables)
    total_height = sum(img.height for _, img in annotated_tables)
    composite = Image.new("RGB", (total_width, total_height), (255, 255, 255))
    y_offset = 0
    for _, img in annotated_tables:
        composite.paste(img, (0, y_offset))
        y_offset += img.height

    return _to_data_uri(composite)


def _to_data_uri(image: Image.Image) -> str:
    buf = BytesIO()
    image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
