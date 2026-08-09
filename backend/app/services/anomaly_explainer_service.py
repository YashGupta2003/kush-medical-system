"""
Pillar 6, Part 3 - LLM-Explained Anomalies.

Takes one flagged anomaly's RAW NUMBERS (from anomaly_service.py) and
asks the LLM to produce a short, plain-English explanation - "this is
unusual because X is Y standard deviations from the shop's normal
pattern" - rather than showing the Owner a bare z-score/isolation-forest
score. This is a presentation layer on top of a REAL statistical model,
not a replacement for one: the LLM never decides what counts as
anomalous (anomaly_service.py already did that with real math) - it only
explains, in the same grounded, RAG-style way Pillar 2's PharmaCopilot
uses retrieved facts rather than its own guesses.

Standalone module (does not require editing copilot_service.py) so this
works today regardless of that file's internal structure. To register
this as an ADDITIONAL PharmaCopilot tool later (so the Owner can ask
PharmaCopilot directly "explain that price jump" instead of clicking a
button), add an entry to copilot_service.py's TOOLS list plus a
TOOL_HANDLERS entry calling explain_anomaly() below - the shape needed
depends on that file's existing registry format, so this is left as a
documented follow-up rather than guessed at blindly here.
"""
import json

from app.config import settings

SYSTEM_PROMPT = (
    "You explain flagged statistical anomalies from a pharmacy's inventory system to the shop "
    "owner in plain, everyday English (2-4 sentences). You are given ONLY the numbers below - "
    "never invent facts not present in them. Never accuse anyone of theft or wrongdoing; the "
    "correct tone is 'this pattern is worth a look', since there are many innocent explanations "
    "(stock count corrections, breakage, expired-stock write-offs, data entry mistakes). End with "
    "a short, neutral suggestion of what to check next."
)


def _fallback_explanation(anomaly: dict) -> str:
    """Used when no Groq API key is configured - a deterministic, still-useful explanation."""
    parts = []
    if "pct_change" in anomaly:
        parts.append(
            f"{anomaly.get('medicine_name', 'This medicine')}'s rate changed by "
            f"{anomaly['pct_change']}% (₹{anomaly.get('old_rate')} → ₹{anomaly.get('new_rate')}), "
            f"which is unusually large compared to this shop's other recent rate changes."
        )
    elif "change_qty" in anomaly:
        parts.append(
            f"A stock adjustment of {anomaly['change_qty']} units for "
            f"{anomaly.get('medicine_name', 'this medicine')} is unusually large compared to this "
            f"shop's typical manual corrections."
        )
    else:
        parts.append("This pattern is statistically unusual compared to this shop's normal history.")
    parts.append(
        "Worth a quick look — could be a genuine correction, a data-entry slip, or something to "
        "double-check with whoever recorded it."
    )
    return " ".join(parts)


def explain_anomaly(anomaly: dict) -> str:
    """
    anomaly: one entry from anomaly_service.detect_price_jump_anomalies()'s
    or detect_stock_adjustment_anomalies()'s output, passed through as-is
    - this function doesn't care which kind it is.
    """
    if not settings.groq_api_key:
        return _fallback_explanation(anomaly)

    try:
        import groq
        client = groq.Groq(api_key=settings.groq_api_key)
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Flagged anomaly data:\n{json.dumps(anomaly, default=str, indent=2)}"},
            ],
            max_tokens=220,
            temperature=0.4,
        )
        text = response.choices[0].message.content
        return text.strip() if text else _fallback_explanation(anomaly)
    except Exception:
        # Never let an LLM/network hiccup break the anomaly screen - the
        # raw numbers are already shown regardless; this text is a bonus.
        return _fallback_explanation(anomaly)