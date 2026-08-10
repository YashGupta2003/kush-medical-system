import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from app.database import SessionLocal
from app.models import ColdChainUnit

def create_default():
    db = SessionLocal()
    existing = db.query(ColdChainUnit).first()
    if not existing:
        print("No cold chain units found. Creating default 'Main Refrigerator'...")
        unit = ColdChainUnit(
            unit_label="Main Refrigerator",
            location_note="Front Pharmacy",
            min_temp_c=2.0,
            max_temp_c=8.0,
            is_active=True
        )
        db.add(unit)
        db.commit()
        print("Created successfully.")
    else:
        print(f"Units already exist (Found: {existing.unit_label}). No action taken.")
    db.close()

if __name__ == "__main__":
    create_default()
