"""
Tests for copilot_service.py. The Groq API itself is always mocked - these
tests verify OUR dispatch/safety logic (which tool gets called, with what
arguments, how errors are handled, how the tool-use loop terminates), never
real model behavior, which would make tests flaky/slow/costly.
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services import copilot_service
from app import models


# ---------------------------------------------------------------------------
# Tool registry integrity
# ---------------------------------------------------------------------------
def test_every_declared_tool_has_a_handler():
    declared = {t["name"] for t in copilot_service.TOOLS}
    handlers = set(copilot_service.TOOL_HANDLERS.keys())
    assert declared == handlers


def test_every_tool_has_a_description_and_schema():
    for tool in copilot_service.TOOLS:
        assert tool["description"], f"{tool['name']} has no description"
        assert tool["input_schema"]["type"] == "object"


def test_groq_tool_format_conversion():
    groq_tools = copilot_service._to_groq_tools()
    assert len(groq_tools) == len(copilot_service.TOOLS)
    for t in groq_tools:
        assert t["type"] == "function"
        assert "name" in t["function"]
        assert "parameters" in t["function"]


# ---------------------------------------------------------------------------
# _dispatch_tool - the safety-critical function: this is the ONLY path
# through which the LLM can ever cause code to run.
# ---------------------------------------------------------------------------
class TestDispatchTool:
    def test_unknown_tool_name_fails_safely(self, db_session):
        result, error = copilot_service._dispatch_tool(db_session, "delete_everything", {})
        assert result is None
        assert "Unknown tool" in error

    def test_known_tool_with_valid_args_succeeds(self, db_session, sample_medicine):
        result, error = copilot_service._dispatch_tool(
            db_session, "search_medicines", {"query": "AMLOKIND"}
        )
        assert error is None
        assert any(m["medicine_id"] == sample_medicine.id for m in result)

    def test_invalid_arguments_fail_safely_not_crash(self, db_session):
        result, error = copilot_service._dispatch_tool(db_session, "get_gst_report", {})
        assert result is None
        assert "Invalid arguments" in error

    def test_tool_cannot_be_called_with_arbitrary_python(self, db_session):
        result, error = copilot_service._dispatch_tool(
            db_session, "__import__", {"name": "os"}
        )
        assert result is None
        assert "Unknown tool" in error


# ---------------------------------------------------------------------------
# Individual tool wrappers - real DB logic, no mocking needed
# ---------------------------------------------------------------------------
class TestToolWrappers:
    def test_search_medicines_partial_match(self, db_session, sample_medicine):
        result = copilot_service._tool_search_medicines(db_session, query="amlokind")
        assert len(result) == 1
        assert result[0]["particulars"] == sample_medicine.particulars

    def test_get_recent_sales_respects_window(self, db_session, sample_medicine):
        from datetime import datetime, timedelta
        old_sale = models.Sale(medicine_id=sample_medicine.id, qty_sold=5, sold_at=datetime.utcnow() - timedelta(days=5))
        recent_sale = models.Sale(medicine_id=sample_medicine.id, qty_sold=2, sold_at=datetime.utcnow())
        db_session.add_all([old_sale, recent_sale])
        db_session.commit()

        result = copilot_service._tool_get_recent_sales(db_session, hours=24)
        assert len(result) == 1
        assert result[0]["qty_sold"] == 2.0

    def test_profit_margin_analysis_shop_average(self, db_session, sample_medicine):
        result = copilot_service._tool_get_profit_margin_analysis(db_session)
        assert result["shop_average_margin_pct"] is not None
        assert result["shop_priced_medicine_count"] == 1

    def test_check_drug_interactions_delegates_to_graph_service(self, db_session):
        from app.services import graph_service
        graph_service.seed_interaction_edges(db_session)
        db_session.commit()

        result = copilot_service._tool_check_drug_interactions(db_session, salts=["Warfarin", "Aspirin"])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# run_copilot_query - the full agentic loop, with a MOCKED Groq client.
# Groq's SDK mirrors OpenAI's response shape:
#   response.choices[0].message.content / .tool_calls
#   response.choices[0].finish_reason == "tool_calls" | "stop"
#   tool_call.function.name / .function.arguments (a JSON STRING)
# ---------------------------------------------------------------------------
def _fake_message(content=None, tool_calls=None):
    return SimpleNamespace(
        content=content, tool_calls=tool_calls,
        model_dump=lambda: {
            "role": "assistant", "content": content,
            "tool_calls": [tc.model_dump() for tc in tool_calls] if tool_calls else None,
        },
    )


def _fake_tool_call(call_id, name, arguments_dict):
    import json as _json
    function_ns = SimpleNamespace(name=name, arguments=_json.dumps(arguments_dict))
    return SimpleNamespace(
        id=call_id, function=function_ns,
        model_dump=lambda: {"id": call_id, "type": "function",
                             "function": {"name": name, "arguments": _json.dumps(arguments_dict)}},
    )


def _fake_response(finish_reason, message):
    choice = SimpleNamespace(finish_reason=finish_reason, message=message)
    return SimpleNamespace(choices=[choice])


class TestRunCopilotQueryNoApiKey:
    def test_returns_friendly_message_when_unconfigured(self, db_session, monkeypatch):
        monkeypatch.setattr(copilot_service.settings, "groq_api_key", "")
        result = copilot_service.run_copilot_query(db_session, "hello")
        assert "isn't configured" in result["reply"]
        assert result["tool_calls"] == []


class TestRunCopilotQueryWithMockedModel:
    def test_direct_text_reply_needs_no_tool_calls(self, db_session, monkeypatch):
        monkeypatch.setattr(copilot_service.settings, "groq_api_key", "fake-key-for-test")

        fake_response = _fake_response("stop", _fake_message(content="Hi, how can I help?"))

        with patch("groq.Groq") as MockClient:
            MockClient.return_value.chat.completions.create.return_value = fake_response
            result = copilot_service.run_copilot_query(db_session, "hello")

        assert result["reply"] == "Hi, how can I help?"
        assert result["tool_calls"] == []

    def test_tool_use_then_final_answer(self, db_session, sample_medicine, monkeypatch):
        monkeypatch.setattr(copilot_service.settings, "groq_api_key", "fake-key-for-test")

        tool_call = _fake_tool_call("call_1", "search_medicines", {"query": "AMLOKIND"})
        tool_use_response = _fake_response("tool_calls", _fake_message(tool_calls=[tool_call]))
        final_response = _fake_response("stop", _fake_message(content=f"Found it: {sample_medicine.particulars}"))

        with patch("groq.Groq") as MockClient:
            MockClient.return_value.chat.completions.create.side_effect = [tool_use_response, final_response]
            result = copilot_service.run_copilot_query(db_session, "find amlokind")

        assert "Found it" in result["reply"]
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["tool"] == "search_medicines"
        assert result["tool_calls"][0]["error"] is None

    def test_runaway_tool_loop_is_capped(self, db_session, monkeypatch):
        monkeypatch.setattr(copilot_service.settings, "groq_api_key", "fake-key-for-test")
        monkeypatch.setattr(copilot_service, "MAX_TOOL_ITERATIONS", 2)

        tool_call = _fake_tool_call("call_x", "get_shop_overview", {})
        always_tool_use = _fake_response("tool_calls", _fake_message(tool_calls=[tool_call]))

        with patch("groq.Groq") as MockClient:
            MockClient.return_value.chat.completions.create.return_value = always_tool_use
            result = copilot_service.run_copilot_query(db_session, "loop forever")

        assert "wasn't able to finish" in result["reply"]
        assert len(result["tool_calls"]) == 2   # capped, not infinite

    def test_unknown_tool_call_reported_as_error_not_crash(self, db_session, monkeypatch):
        monkeypatch.setattr(copilot_service.settings, "groq_api_key", "fake-key-for-test")

        bad_tool_call = _fake_tool_call("call_1", "drop_all_tables", {})
        bad_tool_response = _fake_response("tool_calls", _fake_message(tool_calls=[bad_tool_call]))
        final_response = _fake_response("stop", _fake_message(content="I couldn't do that."))

        with patch("groq.Groq") as MockClient:
            MockClient.return_value.chat.completions.create.side_effect = [bad_tool_response, final_response]
            result = copilot_service.run_copilot_query(db_session, "try something unsafe")

        assert result["tool_calls"][0]["error"] is not None
        assert "Unknown tool" in result["tool_calls"][0]["error"]

    def test_malformed_tool_arguments_json_does_not_crash(self, db_session, monkeypatch):
        monkeypatch.setattr(copilot_service.settings, "groq_api_key", "fake-key-for-test")

        malformed_call = SimpleNamespace(
            id="call_bad", function=SimpleNamespace(name="get_shop_overview", arguments="{not valid json"),
            model_dump=lambda: {"id": "call_bad", "type": "function",
                                 "function": {"name": "get_shop_overview", "arguments": "{not valid json"}},
        )
        tool_response = _fake_response("tool_calls", _fake_message(tool_calls=[malformed_call]))
        final_response = _fake_response("stop", _fake_message(content="Here's the overview."))

        with patch("groq.Groq") as MockClient:
            MockClient.return_value.chat.completions.create.side_effect = [tool_response, final_response]
            result = copilot_service.run_copilot_query(db_session, "give me an overview")

        # Malformed JSON args should fall back to {} rather than raise
        assert result["reply"] == "Here's the overview."