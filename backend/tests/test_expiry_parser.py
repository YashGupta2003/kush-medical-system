"""
Ground-truth tests for expiry_parser.py, covering the real formats seen on
your uploaded bills (Hari Krishna Distributor, Rathore Medicos, etc.) plus
the manual ISO-date input path used by the 'missing expiry' fill-in form.
"""
import calendar
from datetime import date

import pytest

from app.services.expiry_parser import parse_expiry_string


@pytest.mark.parametrize("text,expected", [
    ("6/27", date(2027, 6, 30)),
    ("10/27", date(2027, 10, 31)),
    ("9/27", date(2027, 9, 30)),
    ("8/27", date(2027, 8, 31)),
    ("1/27", date(2027, 1, 31)),
    ("MAR-28", date(2028, 3, 31)),
    ("03-2028", date(2028, 3, 31)),
    ("10/2028", date(2028, 10, 31)),
    ("2027-06-15", date(2027, 6, 15)),   # exact date from a manual <input type="date">
])
def test_parses_known_formats(text, expected):
    assert parse_expiry_string(text) == expected


@pytest.mark.parametrize("text", ["junk", "", None, "13/27", "99/99", "   "])
def test_returns_none_for_unparseable_or_invalid_input(text):
    assert parse_expiry_string(text) is None


def test_resolves_to_last_day_of_month_not_first():
    """
    A medicine printed as expiring '2/28' should be treated as good through
    the END of February 2028, not the 1st - otherwise it would incorrectly
    show as expired for most of its actually-valid month.
    """
    result = parse_expiry_string("2/28")
    expected_last_day = calendar.monthrange(2028, 2)[1]
    assert result.day == expected_last_day
    assert result.month == 2
    assert result.year == 2028


def test_two_digit_year_assumes_2000s():
    result = parse_expiry_string("5/30")
    assert result.year == 2030


def test_case_insensitive_month_abbreviation():
    assert parse_expiry_string("mar-28") == parse_expiry_string("MAR-28")