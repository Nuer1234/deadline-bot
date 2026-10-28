import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dateparse import TZ, DateParseError, parse_deadline, parse_time

# Fixed reference point: Wednesday 2 September 2026, 10:00 Thai time
NOW = datetime(2026, 9, 2, 10, 0, tzinfo=TZ)


class ParseDeadlineTest(unittest.TestCase):
    def parse(self, text):
        return parse_deadline(text, now=NOW)

    def test_iso(self):
        p = self.parse("เขียนรายงาน 2026-09-05")
        self.assertEqual(p.title, "เขียนรายงาน")
        self.assertEqual(p.due, datetime(2026, 9, 5, 23, 59, tzinfo=TZ))

    def test_slash_with_year(self):
        self.assertEqual(self.parse("งาน 5/9/2026").due.date().isoformat(), "2026-09-05")

    def test_buddhist_year(self):
        self.assertEqual(self.parse("งาน 5/9/2569").due.date().isoformat(), "2026-09-05")

    def test_two_digit_buddhist_year(self):
        self.assertEqual(self.parse("งาน 5/9/69").due.date().isoformat(), "2026-09-05")

    def test_no_year_picks_next_occurrence(self):
        # 1 September has already passed, so it must land next year
        self.assertEqual(self.parse("งาน 1/9").due.date().isoformat(), "2027-09-01")
        self.assertEqual(self.parse("งาน 5/9").due.date().isoformat(), "2026-09-05")

    def test_relative_words(self):
        self.assertEqual(self.parse("งาน วันนี้").due.date().isoformat(), "2026-09-02")
        self.assertEqual(self.parse("งาน พรุ่งนี้").due.date().isoformat(), "2026-09-03")
        self.assertEqual(self.parse("งาน มะรืน").due.date().isoformat(), "2026-09-04")
        self.assertEqual(self.parse("งาน tomorrow").due.date().isoformat(), "2026-09-03")

    def test_weekday_means_next_one(self):
        self.assertEqual(self.parse("งาน ศุกร์").due.date().isoformat(), "2026-09-04")
        self.assertEqual(self.parse("งาน วันพุธ").due.date().isoformat(), "2026-09-09")
        self.assertEqual(self.parse("งาน friday").due.date().isoformat(), "2026-09-04")

    def test_month_name(self):
        self.assertEqual(self.parse("อ่านหนังสือ 5 ก.ย.").due.date().isoformat(), "2026-09-05")
        self.assertEqual(self.parse("อ่านหนังสือ 5 ก.ย. 2570").due.date().isoformat(), "2027-09-05")
        self.assertEqual(self.parse("read 5 sep").due.date().isoformat(), "2026-09-05")

    def test_explicit_time(self):
        p = self.parse("ส่งแล็บ 5/9 16:30")
        self.assertEqual(p.due, datetime(2026, 9, 5, 16, 30, tzinfo=TZ))
        self.assertEqual(p.title, "ส่งแล็บ")

    def test_category(self):
        p = self.parse("เขียนรายงาน #Calculus 5/9")
        self.assertEqual(p.title, "เขียนรายงาน")
        self.assertEqual(p.category, "calculus")

    def test_title_keeps_spaces(self):
        self.assertEqual(self.parse("ทำ lab 3 ให้เสร็จ พรุ่งนี้").title, "ทำ lab 3 ให้เสร็จ")

    def test_title_with_number_before_date(self):
        p = self.parse("อ่านบทที่ 12 5/9")
        self.assertEqual(p.title, "อ่านบทที่ 12")
        self.assertEqual(p.due.date().isoformat(), "2026-09-05")

    def test_result_is_timezone_aware(self):
        self.assertIsNotNone(self.parse("งาน พรุ่งนี้").due.tzinfo)

    def test_bad_date_raises(self):
        with self.assertRaises(DateParseError):
            self.parse("งานที่ไม่มีวันที่")
        with self.assertRaises(DateParseError):
            self.parse("งาน 32/13")


class ParseTimeTest(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_time("23:59").hour, 23)
        self.assertEqual(parse_time("9.05").minute, 5)

    def test_invalid(self):
        self.assertIsNone(parse_time("25:00"))
        self.assertIsNone(parse_time("5.9"))   # this is a date, not a time
        self.assertIsNone(parse_time("abc"))


if __name__ == "__main__":
    unittest.main()
