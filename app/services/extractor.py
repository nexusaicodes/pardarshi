from PIL import Image
from io import BytesIO


def extract_tables(pipeline, image_bytes: bytes, ocr: bool = True) -> dict:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    return pipeline.extract_tables(image, ocr=ocr)
