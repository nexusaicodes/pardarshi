from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse

from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, OCR_ENABLED
from app.dependencies import get_pipeline
from app.services.extractor import extract_tables
from app.services.tabulator import build_table_rows

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    from app.main import templates
    return templates.TemplateResponse("index.html", {"request": request})


@router.post("/upload", response_class=HTMLResponse)
def upload(request: Request, file: UploadFile = File(...), pipeline=Depends(get_pipeline)):
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

    # Build row-wise table data for each detected table
    tables_data = []
    for table in result.get("tables", []):
        tables_data.append(build_table_rows(table))

    return templates.TemplateResponse("result.html", {
        "request": request,
        "filename": file.filename,
        "tables_data": tables_data,
    })
