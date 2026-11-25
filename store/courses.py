"""课程表的 SQL。"""

from __future__ import annotations

import sqlite3

BASE_SQL = """
SELECT co.course_id, co.cno, co.title, co.credit, co.teacher, co.hours,
       (SELECT COUNT(*) FROM scores sc WHERE sc.course_id = co.course_id) AS records
  FROM courses co
"""

ORDER_COLUMNS = {
    "cno": "co.cno",
    "title": "co.title",
    "credit": "co.credit",
    "hours": "co.hours",
}

EDITABLE = ("cno", "title", "credit", "teacher", "hours")


def list_courses(conn: sqlite3.Connection, keyword: str = "", order: str = "cno",
                 descending: bool = False) -> list[sqlite3.Row]:
    if order not in ORDER_COLUMNS:
        raise ValueError(f"不支持的排序字段：{order}")
    sql = BASE_SQL + " WHERE 1 = 1"
    params: list = []
    if keyword:
        sql += " AND (co.title LIKE ? OR co.cno LIKE ? OR co.teacher LIKE ?)"
        like = f"%{keyword}%"
        params += [like, like, like]
    sql += f" ORDER BY {ORDER_COLUMNS[order]} {'DESC' if descending else 'ASC'}"
    return conn.execute(sql, params).fetchall()


def options(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT course_id, cno, title FROM courses ORDER BY cno").fetchall()


def get_course(conn: sqlite3.Connection, course_id: int):
    return conn.execute("SELECT * FROM courses WHERE course_id = ?", (course_id,)).fetchone()


def create_course(conn: sqlite3.Connection, data: dict) -> int:
    cur = conn.execute(
        """INSERT INTO courses (cno, title, credit, teacher, hours)
           VALUES (:cno, :title, :credit, :teacher, :hours)""",
        data,
    )
    return int(cur.lastrowid)


def update_course(conn: sqlite3.Connection, course_id: int, changes: dict) -> int:
    fields = [k for k in changes if k in EDITABLE]
    if not fields:
        return 0
    sql = "UPDATE courses SET " + ", ".join(f"{k} = ?" for k in fields) + " WHERE course_id = ?"
    cur = conn.execute(sql, [changes[k] for k in fields] + [course_id])
    return cur.rowcount


def delete_course(conn: sqlite3.Connection, course_id: int) -> int:
    """删课程：相关成绩被外键级联删除。"""
    cur = conn.execute("DELETE FROM courses WHERE course_id = ?", (course_id,))
    return cur.rowcount
