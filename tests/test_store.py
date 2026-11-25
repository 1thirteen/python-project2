"""数据库层：表结构、约束、外键动作、触发器、视图。"""

import sqlite3
import time
import unittest

from store import connection
from tests.support import TempDatabase


class SchemaTest(unittest.TestCase):
    def setUp(self):
        self._db = TempDatabase()
        self.cfg = self._db.__enter__()

    def tearDown(self):
        self._db.__exit__(None, None, None)

    def test_tables_views_trigger_indexes(self):
        conn = connection.connect(self.cfg.db_path)
        try:
            kinds = {}
            for row in conn.execute("SELECT type, name FROM sqlite_master"):
                kinds.setdefault(row["type"], set()).add(row["name"])
            # AUTOINCREMENT 会额外创建内部表 sqlite_sequence
            self.assertIn("sqlite_sequence", kinds["table"])
            self.assertEqual(kinds["table"] - {"sqlite_sequence"},
                             {"classes", "students", "courses", "scores"})
            self.assertEqual(kinds["view"], {"v_student_score", "v_course_stats", "v_student_avg"})
            self.assertEqual(kinds["trigger"], {"trg_scores_touch"})
            self.assertEqual(len(kinds["index"]), 9)   # 4 个自动 + 5 个手工
        finally:
            conn.close()

    def test_seed_counts(self):
        conn = connection.connect(self.cfg.db_path)
        try:
            self.assertEqual(
                connection.counts(conn),
                {"classes": 3, "students": 10, "courses": 5, "scores": 41},
            )
        finally:
            conn.close()

    def test_foreign_keys_enabled_per_connection(self):
        conn = connection.connect(self.cfg.db_path)
        try:
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        finally:
            conn.close()

    def test_unique_sno_rejected(self):
        conn = connection.connect(self.cfg.db_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO students (sno, name, gender) VALUES ('20240101', '重名', '男')"
                )
        finally:
            conn.close()

    def test_gender_check_rejected(self):
        conn = connection.connect(self.cfg.db_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO students (sno, name, gender) VALUES ('20240999', '测试', '未知')"
                )
        finally:
            conn.close()

    def test_score_range_check(self):
        conn = connection.connect(self.cfg.db_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """UPDATE scores SET score = 120
                        WHERE student_id = 1 AND course_id = 1 AND term = '2024-2025-1'"""
                )
        finally:
            conn.close()

    def test_foreign_key_rejects_unknown_student(self):
        conn = connection.connect(self.cfg.db_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """INSERT INTO scores (student_id, course_id, term, score)
                       VALUES (999, 1, '2024-2025-1', 80)"""
                )
        finally:
            conn.close()

    def test_delete_student_cascades_scores(self):
        conn = connection.connect(self.cfg.db_path)
        try:
            conn.execute("DELETE FROM students WHERE student_id = 10")
            conn.commit()
            left = conn.execute(
                "SELECT COUNT(*) FROM scores WHERE student_id = 10"
            ).fetchone()[0]
            total = conn.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
            self.assertEqual(left, 0)
            self.assertEqual(total, 39)
        finally:
            conn.close()

    def test_delete_class_sets_null(self):
        conn = connection.connect(self.cfg.db_path)
        try:
            conn.execute("DELETE FROM classes WHERE class_id = 3")
            conn.commit()
            rows = conn.execute(
                "SELECT class_id FROM students WHERE sno IN ('20250301', '20250302')"
            ).fetchall()
            self.assertEqual([row[0] for row in rows], [None, None])
        finally:
            conn.close()

    def test_trigger_refreshes_updated_at(self):
        conn = connection.connect(self.cfg.db_path)
        try:
            sql = """SELECT updated_at FROM scores
                      WHERE student_id = 3 AND course_id = 1 AND term = '2024-2025-1'"""
            before = conn.execute(sql).fetchone()[0]
            time.sleep(1.05)
            conn.execute(
                """UPDATE scores SET score = 65
                    WHERE student_id = 3 AND course_id = 1 AND term = '2024-2025-1'"""
            )
            conn.commit()
            after = conn.execute(sql).fetchone()[0]
            self.assertNotEqual(before, after)
            self.assertGreater(after, before)
        finally:
            conn.close()

    def test_composite_primary_key_blocks_duplicate(self):
        conn = connection.connect(self.cfg.db_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """INSERT INTO scores (student_id, course_id, term, score)
                       VALUES (1, 1, '2024-2025-1', 100)"""
                )
        finally:
            conn.close()

    def test_course_stats_view(self):
        conn = connection.connect(self.cfg.db_path)
        try:
            rows = {row["cno"]: row for row in conn.execute("SELECT * FROM v_course_stats")}
            self.assertEqual(set(rows), {"C001", "C002", "C003", "C004", "C005"})
            self.assertEqual(rows["C001"]["graded"], 7)
            self.assertEqual(rows["C001"]["avg_score"], 79.14)
            self.assertEqual(rows["C002"]["graded"], 10)
            self.assertEqual(rows["C003"]["graded"], 9)  # 吴磊那条是 NULL，不计入
            self.assertEqual(rows["C005"]["avg_score"], 81.0)
        finally:
            conn.close()

    def test_student_avg_view(self):
        conn = connection.connect(self.cfg.db_path)
        try:
            rows = {row["sno"]: row for row in conn.execute("SELECT * FROM v_student_avg")}
            self.assertEqual(rows["20240101"]["weighted_avg"], 90.66)
            self.assertEqual(rows["20240104"]["weighted_avg"], 69.77)
            self.assertEqual(rows["20250303"]["graded"], 1)   # 另一门没出分
            self.assertEqual(rows["20250303"]["credits"], 3.0)
        finally:
            conn.close()

    def test_init_database_is_repeatable(self):
        info = connection.init_database(self.cfg.db_path, self.cfg.schema_path, self.cfg.seed_path)
        self.assertEqual(info["students"], 10)
        self.assertEqual(info["scores"], 41)


if __name__ == "__main__":
    unittest.main()
