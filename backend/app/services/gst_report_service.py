"""
GST report generation for the shop's Chartered Accountant.

Real bills split GST as CGST + SGST (intra-state purchases), each exactly
half of the total GST%. Since bill_items stores the combined gst_pct and
final amount (see bill_parser.py / cost_calculator.py), the taxable amount
and tax split are derived back out per line item:

    taxable_amount = amount / (1 + gst_pct/100)
    total_tax      = amount - taxable_amount
    cgst = sgst    = total_tax / 2

Grouped by GST% "slab" (5%, 12%, 18%, etc.) - this is exactly the format a
CA expects for GSTR filing, since different slabs are reported separately.
"""
from datetime import date
from decimal import Decimal
from io import BytesIO

from sqlalchemy.orm import Session

from app import models


def get_gst_report(db: Session, year: int, month: int) -> dict:
    items = (
        db.query(models.BillItem)
        .join(models.Bill, models.Bill.id == models.BillItem.bill_id)
        .filter(models.Bill.status == "confirmed", models.Bill.year == year, models.Bill.month == month)
        .filter(models.BillItem.amount.isnot(None), models.BillItem.gst_pct.isnot(None))
        .all()
    )

    slabs: dict[float, dict] = {}
    bill_ids = set()

    for item in items:
        bill_ids.add(item.bill_id)
        gst_pct = float(item.gst_pct or 0)
        amount = float(item.amount or 0)
        if amount <= 0:
            continue

        taxable = amount / (1 + gst_pct / 100) if gst_pct > 0 else amount
        total_tax = amount - taxable
        cgst = sgst = total_tax / 2

        slab = slabs.setdefault(gst_pct, {
            "gst_pct": gst_pct, "taxable_amount": 0.0, "cgst": 0.0, "sgst": 0.0,
            "total_tax": 0.0, "total_amount": 0.0, "item_count": 0,
        })
        slab["taxable_amount"] += taxable
        slab["cgst"] += cgst
        slab["sgst"] += sgst
        slab["total_tax"] += total_tax
        slab["total_amount"] += amount
        slab["item_count"] += 1

    slab_list = sorted(slabs.values(), key=lambda s: s["gst_pct"])
    for s in slab_list:
        for key in ("taxable_amount", "cgst", "sgst", "total_tax", "total_amount"):
            s[key] = round(s[key], 2)

    return {
        "year": year,
        "month": month,
        "month_label": date(year, month, 1).strftime("%B %Y"),
        "slabs": slab_list,
        "grand_taxable_amount": round(sum(s["taxable_amount"] for s in slab_list), 2),
        "grand_cgst": round(sum(s["cgst"] for s in slab_list), 2),
        "grand_sgst": round(sum(s["sgst"] for s in slab_list), 2),
        "grand_total_tax": round(sum(s["total_tax"] for s in slab_list), 2),
        "grand_total_amount": round(sum(s["total_amount"] for s in slab_list), 2),
        "bill_count": len(bill_ids),
    }


def generate_gst_report_pdf(report: dict) -> bytes:
    """Renders the same report data as a printable PDF for the CA."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Kush Medical Hall — GST Purchase Summary", styles["Title"]))
    elements.append(Paragraph(f"Period: {report['month_label']}", styles["Normal"]))
    elements.append(Paragraph(f"Confirmed bills in this period: {report['bill_count']}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    table_data = [["GST %", "Taxable Amt (₹)", "CGST (₹)", "SGST (₹)", "Total Tax (₹)", "Total Amt (₹)"]]
    for s in report["slabs"]:
        table_data.append([
            f"{s['gst_pct']:.1f}%", f"{s['taxable_amount']:,.2f}", f"{s['cgst']:,.2f}",
            f"{s['sgst']:,.2f}", f"{s['total_tax']:,.2f}", f"{s['total_amount']:,.2f}",
        ])
    table_data.append([
        "TOTAL", f"{report['grand_taxable_amount']:,.2f}", f"{report['grand_cgst']:,.2f}",
        f"{report['grand_sgst']:,.2f}", f"{report['grand_total_tax']:,.2f}", f"{report['grand_total_amount']:,.2f}",
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
    elements.append(Spacer(1, 16))
    elements.append(Paragraph(
        "Note: figures are derived from confirmed purchase bills recorded in the system. "
        "CGST/SGST assume intra-state purchases split equally; verify against original "
        "invoices for interstate (IGST) transactions before filing.",
        styles["Italic"],
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer.read()