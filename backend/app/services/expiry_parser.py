import re
import calendar
from datetime import date
from typing import Optional

MONTH_ABBR = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def _resolve(month: int, year: int) -> Optional[date]:
    if not (1 <= month <= 12):
        return None
    if year < 100:
        year += 2000
    if year < 2000 or year > 2100:
        return None
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def parse_expiry_string(text: Optional[str]) -> Optional[date]:
    if not text:
        return None
    text = text.strip().upper()
    if not text:
        return None

    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    m = re.match(r"^(\d{1,2})\s*/\s*(\d{2,4})$", text)
    if m:
        return _resolve(int(m.group(1)), int(m.group(2)))

    m = re.match(r"^([A-Z]{3})[-/]?\s*(\d{2,4})$", text)
    if m and m.group(1) in MONTH_ABBR:
        return _resolve(MONTH_ABBR[m.group(1)], int(m.group(2)))

    m = re.match(r"^(\d{1,2})[.\-](\d{2,4})$", text)
    if m:
        return _resolve(int(m.group(1)), int(m.group(2)))

    return None
