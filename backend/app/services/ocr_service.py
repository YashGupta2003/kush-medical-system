"""
Thin wrapper around Google Cloud Vision's document text detection.

Vision returns every detected word with its bounding box. We keep the raw
word + box list and hand it to bill_parser.py, which reconstructs rows and
columns from the geometry - necessary because every distributor's invoice
(Hari Krishna, Rathore Medicos, Verma Bros, Kaiser Drugs...) uses a
different column layout, so we can't rely on a single fixed template.
"""
import os
from dataclasses import dataclass
from typing import List

from google.cloud import vision

from app.config import settings

os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", settings.google_application_credentials)


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


def run_ocr(image_bytes: bytes) -> tuple[str, List[Word]]:
    """
    Returns (full_raw_text, list_of_words_with_bounding_boxes).
    full_raw_text is stored on the Bill row for debugging/reprocessing;
    the word list is what the parser actually uses.
    """
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
                        Word(
                            text=text,
                            x_min=min(xs), x_max=max(xs),
                            y_min=min(ys), y_max=max(ys),
                        )
                    )
    return full_text, words
