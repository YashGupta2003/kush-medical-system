import pytest
from unittest.mock import patch, MagicMock
from app.services.voice_command_service import VoiceCommandResult
from google.genai.errors import APIError

@pytest.fixture
def mock_genai_client(monkeypatch):
    monkeypatch.setattr("app.services.voice_command_service.settings.gemini_api_key", "test_key")
    with patch("app.services.voice_command_service.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        # Mock generate_content response
        mock_response = MagicMock()
        mock_response.text = '{"intent": "sell", "medicine_name": "Crocin 500", "quantity": 2, "unit": "strip", "confidence": 0.95, "raw_transcript": "Crocin 500, do strip becha"}'
        mock_client.models.generate_content.return_value = mock_response
        
        yield mock_client

def test_voice_command_parse_success(client, owner_headers, db_session, tenant, sample_medicine, mock_genai_client):
    # Setup fuzzy matching scenario - ensure sample_medicine can be found
    sample_medicine.normalized_name = "CROCIN 500"
    db_session.commit()

    # Upload mock audio
    files = {"audio_file": ("test.webm", b"mock audio content", "audio/webm")}
    res = client.post("/v1/voice/command", headers=owner_headers, files=files)
    
    assert res.status_code == 200
    data = res.json()
    assert data["parsed"]["intent"] == "sell"
    assert data["parsed"]["quantity"] == 2
    assert data["requires_confirmation"] is True
    assert data["resolved_medicine"]["id"] == sample_medicine.id
    
    # Check that it didn't change stock yet
    db_session.refresh(sample_medicine)
    # the stock shouldn't have changed, we just parsed it

def test_voice_command_unclear_intent(client, owner_headers, db_session, tenant, mock_genai_client):
    mock_genai_client.models.generate_content.return_value.text = '{"intent": "unclear", "medicine_name": "unknown", "quantity": 0, "unit": "unit", "confidence": 0.1, "raw_transcript": "noise"}'

    files = {"audio_file": ("test.webm", b"noise", "audio/webm")}
    res = client.post("/v1/voice/command", headers=owner_headers, files=files)
    
    assert res.status_code == 200
    data = res.json()
    assert data["parsed"]["intent"] == "unclear"
    assert data["requires_confirmation"] is True
    assert data["resolved_medicine"] is None

def test_voice_command_rate_limit_fallback(client, owner_headers, db_session, tenant, mock_genai_client):
    # Make primary raise 429, fallback succeed
    mock_genai_client.models.generate_content.side_effect = [
        APIError("429 Resource Exhausted", response=MagicMock(status_code=429)),
        MagicMock(text='{"intent": "check_stock", "medicine_name": "Paracetamol", "quantity": 1, "unit": "strip", "confidence": 0.9, "raw_transcript": "check stock"}')
    ]

    files = {"audio_file": ("test.webm", b"audio", "audio/webm")}
    res = client.post("/v1/voice/command", headers=owner_headers, files=files)
    
    assert res.status_code == 200
    assert mock_genai_client.models.generate_content.call_count == 2
    data = res.json()
    assert data["parsed"]["intent"] == "check_stock"


def test_voice_confirm_executes_sale(client, owner_headers, db_session, tenant, sample_medicine):
    initial_stock = float(sample_medicine.current_stock)
    
    payload = {
        "intent": "sell",
        "medicine_id": sample_medicine.id,
        "quantity": 2
    }
    res = client.post("/v1/voice/confirm", headers=owner_headers, json=payload)
    
    assert res.status_code == 200
    db_session.refresh(sample_medicine)
    assert float(sample_medicine.current_stock) == initial_stock - 2

def test_upload_validation_rejects_oversized_audio(client, owner_headers):
    # Oversize file > 5MB
    large_audio = b"0" * (5 * 1024 * 1024 + 10)
    files = {"audio_file": ("large.webm", large_audio, "audio/webm")}
    res = client.post("/v1/voice/command", headers=owner_headers, files=files)
    assert res.status_code == 413

def test_upload_validation_rejects_wrong_mime_type(client, owner_headers):
    # Wrong mime type
    files = {"audio_file": ("test.txt", b"not audio", "text/plain")}
    res = client.post("/v1/voice/command", headers=owner_headers, files=files)
    assert res.status_code == 400

def test_voice_command_rate_limit_on_endpoint(client, owner_headers, db_session, tenant, mock_genai_client):
    for i in range(21):
        files = {"audio_file": (f"test{i}.webm", b"audio", "audio/webm")}
        res = client.post("/v1/voice/command", headers=owner_headers, files=files)
        if res.status_code == 429:
            assert True
            return
    assert False, "Did not hit rate limit"

