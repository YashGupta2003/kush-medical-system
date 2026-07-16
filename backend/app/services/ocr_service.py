"""
OCR with automatic fallback and automatic rotation correction:

  1. Try Google Cloud Vision first (most accurate, needs billing enabled).
  2. If that fails for ANY reason, fall back to Tesseract (free, offline).
  3. Tesseract additionally auto-detects the correct rotation (0/90/180/270)
     since phone photos are very often sideways - this fixes parsing
     failures caused by rotated bill photos.

Config (backend/.env):
  OCR_ENGINE=auto       -> try Google first, fall back to Tesseract (default)
  OCR_ENGINE=google      -> Google only, no fallback
  OCR_ENGINE=tesseract   -> Tesseract only, fully free/offline
"""
import os
from dataclasses import dataclass
from io import BytesIO
from typing import List

from app.config import settings


@dataclass
class Word:
    text: str
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    @property
    def y_center(self) -> float:
        return (self.y_min + self.y_max) / 2

    @property
    def x_center(self) -> float:
        return (self.x_min + self.x_max) / 2


def _run_google_vision(image_bytes: bytes) -> tuple[str, List[Word]]:
    from google.cloud import vision

    os.environ.setdefault(
        "GOOGLE_APPLICATION_CREDENTIALS", settings.google_application_credentials
    )
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)
    response = client.document_text_detection(image=image)

    if response.error.message:
        raise RuntimeError(f"Vision API error: {response.error.message}")

    full_text = response.full_text_annotation.text if response.full_text_annotation else ""

    words: List[Word] = []
    for page in response.full_text_annotation.pages:
        for block in page.blocks:
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    text = "".join(symbol.text for symbol in word.symbols)
                    xs = [v.x for v in word.bounding_box.vertices]
                    ys = [v.y for v in word.bounding_box.vertices]
                    words.append(
                        Word(text=text, x_min=min(xs), x_max=max(xs), y_min=min(ys), y_max=max(ys))
                    )
    return full_text, words


def _preprocess_for_tesseract(image):
    from PIL import ImageOps, ImageFilter
    gray = ImageOps.grayscale(image)
    contrasted = ImageOps.autocontrast(gray)
    return contrasted.filter(ImageFilter.SHARPEN)


def _score_orientation(image) -> tuple[float, dict]:
    """
    Runs Tesseract on one candidate orientation and scores it by total
    confident-word count and average confidence - used to auto-pick the
    correct rotation without relying on Tesseract's own (often unreliable
    on invoice photos) orientation-detection feature.
    """
    import pytesseract
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    confidences = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf_raw = str(data["conf"][i])
        conf = int(conf_raw) if conf_raw.lstrip("-").isdigit() else -1
        if text and conf >= 30:
            confidences.append(conf)
    score = len(confidences) * (sum(confidences) / len(confidences) if confidences else 0)
    return score, data


def _auto_rotate_and_ocr(processed_image):
    """
    Tries 0/90/180/270 degree rotations and keeps whichever orientation
    Tesseract reads most confidently. Phone photos are very often rotated
    (landscape bill photographed sideways), and parsing silently fails if
    the text geometry is sideways - this fixes that at the source instead
    of trying to patch the row/column math around it.
    """
    best_score, best_data, best_angle = -1, None, 0
    for angle in (0, 90, 180, 270):
        candidate = processed_image.rotate(angle, expand=True) if angle else processed_image
        score, data = _score_orientation(candidate)
        if score > best_score:
            best_score, best_data, best_angle = score, data, angle
    print(f"[OCR] auto-rotation chose {best_angle} degrees (confidence score={best_score:.1f})")
    return best_data


def _run_tesseract(image_bytes: bytes) -> tuple[str, List[Word]]:
    import pytesseract
    from PIL import Image

    image = Image.open(BytesIO(image_bytes))
    processed = _preprocess_for_tesseract(image)

    data = _auto_rotate_and_ocr(processed)
    full_text = " ".join(t for t in data["text"] if t.strip())

    words: List[Word] = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf_raw = str(data["conf"][i])
        conf = int(conf_raw) if conf_raw.lstrip("-").isdigit() else -1
        if not text or conf < 30:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        words.append(Word(text=text, x_min=x, x_max=x + w, y_min=y, y_max=y + h))

    return full_text, words


def run_ocr(image_bytes: bytes) -> tuple[str, List[Word]]:
    engine = (settings.ocr_engine or "auto").lower()

    if engine == "tesseract":
        return _run_tesseract(image_bytes)

    if engine == "google":
        return _run_google_vision(image_bytes)

    try:
        return _run_google_vision(image_bytes)
    except Exception as google_error:
        print(f"[OCR] Google Vision failed ({google_error}); falling back to Tesseract.")
        try:
            return _run_tesseract(image_bytes)
        except Exception as tesseract_error:
            raise RuntimeError(
                "Both OCR engines failed. "
                f"Google error: {google_error} | Tesseract error: {tesseract_error}"
            )
