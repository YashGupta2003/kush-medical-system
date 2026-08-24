import os
import json
from app.config import settings
from app.services.bill_parser import ParsedRow

def test_groq():
    if not settings.GROQ_API_KEY:
        print("No API key")
        return
    print("API Key available")
    
if __name__ == "__main__":
    test_groq()
