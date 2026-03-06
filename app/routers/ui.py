from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse

from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, OCR_ENABLED
from app.dependencies import get_pipeline
from app.services.extractor import extract_tables
from app.services.tabulator import build_table_rows, compute_portfolio

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    from app.main import templates
    return templates.TemplateResponse("index.html", {"request": request})


@router.post("/upload", response_class=HTMLResponse)
def upload(
    request: Request,
    file: UploadFile = File(...),
    cash: float = Form(...),
    pipeline=Depends(get_pipeline),
):
    from app.main import templates

    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": f"Unsupported file type: .{ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        })

    image_bytes = file.file.read()
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": "File too large (max 20 MB).",
        })

    try:
        result = extract_tables(pipeline, image_bytes, ocr=OCR_ENABLED)
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": f"Processing failed: {e}",
        })

    # Build and validate table (use first table only)
    tables = result.get("tables", [])
    if not tables:
        return templates.TemplateResponse("result.html", {
            "request": request,
            "filename": file.filename,
            "error": "No tables were detected in this image.",
        })

    table_data = build_table_rows(tables[0])

    if not table_data["valid"]:
        return templates.TemplateResponse("result.html", {
            "request": request,
            "filename": file.filename,
            "table_data": table_data,
            "error": "Table validation failed. Check errors below.",
        })

    portfolio = compute_portfolio(table_data, cash)

    return templates.TemplateResponse("result.html", {
        "request": request,
        "filename": file.filename,
        "table_data": table_data,
        "portfolio": portfolio,
    })
