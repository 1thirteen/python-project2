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
                    transcript = TranscriptWindow(tab, cfg, 3)
                    self.assertEqual(len(transcript.winfo_children()), 2)
                finally:
                    if transcript is not None:
                        transcript.destroy()
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
