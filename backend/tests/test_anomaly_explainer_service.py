"""Tests for anomaly_explainer_service.py — Pillar 6, Part 3 (LLM-Explained Anomalies)."""
from unittest.mock import patch
from types import SimpleNamespace

from app.services import anomaly_explainer_service


def test_no_api_key_uses_fallback_explanation(monkeypatch):
    monkeypatch.setattr(anomaly_explainer_service.settings, "groq_api_key", "")
    result = anomaly_explainer_service.explain_anomaly({
        "medicine_name": "Dolo 650", "old_rate": 10, "new_rate": 50, "pct_change": 400,
    })
    assert "Dolo 650" in result
    assert "worth a quick look" in result.lower() or "worth a" in result.lower()


def test_fallback_never_accuses_anyone(monkeypatch):
    monkeypatch.setattr(anomaly_explainer_service.settings, "groq_api_key", "")
    result = anomaly_explainer_service.explain_anomaly({"change_qty": 500, "medicine_name": "Paracetamol"})
    lowered = result.lower()
    assert "steal" not in lowered and "theft" not in lowered and "fraud" not in lowered


def test_fallback_handles_unrecognized_shape_gracefully(monkeypatch):
    monkeypatch.setattr(anomaly_explainer_service.settings, "groq_api_key", "")
    result = anomaly_explainer_service.explain_anomaly({"something_else": 1})
    assert isinstance(result, str) and len(result) > 0


def test_llm_response_used_when_configured(monkeypatch):
    monkeypatch.setattr(anomaly_explainer_service.settings, "groq_api_key", "fake-key")

    fake_message = SimpleNamespace(content="This price jump is unusual because it is far outside the shop's normal range.")
    fake_choice = SimpleNamespace(message=fake_message)
    fake_response = SimpleNamespace(choices=[fake_choice])

    with patch("groq.Groq") as MockClient:
        MockClient.return_value.chat.completions.create.return_value = fake_response
        result = anomaly_explainer_service.explain_anomaly({"pct_change": 400, "medicine_name": "Dolo 650"})

    assert "unusual" in result.lower()


def test_llm_failure_falls_back_without_crashing(monkeypatch):
    monkeypatch.setattr(anomaly_explainer_service.settings, "groq_api_key", "fake-key")

    with patch("groq.Groq") as MockClient:
        MockClient.return_value.chat.completions.create.side_effect = RuntimeError("network down")
        result = anomaly_explainer_service.explain_anomaly({"pct_change": 400, "medicine_name": "Dolo 650"})

    assert "Dolo 650" in result   # fell back to the deterministic explanation, didn't raise