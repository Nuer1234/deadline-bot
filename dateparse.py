"""Turns the date text people actually type into a timezone-aware datetime.

Every datetime in this project is timezone-aware and bound to Asia/Bangkok, offset
included when it is written to disk. With naive datetimes, deploying to a host whose
clock is UTC shifts anything due at midnight by seven hours.

Supported formats:
    2026-09-05          ISO
    5/9/2026  5-9-69    day/month/year (Gregorian / Buddhist / two-digit)
    5/9                 no year, so the next one that has not passed yet
    5 ก.ย. / 5 sep      Thai and English month names
    วันนี้ พรุ่งนี้ มะรืน today tomorrow
    ศุกร์ / friday      the next occurrence of that weekday
A time may follow, e.g. "5/9 23:59". Without one the deadline is 23:59 that day.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    TZ = ZoneInfo("Asia/Bangkok")
except ZoneInfoNotFoundError:
    # Windows ships no system tz database; the `tzdata` package provides one.
    # Thailand has been on a fixed UTC+7 since 1920 with no DST, so a constant is just
    # as correct as the real zone.
    TZ = timezone(timedelta(hours=7), "ICT")

# No time given means the task is due by the end of the day
DEFAULT_TIME = time(23, 59)


class DateParseError(ValueError):
    """The text could not be read as a date."""


MONTHS: dict[str, int] = {}
_MONTH_TH = [
    ("มกราคม", "ม.ค."), ("กุมภาพันธ์", "ก.พ."), ("มีนาคม", "มี.ค."),
    ("เมษายน", "เม.ย."), ("พฤษภาคม", "พ.ค."), ("มิถุนายน", "มิ.ย."),
    ("กรกฎาคม", "ก.ค."), ("สิงหาคม", "ส.ค."), ("กันยายน", "ก.ย."),
    ("ตุลาคม", "ต.ค."), ("พฤศจิกายน", "พ.ย."), ("ธันวาคม", "ธ.ค."),
]
_MONTH_EN = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
for _i, (_full, _abbr) in enumerate(_MONTH_TH, start=1):
    MONTHS[_full] = _i
    MONTHS[_abbr] = _i
    MONTHS[_abbr.replace(".", "")] = _i  # accept "กย" without the dots too
for _i, _name in enumerate(_MONTH_EN, start=1):
    MONTHS[_name] = _i
    MONTHS[_name[:3]] = _i

# 0 = Monday, matching date.weekday()
WEEKDAYS: dict[str, int] = {}
_WEEKDAY_TH = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]
_WEEKDAY_EN = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
for _i, _name in enumerate(_WEEKDAY_TH):
    WEEKDAYS[_name] = _i
for _i, _name in enumerate(_WEEKDAY_EN):
    WEEKDAYS[_name] = _i
    WEEKDAYS[_name[:3]] = _i
WEEKDAYS["พฤหัส"] = 3

RELATIVE_DAYS = {
    "วันนี้": 0, "today": 0,
    "พรุ่งนี้": 1, "พรุ่งนี": 1, "tomorrow": 1, "tmr": 1,
    "มะรืน": 2, "มะรืนนี้": 2,
}

_ISO_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_DMY_RE = re.compile(r"^(\d{1,2})[/.\-](\d{1,2})(?:[/.\-](\d{2,4}))?$")
_TIME_RE = re.compile(r"^(\d{1,2})[:.](\d{2})$")


def now_bkk() -> datetime:
    return datetime.now(TZ)


def _normalize(token: str) -> str:
    return token.strip().lower().rstrip(",")


def _normalize_year(raw: int) -> int:
    """Normalize a year as typed into a Gregorian year.

    2569 -> 2026 (Buddhist), 69 -> 2026 (two-digit Buddhist), 26 -> 2026, 2026 -> 2026
    """
    if raw >= 2400:
        return raw - 543
    if raw < 100:
        # Two digits: a high number reads as Buddhist (69 = 2569), a low one as
        # Gregorian (26 = 2026). Both land on the same year here.
        return 2500 + raw - 543 if raw >= 60 else 2000 + raw
    return raw


def _year_for(day: int, month: int, today: date) -> int:
    """With no year given, pick the year that puts the date in the future (or today)."""
    for year in (today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate >= today:
            return year
    return today.year


def parse_time(token: str) -> time | None:
    m = _TIME_RE.match(_normalize(token))
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def _parse_single(token: str, today: date) -> date | None:
    t = _normalize(token)
    if not t:
        return None

    if t in RELATIVE_DAYS:
        return today + timedelta(days=RELATIVE_DAYS[t])

    weekday_key = t[3:] if t.startswith("วัน") and len(t) > 3 else t
    if weekday_key in WEEKDAYS:
        delta = (WEEKDAYS[weekday_key] - today.weekday()) % 7
        return today + timedelta(days=delta or 7)  # saying "Friday" on a Friday means next Friday

    m = _ISO_RE.match(t)
    if m:
        return _safe_date(_normalize_year(int(m.group(1))), int(m.group(2)), int(m.group(3)))

    m = _DMY_RE.match(t)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = _normalize_year(int(m.group(3))) if m.group(3) else _year_for(day, month, today)
        return _safe_date(year, month, day)

    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_date_tokens(tokens: list[str], today: date | None = None) -> date | None:
    """Read a date from 1-3 tokens, e.g. ['5/9'] or ['5', 'ก.ย.', '2569']."""
    today = today or now_bkk().date()
    tokens = [_normalize(t) for t in tokens if _normalize(t)]

    if len(tokens) == 1:
        return _parse_single(tokens[0], today)

    if len(tokens) in (2, 3):
        # Shapes like "5 ก.ย." or "sep 5", optionally followed by a year
        head, tail = tokens[0], tokens[1]
        day = month = None
        if head.isdigit() and tail in MONTHS:
            day, month = int(head), MONTHS[tail]
        elif head in MONTHS and tail.isdigit():
            day, month = int(tail), MONTHS[head]
        if day is None:
            return None
        if len(tokens) == 3:
            if not tokens[2].isdigit():
                return None
            year = _normalize_year(int(tokens[2]))
        else:
            year = _year_for(day, month, today)
        return _safe_date(year, month, day)

    return None


@dataclass
class ParsedTask:
    title: str
    due: datetime
    category: str | None


def parse_deadline(text: str, now: datetime | None = None) -> ParsedTask:
    """Split the text after !add into (title, deadline, category).

    The date comes last, an optional time right after it, and a #category may sit
    anywhere in the line:
        "เขียนรายงาน Calculus #calculus 5/9 23:59"
    """
    now = now or now_bkk()
    today = now.date()

    raw_tokens = text.split()
    category = None
    tokens: list[str] = []
    for token in raw_tokens:
        if token.startswith("#") and len(token) > 1:
            if category is None:
                category = token[1:].lower()
        else:
            tokens.append(token)

    if not tokens:
        raise DateParseError("no task title or date given")

    at = DEFAULT_TIME
    if len(tokens) >= 3:
        maybe_time = parse_time(tokens[-1])
        if maybe_time is not None:
            at = maybe_time
            tokens.pop()

    # Try the trailing tokens longest-first, always leaving at least one word as the title
    for n in (3, 2, 1):
        if len(tokens) <= n:
            continue
        found = parse_date_tokens(tokens[-n:], today)
        if found is not None:
            title = " ".join(tokens[:-n]).strip()
            return ParsedTask(title, datetime.combine(found, at, tzinfo=TZ), category)

    raise DateParseError("could not read a date at the end of the text")
