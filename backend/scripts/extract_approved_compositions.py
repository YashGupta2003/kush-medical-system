"""
Takes the file YOU reviewed (composition_suggestions_FOR_REVIEW.csv, after
you've typed YES in the approval column for the rows you confirmed are
correct) and extracts ONLY those approved rows into the clean 2-column
format that scripts/backfill_composition.py expects.

This exists so you never have to manually delete rows or reorder columns
in Excel/Numbers by hand - a mistake there (wrong column order, leftover
extra columns) is exactly what caused the "14478 unmatched" result if you
tried feeding the raw review file straight into backfill_composition.py.

Usage:
    cd backend
    python scripts/extract_approved_compositions.py /path/to/composition_suggestions_FOR_REVIEW.csv
"""
import sys
import os
import csv

MIN_COLUMNS_NEEDED = {"shop_name", "suggested_composition"}


def _find_column(fieldnames, must_contain: str) -> str:
    for name in fieldnames:
        if must_contain.lower() in name.lower():
            return name
    return None


def main(path: str):
    if not os.path.exists(path):
        print(f"File not found: {path}")
        sys.exit(1)

    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        name_col = _find_column(fieldnames, "shop_name")
        composition_col = _find_column(fieldnames, "suggested_composition")
        approved_col = _find_column(fieldnames, "approved")

        missing = [
            label for label, col in
            (("shop_name", name_col), ("suggested_composition", composition_col), ("approved", approved_col))
            if col is None
        ]
        if missing:
            print(f"Couldn't find expected column(s): {missing}")
            print(f"Columns actually found in your file: {fieldnames}")
            print("Make sure you exported the ORIGINAL composition_suggestions_FOR_REVIEW.csv "
                  "(with your YES marks added) without deleting or renaming columns.")
            sys.exit(1)

        approved_rows = []
        seen_medicine_ids = set()
        for row in reader:
            mark = (row.get(approved_col) or "").strip().upper()
            if mark != "YES":
                continue
            medicine_id = row.get("medicine_id", "")
            if medicine_id in seen_medicine_ids:
                # Guards against accidentally marking YES on more than one
                # candidate row for the same medicine - only the first is kept.
                print(f"  Note: medicine_id {medicine_id} had more than one YES row - kept the first, skipped the rest.")
                continue
            seen_medicine_ids.add(medicine_id)

            name = (row.get(name_col) or "").strip()
            composition = (row.get(composition_col) or "").strip()
            if name and composition:
                approved_rows.append((name, composition))

    if not approved_rows:
        print("No approved rows found. Make sure you typed exactly 'YES' (any case) in the "
              "approval column for the rows you confirmed are correct, then re-export/save the file.")
        sys.exit(1)

    out_path = os.path.join(os.path.dirname(os.path.abspath(path)), "approved_compositions_clean.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Medicine Name", "Composition"])
        writer.writerows(approved_rows)

    print(f"Done. {len(approved_rows)} approved medicines written to:\n  {out_path}")
    print("\nNow run:")
    print(f"  python scripts/backfill_composition.py {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/extract_approved_compositions.py /path/to/composition_suggestions_FOR_REVIEW.csv")
        sys.exit(1)
    main(sys.argv[1])
