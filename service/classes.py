"""班级业务：校验、增删改查、异常翻译。"""

from __future__ import annotations

import sqlite3

from common.errors import NotFoundError, translate_integrity
from service import validation
from store import classes, connection

EDITABLE = ("class_name", "major", "grade", "head_teacher")


def _normalize(raw: dict, creating: bool) -> dict:
    data: dict = {}
    if creating or "class_name" in raw:
        data["class_name"] = validation.text(raw.get("class_name"), "班级名称", max_len=40)
    if creating or "major" in raw:
        data["major"] = validation.text(raw.get("major"), "专业", max_len=30)
    if creating or "grade" in raw:
        data["grade"] = validation.integer(raw.get("grade"), "年级", 2000, 2100)
    if "head_teacher" in raw:
        data["head_teacher"] = validation.text(
            raw.get("head_teacher"), "班主任", required=False, max_len=20
        )
    if creating:
        data.setdefault("head_teacher", None)
    return data


def list_classes(cfg, keyword: str = "", order: str = "grade",
                 descending: bool = True) -> list[dict]:
    with connection.session(cfg.db_path) as conn:
        rows = classes.list_classes(conn, keyword, order, descending)
        return [dict(row) for row in rows]


def create(cfg, raw: dict) -> int:
    data = _normalize(raw, creating=True)
    try:
        with connection.session(cfg.db_path) as conn:
            return classes.create_class(conn, data)
    except sqlite3.IntegrityError as exc:
        raise translate_integrity(exc) from None


def update(cfg, class_id: int, raw: dict) -> None:
    changes = _normalize(raw, creating=False)
    if not changes:
        return
    try:
        with connection.session(cfg.db_path) as conn:
            if classes.update_class(conn, class_id, changes) == 0:
                raise NotFoundError(f"班级不存在（class_id={class_id}）")
    except sqlite3.IntegrityError as exc:
        raise translate_integrity(exc) from None


def delete(cfg, class_id: int) -> None:
    """删除班级，班内学生的 class_id 会被置空（未分班）。"""
    with connection.session(cfg.db_path) as conn:
        if classes.delete_class(conn, class_id) == 0:
            raise NotFoundError(f"班级不存在（class_id={class_id}）")
