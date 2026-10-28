"""Exercise the whole logic layer without a Discord token.

Handy while working on the date parser or the message formatting, since there is no
need to restart the real bot to see the result.
    python demo.py

The sample input and the printed output stay in Thai because that is what the bot
actually receives and sends.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# The Windows console defaults to cp874, which cannot print emoji; force utf-8 first
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dateparse import now_bkk, parse_deadline
from formatting import task_line
from reminders import pick_tasks_to_remind, split_by_urgency
from storage import Store

GUILD = 1
USERS = {10: "ชนน", 11: "เพื่อนร่วมกลุ่ม"}

SAMPLE = [
    (10, "เขียนรายงาน Calculus #calculus 5/9"),
    (10, "ส่งแล็บฟิสิกส์ พรุ่งนี้ 16:30 #physics"),
    (10, "อ่านบทที่ 12 ก่อนสอบ ศุกร์"),
    (11, "ทำ pre-lab #physics วันนี้"),
    (11, "ส่ง assignment Prog เมื่อวาน"),  # deliberately unparseable
]


def plain(text: str) -> str:
    return text.replace("**", "").replace("`", "")


def main():
    now = now_bkk()
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "demo.json")

        print("=== Adding tasks ===")
        for user_id, raw in SAMPLE:
            try:
                parsed = parse_deadline(raw, now=now)
            except ValueError:
                print(f"!add {raw}\n   -> no date found; the bot asks the user to retype")
                continue
            task = store.add_task(
                GUILD, parsed.title, parsed.due, user_id, USERS[user_id], parsed.category, now=now
            )
            print(f"!add {raw}\n   -> {plain(task_line(task, now))}")

        print("\n=== !list all ===")
        for name, group in zip(
            ("เลยกำหนดแล้ว", "ครบกำหนดวันนี้", "กำลังจะถึง"),
            split_by_urgency(store.list_tasks(GUILD), now),
        ):
            if group:
                print(f"[{name}]")
                for task in group:
                    print("  " + plain(task_line(task, now, show_owner=True)))

        print("\n=== Daily digest (what the bot would post this morning) ===")
        due = pick_tasks_to_remind(store.all_tasks(GUILD), now)
        if not due:
            print("  nothing to announce today")
        for task in due:
            print("  " + plain(task_line(task, now, show_owner=True)))

        print("\n=== !done 1, then !stats ===")
        store.mark_done(GUILD, 1, now=now)
        stats = store.stats(GUILD, owner_id=10)
        print(f"  done {stats['done']}/{stats['total']} ({stats['percent']}%) "
              f"· pending {stats['pending']} · on time {stats['on_time']}")


if __name__ == "__main__":
    main()
