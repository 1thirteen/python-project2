"""导出：CSV、可打印 HTML、成绩单汇总。"""

import csv
import unittest

from service import exports
from service import scores as score_service
from tests.support import TempDatabase, temp_dir


class ExportTest(unittest.TestCase):
    def setUp(self):
        self._db = TempDatabase()
        self.cfg = self._db.__enter__()

    def tearDown(self):
        self._db.__exit__(None, None, None)

    def test_students_csv(self):
        with temp_dir() as tmp:
            path = exports.write_students_csv(self.cfg, tmp / "s.csv")
            with path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
        self.assertEqual(rows[0][:4], ["学号", "姓名", "性别", "班级"])
        self.assertEqual(len(rows), 11)
        self.assertEqual(rows[1][:2], ["20240101", "张伟"])

    def test_scores_csv_filtered(self):
        with temp_dir() as tmp:
            path = exports.write_scores_csv(self.cfg, tmp / "x.csv", student_id=3)
            with path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
        self.assertEqual(len(rows), 6)          # 表头 + 5 条
        self.assertTrue(all(row[0] == "20240103" for row in rows[1:]))

    def test_transcript_summary(self):
        summary = exports.transcript_summary(self.cfg, 1)
        self.assertEqual(summary["graded"], 5)
        self.assertEqual(summary["credits"], 17.5)
        self.assertEqual(summary["weighted"], 90.66)

    def test_transcript_csv(self):
        with temp_dir() as tmp:
            path = exports.write_transcript_csv(self.cfg, 1, tmp / "t.csv")
            with path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
        self.assertEqual(rows[0][:3], ["学号", "姓名", "课程"])
        self.assertEqual(len(rows), 6)

    def test_transcript_html(self):
        html = exports.transcript_html(self.cfg, 1)
        self.assertIn("学生成绩单", html)
        self.assertIn("张伟", html)
        self.assertIn("90.66", html)
        self.assertIn("window.print()", html)
        self.assertIn("2024级计算机科学与技术1班", html)

    def test_transcript_html_with_missing_score(self):
        html = exports.transcript_html(self.cfg, 10)
        self.assertIn("未录入", html)

    def test_failed_export_keeps_data(self):
        with temp_dir() as tmp:
            path = exports.write_scores_csv(self.cfg, tmp / "all.csv")
            self.assertTrue(path.exists())
            self.assertEqual(len(score_service.list_scores(self.cfg)), 41)


if __name__ == "__main__":
    unittest.main()
