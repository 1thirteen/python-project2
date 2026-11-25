"""学生业务：校验、增删改查、异常翻译。"""

from __future__ import annotations

import sqlite3

from common import paging
from common.errors import NotFoundError, translate_integrity
from service import validation
from store import classes, connection, students

OPTIONAL = ("birthday", "phone", "email", "class_id")


def normalize_payload(raw: dict, creating: bool) -> dict:
    """把界面 / CSV 传来的原始字段校验成可入库的字典。"""
    data: dict = {}
    if creating or "sno" in raw:
        data["sno"] = validation.sno(raw.get("sno"))
    if creating or "name" in raw:
        data["name"] = validation.text(raw.get("name"), "姓名", max_len=20)
    if creating or "gender" in raw:
        data["gender"] = validation.choice(raw.get("gender"), "性别", ("男", "女"))
    if "birthday" in raw:
        data["birthday"] = validation.date_text(raw.get("birthday"), "出生日期")
    if "phone" in raw:
        data["phone"] = validation.phone(raw.get("phone"))
    if "email" in raw:
        data["email"] = validation.email(raw.get("email"))
    if "class_id" in raw:
        data["class_id"] = validation.ref_id(raw.get("class_id"), "班级")
    if creating:
        for key in OPTIONAL:
            data.setdefault(key, None)
    return data


def list_students(cfg, keyword: str = "", class_id=None, order: str = "sno",
                  descending: bool = False) -> list[dict]:
    with connection.session(cfg.db_path) as conn:
        rows = students.list_students(conn, keyword, class_id, order, descending)
        return [dict(row) for row in rows]


def page(cfg, keyword: str = "", class_id=None, order: str = "sno",
         descending: bool = False, page: int = 1, size: int = 50) -> dict:
    """分页查询：一次只取一页，万行级也不用把整表读进内存。"""
    with connection.session(cfg.db_path) as conn:
        total = students.count_students(conn, keyword, class_id)
        page, pages, offset = paging.clamp(page, size, total)
        rows = students.page_students(
            conn, keyword, class_id, order, descending, size, offset
        )
        return {
            "rows": [dict(row) for row in rows],
            "total": total,
            "page": page,
            "pages": pages,
            "size": max(1, int(size)),
        }


def get(cfg, student_id: int) -> dict:
    with connection.session(cfg.db_path) as conn:
        row = students.get_student(conn, student_id)
        if row is None:
            raise NotFoundError(f"学生不存在（student_id={student_id}）")
        return dict(row)


def create(cfg, raw: dict) -> int:
    data = normalize_payload(raw, creating=True)
    try:
        with connection.session(cfg.db_path) as conn:
            return students.create_student(conn, data)
    except sqlite3.IntegrityError as exc:
        raise translate_integrity(exc) from None


def update(cfg, student_id: int, raw: dict) -> None:
    changes = normalize_payload(raw, creating=False)
    if not changes:
        return
    try:
        with connection.session(cfg.db_path) as conn:
            if students.update_student(conn, student_id, changes) == 0:
                raise NotFoundError(f"学生不存在（student_id={student_id}）")
    except sqlite3.IntegrityError as exc:
        raise translate_integrity(exc) from None


def delete(cfg, student_id: int) -> None:
    with connection.session(cfg.db_path) as conn:
        if students.delete_student(conn, student_id) == 0:
            raise NotFoundError(f"学生不存在（student_id={student_id}）")


def class_options(cfg) -> list[dict]:
    """下拉框：[(class_id, class_name)]。"""
    with connection.session(cfg.db_path) as conn:
        return [dict(row) for row in classes.options(conn)]
