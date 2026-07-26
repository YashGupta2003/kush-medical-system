"""
Creates the very first Owner account. Run this ONCE after migrating the
database - there's no public signup screen (this is a single-shop app, not
a multi-tenant SaaS), so the first account has to be created directly like
this. After that, the Owner can create Staff accounts from within the app
itself (Settings/Users screen, backed by POST /auth/users).

Usage:
    cd backend
    python scripts/create_first_owner.py
"""
import sys
import os
import getpass

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal, Base, engine
from app import models
from app.services.auth_service import hash_password


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    existing_owner = db.query(models.User).filter(models.User.role == "owner").first()
    if existing_owner:
        print(f"An owner account already exists: '{existing_owner.username}'. "
              f"Delete it from the database first if you really want to replace it.")
        return

    print("Creating the first Owner account for Kush Medical Hall.")
    username = input("Choose a username: ").strip()
    full_name = input("Full name (optional): ").strip() or None
    password = getpass.getpass("Choose a password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Passwords didn't match. Run the script again.")
        return
    if len(password) < 6:
        print("Password should be at least 6 characters. Run the script again.")
        return

    user = models.User(
        username=username,
        password_hash=hash_password(password),
        full_name=full_name,
        role="owner",
        is_active=True,
    )
    db.add(user)
    db.commit()
    print(f"Owner account '{username}' created. You can now log in from the app.")


if __name__ == "__main__":
    main()