"""Reminder logic, kept free of discord so the tests need no network."""

from __future__ import annotations

from datetime import datetime, timedelta

from storage import Task

# How many days before the due date to warn
LEAD_DAYS = 1


def should_run_digest(last_digest_date: str | None, now: datetime, hour: int) -> bool:
    """Is this guild's daily digest still owed?

    Asks "has today's digest gone out yet?" rather than firing exactly at `hour`.
    Firing on the dot means that if the bot happens to be down at 08:00, that day's
    reminder is lost for good; this way it is sent as soon as the bot is back.
    """
    if now.hour < hour:
        return False
    return last_digest_date != now.date().isoformat()


def pick_tasks_to_remind(tasks: list[Task], now: datetime, lead_days: int = LEAD_DAYS) -> list[Task]:
    """Tasks worth announcing today: unfinished, due within `lead_days`, not yet announced today.

    Overdue tasks are re-announced every day until someone runs !done. That nagging
    is deliberate.
    """
    today = now.date()
    cutoff = today + timedelta(days=lead_days)
    picked = [
        t for t in tasks
        if not t.done and t.due_dt.date() <= cutoff and today.isoformat() not in t.reminded_on
    ]
    return sorted(picked, key=lambda t: t.due_dt)


def split_by_urgency(tasks: list[Task], now: datetime) -> tuple[list[Task], list[Task], list[Task]]:
    """Split into (overdue, due today, due tomorrow or later)."""
    today = now.date()
    overdue, today_due, upcoming = [], [], []
    for t in tasks:
        due = t.due_dt
        if due < now:
            overdue.append(t)
        elif due.date() == today:
            today_due.append(t)
        else:
            upcoming.append(t)
    return overdue, today_due, upcoming
