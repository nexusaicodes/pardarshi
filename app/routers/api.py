import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, OCR_ENABLED
from app.dependencies import get_pipeline
from app.services.extractor import extract_tables

router = APIRouter()


@router.post("/extract")
def api_extract(file: UploadFile = File(...), pipeline=Depends(get_pipeline)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: .{ext}")

    image_bytes = file.file.read()
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 1 MB)")

    try:
        result = extract_tables(pipeline, image_bytes, ocr=OCR_ENABLED)
    except Exception as e:
        raise HTTPException(500, f"Processing failed: {e}")

    return {"status": "ok", "result": result}
