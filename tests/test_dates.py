from datetime import date

import pytest

from amagi_deadlines.dates import (
    Duration, add_business_days, add_months, find_dates, find_durations, parse_date,
    shift, words_to_int,
)


@pytest.mark.parametrize("text, expected", [
    ("January 1, 2026", date(2026, 1, 1)),
    ("Jan. 1 2026", date(2026, 1, 1)),
    ("Sept. 30, 2027", date(2027, 9, 30)),
    ("March 3rd, 2026", date(2026, 3, 3)),
    ("1 January 2026", date(2026, 1, 1)),
    ("the 1st day of July, 2025", date(2025, 7, 1)),
    ("the first day of July 2025", date(2025, 7, 1)),
    ("the twenty-first day of May, 2024", date(2024, 5, 21)),
    ("2026-02-28", date(2026, 2, 28)),
    ("02/28/2026", date(2026, 2, 28)),
])
def test_parse_date_formats(text, expected):
    assert parse_date(text) == expected


def test_impossible_dates_are_ignored():
    assert parse_date("February 30, 2026") is None
    assert find_dates("on 13/45/2026") == []


def test_find_dates_reports_positions():
    text = "begins on March 1, 2026 and ends on February 28, 2031."
    found = find_dates(text)
    assert [f.value for f in found] == [date(2026, 3, 1), date(2031, 2, 28)]
    assert text[found[0].start:found[0].end] == "March 1, 2026"


@pytest.mark.parametrize("text, n", [
    ("sixty", 60), ("twenty-one", 21), ("one hundred twenty", 120),
    ("one hundred and eighty", 180), ("twelve", 12),
])
def test_words_to_int(text, n):
    assert words_to_int(text) == n


@pytest.mark.parametrize("text, expected", [
    ("sixty (60) days", Duration(days=60)),
    ("60 days", Duration(days=60)),
    ("thirty days", Duration(days=30)),
    ("ten (10) business days", Duration(days=10, business=True)),
    ("ten (10) calendar days", Duration(days=10)),
    ("twelve (12) months", Duration(months=12)),
    ("five (5) years", Duration(months=60)),
    ("two weeks", Duration(days=14)),
    ("a year", Duration(months=12)),
])
def test_find_durations(text, expected):
    found = find_durations(f"at least {text} before")
    assert [f.value for f in found] == [expected]


def test_adjacent_durations_combine():
    found = find_durations("a term of five (5) years and three (3) days")
    assert [f.value for f in found] == [Duration(months=60, days=3)]


def test_duration_str():
    assert str(Duration(months=12)) == "1 year"
    assert str(Duration(months=9)) == "9 months"
    assert str(Duration(days=60)) == "60 days"
    assert str(Duration(days=1, business=True)) == "1 business day"
    assert str(Duration(months=24, days=5)) == "2 years and 5 days"


def test_add_months_clamps_to_month_end():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)
    assert add_months(date(2026, 3, 31), -1) == date(2026, 2, 28)
    assert add_months(date(2026, 11, 15), 14) == date(2028, 1, 15)


def test_business_days_skip_weekends():
    friday = date(2026, 10, 23)
    assert add_business_days(friday, 1) == date(2026, 10, 26)
    assert add_business_days(date(2026, 10, 26), -1) == friday


def test_shift_backwards():
    assert shift(date(2027, 12, 31), Duration(days=90), sign=-1) == date(2027, 10, 2)
    assert shift(date(2031, 2, 28), Duration(months=12), sign=-1) == date(2030, 2, 28)
