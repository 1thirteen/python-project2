"""课程业务：校验、增删改查、异常翻译。"""

from __future__ import annotations

import sqlite3

from common.errors import NotFoundError, ValidationError, translate_integrity
from service import validation
from store import connection, courses


def _normalize(raw: dict, creating: bool) -> dict:
    data: dict = {}
    if creating or "cno" in raw:
        cno = validation.text(raw.get("cno"), "课程号", max_len=10)
        if not cno.isalnum():
            raise ValidationError("课程号只能由字母和数字组成")
        data["cno"] = cno.upper()
    if creating or "title" in raw:
        data["title"] = validation.text(raw.get("title"), "课程名称", max_len=40)
    if "credit" in raw:
        data["credit"] = validation.real(raw.get("credit"), "学分", 0.5, 20)
    if "teacher" in raw:
        data["teacher"] = validation.text(
            raw.get("teacher"), "任课教师", required=False, max_len=20
        )
    if "hours" in raw:
        data["hours"] = validation.integer(raw.get("hours"), "学时", 1, 500)
    if creating:
        data.setdefault("credit", 2.0)
        data.setdefault("teacher", None)
        data.setdefault("hours", 32)
    return data


def list_courses(cfg, keyword: str = "", order: str = "cno",
                 descending: bool = False) -> list[dict]:
    with connection.session(cfg.db_path) as conn:
        rows = courses.list_courses(conn, keyword, order, descending)
        return [dict(row) for row in rows]


def options(cfg) -> list[dict]:
    with connection.session(cfg.db_path) as conn:
        return [dict(row) for row in courses.options(conn)]


def create(cfg, raw: dict) -> int:
    data = _normalize(raw, creating=True)
    try:
        with connection.session(cfg.db_path) as conn:
            return courses.create_course(conn, data)
    except sqlite3.IntegrityError as exc:
        raise translate_integrity(exc) from None


def update(cfg, course_id: int, raw: dict) -> None:
    changes = _normalize(raw, creating=False)
    if not changes:
        return
    try:
        with connection.session(cfg.db_path) as conn:
            if courses.update_course(conn, course_id, changes) == 0:
                raise NotFoundError(f"课程不存在（course_id={course_id}）")
    except sqlite3.IntegrityError as exc:
        raise translate_integrity(exc) from None


def delete(cfg, course_id: int) -> None:
    """删除课程：相关成绩被级联删除。"""
    with connection.session(cfg.db_path) as conn:
        if courses.delete_course(conn, course_id) == 0:
            raise NotFoundError(f"课程不存在（course_id={course_id}）")
