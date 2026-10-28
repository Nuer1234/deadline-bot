"""Formatting for the messages the bot sends back to Discord.

The month and weekday names below are the bot's output language and stay in Thai.
"""

from __future__ import annotations

from datetime import datetime

from dateparse import TZ
from storage import Task

THAI_MONTH_ABBR = [
    "", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
    "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
]
THAI_WEEKDAY_ABBR = ["จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา."]


def format_due(due: datetime, now: datetime) -> str:
    """e.g. 'ศ. 5 ก.ย. 23:59' — the Buddhist year is appended only when it differs from now."""
    due = due.astimezone(TZ)
    text = f"{THAI_WEEKDAY_ABBR[due.weekday()]} {due.day} {THAI_MONTH_ABBR[due.month]}"
    if due.year != now.year:
        text += f" {due.year + 543}"
    return f"{text} {due:%H:%M}"


def relative_due(due: datetime, now: datetime) -> str:
    """Human-readable time left, counted in calendar days rather than 24-hour blocks.

    People read "tomorrow" as the next day, not as "in 23 hours". Dividing a timedelta
    by 86400 would make a task due tomorrow night show up as "1 day" or "2 days"
    depending on what time of day you happened to ask.
    """
    days = (due.astimezone(TZ).date() - now.astimezone(TZ).date()).days
    if due < now:
        return "เลยกำหนดแล้ว" if days == 0 else f"เลยกำหนด {abs(days)} วัน"
    if days == 0:
        return "วันนี้"
    if days == 1:
        return "พรุ่งนี้"
    return f"อีก {days} วัน"


def urgency_icon(due: datetime, now: datetime) -> str:
    days = (due.astimezone(TZ).date() - now.astimezone(TZ).date()).days
    if due < now:
        return "🔴"
    if days <= 1:
        return "🟠"
    if days <= 3:
        return "🟡"
    return "🟢"


def task_line(task: Task, now: datetime, show_owner: bool = False) -> str:
    parts = [
        f"{urgency_icon(task.due_dt, now)} `#{task.id}`",
        f"**{task.title}**",
        f"— {format_due(task.due_dt, now)} ({relative_due(task.due_dt, now)})",
    ]
    if task.category:
        parts.append(f"`#{task.category}`")
    if show_owner:
        parts.append(f"· {task.owner_name}")
    return " ".join(parts)
