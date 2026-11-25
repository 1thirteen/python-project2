"""Tkinter 图形界面：浅色/深色主题、分页、导入导出、批量录入。"""

from __future__ import annotations

import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from common import log
from common.errors import AppError
from service import classes as class_service
from service import courses as course_service
from service import exports
from service import imports as import_service
from service import reports
from service import scores as score_service
from service import students as student_service
from store import connection
from ui import theme as theme_mod

PAD = 8


# ------------------------------------------------------------------ 基础控件
class DataTable(ttk.Frame):
    """Treeview + 滚动条 + 表头排序 + 斑马纹 + 空状态。"""

    def __init__(self, master, columns, on_sort=None, on_activate=None,
                 placeholder="没有符合条件的记录"):
        super().__init__(master)
        self.columns = list(columns)
        self.placeholder = placeholder
        self.tree = ttk.Treeview(
            self, columns=[c[0] for c in self.columns], show="headings", selectmode="browse"
        )
        for key, title, width, anchor in self.columns:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=50, anchor=anchor, stretch=True)
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

        self._empty = ttk.Label(self, text=placeholder, style="Muted.TLabel", anchor="center")

    def apply_theme(self, theme) -> None:
        theme.tag_colors(self.tree)

    def fill(self, rows, id_of, values_of, tags_of=None) -> None:
        self.tree.delete(*self.tree.get_children())
        if not rows:
            self._empty.place(relx=0.5, rely=0.45, anchor="center")
            return
        self._empty.place_forget()
        for index, row in enumerate(rows):
            extra = tuple(tags_of(row)) if tags_of else ()
            self.tree.insert(
                "", "end", iid=str(id_of(row)), values=values_of(row),
                tags=("odd" if index % 2 else "even",) + extra,
            )

    def mark_sorted(self, field: str | None, descending: bool) -> None:
        for key, title, _width, _anchor in self.columns:
            arrow = ""
            if key == field:
                arrow = " ▼" if descending else " ▲"
            self.tree.heading(key, text=title + arrow)

    def selected_id(self):
        selection = self.tree.selection()
        return selection[0] if selection else None


class Pager(ttk.Frame):
    """上一页 / 下一页 + 每页条数。"""

    def __init__(self, master, size: int, sizes, on_change):
        super().__init__(master)
        self._on_change = on_change
        self._page, self._pages, self._total = 1, 1, 0

        self.prev = ttk.Button(self, text="上一页", width=7, command=self._prev)
        self.prev.pack(side="left")
        self.info = ttk.Label(self, text="", style="Muted.TLabel")
        self.info.pack(side="left", padx=8)
        self.next = ttk.Button(self, text="下一页", width=7, command=self._next)
        self.next.pack(side="left")

        ttk.Label(self, text="每页", style="Muted.TLabel").pack(side="left", padx=(12, 4))
        self.size_box = ttk.Combobox(
            self, state="readonly", width=4, values=[str(v) for v in sizes]
        )
        self.size_box.set(str(size))
        self.size_box.pack(side="left")
        self.size_box.bind("<<ComboboxSelected>>", self._size_changed)

    def _size(self) -> int:
        try:
            return max(1, int(self.size_box.get()))
        except (TypeError, ValueError):
            return 50

    def _prev(self):
        if self._page > 1:
            self._on_change(self._page - 1, self._size())

    def _next(self):
        if self._page < self._pages:
            self._on_change(self._page + 1, self._size())

    def _size_changed(self, _event=None):
        self._on_change(1, self._size())

    def update_state(self, total: int, page: int, pages: int, size: int | None = None) -> None:
        self._total, self._page, self._pages = total, page, pages
        if size is not None and self.size_box.get() != str(size):
            self.size_box.set(str(size))
        self.info.configure(text=f"第 {page}/{pages} 页 · {total} 条")
        self.prev.configure(state="normal" if page > 1 else "disabled")
        self.next.configure(state="normal" if page < pages else "disabled")


class FormDialog(tk.Toplevel):
    """通用表单弹窗：字段由 (key, 标签, 类型, 选项) 描述。"""

    def __init__(self, master, title, fields, on_submit, values=None, readonly=(),
                 subtitle=""):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self._on_submit = on_submit
        self._widgets = {}
        values = values or {}

        palette = getattr(master, "palette", None) or theme_mod.LIGHT
        self.configure(bg=palette["bg"])
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        row = 0
        if subtitle:
            ttk.Label(frame, text=subtitle, style="Muted.TLabel").grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(0, 10)
            )
            row += 1

        for key, label, kind, options in fields:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="e",
                                              pady=4, padx=(0, 10))
            if kind == "combo":
                pairs = list(options)
                widget = ttk.Combobox(
                    frame, state="readonly", width=30,
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
                widget = ttk.Entry(frame, width=32)
                widget.insert(0, "" if values.get(key) is None else str(values.get(key)))
            widget.grid(row=row, column=1, sticky="we", pady=4)
            if key in readonly:
                widget.configure(state="disabled")
            self._widgets[key] = widget
            row += 1

        buttons = ttk.Frame(frame)
        buttons.grid(row=row, column=0, columnspan=2, pady=(14, 0), sticky="e")
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="保存", style="Accent.TButton",
                   command=self._submit).pack(side="right")

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


class BatchScoreDialog(tk.Toplevel):
    """按班级批量录入：选班级 + 课程 + 学期，一次填完整班成绩。"""

    def __init__(self, master, app, on_done):
        super().__init__(master)
        self.app = app
        self.cfg = app.cfg
        self.on_done = on_done
        self.palette = app.theme.palette
        self._entries: list[tuple[int, ttk.Entry]] = []
        self.title("批量录入成绩")
        self.geometry("720x600")
        self.transient(master)
        self.configure(bg=self.palette["bg"])
        self.grab_set()

        head = ttk.Frame(self, padding=(14, 12, 14, 6))
        head.pack(fill="x")
        ttk.Label(head, text="班级").grid(row=0, column=0, sticky="e")
        self.class_box = ttk.Combobox(head, state="readonly", width=26)
        self.class_box.grid(row=0, column=1, sticky="w", padx=(4, 12))
        ttk.Label(head, text="课程").grid(row=0, column=2, sticky="e")
        self.course_box = ttk.Combobox(head, state="readonly", width=20)
        self.course_box.grid(row=0, column=3, sticky="w", padx=(4, 0))
        ttk.Label(head, text="学期").grid(row=1, column=0, sticky="e", pady=(8, 0))
        self.term_entry = ttk.Entry(head, width=14)
        self.term_entry.grid(row=1, column=1, sticky="w", padx=(4, 12), pady=(8, 0))
        ttk.Button(head, text="读取花名册", command=self.load).grid(
            row=1, column=2, columnspan=2, sticky="w", pady=(8, 0)
        )

        self._classes = {row["class_name"]: row["class_id"]
                         for row in student_service.class_options(self.cfg)}
        self.class_box.configure(values=list(self._classes))
        if self._classes:
            self.class_box.current(0)
        courses = course_service.options(self.cfg)
        self._courses = {f"{row['cno']} {row['title']}": row["course_id"] for row in courses}
        self.course_box.configure(values=list(self._courses))
        if self._courses:
            self.course_box.current(0)
        terms = score_service.terms(self.cfg)
        self.term_entry.insert(0, terms[0] if terms else "2024-2025-1")

        body = ttk.Frame(self, padding=(14, 0, 14, 0))
        body.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(body, highlightthickness=0, bg=self.palette["bg"])
        bar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.inner = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

        foot = ttk.Frame(self, padding=(14, 8, 14, 12))
        foot.pack(fill="x")
        self.summary = ttk.Label(foot, text="先选班级和课程，再点「读取花名册」",
                                 style="Muted.TLabel")
        self.summary.pack(side="left")
        ttk.Button(foot, text="取消", command=self._close).pack(side="right")
        ttk.Button(foot, text="保存", style="Accent.TButton",
                   command=self.save).pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self._close)

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _close(self):
        self.canvas.unbind_all("<MouseWheel>")
        self.grab_release()
        self.destroy()

    def load(self):
        class_name = self.class_box.get()
        course_name = self.course_box.get()
        if class_name not in self._classes or course_name not in self._courses:
            messagebox.showinfo("提示", "请选择班级和课程", parent=self)
            return
        try:
            rows = score_service.roster(
                self.cfg, self._classes[class_name], self._courses[course_name],
                self.term_entry.get().strip(),
            )
        except AppError as exc:
            messagebox.showerror("读取失败", str(exc), parent=self)
            return
        for child in self.inner.winfo_children():
            child.destroy()
        self._entries.clear()
        ttk.Label(self.inner, text="学号", style="Head.TLabel").grid(row=0, column=0,
                                                                    sticky="w", padx=6)
        ttk.Label(self.inner, text="姓名", style="Head.TLabel").grid(row=0, column=1,
                                                                    sticky="w", padx=6)
        ttk.Label(self.inner, text="成绩（留空表示暂不录入）", style="Head.TLabel").grid(
            row=0, column=2, sticky="w", padx=6
        )
        for index, row in enumerate(rows, start=1):
            ttk.Label(self.inner, text=row["sno"]).grid(row=index, column=0, sticky="w", padx=6)
            ttk.Label(self.inner, text=row["name"]).grid(row=index, column=1, sticky="w", padx=6)
            entry = ttk.Entry(self.inner, width=12)
            if row["score"] is not None:
                entry.insert(0, f"{row['score']:g}")
            entry.grid(row=index, column=2, sticky="w", padx=6, pady=2)
            self._entries.append((row["student_id"], entry))
        self.summary.configure(text=f"共 {len(rows)} 名学生，填好后点「保存」")

    def save(self):
        if not self._entries:
            messagebox.showinfo("提示", "请先读取花名册", parent=self)
            return
        course_name = self.course_box.get()
        try:
            result = score_service.batch_save(
                self.cfg, self._courses[course_name], self.term_entry.get().strip(),
                [{"student_id": sid, "score": entry.get()}
                 for sid, entry in self._entries],
            )
        except AppError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self)
            return
        message = f"成功保存 {result['saved']} 条，跳过 {result['skipped']} 条空值"
        if result["errors"]:
            detail = "\n".join(f"student_id={e['student_id']}：{e['message']}"
                               for e in result["errors"][:6])
            message += f"\n\n{len(result['errors'])} 条有问题：\n{detail}"
            messagebox.showwarning("部分保存", message, parent=self)
        else:
            messagebox.showinfo("保存完成", message, parent=self)
        self.on_done()
        self.load()


# ------------------------------------------------------------------ 页签基类
class BaseTab(ttk.Frame):
    ORDER = "sno"

    def __init__(self, master, app):
        super().__init__(master, padding=(PAD, PAD, PAD, 0))
        self.app = app
        self.cfg = app.cfg
        self.palette = app.theme.palette
        self.order = self.ORDER
        self.desc = False
        self.page_no = 1
        self.size = self.cfg.page_size
        self.total = 0
        self.pages = 1
        self.table: DataTable | None = None
        self.pager: Pager | None = None

    # 子类在底部放分页器
    def make_pager(self, parent) -> Pager:
        self.pager = Pager(parent, self.size, self.cfg.page_size_options, self.goto)
        return self.pager

    def goto(self, page: int, size: int) -> None:
        self.page_no, self.size = page, size
        self.reload()

    def on_sort(self, field: str) -> None:
        if self.order == field:
            self.desc = not self.desc
        else:
            self.order, self.desc = field, False
        self.page_no = 1
        self.reload()

    def apply_theme(self) -> None:
        self.palette = self.app.theme.palette
        if self.table is not None:
            self.table.apply_theme(self.app.theme)

    def refresh_options(self) -> None:
        """下拉框数据变了以后重建。"""

    def reload(self) -> None:
        """重新查询并填表。"""

    def guarded(self, func, *args) -> None:
        try:
            func(*args)
        except AppError as exc:
            messagebox.showerror("操作失败", str(exc), parent=self)
        else:
            self.app.notify_changed()

    def ask_delete(self, message: str) -> bool:
        return messagebox.askyesno("确认删除", message, parent=self)

    def require_selection(self, hint: str):
        selected = self.table.selected_id() if self.table else None
        if selected is None:
            messagebox.showinfo("提示", hint, parent=self)
        return selected

    def update_pager(self, result: dict) -> None:
        self.total, self.pages = result["total"], result["pages"]
        self.page_no = result["page"]
        if self.pager is not None:
            self.pager.update_state(self.total, self.page_no, self.pages, self.size)


# ------------------------------------------------------------------ 学生
class StudentsTab(BaseTab):
    ORDER = "sno"

    def __init__(self, master, app):
        super().__init__(master, app)
        self._class_map: dict[str, int | None] = {"全部": None}

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, PAD))
        ttk.Label(bar, text="搜索").pack(side="left")
        self.keyword = ttk.Entry(bar, width=22)
        self.keyword.pack(side="left", padx=(6, 12))
        self.keyword.bind("<Return>", lambda _event: self.search())
        ttk.Label(bar, text="班级").pack(side="left")
        self.class_box = ttk.Combobox(bar, state="readonly", width=26)
        self.class_box.pack(side="left", padx=(6, 12))
        self.class_box.bind("<<ComboboxSelected>>", lambda _event: self.search())
        ttk.Button(bar, text="查询", style="Accent.TButton",
                   command=self.search).pack(side="left")
        ttk.Button(bar, text="重置", command=self.reset).pack(side="left", padx=(6, 0))

        export = ttk.Menubutton(bar, text="导入导出")
        export_menu = tk.Menu(export, tearoff=0)
        export_menu.add_command(label="导入学生 CSV…", command=self.import_csv)
        export_menu.add_command(label="导出当前筛选 CSV…", command=self.export_csv)
        export_menu.add_separator()
        export_menu.add_command(label="保存导入模板…", command=self.save_template)
        export["menu"] = export_menu
        export.pack(side="right")

        bottom = ttk.Frame(self)
        bottom.pack(side="bottom", fill="x", pady=(PAD, 4))
        actions = ttk.Frame(bottom)
        actions.pack(fill="x")
        ttk.Button(actions, text="新增学生", style="Accent.TButton",
                   command=self.add).pack(side="left")
        ttk.Button(actions, text="编辑", command=self.edit).pack(side="left", padx=6)
        ttk.Button(actions, text="删除", command=self.delete).pack(side="left")
        ttk.Button(actions, text="成绩单", command=self.transcript).pack(side="left", padx=6)
        self.count_label = ttk.Label(actions, text="", style="Muted.TLabel")
        self.count_label.pack(side="left", padx=12)
        pager_row = ttk.Frame(bottom)
        pager_row.pack(fill="x", pady=(6, 0))
        self.make_pager(pager_row).pack(side="right")

        self.table = DataTable(
            self,
            [("sno", "学号", 100, "w"), ("name", "姓名", 90, "w"),
             ("gender", "性别", 50, "center"), ("class_name", "班级", 240, "w"),
             ("phone", "电话", 110, "w"), ("enroll_date", "入学日期", 100, "center")],
            on_sort=self.on_sort, on_activate=self.edit,
            placeholder="没有找到学生",
        )
        self.table.pack(fill="both", expand=True)
        self.table.apply_theme(app.theme)
        self.refresh_options()
        self.reload()

    def refresh_options(self):
        options = student_service.class_options(self.cfg)
        self._class_map = {"全部": None, **{row["class_name"]: row["class_id"] for row in options}}
        current = self.class_box.get() or "全部"
        self.class_box.configure(values=list(self._class_map))
        self.class_box.set(current if current in self._class_map else "全部")

    def search(self):
        self.page_no = 1
        self.reload()

    def reload(self):
        try:
            result = student_service.page(
                self.cfg, keyword=self.keyword.get().strip(),
                class_id=self._class_map.get(self.class_box.get() or "全部"),
                order=self.order or "sno", descending=self.desc,
                page=self.page_no, size=self.size,
            )
        except AppError as exc:
            messagebox.showerror("查询失败", str(exc), parent=self)
            return
        self.table.fill(
            result["rows"], id_of=lambda r: r["student_id"],
            values_of=lambda r: (r["sno"], r["name"], r["gender"], r["class_name"],
                                 r["phone"] or "", r["enroll_date"]),
        )
        self.table.mark_sorted(self.order, self.desc)
        self.update_pager(result)
        self.count_label.configure(text=f"共 {result['total']} 名学生")
        self.app.set_status(f"学生 {result['total']} 人")

    def reset(self):
        self.keyword.delete(0, "end")
        self.class_box.set("全部")
        self.search()

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
                          lambda data: self.guarded(submit, data), values,
                          subtitle="学号 4–20 位数字；班级可以留空（未分班）")

    def add(self):
        self._dialog()

    def edit(self):
        student_id = self.require_selection("请先选中一名学生")
        if student_id is None:
            return None
        try:
            student = student_service.get(self.cfg, int(student_id))
        except AppError as exc:
            messagebox.showerror("读取失败", str(exc), parent=self)
            return None
        return self._dialog(student)

    def delete(self):
        student_id = self.require_selection("请先选中一名学生")
        if student_id is None:
            return
        if not self.ask_delete("删除该学生？他的成绩会一并删除。"):
            return
        self.guarded(student_service.delete, self.cfg, int(student_id))

    def transcript(self):
        student_id = self.require_selection("请先选中一名学生")
        if student_id is None:
            return
        try:
            TranscriptWindow(self, self.app, int(student_id))
        except AppError as exc:
            messagebox.showerror("读取失败", str(exc), parent=self)

    # ---- CSV ----
    def import_csv(self):
        path = filedialog.askopenfilename(
            parent=self, title="选择学生 CSV",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            result = import_service.import_students(self.cfg, path)
        except AppError as exc:
            messagebox.showerror("导入失败", str(exc), parent=self)
            return
        except OSError as exc:
            messagebox.showerror("读取失败", str(exc), parent=self)
            return
        message = f"共 {result['total']} 行，成功导入 {result['inserted']} 行"
        if result["errors"]:
            detail = "\n".join(f"第 {line} 行：{text}" for line, text in result["errors"][:8])
            message += f"\n\n{len(result['errors'])} 行有问题：\n{detail}"
            messagebox.showwarning("部分导入", message, parent=self)
        else:
            messagebox.showinfo("导入完成", message, parent=self)
        self.app.notify_changed()

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="导出学生名册", defaultextension=".csv",
            initialfile="学生名册.csv", filetypes=[("CSV 文件", "*.csv")],
        )
        if not path:
            return
        try:
            target = exports.write_students_csv(self.cfg, path)
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc), parent=self)
            return
        messagebox.showinfo("导出完成", f"已写入 {target}", parent=self)

    def save_template(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="保存导入模板", defaultextension=".csv",
            initialfile="学生导入模板.csv", filetypes=[("CSV 文件", "*.csv")],
        )
        if not path:
            return
        import_service.write_template(path, "students")
        messagebox.showinfo("模板已保存", path, parent=self)


# ------------------------------------------------------------------ 班级
class ClassesTab(BaseTab):
    ORDER = "grade"

    def __init__(self, master, app):
        super().__init__(master, app)
        self.desc = True
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, PAD))
        ttk.Label(bar, text="搜索").pack(side="left")
        self.keyword = ttk.Entry(bar, width=24)
        self.keyword.pack(side="left", padx=(6, 12))
        self.keyword.bind("<Return>", lambda _event: self.reload())
        ttk.Button(bar, text="查询", style="Accent.TButton",
                   command=self.reload).pack(side="left")

        bottom = ttk.Frame(self)
        bottom.pack(side="bottom", fill="x", pady=(PAD, 4))
        ttk.Button(bottom, text="新增班级", style="Accent.TButton",
                   command=self.add).pack(side="left")
        ttk.Button(bottom, text="编辑", command=self.edit).pack(side="left", padx=6)
        ttk.Button(bottom, text="删除", command=self.delete).pack(side="left")
        self.count_label = ttk.Label(bottom, text="", style="Muted.TLabel")
        self.count_label.pack(side="left", padx=12)

        self.table = DataTable(
            self,
            [("class_name", "班级", 300, "w"), ("major", "专业", 200, "w"),
             ("grade", "年级", 70, "center"), ("head_teacher", "班主任", 90, "center"),
             ("students", "人数", 60, "center")],
            on_sort=self.on_sort, on_activate=self.edit,
            placeholder="还没有班级，点「新增班级」建一个",
        )
        self.table.pack(fill="both", expand=True)
        self.table.apply_theme(app.theme)
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
            rows, id_of=lambda r: r["class_id"],
            values_of=lambda r: (r["class_name"], r["major"], r["grade"],
                                 r["head_teacher"] or "", r["students"]),
        )
        self.table.mark_sorted(self.order, self.desc)
        self.count_label.configure(text=f"共 {len(rows)} 个班级")
        self.app.set_status(f"班级 {len(rows)} 个")

    def _dialog(self, klass=None):
        fields = [
            ("class_name", "班级名称", "text", None),
            ("major", "专业", "text", None),
            ("grade", "年级", "text", None),
            ("head_teacher", "班主任", "text", None),
        ]
        values = dict(klass) if klass else {"grade": "2026"}
        if klass:
            def submit(data):
                class_service.update(self.cfg, klass["class_id"], data)
        else:
            def submit(data):
                class_service.create(self.cfg, data)
        return FormDialog(self, "编辑班级" if klass else "新增班级", fields,
                          lambda data: self.guarded(submit, data), values)

    def add(self):
        return self._dialog()

    def edit(self):
        class_id = self.require_selection("请先选中一个班级")
        if class_id is None:
            return None
        row = next((r for r in class_service.list_classes(self.cfg)
                    if r["class_id"] == int(class_id)), None)
        return self._dialog(row)

    def delete(self):
        class_id = self.require_selection("请先选中一个班级")
        if class_id is None:
            return
        if not self.ask_delete("删除该班级？班内学生会变成「未分班」，不会被删除。"):
            return
        self.guarded(class_service.delete, self.cfg, int(class_id))


# ------------------------------------------------------------------ 课程
class CoursesTab(BaseTab):
    ORDER = "cno"

    def __init__(self, master, app):
        super().__init__(master, app)
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, PAD))
        ttk.Label(bar, text="搜索").pack(side="left")
        self.keyword = ttk.Entry(bar, width=24)
        self.keyword.pack(side="left", padx=(6, 12))
        self.keyword.bind("<Return>", lambda _event: self.reload())
        ttk.Button(bar, text="查询", style="Accent.TButton",
                   command=self.reload).pack(side="left")

        bottom = ttk.Frame(self)
        bottom.pack(side="bottom", fill="x", pady=(PAD, 4))
        ttk.Button(bottom, text="新增课程", style="Accent.TButton",
                   command=self.add).pack(side="left")
        ttk.Button(bottom, text="编辑", command=self.edit).pack(side="left", padx=6)
        ttk.Button(bottom, text="删除", command=self.delete).pack(side="left")
        self.count_label = ttk.Label(bottom, text="", style="Muted.TLabel")
        self.count_label.pack(side="left", padx=12)

        self.table = DataTable(
            self,
            [("cno", "课程号", 80, "center"), ("title", "课程名", 220, "w"),
             ("credit", "学分", 60, "center"), ("hours", "学时", 60, "center"),
             ("teacher", "任课教师", 100, "center"), ("records", "成绩条数", 80, "center")],
            on_sort=self.on_sort, on_activate=self.edit,
            placeholder="还没有课程，点「新增课程」建一门",
        )
        self.table.pack(fill="both", expand=True)
        self.table.apply_theme(app.theme)
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
            rows, id_of=lambda r: r["course_id"],
            values_of=lambda r: (r["cno"], r["title"], f"{r['credit']:g}",
                                 r["hours"], r["teacher"] or "", r["records"]),
        )
        self.table.mark_sorted(self.order, self.desc)
        self.count_label.configure(text=f"共 {len(rows)} 门课程")
        self.app.set_status(f"课程 {len(rows)} 门")

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
        return self._dialog()

    def edit(self):
        course_id = self.require_selection("请先选中一门课程")
        if course_id is None:
            return None
        row = next((r for r in course_service.list_courses(self.cfg)
                    if r["course_id"] == int(course_id)), None)
        return self._dialog(row)

    def delete(self):
        course_id = self.require_selection("请先选中一门课程")
        if course_id is None:
            return
        if not self.ask_delete("删除该课程？相关成绩会被级联删除。"):
            return
        self.guarded(course_service.delete, self.cfg, int(course_id))


# ------------------------------------------------------------------ 成绩
class ScoresTab(BaseTab):
    ORDER = "sno"

    def __init__(self, master, app):
        super().__init__(master, app)
        self._courses: dict[str, int | None] = {"全部课程": None}

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, PAD))
        ttk.Label(bar, text="学生").pack(side="left")
        self.keyword = ttk.Entry(bar, width=16)
        self.keyword.pack(side="left", padx=(4, 10))
        self.keyword.bind("<Return>", lambda _event: self.search())
        ttk.Label(bar, text="课程").pack(side="left")
        self.course_box = ttk.Combobox(bar, state="readonly", width=18)
        self.course_box.pack(side="left", padx=(4, 10))
        self.course_box.bind("<<ComboboxSelected>>", lambda _event: self.search())
        ttk.Label(bar, text="学期").pack(side="left")
        self.term_box = ttk.Combobox(bar, state="readonly", width=14)
        self.term_box.pack(side="left", padx=(4, 10))
        self.term_box.bind("<<ComboboxSelected>>", lambda _event: self.search())
        self.missing = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="只看未录入", variable=self.missing,
                        command=self.search).pack(side="left", padx=(0, 10))
        ttk.Button(bar, text="查询", style="Accent.TButton",
                   command=self.search).pack(side="left")

        export = ttk.Menubutton(bar, text="导入导出")
        export_menu = tk.Menu(export, tearoff=0)
        export_menu.add_command(label="导入成绩 CSV…", command=self.import_csv)
        export_menu.add_command(label="导出当前筛选 CSV…", command=self.export_csv)
        export["menu"] = export_menu
        export.pack(side="right")

        bottom = ttk.Frame(self)
        bottom.pack(side="bottom", fill="x", pady=(PAD, 4))
        actions = ttk.Frame(bottom)
        actions.pack(fill="x")
        ttk.Button(actions, text="录入 / 修改", style="Accent.TButton",
                   command=self.edit).pack(side="left")
        ttk.Button(actions, text="批量录入", command=self.batch_entry).pack(side="left", padx=6)
        ttk.Button(actions, text="删除", command=self.delete).pack(side="left")
        self.count_label = ttk.Label(actions, text="", style="Muted.TLabel")
        self.count_label.pack(side="left", padx=12)
        pager_row = ttk.Frame(bottom)
        pager_row.pack(fill="x", pady=(6, 0))
        self.make_pager(pager_row).pack(side="right")

        self.table = DataTable(
            self,
            [("sno", "学号", 100, "w"), ("name", "姓名", 80, "w"),
             ("course", "课程", 170, "w"), ("term", "学期", 110, "center"),
             ("score", "成绩", 60, "center"), ("pass_state", "状态", 70, "center")],
            on_sort=self.on_sort, on_activate=self.edit,
            placeholder="没有符合条件的成绩记录",
        )
        self.table.pack(fill="both", expand=True)
        self.table.apply_theme(app.theme)
        self._rows: list[dict] = []
        self.refresh_options()
        self.reload()

    def refresh_options(self):
        courses = course_service.options(self.cfg)
        self._courses = {"全部课程": None, **{
            f"{row['cno']} {row['title']}": row["course_id"] for row in courses
        }}
        current = self.course_box.get() or "全部课程"
        self.course_box.configure(values=list(self._courses))
        self.course_box.set(current if current in self._courses else "全部课程")
        terms = ["全部学期"] + score_service.terms(self.cfg)
        current = self.term_box.get() or "全部学期"
        self.term_box.configure(values=terms)
        self.term_box.set(current if current in terms else "全部学期")

    def search(self):
        self.page_no = 1
        self.reload()

    def reload(self):
        term = self.term_box.get()
        try:
            result = score_service.page(
                self.cfg,
                course_id=self._courses.get(self.course_box.get() or "全部课程"),
                term=None if term in ("", "全部学期") else term,
                keyword=self.keyword.get().strip(),
                only_missing=bool(self.missing.get()),
                order=self.order or "sno", descending=self.desc,
                page=self.page_no, size=self.size,
            )
        except AppError as exc:
            messagebox.showerror("查询失败", str(exc), parent=self)
            return
        self._rows = result["rows"]
        self.table.fill(
            self._rows,
            id_of=lambda r: f"{r['student_id']}-{r['course_id']}-{r['term']}",
            values_of=lambda r: (r["sno"], r["name"], r["course"], r["term"],
                                 "" if r["score"] is None else f"{r['score']:g}",
                                 r["pass_state"]),
            tags_of=lambda r: ("missing",) if r["score"] is None else (
                ("fail",) if r["score"] < 60 else ()),
        )
        self.table.mark_sorted(self.order, self.desc)
        self.update_pager(result)
        self.count_label.configure(text=f"共 {result['total']} 条成绩")
        self.app.set_status(f"成绩 {result['total']} 条")

    def _current_row(self):
        selected = self.table.selected_id()
        if selected is None:
            return None
        return next((row for row in self._rows
                     if f"{row['student_id']}-{row['course_id']}-{row['term']}" == selected),
                    None)

    def _dialog(self, row=None):
        course_pairs = [(row["cno"], f"{row['cno']} {row['title']}")
                        for row in course_service.options(self.cfg)]
        terms = score_service.terms(self.cfg)
        fields = [
            ("sno", "学号", "text", None),
            ("cno", "课程", "combo", course_pairs),
            ("term", "学期", "text", None),
            ("score", "成绩", "text", None),
        ]
        values = {
            "sno": row["sno"] if row else "",
            "cno": row["cno"] if row else (course_pairs[0][0] if course_pairs else ""),
            "term": row["term"] if row else (terms[0] if terms else "2024-2025-1"),
            "score": "" if row is None or row["score"] is None else f"{row['score']:g}",
        }

        def submit(data):
            score_service.save_by_codes(
                self.cfg, data["sno"], data["cno"], data["term"], data["score"]
            )

        return FormDialog(
            self, "录入 / 修改成绩", fields,
            lambda data: self.guarded(submit, data), values,
            readonly=("sno", "cno", "term") if row else (),
            subtitle="留空表示「未录入」；同一学生同一课程同一学期只有一条记录",
        )

    def edit(self):
        row = self._current_row()
        if row is None:
            messagebox.showinfo("提示", "请先选中一条成绩", parent=self)
            return None
        return self._dialog(row)

    def delete(self):
        row = self._current_row()
        if row is None:
            messagebox.showinfo("提示", "请先选中一条成绩", parent=self)
            return
        if not self.ask_delete(f"删除 {row['name']} 的《{row['course']}》{row['term']} 成绩？"):
            return
        self.guarded(score_service.delete, self.cfg, row["student_id"],
                     row["course_id"], row["term"])

    def batch_entry(self):
        BatchScoreDialog(self, self.app, self.app.notify_changed)

    def import_csv(self):
        path = filedialog.askopenfilename(
            parent=self, title="选择成绩 CSV",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            result = import_service.import_scores(self.cfg, path)
        except AppError as exc:
            messagebox.showerror("导入失败", str(exc), parent=self)
            return
        except OSError as exc:
            messagebox.showerror("读取失败", str(exc), parent=self)
            return
        message = f"共 {result['total']} 行，成功写入 {result['saved']} 行"
        if result["errors"]:
            detail = "\n".join(f"第 {line} 行：{text}" for line, text in result["errors"][:8])
            message += f"\n\n{len(result['errors'])} 行有问题：\n{detail}"
            messagebox.showwarning("部分导入", message, parent=self)
        else:
            messagebox.showinfo("导入完成", message, parent=self)
        self.app.notify_changed()

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="导出成绩", defaultextension=".csv",
            initialfile="成绩明细.csv", filetypes=[("CSV 文件", "*.csv")],
        )
        if not path:
            return
        term = self.term_box.get()
        try:
            target = exports.write_scores_csv(
                self.cfg, path,
                course_id=self._courses.get(self.course_box.get() or "全部课程"),
                term=None if term in ("", "全部学期") else term,
                keyword=self.keyword.get().strip(),
                only_missing=bool(self.missing.get()),
            )
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc), parent=self)
            return
        messagebox.showinfo("导出完成", f"已写入 {target}", parent=self)


# ------------------------------------------------------------------ 成绩单
class TranscriptWindow(tk.Toplevel):
    def __init__(self, master, app, student_id):
        super().__init__(master)
        self.cfg = app.cfg
        self.student_id = student_id
        self.palette = app.theme.palette
        summary = exports.transcript_summary(self.cfg, student_id)
        student = student_service.get(self.cfg, student_id)

        self.title(f"成绩单 · {student['name']}")
        self.transient(master)
        self.geometry("720x460")
        self.configure(bg=self.palette["bg"])

        head = ttk.Frame(self, padding=(14, 12, 14, 6))
        head.pack(fill="x")
        ttk.Label(head, text=f"{student['sno']}  {student['name']}",
                  style="Title.TLabel").pack(side="left")
        ttk.Label(head, text=student["class_name"], style="Muted.TLabel").pack(
            side="left", padx=12
        )
        weighted = "—" if summary["weighted"] is None else f"{summary['weighted']:.2f}"
        ttk.Label(
            head,
            text=f"已出分 {summary['graded']} 门 / {summary['credits']:g} 学分　"
                 f"加权平均 {weighted}",
            style="Muted.TLabel",
        ).pack(side="right")

        table = DataTable(
            self,
            [("course", "课程", 180, "w"), ("term", "学期", 110, "center"),
             ("credit", "学分", 60, "center"), ("score", "成绩", 60, "center"),
             ("pass_state", "状态", 70, "center")],
            placeholder="还没有成绩记录",
        )
        table.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        table.apply_theme(app.theme)
        table.fill(
            summary["rows"], id_of=lambda r: f"{r['course_id']}",
            values_of=lambda r: (r["course"], r["term"], f"{r['credit']:g}",
                                 "" if r["score"] is None else f"{r['score']:g}",
                                 r["pass_state"]),
            tags_of=lambda r: ("missing",) if r["score"] is None else (
                ("fail",) if r["score"] < 60 else ()),
        )

        foot = ttk.Frame(self, padding=(14, 0, 14, 12))
        foot.pack(fill="x")
        ttk.Button(foot, text="导出 CSV", command=self.export_csv).pack(side="left")
        ttk.Button(foot, text="打印 / 预览", style="Accent.TButton",
                   command=self.print_preview).pack(side="left", padx=8)
        ttk.Button(foot, text="关闭", command=self.destroy).pack(side="right")

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="导出成绩单", defaultextension=".csv",
            initialfile="成绩单.csv", filetypes=[("CSV 文件", "*.csv")],
        )
        if not path:
            return
        try:
            target = exports.write_transcript_csv(self.cfg, self.student_id, path)
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc), parent=self)
            return
        messagebox.showinfo("导出完成", f"已写入 {target}", parent=self)

    def print_preview(self):
        try:
            target = exports.write_transcript_html(
                self.cfg, self.student_id,
                Path(self.cfg.db_path).parent / f"成绩单-{self.student_id}.html",
            )
        except OSError as exc:
            messagebox.showerror("生成失败", str(exc), parent=self)
            return
        webbrowser.open(target.resolve().as_uri())


# ------------------------------------------------------------------ 统计
class StatsTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, PAD))
        ttk.Button(bar, text="刷新统计", style="Accent.TButton",
                   command=self.reload).pack(side="left")
        self.summary = ttk.Label(bar, text="", style="Muted.TLabel")
        self.summary.pack(side="left", padx=12)

        panes = ttk.Panedwindow(self, orient="vertical")
        panes.pack(fill="both", expand=True)

        top = ttk.Frame(panes)
        ttk.Label(top, text="按班级", style="Head.TLabel").pack(anchor="w")
        self.class_table = DataTable(top, [
            ("class_name", "班级", 260, "w"), ("major", "专业", 170, "w"),
            ("students", "人数", 60, "center"), ("graded", "已出分", 70, "center"),
            ("avg_score", "平均分", 80, "center")],
            placeholder="还没有班级")
        self.class_table.pack(fill="both", expand=True)
        self.class_table.apply_theme(app.theme)
        panes.add(top, weight=1)

        bottom = ttk.Frame(panes)
        left = ttk.Frame(bottom)
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="按课程", style="Head.TLabel").pack(anchor="w")
        self.course_table = DataTable(left, [
            ("course", "课程", 130, "w"), ("graded", "已出分", 65, "center"),
            ("avg_score", "平均", 65, "center"), ("max_score", "最高", 60, "center"),
            ("min_score", "最低", 60, "center"), ("pass_rate", "及格率%", 75, "center")],
            placeholder="还没有课程")
        self.course_table.pack(fill="both", expand=True)
        self.course_table.apply_theme(app.theme)

        right = ttk.Frame(bottom)
        right.pack(side="left", fill="both", expand=True, padx=(PAD, 0))
        ttk.Label(right, text="加权平均分排行", style="Head.TLabel").pack(anchor="w")
        self.rank_table = DataTable(right, [
            ("sno", "学号", 95, "w"), ("name", "姓名", 75, "w"),
            ("credits", "学分", 55, "center"), ("weighted_avg", "加权平均", 85, "center")],
            placeholder="还没有成绩")
        self.rank_table.pack(fill="both", expand=True)
        self.rank_table.apply_theme(app.theme)
        panes.add(bottom, weight=2)

        self.reload()

    def apply_theme(self):
        self.palette = self.app.theme.palette
        for table in (self.class_table, self.course_table, self.rank_table):
            table.apply_theme(self.app.theme)

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


# ------------------------------------------------------------------ 主窗口
class App(tk.Tk):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.title(f"{cfg.title} · 课题2 学生管理系统")
        self.geometry(f"{cfg.window[0]}x{cfg.window[1]}")
        self.minsize(1060, 660)

        mode = theme_mod.load_mode(cfg) if Path(cfg.db_path).exists() else cfg.theme
        self.theme = theme_mod.Theme(self, cfg, mode)
        self.palette = self.theme.palette
        log.get("ui").info("打开界面：主题=%s 数据库=%s", mode, cfg.db_path)

        self._build_menu()
        self.status = ttk.Label(self, text="就绪", style="Status.TLabel", anchor="w")
        self.status.pack(side="bottom", fill="x")
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(10, 6))

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

        view_menu = tk.Menu(menubar, tearoff=0)
        self._theme_var = tk.IntVar(value=0 if self.theme.mode == "light" else 1)
        view_menu.add_radiobutton(label="浅色主题", variable=self._theme_var, value=0,
                                  command=lambda: self.set_theme("light"))
        view_menu.add_radiobutton(label="深色主题", variable=self._theme_var, value=1,
                                  command=lambda: self.set_theme("dark"))
        menubar.add_cascade(label="视图", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于", command=self._about)
        menubar.add_cascade(label="帮助", menu=help_menu)
        self.configure(menu=menubar)

    def set_theme(self, mode: str) -> None:
        self.theme.apply(mode)
        self.palette = self.theme.palette
        theme_mod.save_mode(self.cfg, mode)
        for _title, tab in self.tabs:
            tab.apply_theme()
        self._theme_var.set(0 if mode == "light" else 1)
        self.set_status("已切换为" + ("浅色主题" if mode == "light" else "深色主题"))

    def _about(self):
        messagebox.showinfo(
            "关于",
            f"{self.cfg.title} {self.cfg.version}\n"
            "课题2 · 数据库编程：基于 Python 的管理信息系统\n\n"
            "SQLite + Tkinter，仅使用标准库；支持分页、批量录入与 CSV 导入导出。",
            parent=self,
        )

    def _on_tab_changed(self, _event=None):
        index = self.notebook.index(self.notebook.select())
        _title, tab = self.tabs[index]
        tab.reload()

    def notify_changed(self) -> None:
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
