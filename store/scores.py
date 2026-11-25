"""成绩表的 SQL：分页查询、录入、批量写入、删除。"""

from __future__ import annotations

import sqlite3

BASE_SQL = """
SELECT sc.rowid      AS score_id,
       s.student_id  AS student_id,
       co.course_id  AS course_id,
       co.cno        AS cno,
       s.sno         AS sno,
       s.name        AS name,
       c.class_name  AS class_name,
       co.title      AS course,
       co.credit     AS credit,
       sc.term       AS term,
       sc.score      AS score,
       sc.updated_at AS updated_at,
       CASE WHEN sc.score IS NULL THEN '未录入'
            WHEN sc.score >= 60   THEN '及格'
            ELSE '不及格' END     AS pass_state
  FROM scores sc
  JOIN students s  ON s.student_id = sc.student_id
  JOIN courses  co ON co.course_id = sc.course_id
  LEFT JOIN classes c ON c.class_id = s.class_id
"""

ORDER_COLUMNS = {
    "sno": "s.sno",
    "name": "s.name",
    "course": "co.title",
    "term": "sc.term",
    "score": "sc.score",
    "class_name": "class_name",
}

COUNT_FROM = """
  FROM scores sc
  JOIN students s  ON s.student_id = sc.student_id
  JOIN courses  co ON co.course_id = sc.course_id
"""


def _filters(student_id=None, course_id=None, term=None, keyword: str = "",
             only_missing: bool = False) -> tuple[str, list]:
    sql, params = "", []
    if student_id is not None:
        sql += " AND s.student_id = ?"
        params.append(student_id)
    if course_id is not None:
        sql += " AND co.course_id = ?"
        params.append(course_id)
    if term:
        sql += " AND sc.term = ?"
        params.append(term)
    if keyword:
        sql += " AND (s.name LIKE ? OR s.sno LIKE ? OR co.title LIKE ?)"
        params += [f"%{keyword}%"] * 3
    if only_missing:
        sql += " AND sc.score IS NULL"
    return sql, params


def _order(order: str, descending: bool) -> str:
    if order not in ORDER_COLUMNS:
        raise ValueError(f"不支持的排序字段：{order}")
    direction = "DESC" if descending else "ASC"
    return f" ORDER BY {ORDER_COLUMNS[order]} {direction}, s.sno, sc.term"


def list_scores(conn: sqlite3.Connection, student_id=None, course_id=None, term=None,
                keyword: str = "", only_missing: bool = False,
                order: str = "sno", descending: bool = False) -> list[sqlite3.Row]:
    where, params = _filters(student_id, course_id, term, keyword, only_missing)
    sql = BASE_SQL + " WHERE 1 = 1" + where + _order(order, descending)
    return conn.execute(sql, params).fetchall()


def count_scores(conn: sqlite3.Connection, student_id=None, course_id=None, term=None,
                 keyword: str = "", only_missing: bool = False) -> int:
    where, params = _filters(student_id, course_id, term, keyword, only_missing)
    return conn.execute(
        "SELECT COUNT(*)" + COUNT_FROM + " WHERE 1 = 1" + where, params
    ).fetchone()[0]


def page_scores(conn: sqlite3.Connection, student_id=None, course_id=None, term=None,
                keyword: str = "", only_missing: bool = False,
                order: str = "sno", descending: bool = False,
                limit: int = 50, offset: int = 0) -> list[sqlite3.Row]:
    where, params = _filters(student_id, course_id, term, keyword, only_missing)
    sql = BASE_SQL + " WHERE 1 = 1" + where + _order(order, descending)
    sql += " LIMIT ? OFFSET ?"
    return conn.execute(sql, params + [limit, offset]).fetchall()


def get_score(conn: sqlite3.Connection, student_id: int, course_id: int, term: str):
    return conn.execute(
        "SELECT * FROM scores WHERE student_id = ? AND course_id = ? AND term = ?",
        (student_id, course_id, term),
    ).fetchone()


def save_score(conn: sqlite3.Connection, student_id: int, course_id: int,
               term: str, score) -> str:
    """存在则 UPDATE（触发器刷新 updated_at），否则 INSERT。返回 inserted / updated。"""
    exists = get_score(conn, student_id, course_id, term) is not None
    if exists:
        cur = conn.execute(
            """UPDATE scores SET score = ?
                WHERE student_id = ? AND course_id = ? AND term = ?""",
            (score, student_id, course_id, term),
        )
        if cur.rowcount == 0:
            raise RuntimeError("成绩行在更新时消失了")
        return "updated"
    conn.execute(
        """INSERT INTO scores (student_id, course_id, term, score)
           VALUES (?, ?, ?, ?)""",
        (student_id, course_id, term, score),
    )
    return "inserted"


def delete_score(conn: sqlite3.Connection, student_id: int, course_id: int, term: str) -> int:
    cur = conn.execute(
        "DELETE FROM scores WHERE student_id = ? AND course_id = ? AND term = ?",
        (student_id, course_id, term),
    )
    return cur.rowcount


def terms(conn: sqlite3.Connection) -> list[str]:
    return [row[0] for row in conn.execute(
        "SELECT DISTINCT term FROM scores ORDER BY term DESC"
    )]


def graded(conn: sqlite3.Connection, student_id: int) -> list[sqlite3.Row]:
    """某名学生的成绩单（按学期、课程排序），供界面详情使用。"""
    return conn.execute(
        BASE_SQL + " WHERE s.student_id = ? ORDER BY sc.term DESC, co.cno",
        (student_id,),
    ).fetchall()


def roster(conn: sqlite3.Connection, class_id: int, course_id: int,
           term: str) -> list[sqlite3.Row]:
    """批量录入用：某班全部学生 + 指定课程/学期下的现有成绩（没有记录时 score 为 NULL）。"""
    return conn.execute(
        """
        SELECT s.student_id, s.sno, s.name, c.class_name,
               sc.score, sc.updated_at, sc.rowid AS score_id
          FROM students s
          LEFT JOIN classes c ON c.class_id = s.class_id
          LEFT JOIN scores sc ON sc.student_id = s.student_id
                             AND sc.course_id = ?
                             AND sc.term = ?
         WHERE s.class_id = ?
         ORDER BY s.sno
        """,
        (course_id, term, class_id),
    ).fetchall()
