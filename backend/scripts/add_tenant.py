with open("backend/app/models.py", "r") as f:
    content = f.read()

tenant_class = """
class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    email = Column(String(150), nullable=False, unique=True, index=True)
    phone = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")

"""
if "class Tenant(Base):" not in content:
    content = content.replace("class Medicine(Base):", tenant_class + "class Medicine(Base):")
    with open("backend/app/models.py", "w") as f:
        f.write(content)
