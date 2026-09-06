"""
Shared fixtures for the whole test suite.

Every test gets a FRESH in-memory SQLite database (not your real MySQL dev
database) - created and torn down per test function, so tests never
interfere with each other or with real shop data. FastAPI's `get_db`
dependency is overridden to point at this test database for any test that
uses the `client` fixture.
"""
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app import models
from app.services.auth_service import hash_password, create_access_token


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def tenant(db_session):
    t = models.Tenant(
        slug="test-shop", shop_name="Test Pharmacy", owner_name="Test Owner",
        email="test@example.com"
    )
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


@pytest.fixture()
def owner_user(db_session, tenant):
    user = models.User(
        username="owner1", password_hash=hash_password("ownerpass123"),
        full_name="Test Owner", role="owner", is_active=True, tenant_id=tenant.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def staff_user(db_session, tenant):
    user = models.User(
        username="staff1", password_hash=hash_password("staffpass123"),
        full_name="Test Staff", role="staff", is_active=True, tenant_id=tenant.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def owner_headers(owner_user):
    token = create_access_token(owner_user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def staff_headers(staff_user):
    token = create_access_token(staff_user)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Domain data fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def sample_medicine(db_session, tenant):
    med = models.Medicine(
        particulars="AMLOKIND AT TAB",
        normalized_name="AMLOKIND AT TAB",
        unit="15S", mrp=118.53, net_rate=61.18, company="MANKIND",
        current_stock=20, low_stock_threshold=10, tenant_id=tenant.id
    )
    db_session.add(med)
    db_session.commit()
    db_session.refresh(med)
    return med


@pytest.fixture()
def sample_distributor(db_session, tenant):
    d = models.Distributor(name="HARI KRISHNA DISTRIBUTOR", tenant_id=tenant.id)
    db_session.add(d)
    db_session.commit()
    db_session.refresh(d)
    return d