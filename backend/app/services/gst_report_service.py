"""
GST report generation for the shop's Chartered Accountant.

Input-tax (purchase) report is derived from confirmed bill items. Real bills
store a combined GST% and line amount; taxable/tax are derived per line:

    taxable_amount = amount / (1 + gst_pct/100)
    total_tax      = amount - taxable_amount

Tax split:
  - intra-state (or unknown): CGST = SGST = total_tax / 2
  - inter-state:              IGST = total_tax

Period handling (Issue 6): purchase lines are included in the selected period
based on `Bill.invoice_date` (year/month). Confirmed bills without
`invoice_date` are separated and reported with warnings so the CA can resolve
them (not silently bucketed by upload/derived year/month).

Sales/output GST estimates are derived from sale-time snapshots (Issue 5) for
the selected period when available, with legacy fallback where snapshots are
missing. Estimates are additive and do not change the purchase report contract.

All money math uses Decimal with ROUND_HALF_UP to 2dp at defined points.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from typing import Optional

from sqlalchemy.orm import Session

from app import models

Q2 = Decimal("0.01")
ZERO = Decimal("0.00")


def _d(value) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return ZERO


def _q2(value: Decimal) -> Decimal:
    return _d(value).quantize(Q2, rounding=ROUND_HALF_UP)


def _gstin_state_code(gstin: Optional[str]) -> Optional[str]:
    if not gstin:
        return None
    code = str(gstin).strip()[:2]
    return code if len(code) == 2 and code.isalnum() else None


def _is_interstate(tenant_gstin: Optional[str], distributor_gstin: Optional[str]) -> Optional[bool]:
    t = _gstin_state_code(tenant_gstin)
    d = _gstin_state_code(distributor_gstin)
    if not t or not d:
        return None
    return t.upper() != d.upper()


def _empty_slab(gst_pct: Decimal) -> dict:
    return {
        "gst_pct": float(_q2(gst_pct)),
        "taxable_amount": ZERO,
        "cgst": ZERO,
        "sgst": ZERO,
        "igst": ZERO,
        "total_tax": ZERO,
        "total_amount": ZERO,
        "item_count": 0,
    }


def _slab_to_output(slab: dict) -> dict:
    return {
        "gst_pct": float(_q2(_d(slab["gst_pct"]))),
        "taxable_amount": float(_q2(slab["taxable_amount"])),
        "cgst": float(_q2(slab["cgst"])),
        "sgst": float(_q2(slab["sgst"])),
        "igst": float(_q2(slab.get("igst", ZERO))),
        "total_tax": float(_q2(slab["total_tax"])),
        "total_amount": float(_q2(slab["total_amount"])),
        "item_count": int(slab["item_count"]),
    }


def _iter_confirmed_purchase_items(db: Session, tenant_id: int):
    """Confirmed purchase bill items for tenant (period decided by invoice_date)."""
    return (
        db.query(models.BillItem, models.Bill, models.Distributor)
        .join(models.Bill, models.Bill.id == models.BillItem.bill_id)
        .outerjoin(models.Distributor, models.Distributor.id == models.Bill.distributor_id)
        .filter(
            models.Bill.tenant_id == tenant_id,
            models.Bill.status == "confirmed",
            models.BillItem.amount.isnot(None),
            models.BillItem.gst_pct.isnot(None),
        )
        .all()
    )


def _sale_line_amounts(sale: models.Sale) -> Optional[dict]:
    """Derive sale taxable/tax/total from snapshots, with legacy fallback."""
    qty = _d(getattr(sale, "qty_sold", None))
    if qty <= 0:
        return None

    gst_pct = _d(getattr(sale, "gst_pct_snapshot", None))
    unit_mrp = getattr(sale, "unit_mrp_snapshot", None)
    med = getattr(sale, "medicine", None)
    if unit_mrp is None and med is not None:
        unit_mrp = getattr(med, "mrp", None)

    line_total = getattr(sale, "line_total", None)
    if line_total is None:
        if unit_mrp is None:
            return None
        line_total = _q2(_d(unit_mrp) * qty)
    else:
        line_total = _q2(_d(line_total))

    line_tax = getattr(sale, "line_tax_amount", None)
    line_subtotal = getattr(sale, "line_subtotal", None)
    if line_tax is None or line_subtotal is None:
        if gst_pct > 0:
            line_tax = _q2((line_total * gst_pct) / (Decimal("100") + gst_pct))
            line_subtotal = _q2(line_total - line_tax)
        else:
            line_tax = ZERO
            line_subtotal = line_total
    else:
        line_tax = _q2(_d(line_tax))
        line_subtotal = _q2(_d(line_subtotal))

    return {
        "gst_pct": _q2(gst_pct),
        "taxable": line_subtotal,
        "tax": line_tax,
        "total": line_total,
    }


def _compute_sales_output_estimates(db: Session, tenant_id: int, year: int, month: int) -> dict:
    """Additive sale/output-GST estimates for the period from sale snapshots."""
    slabs: dict[Decimal, dict] = {}
    sale_ids = set()

    # Use sold_at period. (Sale.sold_at is timezone-aware in app code; comparisons by month/year are calendar-based.)
    sales = (
        db.query(models.Sale)
        .filter(models.Sale.tenant_id == tenant_id)
        .all()
    )

    for sale in sales:
        sold_at = getattr(sale, "sold_at", None)
        if not sold_at:
            continue
        try:
            if sold_at.year != year or sold_at.month != month:
                continue
        except Exception:
            continue
        vals = _sale_line_amounts(sale)
        if not vals or vals["total"] <= 0:
            continue
        sale_ids.add(sale.id)
        gst_pct = vals["gst_pct"]
        slab = slabs.setdefault(gst_pct, _empty_slab(gst_pct))
        # Output tax treated as intra-state/unspecified split (CGST/SGST) for estimate; IGST kept 0.
        cgst = _q2(vals["tax"] / Decimal("2")) if vals["tax"] > 0 else ZERO
        sgst = _q2(vals["tax"] - cgst)
        slab["taxable_amount"] += vals["taxable"]
        slab["total_tax"] += vals["tax"]
        slab["cgst"] += cgst
        slab["sgst"] += sgst
        slab["total_amount"] += vals["total"]
        slab["item_count"] += 1

    slab_list = [_slab_to_output(s) for _, s in sorted(slabs.items(), key=lambda kv: kv[0])]
    return {
        "period_basis": "sale.sold_at",
        "slabs": slab_list,
        "grand_taxable_amount": float(_q2(sum(_d(s["taxable_amount"]) for s in slab_list))),
        "grand_cgst": float(_q2(sum(_d(s["cgst"]) for s in slab_list))),
        "grand_sgst": float(_q2(sum(_d(s["sgst"]) for s in slab_list))),
        "grand_igst": 0.0,
        "grand_total_tax": float(_q2(sum(_d(s["total_tax"]) for s in slab_list))),
        "grand_total_amount": float(_q2(sum(_d(s["total_amount"]) for s in slab_list))),
        "sale_count": len(sale_ids),
        "note": "Estimated output GST from recorded sale snapshots for the selected period (sale.sold_at). Verify before filing.",
    }


def get_gst_report(db: Session, tenant_id: int, year: int, month: int) -> dict:
    tenant = db.get(models.Tenant, tenant_id) if tenant_id is not None else None
    tenant_gstin = getattr(tenant, "gstin", None) if tenant else None

    slabs: dict[Decimal, dict] = {}
    included_bill_ids = set()
    undated_bill_ids = set()
    assumed_intrastate_bill_ids = set()

    for item, bill, distributor in _iter_confirmed_purchase_items(db, tenant_id):
        inv_date = getattr(bill, "invoice_date", None)
        if not inv_date:
            undated_bill_ids.add(bill.id)
            continue
        try:
            if inv_date.year != year or inv_date.month != month:
                continue
        except Exception:
            undated_bill_ids.add(bill.id)
            continue

        gst_pct = _q2(_d(item.gst_pct))
        amount = _q2(_d(item.amount))
        if amount <= 0:
            continue

        taxable = _q2(amount / (Decimal("1") + gst_pct / Decimal("100"))) if gst_pct > 0 else amount
        total_tax = _q2(amount - taxable)

        interstate = _is_interstate(tenant_gstin, getattr(distributor, "gstin", None))
        if interstate is None:
            assumed_intrastate_bill_ids.add(bill.id)
            interstate = False

        if interstate:
            cgst = ZERO
            sgst = ZERO
            igst = total_tax
        else:
            cgst = _q2(total_tax / Decimal("2")) if total_tax > 0 else ZERO
            sgst = _q2(total_tax - cgst)
            igst = ZERO

        slab = slabs.setdefault(gst_pct, _empty_slab(gst_pct))
        slab["taxable_amount"] += taxable
        slab["cgst"] += cgst
        slab["sgst"] += sgst
        slab["igst"] += igst
        slab["total_tax"] += total_tax
        slab["total_amount"] += amount
        slab["item_count"] += 1
        included_bill_ids.add(bill.id)

    slab_list = [_slab_to_output(s) for _, s in sorted(slabs.items(), key=lambda kv: kv[0])]

    warnings = []
    if undated_bill_ids:
        warnings.append(
            f"{len(undated_bill_ids)} confirmed bill(s) have no invoice_date and were excluded from this period; set invoice dates to include them."
        )
    if assumed_intrastate_bill_ids:
        warnings.append(
            f"{len(assumed_intrastate_bill_ids)} included bill(s) defaulted to intra-state CGST/SGST because tenant/distributor GSTIN state could not be determined."
        )

    # Sales/output estimates (additive). Keep report generation resilient.
    try:
        sales_output = _compute_sales_output_estimates(db, tenant_id, year, month)
    except Exception:
        sales_output = {
            "period_basis": "sale.sold_at",
            "slabs": [],
            "grand_taxable_amount": 0.0,
            "grand_cgst": 0.0,
            "grand_sgst": 0.0,
            "grand_igst": 0.0,
            "grand_total_tax": 0.0,
            "grand_total_amount": 0.0,
            "sale_count": 0,
            "note": "Sales/output estimates unavailable.",
        }

    return {
        "year": year,
        "month": month,
        "month_label": date(year, month, 1).strftime("%B %Y"),
        "period_basis": "bill.invoice_date",
        "slabs": slab_list,
        "grand_taxable_amount": float(_q2(sum(_d(s["taxable_amount"]) for s in slab_list))),
        "grand_cgst": float(_q2(sum(_d(s["cgst"]) for s in slab_list))),
        "grand_sgst": float(_q2(sum(_d(s["sgst"]) for s in slab_list))),
        "grand_igst": float(_q2(sum(_d(s["igst"]) for s in slab_list))),
        "grand_total_tax": float(_q2(sum(_d(s["total_tax"]) for s in slab_list))),
        "grand_total_amount": float(_q2(sum(_d(s["total_amount"]) for s in slab_list))),
        "bill_count": len(included_bill_ids),
        # Additive Issue 6 fields (backward-compatible)
        "undated_bill_count": len(undated_bill_ids),
        "undated_bill_ids": sorted(undated_bill_ids),
        "assumed_intrastate_bill_count": len(assumed_intrastate_bill_ids),
        "warnings": warnings,
        "sales_output_estimates": sales_output,
    }


def generate_gst_report_pdf(report: dict, pharmacy_name: str = "Pharmacy") -> bytes:
    """Renders the purchase report data as a printable PDF for the CA."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"{pharmacy_name} — GST Purchase Summary", styles["Title"]))
    elements.append(Paragraph(f"Period: {report.get('month_label')}", styles["Normal"]))
    elements.append(Paragraph(f"Basis: {report.get('period_basis', 'bill.invoice_date')}", styles["Normal"]))
    elements.append(Paragraph(f"Confirmed bills in this period: {report.get('bill_count', 0)}", styles["Normal"]))
    if report.get("undated_bill_count"):
        elements.append(Paragraph(
            f"Excluded undated confirmed bills: {report['undated_bill_count']} (set invoice dates to include).",
            styles["Normal"],
        ))
    elements.append(Spacer(1, 12))

    table_data = [["GST %", "Taxable Amt (₹)", "CGST (₹)", "SGST (₹)", "IGST (₹)", "Total Tax (₹)", "Total Amt (₹)"]]
    for s in report.get("slabs", []):
        table_data.append([
            f"{float(s.get('gst_pct', 0)):.1f}%",
            f"{float(s.get('taxable_amount', 0)):,.2f}",
            f"{float(s.get('cgst', 0)):,.2f}",
            f"{float(s.get('sgst', 0)):,.2f}",
            f"{float(s.get('igst', 0)):,.2f}",
            f"{float(s.get('total_tax', 0)):,.2f}",
            f"{float(s.get('total_amount', 0)):,.2f}",
        ])
    table_data.append([
        "TOTAL",
        f"{float(report.get('grand_taxable_amount', 0)):,.2f}",
        f"{float(report.get('grand_cgst', 0)):,.2f}",
        f"{float(report.get('grand_sgst', 0)):,.2f}",
        f"{float(report.get('grand_igst', 0)):,.2f}",
        f"{float(report.get('grand_total_tax', 0)):,.2f}",
        f"{float(report.get('grand_total_amount', 0)):,.2f}",
    ])

    table = Table(table_data, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1c1c1e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f0f0f0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))

    warnings = report.get("warnings") or []
    for w in warnings:
        elements.append(Paragraph(f"Warning: {w}", styles["Italic"]))
    if warnings:
        elements.append(Spacer(1, 8))

    elements.append(Paragraph(
        "Note: figures are derived from confirmed purchase bills recorded in the system. "
        "CGST/SGST/IGST split is determined from GSTIN state codes when available; "
        "verify against original invoices before filing. Sales/output estimates (if any) are separate and indicative.",
        styles["Italic"],
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer.read()
