"""
One-time fix-up: re-parses EVERY medicine that already has composition text
(Medicine.composition) and regenerates its medicine_salts rows using the
current parser in composition_service.py.

Why this is needed: earlier versions of parse_composition() didn't handle
the parenthetical strength format ("Paracetamol (325mg)") that this
project's real data actually uses - it left the brackets/strength stuck
inside salt_name (e.g. "PARACETAMOL (325MG)" instead of "PARACETAMOL"),
which silently broke every substitute search. Medicine.composition itself
(the raw display text) was never wrong - only the derived salt rows were -
so this script is 100% safe to run: it doesn't touch composition text, it
only re-derives medicine_salts from it.

Safe to run more than once (set_medicine_composition always deletes and
recreates a medicine's salt rows, never appends).

Usage:
    cd backend
    python scripts/reparse_all_compositions.py
"""
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.models import Medicine
from app.services.composition_service import set_medicine_composition


def main():
    db = SessionLocal()
    medicines = db.query(Medicine).filter(
        Medicine.composition.isnot(None), Medicine.composition != ""
    ).all()

    print(f"Re-parsing {len(medicines)} medicines that already have composition text...")

    for i, med in enumerate(medicines, 1):
        set_medicine_composition(db, med.id, med.composition)
        if i % 500 == 0:
            db.commit()
            print(f"  ...{i}/{len(medicines)} done")

    db.commit()
    db.close()
    print(f"Done. {len(medicines)} medicines' salt data re-derived with the corrected parser.")


if __name__ == "__main__":
    main()
