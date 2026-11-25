"""统计报表：数据全部来自 SQL 聚合与视图，界面只负责展示。"""

from __future__ import annotations

from store import connection

CLASS_SUMMARY_SQL = """
SELECT c.class_id, c.class_name, c.grade, c.major,
       COUNT(DISTINCT s.student_id) AS students,
       COUNT(sc.score)              AS graded,
       ROUND(AVG(sc.score), 2)      AS avg_score
  FROM classes c
  LEFT JOIN students s ON s.class_id   = c.class_id
  LEFT JOIN scores   sc ON sc.student_id = s.student_id
 GROUP BY c.class_id
 ORDER BY c.grade DESC, c.class_name
"""

COURSE_STATS_SQL = """
SELECT cno, course, graded, avg_score, max_score, min_score, pass_rate
  FROM v_course_stats
 ORDER BY cno
"""

RANKING_SQL = """
SELECT sno, name, class_name, graded, credits, weighted_avg
  FROM v_student_avg
 ORDER BY weighted_avg DESC, sno
"""


def overview(cfg) -> dict:
    with connection.session(cfg.db_path) as conn:
        row = conn.execute(
            """SELECT (SELECT COUNT(*) FROM classes)  AS classes,
                      (SELECT COUNT(*) FROM students) AS students,
                      (SELECT COUNT(*) FROM courses)  AS courses,
                      (SELECT COUNT(*) FROM scores)   AS scores,
                      (SELECT COUNT(*) FROM scores WHERE score IS NULL) AS missing,
                      (SELECT ROUND(AVG(score), 2) FROM scores) AS avg_score"""
        ).fetchone()
        return dict(row)


def class_summary(cfg) -> list[dict]:
    with connection.session(cfg.db_path) as conn:
        return [dict(row) for row in conn.execute(CLASS_SUMMARY_SQL)]


def course_stats(cfg) -> list[dict]:
    with connection.session(cfg.db_path) as conn:
        return [dict(row) for row in conn.execute(COURSE_STATS_SQL)]


def ranking(cfg) -> list[dict]:
    with connection.session(cfg.db_path) as conn:
        return [dict(row) for row in conn.execute(RANKING_SQL)]
