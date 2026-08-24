import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.services.ocr_service import Word
from app.core.logging import get_logger

logger = get_logger("bill_parser")

ROW_Y_TOLERANCE_FALLBACK = 12

HEADER_ALIASES = {
    "PRODUCT": "name", "PARTICULARS": "name", "ITEM": "name", "DESCRIPTION": "name",
    "PACK": "pack",
    "BATCH": "batch", "BATCHNO": "batch",
    "EXP": "exp_date", "EXPIRY": "exp_date", "EXPDATE": "exp_date",
    "QTY": "qty",
    "FREE": "free_qty",
    "MRP": "mrp",
    "RATE": "rate",
    "DISC": "discount_pct", "DIS": "discount_pct", "SDIS": "special_discount_pct",
    "GST": "gst_pct", "CGST": "cgst_pct", "SGST": "sgst_pct",
    "AMOUNT": "amount", "AMT": "amount",
    "HSN": "hsn",
}


@dataclass
class ParsedRow:
    fields: dict = field(default_factory=dict)


def _adaptive_row_tolerance(words: List[Word]) -> float:
    if not words:
        return ROW_Y_TOLERANCE_FALLBACK
    heights = sorted(w.y_max - w.y_min for w in words if w.y_max > w.y_min)
    if not heights:
        return ROW_Y_TOLERANCE_FALLBACK
    median_height = heights[len(heights) // 2]
    return max(median_height * 0.6, ROW_Y_TOLERANCE_FALLBACK)


def _cluster_rows(words: List[Word]) -> List[List[Word]]:
    row_tolerance = _adaptive_row_tolerance(words)
    words_sorted = sorted(words, key=lambda w: w.y_center)
    rows: List[List[Word]] = []
    current: List[Word] = []
    current_y: Optional[float] = None

    for w in words_sorted:
        if current_y is None or abs(w.y_center - current_y) <= row_tolerance:
            current.append(w)
            current_y = w.y_center if current_y is None else (current_y + w.y_center) / 2
        else:
            rows.append(sorted(current, key=lambda x: x.x_center))
            current = [w]
            current_y = w.y_center
    if current:
        rows.append(sorted(current, key=lambda x: x.x_center))
    return rows


def _clean_token(text: str) -> str:
    return re.sub(r"[^A-Z]", "", text.upper())


def _find_header_row(rows: List[List[Word]]) -> Optional[int]:
    best_idx, best_score = None, 0
    for i, row in enumerate(rows):
        score = sum(1 for w in row if _clean_token(w.text) in HEADER_ALIASES)
        if score > best_score:
            best_score, best_idx = score, i
    logger.debug(f"best header row candidate: index={best_idx}, keyword_score={best_score}, total_rows_detected={len(rows)}")
    return best_idx if best_score >= 4 else None


def _build_column_map(header_row: List[Word]) -> List[tuple[float, str]]:
    columns = []
    for w in header_row:
        key = _clean_token(w.text)
        if key in HEADER_ALIASES:
            columns.append((w.x_center, HEADER_ALIASES[key]))
    logger.debug(f"header row raw words: {[w.text for w in header_row]}")
    logger.debug(f"columns mapped: {columns}")
    return sorted(columns, key=lambda c: c[0])


def _nearest_column(x_center: float, columns: List[tuple[float, str]]) -> str:
    return min(columns, key=lambda c: abs(c[0] - x_center))[1]


NUMERIC_FIELDS = {
    "qty", "free_qty", "mrp", "rate", "discount_pct",
    "special_discount_pct", "gst_pct", "cgst_pct", "sgst_pct", "amount",
}


def _to_number(text: str) -> Optional[float]:
    cleaned = re.sub(r"[^0-9.]", "", text)
    if not cleaned or cleaned == ".":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_bill_words(words: List[Word]) -> List[ParsedRow]:
    logger.info(f"total OCR words detected: {len(words)}")
    rows = _cluster_rows(words)
    logger.info(f"words clustered into {len(rows)} rows")
    header_idx = _find_header_row(rows)
    if header_idx is None:
        logger.warning("FAILED: no header row found.")
        return []

    columns = _build_column_map(rows[header_idx])
    if not columns:
        logger.warning("FAILED: header row found but no columns could be mapped.")
        return []

    parsed_rows: List[ParsedRow] = []

    for row in rows[header_idx + 1:]:
        row_text = " ".join(w.text for w in row).upper()
        if any(stop in row_text for stop in ("SUBTOTAL", "SUB TOTAL", "GRAND TOTAL", "TOTAL QTY", "ROUND OFF", "TERMS")):
            continue

        pr = ParsedRow()
        name_tokens = []
        for w in row:
            col = _nearest_column(w.x_center, columns)
            if col == "name":
                name_tokens.append(w.text)
                continue
            if col in NUMERIC_FIELDS:
                num = _to_number(w.text)
                if num is not None:
                    pr.fields[col] = num
            else:
                pr.fields[col] = (pr.fields.get(col, "") + " " + w.text).strip()

        if name_tokens:
            pr.fields["name"] = " ".join(name_tokens)

        if "gst_pct" not in pr.fields and "cgst_pct" in pr.fields and "sgst_pct" in pr.fields:
            pr.fields["gst_pct"] = pr.fields["cgst_pct"] + pr.fields["sgst_pct"]

        has_name = bool(pr.fields.get("name"))
        has_qty_or_rate = bool(pr.fields.get("qty") or pr.fields.get("rate"))
        if has_name and has_qty_or_rate:
            parsed_rows.append(pr)
        else:
            logger.debug(f"row dropped - name={pr.fields.get('name')!r} qty={pr.fields.get('qty')} rate={pr.fields.get('rate')}")

    logger.info(f"final result: {len(parsed_rows)} usable line items out of {len(rows) - header_idx - 1} candidate rows")
    return parsed_rows

def parse_bill_advanced(raw_text: str, words: List[Word]) -> List[ParsedRow]:
    from app.config import settings
    if settings.groq_api_key:
        try:
            import json
            from groq import Groq
            client = Groq(api_key=settings.groq_api_key)
            prompt = f"""
You are a highly accurate pharmacy bill OCR extraction system.
Extract all the medicine line items from the following OCR text of a purchase bill.
Return a valid JSON object with a single key "items" which is an array of objects.
Do not include markdown formatting, backticks, or any explanations.

The JSON should look exactly like this:
{{
  "items": [
    {{
      "name": "PARACETAMOL 500MG TABS",
      "pack": "10x10",
      "batch": "B1234",
      "exp_date": "10/26",
      "qty": 10,
      "free_qty": 0,
      "mrp": 50.0,
      "rate": 35.0,
      "discount_pct": 10.0,
      "special_discount_pct": 0,
      "gst_pct": 12.0,
      "amount": 315.0
    }}
  ]
}}

Extract ONLY the line items. Ignore headers, subtotals, footers, terms, and bank details.
If a numeric field is not present, omit it or set to 0.

OCR Text:
{raw_text[:4000]}
"""
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=settings.groq_model,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content.strip()
            data = json.loads(content)
            items = data.get("items", [])
            
            parsed = []
            for item in items:
                # Basic validation: must have name and (qty or rate)
                name = item.get("name")
                if not name:
                    continue
                qty = item.get("qty", 0)
                rate = item.get("rate", 0)
                if not (qty or rate):
                    continue
                    
                pr = ParsedRow()
                for k, v in item.items():
                    if v is not None and str(v).strip() != "":
                        pr.fields[k] = v
                parsed.append(pr)
                
            if parsed:
                logger.info(f"LLM successfully extracted {len(parsed)} items from bill")
                return parsed
            else:
                logger.warning("LLM returned 0 items, falling back to heuristic parser")
        except Exception as e:
            logger.error(f"LLM bill parsing failed: {e}", exc_info=True)
            logger.warning("Falling back to heuristic parser")
            
    # Fallback
    return parse_bill_words(words)
