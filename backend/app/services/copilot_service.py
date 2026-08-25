"""
PharmaCopilot - Pillar 2: an agentic assistant that answers questions about
THIS shop's own data by calling already-tested service functions as "tools"
(OpenAI-style function-calling, via Groq's OpenAI-compatible API) - never
by writing or executing arbitrary SQL, and never by answering from the
model's own training-data "knowledge" for anything data-specific to this
shop.

Runs on Groq (fast inference over open-weight models like openai/gpt-oss-120b)
via the official `groq` Python SDK, which mirrors the OpenAI chat-completions
interface - tool schemas use the standard OpenAI "type": "function" wrapper,
and tool results are returned as role="tool" messages.

Every tool below wraps a function that already existed in this codebase
before this file did, EXCEPT two clearly-marked additions
(profit_analytics_service, sales_lookup_service) where no existing function
covered that exact question - see their own module docstrings.

Safety model: the LLM can only ever trigger one of the exact functions
listed in TOOL_HANDLERS below, with whatever arguments IT chooses - it can
never execute code, run SQL, or call anything outside this fixed allowlist.
A tool call that doesn't match a known name, or whose arguments don't match
the target function's signature, fails safely and is reported back to the
model as an error rather than crashing the request.
"""
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.services import (
    analytics_service, expiry_service, gst_report_service, stock_service,
    graph_service, composition_service, profit_analytics_service, sales_lookup_service,
)

logger = logging.getLogger("app.copilot")

MAX_TOOL_ITERATIONS = 5

SYSTEM_PROMPT = """You are PharmaCopilot, an assistant built into Kush Medical Hall's pharmacy \
management system. You answer the shop owner's/staff's questions about THEIR OWN shop data by \
calling the tools provided - you must never answer a factual question about their shop's data \
(stock, sales, expiry, GST, spend, pricing) from memory or estimation. Always call a tool first.

Rules you must follow:
- For any question about stock levels, sales, expiry dates, GST, spend, or pricing: call the \
relevant tool(s) before answering. Never invent or estimate numbers.
- For questions about drug interactions or which medicines treat a condition: call \
check_drug_interactions or find_medicines_for_condition - answer ONLY from what those tools \
return, never from your own general medical training data. This shop's curated data is the only \
source of truth here, since it's what's actually been verified for this catalog.
- If a question needs a specific medicine's ID and you only have its name, call search_medicines \
first to resolve it before calling any tool that needs medicine_id.
- Never provide dosing instructions, diagnoses, or clinical advice as if speaking to a patient - \
you are a business/inventory assistant for the shop owner and staff, not a clinical decision \
tool. If a question requires a pharmacist's or doctor's judgment, say so plainly and stop there.
- Keep answers concise and concrete: lead with the number or fact, then a short line of context. \
This is a busy shop owner checking something quickly, not a conversation partner.
- If a tool returns an empty result, say so plainly ("no medicines found matching that") rather \
than guessing at an answer.
"""


# ---------------------------------------------------------------------------
# Tool wrapper functions - the ONLY functions the LLM can ever trigger.
# Each takes (db, **kwargs) and returns a JSON-serializable dict/list.
# ---------------------------------------------------------------------------
def _tool_get_expiring_medicines(db: Session, days: int = 90, distributor_name: Optional[str] = None):
    results = expiry_service.get_expiry_dashboard(db, days=days)
    if distributor_name:
        needle = distributor_name.strip().upper()
        results = [r for r in results if r.get("distributor_name") and needle in r["distributor_name"].upper()]
    return results


def _tool_get_gst_report(db: Session, year: int, month: int):
    return gst_report_service.get_gst_report(db, year, month)


def _tool_get_monthly_spend(db: Session, months: int = 6):
    return analytics_service.get_monthly_spend(db, months=months)


def _tool_get_price_changes(db: Session, days: int = 90, limit: int = 10):
    return analytics_service.get_price_changes(db, days=days, limit=limit)


def _tool_get_top_selling(db: Session, days: int = 30, limit: int = 10):
    return analytics_service.get_top_selling(db, days=days, limit=limit)


def _tool_get_top_medicines_by_spend(db: Session, year: Optional[int] = None, month: Optional[int] = None, limit: int = 10):
    return analytics_service.get_top_medicines_by_spend(db, year=year, month=month, limit=limit)


def _tool_get_distributor_breakdown(db: Session, year: Optional[int] = None, month: Optional[int] = None):
    return analytics_service.get_distributor_breakdown(db, year=year, month=month)


def _tool_get_shop_overview(db: Session):
    return analytics_service.get_overview(db)


def _tool_get_reorder_list(db: Session):
    return stock_service.get_reorder_list(db)


def _tool_search_medicines(db: Session, query: str, limit: int = 10):
    medicines = (
        db.query(models.Medicine)
        .filter(models.Medicine.particulars.ilike(f"%{query}%"))
        .limit(limit)
        .all()
    )
    return [
        {
            "medicine_id": m.id, "particulars": m.particulars, "company": m.company,
            "current_stock": float(m.current_stock or 0), "composition": m.composition,
        }
        for m in medicines
    ]


def _tool_get_stock_snapshot(db: Session, medicine_id: int):
    return stock_service.get_stock_snapshot(db, medicine_id)


def _tool_check_drug_interactions(db: Session, salts: list):
    return graph_service.check_interactions(db, salts)


def _tool_find_medicines_for_condition(db: Session, condition: str, in_stock_only: bool = True):
    return graph_service.get_medicines_for_condition(db, condition, in_stock_only=in_stock_only)


def _tool_find_substitutes(db: Session, salt_or_medicine_name: str, in_stock_only: bool = True):
    return composition_service.find_substitutes(db, salt_or_medicine_name, in_stock_only=in_stock_only)


def _tool_get_medicine_graph(db: Session, medicine_id: int):
    return graph_service.get_medicine_graph(db, medicine_id)


def _tool_get_profit_margin_analysis(db: Session, condition: Optional[str] = None):
    # NEW addition - see profit_analytics_service.py's docstring for why.
    return profit_analytics_service.get_profit_margin_analysis(db, condition=condition)


def _tool_get_recent_sales(db: Session, hours: int = 24):
    # NEW addition - see sales_lookup_service.py's docstring for why.
    return sales_lookup_service.get_recent_sales(db, hours=hours)


def _tool_get_uncollected_prescriptions(db: Session, minutes: int = 30):
    # NEW — PIE integration: flag prescriptions scanned but not converted to sale
    from app.services import prescription_service
    return prescription_service.get_uncollected_prescriptions(db, minutes=minutes)


TOOL_HANDLERS = {
    "get_expiring_medicines": _tool_get_expiring_medicines,
    "get_gst_report": _tool_get_gst_report,
    "get_monthly_spend": _tool_get_monthly_spend,
    "get_price_changes": _tool_get_price_changes,
    "get_top_selling": _tool_get_top_selling,
    "get_top_medicines_by_spend": _tool_get_top_medicines_by_spend,
    "get_distributor_breakdown": _tool_get_distributor_breakdown,
    "get_shop_overview": _tool_get_shop_overview,
    "get_reorder_list": _tool_get_reorder_list,
    "search_medicines": _tool_search_medicines,
    "get_stock_snapshot": _tool_get_stock_snapshot,
    "check_drug_interactions": _tool_check_drug_interactions,
    "find_medicines_for_condition": _tool_find_medicines_for_condition,
    "find_substitutes": _tool_find_substitutes,
    "get_medicine_graph": _tool_get_medicine_graph,
    "get_profit_margin_analysis": _tool_get_profit_margin_analysis,
    "get_recent_sales": _tool_get_recent_sales,
    "get_uncollected_prescriptions": _tool_get_uncollected_prescriptions,
}


# ---------------------------------------------------------------------------
# Tool schemas, in Anthropic's tool-use format (name/description/input_schema).
# The description is what the model actually reads to decide which tool to
# call - keep these accurate and specific, they matter more than the code.
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "get_expiring_medicines",
        "description": "List medicine batches expiring within N days (default 90), optionally filtered to a specific distributor's name (partial match).",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "How many days ahead to check, default 90"},
                "distributor_name": {"type": "string", "description": "Optional distributor name filter, partial match"},
            },
        },
    },
    {
        "name": "get_gst_report",
        "description": "GST slab-wise breakdown (CGST/SGST/taxable amount) for a specific year and month, from confirmed purchase bills.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer"},
                "month": {"type": "integer", "description": "1-12"},
            },
            "required": ["year", "month"],
        },
    },
    {
        "name": "get_monthly_spend",
        "description": "Total confirmed-bill purchase spend per calendar month, for the last N months (default 6, including the current month).",
        "input_schema": {
            "type": "object",
            "properties": {"months": {"type": "integer", "description": "Default 6"}},
        },
    },
    {
        "name": "get_price_changes",
        "description": "Medicines with the biggest net rate change over a time window (default last 90 days), ranked by magnitude of change.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Default 90"},
                "limit": {"type": "integer", "description": "Default 10"},
            },
        },
    },
    {
        "name": "get_top_selling",
        "description": "Top medicines by quantity sold (from recorded sales), over a time window (default last 30 days).",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Default 30"},
                "limit": {"type": "integer", "description": "Default 10"},
            },
        },
    },
    {
        "name": "get_top_medicines_by_spend",
        "description": "Medicines the shop spent the most cumulative money purchasing, for a given year/month (defaults to the current month).",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer"}, "month": {"type": "integer"},
                "limit": {"type": "integer", "description": "Default 10"},
            },
        },
    },
    {
        "name": "get_distributor_breakdown",
        "description": "How much was purchased from each distributor in a given year/month (defaults to the current month).",
        "input_schema": {
            "type": "object",
            "properties": {"year": {"type": "integer"}, "month": {"type": "integer"}},
        },
    },
    {
        "name": "get_shop_overview",
        "description": "The shop's top-line stats right now: this month's spend vs last month, stock value on hand, low-stock count, bills awaiting review, expiring/expired count.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_reorder_list",
        "description": "Every medicine currently below its low-stock threshold, or manually flagged for reorder, grouped by distributor.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_medicines",
        "description": "Search the master medicine list by (partial) name. Use this to resolve a medicine name to its medicine_id before calling a tool that needs one.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}, "limit": {"type": "integer", "description": "Default 10"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_stock_snapshot",
        "description": "Current stock level, low-stock threshold, and last-purchase details for one specific medicine (by medicine_id).",
        "input_schema": {
            "type": "object",
            "properties": {"medicine_id": {"type": "integer"}},
            "required": ["medicine_id"],
        },
    },
    {
        "name": "check_drug_interactions",
        "description": "Checks a set of salt/composition names against each other for known drug-drug interactions. Pass every salt involved (e.g. from multiple medicines) in one call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "salts": {"type": "array", "items": {"type": "string"}, "description": "List of salt names, e.g. [\"Paracetamol\", \"Warfarin\"]"},
            },
            "required": ["salts"],
        },
    },
    {
        "name": "find_medicines_for_condition",
        "description": "Finds medicines (optionally in-stock only) associated with treating a given condition, e.g. 'Fever', 'Bacterial Infection', 'Allergy'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "condition": {"type": "string"},
                "in_stock_only": {"type": "boolean", "description": "Default true"},
            },
            "required": ["condition"],
        },
    },
    {
        "name": "find_substitutes",
        "description": "Finds medicines sharing the same salt/composition as the given salt name or medicine composition text - for 'what can I substitute X with' questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "salt_or_medicine_name": {"type": "string"},
                "in_stock_only": {"type": "boolean", "description": "Default true"},
            },
            "required": ["salt_or_medicine_name"],
        },
    },
    {
        "name": "get_medicine_graph",
        "description": "Full relationship graph for one medicine (by medicine_id): what salts it contains, what those salts interact with, what conditions they treat, substitute medicines, and supplying distributors.",
        "input_schema": {
            "type": "object",
            "properties": {"medicine_id": {"type": "integer"}},
            "required": ["medicine_id"],
        },
    },
    {
        "name": "get_profit_margin_analysis",
        "description": "Average profit margin % across the whole shop's priced catalog, optionally compared against medicines for a specific condition (e.g. condition='Bacterial Infection' as a proxy for antibiotics).",
        "input_schema": {
            "type": "object",
            "properties": {"condition": {"type": "string", "description": "Optional condition name to compare against the shop average"}},
        },
    },
    {
        "name": "get_recent_sales",
        "description": "Every sale recorded in the last N hours (default 24), most recent first - use this for 'what did I sell today/recently' questions.",
        "input_schema": {
            "type": "object",
            "properties": {"hours": {"type": "integer", "description": "Default 24"}},
        },
    },
    {
        "name": "get_uncollected_prescriptions",
        "description": "Returns prescriptions that were scanned and processed but NOT converted to a sale within N minutes (default 30) — flags potential revenue leakage where a patient scanned a prescription but didn't buy.",
        "input_schema": {
            "type": "object",
            "properties": {
                "minutes": {"type": "integer", "description": "How many minutes to wait before flagging a prescription as uncollected. Default 30."},
            },
        },
    },
]

_KNOWN_TOOL_NAMES = {t["name"] for t in TOOLS}
assert _KNOWN_TOOL_NAMES == set(TOOL_HANDLERS.keys()), "TOOLS and TOOL_HANDLERS have drifted out of sync"


def _dispatch_tool(db: Session, name: str, kwargs: dict) -> tuple[object, Optional[str]]:
    """
    Runs exactly one tool call. Returns (result, error) - error is None on
    success. Never raises - a bad tool name or bad arguments becomes an
    error string handed back to the model (which can then retry sensibly),
    not a crashed request.
    """
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return None, f"Unknown tool '{name}' - not in the allowed tool list."
    try:
        result = handler(db, **(kwargs or {}))
        return result, None
    except TypeError as e:
        return None, f"Invalid arguments for '{name}': {e}"
    except Exception as e:
        logger.exception("Copilot tool '%s' raised an exception", name)
        return None, f"Tool '{name}' failed: {e}"


def _assistant_message_dict(message) -> dict:
    """
    Builds a minimal, API-safe assistant message dict from a Groq/OpenAI
    response message object - deliberately NOT a raw .model_dump() of the
    whole object. Newer SDK response objects include extra response-only
    fields (e.g. "annotations") that the chat-completions endpoint REJECTS
    when that same dict is echoed back as INPUT on the next turn ("property
    'annotations' is unsupported"). Only role/content/tool_calls are valid
    to send back - this function keeps exactly those and nothing else, so
    conversation history is always safe to replay regardless of which extra
    fields a given SDK version happens to add to its response objects.
    """
    result = {"role": "assistant", "content": message.content}
    if message.tool_calls:
        result["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in message.tool_calls
        ]
    return result


def _to_groq_tools() -> list[dict]:
    """Converts our internal TOOLS format into the OpenAI/Groq "type": "function" wrapper shape."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in TOOLS
    ]


def run_copilot_query(db: Session, user_message: str, history: Optional[list] = None) -> dict:
    """
    Runs one turn of the PharmaCopilot conversation on Groq: sends the
    user's message (plus prior history) to the model with the tool
    registry attached, executes whatever tools the model asks for against
    THIS shop's real data, feeds the results back, and repeats until the
    model gives a final text answer (or MAX_TOOL_ITERATIONS is hit, as a
    safety cap against a runaway tool-call loop).

    Returns {"reply": str, "tool_calls": [...], "history": [...]} - history
    is meant to be echoed back by the frontend on the next turn for
    multi-turn conversation, kept opaque (the frontend doesn't need to
    understand its structure, only pass it back). The system prompt is NOT
    stored in history - it's freshly prepended on every call, so it never
    gets duplicated as the conversation grows.
    """
    if not settings.groq_api_key:
        return {
            "reply": "PharmaCopilot isn't configured yet - an administrator needs to add "
                     "GROQ_API_KEY to the backend's .env file.",
            "tool_calls": [], "history": history or [],
        }

    from groq import Groq

    client = Groq(api_key=settings.groq_api_key)
    conversation = list(history or [])
    conversation.append({"role": "user", "content": user_message})

    groq_tools = _to_groq_tools()
    tool_calls_made = []

    for _ in range(MAX_TOOL_ITERATIONS):
        api_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation

        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=api_messages,
            tools=groq_tools,
            tool_choice="auto",
            max_tokens=1024,
        )

        choice = response.choices[0]
        message = choice.message
        conversation.append(_assistant_message_dict(message))

        if choice.finish_reason != "tool_calls" or not message.tool_calls:
            return {"reply": message.content or "", "tool_calls": tool_calls_made, "history": conversation}

        for tool_call in message.tool_calls:
            try:
                args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result, error = _dispatch_tool(db, tool_call.function.name, args)
            tool_calls_made.append({"tool": tool_call.function.name, "input": args, "error": error})
            conversation.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str) if error is None else f"Error: {error}",
            })

    return {
        "reply": "I wasn't able to finish gathering the data for that in time - try asking a more specific question.",
        "tool_calls": tool_calls_made, "history": conversation,
    }