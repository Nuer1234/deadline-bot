import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dateparse import TZ
from formatting import relative_due
from reminders import pick_tasks_to_remind, should_run_digest, split_by_urgency
from storage import Store

NOW = datetime(2026, 9, 2, 10, 0, tzinfo=TZ)
GUILD = 111
ALICE, BOB = 1, 2


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "data.json")

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, title, days, owner=ALICE, category=None):
        return self.store.add_task(
            GUILD, title, NOW + timedelta(days=days), owner, f"user{owner}", category, now=NOW
        )


class StoreTest(StoreTestCase):
    def test_ids_increase(self):
        self.assertEqual(self.add("a", 1).id, 1)
        self.assertEqual(self.add("b", 2).id, 2)

    def test_list_sorted_by_due(self):
        self.add("ไกล", 5)
        self.add("ใกล้", 1)
        self.assertEqual([t.title for t in self.store.list_tasks(GUILD)], ["ใกล้", "ไกล"])

    def test_done_hides_from_list(self):
        task = self.add("a", 1)
        self.store.mark_done(GUILD, task.id, now=NOW)
        self.assertEqual(self.store.list_tasks(GUILD), [])
        self.assertEqual(len(self.store.list_tasks(GUILD, include_done=True)), 1)

    def test_filter_by_owner_and_category(self):
        self.add("ของ alice", 1, owner=ALICE, category="calculus")
        self.add("ของ bob", 1, owner=BOB)
        self.assertEqual(len(self.store.list_tasks(GUILD, owner_id=ALICE)), 1)
        self.assertEqual(len(self.store.list_tasks(GUILD, category="Calculus")), 1)

    def test_guilds_are_separate(self):
        self.add("a", 1)
        self.assertEqual(self.store.list_tasks(222), [])

    def test_persists_across_restart(self):
        self.add("จำได้ไหม", 1, category="physics")
        reopened = Store(self.store.path)
        tasks = reopened.list_tasks(GUILD)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].title, "จำได้ไหม")
        # The value read back must still be the same Thai local time that was saved
        self.assertEqual(tasks[0].due_dt, NOW + timedelta(days=1))

    def test_stats(self):
        early = self.add("ส่งทัน", 5)
        late = self.add("ส่งช้า", -5)
        self.add("ยังไม่ทำ", 3)
        self.store.mark_done(GUILD, early.id, now=NOW)
        self.store.mark_done(GUILD, late.id, now=NOW)
        stats = self.store.stats(GUILD)
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["done"], 2)
        self.assertEqual(stats["pending"], 1)
        self.assertEqual(stats["on_time"], 1)
        self.assertEqual(stats["percent"], 67)

    def test_delete(self):
        task = self.add("ผิด", 1)
        self.store.delete_task(GUILD, task.id)
        self.assertIsNone(self.store.get_task(GUILD, task.id))


class ReminderTest(StoreTestCase):
    def test_picks_due_within_lead_time_only(self):
        self.add("พรุ่งนี้", 1)
        self.add("อีก 3 วัน", 3)
        self.add("เลยกำหนด", -2)
        picked = pick_tasks_to_remind(self.store.all_tasks(GUILD), NOW)
        self.assertEqual([t.title for t in picked], ["เลยกำหนด", "พรุ่งนี้"])

    def test_skips_done(self):
        task = self.add("เสร็จแล้ว", 1)
        self.store.mark_done(GUILD, task.id, now=NOW)
        self.assertEqual(pick_tasks_to_remind(self.store.all_tasks(GUILD), NOW), [])

    def test_no_double_reminder_same_day(self):
        task = self.add("พรุ่งนี้", 1)
        self.store.mark_reminded(GUILD, task.id, NOW.date().isoformat())
        self.assertEqual(pick_tasks_to_remind(self.store.all_tasks(GUILD), NOW), [])
        # The next day it may be announced again, since the task is still unfinished
        self.assertEqual(len(pick_tasks_to_remind(self.store.all_tasks(GUILD), NOW + timedelta(days=1))), 1)

    def test_split_by_urgency(self):
        self.add("เลย", -1)
        self.add("วันนี้", 0)
        self.add("พรุ่งนี้", 1)
        overdue, today, upcoming = split_by_urgency(self.store.list_tasks(GUILD), NOW)
        self.assertEqual([t.title for t in overdue], ["เลย"])
        self.assertEqual([t.title for t in today], ["วันนี้"])
        self.assertEqual([t.title for t in upcoming], ["พรุ่งนี้"])


class DigestScheduleTest(unittest.TestCase):
    def test_not_before_reminder_hour(self):
        self.assertFalse(should_run_digest(None, NOW.replace(hour=7), hour=8))

    def test_runs_once_per_day(self):
        self.assertTrue(should_run_digest(None, NOW, hour=8))
        self.assertFalse(should_run_digest("2026-09-02", NOW, hour=8))

    def test_catches_up_after_downtime(self):
        # Bot was down at 08:00 and only came back at 14:00, so today's digest is still owed
        self.assertTrue(should_run_digest("2026-09-01", NOW.replace(hour=14), hour=8))


class RelativeDueTest(unittest.TestCase):
    def test_counts_calendar_days_not_24h_blocks(self):
        # Due 23:59 tomorrow, asked at 10:00 today: must read as "tomorrow", not "in 2 days"
        tomorrow_night = datetime(2026, 9, 3, 23, 59, tzinfo=TZ)
        self.assertEqual(relative_due(tomorrow_night, NOW), "พรุ่งนี้")
        self.assertEqual(relative_due(datetime(2026, 9, 2, 23, 59, tzinfo=TZ), NOW), "วันนี้")
        self.assertEqual(relative_due(datetime(2026, 9, 6, 23, 59, tzinfo=TZ), NOW), "อีก 4 วัน")

    def test_overdue(self):
        self.assertEqual(relative_due(datetime(2026, 9, 1, 23, 59, tzinfo=TZ), NOW), "เลยกำหนด 1 วัน")


if __name__ == "__main__":
    unittest.main()
