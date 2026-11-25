"""学生表的 SQL：列表、分页、总数、增删改。"""

from __future__ import annotations

import sqlite3

BASE_SQL = """
SELECT s.student_id, s.sno, s.name, s.gender, s.birthday, s.phone, s.email,
       s.class_id, COALESCE(c.class_name, '（未分班）') AS class_name,
       s.enroll_date
  FROM students s
  LEFT JOIN classes c ON c.class_id = s.class_id
"""

ORDER_COLUMNS = {
    "sno": "s.sno",
    "name": "s.name",
    "gender": "s.gender",
    "class_name": "class_name",
    "enroll_date": "s.enroll_date",
}

EDITABLE = ("sno", "name", "gender", "birthday", "phone", "email", "class_id")


def _filters(keyword: str, class_id) -> tuple[str, list]:
    sql, params = "", []
    if keyword:
        sql += " AND (s.name LIKE ? OR s.sno LIKE ? OR s.phone LIKE ?)"
        params += [f"%{keyword}%"] * 3
    if class_id is not None:
        sql += " AND s.class_id = ?"
        params.append(class_id)
    return sql, params


def _order(order: str, descending: bool) -> str:
    if order not in ORDER_COLUMNS:
        raise ValueError(f"不支持的排序字段：{order}")
    direction = "DESC" if descending else "ASC"
    return f" ORDER BY {ORDER_COLUMNS[order]} {direction}, s.sno"


def list_students(conn: sqlite3.Connection, keyword: str = "", class_id=None,
                  order: str = "sno", descending: bool = False) -> list[sqlite3.Row]:
    where, params = _filters(keyword, class_id)
    sql = BASE_SQL + " WHERE 1 = 1" + where + _order(order, descending)
    return conn.execute(sql, params).fetchall()


def count_students(conn: sqlite3.Connection, keyword: str = "", class_id=None) -> int:
    where, params = _filters(keyword, class_id)
    return conn.execute(
        "SELECT COUNT(*) FROM students s WHERE 1 = 1" + where, params
    ).fetchone()[0]


def page_students(conn: sqlite3.Connection, keyword: str = "", class_id=None,
                  order: str = "sno", descending: bool = False,
                  limit: int = 50, offset: int = 0) -> list[sqlite3.Row]:
    where, params = _filters(keyword, class_id)
    sql = BASE_SQL + " WHERE 1 = 1" + where + _order(order, descending)
    sql += " LIMIT ? OFFSET ?"
    return conn.execute(sql, params + [limit, offset]).fetchall()


def get_student(conn: sqlite3.Connection, student_id: int):
    return conn.execute(BASE_SQL + " WHERE s.student_id = ?", (student_id,)).fetchone()


def find_by_sno(conn: sqlite3.Connection, sno: str):
    return conn.execute("SELECT * FROM students WHERE sno = ?", (sno,)).fetchone()


def create_student(conn: sqlite3.Connection, data: dict) -> int:
    cur = conn.execute(
        """INSERT INTO students (sno, name, gender, birthday, phone, email, class_id)
           VALUES (:sno, :name, :gender, :birthday, :phone, :email, :class_id)""",
        data,
    )
    return int(cur.lastrowid)


def update_student(conn: sqlite3.Connection, student_id: int, changes: dict) -> int:
    fields = [k for k in changes if k in EDITABLE]
    if not fields:
        return 0
    sql = "UPDATE students SET " + ", ".join(f"{k} = ?" for k in fields) + " WHERE student_id = ?"
    cur = conn.execute(sql, [changes[k] for k in fields] + [student_id])
    return cur.rowcount


def delete_student(conn: sqlite3.Connection, student_id: int) -> int:
    """删学生：他的成绩被外键级联删除。"""
    cur = conn.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
    return cur.rowcount
