"""分页：页数、边界、跨页不重复。"""

import unittest

from service import scores as score_service
from service import students as student_service
from tests.support import TempDatabase


class StudentPagingTest(unittest.TestCase):
    def setUp(self):
        self._db = TempDatabase()
        self.cfg = self._db.__enter__()

    def tearDown(self):
        self._db.__exit__(None, None, None)

    def test_default_page_holds_everything(self):
        result = student_service.page(self.cfg)
        self.assertEqual(result["total"], 10)
        self.assertEqual(result["pages"], 1)
        self.assertEqual(len(result["rows"]), 10)
        self.assertEqual(result["page"], 1)

    def test_small_pages(self):
        first = student_service.page(self.cfg, size=4)
        self.assertEqual(first["pages"], 3)
        self.assertEqual(len(first["rows"]), 4)

        last = student_service.page(self.cfg, size=4, page=3)
        self.assertEqual(last["page"], 3)
        self.assertEqual(len(last["rows"]), 2)

    def test_page_out_of_range_is_clamped(self):
        result = student_service.page(self.cfg, size=4, page=99)
        self.assertEqual(result["page"], 3)

    def test_total_respects_filters(self):
        result = student_service.page(self.cfg, keyword="王", size=2)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["pages"], 1)

        result = student_service.page(self.cfg, class_id=2, size=2)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["pages"], 2)

    def test_no_duplicates_across_pages(self):
        seen = []
        for page in (1, 2, 3):
            seen += [row["sno"] for row in student_service.page(self.cfg, size=4, page=page)["rows"]]
        self.assertEqual(len(seen), 10)
        self.assertEqual(len(set(seen)), 10)


class ScorePagingTest(unittest.TestCase):
    def setUp(self):
        self._db = TempDatabase()
        self.cfg = self._db.__enter__()

    def tearDown(self):
        self._db.__exit__(None, None, None)

    def test_score_pages(self):
        result = score_service.page(self.cfg, size=20)
        self.assertEqual(result["total"], 41)
        self.assertEqual(result["pages"], 3)
        self.assertEqual(len(result["rows"]), 20)

        last = score_service.page(self.cfg, size=20, page=3)
        self.assertEqual(len(last["rows"]), 1)

    def test_only_missing(self):
        result = score_service.page(self.cfg, only_missing=True)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["rows"][0]["sno"], "20250303")

    def test_search_by_keyword(self):
        result = score_service.page(self.cfg, keyword="高等数学")
        self.assertEqual(result["total"], 7)
        self.assertEqual(result["pages"], 1)

    def test_empty_result_is_one_page(self):
        result = score_service.page(self.cfg, keyword="不存在的课程")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["pages"], 1)
        self.assertEqual(result["rows"], [])


if __name__ == "__main__":
    unittest.main()
