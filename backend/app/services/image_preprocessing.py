"""
OpenCV preprocessing layer, run BEFORE the image reaches OCR (Tesseract or
Google Vision). This is what separates a "works on a perfect photo" pipeline
from one that tolerates real phone photos: slightly rotated, with background
table/hand visible, uneven lighting.

Pipeline, in order:
  1. Decode bytes -> OpenCV BGR array
  2. Auto-crop: find the largest rectangular light region (the paper) and
     crop everything else out (table wood, fingers, background).
  3. Deskew: detect the dominant text-line angle and rotate to straighten it.
  4. Adaptive threshold: convert to a clean high-contrast black/white image.

Every step is defensive: if a step's assumptions don't hold for a given
image, it falls back to the un-cropped/un-deskewed image rather than
mangling it further.
"""
import cv2
import numpy as np
from dataclasses import dataclass


@dataclass
class PreprocessResult:
    image_bytes: bytes
    was_cropped: bool
    deskew_angle_degrees: float
    warnings: list[str]


def _decode(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image - file may be corrupt or an unsupported format.")
    return img


def _encode(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ValueError("Could not re-encode processed image.")
    return buf.tobytes()


def _auto_crop_to_paper(img: np.ndarray, warnings: list[str]) -> tuple[np.ndarray, bool]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        warnings.append("auto-crop: no contours found, using full image")
        return img, False

    img_area = img.shape[0] * img.shape[1]
    largest = max(contours, key=cv2.contourArea)
    area_ratio = cv2.contourArea(largest) / img_area

    if area_ratio < 0.15:
        warnings.append(f"auto-crop: largest contour only {area_ratio:.0%} of frame, skipping crop")
        return img, False

    x, y, w, h = cv2.boundingRect(largest)
    pad = int(0.01 * max(w, h))
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(img.shape[1], x + w + pad), min(img.shape[0], y + h + pad)
    cropped = img[y0:y1, x0:x1]

    if cropped.size == 0:
        warnings.append("auto-crop: crop resulted in empty image, using full image")
        return img, False

    return cropped, True


def _estimate_skew_angle(img: np.ndarray) -> float:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=150,
                             minLineLength=img.shape[1] // 4, maxLineGap=20)
    if lines is None or len(lines) == 0:
        return 0.0

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(angle) < 20:
            angles.append(angle)

    if not angles:
        return 0.0
    return float(np.median(angles))


def _deskew(img: np.ndarray, warnings: list[str]) -> tuple[np.ndarray, float]:
    angle = _estimate_skew_angle(img)
    if abs(angle) < 0.3:
        return img, 0.0
    if abs(angle) > 15:
        warnings.append(f"deskew: estimated angle {angle:.1f} degrees looked unreliable, skipping")
        return img, 0.0

    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(img, matrix, (w, h), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)
    return rotated, angle


def _adaptive_threshold(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    thresholded = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,
        blockSize=25, C=10,
    )
    return cv2.cvtColor(thresholded, cv2.COLOR_GRAY2BGR)


def preprocess_bill_image(image_bytes: bytes) -> PreprocessResult:
    warnings: list[str] = []
    img = _decode(image_bytes)

    cropped, was_cropped = _auto_crop_to_paper(img, warnings)
    deskewed, angle = _deskew(cropped, warnings)
    thresholded = _adaptive_threshold(deskewed)

    return PreprocessResult(
        image_bytes=_encode(thresholded),
        was_cropped=was_cropped,
        deskew_angle_degrees=angle,
        warnings=warnings,
    )


def crop_region(image_bytes: bytes, x0: int, y0: int, x1: int, y1: int) -> bytes:
    img = _decode(image_bytes)
    h, w = img.shape[:2]
    pad = 6
    x0, y0 = max(0, min(x0, w) - pad), max(0, min(y0, h) - pad)
    x1, y1 = max(0, min(x1, w) + pad), max(0, min(y1, h) + pad)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("Invalid crop region")
    crop = img[y0:y1, x0:x1]
    scale = 3 if max(crop.shape[:2]) < 200 else 1
    if scale > 1:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return _encode(crop)
