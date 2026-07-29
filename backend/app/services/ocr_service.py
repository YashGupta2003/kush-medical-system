import os
from dataclasses import dataclass
from io import BytesIO
from typing import List

from app.config import settings
from app.core.logging import get_logger

logger = get_logger("ocr_service")


@dataclass
class Word:
    text: str
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    confidence: float = 100.0

    @property
    def y_center(self) -> float:
        return (self.y_min + self.y_max) / 2

    @property
    def x_center(self) -> float:
        return (self.x_min + self.x_max) / 2


@dataclass
class OcrResult:
    full_text: str
    words: List[Word]
    avg_confidence: float
    engine_used: str


def _run_google_vision(image_bytes: bytes) -> OcrResult:
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
    confidences = []
    for page in response.full_text_annotation.pages:
        for block in page.blocks:
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    text = "".join(symbol.text for symbol in word.symbols)
                    xs = [v.x for v in word.bounding_box.vertices]
                    ys = [v.y for v in word.bounding_box.vertices]
                    conf = float(getattr(word, "confidence", 0.95)) * 100
                    confidences.append(conf)
                    words.append(
                        Word(text=text, x_min=min(xs), x_max=max(xs),
                             y_min=min(ys), y_max=max(ys), confidence=conf)
                    )
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return OcrResult(full_text=full_text, words=words, avg_confidence=avg_conf, engine_used="google")


def _preprocess_for_tesseract(image):
    from PIL import ImageOps, ImageFilter
    gray = ImageOps.grayscale(image)
    contrasted = ImageOps.autocontrast(gray)
    return contrasted.filter(ImageFilter.SHARPEN)


def _score_orientation(image) -> tuple[float, dict]:
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
    best_score, best_data, best_angle = -1, None, 0
    for angle in (0, 90, 180, 270):
        candidate = processed_image.rotate(angle, expand=True) if angle else processed_image
        score, data = _score_orientation(candidate)
        if score > best_score:
            best_score, best_data, best_angle = score, data, angle
    logger.info(f"auto-rotation chose {best_angle} degrees (confidence score={best_score:.1f})")
    return best_data


def _run_tesseract(image_bytes: bytes) -> OcrResult:
    import pytesseract
    from PIL import Image

    image = Image.open(BytesIO(image_bytes))
    processed = _preprocess_for_tesseract(image)

    data = _auto_rotate_and_ocr(processed)
    full_text = " ".join(t for t in data["text"] if t.strip())

    words: List[Word] = []
    confidences = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf_raw = str(data["conf"][i])
        conf = int(conf_raw) if conf_raw.lstrip("-").isdigit() else -1
        if not text or conf < 30:
            continue
        confidences.append(conf)
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        words.append(Word(text=text, x_min=x, x_max=x + w, y_min=y, y_max=y + h, confidence=float(conf)))

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return OcrResult(full_text=full_text, words=words, avg_confidence=avg_conf, engine_used="tesseract")


def run_ocr(image_bytes: bytes) -> OcrResult:
    engine = (settings.ocr_engine or "auto").lower()

    if engine == "tesseract":
        return _run_tesseract(image_bytes)

    if engine == "google":
        return _run_google_vision(image_bytes)

    try:
        return _run_google_vision(image_bytes)
    except Exception as google_error:
        logger.warning(f"Google Vision failed ({google_error}); falling back to Tesseract.")
        try:
            return _run_tesseract(image_bytes)
        except Exception as tesseract_error:
            raise RuntimeError(
                "Both OCR engines failed. "
                f"Google error: {google_error} | Tesseract error: {tesseract_error}"
            )
