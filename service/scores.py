"""成绩业务：录入 / 修改 / 删除 / 查询。"""

from __future__ import annotations

import sqlite3

from common.errors import NotFoundError, translate_integrity
from service import validation
from store import connection, scores


def list_scores(cfg, student_id=None, course_id=None, term=None, keyword: str = "",
                only_missing: bool = False, order: str = "sno",
                descending: bool = False) -> list[dict]:
    with connection.session(cfg.db_path) as conn:
        rows = scores.list_scores(
            conn, student_id, course_id, term, keyword, only_missing, order, descending
        )
        return [dict(row) for row in rows]


def save(cfg, student_id, course_id, term, score) -> str:
    """录入或修改一条成绩；返回 inserted / updated。"""
    sid = validation.integer(student_id, "学生", 1, 2 ** 31 - 1)
    cid = validation.integer(course_id, "课程", 1, 2 ** 31 - 1)
    term_text = validation.term(term)
    value = validation.score(score)
    try:
        with connection.session(cfg.db_path) as conn:
            return scores.save_score(conn, sid, cid, term_text, value)
    except sqlite3.IntegrityError as exc:
        raise translate_integrity(exc) from None


def delete(cfg, student_id, course_id, term) -> None:
    sid = validation.integer(student_id, "学生", 1, 2 ** 31 - 1)
    cid = validation.integer(course_id, "课程", 1, 2 ** 31 - 1)
    term_text = validation.term(term)
    with connection.session(cfg.db_path) as conn:
        if scores.delete_score(conn, sid, cid, term_text) == 0:
            raise NotFoundError("这条成绩不存在")


def terms(cfg) -> list[str]:
    with connection.session(cfg.db_path) as conn:
        return scores.terms(conn)


def transcript(cfg, student_id: int) -> list[dict]:
    with connection.session(cfg.db_path) as conn:
        return [dict(row) for row in scores.graded(conn, student_id)]
