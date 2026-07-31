"""
Composition match SUGGESTION tool - deliberately read-only, touches your
database in zero ways. It never writes a composition automatically.

Why not auto-apply: real testing against this exact codebase's medicine
names proved that fuzzy-matching short shop abbreviations ("1 AL SYP",
"A TO Z TAB", "625 TAB") against a large external medicine-name dataset
produces confidently WRONG matches even at 90-100% similarity scores -
e.g. "A TO Z TAB" (a multivitamin in most Indian pharmacies) matched
"A To Z Cream" (a Clobetasol+Neomycin steroid cream) at 100% purely
because the short brand name is identical while the actual product is
completely different. Auto-applying results like that would silently
poison the Substitute Finder feature with wrong salt data - worse than
leaving composition blank, since blank is visibly "not set" while a wrong
value looks confident and correct.

So this script only WRITES A REVIEW SPREADSHEET. A human (you, or your
pharmacist) looks at each row, keeps the ones that are actually correct
(deleting the wrong ones), and then runs scripts/backfill_composition.py
on the cleaned-up file - which only ever applies a composition when the
medicine name matches EXACTLY (case/punctuation-insensitive), so a row
you didn't clean up correctly simply won't match anything rather than
silently applying to the wrong medicine.

Get the source dataset (free, no API key, ~250k Indian medicines) from:
    https://github.com/junioralive/Indian-Medicine-Dataset
    (DATA/indian_medicine_data.csv)

Usage:
    cd backend
    python scripts/suggest_composition_matches.py /path/to/indian_medicine_data.csv
"""
import sys
import os
import csv
import re

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from rapidfuzz import process, fuzz
from app.database import SessionLocal
from app.models import Medicine

# How many candidate matches to show per medicine - a human picks the right
# one (or none) rather than the script guessing for them.
TOP_N_CANDIDATES = 3
# Below this score, don't even bother suggesting - pure noise.
MIN_SCORE_TO_SHOW = 55

_FORM_WORDS_RE = re.compile(
    r"\b(TABLET|TABLETS|TAB|CAPSULE|CAPSULES|CAP|SYRUP|SYP|DROP|DROPS|GEL|CREAM|"
    r"LOTION|INJECTION|OINTMENT|POWDER|SUSPENSION)\b"
)


def _normalize(text: str) -> str:
    text = text.upper()
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _core_name(text: str) -> str:
    text = _normalize(text)
    text = _FORM_WORDS_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean_composition(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*\+\s*", " + ", text)
    return text


def _load_dataset(csv_path: str) -> dict:
    """core_name -> {"name": ..., "composition": ...}, deduplicated."""
    seen = {}
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            # Prefer salt_composition if the dataset has it - in practice it's
            # sometimes MORE complete than short_composition1/2 combined (a
            # third salt can appear there that isn't split into its own
            # short_composition column). Fall back to short_composition1/2
            # for datasets that don't have salt_composition at all.
            composition = (row.get("salt_composition") or "").strip()
            if not composition:
                comp1 = (row.get("short_composition1") or "").strip()
                comp2 = (row.get("short_composition2") or "").strip()
                composition = " + ".join(c for c in (comp1, comp2) if c)
            composition = _clean_composition(composition)

            if not composition or row.get("Is_discontinued", "").upper() == "TRUE":
                continue
            core = _core_name(row["name"])
            if core and core not in seen:
                seen[core] = {"name": row["name"], "composition": composition}
    return seen


def main(csv_path: str):
    print("Loading external dataset (read-only, this script never writes to it)...")
    dataset = _load_dataset(csv_path)
    choices = list(dataset.keys())
    print(f"{len(dataset)} unique reference products loaded.\n")

    db = SessionLocal()
    medicines = db.query(Medicine).filter(
        (Medicine.composition.is_(None)) | (Medicine.composition == "")
    ).all()
    db.close()
    print(f"{len(medicines)} medicines in your master list have no composition yet.")
    print("Generating candidate suggestions for each (this does NOT touch your database)...\n")

    rows = []
    for i, med in enumerate(medicines, 1):
        query_core = _core_name(med.particulars)
        matches = process.extract(
            query_core, choices, scorer=fuzz.token_sort_ratio,
            score_cutoff=MIN_SCORE_TO_SHOW, limit=TOP_N_CANDIDATES,
        )
        if not matches:
            rows.append({
                "medicine_id": med.id, "shop_name": med.particulars, "unit": med.unit or "",
                "candidate_rank": "", "candidate_name": "NO CANDIDATE FOUND",
                "suggested_composition": "", "match_score": "",
                "APPROVED (fill YES here, leave rest blank)": "",
            })
            continue
        for rank, (matched_core, score, _idx) in enumerate(matches, 1):
            d = dataset[matched_core]
            rows.append({
                "medicine_id": med.id, "shop_name": med.particulars, "unit": med.unit or "",
                "candidate_rank": rank, "candidate_name": d["name"],
                "suggested_composition": d["composition"], "match_score": round(score, 1),
                "APPROVED (fill YES here, leave rest blank)": "",
            })

        if i % 500 == 0:
            print(f"  ...{i}/{len(medicines)} processed")

    out_path = "composition_suggestions_FOR_REVIEW.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. {len(medicines)} medicines processed -> {out_path}")
    print(
        "\nNEXT STEPS (manual, on purpose):\n"
        "  1. Open the CSV. For each medicine_id, look at its candidate rows.\n"
        "  2. If a candidate is genuinely correct, type YES in the last column for that ONE row.\n"
        "     If none of the candidates are right (common for shop-specific/regional names,\n"
        "     discontinued products), leave all blank - do not guess.\n"
        "  3. Filter/sort the sheet to keep only rows marked YES, then save two columns\n"
        "     (shop_name, suggested_composition) as a new file matching the format expected by\n"
        "     scripts/backfill_composition.py, and run that script on it.\n"
        "  4. For medicines with no good candidate at all, prioritize filling those in by hand\n"
        "     from the Search screen - start with your best-selling medicines (check the\n"
        "     Analytics > Top Sellers list) rather than trying to do all of them at once."
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/suggest_composition_matches.py /path/to/indian_medicine_data.csv")
        sys.exit(1)
    main(sys.argv[1])