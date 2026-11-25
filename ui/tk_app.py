"""Tkinter 图形界面：学生 / 班级 / 课程 / 成绩 / 统计 五个页签。"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from common.errors import AppError
from service import classes as class_service
from service import courses as course_service
from service import reports
from service import scores as score_service
from service import students as student_service
from store import connection

PAD = 8
FAIL_COLOR = "#b91c1c"
MISSING_COLOR = "#b45309"


class DataTable(ttk.Frame):
    """Treeview + 滚动条 + 表头排序。"""

    def __init__(self, master, columns, on_sort=None, on_activate=None):
        super().__init__(master)
        self.columns = list(columns)
        self._on_sort = on_sort
        self.tree = ttk.Treeview(
            self, columns=[c[0] for c in self.columns], show="headings", selectmode="browse"
        )
        for key, title, width, anchor in self.columns:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=50, anchor=anchor, stretch=True)
        self.tree.tag_configure("fail", foreground=FAIL_COLOR)
        self.tree.tag_configure("missing", foreground=MISSING_COLOR)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        bar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        if on_sort is not None:
            for key, _title, _width, _anchor in self.columns:
                self.tree.heading(key, command=lambda k=key: on_sort(k))
        if on_activate is not None:
            self.tree.bind("<Double-1>", lambda _event: on_activate())

    def fill(self, rows, id_of, values_of, tag_of=None) -> None:
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            tag = tag_of(row) if tag_of else ""
            self.tree.insert(
                "", "end", iid=str(id_of(row)), values=values_of(row),
                tags=(tag,) if tag else (),
            )

    def mark_sorted(self, field: str | None, descending: bool) -> None:
        for key, title, _width, _anchor in self.columns:
            arrow = ""
            if key == field:
                arrow = " ▼" if descending else " ▲"
            self.tree.heading(key, text=title + arrow)

    def selected_id(self):
        selection = self.tree.selection()
        return int(selection[0]) if selection else None


class FormDialog(tk.Toplevel):
    """通用表单弹窗：字段由 (key, 标签, 类型, 选项) 描述。"""

    def __init__(self, master, title, fields, on_submit, values=None, readonly=()):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self._on_submit = on_submit
        self._widgets = {}
        values = values or {}

        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)
        for row, (key, label, kind, options) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="e", pady=4, padx=(0, 8))
            if kind == "combo":
                pairs = list(options)
                widget = ttk.Combobox(
                    frame, state="readonly", width=28,
                    values=[text for _value, text in pairs],
                )
                widget._pairs = pairs  # type: ignore[attr-defined]
                current = values.get(key)
                for value, text in pairs:
                    if str(value) == str(current):
                        widget.set(text)
                        break
                else:
                    if pairs:
                        widget.current(0)
            else:
                widget = ttk.Entry(frame, width=30)
                widget.insert(0, "" if values.get(key) is None else str(values.get(key)))
            widget.grid(row=row, column=1, sticky="we", pady=4)
            if key in readonly:
                widget.configure(state="disabled")
            self._widgets[key] = widget

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(fields), column=0, columnspan=2, pady=(12, 0), sticky="e")
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="保存", command=self._submit).pack(side="right")

        self.bind("<Return>", lambda _event: self._submit())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()
        first = next(iter(self._widgets.values()), None)
        if first is not None:
            first.focus_set()
        self.update_idletasks()
        self._center(master)

    def _center(self, master) -> None:
        width, height = self.winfo_width(), self.winfo_height()
        x = master.winfo_rootx() + (master.winfo_width() - width) // 2
        y = master.winfo_rooty() + (master.winfo_height() - height) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def collect(self) -> dict:
        data = {}
        for key, widget in self._widgets.items():
            if isinstance(widget, ttk.Combobox):
                pairs = getattr(widget, "_pairs", [])
                index = widget.current()
                data[key] = pairs[index][0] if 0 <= index < len(pairs) else ""
            else:
                data[key] = widget.get().strip()
        return data

    def _submit(self) -> None:
        try:
            self._on_submit(self.collect())
        except AppError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self)
        else:
            self.destroy()


class BaseTab(ttk.Frame):
    """页签基类：统一状态栏、异常提示、排序状态。"""

    def __init__(self, master, app):
        super().__init__(master, padding=PAD)
        self.app = app
        self.cfg = app.cfg
        self.order = None
        self.desc = False
        self.table = None

    def on_sort(self, field: str) -> None:
        if self.order == field:
            self.desc = not self.desc
        else:
            self.order, self.desc = field, False
        self.reload()

    def refresh_options(self) -> None:
        """子类覆盖：下拉框数据变了以后重建。"""

    def reload(self) -> None:
        """子类覆盖：重新查询并填表。"""

    def guarded(self, func, *args) -> None:
        """统一把业务异常弹成对话框。"""
        try:
            func(*args)
        except AppError as exc:
            messagebox.showerror("操作失败", str(exc), parent=self)
        else:
            self.app.notify_changed()

    def ask_delete(self, message: str) -> bool:
        return messagebox.askyesno("确认删除", message, parent=self)


class StudentsTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.order = "sno"
        self._class_map = {"全部": None}

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, PAD))
        ttk.Label(bar, text="搜索").pack(side="left")
        self.keyword = ttk.Entry(bar, width=22)
        self.keyword.pack(side="left", padx=(6, 12))
        self.keyword.bind("<Return>", lambda _event: self.reload())
        ttk.Label(bar, text="班级").pack(side="left")
        self.class_box = ttk.Combobox(bar, state="readonly", width=26)
        self.class_box.pack(side="left", padx=(6, 12))
        self.class_box.bind("<<ComboboxSelected>>", lambda _event: self.reload())
        ttk.Button(bar, text="查询", command=self.reload).pack(side="left")
        ttk.Button(bar, text="重置", command=self.reset).pack(side="left", padx=(6, 0))

        buttons = ttk.Frame(self)
        buttons.pack(side="bottom", fill="x", pady=(PAD, 0))
        ttk.Button(buttons, text="新增学生", command=self.add).pack(side="left")
        ttk.Button(buttons, text="编辑", command=self.edit).pack(side="left", padx=6)
        ttk.Button(buttons, text="删除", command=self.delete).pack(side="left")
        ttk.Button(buttons, text="成绩单", command=self.transcript).pack(side="left", padx=6)
        self.count_label = ttk.Label(buttons, text="")
        self.count_label.pack(side="right")

        self.table = DataTable(
            self,
            [
                ("sno", "学号", 100, "w"),
                ("name", "姓名", 90, "w"),
                ("gender", "性别", 50, "center"),
                ("class_name", "班级", 240, "w"),
                ("phone", "电话", 110, "w"),
                ("enroll_date", "入学日期", 100, "center"),
            ],
            on_sort=self.on_sort,
            on_activate=self.edit,
        )
        self.table.pack(fill="both", expand=True)
        self.refresh_options()
        self.reload()

    def refresh_options(self):
        options = student_service.class_options(self.cfg)
        self._class_map = {"全部": None, **{row["class_name"]: row["class_id"] for row in options}}
        current = self.class_box.get() or "全部"
        self.class_box.configure(values=list(self._class_map))
        self.class_box.set(current if current in self._class_map else "全部")

    def reload(self):
        try:
            rows = student_service.list_students(
                self.cfg,
                keyword=self.keyword.get().strip(),
                class_id=self._class_map.get(self.class_box.get() or "全部"),
                order=self.order or "sno",
                descending=self.desc,
            )
        except AppError as exc:
            messagebox.showerror("查询失败", str(exc), parent=self)
            return
        self.table.fill(
            rows,
            id_of=lambda r: r["student_id"],
            values_of=lambda r: (
                r["sno"], r["name"], r["gender"], r["class_name"], r["phone"] or "",
                r["enroll_date"],
            ),
        )
        self.table.mark_sorted(self.order, self.desc)
        self.count_label.configure(text=f"共 {len(rows)} 名学生")
        self.app.set_status(f"学生 共 {len(rows)} 条")

    def reset(self):
        self.keyword.delete(0, "end")
        self.class_box.set("全部")
        self.reload()

    def _dialog(self, student=None):
        options = [("", "（未分班）")] + [
            (str(row["class_id"]), row["class_name"])
            for row in student_service.class_options(self.cfg)
        ]
        fields = [
            ("sno", "学号", "text", None),
            ("name", "姓名", "text", None),
            ("gender", "性别", "combo", [("男", "男"), ("女", "女")]),
            ("birthday", "出生日期", "text", None),
            ("phone", "电话", "text", None),
            ("email", "邮箱", "text", None),
            ("class_id", "班级", "combo", options),
        ]
        values = dict(student) if student else {"gender": "男", "class_id": ""}
        if values.get("class_id") is None:
            values["class_id"] = ""
        if student:
            def submit(data):
                student_service.update(self.cfg, student["student_id"], data)
        else:
            def submit(data):
                student_service.create(self.cfg, data)
        return FormDialog(self, "编辑学生" if student else "新增学生", fields,
                          lambda data: self.guarded(submit, data), values)

    def add(self):
        self._dialog()

    def edit(self):
        student_id = self.table.selected_id()
        if student_id is None:
            messagebox.showinfo("提示", "请先选中一名学生", parent=self)
            return
        try:
            student = student_service.get(self.cfg, student_id)
        except AppError as exc:
            messagebox.showerror("读取失败", str(exc), parent=self)
            return
        return self._dialog(student)

    def delete(self):
        student_id = self.table.selected_id()
        if student_id is None:
            messagebox.showinfo("提示", "请先选中一名学生", parent=self)
            return
        if not self.ask_delete("删除该学生？他的成绩会一并删除。"):
            return
        self.guarded(student_service.delete, self.cfg, student_id)

    def transcript(self):
        student_id = self.table.selected_id()
        if student_id is None:
            messagebox.showinfo("提示", "请先选中一名学生", parent=self)
            return
        try:
            TranscriptWindow(self, self.cfg, student_id)
        except AppError as exc:
            messagebox.showerror("读取失败", str(exc), parent=self)


class TranscriptWindow(tk.Toplevel):
    """一名学生的成绩单。"""

    def __init__(self, master, cfg, student_id):
        super().__init__(master)
        student = student_service.get(cfg, student_id)
        rows = score_service.transcript(cfg, student_id)
        self.title(f"成绩单 · {student['name']}")
        self.transient(master)
        self.geometry("640x420")

        head = ttk.Frame(self, padding=(12, 10))
        head.pack(fill="x")
        ttk.Label(head, text=f"{student['sno']}  {student['name']}",
                  font=("Microsoft YaHei UI", 12, "bold")).pack(side="left")
        ttk.Label(head, text=student["class_name"]).pack(side="left", padx=12)

        credits = sum(row["credit"] or 0 for row in rows if row["score"] is not None)
        graded = [row for row in rows if row["score"] is not None]
        weighted = (
            sum(row["score"] * row["credit"] for row in graded) / credits if credits else None
        )
        ttk.Label(
            head,
            text=f"已出分 {len(graded)} 门 / {credits:g} 学分"
                 + (f"　加权平均 {weighted:.2f}" if weighted is not None else ""),
        ).pack(side="right")

        table = DataTable(
            self,
            [
                ("course", "课程", 160, "w"),
                ("term", "学期", 110, "center"),
                ("credit", "学分", 60, "center"),
                ("score", "成绩", 60, "center"),
                ("pass_state", "状态", 70, "center"),
            ],
        )
        table.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        table.fill(
            rows,
            id_of=lambda r: f"{r['course_id']}",
            values_of=lambda r: (
                r["course"], r["term"], f"{r['credit']:g}",
                "" if r["score"] is None else f"{r['score']:g}",
                r["pass_state"],
            ),
            tag_of=lambda r: "missing" if r["score"] is None else (
                "fail" if r["score"] < 60 else ""
            ),
        )


class ClassesTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.order = "grade"
        self.desc = True
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, PAD))
        ttk.Label(bar, text="搜索").pack(side="left")
        self.keyword = ttk.Entry(bar, width=24)
        self.keyword.pack(side="left", padx=(6, 12))
        self.keyword.bind("<Return>", lambda _event: self.reload())
        ttk.Button(bar, text="查询", command=self.reload).pack(side="left")

        buttons = ttk.Frame(self)
        buttons.pack(side="bottom", fill="x", pady=(PAD, 0))
        ttk.Button(buttons, text="新增班级", command=self.add).pack(side="left")
        ttk.Button(buttons, text="编辑", command=self.edit).pack(side="left", padx=6)
        ttk.Button(buttons, text="删除", command=self.delete).pack(side="left")
        self.count_label = ttk.Label(buttons, text="")
        self.count_label.pack(side="right")

        self.table = DataTable(
            self,
            [
                ("class_name", "班级", 300, "w"),
                ("major", "专业", 200, "w"),
                ("grade", "年级", 70, "center"),
                ("head_teacher", "班主任", 90, "center"),
                ("students", "人数", 60, "center"),
            ],
            on_sort=self.on_sort,
            on_activate=self.edit,
        )
        self.table.pack(fill="both", expand=True)
        self.reload()

    def reload(self):
        try:
            rows = class_service.list_classes(
                self.cfg, keyword=self.keyword.get().strip(),
                order=self.order or "grade", descending=self.desc,
            )
        except AppError as exc:
            messagebox.showerror("查询失败", str(exc), parent=self)
            return
        self.table.fill(
            rows,
            id_of=lambda r: r["class_id"],
            values_of=lambda r: (
                r["class_name"], r["major"], r["grade"], r["head_teacher"] or "",
                r["students"],
            ),
        )
        self.table.mark_sorted(self.order, self.desc)
        self.count_label.configure(text=f"共 {len(rows)} 个班级")
        self.app.set_status(f"班级 共 {len(rows)} 条")

    def _dialog(self, klass=None):
        fields = [
            ("class_name", "班级名称", "text", None),
            ("major", "专业", "text", None),
            ("grade", "年级", "text", None),
            ("head_teacher", "班主任", "text", None),
        ]
        values = dict(klass) if klass else {"grade": "2026"}
        fields[2] = ("grade", "年级", "text", None)
        if klass:
            def submit(data):
                class_service.update(self.cfg, klass["class_id"], data)
        else:
            def submit(data):
                class_service.create(self.cfg, data)
        return FormDialog(self, "编辑班级" if klass else "新增班级", fields,
                          lambda data: self.guarded(submit, data), values)

    def add(self):
        self._dialog()

    def edit(self):
        class_id = self.table.selected_id()
        if class_id is None:
            messagebox.showinfo("提示", "请先选中一个班级", parent=self)
            return
        row = next((r for r in class_service.list_classes(self.cfg)
                    if r["class_id"] == class_id), None)
        return self._dialog(row)

    def delete(self):
        class_id = self.table.selected_id()
        if class_id is None:
            messagebox.showinfo("提示", "请先选中一个班级", parent=self)
            return
        if not self.ask_delete("删除该班级？班内学生会变成「未分班」，不会被删除。"):
            return
        self.guarded(class_service.delete, self.cfg, class_id)


class CoursesTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.order = "cno"
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, PAD))
        ttk.Label(bar, text="搜索").pack(side="left")
        self.keyword = ttk.Entry(bar, width=24)
        self.keyword.pack(side="left", padx=(6, 12))
        self.keyword.bind("<Return>", lambda _event: self.reload())
        ttk.Button(bar, text="查询", command=self.reload).pack(side="left")

        buttons = ttk.Frame(self)
        buttons.pack(side="bottom", fill="x", pady=(PAD, 0))
        ttk.Button(buttons, text="新增课程", command=self.add).pack(side="left")
        ttk.Button(buttons, text="编辑", command=self.edit).pack(side="left", padx=6)
        ttk.Button(buttons, text="删除", command=self.delete).pack(side="left")
        self.count_label = ttk.Label(buttons, text="")
        self.count_label.pack(side="right")

        self.table = DataTable(
            self,
            [
                ("cno", "课程号", 80, "center"),
                ("title", "课程名", 220, "w"),
                ("credit", "学分", 60, "center"),
                ("hours", "学时", 60, "center"),
                ("teacher", "任课教师", 100, "center"),
                ("records", "成绩条数", 80, "center"),
            ],
            on_sort=self.on_sort,
            on_activate=self.edit,
        )
        self.table.pack(fill="both", expand=True)
        self.reload()

    def reload(self):
        try:
            rows = course_service.list_courses(
                self.cfg, keyword=self.keyword.get().strip(),
                order=self.order or "cno", descending=self.desc,
            )
        except AppError as exc:
            messagebox.showerror("查询失败", str(exc), parent=self)
            return
        self.table.fill(
            rows,
            id_of=lambda r: r["course_id"],
            values_of=lambda r: (
                r["cno"], r["title"], f"{r['credit']:g}", r["hours"],
                r["teacher"] or "", r["records"],
            ),
        )
        self.table.mark_sorted(self.order, self.desc)
        self.count_label.configure(text=f"共 {len(rows)} 门课程")
        self.app.set_status(f"课程 共 {len(rows)} 条")

    def _dialog(self, course=None):
        fields = [
            ("cno", "课程号", "text", None),
            ("title", "课程名称", "text", None),
            ("credit", "学分", "text", None),
            ("hours", "学时", "text", None),
            ("teacher", "任课教师", "text", None),
        ]
        values = dict(course) if course else {"credit": "2.0", "hours": "32"}
        if course:
            def submit(data):
                course_service.update(self.cfg, course["course_id"], data)
        else:
            def submit(data):
                course_service.create(self.cfg, data)
        return FormDialog(self, "编辑课程" if course else "新增课程", fields,
                          lambda data: self.guarded(submit, data), values)

    def add(self):
        self._dialog()

    def edit(self):
        course_id = self.table.selected_id()
        if course_id is None:
            messagebox.showinfo("提示", "请先选中一门课程", parent=self)
            return
        row = next((r for r in course_service.list_courses(self.cfg)
                    if r["course_id"] == course_id), None)
        return self._dialog(row)

    def delete(self):
        course_id = self.table.selected_id()
        if course_id is None:
            messagebox.showinfo("提示", "请先选中一门课程", parent=self)
            return
        if not self.ask_delete("删除该课程？相关成绩会被级联删除。"):
            return
        self.guarded(course_service.delete, self.cfg, course_id)


class ScoresTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.order = "sno"
        self._students = {}
        self._courses = {}

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, PAD))
        ttk.Label(bar, text="学生").pack(side="left")
        self.student_box = ttk.Combobox(bar, state="readonly", width=22)
        self.student_box.pack(side="left", padx=(4, 10))
        self.student_box.bind("<<ComboboxSelected>>", lambda _event: self.reload())
        ttk.Label(bar, text="课程").pack(side="left")
        self.course_box = ttk.Combobox(bar, state="readonly", width=18)
        self.course_box.pack(side="left", padx=(4, 10))
        self.course_box.bind("<<ComboboxSelected>>", lambda _event: self.reload())
        ttk.Label(bar, text="学期").pack(side="left")
        self.term_box = ttk.Combobox(bar, state="readonly", width=14)
        self.term_box.pack(side="left", padx=(4, 10))
        self.term_box.bind("<<ComboboxSelected>>", lambda _event: self.reload())
        self.missing = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="只看未录入", variable=self.missing,
                        command=self.reload).pack(side="left", padx=(0, 10))
        ttk.Button(bar, text="刷新", command=self.reload).pack(side="left")

        buttons = ttk.Frame(self)
        buttons.pack(side="bottom", fill="x", pady=(PAD, 0))
        ttk.Button(buttons, text="录入 / 修改", command=self.edit).pack(side="left")
        ttk.Button(buttons, text="删除", command=self.delete).pack(side="left", padx=6)
        self.count_label = ttk.Label(buttons, text="")
        self.count_label.pack(side="right")

        self.table = DataTable(
            self,
            [
                ("sno", "学号", 100, "w"),
                ("name", "姓名", 80, "w"),
                ("course", "课程", 170, "w"),
                ("term", "学期", 110, "center"),
                ("score", "成绩", 60, "center"),
                ("pass_state", "状态", 70, "center"),
            ],
            on_sort=self.on_sort,
            on_activate=self.edit,
        )
        self.table.pack(fill="both", expand=True)
        self.refresh_options()
        self.reload()

    def refresh_options(self):
        students = student_service.list_students(self.cfg)
        self._students = {"全部学生": None, **{
            f"{row['sno']} {row['name']}": row["student_id"] for row in students
        }}
        courses = course_service.options(self.cfg)
        self._courses = {"全部课程": None, **{
            f"{row['cno']} {row['title']}": row["course_id"] for row in courses
        }}
        for box, mapping in ((self.student_box, self._students),
                             (self.course_box, self._courses)):
            default = "全部学生" if box is self.student_box else "全部课程"
            current = box.get() or default
            box.configure(values=list(mapping))
            box.set(current if current in mapping else default)
        terms = ["全部学期"] + score_service.terms(self.cfg)
        current = self.term_box.get() or "全部学期"
        self.term_box.configure(values=terms)
        self.term_box.set(current if current in terms else "全部学期")

    def reload(self):
        term = self.term_box.get()
        try:
            rows = score_service.list_scores(
                self.cfg,
                student_id=self._students.get(self.student_box.get() or "全部学生"),
                course_id=self._courses.get(self.course_box.get() or "全部课程"),
                term=None if term in ("", "全部学期") else term,
                only_missing=bool(self.missing.get()),
                order=self.order or "sno",
                descending=self.desc,
            )
        except AppError as exc:
            messagebox.showerror("查询失败", str(exc), parent=self)
            return
        self.table.fill(
            rows,
            id_of=lambda r: f"{r['student_id']}-{r['course_id']}-{r['term']}",
            values_of=lambda r: (
                r["sno"], r["name"], r["course"], r["term"],
                "" if r["score"] is None else f"{r['score']:g}", r["pass_state"],
            ),
            tag_of=lambda r: "missing" if r["score"] is None else (
                "fail" if r["score"] < 60 else ""
            ),
        )
        self._rows = rows
        self.table.mark_sorted(self.order, self.desc)
        self.count_label.configure(text=f"共 {len(rows)} 条成绩")
        self.app.set_status(f"成绩 共 {len(rows)} 条")

    def _dialog(self, row=None):
        student_pairs = [(str(value), label) for label, value in self._students.items()
                         if value is not None]
        course_pairs = [(str(value), label) for label, value in self._courses.items()
                        if value is not None]
        terms = score_service.terms(self.cfg)
        fields = [
            ("student_id", "学生", "combo", student_pairs),
            ("course_id", "课程", "combo", course_pairs),
            ("term", "学期", "text", None),
            ("score", "成绩", "text", None),
        ]
        values = {
            "student_id": row["student_id"] if row else "",
            "course_id": row["course_id"] if row else "",
            "term": row["term"] if row else (terms[0] if terms else "2024-2025-1"),
            "score": "" if row is None or row["score"] is None else f"{row['score']:g}",
        }
        if row:
            values["student_id"] = str(row["student_id"])
            values["course_id"] = str(row["course_id"])

        def submit(data):
            score_service.save(
                self.cfg, data["student_id"], data["course_id"], data["term"],
                data["score"],
            )

        return FormDialog(self, "录入 / 修改成绩", fields,
                          lambda data: self.guarded(submit, data), values,
                          readonly=("student_id", "course_id", "term") if row else ())

    def edit(self):
        row = self._current_row()
        if row is None:
            messagebox.showinfo("提示", "请先选中一条成绩", parent=self)
            return
        return self._dialog(row)

    def _current_row(self):
        selection = self.table.tree.selection()
        if not selection:
            return None
        key = selection[0]
        for row in self._rows:
            if f"{row['student_id']}-{row['course_id']}-{row['term']}" == key:
                return row
        return None

    def delete(self):
        row = self._current_row()
        if row is None:
            messagebox.showinfo("提示", "请先选中一条成绩", parent=self)
            return
        if not self.ask_delete(
            f"删除 {row['name']} 的《{row['course']}》{row['term']} 成绩？"
        ):
            return
        self.guarded(score_service.delete, self.cfg, row["student_id"],
                     row["course_id"], row["term"])


class StatsTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, PAD))
        ttk.Button(bar, text="刷新统计", command=self.reload).pack(side="left")
        self.summary = ttk.Label(bar, text="")
        self.summary.pack(side="left", padx=12)

        panes = ttk.Panedwindow(self, orient="vertical")
        panes.pack(fill="both", expand=True)

        top = ttk.Frame(panes)
        ttk.Label(top, text="按班级").pack(anchor="w")
        self.class_table = DataTable(top, [
            ("class_name", "班级", 260, "w"),
            ("major", "专业", 170, "w"),
            ("students", "人数", 60, "center"),
            ("graded", "已出分", 70, "center"),
            ("avg_score", "平均分", 80, "center"),
        ])
        self.class_table.pack(fill="both", expand=True)
        panes.add(top, weight=1)

        bottom = ttk.Frame(panes)
        left = ttk.Frame(bottom)
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="按课程").pack(anchor="w")
        self.course_table = DataTable(left, [
            ("course", "课程", 130, "w"),
            ("graded", "已出分", 65, "center"),
            ("avg_score", "平均", 65, "center"),
            ("max_score", "最高", 60, "center"),
            ("min_score", "最低", 60, "center"),
            ("pass_rate", "及格率%", 75, "center"),
        ])
        self.course_table.pack(fill="both", expand=True)

        right = ttk.Frame(bottom)
        right.pack(side="left", fill="both", expand=True, padx=(PAD, 0))
        ttk.Label(right, text="加权平均分排行").pack(anchor="w")
        self.rank_table = DataTable(right, [
            ("sno", "学号", 95, "w"),
            ("name", "姓名", 75, "w"),
            ("credits", "学分", 55, "center"),
            ("weighted_avg", "加权平均", 85, "center"),
        ])
        self.rank_table.pack(fill="both", expand=True)
        panes.add(bottom, weight=2)

        self.reload()

    def reload(self):
        try:
            info = reports.overview(self.cfg)
            classes = reports.class_summary(self.cfg)
            courses = reports.course_stats(self.cfg)
            ranking = reports.ranking(self.cfg)
        except AppError as exc:
            messagebox.showerror("统计失败", str(exc), parent=self)
            return
        self.summary.configure(
            text=f"班级 {info['classes']}　学生 {info['students']}　课程 {info['courses']}　"
                 f"成绩 {info['scores']}（未录入 {info['missing']}）　总平均 {info['avg_score']}"
        )
        self.class_table.fill(classes, lambda r: r["class_id"],
                             lambda r: (r["class_name"], r["major"], r["students"],
                                        r["graded"], r["avg_score"]))
        self.course_table.fill(courses, lambda r: r["cno"],
                              lambda r: (r["course"], r["graded"], r["avg_score"],
                                         r["max_score"], r["min_score"], r["pass_rate"]))
        self.rank_table.fill(ranking, lambda r: r["sno"],
                            lambda r: (r["sno"], r["name"], f"{r['credits']:g}",
                                       r["weighted_avg"]))
        self.app.set_status(f"统计　学生 {info['students']}　成绩 {info['scores']}")


class App(tk.Tk):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.title(f"{cfg.title} · 课题2 学生管理系统")
        self.geometry(f"{cfg.window[0]}x{cfg.window[1]}")
        self.minsize(1020, 640)
        try:
            self.tk.call("tk", "scaling", 1.2)
        except tk.TclError:
            pass

        style = ttk.Style(self)
        for theme in ("vista", "winnative", "clam"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break
        style.configure("Treeview", rowheight=26)

        self._build_menu()
        self.status = ttk.Label(self, text="就绪", anchor="w", padding=(10, 4))
        self.status.pack(side="bottom", fill="x")
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(10, 4))

        self.tabs = [
            ("学生", StudentsTab(self.notebook, self)),
            ("班级", ClassesTab(self.notebook, self)),
            ("课程", CoursesTab(self.notebook, self)),
            ("成绩", ScoresTab(self.notebook, self)),
            ("统计", StatsTab(self.notebook, self)),
        ]
        for title, tab in self.tabs:
            self.notebook.add(tab, text=f"  {title}  ")

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="刷新全部", command=self.notify_changed)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.destroy)
        menubar.add_cascade(label="文件", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于", command=self._about)
        menubar.add_cascade(label="帮助", menu=help_menu)
        self.configure(menu=menubar)

    def _about(self):
        messagebox.showinfo(
            "关于",
            f"{self.cfg.title} {self.cfg.version}\n"
            "课题2 · 数据库编程：基于 Python 的管理信息系统\n\n"
            "SQLite + Tkinter，仅使用标准库。",
            parent=self,
        )

    def _on_tab_changed(self, _event=None):
        index = self.notebook.index(self.notebook.select())
        _title, tab = self.tabs[index]
        tab.reload()

    def notify_changed(self):
        """任何一次增删改之后：刷新所有页签的下拉框与数据。"""
        for _title, tab in self.tabs:
            tab.refresh_options()
            tab.reload()

    def set_status(self, text: str) -> None:
        self.status.configure(text=text)


def _enable_dpi_awareness() -> None:
    """Windows 高分屏下让 Tk 使用物理像素，避免界面发虚、坐标对不上。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001 - 老系统没有 shcore，忽略即可
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


def run(cfg) -> int:
    _enable_dpi_awareness()
    if not Path(cfg.db_path).exists():
        connection.init_database(cfg.db_path, cfg.schema_path, cfg.seed_path)
    try:
        app = App(cfg)
    except tk.TclError as exc:
        print(f"无法启动图形界面：{exc}", file=sys.stderr)
        print("可以改用命令行：python main.py cli -h", file=sys.stderr)
        return 2
    app.mainloop()
    return 0
