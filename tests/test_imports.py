"""CSV 导入：正常导入、逐行报错、模板。"""

import unittest

from common.errors import ValidationError
from service import imports as import_service
from service import scores as score_service
from service import students as student_service
from tests.support import TempDatabase, temp_dir


def write_csv(path, text):
    path.write_text(text, encoding="utf-8-sig")
    return path


class StudentImportTest(unittest.TestCase):
    def setUp(self):
        self._db = TempDatabase()
        self.cfg = self._db.__enter__()

    def tearDown(self):
        self._db.__exit__(None, None, None)

    def test_import_valid_rows(self):
        with temp_dir() as tmp:
            path = write_csv(tmp / "s.csv", (
                "学号,姓名,性别,班级,电话,邮箱,出生日期\n"
                "20260301,林小满,女,2024级软件工程2班,13800000010,lin@example.com,2008-01-01\n"
                "20260302,周舟,男,,13900000000,,\n"
            ))
            result = import_service.import_students(self.cfg, path)
        self.assertEqual(result["inserted"], 2)
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(student_service.list_students(self.cfg)), 12)
        row = [s for s in student_service.list_students(self.cfg) if s["sno"] == "20260302"][0]
        self.assertIsNone(row["class_id"])

    def test_duplicate_and_bad_rows_are_reported(self):
        with temp_dir() as tmp:
            path = write_csv(tmp / "bad.csv", (
                "学号,姓名,性别,班级\n"
                "20240101,重名,男,2024级软件工程2班\n"
                "20260303,小明,未知,\n"
                "20260304,小红,女,不存在的班\n"
                "20260305,小刚,男,2024级软件工程2班\n"
            ))
            result = import_service.import_students(self.cfg, path)
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(len(result["errors"]), 3)
        lines = [line for line, _message in result["errors"]]
        self.assertEqual(lines, [2, 3, 4])

    def test_missing_required_columns(self):
        with temp_dir() as tmp:
            path = write_csv(tmp / "bad.csv", "电话,邮箱\n13800000000,a@b.com\n")
            with self.assertRaises(ValidationError):
                import_service.import_students(self.cfg, path)

    def test_template_round_trip(self):
        with temp_dir() as tmp:
            template = import_service.write_template(tmp / "t.csv", "students")
            text = template.read_text(encoding="utf-8-sig")
            self.assertTrue(text.startswith("学号,姓名,性别"))
            # 模板里的示例行可以直接导入
            result = import_service.import_students(self.cfg, template)
        self.assertEqual(result["inserted"], 1)


class ScoreImportTest(unittest.TestCase):
    def setUp(self):
        self._db = TempDatabase()
        self.cfg = self._db.__enter__()

    def tearDown(self):
        self._db.__exit__(None, None, None)

    def test_upsert_and_errors(self):
        with temp_dir() as tmp:
            path = write_csv(tmp / "s.csv", (
                "学号,课程号,学期,成绩\n"
                "20240101,C001,2024-2025-1,80\n"      # 已有记录 -> 更新
                "20240101,C004,2024-2025-2,77\n"      # 已有记录 -> 更新
                "20240102,C001,2024-2025-1,abc\n"     # 成绩非法
                "99999999,C001,2024-2025-1,90\n"      # 学号不存在
                "20240101,C999,2024-2025-1,90\n"      # 课程不存在
                "20240102,C004,2024-2025-2,\n"        # 留空 -> 未录入
            ))
            result = import_service.import_scores(self.cfg, path)
        self.assertEqual(result["saved"], 3)
        self.assertEqual(len(result["errors"]), 3)
        rows = score_service.list_scores(self.cfg, student_id=1, course_id=1,
                                         term="2024-2025-1")
        self.assertEqual(rows[0]["score"], 80.0)
        missing = score_service.list_scores(self.cfg, student_id=2, course_id=4,
                                            term="2024-2025-2")
        self.assertIsNone(missing[0]["score"])

    def test_template(self):
        with temp_dir() as tmp:
            template = import_service.write_template(tmp / "t.csv", "scores")
            self.assertTrue(template.read_text(encoding="utf-8-sig").startswith("学号,课程号"))


if __name__ == "__main__":
    unittest.main()
