import pytest

def test_copilot_rate_limit(client, owner_headers):
    status_codes = []
    for i in range(12):
        resp = client.post("/copilot/chat", json={"message": f"test {i}", "history": []}, headers=owner_headers)
        status_codes.append(resp.status_code)
    
    assert 429 in status_codes
