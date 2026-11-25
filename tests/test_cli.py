"""命令行界面：子命令解析、表格输出、错误退出码。"""

import csv
import unittest
from pathlib import Path

from tests.support import TempDatabase, run_cli, temp_dir


class CliTest(unittest.TestCase):
    def setUp(self):
        self._db = TempDatabase()
        self.cfg = self._db.__enter__()

    def tearDown(self):
        self._db.__exit__(None, None, None)

    def test_students_list(self):
        code, out, _ = run_cli(self.cfg, ["students", "list"])
        self.assertEqual(code, 0)
        self.assertIn("张伟", out)
        self.assertIn("共 10 条", out)
        self.assertIn("2024级计算机科学与技术1班", out)

    def test_students_search_and_sort(self):
        code, out, _ = run_cli(self.cfg, ["students", "list", "--keyword", "王"])
        self.assertEqual(code, 0)
        self.assertIn("王强", out)
        self.assertIn("共 1 条", out)

        code, out, _ = run_cli(self.cfg, ["students", "list", "--sort", "name", "--desc"])
        self.assertEqual(code, 0)
        self.assertIn("共 10 条", out)

    def test_students_add_edit_delete(self):
        code, out, _ = run_cli(self.cfg, [
            "students", "add", "--sno", "20260301", "--name", "林小满",
            "--gender", "女", "--class-id", "3",
        ])
        self.assertEqual(code, 0)
        self.assertIn("已新增学生", out)

        code, out, _ = run_cli(self.cfg, ["students", "list", "--keyword", "林小满"])
        self.assertIn("2025级数据科学与大数据技术1班", out)

        code, out, _ = run_cli(self.cfg, ["students", "edit", "11", "--phone", "13800000010"])
        self.assertEqual(code, 0)

        code, out, _ = run_cli(self.cfg, ["students", "show", "11"])
        self.assertEqual(code, 0)
        self.assertIn("林小满", out)

        code, out, _ = run_cli(self.cfg, ["students", "delete", "11"])
        self.assertEqual(code, 0)
        self.assertIn("已删除学生", out)

    def test_conflict_exit_code_and_message(self):
        code, _, err = run_cli(self.cfg, [
            "students", "add", "--sno", "20240101", "--name", "重名", "--gender", "男",
        ])
        self.assertEqual(code, 1)
        self.assertIn("学号已存在", err)

    def test_scores_list_and_set(self):
        code, out, _ = run_cli(self.cfg, ["scores", "list", "--student-id", "3"])
        self.assertEqual(code, 0)
        self.assertIn("王强", out)
        self.assertIn("不及格", out)

        code, out, _ = run_cli(self.cfg, [
            "scores", "set", "--student-id", "3", "--course-id", "1",
            "--term", "2024-2025-1", "--score", "65",
        ])
        self.assertEqual(code, 0)
        self.assertIn("已更新成绩", out)

        code, out, _ = run_cli(self.cfg, ["scores", "list", "--missing"])
        self.assertIn("吴磊", out)

    def test_stats(self):
        code, out, _ = run_cli(self.cfg, ["stats", "overview"])
        self.assertEqual(code, 0)
        self.assertIn("总平均分", out)
        self.assertIn("80.17", out)

        code, out, _ = run_cli(self.cfg, ["stats", "courses"])
        self.assertIn("79.14", out)
        self.assertIn("共 5 条", out)

        code, out, _ = run_cli(self.cfg, ["stats", "ranking"])
        self.assertIn("90.66", out)

        code, out, _ = run_cli(self.cfg, ["stats", "classes"])
        self.assertIn("2024级软件工程2班", out)

    def test_export_csv(self):
        target = Path(self.cfg.db_path).parent / "students.csv"
        code, out, _ = run_cli(self.cfg, ["export", "--what", "students", "--out", str(target)])
        self.assertEqual(code, 0)
        self.assertEqual(code, 0)
        with target.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0]["sno"], "20240101")
        self.assertEqual(rows[0]["name"], "张伟")

    def test_unknown_student_message(self):
        code, _, err = run_cli(self.cfg, ["students", "show", "999"])
        self.assertEqual(code, 1)
        self.assertIn("学生不存在", err)

    def test_students_paging(self):
        code, out, _ = run_cli(self.cfg, ["students", "list", "--page", "2", "--size", "4"])
        self.assertEqual(code, 0)
        self.assertIn("第 2 / 3 页", out)
        self.assertIn("共 10 条", out)

    def test_scores_paging(self):
        code, out, _ = run_cli(self.cfg, ["scores", "list", "--size", "20", "--page", "3"])
        self.assertEqual(code, 0)
        self.assertIn("第 3 / 3 页", out)
        self.assertIn("共 41 条", out)

    def test_import_students_csv(self):
        with temp_dir() as tmp:
            path = tmp / "s.csv"
            path.write_text("学号,姓名,性别,班级\n20260301,林小满,女,2024级软件工程2班\n",
                            encoding="utf-8-sig")
            code, out, _ = run_cli(self.cfg, ["students", "import", "--file", str(path)])
        self.assertEqual(code, 0)
        self.assertIn("成功导入 1 行", out)

    def test_import_reports_errors(self):
        with temp_dir() as tmp:
            path = tmp / "s.csv"
            path.write_text("学号,姓名,性别\n20240101,重名,男\n", encoding="utf-8-sig")
            code, out, _ = run_cli(self.cfg, ["students", "import", "--file", str(path)])
        self.assertEqual(code, 1)
        self.assertIn("第 2 行", out)
        self.assertIn("学号已存在", out)

    def test_transcript_export(self):
        with temp_dir() as tmp:
            target = tmp / "t.csv"
            code, out, _ = run_cli(self.cfg, ["students", "transcript", "3", "--out", str(target)])
            self.assertEqual(code, 0)
            self.assertTrue(target.exists())
            with target.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(len(rows), 6)

            html = tmp / "t.html"
            code, _, _ = run_cli(self.cfg, ["students", "transcript", "3", "--out", str(html)])
            self.assertEqual(code, 0)
            self.assertIn("学生成绩单", html.read_text(encoding="utf-8"))

    def test_template_command(self):
        with temp_dir() as tmp:
            target = tmp / "模板.csv"
            code, out, _ = run_cli(self.cfg, ["students", "template", "--out", str(target)])
            self.assertEqual(code, 0)
            self.assertTrue(target.exists())
            self.assertIn("学号", target.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
