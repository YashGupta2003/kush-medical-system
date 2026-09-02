import sys
import os

filepath = "backend/app/models.py"
with open(filepath, "r") as f:
    content = f.read()

if "def shop_name(self):" not in content:
    content = content.replace('    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))\n\n    __table_args__ =', '    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))\n\n    @property\n    def shop_name(self):\n        return self.tenant.name if self.tenant else None\n\n    __table_args__ =')
    with open(filepath, "w") as f:
        f.write(content)
