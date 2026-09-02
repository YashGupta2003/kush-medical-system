import re

with open('backend/app/models.py', 'r') as f:
    lines = f.readlines()

new_lines = []
in_class = False
class_name = ""

for line in lines:
    new_lines.append(line)
    
    match = re.match(r'^class (\w+)\(Base\):', line)
    if match:
        class_name = match.group(1)
        in_class = True
        continue
        
    if in_class and line.strip().startswith('id = Column('):
        if class_name != 'Tenant':
            new_lines.append('    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)\n')
        in_class = False

with open('backend/app/models.py', 'w') as f:
    f.writelines(new_lines)
