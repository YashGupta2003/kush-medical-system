"""Generate 3 crisp realistic Indian Wholesale Pharmacy Tax Invoice PDFs for live OCR demo.

Outputs cleanly to <repo_root>/demo_bills/ using high-contrast print layout
(dark ink on light paper, horizontal dividers only without cramped vertical grid
lines) and medicines from Kush Medical Hall (tenant_id=1) so PDF-to-PNG +
Tesseract/Vision OCR + Groq/heuristic parsing + RapidFuzz auto-matching all work
accurately during live demos.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle


INVOICES = [
    {
        "filename": "01_Hari_Krishna_Distributor_Tax_Invoice.pdf",
        "distributor": "HARI KRISHNA DISTRIBUTOR",
        "address": "Plot 14, Bhagirath Palace Pharma Market, Chandni Chowk, New Delhi - 110006",
        "gstin": "07AABCH1234F1Z1",
        "dl_no": "DL-ND-20B/48219 & 21B/48220",
        "phone": "+91 98100 11223",
        "invoice_no": "HK-DEMO-2026-101",
        "invoice_date": "26-11-2026",
        "tax_type": "CGST + SGST (Intra-State Delhi 07)",
        "items": [
            # (Particulars, Pack, Batch, Exp, Qty, Free, Rate, Disc%, MRP, GST%)
            ("DOLO 650 TABLETS", "15T", "DL2611A", "08/27", 20, 2, 26.80, 0, 33.50, 5),
            ("PAN-D CAPSULES", "15C", "PD2609X", "11/27", 15, 1, 159.20, 2, 199.00, 12),
            ("MONTEK-LC TABLETS", "10T", "ML2610K", "06/28", 30, 3, 148.00, 5, 185.00, 12),
            ("AZITHRAL 500 TABLETS", "5T", "AZ2607M", "04/27", 12, 0, 105.60, 0, 132.00, 12),
            ("AMLOKIND-AT TABS", "15T", "AM2605R", "09/27", 25, 2, 58.00, 0, 72.50, 12),
            ("CALPOL 650", "15T", "CP2612B", "10/27", 20, 2, 35.20, 0, 37.49, 5),
        ],
    },
    {
        "filename": "02_Rathore_Medicos_Tax_Invoice.pdf",
        "distributor": "RATHORE MEDICOS",
        "address": "Shop 88, Sector-7 Wholesale Complex, Rohini, New Delhi - 110085",
        "gstin": "07AACCR5678G1Z2",
        "dl_no": "DL-RH-20B/71904 & 21B/71905",
        "phone": "+91 98100 22334",
        "invoice_no": "RM-DEMO-2026-205",
        "invoice_date": "26-11-2026",
        "tax_type": "CGST + SGST (Intra-State Delhi 07)",
        "items": [
            ("AUGMENTIN 625 DUO", "10T", "AG2611Z", "05/28", 10, 1, 178.80, 0, 223.50, 12),
            ("TELMA 40 TABLETS", "15T", "TM2608P", "07/27", 20, 2, 112.00, 5, 140.00, 12),
            ("GLYCOMET-GP 1 TABLETS", "15T", "GL2603C", "03/28", 25, 2, 102.40, 2, 128.00, 12),
            ("COMBIFLAM TABLETS", "20T", "CB2604D", "12/27", 30, 3, 36.80, 0, 46.00, 12),
            ("SHELCAL 500 TABLETS", "15T", "SH2609N", "11/27", 18, 1, 111.60, 0, 139.50, 18),
        ],
    },
    {
        "filename": "03_Apex_Lifecare_Interstate_IGST.pdf",
        "distributor": "APEX LIFECARE MUMBAI",
        "address": "Unit 402, Pharma Hub SEZ, Andheri East, Mumbai, Maharashtra - 400093",
        "gstin": "27AABCA9988M1Z5",
        "dl_no": "MH-MUM-20B/99210 & 21B/99211",
        "phone": "+91 98204 45566",
        "invoice_no": "AL-DEMO-2026-309",
        "invoice_date": "26-11-2026",
        "tax_type": "IGST (Inter-State Maharashtra 27 -> Delhi 07)",
        "items": [
            ("ECOSPRIN 75", "14T", "EC2611T", "10/28", 40, 4, 17.57, 0, 24.52, 5),
            ("ZERODOL P", "10T", "ZD2604A", "08/27", 20, 2, 80.68, 5, 114.83, 12),
            ("AZEE 500", "5T", "AZE2609", "09/27", 15, 1, 82.85, 2, 125.04, 12),
            ("CLAVAM 625", "10T", "CLV2610", "07/28", 12, 1, 162.76, 0, 234.63, 12),
            ("CROCIN PAIN FORTE", "15T", "CPF2608", "06/28", 25, 2, 25.07, 0, 35.03, 5),
        ],
    },
]


def build_invoice_pdf(spec: dict, out_path: str) -> None:
    width, height = A4
    c = canvas.Canvas(out_path, pagesize=A4)
    c.setTitle(f"{spec['distributor']} - {spec['invoice_no']}")

    c.setFillColor(colors.white)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # Outer paper border covering ~92% of page so OpenCV auto-crop frames whole invoice cleanly
    margin = 8 * mm
    c.setStrokeColor(colors.HexColor("#334155"))
    c.setLineWidth(1.2)
    c.rect(margin, margin, width - 2 * margin, height - 2 * margin, fill=0, stroke=1)

    # High-contrast light banner with crisp dark ink (survives adaptive thresholding cleanly)
    banner_h = 26 * mm
    c.setFillColor(colors.HexColor("#f1f5f9"))
    c.rect(margin, height - margin - banner_h, width - 2 * margin, banner_h, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#0d9488"))
    c.setLineWidth(2.0)
    c.line(margin, height - margin - banner_h, width - margin, height - margin - banner_h)

    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica-Bold", 15)
    c.drawString(margin + 5 * mm, height - margin - 9 * mm, spec["distributor"])
    c.setFont("Helvetica", 9)
    c.drawString(margin + 5 * mm, height - margin - 15 * mm, spec["address"])
    c.drawString(
        margin + 5 * mm,
        height - margin - 20.5 * mm,
        f"GSTIN: {spec['gstin']}  |  DL No: {spec['dl_no']}  |  Ph: {spec['phone']}",
    )

    c.setFillColor(colors.HexColor("#0f766e"))
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(width - margin - 5 * mm, height - margin - 9 * mm, "TAX INVOICE")
    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica-Bold", 9.5)
    c.drawRightString(width - margin - 5 * mm, height - margin - 15.5 * mm, f"Invoice: {spec['invoice_no']}")
    c.setFont("Helvetica", 9)
    c.drawRightString(width - margin - 5 * mm, height - margin - 21 * mm, f"Date: {spec['invoice_date']}")

    # Buyer Block
    meta_y = height - margin - banner_h - 23 * mm
    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(margin + 5 * mm, meta_y + 14 * mm, "Billed To: KUSH MEDICAL HALL")
    c.setFont("Helvetica", 9)
    c.drawString(margin + 5 * mm, meta_y + 8.5 * mm, "Main Market, Rohini Sector 7, New Delhi - 110085  |  Buyer GSTIN: 07AAACK9999A1Z5")
    c.drawString(margin + 5 * mm, meta_y + 3 * mm, f"Supply Type: {spec['tax_type']}")

    # Table (no vertical dividers, crisp spacing, dark bold header on soft gray)
    rows = [
        ["PARTICULARS", "PACK", "BATCH", "EXP", "QTY", "FREE", "RATE", "DISC", "MRP", "GST", "AMOUNT"]
    ]

    total_taxable = 0.0
    total_gst = 0.0
    grand_total = 0.0

    for name, pack, batch, exp, qty, free_q, rate, disc, mrp, gst in spec["items"]:
        taxable = round(qty * rate * (1.0 - disc / 100.0), 2)
        tax_amt = round(taxable * (gst / 100.0), 2)
        line_amt = round(taxable + tax_amt, 2)
        total_taxable += taxable
        total_gst += tax_amt
        grand_total += line_amt
        rows.append([
            name,
            pack,
            batch,
            exp,
            f"{qty}",
            f"{free_q}",
            f"{rate:.2f}",
            f"{disc}",
            f"{mrp:.2f}",
            f"{gst}",
            f"{line_amt:.2f}",
        ])

    col_widths = [
        48 * mm,  # PARTICULARS
        13 * mm,  # PACK
        20 * mm,  # BATCH
        13 * mm,  # EXP
        11 * mm,  # QTY
        11 * mm,  # FREE
        16 * mm,  # RATE
        11 * mm,  # DISC
        16 * mm,  # MRP
        11 * mm,  # GST
        20 * mm,  # AMOUNT
    ]  # sum = 190mm cleanly centered inside 194mm frame

    tbl = Table(rows, colWidths=col_widths, rowHeights=[10 * mm] + [11 * mm] * len(spec["items"]))
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9.2),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#0f172a")),
        ("ALIGN", (0, 0), (3, -1), "LEFT"),
        ("ALIGN", (4, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEABOVE", (0, 0), (-1, 0), 1.0, colors.HexColor("#0f172a")),
        ("LINEBELOW", (0, 0), (-1, 0), 1.0, colors.HexColor("#0f172a")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("LINEBELOW", (0, -1), (-1, -1), 1.0, colors.HexColor("#0f172a")),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))

    tw, th = tbl.wrapOn(c, width - 2 * margin, height)
    table_y = meta_y - 6 * mm - th
    tbl.drawOn(c, margin + 2 * mm, table_y)

    # Summary Block
    sum_y = table_y - 34 * mm
    c.setFillColor(colors.HexColor("#f8fafc"))
    c.setStrokeColor(colors.HexColor("#64748b"))
    c.setLineWidth(0.8)
    c.rect(width - margin - 78 * mm, sum_y, 74 * mm, 26 * mm, fill=1, stroke=1)

    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica", 9.5)
    c.drawString(width - margin - 74 * mm, sum_y + 19 * mm, "Taxable Subtotal:")
    c.drawRightString(width - margin - 7 * mm, sum_y + 19 * mm, f"Rs. {total_taxable:,.2f}")
    c.drawString(width - margin - 74 * mm, sum_y + 12.5 * mm, "Total GST Tax:")
    c.drawRightString(width - margin - 7 * mm, sum_y + 12.5 * mm, f"Rs. {total_gst:,.2f}")
    c.line(width - margin - 74 * mm, sum_y + 9.5 * mm, width - margin - 7 * mm, sum_y + 9.5 * mm)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(width - margin - 74 * mm, sum_y + 3.5 * mm, "NET PAYABLE:")
    c.drawRightString(width - margin - 7 * mm, sum_y + 3.5 * mm, f"Rs. {grand_total:,.2f}")

    # Footer
    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.HexColor("#334155"))
    c.drawString(margin + 5 * mm, margin + 14 * mm, "Declaration: Certified that supplied medicines are genuine and GST has been charged as applicable.")
    c.drawString(margin + 5 * mm, margin + 8 * mm, "Terms: Subject to Delhi Jurisdiction | Demo Invoice for PharmOs OCR Verification.")
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#0f172a"))
    c.drawRightString(width - margin - 5 * mm, margin + 8 * mm, f"For {spec['distributor']}")

    c.showPage()
    c.save()


def main():
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "demo_bills"))
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for spec in INVOICES:
        out_path = os.path.join(out_dir, spec["filename"])
        build_invoice_pdf(spec, out_path)
        paths.append(out_path)
        print("Generated:", out_path)
    return paths


if __name__ == "__main__":
    main()
