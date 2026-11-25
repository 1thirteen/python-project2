"""统计报表：口径与文档中的数字逐一核对。"""

import unittest

from service import reports
from tests.support import TempDatabase


class ReportsTest(unittest.TestCase):
    def setUp(self):
        self._db = TempDatabase()
        self.cfg = self._db.__enter__()

    def tearDown(self):
        self._db.__exit__(None, None, None)

    def test_overview(self):
        info = reports.overview(self.cfg)
        self.assertEqual(info["classes"], 3)
        self.assertEqual(info["students"], 10)
        self.assertEqual(info["courses"], 5)
        self.assertEqual(info["scores"], 41)
        self.assertEqual(info["missing"], 1)
        self.assertEqual(info["avg_score"], 80.17)

    def test_class_summary(self):
        rows = {row["class_name"]: row for row in reports.class_summary(self.cfg)}
        self.assertEqual(rows["2024级计算机科学与技术1班"]["students"], 4)
        self.assertEqual(rows["2024级计算机科学与技术1班"]["avg_score"], 77.0)
        self.assertEqual(rows["2024级软件工程2班"]["avg_score"], 84.73)
        self.assertEqual(rows["2025级数据科学与大数据技术1班"]["avg_score"], 79.2)

    def test_course_stats(self):
        rows = {row["cno"]: row for row in reports.course_stats(self.cfg)}
        self.assertEqual(rows["C001"]["graded"], 7)
        self.assertEqual(rows["C001"]["pass_rate"], 85.7)
        self.assertEqual(rows["C002"]["graded"], 10)
        self.assertEqual(rows["C002"]["pass_rate"], 100.0)
        self.assertEqual(rows["C003"]["graded"], 9)
        self.assertEqual(rows["C003"]["avg_score"], 82.11)
        self.assertEqual(rows["C005"]["min_score"], 60.0)

    def test_ranking(self):
        rows = reports.ranking(self.cfg)
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0]["sno"], "20240101")
        self.assertEqual(rows[0]["weighted_avg"], 90.66)
        self.assertEqual(rows[-1]["sno"], "20240103")
        self.assertEqual(rows[-1]["weighted_avg"], 56.74)

    def test_ranking_is_descending(self):
        values = [row["weighted_avg"] for row in reports.ranking(self.cfg)]
        self.assertEqual(values, sorted(values, reverse=True))


if __name__ == "__main__":
    unittest.main()
