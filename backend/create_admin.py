from app.database import SessionLocal, Base, engine
from app import models
from app.services.auth_service import hash_password

Base.metadata.create_all(bind=engine)
db = SessionLocal()

existing_owner = db.query(models.User).filter(models.User.role == "owner").first()
if existing_owner:
    print(f"Owner exists: {existing_owner.username}")
    # Update password just in case
    existing_owner.password_hash = hash_password("password123")
    db.commit()
    print("Password reset to 'password123'")
else:
    user = models.User(
        username="admin",
        password_hash=hash_password("password123"),
        full_name="Admin User",
        role="owner",
        is_active=True,
    )
    db.add(user)
    db.commit()
    print("Owner 'admin' created with password 'password123'")
