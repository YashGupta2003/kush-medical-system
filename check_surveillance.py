import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from app.database import SessionLocal
from app.models import SurveillanceDailyCount

db = SessionLocal()
count = db.query(SurveillanceDailyCount).count()
print(f"Total rows in SurveillanceDailyCount: {count}")
