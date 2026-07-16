import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.services.ocr_service import Word

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
    print(f"[bill_parser] best header row candidate: index={best_idx}, keyword_score={best_score}, "
          f"total_rows_detected={len(rows)}")
    return best_idx if best_score >= 2 else None


def _build_column_map(header_row: List[Word]) -> List[tuple[float, str]]:
    columns = []
    for w in header_row:
        key = _clean_token(w.text)
        if key in HEADER_ALIASES:
            columns.append((w.x_center, HEADER_ALIASES[key]))
    print(f"[bill_parser] header row raw words: {[w.text for w in header_row]}")
    print(f"[bill_parser] columns mapped: {columns}")
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
    print(f"[bill_parser] total OCR words detected: {len(words)}")
    rows = _cluster_rows(words)
    print(f"[bill_parser] words clustered into {len(rows)} rows")
    header_idx = _find_header_row(rows)
    if header_idx is None:
        print("[bill_parser] FAILED: no header row found.")
        return []

    columns = _build_column_map(rows[header_idx])
    if not columns:
        print("[bill_parser] FAILED: header row found but no columns could be mapped.")
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
            print(f"[bill_parser] row dropped - name={pr.fields.get('name')!r} "
                  f"qty={pr.fields.get('qty')} rate={pr.fields.get('rate')} "
                  f"all_fields={pr.fields}")

    print(f"[bill_parser] final result: {len(parsed_rows)} usable line items out of "
          f"{len(rows) - header_idx - 1} candidate rows after the header")
    return parsed_rows
