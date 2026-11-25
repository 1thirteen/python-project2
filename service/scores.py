"""成绩业务：分页查询、单条录入（按学号/课程号）、按班级批量录入、删除。"""

from __future__ import annotations

import sqlite3

from common import paging
from common.errors import NotFoundError, ValidationError, translate_integrity
from service import validation
from store import connection, courses, scores, students


def page(cfg, student_id=None, course_id=None, term=None, keyword: str = "",
         only_missing: bool = False, order: str = "sno", descending: bool = False,
         page: int = 1, size: int = 50) -> dict:
    with connection.session(cfg.db_path) as conn:
        total = scores.count_scores(conn, student_id, course_id, term, keyword, only_missing)
        page, pages, offset = paging.clamp(page, size, total)
        rows = scores.page_scores(
            conn, student_id, course_id, term, keyword, only_missing,
            order, descending, size, offset,
        )
        return {
            "rows": [dict(row) for row in rows],
            "total": total,
            "page": page,
            "pages": pages,
            "size": max(1, int(size)),
        }


def list_scores(cfg, student_id=None, course_id=None, term=None, keyword: str = "",
                only_missing: bool = False, order: str = "sno",
                descending: bool = False) -> list[dict]:
    """不分页，供导出与统计使用。"""
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


def save_by_codes(cfg, sno_text, cno_text, term, score) -> str:
    """用业务编号录入：界面上填学号 + 课程号，比下拉框更适合上万条数据。"""
    sno = validation.sno(sno_text)
    cno = validation.text(cno_text, "课程号", max_len=10).upper()
    term_text = validation.term(term)
    value = validation.score(score)
    with connection.session(cfg.db_path) as conn:
        student = students.find_by_sno(conn, sno)
        if student is None:
            raise NotFoundError(f"学号 {sno} 不存在")
        course = courses.find_by_cno(conn, cno)
        if course is None:
            raise NotFoundError(f"课程号 {cno} 不存在")
        try:
            return scores.save_score(
                conn, student["student_id"], course["course_id"], term_text, value
            )
        except sqlite3.IntegrityError as exc:
            raise translate_integrity(exc) from None


def roster(cfg, class_id, course_id, term: str) -> list[dict]:
    """批量录入：班级花名册 + 该课程/学期下已有成绩。"""
    class_id = validation.integer(class_id, "班级", 1, 2 ** 31 - 1)
    course_id = validation.integer(course_id, "课程", 1, 2 ** 31 - 1)
    term_text = validation.term(term)
    with connection.session(cfg.db_path) as conn:
        return [dict(row) for row in scores.roster(conn, class_id, course_id, term_text)]


def batch_save(cfg, course_id, term, entries) -> dict:
    """批量保存：entries 为 [(student_id, 成绩文本)]；空文本表示「这次不改」。

    整批一个事务，单行失败只记录错误、不影响其它行。
    """
    cid = validation.integer(course_id, "课程", 1, 2 ** 31 - 1)
    term_text = validation.term(term)
    saved, skipped, errors = 0, 0, []
    with connection.session(cfg.db_path) as conn:
        for entry in entries:
            student_id = validation.integer(entry.get("student_id"), "学生", 1, 2 ** 31 - 1)
            raw = "" if entry.get("score") is None else str(entry.get("score")).strip()
            if raw == "":
                skipped += 1
                continue
            try:
                value = validation.score(raw)
                scores.save_score(conn, student_id, cid, term_text, value)
                saved += 1
            except ValidationError as exc:
                errors.append({"student_id": student_id, "message": str(exc)})
            except sqlite3.IntegrityError as exc:
                errors.append({"student_id": student_id, "message": str(translate_integrity(exc))})
    return {"saved": saved, "skipped": skipped, "errors": errors}


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
