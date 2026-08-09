"""
WhatsApp delivery layer for the Notification Engine (Priority 1).

Design decision — graceful no-op pattern:
  This module deliberately mirrors copilot_service.py's treatment of the
  Groq API key: if any required credential is absent or empty, every public
  function logs a warning and returns None rather than raising an exception.
  This means:
    - A deployment without Twilio configured still works fully for in-app
      notifications — only the WhatsApp delivery channel silently doesn't fire.
    - Tests never need a Twilio test account — they call into notification_service
      which calls send_message here, which no-ops cleanly.
    - Whoever DOES configure Twilio gets WhatsApp delivery with no extra wiring.

  This is an explicitly documented trade-off: "no-op with log" is the right
  choice here because WhatsApp is a best-effort delivery channel on top of
  the in-app record, not the source of truth (see notification_service.py).

Twilio WhatsApp sandbox / production note:
  - In the Twilio sandbox, your `twilio_whatsapp_number` is "whatsapp:+14155238886"
  - In production it's your approved WhatsApp Business number, e.g.
    "whatsapp:+911234567890"
  - The recipient number must be in "whatsapp:+91XXXXXXXXXX" format (the
    prefix is added by this module — caller just passes the E.164 number).
"""
from app.config import settings
from app.core.logging import get_logger

logger = get_logger("whatsapp_service")


def _get_client():
    """
    Returns a Twilio REST client if all credentials are present, else None.
    Mirrors copilot_service._get_groq_client()'s pattern exactly.
    """
    sid = settings.twilio_account_sid
    token = settings.twilio_auth_token
    number = settings.twilio_whatsapp_number

    if not sid or not token or not number:
        logger.warning(
            "Twilio credentials not configured "
            "(TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_WHATSAPP_NUMBER). "
            "WhatsApp delivery is disabled. Set these in .env to enable it."
        )
        return None, None

    try:
        from twilio.rest import Client
        return Client(sid, token), number
    except ImportError:
        logger.warning(
            "twilio package not installed. Run `pip install twilio==9.3.7`. "
            "WhatsApp delivery is disabled until then."
        )
        return None, None


def send_message(to: str, body: str) -> bool:
    """
    Sends a WhatsApp message to `to` (E.164 format, e.g. "+919876543210").
    Returns True on success, False on failure/no-op.

    Caller must add the "whatsapp:" prefix if it's not already present.
    This function handles it automatically to keep callers simple.
    """
    client, from_number = _get_client()
    if not client:
        return False

    # Normalise: Twilio requires "whatsapp:+..." format
    to_normalized = to if to.startswith("whatsapp:") else f"whatsapp:{to}"

    try:
        message = client.messages.create(
            body=body,
            from_=from_number,
            to=to_normalized,
        )
        logger.info(f"WhatsApp sent: SID={message.sid} to={to_normalized}")
        return True
    except Exception as exc:
        logger.warning(f"WhatsApp send failed to {to_normalized}: {exc}")
        return False


def send_digest(to: str, digest: dict) -> bool:
    """
    Formats and sends the daily digest as a WhatsApp message.
    Returns True on success, False on no-op/failure.
    """
    lines = [
        "🏥 *Kush Medical Hall — Daily Digest*",
        "",
        f"📊 Adherence overdue: *{digest.get('adherence_overdue_count', 0)}* customers",
        f"💳 Outstanding credit: *₹{digest.get('outstanding_credit_total', 0):.0f}* "
        f"({digest.get('outstanding_credit_customers', 0)} customers)",
        f"⏳ Near-expiry/expired batches: *{digest.get('near_expiry_critical_count', 0)}*",
        f"📦 Low stock items: *{digest.get('low_stock_count', 0)}*",
        f"🚨 Anomaly flags: *{digest.get('anomaly_flag_count', 0)}*",
    ]
    return send_message(to, "\n".join(lines))
