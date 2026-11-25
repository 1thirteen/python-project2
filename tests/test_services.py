"""业务层：校验、异常翻译、增删改查。"""

import unittest

from common.errors import ConflictError, NotFoundError, ValidationError
from service import classes as class_service
from service import courses as course_service
from service import scores as score_service
from service import students as student_service
from tests.support import TempDatabase


class StudentServiceTest(unittest.TestCase):
    def setUp(self):
        self._db = TempDatabase()
        self.cfg = self._db.__enter__()

    def tearDown(self):
        self._db.__exit__(None, None, None)

    def test_list_and_search(self):
        self.assertEqual(len(student_service.list_students(self.cfg)), 10)
        rows = student_service.list_students(self.cfg, keyword="张")
        self.assertEqual([row["sno"] for row in rows], ["20240101"])
        rows = student_service.list_students(self.cfg, class_id=2)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["class_id"] == 2 for row in rows))

    def test_sort_by_name_descending(self):
        rows = student_service.list_students(self.cfg, order="name", descending=True)
        names = [row["name"] for row in rows]
        self.assertEqual(names, sorted(names, reverse=True))

    def test_create_and_read_back(self):
        new_id = student_service.create(self.cfg, {
            "sno": "20260301", "name": "林小满", "gender": "女",
            "phone": "13800000010", "class_id": 3,
        })
        student = student_service.get(self.cfg, new_id)
        self.assertEqual(student["sno"], "20260301")
        self.assertEqual(student["class_name"], "2025级数据科学与大数据技术1班")
        self.assertEqual(student["phone"], "13800000010")

    def test_create_without_optional_fields(self):
        new_id = student_service.create(self.cfg, {
            "sno": "20260302", "name": "未分班同学", "gender": "男",
        })
        student = student_service.get(self.cfg, new_id)
        self.assertIsNone(student["class_id"])
        self.assertEqual(student["class_name"], "（未分班）")
        self.assertIsNone(student["phone"])

    def test_duplicate_sno_is_conflict(self):
        with self.assertRaises(ConflictError) as ctx:
            student_service.create(self.cfg, {
                "sno": "20240101", "name": "重名", "gender": "男",
            })
        self.assertIn("学号已存在", str(ctx.exception))

    def test_unknown_class_is_conflict(self):
        with self.assertRaises(ConflictError):
            student_service.create(self.cfg, {
                "sno": "20260303", "name": "测试", "gender": "女", "class_id": 99,
            })

    def test_validation_errors(self):
        cases = [
            {"sno": "abc", "name": "测试", "gender": "男"},          # 学号非数字
            {"sno": "20260304", "name": "", "gender": "男"},          # 姓名为空
            {"sno": "20260305", "name": "测试", "gender": "未知"},    # 性别非法
            {"sno": "20260306", "name": "测试", "gender": "男",
             "phone": "12345"},                                        # 手机号格式
            {"sno": "20260307", "name": "测试", "gender": "男",
             "birthday": "2006/03/12"},                                # 日期格式
            {"sno": "20260308", "name": "测试", "gender": "男",
             "email": "not-an-email"},                                 # 邮箱格式
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    student_service.create(self.cfg, payload)

    def test_update_partial(self):
        student_service.update(self.cfg, 1, {"phone": "13900000000", "class_id": 2})
        student = student_service.get(self.cfg, 1)
        self.assertEqual(student["phone"], "13900000000")
        self.assertEqual(student["class_id"], 2)
        self.assertEqual(student["name"], "张伟")   # 没传的字段保持不变

    def test_update_unknown_student(self):
        with self.assertRaises(NotFoundError):
            student_service.update(self.cfg, 999, {"name": "不存在"})

    def test_delete_cascades_scores(self):
        before = len(score_service.list_scores(self.cfg, student_id=10))
        self.assertEqual(before, 2)
        student_service.delete(self.cfg, 10)
        self.assertEqual(score_service.list_scores(self.cfg, student_id=10), [])
        with self.assertRaises(NotFoundError):
            student_service.get(self.cfg, 10)

    def test_class_options(self):
        options = student_service.class_options(self.cfg)
        self.assertEqual(len(options), 3)
        self.assertEqual(options[0]["class_name"], "2025级数据科学与大数据技术1班")


class CourseServiceTest(unittest.TestCase):
    def setUp(self):
        self._db = TempDatabase()
        self.cfg = self._db.__enter__()

    def tearDown(self):
        self._db.__exit__(None, None, None)

    def test_create_and_uppercase_cno(self):
        course_id = course_service.create(self.cfg, {
            "cno": "c006", "title": "操作系统", "credit": 3.5, "hours": 56,
        })
        rows = course_service.list_courses(self.cfg, keyword="操作系统")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cno"], "C006")
        self.assertEqual(rows[0]["course_id"], course_id)

    def test_duplicate_cno(self):
        with self.assertRaises(ConflictError):
            course_service.create(self.cfg, {"cno": "C001", "title": "重复"})

    def test_invalid_credit(self):
        with self.assertRaises(ValidationError):
            course_service.create(self.cfg, {"cno": "C007", "title": "测试", "credit": 0})

    def test_delete_course_removes_scores(self):
        before = len(score_service.list_scores(self.cfg, course_id=5))
        self.assertEqual(before, 7)
        course_service.delete(self.cfg, 5)
        self.assertEqual(score_service.list_scores(self.cfg, course_id=5), [])

    def test_defaults(self):
        course_id = course_service.create(self.cfg, {"cno": "C008", "title": "默认值课程"})
        row = [r for r in course_service.list_courses(self.cfg) if r["course_id"] == course_id][0]
        self.assertEqual(row["credit"], 2.0)
        self.assertEqual(row["hours"], 32)


class ClassServiceTest(unittest.TestCase):
    def setUp(self):
        self._db = TempDatabase()
        self.cfg = self._db.__enter__()

    def tearDown(self):
        self._db.__exit__(None, None, None)

    def test_list_with_counts(self):
        rows = {row["class_name"]: row for row in class_service.list_classes(self.cfg)}
        self.assertEqual(rows["2024级计算机科学与技术1班"]["students"], 4)
        self.assertEqual(rows["2024级软件工程2班"]["students"], 3)

    def test_create_and_duplicate(self):
        class_id = class_service.create(self.cfg, {
            "class_name": "2026级人工智能1班", "major": "人工智能", "grade": 2026,
        })
        self.assertGreater(class_id, 3)
        with self.assertRaises(ConflictError):
            class_service.create(self.cfg, {
                "class_name": "2026级人工智能1班", "major": "人工智能", "grade": 2026,
            })

    def test_delete_keeps_students(self):
        class_service.delete(self.cfg, 3)
        rows = student_service.list_students(self.cfg, class_id=3)
        self.assertEqual(rows, [])
        students = [row for row in student_service.list_students(self.cfg)
                    if row["sno"].startswith("2025")]
        self.assertEqual(len(students), 3)
        self.assertTrue(all(row["class_id"] is None for row in students))

    def test_invalid_grade(self):
        with self.assertRaises(ValidationError):
            class_service.create(self.cfg, {
                "class_name": "坏年级班", "major": "测试", "grade": 1800,
            })


class ScoreServiceTest(unittest.TestCase):
    def setUp(self):
        self._db = TempDatabase()
        self.cfg = self._db.__enter__()

    def tearDown(self):
        self._db.__exit__(None, None, None)

    def test_list_all_and_missing(self):
        self.assertEqual(len(score_service.list_scores(self.cfg)), 41)
        missing = score_service.list_scores(self.cfg, only_missing=True)
        self.assertEqual(len(missing), 1)
        self.assertIsNone(missing[0]["score"])
        self.assertEqual(missing[0]["pass_state"], "未录入")

    def test_insert_then_update(self):
        action = score_service.save(self.cfg, 1, 5, "2026-2027-1", 88)
        self.assertEqual(action, "inserted")
        action = score_service.save(self.cfg, 1, 5, "2026-2027-1", 92)
        self.assertEqual(action, "updated")
        rows = score_service.list_scores(self.cfg, student_id=1, course_id=5, term="2026-2027-1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["score"], 92)

    def test_null_score_means_missing(self):
        score_service.save(self.cfg, 9, 5, "2024-2025-1", None)
        rows = score_service.list_scores(self.cfg, student_id=9, course_id=5,
                                         term="2024-2025-1")
        self.assertEqual(rows[0]["pass_state"], "未录入")

    def test_score_range(self):
        for bad in (-1, 101, "abc"):
            with self.subTest(score=bad):
                with self.assertRaises(ValidationError):
                    score_service.save(self.cfg, 1, 1, "2024-2025-1", bad)

    def test_term_format(self):
        with self.assertRaises(ValidationError):
            score_service.save(self.cfg, 1, 1, "2024/2025/1", 80)

    def test_unknown_student_is_conflict(self):
        with self.assertRaises(ConflictError):
            score_service.save(self.cfg, 999, 1, "2024-2025-1", 80)

    def test_delete_twice(self):
        score_service.delete(self.cfg, 1, 1, "2024-2025-1")
        with self.assertRaises(NotFoundError):
            score_service.delete(self.cfg, 1, 1, "2024-2025-1")

    def test_terms_and_transcript(self):
        self.assertEqual(score_service.terms(self.cfg)[0], "2025-2026-1")
        transcript = score_service.transcript(self.cfg, 3)
        self.assertEqual(len(transcript), 5)
        self.assertEqual([row["score"] for row in transcript if row["score"] < 60],
                         [51.0, 55.0, 58.0])


class ScoreEntryTest(unittest.TestCase):
    """按学号/课程号录入 + 按班级批量录入。"""

    def setUp(self):
        self._db = TempDatabase()
        self.cfg = self._db.__enter__()

    def tearDown(self):
        self._db.__exit__(None, None, None)

    def test_save_by_codes_updates(self):
        action = score_service.save_by_codes(self.cfg, "20240101", "C001", "2024-2025-1", 85)
        self.assertEqual(action, "updated")
        rows = score_service.list_scores(self.cfg, student_id=1, course_id=1,
                                         term="2024-2025-1")
        self.assertEqual(rows[0]["score"], 85.0)

    def test_save_by_codes_new_term(self):
        action = score_service.save_by_codes(self.cfg, "20240101", "c001", "2026-2027-1", 77)
        self.assertEqual(action, "inserted")
        rows = score_service.list_scores(self.cfg, student_id=1, course_id=1,
                                         term="2026-2027-1")
        self.assertEqual(rows[0]["score"], 77.0)

    def test_save_by_codes_unknown_codes(self):
        with self.assertRaises(NotFoundError):
            score_service.save_by_codes(self.cfg, "99999999", "C001", "2024-2025-1", 80)
        with self.assertRaises(NotFoundError):
            score_service.save_by_codes(self.cfg, "20240101", "C999", "2024-2025-1", 80)

    def test_roster(self):
        rows = score_service.roster(self.cfg, 1, 1, "2024-2025-1")
        self.assertEqual(len(rows), 4)
        scores = {row["sno"]: row["score"] for row in rows}
        self.assertEqual(scores["20240101"], 92.0)
        self.assertEqual(scores["20240103"], 55.0)
        self.assertTrue(all(row["score"] is not None for row in rows))

    def test_roster_shows_null_for_unrecorded(self):
        rows = score_service.roster(self.cfg, 3, 1, "2024-2025-1")
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["score"] is None for row in rows))

    def test_batch_save_mixes_saved_skipped_and_errors(self):
        rows = score_service.roster(self.cfg, 1, 1, "2024-2025-1")
        ids = [row["student_id"] for row in rows]
        result = score_service.batch_save(self.cfg, 1, "2024-2025-1", [
            {"student_id": ids[0], "score": "70"},
            {"student_id": ids[1], "score": ""},
            {"student_id": ids[2], "score": "abc"},
        ])
        self.assertEqual(result["saved"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(len(result["errors"]), 1)
        updated = score_service.list_scores(self.cfg, student_id=ids[0], course_id=1,
                                            term="2024-2025-1")
        self.assertEqual(updated[0]["score"], 70.0)

    def test_batch_save_all_rows(self):
        rows = score_service.roster(self.cfg, 3, 1, "2024-2025-1")
        result = score_service.batch_save(self.cfg, 1, "2024-2025-1", [
            {"student_id": row["student_id"], "score": 80} for row in rows
        ])
        self.assertEqual(result["saved"], 3)
        self.assertEqual(result["errors"], [])
        after = score_service.roster(self.cfg, 3, 1, "2024-2025-1")
        self.assertTrue(all(row["score"] == 80.0 for row in after))

    def test_batch_save_invalid_term(self):
        with self.assertRaises(ValidationError):
            score_service.batch_save(self.cfg, 1, "2024/2025", [])


if __name__ == "__main__":
    unittest.main()
