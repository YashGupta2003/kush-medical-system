import json
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.config import settings
from app.services.matcher import find_best_match

logger = logging.getLogger(__name__)

class VoiceCommandResult(BaseModel):
    intent: str = Field(description='One of "sell", "check_stock", "restock", "unclear"')
    medicine_name: str = Field(description='Name of the medicine mentioned')
    quantity: int = Field(description='Quantity mentioned (must be normalized to an integer)')
    unit: str = Field(description='Unit of the quantity, e.g. "strip", "tablet", "bottle", "box", "unit"')
    confidence: float = Field(description='0.0 to 1.0, estimate of how sure you are')
    raw_transcript: str = Field(description='What you heard, for the human to double-check')

def parse_voice_command(audio_bytes: bytes, mime_type: str) -> VoiceCommandResult:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=settings.gemini_api_key)
    
    prompt = (
        "You are an AI voice assistant for a pharmacy counter in India. "
        "The speaker is a pharmacy staff member. "
        "Speech may be in Hindi, English, or a mix of both (Hinglish). "
        "Numbers may be spoken as Hindi words ('do', 'teen', 'paanch', etc.) and must be normalized to integers. "
        "Medicine names might be mispronounced brand names. "
        "Your goal is to parse the voice command into a structured intent. "
        "Allowed intents are: 'sell', 'check_stock', 'restock', 'unclear'. "
        "If the audio is unclear, too noisy, or doesn't match a stock/sale command, return intent: 'unclear' rather than guessing."
    )
    
    blob = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
    
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=VoiceCommandResult,
        temperature=0.0
    )
    
    # Try primary model first
    model_name = settings.gemini_voice_model_primary
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[prompt, blob],
            config=config
        )
    except APIError as e:
        # Check for 429 Resource Exhausted
        if getattr(e, "code", None) == 429 or "429" in str(e):
            logger.warning(f"Primary model {model_name} rate limited. Retrying with fallback.")
            model_name = settings.gemini_voice_model_fallback
            response = client.models.generate_content(
                model=model_name,
                contents=[prompt, blob],
                config=config
            )
        else:
            raise

    logger.info(f"Voice command parsed successfully using {model_name}")
    
    result_text = response.text
    try:
        parsed_json = json.loads(result_text)
        return VoiceCommandResult(**parsed_json)
    except Exception as e:
        logger.error(f"Failed to parse Gemini response as JSON: {result_text}")
        raise RuntimeError("Failed to parse AI response.") from e

def resolve_medicine_intent(db: Session, tenant_id: int, parsed_result: VoiceCommandResult) -> dict:
    """
    Takes the parsed intent and uses the existing fuzzy matcher to resolve the medicine name.
    """
    if parsed_result.intent == "unclear":
        return {
            "parsed": parsed_result.model_dump(),
            "resolved_medicine": None,
            "requires_confirmation": True
        }

    # Reusing the existing fuzzy matcher from matcher.py
    # Tenant isolation is handled automatically by the DB session listener
    medicine, score, match_type = find_best_match(db, parsed_result.medicine_name)
    
    if not medicine:
        return {
            "parsed": parsed_result.model_dump(),
            "resolved_medicine": None,
            "requires_confirmation": True,
            "message": "Medicine not found, please confirm manually."
        }
    
    return {
        "parsed": parsed_result.model_dump(),
        "resolved_medicine": {
            "id": medicine.id,
            "name": medicine.particulars or medicine.name,
            "unit": medicine.unit,
            "mrp": medicine.mrp,
            "current_stock": float(medicine.current_stock) if medicine.current_stock else 0
        },
        "requires_confirmation": True
    }
