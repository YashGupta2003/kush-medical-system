"""Comprehensive idempotent demo data seeder for PharmOs (Kush Medical Hall).

Populates tenant_id=1 ('Kush Medical Hall') with 610+ realistic Indian medicines,
salt/graph links, distributors, historical confirmed & pending bills, GST slabs
(CGST/SGST + IGST), expiry batches (expired/critical/warning/upcoming/missing),
65+ days of seasonal POS sales & invoices (activating Holt-Winters forecasts),
manual stock adjustments (for anomaly detection), cold-chain fridges & excursion
logs, customer udhaar & adherence refill alerts, surveillance & k>=3 regional pulse
heatmaps, prescriptions ready for POS, network listings, notifications, and a
valid SHA-256 TrustChain audit trail.

Usage:
    cd backend
    PYTHONPATH=. venv/bin/python scripts/seed_demo_data.py
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image, ImageDraw
from sqlalchemy import text

from app import models
from app.core.cache import invalidate_analytics_cache
from app.database import SessionLocal, bypass_tenant_filter, tenant_context
from app.services import (
    audit_service,
    composition_service,
    cross_tenant_integrity_service,
    customer_service,
    graph_service,
    heatmap_service,
    reorder_intelligence,
    surveillance_service,
    trust_score_service,
)
from app.services.auth_service import hash_password
from app.services.cost_calculator import compute_cost_per_unit

RNG = random.Random(20261126)

# 25 realistic therapeutic families mapping cleanly onto curated salt_conditions
DRUG_FAMILIES = [
    ("PARACETAMOL 650 MG", "15 TABS", 5.0, [
        "CALPOL 650", "CROCIN PAIN", "PACIMOL 650", "DOLOPAR 650", "METACIN 650",
        "PYRIGESIC 650", "PARACIP 650", "FEBRINIL 650", "XTAPARA 650", "THERMADOL 650",
        "DOLOWIN P650", "SUMO L 650", "BIOCETAMOL 650", "PARAFIT 650", "MALIDENS 650",
    ], ["GSK", "MICRO LABS", "IPCA", "CIPLA", "ALKEM"], (28, 48)),
    ("PARACETAMOL 500 MG", "15 TABS", 5.0, [
        "CROCIN ADVANCE", "CALPOL 500", "P-500 TAB", "PACIMOL 500", "DOLOPAR 500",
        "METACIN 500", "PYRIGESIC 500", "SUMO L 500", "PARACIP 500", "FEBREX 500",
        "NOVALGIN P", "TYLENOL 500", "DOLOMAX 500", "ZEPAMOL 500", "ANACIN P",
    ], ["GSK", "IPCA", "CIPLA", "MICRO LABS"], (18, 34)),
    ("IBUPROFEN 400 MG + PARACETAMOL 325 MG", "15 TABS", 12.0, [
        "IBUGESIC PLUS", "FLEXON", "ZUCOFLAM", "BRUFEN P", "BRUPARA",
        "COMBIPARA", "DOLOFLEX", "RELIFLAM", "PAINGONE P", "IBUPARA FORTE",
        "SYMOFLAM", "TRIFLAM", "ORTHOFLAM", "KINETIC P", "ALFLAM PLUS",
    ], ["CIPLA", "ARISTO", "SANOFI", "ABBOTT"], (38, 65)),
    ("DICLOFENAC 50 MG + PARACETAMOL 325 MG", "10 TABS", 12.0, [
        "VOVERAN PLUS", "DYNAPAR DP", "REACTIN PLUS", "NAC PLUS", "DICLOGESIC",
        "DICLOMOL", "OXALGIN DP", "ZYDUS NAC P", "RELAXYL DP", "JONAC PLUS",
        "POWERGESIC", "MAGNADOL", "DOLAR DP", "DICLOWIN PLUS", "ARTHO P",
    ], ["NOVARTIS", "TROIKAA", "SUN PHARMA", "CIPLA", "ZYDUS"], (45, 95)),
    ("ACECLOFENAC 100 MG + PARACETAMOL 325 MG", "10 TABS", 12.0, [
        "ZERODOL P", "HIFENAC P", "ACECLO PLUS", "ALTRAZ P", "DOLOKIND PLUS",
        "SIGNODOL P", "ACENAC P", "ACEROC P", "ACEMIZ PLUS", "MOVEXX P",
        "ACESET P", "CHYMORAL AP", "ZOFLAM P", "RELICEK P", "DOLOWIN PLUS",
    ], ["IPCA", "INTAS", "MANKIND", "ARISTO", "TORRENT"], (55, 115)),
    ("ASPIRIN 75 MG", "14 TABS", 5.0, [
        "ECOSPRIN 75", "LOPRIN 75", "DELISPRIN 75", "DISPRIN CV", "ASPIKIND 75",
        "CARDIOSPRIN 75", "ASA 75", "PLATELET 75", "ECOHEART 75", "VASOSPRIN 75",
        "CORASPRIN 75", "MYOSPRIN 75", "CLOTGUARD 75", "ASPIGUARD 75", "ASPILIFE 75",
    ], ["USV", "TORRENT", "MANKIND", "SUN PHARMA"], (10, 26)),
    ("WARFARIN 5 MG", "10 TABS", 5.0, [
        "WARF 5", "UNIWARFIN 5", "SOFWARF 5", "COUMADIN IND", "THROMBOWARF 5",
        "WARFOKIND 5", "ANTICOAG 5", "WARFCIP 5", "HEMAWARF 5", "CARDIOWARF 5",
    ], ["CIPLA", "UNICHEM", "MANKIND"], (32, 75)),
    ("AMOXICILLIN 500 MG + CLAVULANIC ACID 125 MG", "10 TABS", 12.0, [
        "CLAVAM 625", "MOXIKIND CV 625", "ADVENT 625", "SENSICLAV 625", "MEGA-CV 625",
        "AUGPEN 625", "MOXCV 625", "AMOXICLAV 625", "ACUVIN 625", "BACTICLAV 625",
        "CLAVURID 625", "INCV 625", "CLAVOMED 625", "POLICLAV 625", "SYNERMOX 625",
    ], ["ALKEM", "MANKIND", "CIPLA", "ARISTO", "SUN PHARMA"], (165, 245)),
    ("AZITHROMYCIN 500 MG", "5 TABS", 12.0, [
        "AZEE 500", "ZITHROX 500", "ATM 500", "AZIKIND 500", "AZIVENT 500",
        "AZIBACT 500", "ZATHRIN 500", "AZICIP 500", "AZIMAX 500", "ZADY 500",
        "AZITHRO 500", "MACROZIT 500", "AZIFAST 500", "ZETRA 500", "AZICARE 500",
    ], ["CIPLA", "MACLEODS", "INDOCO", "MANKIND", "FBD"], (95, 148)),
    ("CIPROFLOXACIN 500 MG", "10 TABS", 12.0, [
        "CIPLOX 500", "CIFRAN 500", "CIPROBID 500", "CIPRODAC 500", "C-FLOX 500",
        "BAYCIP 500", "CIPROCIN 500", "ZOFLOX CIP", "MICROFLOX 500", "QUINOCIP 500",
        "ALCIP 500", "CIPROKIND 500", "CIPROWIN 500", "CIPROMAX 500", "URICAP CIP",
    ], ["CIPLA", "SUN PHARMA", "ZYDUS", "MANKIND"], (40, 82)),
    ("PANTOPRAZOLE 40 MG + DOMPERIDONE 30 MG", "15 CAPS", 12.0, [
        "PANTOCID DSR", "PANTOP DSR", "PANTODAC DSR", "PANSEC DSR", "PANTAKIND DSR",
        "NEXPRO RD", "PENTAB D", "PANTIN DSR", "ULPAN DSR", "GASOPAN DSR",
        "ACIDBAN DSR", "PANORAY DSR", "PANCURE DSR", "DOMPAN SR", "PEPTILOC D",
    ], ["SUN PHARMA", "ARISTO", "ZYDUS", "CIPLA", "MANKIND"], (140, 225)),
    ("PANTOPRAZOLE 40 MG", "15 TABS", 12.0, [
        "PAN 40", "PANTOCID 40", "PANTOP 40", "PANTODAC 40", "PANTAKIND 40",
        "PANSEC 40", "PANTOZOL 40", "PANORAY 40", "ACIGUARD 40", "GASTROPAN 40",
        "PANALOC 40", "PANTAFER 40", "PANWIN 40", "ZYPAN 40", "ALKOPAN 40",
    ], ["ALKEM", "SUN PHARMA", "ARISTO", "ZYDUS", "MANKIND"], (110, 175)),
    ("AMLODIPINE 5 MG + ATENOLOL 50 MG", "15 TABS", 12.0, [
        "AMLOPRES AT", "STAMLO BETA", "AMLOGARD AT", "AMLOSAFE AT", "AMLOVAS AT",
        "BETANICARD AM", "AMLOAT 5/50", "CARDIOKIND AT", "TENORMIN AM", "AMLODAC AT",
        "AMLOTEN", "HYPERTEN AT", "VASOCARE AT", "PRESSDOWN AT", "NORMABP AT",
    ], ["CIPLA", "DR. REDDY'S", "PFIZER", "MANKIND", "ZYDUS"], (65, 118)),
    ("TELMISARTAN 40 MG", "15 TABS", 12.0, [
        "TELMIKIND 40", "TAZLOC 40", "SARTEL 40", "TELVAS 40", "CRESAR 40",
        "TELPRES 40", "TELMAGE 40", "TELMIHEAL 40", "TELSA 40", "TELMED 40",
        "TELMIWELL 40", "ERITEL 40", "TELSAR 40", "TELMIMAX 40", "INDITEL 40",
    ], ["MANKIND", "USV", "INTAS", "ARISTO", "CIPLA"], (95, 168)),
    ("METFORMIN 500 MG + GLIMEPIRIDE 1 MG", "15 TABS", 12.0, [
        "AMARYL M1", "GLIMESTAR M1", "AZULIX 1 MF", "GLUCONORM G1", "GEMER 1",
        "GLIMISAVE M1", "METGIM 1", "DIAPRIDE M1", "GLIMEPREX MF1", "ZORYL M1",
        "EUGLIM M1", "GLIMIKIND M1", "SEMIGLY M1", "SUGARMID G1", "BETAGLIM M1",
    ], ["SANOFI", "MANKIND", "TORRENT", "LUPIN", "SUN PHARMA"], (105, 165)),
    ("METFORMIN 500 MG", "20 TABS", 5.0, [
        "GLYCOMET 500 SR", "OBIMET SR 500", "GLUCONORM SR 500", "CETAPIN XR 500", "METLONG 500",
        "FORMIN SR 500", "GLYCIPHAGE SR 500", "OKAMET 500", "MELMET SR 500", "METFOR 500",
        "DIABEMET 500", "EXERMET 500", "METOSAFE 500", "BIGOMET SR 500", "MEFORM 500",
    ], ["USV", "ABBOTT", "LUPIN", "FRANCO-INDIAN", "CIPLA"], (42, 85)),
    ("MONTELUKAST 10 MG + LEVOCETIRIZINE 5 MG", "10 TABS", 12.0, [
        "MONTAIR LC", "TELEKAST L", "MONTEK LC KID", "ROMILAST L", "ODIMONT LC",
        "MONTINA L", "SOLITAIRE LC", "L-MOKIND", "MONTELUK LC", "AIRMIST LC",
        "ALLERGO LC", "CETMONT L", "BREATHEZ LC", "MONTAZ L", "LEVMONT 10/5",
    ], ["CIPLA", "LUPIN", "SUN PHARMA", "ARISTO", "INTAS"], (155, 225)),
    ("LEVOCETIRIZINE 5 MG", "10 TABS", 12.0, [
        "LEVOZET 5", "TECZINE 5", "LEVOCET 5", "LEVOSIZ 5", "VOZET 5",
        "XYVOZ 5", "OKACET L", "ALERCET L", "HISTAFREE 5", "LESUR 5",
        "LEVORID 5", "ALLERGIN L", "LEVOTEC 5", "CITZIN L", "NOALLERGY L",
    ], ["SUN PHARMA", "CIPLA", "SYSTOPIC", "DR. REDDY'S"], (55, 92)),
    ("ATORVASTATIN 10 MG", "15 TABS", 12.0, [
        "ATORVA 10", "TONACT 10", "STORVAS 10", "LIPVAS 10", "ATORKIND 10",
        "ATOCOR 10", "LIPITOR 10 IND", "MODLIP 10", "STATOR 10", "ASTOR 10",
        "MACTOR 10", "LIPICURE 10", "LIPIGARD 10", "ATORMED 10", "CHOLESTAT 10",
    ], ["ZYDUS", "LUPIN", "SUN PHARMA", "CIPLA", "MANKIND"], (88, 155)),
    ("NITROGLYCERIN 2.6 MG", "30 TABS", 12.0, [
        "NITROLONG 2.6", "GTN SORBITRATE CR 2.6", "NITROCONTIN 2.6", "MONOTRATE OD", "ANGISPAN TR 2.6",
        "CORONIT 2.6", "MYONIT SR 2.6", "VASOTRATE CR", "CARDIONIT 2.6", "ANGINIL 2.6",
    ], ["ABBOTT", "MODI MUNDI", "TORRENT"], (145, 240)),
    ("CALCIUM 500 MG + VITAMIN D3 250 IU", "15 TABS", 12.0, [
        "SHELCAL 500 HD", "CIPCAL 500", "CALCIMAX 500", "OSTEOFOS D3", "GEMCAL D3",
        "BONEFIT 500", "CALCIKIND PLUS", "SUPRACAL", "CALCIDOL 500", "OROCAL 500",
        "CALCIROL TAB", "NUTRICAL D3", "CALCIVIT 500", "MAXICAL 500", "OSTEOCAL 500",
    ], ["TORRENT", "CIPLA", "ALKEM", "MANKIND", "PHARMED"], (115, 195)),
    ("INSULIN GLARGINE 100 IU", "3 ML PEN", 5.0, [
        "LANTUS SOLOSTAR", "BASALOG REFILL", "GLARITUS PEN", "TOUJEO PEN", "BASAGLAR CARTRIDGE",
        "INULIN G PEN", "GLARGIKIND 100", "SEMGLEE PEN", "GLARGEN 100", "LONGBASAL 100",
    ], ["SANOFI", "BIOCON", "WOCKHARDT", "ELI LILLY"], (520, 890)),
    ("CEFIXIME 200 MG", "10 TABS", 12.0, [
        "TAXIM O 200", "ZIFI 200", "MAHACEF 200", "CEFOLAC 200", "OMNIX 200",
        "GRAMOCEF O 200", "MILIXIM 200", "FIXCOM 200", "CEFIX 200", "TOPCEF 200",
        "CEFSPAN 200", "TRICEF 200", "HICEF 200", "CEFIKIND 200", "XIME 200",
    ], ["ALKEM", "FDC", "MANKIND", "CIPLA", "ARISTO"], (95, 145)),
    ("METRONIDAZOLE 400 MG", "15 TABS", 5.0, [
        "FLAGYL 400", "METROGYL 400", "ARISTOGYL 400", "METRON 400", "UNIMEZOL 400",
        "ENTROGYL 400", "AMEBAGYL 400", "METROCIP 400", "METROKIND 400", "PROTOGYL 400",
    ], ["ABBOTT", "JB CHEMICALS", "ARISTO", "CIPLA"], (22, 42)),
    ("FUROSEMIDE 40 MG", "15 TABS", 5.0, [
        "LASIX 40", "FRUSELAC 40", "FUROX 40", "DIURIL IND 40", "LASIKIND 40",
        "FLUIDEX 40", "EDEMEX 40", "FRUSIX 40", "AQUAFOR 40", "LASIX RETARD",
    ], ["SANOFI", "MANKIND", "CIPLA"], (18, 44)),
]


def _norm(text_val: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text_val.upper())


def _create_sample_images(uploads_dir: str) -> tuple[str, str]:
    os.makedirs(uploads_dir, exist_ok=True)
    bill_path = os.path.join(uploads_dir, "demo_bill_sample.png")
    rx_path = os.path.join(uploads_dir, "demo_rx_sample.png")

    img = Image.new("RGB", (820, 560), color=(250, 252, 255))
    d = ImageDraw.Draw(img)
    lines = [
        "HARI KRISHNA DISTRIBUTOR - TAX INVOICE",
        "GSTIN: 07AABCH1234F1Z1 | Invoice: HK-DEMO-901 | Date: 2026-11-24",
        "---------------------------------------------------------------------",
        "PARTICULARS                  PACK    QTY  FREE  RATE     MRP    GST%",
        "DOLO 650 TABLETS            15T      20    2   26.80   33.50   5%",
        "AUGMENTIN 625 DUO           10T      10    1  178.80  223.50  12%",
        "PAN-D CAPSULES              15C      15    1  159.20  199.00  12%",
        "COMBIFLAM TABLETS           20T      25    0   36.80   46.00  12%",
    ]
    for i, line in enumerate(lines):
        d.text((28, 30 + i * 38), line, fill=(20, 32, 48))
    img.save(bill_path, format="PNG")

    rx = Image.new("RGB", (760, 500), color=(255, 255, 250))
    drx = ImageDraw.Draw(rx)
    rx_lines = [
        "Dr. A. K. Verma, MD (Medicine) | City Care Clinic",
        "Patient: Rahul Sharma | Date: 2026-11-26",
        "----------------------------------------------------------",
        "Rx:",
        "1. Tab AUGMENTIN 625 DUO  x 10 tabs   (1-0-1 x 5 days)",
        "2. Cap PAN-D              x 15 caps   (1-0-0 before breakfast)",
        "3. Tab DOLO 650           x 15 tabs   (SOS for fever > 100F)",
    ]
    for i, line in enumerate(rx_lines):
        drx.text((28, 32 + i * 44), line, fill=(18, 28, 42))
    rx.save(rx_path, format="PNG")
    return bill_path, rx_path


def main():
    db = SessionLocal()
    try:
        # 1. Clean reset of transactional & catalog extensions while preserving core tenants/reference
        with bypass_tenant_filter(db):
            # Delete tenant_id=1 transactional tables cleanly in FK order
            for tbl in [
                "audit_ledger",
                "notifications",
                "prescription_items",
                "prescriptions",
                "cold_chain_readings",
                "cold_chain_units",
                "customer_credit_ledger",
                "stock_ledger",
                "rate_history",
                "medicine_batches",
                "sales",
                "sale_invoices",
                "sale_invoice_counters",
                "bill_items",
                "bills",
                "reorder_items",
                "network_listings",
                "distributor_trust_scores",
                "distributor_field_accuracy",
                "distributor_bill_templates",
                "medicine_salts",
                "surveillance_daily_counts",
                "cross_tenant_batch_alerts",
                "regional_health_alerts",
                "region_heatmap_snapshots",
                "region_heatmap_runs",
            ]:
                db.execute(text(f"DELETE FROM {tbl}"))
            db.execute(text("DELETE FROM graph_edges WHERE tenant_id IS NOT NULL"))
            db.execute(text("DELETE FROM medicines WHERE tenant_id = 1 AND id > 10"))
            db.commit()

            # 2. Set known local demo passwords cleanly
            owner_u = db.query(models.User).filter_by(tenant_id=1, username="kushmedical@gmail.com").first()
            staff_u = db.query(models.User).filter_by(tenant_id=1, username="staff@kushmedical.com").first()
            metro_u = db.query(models.User).filter_by(tenant_id=2, username="metromedical@gmail.com").first()
            if owner_u:
                owner_u.password_hash = hash_password("Kush@1234")
            if staff_u:
                staff_u.password_hash = hash_password("Staff@1234")
            if metro_u:
                metro_u.password_hash = hash_password("Metro@1234")

            # Ensure 3rd regional tenant in DELHI_NORTH exists for k>=3 PharmOs Pulse heatmap
            partner_tenant = db.query(models.Tenant).filter_by(slug="arogya-kendra").first()
            if not partner_tenant:
                partner_tenant = models.Tenant(
                    slug="arogya-kendra",
                    shop_name="Arogya Kendra Pharmacy",
                    owner_name="Dr. Meera Nair",
                    email="arogya@example.com",
                    phone="9899112233",
                    gstin="07AAEFA4321K1Z8",
                    city="New Delhi",
                    plan="pro",
                    is_active=True,
                    email_verified=True,
                    region_code="DELHI_NORTH",
                    surveillance_opt_in=True,
                )
                db.add(partner_tenant)
                db.flush()

            # Ensure Metro Medical also opted in DELHI_NORTH so k=3 in DELHI_NORTH
            t2 = db.get(models.Tenant, 2)
            if t2:
                t2.region_code = "DELHI_NORTH"
                t2.surveillance_opt_in = True
            db.commit()

        # Everything below runs cleanly scoped to Kush Medical Hall (tenant_id=1) unless noted
        with tenant_context(db, 1):
            # 3. Ensure distributors (3 existing + 2 additional including interstate 27... for IGST)
            dist_specs = [
                ("Hari Krishna Distributor", "9810011223", "07AABCH1234F1Z1"),
                ("Rathore Medicos", "9810022334", "07AACCR5678G1Z2"),
                ("Verma Bros Pharmaceuticals", "9810033445", "07AADCV9012H1Z3"),
                ("Apex Lifecare Mumbai", "9820445566", "27AABCA9988M1Z5"),   # Interstate IGST
                ("Medline Surgical & Cold", "9811998877", "07AADCM4455K1Z9"),
            ]
            distributors = []
            for name, phone, gstin in dist_specs:
                d = db.query(models.Distributor).filter_by(tenant_id=1, name=name).first()
                if not d:
                    d = models.Distributor(tenant_id=1, name=name, phone=phone, gstin=gstin)
                    db.add(d)
                    db.flush()
                distributors.append(d)

            # Reset initial 10 medicines stock thresholds neatly
            base_meds = db.query(models.Medicine).filter(models.Medicine.tenant_id == 1, models.Medicine.id <= 10).all()
            existing_norms = {_norm(m.particulars) for m in base_meds}
            existing_barcodes = {m.barcode for m in base_meds if m.barcode}

            # 4. Add 610 realistic Indian pharmacy medicines (so >= 620 total in Kush Medical Hall)
            suffix_variants = ["TAB", "FORTE", "PLUS", "DS", "SR"]
            new_meds = []
            barcode_seq = 8901100000100
            target_new_count = 610

            candidates = []
            for comp, unit, gst, brands, companies, (min_mrp, max_mrp) in DRUG_FAMILIES:
                for brand in brands:
                    for var_idx, suf in enumerate(suffix_variants):
                        name = brand if var_idx == 0 else f"{brand} {suf}"
                        comp_name = companies[(len(name) + var_idx) % len(companies)]
                        dist_obj = distributors[(len(name) + var_idx) % len(distributors)]
                        candidates.append((name, unit, comp, comp_name, dist_obj.name, min_mrp, max_mrp, gst))

            for idx, (name, unit, comp, company, stockist, min_mrp, max_mrp, _gst) in enumerate(candidates):
                if len(new_meds) >= target_new_count:
                    break
                norm = _norm(name)
                if norm in existing_norms:
                    continue
                existing_norms.add(norm)

                mrp = round(RNG.uniform(min_mrp, max_mrp), 2)
                # Mix margins cleanly: mostly healthy 20-32%, some thin ~13%, a few critical ~7%
                if idx % 17 == 0:
                    margin = RNG.uniform(0.06, 0.09)
                elif idx % 9 == 0:
                    margin = RNG.uniform(0.11, 0.16)
                else:
                    margin = RNG.uniform(0.20, 0.34)
                net_rate = round(mrp * (1.0 - margin), 2)

                # Deliberately seed ~24 low-stock SKUs, ~25 high-stock dead-stock SKUs, rest healthy
                if idx < 22:
                    threshold = 30
                    stock = RNG.randint(2, 22)
                elif idx < 48:
                    threshold = 15
                    stock = RNG.randint(55, 160)
                else:
                    threshold = RNG.choice([10, 15, 20, 25, 30])
                    stock = RNG.randint(threshold + 15, threshold + 190)

                barcode_seq += 1
                bc = str(barcode_seq)
                while bc in existing_barcodes:
                    barcode_seq += 1
                    bc = str(barcode_seq)
                existing_barcodes.add(bc)

                med = models.Medicine(
                    tenant_id=1,
                    particulars=name,
                    normalized_name=norm,
                    unit=unit,
                    mrp=mrp,
                    net_rate=net_rate,
                    company=company,
                    stockist=stockist,
                    current_stock=stock,
                    low_stock_threshold=threshold,
                    lead_time_days=RNG.choice([2, 3, 4, 5, 7]),
                    barcode=bc,
                    composition=comp,
                )
                db.add(med)
                new_meds.append(med)

            db.flush()
            all_meds = base_meds + new_meds
            # Ensure demo flagship medicines have realistic stock levels & 4 fast-moving items trigger Smart Purchase
            for idx_m, m_obj in enumerate(all_meds[:12]):
                if 7 <= idx_m <= 10:
                    m_obj.current_stock = [4, 6, 5, 8][idx_m - 7]
                    m_obj.low_stock_threshold = 25
                elif float(m_obj.current_stock or 0) < 40:
                    m_obj.current_stock = 65
            db.flush()
            print(f"Seeded medicines for Kush Medical Hall: {len(all_meds)} total")

            # Parse salts cleanly for all 620 medicines + build PharmaGraph in fast batch
            meds_by_salt_set = {}
            for m in all_meds:
                if not m.composition:
                    continue
                parsed_list = composition_service.parse_composition(m.composition)
                salt_key = tuple(sorted(p.salt_name for p in parsed_list))
                meds_by_salt_set.setdefault(salt_key, []).append(m)
                for parsed in parsed_list:
                    db.add(models.MedicineSalt(
                        tenant_id=1, medicine_id=m.id, salt_name=parsed.salt_name, strength=parsed.strength
                    ))
                    db.add(models.GraphEdge(
                        tenant_id=1, source_type="medicine", source_id=str(m.id),
                        edge_type="CONTAINS", target_type="salt", target_id=parsed.salt_name,
                    ))

            sub_count = 0
            for salt_key, group_meds in meds_by_salt_set.items():
                if not salt_key or len(group_meds) < 2:
                    continue
                for m in group_meds:
                    for peer in group_meds[:26]:
                        if peer.id == m.id:
                            continue
                        db.add(models.GraphEdge(
                            tenant_id=1,
                            source_type="medicine",
                            source_id=str(m.id),
                            edge_type="SUBSTITUTES",
                            target_type="medicine",
                            target_id=str(peer.id),
                            weight=100.0,
                            edge_metadata=json.dumps({"match_type": "exact"}),
                        ))
                        sub_count += 1

            inter_count = graph_service.seed_interaction_edges(db)
            treat_count = graph_service.seed_condition_edges(db)
            db.flush()
            print(f"PharmaGraph built fast: contains={len(all_meds)}, substitutes={sub_count}, interactions={inter_count}, treats={treat_count}")

            # 5. Generate sample PNG bill & prescription images
            uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
            bill_img, rx_img = _create_sample_images(uploads_dir)

            # 6. Distributor templates & field accuracy (ADM confidence badges)
            template_cols = json.dumps({"particulars": 0, "qty": 2, "rate": 4, "mrp": 5})
            for d_idx, d in enumerate(distributors):
                db.add(models.DistributorBillTemplate(
                    tenant_id=1,
                    distributor_id=d.id,
                    header_signature=f"PARTICULARS|PACK|QTY|FREE|RATE|MRP|GST::{d.id}",
                    column_field_map=template_cols,
                    sample_count=12 if d_idx == 0 else (6 if d_idx == 1 else 4),
                    last_confirmed_at=datetime.now(timezone.utc) - timedelta(days=d_idx + 1),
                ))
                for fname, total_n, corr_n in (
                    [("name", 80, 2), ("qty", 80, 1), ("rate", 80, 2), ("mrp", 80, 1), ("batch", 80, 3)]
                    if d_idx != 1
                    else [("name", 40, 2), ("qty", 40, 3), ("rate", 40, 2), ("batch", 40, 14), ("exp_date", 40, 15)]
                ):
                    db.add(models.DistributorFieldAccuracy(
                        tenant_id=1,
                        distributor_id=d.id,
                        field_name=fname,
                        times_total=total_n,
                        times_corrected=corr_n,
                    ))
            db.flush()

            # 7. Bills (18 confirmed across last 6 months + 2 pending_review/needs_attention) + Batches + RateHistory
            today = date.today()
            now_utc = datetime.now(timezone.utc)
            top_meds = all_meds[:16]
            confirmed_bill_items = []

            # Month offsets 5..0 (0 = current month, ensuring rich data this month!)
            bills_per_month = [2, 2, 3, 3, 3, 5]
            inv_counter = 100
            for m_offset_idx, count in enumerate(bills_per_month):
                m_back = 5 - m_offset_idx
                # Compute target (year, month) cleanly
                y, mo = today.year, today.month - m_back
                while mo <= 0:
                    mo += 12
                    y -= 1
                for j in range(count):
                    inv_counter += 1
                    dist = distributors[(inv_counter + j) % len(distributors)]
                    day_num = min(26, 4 + j * 4)
                    inv_date = date(y, mo, day_num)
                    inv_no = f"HK-{y}{mo:02d}-{inv_counter}"
                    bill = models.Bill(
                        tenant_id=1,
                        distributor_id=dist.id,
                        invoice_no=inv_no,
                        invoice_date=inv_date,
                        year=y,
                        month=mo,
                        image_path=bill_img,
                        status="confirmed",
                        uploaded_at=datetime(y, mo, day_num, 11, 30, tzinfo=timezone.utc),
                        ocr_confidence=round(RNG.uniform(91.0, 98.5), 2),
                        checksum=hashlib.sha256(inv_no.encode()).hexdigest(),
                        confirmed_invoice_key=f"1:{dist.id}:{inv_no}",
                    )
                    db.add(bill)
                    db.flush()

                    bill_total = 0.0
                    # Mix 5%, 12%, 18% GST slabs across line items; guarantee fast_meds distributor links
                    if m_offset_idx == len(bills_per_month) - 1 and j == 0:
                        chosen_meds = all_meds[7:12]
                    elif m_offset_idx == len(bills_per_month) - 1 and j == 1:
                        chosen_meds = all_meds[0:5]
                    else:
                        chosen_meds = RNG.sample(top_meds + all_meds[16:40], k=5)
                    for k_idx, m in enumerate(chosen_meds):
                        qty = RNG.choice([10, 15, 20, 25])
                        free_qty = 2 if qty >= 20 else (1 if k_idx % 2 == 0 else 0)
                        gst_pct = [5.0, 12.0, 12.0, 18.0, 5.0][k_idx % 5]
                        disc_pct = RNG.choice([0.0, 2.0, 5.0])
                        rate = float(m.net_rate or 50.0)
                        line_amt = round(qty * rate * (1 - disc_pct / 100.0) * (1 + gst_pct / 100.0), 2)
                        cost_u = compute_cost_per_unit(rate, qty, disc_pct, 0.0, gst_pct, free_qty)
                        bill_total += line_amt

                        bi = models.BillItem(
                            tenant_id=1,
                            bill_id=bill.id,
                            medicine_id=m.id,
                            raw_name=m.particulars,
                            pack=m.unit,
                            batch=f"B{y%100}{mo:02d}{inv_counter}{k_idx}",
                            exp_date=f"{((mo + 8) % 12) + 1:02d}/{str(y + 1)[-2:]}",
                            qty=qty,
                            free_qty=free_qty,
                            mrp=float(m.mrp or 80.0),
                            rate=rate,
                            discount_pct=disc_pct,
                            special_discount_pct=0.0,
                            gst_pct=gst_pct,
                            amount=line_amt,
                            computed_cost_per_unit=cost_u,
                            match_confidence=97.0,
                            match_status="auto",
                        )
                        db.add(bi)
                        db.flush()
                        confirmed_bill_items.append((bi, bill, m))
                        graph_service.sync_supplies_edge(db, dist.id, m.id)

                    bill.total_amount = round(bill_total, 2)

            # Add 2 pending bills for BillHistory / ReviewBill live demo
            for p_status, conf, note in [
                ("pending_review", 94.2, None),
                ("needs_attention", 61.5, "Skewed scan header detected on line 3; verify expiry column."),
            ]:
                inv_counter += 1
                pb = models.Bill(
                    tenant_id=1,
                    distributor_id=distributors[0].id,
                    invoice_no=f"DRAFT-{inv_counter}",
                    invoice_date=today,
                    year=today.year,
                    month=today.month,
                    image_path=bill_img,
                    status=p_status,
                    uploaded_at=now_utc - timedelta(hours=2),
                    ocr_confidence=conf,
                    needs_attention_reason=note,
                    total_amount=4280.0,
                )
                db.add(pb)
                db.flush()
                for m in all_meds[:3]:
                    db.add(models.BillItem(
                        tenant_id=1,
                        bill_id=pb.id,
                        medicine_id=m.id if p_status == "pending_review" else None,
                        raw_name=m.particulars,
                        pack=m.unit,
                        batch=f"NEW-{inv_counter}",
                        exp_date="08/27" if p_status == "pending_review" else None,
                        qty=10,
                        free_qty=1,
                        mrp=float(m.mrp or 100.0),
                        rate=float(m.net_rate or 75.0),
                        gst_pct=12.0,
                        amount=round(10 * float(m.net_rate or 75.0) * 1.12, 2),
                        match_confidence=96.0 if p_status == "pending_review" else 42.0,
                        match_status="auto" if p_status == "pending_review" else "unmatched",
                    ))
            db.flush()

            # 8. Medicine Batches across every urgency bucket + 3 missing expiry + 1 distributor batch collision
            urgency_offsets = [
                -18, -9, -3,                    # expired
                2, 4, 6, 7,                     # critical (<= 7d)
                14, 19, 24, 28, 30,             # warning (<= 30d)
                45, 68, 95, 130, 180, 240,      # upcoming
                None, None, None,               # missing expiry
            ]
            cold_chain_meds = [m for m in all_meds if "INSULIN" in (m.composition or "") or "GLARGINE" in (m.composition or "")]
            batch_pool = confirmed_bill_items[:len(urgency_offsets)]
            created_batches = []
            for idx, (bi, bill, m) in enumerate(batch_pool):
                off = urgency_offsets[idx]
                exp_dt = None if off is None else (today + timedelta(days=off))
                is_cc = idx in (12, 13)
                target_med_id = cold_chain_meds[0].id if (is_cc and cold_chain_meds) else m.id
                batch_no = "COLLIDE-99X" if idx == 4 else (bi.batch or f"BATCH-{idx+100}")
                mb = models.MedicineBatch(
                    tenant_id=1,
                    medicine_id=target_med_id,
                    batch_no=batch_no,
                    expiry_date=exp_dt,
                    qty_received=float(bi.qty or 10) + float(bi.free_qty or 0),
                    bill_item_id=bi.id,
                    distributor_id=bill.distributor_id,
                    is_cold_chain=is_cc,
                )
                db.add(mb)
                created_batches.append(mb)

            # Create confirmed Bill + BillItem + MedicineBatch on Tenant 1 & Tenant 2 for AUGMENTIN 625 DUO ("COLLIDE-99X")
            # so both Supply Trust Score (intra-tenant collision) AND Batch Integrity Scan Now (cross-tenant collision) persist open alerts!
            aug_med = db.query(models.Medicine).filter(
                models.Medicine.tenant_id == 1,
                models.Medicine.particulars.ilike("%AUGMENTIN%"),
            ).first() or confirmed_bill_items[4][2]
            other_dist = distributors[1] if distributors[1].id != distributors[0].id else distributors[2]
            for d_obj, inv_suffix, unit_rate in [
                (distributors[0], f"COL-T1A-{inv_counter+9}", round(float(aug_med.net_rate or 170.0), 2)),
                (other_dist, f"COL-T1B-{inv_counter+10}", round(float(aug_med.net_rate or 170.0) * 0.55, 2)),
            ]:
                col_bill = models.Bill(
                    tenant_id=1,
                    distributor_id=d_obj.id,
                    invoice_no=inv_suffix,
                    invoice_date=today - timedelta(days=4),
                    year=today.year,
                    month=today.month,
                    image_path=bill_img,
                    status="confirmed",
                    uploaded_at=now_utc - timedelta(days=4),
                    total_amount=round(10 * unit_rate * 1.12, 2),
                    confirmed_invoice_key=f"1:{d_obj.id}:{inv_suffix}",
                )
                db.add(col_bill)
                db.flush()
                col_bi = models.BillItem(
                    tenant_id=1,
                    bill_id=col_bill.id,
                    medicine_id=aug_med.id,
                    raw_name=aug_med.particulars,
                    batch="COLLIDE-99X",
                    qty=10,
                    mrp=float(aug_med.mrp or 223.5),
                    rate=unit_rate,
                    gst_pct=12.0,
                    amount=round(10 * unit_rate * 1.12, 2),
                )
                db.add(col_bi)
                db.flush()
                db.add(models.MedicineBatch(
                    tenant_id=1,
                    medicine_id=aug_med.id,
                    batch_no="COLLIDE-99X",
                    expiry_date=today + timedelta(days=120),
                    qty_received=10,
                    bill_item_id=col_bi.id,
                    distributor_id=d_obj.id,
                    is_cold_chain=False,
                ))
            db.flush()

            # 9. RateHistory entries (routine + 2 outlier price spikes + margin compression triggers)
            for idx, (bi, bill, m) in enumerate(confirmed_bill_items[:10]):
                old_r = float(m.net_rate or 80.0)
                if idx == 0:
                    new_r = round(old_r * 2.15, 2)  # +115% price anomaly!
                elif idx == 1:
                    new_r = round(old_r * 1.48, 2)  # +48% margin compression!
                elif idx == 2:
                    new_r = round(old_r * 0.72, 2)  # low-cost grey-market outlier for TrustScore!
                else:
                    new_r = round(old_r * RNG.uniform(1.02, 1.07), 2)
                db.add(models.RateHistory(
                    tenant_id=1,
                    medicine_id=m.id,
                    bill_item_id=bi.id,
                    old_net_rate=old_r,
                    new_net_rate=new_r,
                    old_mrp=float(m.mrp or 120.0),
                    new_mrp=float(m.mrp or 120.0),
                    changed_at=now_utc - timedelta(days=idx * 5 + 2),
                ))
            db.flush()

            # 10. Customers, Consent, Udhaar Credit Ledger & Overdue Refill History
            cust_specs = [
                ("9811122233", "Rahul Sharma", True),
                ("9822233344", "Amit Verma", True),
                ("9833344455", "Sunita Devi", True),
                ("9844455566", "Rajeshwari Devi", True),
                ("9855566677", "Mohit Agarwal", False),
                ("9866677788", "Priya Nair", True),
                ("9877788899", "Suresh Bansal", False),
                ("9888899900", "Kavita Joshi", True),
            ]
            customers = []
            for phone, cname, consented in cust_specs:
                c = customer_service.get_or_create_customer(db, phone=phone, tenant_id=1, name=cname, consented=consented)
                if consented and not c.consent_given_at:
                    c.consent_given_at = now_utc - timedelta(days=90)
                customers.append(c)
            db.flush()

            customer_service.charge_credit(db, customers[0].id, 1450.0, tenant_id=1, note="Monthly chronic prescription pack")
            customer_service.record_payment(db, customers[0].id, 600.0, tenant_id=1, note="UPI partial settlement")
            customer_service.charge_credit(db, customers[2].id, 420.0, tenant_id=1, note="Insulin & glucometer strips")

            # 11. 70 Days of Historical POS Sales + SaleInvoices + StockLedger (drives Holt-Winters!)
            invoice_seq = 0
            fast_meds = all_meds[:12]
            ledger_balances = {m.id: float(m.current_stock or 50) for m in all_meds[:20]}

            for days_ago in range(70, 0, -1):
                sale_dt = now_utc - timedelta(days=days_ago)
                weekday = sale_dt.weekday()
                # Weekly seasonality: Monday (0) and Saturday (5) sell higher volumes
                season_mult = 2 if weekday in (0, 5) else 1
                num_invoices = 1 if days_ago % 2 == 1 else 2

                for _ in range(num_invoices):
                    invoice_seq += 1
                    cust = customers[invoice_seq % len(customers)] if invoice_seq % 3 == 0 else None
                    pay_mode = RNG.choice(["cash", "upi", "upi", "card"])
                    inv_obj = models.SaleInvoice(
                        tenant_id=1,
                        invoice_number=f"INV-2026-{invoice_seq:04d}",
                        customer_id=cust.id if cust else None,
                        payment_mode=pay_mode,
                        subtotal_amount=0,
                        tax_amount=0,
                        total_amount=0,
                        total_profit=0,
                        created_by_user_id=owner_u.id if (invoice_seq % 2 == 0 or not staff_u) else staff_u.id,
                        sold_at=sale_dt,
                    )
                    db.add(inv_obj)
                    db.flush()

                    inv_sub = 0.0
                    inv_tax = 0.0
                    inv_tot = 0.0
                    inv_prof = 0.0

                    # Pick 3-5 items per invoice from top medicines so all 12 have >=30 sale days (Holt-Winters)
                    line_meds = RNG.sample(fast_meds, k=5 if season_mult == 2 else 3)
                    for m in line_meds:
                        qty = float(season_mult * RNG.choice([1, 2]))
                        mrp_u = float(m.mrp or 50.0)
                        cost_u = float(m.net_rate or 38.0)
                        gst_pct = 5.0 if "PARACETAMOL" in (m.composition or "") else 12.0
                        line_total = round(qty * mrp_u, 2)
                        line_sub = round(line_total / (1.0 + gst_pct / 100.0), 2)
                        line_tax = round(line_total - line_sub, 2)
                        line_prof = round(qty * (mrp_u - cost_u), 2)

                        inv_sub += line_sub
                        inv_tax += line_tax
                        inv_tot += line_total
                        inv_prof += line_prof

                        sale_row = models.Sale(
                            tenant_id=1,
                            medicine_id=m.id,
                            qty_sold=qty,
                            sold_at=sale_dt,
                            customer_id=cust.id if cust else None,
                            sale_invoice_id=inv_obj.id,
                            medicine_name_snapshot=m.particulars,
                            medicine_composition_snapshot=m.composition,
                            unit_mrp_snapshot=mrp_u,
                            unit_cost_snapshot=cost_u,
                            gst_pct_snapshot=gst_pct,
                            line_subtotal=line_sub,
                            line_tax_amount=line_tax,
                            line_total=line_total,
                            line_profit=line_prof,
                        )
                        db.add(sale_row)
                        db.flush()

                        bal = ledger_balances.get(m.id, float(m.current_stock or 50))
                        db.add(models.StockLedger(
                            tenant_id=1,
                            medicine_id=m.id,
                            change_qty=-qty,
                            resulting_balance=bal,
                            reason="sale",
                            reference_sale_id=sale_row.id,
                            note=f"POS {inv_obj.invoice_number}",
                            created_by_user_id=inv_obj.created_by_user_id,
                            created_at=sale_dt,
                        ))

                    inv_obj.subtotal_amount = round(inv_sub, 2)
                    inv_obj.tax_amount = round(inv_tax, 2)
                    inv_obj.total_amount = round(inv_tot, 2)
                    inv_obj.total_profit = round(inv_prof, 2)

            # Seed explicit recurring chronic adherence pattern for 2 consented customers (gap ~28d, overdue > 42d)
            for cust_idx, med_idx in [(0, 5), (2, 8)]:  # TELMA 40 & GLYCOMET-GP 1
                cm = all_meds[med_idx]
                for d_back in [74, 46]:
                    sdt = now_utc - timedelta(days=d_back)
                    qty = 2.0
                    mrp_u = float(cm.mrp or 130.0)
                    cost_u = float(cm.net_rate or 100.0)
                    lt = round(qty * mrp_u, 2)
                    ls = round(lt / 1.12, 2)
                    db.add(models.Sale(
                        tenant_id=1,
                        medicine_id=cm.id,
                        qty_sold=qty,
                        sold_at=sdt,
                        customer_id=customers[cust_idx].id,
                        medicine_name_snapshot=cm.particulars,
                        medicine_composition_snapshot=cm.composition,
                        unit_mrp_snapshot=mrp_u,
                        unit_cost_snapshot=cost_u,
                        gst_pct_snapshot=12.0,
                        line_subtotal=ls,
                        line_tax_amount=round(lt - ls, 2),
                        line_total=lt,
                        line_profit=round(qty * (mrp_u - cost_u), 2),
                    ))

            # Update SaleInvoiceCounter so live POS checkout starts sequentially
            db.add(models.SaleInvoiceCounter(tenant_id=1, last_number=invoice_seq))

            # Seed manual_adjustment StockLedger rows for Anomaly Detection (Inventory Drift + Staff outlier)
            adj_samples = [
                (all_meds[10].id, -2, "Broken tablet strip", owner_u.id, 18),
                (all_meds[11].id, -1, "Sample display unit", owner_u.id, 15),
                (all_meds[12].id, -3, "Physical count match", staff_u.id if staff_u else owner_u.id, 12),
                (all_meds[13].id, -2, "Blister torn during rack shift", staff_u.id if staff_u else owner_u.id, 10),
                (all_meds[14].id, 2, "Found extra unopened strip", staff_u.id if staff_u else owner_u.id, 8),
                (all_meds[15].id, -4, "Damaged strip returned", staff_u.id if staff_u else owner_u.id, 6),
                (all_meds[16].id, -2, "Shelf recount adjustment", staff_u.id if staff_u else owner_u.id, 4),
                (all_meds[17].id, -45, "Large missing stock discrepancy", staff_u.id if staff_u else owner_u.id, 2),
            ]
            for mid, cqty, note, uid, dback in adj_samples:
                med_obj = db.get(models.Medicine, mid)
                db.add(models.StockLedger(
                    tenant_id=1,
                    medicine_id=mid,
                    change_qty=cqty,
                    resulting_balance=float(med_obj.current_stock or 20),
                    reason="manual_adjustment",
                    note=note,
                    created_by_user_id=uid,
                    created_at=now_utc - timedelta(days=dback),
                ))

            # Reorder items
            for m in all_meds[7:10]:
                db.add(models.ReorderItem(
                    tenant_id=1,
                    medicine_id=m.id,
                    distributor_id=distributors[0].id,
                    quantity_needed=30,
                    note="Low stock demo reorder queue",
                    source="auto_low_stock",
                    fulfilled=False,
                ))

            db.flush()
            # Compute smart thresholds for top medicines
            for m in fast_meds:
                reorder_intelligence.compute_smart_threshold(db, m.id)

            # 12. Cold-Chain Units & Readings
            u1 = models.ColdChainUnit(
                tenant_id=1, unit_label="Main Vaccine Fridge", location_note="Counter Rear Bay", min_temp_c=2.0, max_temp_c=8.0
            )
            u2 = models.ColdChainUnit(
                tenant_id=1, unit_label="Insulin Chiller B", location_note="Storage Room Wall B", min_temp_c=2.0, max_temp_c=8.0
            )
            db.add_all([u1, u2])
            db.flush()

            for day_back in range(10, -1, -1):
                for unit, t_val, exc, note in [
                    (u1, 10.6 if day_back == 1 else round(RNG.uniform(3.8, 5.4), 1), day_back == 1, "Compressor check" if day_back == 1 else "Morning log"),
                    (u2, 11.4 if day_back == 3 else round(RNG.uniform(4.0, 5.8), 1), day_back == 3, "Power fluctuation alert" if day_back == 3 else "Afternoon log"),
                ]:
                    db.add(models.ColdChainReading(
                        tenant_id=1,
                        unit_id=unit.id,
                        recorded_temp_c=t_val,
                        recorded_by_user_id=owner_u.id,
                        recorded_at=now_utc - timedelta(days=day_back, hours=3),
                        note=note,
                        is_excursion=exc,
                    ))

            # 13. Inter-Pharmacy Nodes & Listings
            node_self = db.query(models.PharmacyNode).filter_by(tenant_id=1, is_self=True).first()
            if not node_self:
                node_self = models.PharmacyNode(
                    tenant_id=1, shop_name="Kush Medical Hall", contact_phone="9876543210", is_self=True, opted_in=True
                )
                db.add(node_self)
            node_peer = db.query(models.PharmacyNode).filter_by(tenant_id=1, shop_name="City Care Chemist (Rohini)").first()
            if not node_peer:
                node_peer = models.PharmacyNode(
                    tenant_id=1, shop_name="City Care Chemist (Rohini)", contact_phone="9811445566", is_self=False, opted_in=True
                )
                db.add(node_peer)
            db.flush()

            for ltype, mname, comp, qty, exp_off, note_txt, n_id in [
                ("near_expiry", "COMBIFLAM TABLETS", "IBUPROFEN 400 MG + PARACETAMOL 325 MG", 35, 19, "Near-expiry surplus @ 15% off MRP", node_self.id),
                ("excess_stock", "PAN-D CAPSULES", "PANTOPRAZOLE 40 MG + DOMPERIDONE 30 MG", 20, 24, "Available for same-day transfer", node_self.id),
                ("shortage_request", "MONTEK-LC TABLETS", "MONTELUKAST 10 MG + LEVOCETIRIZINE 5 MG", 15, None, "Urgent prescription demand", node_peer.id),
                ("near_expiry", "AUGMENTIN 625 DUO", "AMOXICILLIN 500 MG + CLAVULANIC ACID 125 MG", 12, 35, "Peer pharmacy surplus stock", node_peer.id),
            ]:
                db.add(models.NetworkListing(
                    tenant_id=1,
                    pharmacy_node_id=n_id,
                    listing_type=ltype,
                    medicine_name=mname,
                    composition=comp,
                    quantity=qty,
                    expiry_date=today + timedelta(days=exp_off) if exp_off else None,
                    note=note_txt,
                    status="open",
                ))

            # 14. Prescriptions (2 ready for one-tap POS prefill, 1 converted)
            rx_specs = [
                ("ready", False, "Dr. A. K. Verma", "City Care Clinic", now_utc - timedelta(minutes=45), customers[0].id),
                ("ready", False, "Dr. Neha Kapoor", "Sunrise Polyclinic", now_utc - timedelta(minutes=12), customers[2].id),
                ("converted", True, "Dr. R. Malhotra", "North Delhi Heart Center", now_utc - timedelta(days=2), customers[1].id),
            ]
            for r_status, conv, doc_n, clinic_n, cr_at, cid in rx_specs:
                rx_row = models.Prescription(
                    tenant_id=1,
                    customer_id=cid,
                    image_path=rx_img,
                    status=r_status,
                    converted_to_sale=conv,
                    purchased_at=(cr_at + timedelta(minutes=10)) if conv else None,
                    raw_ocr_text=f"Rx {doc_n} - AUGMENTIN 625, PAN-D, DOLO 650",
                    ocr_confidence=95.4,
                    doctor_name=doc_n,
                    clinic_name=clinic_n,
                    created_at=cr_at,
                )
                db.add(rx_row)
                db.flush()
                for m_item, dos in [(all_meds[1], "1-0-1 x 5 days"), (all_meds[2], "1-0-0 before meals"), (all_meds[0], "SOS fever")]:
                    db.add(models.PrescriptionItem(
                        tenant_id=1,
                        prescription_id=rx_row.id,
                        medicine_id=m_item.id,
                        raw_name=m_item.particulars,
                        qty_prescribed=10,
                        dosage_instructions=dos,
                        match_confidence=98.0,
                        match_status="auto",
                        in_stock=True,
                        current_stock_qty=float(m_item.current_stock or 10),
                        added_to_cart=conv,
                    ))

            # 15. Notifications (unread + read) using exact models.Notification Enum values
            notif_samples = [
                ("anomaly_flagged", "Critical Cold Chain Excursion: Vaccine Fridge", "Recorded 10.6°C above safe 2–8°C threshold.", "critical", False),
                ("near_expiry", "4 Batches Expiring Within 7 Days", "Review near-expiry shelf items and list surplus on Pharma Network.", "warning", False),
                ("adherence_overdue", "2 Patients Overdue for Chronic Refill", "Rahul Sharma (TELMA 40) & Sunita Devi (GLYCOMET-GP 1) are overdue.", "info", False),
                ("regional_health_spike", "Surveillance Spike: Fever (DELHI_NORTH)", "Fever OTC signals spiked across 3+ pharmacies in DELHI_NORTH.", "warning", False),
                ("cross_tenant_alert", "Network Batch Collision Detected", "Batch COLLIDE-99X flagged across multiple pharmacy nodes.", "critical", False),
                ("system", "Smart Reorder Thresholds Refreshed", "12 fast-moving medicines have updated 30-day reorder suggestions.", "info", True),
            ]
            for ntype, ntitle, nbody, nsev, is_r in notif_samples:
                db.add(models.Notification(
                    tenant_id=1,
                    recipient_user_id=None,
                    notification_type=ntype,
                    title=ntitle,
                    body=nbody,
                    severity=nsev,
                    channel="in_app",
                    is_read=is_r,
                    created_at=now_utc - timedelta(hours=1 if not is_r else 24),
                ))

            # 16. Surveillance signals across 14 days for tenant 1
            for d_back in range(14, -1, -1):
                cdate = today - timedelta(days=d_back)
                fever_u = 38 if d_back == 0 else (29 if d_back == 1 else RNG.randint(6, 11))
                pain_u = RNG.randint(8, 14)
                bact_u = 18 if d_back == 0 else RNG.randint(4, 8)
                acid_u = RNG.randint(5, 10)
                for cond_name, units in [
                    ("Fever", fever_u),
                    ("Pain", pain_u),
                    ("Bacterial Infection", bact_u),
                    ("Acidity", acid_u),
                ]:
                    db.add(models.SurveillanceDailyCount(
                        tenant_id=1,
                        condition_name=cond_name,
                        count_date=cdate,
                        otc_units=units,
                    ))

            # 17. TrustChain intact SHA-256 chain entries
            for b_item, bill_obj, med_obj in confirmed_bill_items[-6:]:
                audit_service.log_event(db, "bill_confirmed", bill_obj.id, {
                    "tenant_id": 1, "invoice_no": bill_obj.invoice_no, "total_amount": float(bill_obj.total_amount or 0)
                })
                audit_service.log_event(db, "batch_received", b_item.id, {
                    "tenant_id": 1, "medicine_id": med_obj.id, "qty": float(b_item.qty or 0)
                })
            audit_service.log_event(db, "rate_change", all_meds[0].id, {
                "tenant_id": 1, "medicine": all_meds[0].particulars, "note": "Verified post-invoice rate update"
            })
            audit_service.log_event(db, "cold_chain_reading", u1.id, {
                "tenant_id": 1, "unit": u1.unit_label, "recorded_temp_c": 10.6, "is_excursion": True
            })

            db.commit()

            # Compute Trust Scores for tenant 1
            trust_score_service.compute_all_distributor_scores(db)
            db.commit()

        # 18. Global cross-tenant Regional Pulse (k>=3 in DELHI_NORTH + suppressed k=2 condition) + Network Integrity
        with bypass_tenant_filter(db):
            t2 = db.get(models.Tenant, 2)
            t3 = db.query(models.Tenant).filter_by(slug="arogya-kendra").first()
            for partner in [t2, t3]:
                if not partner:
                    continue
                for d_back in range(14, -1, -1):
                    cdate = today - timedelta(days=d_back)
                    for cond_name, units in [
                        ("Fever", 34 if d_back <= 1 else RNG.randint(6, 10)),
                        ("Bacterial Infection", 16 if d_back == 0 else RNG.randint(4, 7)),
                    ]:
                        db.add(models.SurveillanceDailyCount(
                            tenant_id=partner.id,
                            condition_name=cond_name,
                            count_date=cdate,
                            otc_units=units,
                        ))
            # Add a k=2 suppressed condition ('Migraine') between tenant 1 & 2 only (NOT tenant 3)
            for t_id_sup in (1, 2):
                db.add(models.SurveillanceDailyCount(
                    tenant_id=t_id_sup, condition_name="Migraine", count_date=today, otc_units=12
                ))

            # Ensure Tenant 2 (Metro Medical Store) has matching confirmed BillItem for COLLIDE-99X from a second distributor
            t1_aug = db.query(models.Medicine).filter(
                models.Medicine.tenant_id == 1,
                models.Medicine.particulars.ilike("%AUGMENTIN%"),
            ).first()
            aug_particulars = t1_aug.particulars if t1_aug else "AUGMENTIN 625 DUO"
            if t2:
                t2_dist = db.query(models.Distributor).filter_by(tenant_id=t2.id, name="Unverified Parallel Wholesaler").first()
                if not t2_dist:
                    t2_dist = models.Distributor(
                        tenant_id=t2.id, name="Unverified Parallel Wholesaler", phone="9811009988", gstin="07AABCU9988K1Z2"
                    )
                    db.add(t2_dist)
                    db.flush()
                t2_med = db.query(models.Medicine).filter_by(tenant_id=t2.id, normalized_name=_norm(aug_particulars)).first()
                if not t2_med:
                    t2_med = models.Medicine(
                        tenant_id=t2.id,
                        particulars=aug_particulars,
                        normalized_name=_norm(aug_particulars),
                        unit="10 TABS",
                        mrp=223.5,
                        net_rate=165.0,
                        company="GSK",
                        current_stock=20,
                    )
                    db.add(t2_med)
                    db.flush()
                t2_bill = models.Bill(
                    tenant_id=t2.id,
                    distributor_id=t2_dist.id,
                    invoice_no="UPW-T2-901",
                    invoice_date=today - timedelta(days=2),
                    year=today.year,
                    month=today.month,
                    image_path=bill_img,
                    status="confirmed",
                    uploaded_at=now_utc - timedelta(days=2),
                    total_amount=1848.0,
                    confirmed_invoice_key=f"{t2.id}:{t2_dist.id}:UPW-T2-901",
                )
                db.add(t2_bill)
                db.flush()
                db.add(models.BillItem(
                    tenant_id=t2.id,
                    bill_id=t2_bill.id,
                    medicine_id=t2_med.id,
                    raw_name=aug_particulars,
                    batch="COLLIDE-99X",
                    qty=10,
                    mrp=223.5,
                    rate=165.0,
                    gst_pct=12.0,
                    amount=1848.0,
                ))

            db.add(models.RegionalHealthAlert(
                region_code="DELHI_NORTH",
                condition_name="Fever",
                alert_date=today,
                contributing_tenant_count=3,
                total_regional_units=106,
                regional_avg_units=27.4,
                z_score=3.42,
                severity="elevated",
                status="open",
            ))
            db.commit()

            # Compute genuine open CrossTenantBatchAlert rows via real collision scanner
            cross_tenant_integrity_service.scan_cross_tenant_collisions(db)

        heatmap_service.refresh_heatmap(db)
        invalidate_analytics_cache()

        print("\n=== DEMO DATA SEED COMPLETE ===")
        print("Medicines in Kush Medical Hall:", db.query(models.Medicine).filter_by(tenant_id=1).count())
        print("Audit Ledger Chain Verify:", audit_service.verify_chain(db))

    finally:
        db.close()


if __name__ == "__main__":
    main()
