"""
Clean Seeding Script for PharmOs.

Sets up:
1. Kush Medical Hall (Tenant #1)
   - Owner login: kushmedical@gmail.com / Password@123
   - Staff login: staff@kushmedical.com / Password@123
   - Top Indian pharmacy medicines with stock and composition
   - Distributors, Customers, and Initial Stock Ledger
2. Metro Medical Store (Tenant #2)
   - Owner login: metromedical@gmail.com / Password@123
   - Separate isolated medicines and distributors
   - Demonstrates that Tenant #2 CANNOT see Kush Medical's inventory or data!
"""
from datetime import datetime, timezone
from decimal import Decimal
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal, Base, engine, bypass_tenant_filter, tenant_context
from app import models
from app.services.auth_service import hash_password
from app.services.matcher import normalize
from app.services.clinical_reference_service import seed_clinical_data
from app.services.graph_service import sync_reference_graph_edges


def seed_database():
    print("Ensuring tables exist...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    with bypass_tenant_filter(db):
        print("Seeding clinical reference data (salts & interactions)...")
        seed_clinical_data(db)
        sync_reference_graph_edges(db)
        db.commit()

        # -------------------------------------------------------------
        # 1. Kush Medical Hall (Tenant 1)
        # -------------------------------------------------------------
        kush_tenant = db.query(models.Tenant).filter(models.Tenant.slug == "kush-medical").first()
        if not kush_tenant:
            kush_tenant = models.Tenant(
                slug="kush-medical",
                shop_name="Kush Medical Hall",
                owner_name="Kush Gupta",
                email="kushmedical@gmail.com",
                phone="9876543210",
                gstin="07AAAAA0000A1Z5",
                city="New Delhi",
                address="Shop No. 4, Main Market, Delhi",
                plan="pro",
                is_active=True,
                email_verified=True,
                region_code="DELHI_NORTH",
                surveillance_opt_in=True,
            )
            db.add(kush_tenant)
            db.commit()
            db.refresh(kush_tenant)
            print(f"Created Tenant: [{kush_tenant.id}] {kush_tenant.shop_name}")
        else:
            print(f"Tenant [{kush_tenant.id}] {kush_tenant.shop_name} already exists.")

        # Kush Medical Users
        kush_owner = db.query(models.User).filter(
            models.User.tenant_id == kush_tenant.id,
            models.User.username == "kushmedical@gmail.com",
        ).first()
        if not kush_owner:
            kush_owner = models.User(
                tenant_id=kush_tenant.id,
                username="kushmedical@gmail.com",
                password_hash=hash_password("Password@123"),
                full_name="Kush Gupta (Owner)",
                role="owner",
                is_active=True,
            )
            db.add(kush_owner)

        kush_staff = db.query(models.User).filter(
            models.User.tenant_id == kush_tenant.id,
            models.User.username == "staff@kushmedical.com",
        ).first()
        if not kush_staff:
            kush_staff = models.User(
                tenant_id=kush_tenant.id,
                username="staff@kushmedical.com",
                password_hash=hash_password("Password@123"),
                full_name="Ramesh Kumar (Staff)",
                role="staff",
                is_active=True,
            )
            db.add(kush_staff)
        db.commit()

        # -------------------------------------------------------------
        # Kush Medical Distributors
        # -------------------------------------------------------------
        distributors_data = [
            ("Hari Krishna Distributor", "07AABCH1234F1Z1", "9810011223", "Chandni Chowk, Delhi"),
            ("Rathore Medicos", "07AACCR5678G1Z2", "9810022334", "Bhagirath Palace, Delhi"),
            ("Verma Bros Pharmaceuticals", "07AADCV9012H1Z3", "9810033445", "Daryaganj, Delhi"),
        ]
        kush_dist_map = {}
        for d_name, d_gst, d_phone, d_addr in distributors_data:
            dist = db.query(models.Distributor).filter(
                models.Distributor.tenant_id == kush_tenant.id,
                models.Distributor.name == d_name,
            ).first()
            if not dist:
                dist = models.Distributor(
                    tenant_id=kush_tenant.id,
                    name=d_name,
                    gstin=d_gst,
                    phone=d_phone,
                    address=d_addr,
                )
                db.add(dist)
                db.commit()
                db.refresh(dist)
            kush_dist_map[d_name] = dist

        # -------------------------------------------------------------
        # Kush Medical Medicines Inventory
        # -------------------------------------------------------------
        medicines_data = [
            {
                "particulars": "DOLO 650 TABLETS",
                "unit": "15 TABS",
                "mrp": Decimal("33.50"),
                "net_rate": Decimal("26.80"),
                "company": "MICRO LABS",
                "stockist": "Hari Krishna Distributor",
                "current_stock": Decimal("120"),
                "low_stock_threshold": Decimal("30"),
                "composition": "PARACETAMOL 650 MG",
                "barcode": "8901148205461",
            },
            {
                "particulars": "AUGMENTIN 625 DUO",
                "unit": "10 TABS",
                "mrp": Decimal("223.50"),
                "net_rate": Decimal("178.80"),
                "company": "GSK",
                "stockist": "Rathore Medicos",
                "current_stock": Decimal("45"),
                "low_stock_threshold": Decimal("15"),
                "composition": "AMOXICILLIN 500 MG + CLAVULANIC ACID 125 MG",
                "barcode": "8901234567890",
            },
            {
                "particulars": "PAN-D CAPSULES",
                "unit": "15 CAPS",
                "mrp": Decimal("199.00"),
                "net_rate": Decimal("159.20"),
                "company": "ALKEM",
                "stockist": "Hari Krishna Distributor",
                "current_stock": Decimal("80"),
                "low_stock_threshold": Decimal("20"),
                "composition": "PANTOPRAZOLE 40 MG + DOMPERIDONE 30 MG",
                "barcode": "8902345678901",
            },
            {
                "particulars": "AZITHRAL 500 TABLETS",
                "unit": "5 TABS",
                "mrp": Decimal("132.00"),
                "net_rate": Decimal("105.60"),
                "company": "ALEMBIC",
                "stockist": "Verma Bros Pharmaceuticals",
                "current_stock": Decimal("60"),
                "low_stock_threshold": Decimal("15"),
                "composition": "AZITHROMYCIN 500 MG",
                "barcode": "8903456789012",
            },
            {
                "particulars": "AMLOKIND-AT TABS",
                "unit": "15 TABS",
                "mrp": Decimal("72.50"),
                "net_rate": Decimal("58.00"),
                "company": "MANKIND",
                "stockist": "Hari Krishna Distributor",
                "current_stock": Decimal("90"),
                "low_stock_threshold": Decimal("25"),
                "composition": "AMLODIPINE 5 MG + ATENOLOL 50 MG",
                "barcode": "8904567890123",
            },
            {
                "particulars": "TELMA 40 TABLETS",
                "unit": "15 TABS",
                "mrp": Decimal("140.00"),
                "net_rate": Decimal("112.00"),
                "company": "GLENMARK",
                "stockist": "Rathore Medicos",
                "current_stock": Decimal("50"),
                "low_stock_threshold": Decimal("20"),
                "composition": "TELMISARTAN 40 MG",
                "barcode": "8905678901234",
            },
            {
                "particulars": "COMBIFLAM TABLETS",
                "unit": "20 TABS",
                "mrp": Decimal("46.00"),
                "net_rate": Decimal("36.80"),
                "company": "SANOFI",
                "stockist": "Verma Bros Pharmaceuticals",
                "current_stock": Decimal("150"),
                "low_stock_threshold": Decimal("40"),
                "composition": "IBUPROFEN 400 MG + PARACETAMOL 325 MG",
                "barcode": "8906789012345",
            },
            {
                "particulars": "MONTEK-LC TABLETS",
                "unit": "10 TABS",
                "mrp": Decimal("185.00"),
                "net_rate": Decimal("148.00"),
                "company": "SUN PHARMA",
                "stockist": "Hari Krishna Distributor",
                "current_stock": Decimal("10"),  # Low stock test case
                "low_stock_threshold": Decimal("25"),
                "composition": "MONTELUKAST 10 MG + LEVOCETIRIZINE 5 MG",
                "barcode": "8907890123456",
            },
            {
                "particulars": "GLYCOMET-GP 1 TABLETS",
                "unit": "15 TABS",
                "mrp": Decimal("128.00"),
                "net_rate": Decimal("102.40"),
                "company": "USV",
                "stockist": "Rathore Medicos",
                "current_stock": Decimal("40"),
                "low_stock_threshold": Decimal("20"),
                "composition": "METFORMIN 500 MG + GLIMEPIRIDE 1 MG",
                "barcode": "8908901234567",
            },
            {
                "particulars": "SHELCAL 500 TABLETS",
                "unit": "15 TABS",
                "mrp": Decimal("139.50"),
                "net_rate": Decimal("111.60"),
                "company": "TORRENT",
                "stockist": "Verma Bros Pharmaceuticals",
                "current_stock": Decimal("85"),
                "low_stock_threshold": Decimal("20"),
                "composition": "CALCIUM 500 MG + VITAMIN D3 250 IU",
                "barcode": "8909012345678",
            },
        ]

        for m_data in medicines_data:
            med = db.query(models.Medicine).filter(
                models.Medicine.tenant_id == kush_tenant.id,
                models.Medicine.particulars == m_data["particulars"],
            ).first()
            if not med:
                med = models.Medicine(
                    tenant_id=kush_tenant.id,
                    particulars=m_data["particulars"],
                    normalized_name=normalize(m_data["particulars"]),
                    unit=m_data["unit"],
                    mrp=m_data["mrp"],
                    net_rate=m_data["net_rate"],
                    company=m_data["company"],
                    stockist=m_data["stockist"],
                    current_stock=m_data["current_stock"],
                    low_stock_threshold=m_data["low_stock_threshold"],
                    composition=m_data["composition"],
                    barcode=m_data["barcode"],
                    lead_time_days=3,
                )
                db.add(med)
        db.commit()

        # -------------------------------------------------------------
        # Kush Medical Customers
        # -------------------------------------------------------------
        customers_data = [
            ("Rahul Sharma", "9811122233"),
            ("Amit Verma", "9822233344"),
            ("Sunita Devi", "9833344455"),
        ]
        for c_name, c_phone in customers_data:
            cust = db.query(models.Customer).filter(
                models.Customer.tenant_id == kush_tenant.id,
                models.Customer.phone == c_phone,
            ).first()
            if not cust:
                cust = models.Customer(
                    tenant_id=kush_tenant.id,
                    name=c_name,
                    phone=c_phone,
                )
                db.add(cust)
        db.commit()

        # -------------------------------------------------------------
        # 2. Metro Medical Store (Tenant 2 — For Cross-Tenant Testing)
        # -------------------------------------------------------------
        metro_tenant = db.query(models.Tenant).filter(models.Tenant.slug == "metro-medical").first()
        if not metro_tenant:
            metro_tenant = models.Tenant(
                slug="metro-medical",
                shop_name="Metro Medical Store",
                owner_name="Vikram Singh",
                email="metromedical@gmail.com",
                phone="9876500000",
                city="Gurgaon",
                plan="free",
                is_active=True,
                email_verified=True,
            )
            db.add(metro_tenant)
            db.commit()
            db.refresh(metro_tenant)

            metro_owner = models.User(
                tenant_id=metro_tenant.id,
                username="metromedical@gmail.com",
                password_hash=hash_password("Password@123"),
                full_name="Vikram Singh",
                role="owner",
                is_active=True,
            )
            db.add(metro_owner)

            # Metro Medical unique medicine
            metro_med = models.Medicine(
                tenant_id=metro_tenant.id,
                particulars="METRO-CALCIUM SYRUP",
                normalized_name=normalize("METRO-CALCIUM SYRUP"),
                unit="200 ML",
                mrp=Decimal("95.00"),
                net_rate=Decimal("70.00"),
                company="METRO LABS",
                current_stock=Decimal("30"),
                barcode="9999999999999",
            )
            db.add(metro_med)
            db.commit()
            print(f"Created Tenant 2: [{metro_tenant.id}] {metro_tenant.shop_name}")

    db.close()
    print("\nDatabase initialization & Seeding completed successfully!")
    print("----------------------------------------------------------------")
    print("Kush Medical Hall Credentials:")
    print("  Store Name: Kush Medical Hall")
    print("  Owner Login: kushmedical@gmail.com  / Password@123")
    print("  Staff Login: staff@kushmedical.com  / Password@123")
    print("----------------------------------------------------------------")
    print("Tenant Isolation Test Store:")
    print("  Store Name: Metro Medical Store")
    print("  Owner Login: metromedical@gmail.com / Password@123")
    print("----------------------------------------------------------------\n")


if __name__ == "__main__":
    seed_database()
