"""图形界面冒烟测试：能建窗口、五个页签都有数据、弹窗能打开。"""

import unittest


class GuiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk

            from ui.tk_app import App  # noqa: F401

            probe = tk.Tk()
            probe.destroy()
        except Exception as exc:  # noqa: BLE001 - 无图形环境时跳过
            raise unittest.SkipTest(f"没有可用的图形环境：{exc}")

    def test_tabs_render_data(self):
        from ui.tk_app import App
        from tests.support import TempDatabase

        with TempDatabase() as cfg:
            app = App(cfg)
            try:
                names = [title for title, _tab in app.tabs]
                self.assertEqual(names, ["学生", "班级", "课程", "成绩", "统计"])

                students = app.tabs[0][1]
                self.assertEqual(len(students.table.tree.get_children()), 10)
                self.assertEqual(
                    students.table.tree.item("1")["values"][1], "张伟"
                )

                scores = app.tabs[3][1]
                self.assertEqual(len(scores.table.tree.get_children()), 41)

                stats = app.tabs[4][1]
                self.assertIn("总平均", stats.summary.cget("text"))

                for index in range(len(app.tabs)):
                    app.notebook.select(index)
                    app.update()
            finally:
                app.destroy()

    def test_form_dialog_opens(self):
        from ui.tk_app import App
        from tests.support import TempDatabase

        with TempDatabase() as cfg:
            app = App(cfg)
            try:
                tab = app.tabs[0][1]
                dialog = tab._dialog()
                try:
                    self.assertIn("sno", dialog._widgets)
                    self.assertIn("class_id", dialog._widgets)
                    self.assertEqual(dialog.title(), "新增学生")
                finally:
                    dialog.destroy()
                transcript = None
                try:
                    from ui.tk_app import TranscriptWindow

                    tab.table.tree.selection_set("3")
                    transcript = TranscriptWindow(tab, app, 3)
                    self.assertGreaterEqual(len(transcript.winfo_children()), 3)
                finally:
                    if transcript is not None:
                        transcript.destroy()
            finally:
                app.destroy()

    def test_theme_toggle(self):
        from ui import theme as theme_mod
        from ui.tk_app import App
        from tests.support import TempDatabase

        with TempDatabase() as cfg:
            app = App(cfg)
            try:
                self.assertEqual(app.theme.mode, "light")
                app.set_theme("dark")
                self.assertEqual(app.theme.mode, "dark")
                self.assertEqual(app.cget("bg"), theme_mod.DARK["bg"])
                self.assertEqual(
                    str(app.tabs[0][1].table.tree.tag_configure("odd", "background")),
                    theme_mod.DARK["stripe"],
                )
                app.set_theme("light")
                self.assertEqual(app.theme.mode, "light")
            finally:
                app.destroy()

    def test_pager_controls_pages(self):
        from ui.tk_app import App
        from tests.support import TempDatabase

        with TempDatabase() as cfg:
            app = App(cfg)
            try:
                students = app.tabs[0][1]
                self.assertEqual(len(students.table.tree.get_children()), 10)
                self.assertIn("1/1", students.pager.info.cget("text"))

                students.goto(1, 4)
                self.assertEqual(students.pages, 3)
                self.assertEqual(len(students.table.tree.get_children()), 4)
                self.assertIn("1/3", students.pager.info.cget("text"))

                students.pager._next()
                self.assertEqual(students.page_no, 2)
                self.assertIn("2/3", students.pager.info.cget("text"))
            finally:
                app.destroy()

    def test_batch_dialog_loads_roster(self):
        from ui.tk_app import App, BatchScoreDialog
        from tests.support import TempDatabase

        with TempDatabase() as cfg:
            app = App(cfg)
            dialog = None
            try:
                dialog = BatchScoreDialog(app, app, lambda: None)
                dialog.class_box.set("2024级计算机科学与技术1班")
                dialog.course_box.set("C001 高等数学")
                dialog.term_entry.delete(0, "end")
                dialog.term_entry.insert(0, "2024-2025-1")
                dialog.load()
                self.assertEqual(len(dialog._entries), 4)
                self.assertEqual([entry.get() for _sid, entry in dialog._entries],
                                 ["92", "88", "55", "68"])
            finally:
                if dialog is not None:
                    dialog._close()
                app.destroy()


if __name__ == "__main__":
    unittest.main()
