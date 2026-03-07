from PIL import Image
from io import BytesIO

Image.MAX_IMAGE_PIXELS = 10_000_000  # ~10 megapixels; prevents decompression bombs


def extract_tables(pipeline, image_bytes: bytes, ocr: bool = True) -> dict:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    return pipeline.extract_tables(image, ocr=ocr)
