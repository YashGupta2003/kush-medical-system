from app.services.image_preprocessing import ensure_image_bytes
import sys

with open('backend/test_pdf_input.pdf', 'wb') as f:
    f.write(b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Count 1\n/Kids [ 3 0 R ]\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [ 0 0 100 100 ]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 0\n>>\nstream\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000216 00000 n\ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n259\n%%EOF\n')

with open('backend/test_pdf_input.pdf', 'rb') as f:
    pdf_bytes = f.read()

png_bytes = ensure_image_bytes(pdf_bytes)
print("Is PNG:", png_bytes.startswith(b'\x89PNG'))
