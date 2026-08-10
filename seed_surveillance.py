import sys
import os
import random
from datetime import date, timedelta
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.database import SessionLocal, Base, engine
from app import models

def seed_surveillance():
    db = SessionLocal()
    
    # Conditions to seed
    conditions = ["Fever", "Cough", "Cold", "Headache"]
    
    print("Clearing old surveillance data...")
    db.query(models.SurveillanceDailyCount).delete()
    db.commit()
    
    print("Seeding new surveillance data...")
    today = date.today()
    
    # 30 days of data
    for i in range(30):
        current_date = today - timedelta(days=29-i)
        for cond in conditions:
            # Generate a baseline with some random noise
            baseline = random.randint(5, 20)
            
            # Create a fake "spike" for Fever a few days ago
            if cond == "Fever" and i == 25:
                baseline = 65
                
            record = models.SurveillanceDailyCount(
                condition_name=cond,
                count_date=current_date,
                otc_units=baseline
            )
            db.add(record)
            
    db.commit()
    db.close()
    print("Done seeding surveillance data.")

if __name__ == "__main__":
    seed_surveillance()
