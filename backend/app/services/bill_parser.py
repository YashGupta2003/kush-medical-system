"""
Reconstructs a table (rows/columns) from a flat list of OCR words + bounding
boxes, then maps the header row's column positions to known field names
(QTY, MRP, RATE, DISC%, GST%, BATCH, EXP, HSN, FREE, AMOUNT, PRODUCT...).

This is what lets one parser handle Hari Krishna Distributor, Rathore
Medicos, Verma Bros, Kaiser Drugs, etc. even though each prints a different
column layout - instead of hard-coding a template per distributor, we read
each bill's own header row and use it as the template for that bill.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.services.ocr_service import Word

ROW_Y_TOLERANCE = 12   # px; words within this y-band are treated as the same row

# header keyword -> canonical field name
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


def _cluster_rows(words: List[Word]) -> List[List[Word]]:
    words_sorted = sorted(words, key=lambda w: w.y_center)
    rows: List[List[Word]] = []
    current: List[Word] = []
    current_y: Optional[float] = None

    for w in words_sorted:
        if current_y is None or abs(w.y_center - current_y) <= ROW_Y_TOLERANCE:
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
    """Header row = the row with the most words matching HEADER_ALIASES keys."""
    best_idx, best_score = None, 0
    for i, row in enumerate(rows):
        score = sum(1 for w in row if _clean_token(w.text) in HEADER_ALIASES)
        if score > best_score:
            best_score, best_idx = score, i
    return best_idx if best_score >= 3 else None


def _build_column_map(header_row: List[Word]) -> List[tuple[float, str]]:
    """Returns [(x_center, field_name), ...] sorted left to right."""
    columns = []
    for w in header_row:
        key = _clean_token(w.text)
        if key in HEADER_ALIASES:
            columns.append((w.x_center, HEADER_ALIASES[key]))
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
    """
    Main entry point. Given all OCR words on the invoice, returns one
    ParsedRow per detected line item, with fields already mapped by name
    (qty, mrp, rate, discount_pct, gst_pct, etc.) wherever the header
    row could be matched to a column position.

    NOTE: this is a heuristic reconstruction, not a guaranteed-perfect parse.
    Every row produced here is meant to be shown to the user on the review
    screen for confirmation/edit before anything is saved to the master list
    (see the /bills/{id}/confirm endpoint) - this keeps OCR mistakes from
    silently corrupting real shop data.
    """
    rows = _cluster_rows(words)
    header_idx = _find_header_row(rows)
    if header_idx is None:
        return []  # caller should flag this bill as "needs fully manual entry"

    columns = _build_column_map(rows[header_idx])
    if not columns:
        return []

    parsed_rows: List[ParsedRow] = []
    name_parts_by_row: List[str] = []

    for row in rows[header_idx + 1:]:
        # skip footer/summary rows (e.g. "SUB TOTAL", "GRAND TOTAL", "GST 2.5%")
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
                # text fields: batch, exp_date, hsn, pack - append if already present
                pr.fields[col] = (pr.fields.get(col, "") + " " + w.text).strip()

        if name_tokens:
            pr.fields["name"] = " ".join(name_tokens)

        # merge separate cgst/sgst into one gst_pct if no combined gst_pct was found
        if "gst_pct" not in pr.fields and "cgst_pct" in pr.fields and "sgst_pct" in pr.fields:
            pr.fields["gst_pct"] = pr.fields["cgst_pct"] + pr.fields["sgst_pct"]

        if pr.fields.get("name") and (pr.fields.get("qty") or pr.fields.get("rate")):
            parsed_rows.append(pr)

    return parsed_rows
