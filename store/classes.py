"""班级表的 SQL。"""

from __future__ import annotations

import sqlite3

LIST_SQL = """
SELECT c.class_id, c.class_name, c.major, c.grade, c.head_teacher,
       COUNT(s.student_id) AS students
  FROM classes c
  LEFT JOIN students s ON s.class_id = c.class_id
"""

ORDER_COLUMNS = {
    "class_name": "c.class_name",
    "grade": "c.grade",
    "students": "students",
}

EDITABLE = ("class_name", "major", "grade", "head_teacher")


def list_classes(conn: sqlite3.Connection, keyword: str = "", order: str = "grade",
                 descending: bool = True) -> list[sqlite3.Row]:
    if order not in ORDER_COLUMNS:
        raise ValueError(f"不支持的排序字段：{order}")
    sql = LIST_SQL + " WHERE 1 = 1"
    params: list = []
    if keyword:
        sql += " AND (c.class_name LIKE ? OR c.major LIKE ?)"
        like = f"%{keyword}%"
        params += [like, like]
    sql += " GROUP BY c.class_id"
    sql += f" ORDER BY {ORDER_COLUMNS[order]} {'DESC' if descending else 'ASC'}, c.class_name"
    return conn.execute(sql, params).fetchall()


def options(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """下拉框用的 (class_id, class_name) 列表。"""
    return conn.execute(
        "SELECT class_id, class_name FROM classes ORDER BY grade DESC, class_name"
    ).fetchall()


def get_class(conn: sqlite3.Connection, class_id: int):
    return conn.execute("SELECT * FROM classes WHERE class_id = ?", (class_id,)).fetchone()


def create_class(conn: sqlite3.Connection, data: dict) -> int:
    cur = conn.execute(
        """INSERT INTO classes (class_name, major, grade, head_teacher)
           VALUES (:class_name, :major, :grade, :head_teacher)""",
        data,
    )
    return int(cur.lastrowid)


def update_class(conn: sqlite3.Connection, class_id: int, changes: dict) -> int:
    fields = [k for k in changes if k in EDITABLE]
    if not fields:
        return 0
    sql = "UPDATE classes SET " + ", ".join(f"{k} = ?" for k in fields) + " WHERE class_id = ?"
    cur = conn.execute(sql, [changes[k] for k in fields] + [class_id])
    return cur.rowcount


def delete_class(conn: sqlite3.Connection, class_id: int) -> int:
    """删班级：学生保留，class_id 被外键置为 NULL。"""
    cur = conn.execute("DELETE FROM classes WHERE class_id = ?", (class_id,))
    return cur.rowcount
