"""
One-time (or repeatable) import of the shop's existing Excel rate list into
the `medicines` table.

Handles two real quirks found in the actual file:
1. Some MRP / NET RATE cells store two slash-separated values, e.g. "103/121"
   or "77.55/77.55" (an older value and a current one, patched in by hand
   over time). We keep the LAST value as current, since that's what the
   most recent manual edit left behind.
2. COMPANY / STOCKIST are blank for most rows - that's fine, left as NULL.

Usage:
    cd backend
    python scripts/import_rate_list.py /path/to/kush_medical_rate_list_.xlsx
"""
import sys
import os
import re

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import openpyxl
from app.database import SessionLocal, Base, engine
from app.models import Medicine
from app.services.matcher import normalize


def parse_maybe_slash_value(raw) -> float | None:
    """'103/121' -> 121.0 (take the latest/rightmost value). Plain '72' -> 72.0."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip()
    if not text:
        return None
    parts = re.split(r"[/\\]", text)
    try:
        return float(parts[-1].strip())
    except ValueError:
        return None


def main(xlsx_path: str):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb["Sheet1"]

    inserted, skipped = 0, 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        particulars = row[0]
        if not particulars or not str(particulars).strip():
            skipped += 1
            continue

        unit = row[1]
        mrp = parse_maybe_slash_value(row[2])
        net_rate = parse_maybe_slash_value(row[3])
        company = (row[4] or None)
        stockist = (row[5] or None) if len(row) > 5 else None

        particulars = str(particulars).strip()
        medicine = Medicine(
            particulars=particulars,
            normalized_name=normalize(particulars),
            unit=str(unit).strip() if unit else None,
            mrp=mrp,
            net_rate=net_rate,
            company=str(company).strip() if company else None,
            stockist=str(stockist).strip() if stockist else None,
        )
        db.add(medicine)
        inserted += 1

        if inserted % 500 == 0:
            db.commit()
            print(f"  ...{inserted} rows committed so far")

    db.commit()
    db.close()
    print(f"Done. Inserted {inserted} medicines, skipped {skipped} blank rows.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/import_rate_list.py /path/to/rate_list.xlsx")
        sys.exit(1)
    main(sys.argv[1])
