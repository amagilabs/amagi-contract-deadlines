"""Find calendar dates and durations ("sixty (60) days") in contract text."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "october": 10,
    "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}

UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}
ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11,
    "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15,
    "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19,
    "twentieth": 20, "thirtieth": 30,
}

_MONTH = r"(?P<mon>" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\.?"
_ORD_WORD = (
    r"(?:(?:twenty|thirty)[\s-])?(?:"
    + "|".join(sorted(ORDINALS, key=len, reverse=True))
    + r")"
)
_DAY = r"(?P<day>\d{1,2})(?:st|nd|rd|th)?"
_YEAR = r"(?P<year>(?:19|20)\d{2})"

_DATE_PATTERNS = [
    # January 1, 2026 / Jan. 1 2026 / January 1st, 2026
    re.compile(r"\b" + _MONTH + r"\s+" + _DAY + r",?\s+" + _YEAR + r"\b", re.I),
    # 1 January 2026 / 1st day of January, 2026 / the first day of January 2026
    re.compile(
        r"\b(?:(?P<day>\d{1,2})(?:st|nd|rd|th)?|(?P<oday>" + _ORD_WORD + r"))"
        r"\s+(?:day\s+of\s+)?" + _MONTH + r",?\s+" + _YEAR + r"\b",
        re.I,
    ),
    # 2026-01-01
    re.compile(r"\b(?P<year>(?:19|20)\d{2})-(?P<mnum>\d{1,2})-(?P<day>\d{1,2})\b"),
    # 01/01/2026 (US month/day/year)
    re.compile(r"\b(?P<mnum>\d{1,2})/(?P<day>\d{1,2})/(?P<year>(?:19|20)\d{2})\b"),
]


@dataclass
class Found:
    value: date
    start: int
    end: int
    text: str


def _ordinal_value(word: str) -> Optional[int]:
    parts = re.split(r"[\s-]+", word.lower())
    if len(parts) == 2:
        tens = {"twenty": 20, "thirty": 30}.get(parts[0])
        unit = ORDINALS.get(parts[1])
        if tens is None or unit is None or unit > 9:
            return None
        return tens + unit
    return ORDINALS.get(parts[0])


def find_dates(text: str) -> List[Found]:
    """Every calendar date in ``text``, in order, without overlaps."""
    hits: List[Found] = []
    for pattern in _DATE_PATTERNS:
        for m in pattern.finditer(text):
            groups = m.groupdict()
            try:
                if groups.get("mon"):
                    month = MONTHS[groups["mon"].lower().rstrip(".")]
                else:
                    month = int(groups["mnum"])
                if groups.get("day"):
                    day = int(groups["day"])
                else:
                    day = _ordinal_value(groups["oday"]) or 0
                value = date(int(groups["year"]), month, day)
            except (ValueError, KeyError, TypeError):
                continue
            hits.append(Found(value, m.start(), m.end(), m.group(0)))
    hits.sort(key=lambda f: (f.start, -(f.end - f.start)))
    out: List[Found] = []
    for hit in hits:
        if out and hit.start < out[-1].end:
            continue
        out.append(hit)
    return out


def parse_date(text: str) -> Optional[date]:
    """Parse one date written any way find_dates understands."""
    found = find_dates(text.strip())
    return found[0].value if found else None


# ---------------------------------------------------------------- durations

_NUM_WORD = "|".join(sorted(list(UNITS) + list(TENS) + ["hundred"], key=len, reverse=True))
_NUM_WORDS = r"(?:(?:" + _NUM_WORD + r")(?:[\s-]+(?:and[\s-]+)?(?:" + _NUM_WORD + r"))*)"
_DURATION_RE = re.compile(
    r"\b(?:(?P<words>" + _NUM_WORDS + r")\s*\(\s*(?P<paren>\d{1,4})\s*\)"
    r"|(?P<digits>\d{1,4})"
    r"|(?P<bare>" + _NUM_WORDS + r")"
    r"|(?P<article>an?))"
    r"[\s-]+(?P<kind>calendar[\s-]+|business[\s-]+|banking[\s-]+|working[\s-]+)?"
    r"(?P<unit>day|week|month|year)s?\b",
    re.I,
)
_ANNUAL_RE = re.compile(r"\b(?P<unit>annual|yearly|monthly)\b", re.I)


def words_to_int(text: str) -> Optional[int]:
    """'one hundred and eighty' -> 180. None when it is not a number."""
    total, current = 0, 0
    seen = False
    for token in re.split(r"[\s-]+", text.lower().strip()):
        if not token or token == "and":
            continue
        if token in UNITS:
            current += UNITS[token]
        elif token in TENS:
            current += TENS[token]
        elif token == "hundred":
            current = (current or 1) * 100
        else:
            return None
        seen = True
    return total + current if seen else None


@dataclass(frozen=True)
class Duration:
    months: int = 0
    days: int = 0
    business: bool = False

    def __str__(self) -> str:
        parts = []
        if self.months:
            if self.months % 12 == 0:
                years = self.months // 12
                parts.append(f"{years} year" + ("s" if years != 1 else ""))
            else:
                parts.append(f"{self.months} month" + ("s" if self.months != 1 else ""))
        if self.days or not parts:
            word = "business day" if self.business else "day"
            parts.append(f"{self.days} {word}" + ("s" if self.days != 1 else ""))
        return " and ".join(parts)

    def __add__(self, other: "Duration") -> "Duration":
        return Duration(self.months + other.months, self.days + other.days,
                        self.business or other.business)


@dataclass
class FoundDuration:
    value: Duration
    start: int
    end: int
    text: str


def find_durations(text: str) -> List[FoundDuration]:
    """Every duration in ``text``. Adjacent ones joined by 'and' are combined."""
    raw: List[FoundDuration] = []
    for m in _DURATION_RE.finditer(text):
        g = m.groupdict()
        if g["paren"]:
            n = int(g["paren"])
        elif g["digits"]:
            n = int(g["digits"])
        elif g["bare"]:
            n = words_to_int(g["bare"])
        else:
            n = 1  # "a year", "an additional ..." is handled by the article branch
        if n is None:
            continue
        unit = g["unit"].lower()
        business = bool(g["kind"]) and not g["kind"].lower().startswith("calendar")
        if unit == "year":
            value = Duration(months=12 * n)
        elif unit == "month":
            value = Duration(months=n)
        elif unit == "week":
            value = Duration(days=7 * n)
        else:
            value = Duration(days=n, business=business)
        raw.append(FoundDuration(value, m.start(), m.end(), m.group(0)))
    for m in _ANNUAL_RE.finditer(text):
        unit = m.group("unit").lower()
        value = Duration(months=1) if unit == "monthly" else Duration(months=12)
        raw.append(FoundDuration(value, m.start(), m.end(), m.group(0)))
    raw.sort(key=lambda d: d.start)

    out: List[FoundDuration] = []
    for item in raw:
        if out and item.start < out[-1].end:
            continue
        if out and re.fullmatch(r"\s*(?:,\s*)?and\s+", text[out[-1].end:item.start]) \
                and out[-1].value.months and not item.value.months:
            prev = out[-1]
            out[-1] = FoundDuration(prev.value + item.value, prev.start, item.end,
                                    text[prev.start:item.end])
            continue
        out.append(item)
    return out


# ---------------------------------------------------------------- arithmetic

def add_months(d: date, months: int) -> date:
    index = d.year * 12 + (d.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def add_business_days(d: date, n: int) -> date:
    step = 1 if n >= 0 else -1
    remaining = abs(n)
    while remaining:
        d += timedelta(days=step)
        if d.weekday() < 5:
            remaining -= 1
    return d


def shift(d: date, duration: Duration, sign: int = 1) -> date:
    """d plus (sign=1) or minus (sign=-1) a duration."""
    out = add_months(d, sign * duration.months)
    if duration.business:
        return add_business_days(out, sign * duration.days)
    return out + timedelta(days=sign * duration.days)
