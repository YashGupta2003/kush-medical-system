"""
Setup wizard endpoint — POST /setup/import-medicine-list

Called by the frontend SetupWizard after a new tenant registers.
Accepts an Excel/CSV file and bulk-imports all medicines into the
tenant's medicine catalog.

This is a simplified wrapper around the same import logic used by the
original CLI script (scripts/import_rate_list.py), but:
1. Requires authentication (owner only — no random uploads)
2. Tags every imported medicine with the authenticated tenant's ID
3. Returns a summary { imported, skipped, errors } for the UI

Column mapping (case-insensitive, extra columns ignored):
  Particulars / Medicine Name / Name  → particulars
  Unit / Pack Size                    → unit
  MRP / M.R.P.                        → mrp
  Net Rate / Rate / Cost              → net_rate
  Company / Manufacturer              → company
  Stockist / Supplier                 → stockist
  Composition / Salt                  → composition
"""
import io
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.deps import require_owner, get_current_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/setup", tags=["setup"])

# Canonical column aliases — each key is what we call it internally,
# the list is all the variants we might find in the uploaded file.
COLUMN_ALIASES = {
    "particulars": ["particulars", "medicine name", "name", "item name", "product", "description", "medicine"],
    "unit":        ["unit", "pack size", "packing", "pack"],
    "mrp":         ["mrp", "m.r.p.", "m.r.p", "max retail price", "retail price"],
    "net_rate":    ["net rate", "rate", "cost", "net_rate", "cost price", "purchase rate", "buy rate"],
    "company":     ["company", "manufacturer", "brand", "mfr"],
    "stockist":    ["stockist", "supplier", "distributor", "vendor"],
    "composition": ["composition", "salt", "generic name", "ingredients", "active ingredient"],
}


def _normalize_col(col: str) -> str:
    return col.strip().lower().replace(".", "").replace("_", " ")


def _map_columns(df_columns: list) -> dict:
    """Returns a mapping of {internal_name: actual_df_column_name}."""
    normalized = {_normalize_col(c): c for c in df_columns}
    result = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                result[field] = normalized[alias]
                break
    return result


def _normalize_medicine_name(name: str) -> str:
    """Uppercase + strip punctuation — same logic as the existing matcher.py."""
    import re
    return re.sub(r"[^\w\s]", "", str(name).upper()).strip()


@router.post("/import-medicine-list", summary="Import medicine list from Excel/CSV (Setup Wizard)")
def import_medicine_list(
    file: UploadFile = File(..., description="Excel (.xlsx, .xls) or CSV medicine rate list"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_owner),
    tenant: models.Tenant = Depends(get_current_tenant),
):
    """
    Owner-only: import a medicine rate list from Excel or CSV.
    Tags all imported medicines with the current tenant's ID.
    Returns { imported, skipped, errors, error_details }.
    """
    # ── Read file ─────────────────────────────────────────────────────────
    filename = file.filename or ""
    content = file.file.read()

    try:
        import pandas as pd

        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content), dtype=str, keep_default_na=False)
        else:
            raise HTTPException(400, "Unsupported file type. Please upload .xlsx, .xls, or .csv")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(422, f"Could not read file: {e}")

    if df.empty:
        raise HTTPException(422, "The uploaded file appears to be empty.")

    # ── Map columns ──────────────────────────────────────────────────────
    col_map = _map_columns(list(df.columns))
    if "particulars" not in col_map:
        raise HTTPException(
            422,
            f"Could not find a medicine name column. "
            f"Expected one of: {', '.join(COLUMN_ALIASES['particulars'])}. "
            f"Found columns: {', '.join(df.columns.tolist())}"
        )

    # ── Import loop ──────────────────────────────────────────────────────
    imported = 0
    skipped = 0
    errors = 0
    error_details = []

    for idx, row in df.iterrows():
        raw_name = row.get(col_map["particulars"], "").strip()
        if not raw_name:
            skipped += 1
            continue

        normalized = _normalize_medicine_name(raw_name)

        def get_numeric(field):
            col = col_map.get(field)
            if not col:
                return None
            val = str(row.get(col, "")).strip().replace(",", "")
            try:
                return float(val) if val else None
            except ValueError:
                return None

        try:
            # Check if this medicine already exists for this tenant
            existing = db.query(models.Medicine).filter(
                models.Medicine.tenant_id == tenant.id,
                models.Medicine.normalized_name == normalized,
            ).first()

            if existing:
                # Update rates if newer data provided
                new_mrp = get_numeric("mrp")
                new_rate = get_numeric("net_rate")
                if new_mrp is not None:
                    existing.mrp = new_mrp
                if new_rate is not None:
                    existing.net_rate = new_rate
                skipped += 1
            else:
                medicine = models.Medicine(
                    tenant_id=tenant.id,
                    particulars=raw_name,
                    normalized_name=normalized,
                    unit=str(row.get(col_map.get("unit", ""), "") or "").strip() or None,
                    mrp=get_numeric("mrp"),
                    net_rate=get_numeric("net_rate"),
                    company=str(row.get(col_map.get("company", ""), "") or "").strip() or None,
                    stockist=str(row.get(col_map.get("stockist", ""), "") or "").strip() or None,
                    composition=str(row.get(col_map.get("composition", ""), "") or "").strip() or None,
                    current_stock=0,
                )
                db.add(medicine)
                imported += 1

            # Commit in batches of 500 for performance
            if (imported + skipped) % 500 == 0:
                db.commit()

        except Exception as e:
            errors += 1
            error_details.append(f"Row {idx + 2}: {raw_name[:50]} — {str(e)[:100]}")
            logger.warning(f"Import error for tenant {tenant.id}, row {idx}: {e}")

    # Final commit
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Database error during final commit: {e}")

    logger.info(
        f"Medicine import complete for tenant {tenant.id} ({tenant.shop_name}): "
        f"imported={imported}, skipped={skipped}, errors={errors}"
    )

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "error_details": error_details[:20],  # cap at 20 details to keep response small
        "message": f"Import complete. {imported} medicines added, {skipped} already existed, {errors} errors.",
    }
