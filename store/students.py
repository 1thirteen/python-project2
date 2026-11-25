"""学生表的 SQL。"""

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


def list_students(conn: sqlite3.Connection, keyword: str = "", class_id=None,
                  order: str = "sno", descending: bool = False) -> list[sqlite3.Row]:
    if order not in ORDER_COLUMNS:
        raise ValueError(f"不支持的排序字段：{order}")
    sql = BASE_SQL + " WHERE 1 = 1"
    params: list = []
    if keyword:
        sql += " AND (s.name LIKE ? OR s.sno LIKE ? OR s.phone LIKE ?)"
        like = f"%{keyword}%"
        params += [like, like, like]
    if class_id is not None:
        sql += " AND s.class_id = ?"
        params.append(class_id)
    sql += f" ORDER BY {ORDER_COLUMNS[order]} {'DESC' if descending else 'ASC'}, s.sno"
    return conn.execute(sql, params).fetchall()


def get_student(conn: sqlite3.Connection, student_id: int):
    return conn.execute(BASE_SQL + " WHERE s.student_id = ?", (student_id,)).fetchone()


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
