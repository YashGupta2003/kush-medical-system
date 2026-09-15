import pytest
from app.config import settings

def test_upload_size_limit(client, owner_headers):
    # Set limit to very small (e.g., 0 MB technically would fail everything but let's test)
    # Wait, size check is max_bytes = settings.max_upload_size_mb * 1024 * 1024.
    # I can't easily mock settings mid-request without reloading.
    # Instead, let's mock the settings value.
    original = settings.max_upload_size_mb
    settings.max_upload_size_mb = 0 # 0 bytes
    
    try:
        # A 10-byte file should be > 0 bytes limit.
        response = client.post("/bills/upload", files={"file": ("test.png", b"test"*10, "image/png")}, headers=owner_headers)
        assert response.status_code == 413
        assert "too large" in response.text.lower()
    finally:
        settings.max_upload_size_mb = original

def test_upload_magic_bytes_spoofed(client, owner_headers):
    # Spoof content type as image/png, but send plain text content
    response = client.post("/bills/upload", files={"file": ("test.png", b"This is just some plain text, not a PNG file.", "image/png")}, headers=owner_headers)
    assert response.status_code == 400
    assert "Invalid file content" in response.text
