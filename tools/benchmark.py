"""万行级基准：批量造数据，测分页 / 搜索 / 聚合的耗时。

    python tools/benchmark.py --students 10000 --courses 20
    python tools/benchmark.py --students 10000 --keep   # 保留 data/bench.db
"""

from __future__ import annotations

import argparse
import random
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from common.config import ROOT as REPO_ROOT  # noqa: E402
from store import connection  # noqa: E402

SURNAMES = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
GIVEN = "伟芳娜敏静丽强磊军洋勇艳杰娟涛明超秀霞平刚桂英"


def build_database(db_path: Path, students: int, courses: int) -> dict:
    if db_path.exists():
        db_path.unlink()
    conn = connection.connect(db_path)
    try:
        conn.executescript((REPO_ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
        classes = max(1, students // 250)
        conn.executemany(
            "INSERT INTO classes (class_name, major, grade, head_teacher) VALUES (?, ?, ?, ?)",
            [(f"2024级测试{i:04d}班", "测试专业", 2024, f"老师{i}") for i in range(1, classes + 1)],
        )
        conn.executemany(
            "INSERT INTO courses (cno, title, credit, teacher, hours) VALUES (?, ?, ?, ?, ?)",
            [(f"B{i:03d}", f"基准课程{i:03d}", 2.0 + (i % 4) * 0.5, f"教师{i}", 32) for i in range(1, courses + 1)],
        )
        random.seed(42)
        rows = []
        for index in range(1, students + 1):
            name = random.choice(SURNAMES) + "".join(random.choice(GIVEN) for _ in range(2))
            rows.append((f"{20240000 + index}", name, random.choice(("男", "女")),
                         random.choice(("2005-01-01", "2006-06-15", None)),
                         f"138{index:08d}", None,
                         random.randint(1, classes), "2024-09-01"))
        conn.executemany(
            """INSERT INTO students (sno, name, gender, birthday, phone, email, class_id, enroll_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        student_ids = [row[0] for row in conn.execute("SELECT student_id FROM students")]
        course_ids = [row[0] for row in conn.execute("SELECT course_id FROM courses")]
        score_rows = []
        for sid in student_ids:
            for cid in random.sample(course_ids, k=min(3, len(course_ids))):
                score = None if random.random() < 0.03 else random.randint(40, 100)
                score_rows.append((sid, cid, "2024-2025-1", score))
        conn.executemany(
            """INSERT INTO scores (student_id, course_id, term, score) VALUES (?, ?, ?, ?)""",
            score_rows,
        )
        conn.commit()
        return {
            "students": conn.execute("SELECT COUNT(*) FROM students").fetchone()[0],
            "scores": conn.execute("SELECT COUNT(*) FROM scores").fetchone()[0],
            "classes": classes,
            "courses": courses,
        }
    finally:
        conn.close()


def timed(func, *args, repeats: int = 5) -> float:
    """返回多次执行的中位数（毫秒）。"""
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        func(*args)
        samples.append((time.perf_counter() - start) * 1000)
    samples.sort()
    return samples[len(samples) // 2]


def bench(db_path: Path, size: int) -> list[tuple[str, float, str]]:
    from service import scores as score_service
    from service import students as student_service
    from common.config import Config

    cfg = Config(
        root=REPO_ROOT,
        db_path=db_path,
        schema_path=REPO_ROOT / "db" / "schema.sql",
        seed_path=REPO_ROOT / "db" / "seed.sql",
    )
    results = []

    def measure(label, func, detail=""):
        results.append((label, timed(func), detail))

    measure("学生第 1 页", lambda: student_service.page(cfg, size=size), f"每页 {size}")
    measure("学生第 10 页", lambda: student_service.page(cfg, page=10, size=size), f"每页 {size}")
    measure("学生末页", lambda: student_service.page(cfg, page=200, size=size), f"每页 {size}")
    measure("学生按班级筛选", lambda: student_service.page(cfg, class_id=1, size=size),
            f"第 3 页 {size}")
    measure("学生按姓名搜索", lambda: student_service.page(cfg, keyword="张", size=size),
            "LIKE '%张%'")
    measure("成绩第 1 页", lambda: score_service.page(cfg, size=size), f"每页 {size}")
    measure("成绩按课程筛选", lambda: score_service.page(cfg, course_id=1, size=size),
            "idx_scores_course")
    measure("成绩按学期筛选", lambda: score_service.page(cfg, term="2024-2025-1", size=size),
            "idx_scores_term")
    measure("成绩只看未录入", lambda: score_service.page(cfg, only_missing=True, size=size))

    from service import reports
    measure("统计：按课程聚合", lambda: reports.course_stats(cfg))
    measure("统计：加权排行", lambda: reports.ranking(cfg))
    return results


def explain(db_path: Path) -> list[tuple[str, str]]:
    conn = connection.connect(db_path)
    try:
        queries = [
            ("按班级分页", "SELECT * FROM students WHERE class_id = 1 ORDER BY name LIMIT 50 OFFSET 0"),
            ("按学期筛选成绩", "SELECT * FROM scores WHERE term = '2024-2025-1' LIMIT 50"),
            ("按学号查人", "SELECT * FROM students WHERE sno = '20240123'"),
            ("按课程筛选成绩", "SELECT * FROM scores WHERE course_id = 3 LIMIT 50"),
        ]
        rows = []
        for label, sql in queries:
            plans = [row["detail"] for row in conn.execute("EXPLAIN QUERY PLAN " + sql)]
            rows.append((label, " / ".join(plans)))
        return rows
    finally:
        conn.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="万行级基准")
    parser.add_argument("--students", type=int, default=10000)
    parser.add_argument("--courses", type=int, default=20)
    parser.add_argument("--size", type=int, default=50, help="每页条数")
    parser.add_argument("--db", default=str(REPO_ROOT / "data" / "bench.db"))
    parser.add_argument("--keep", action="store_true", help="跑完保留数据库文件")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    build_start = time.perf_counter()
    info = build_database(db_path, args.students, args.courses)
    build_cost = time.perf_counter() - build_start

    print(f"造数据：学生 {info['students']}，成绩 {info['scores']}，"
          f"班级 {info['classes']}，课程 {info['courses']}（{build_cost:.2f}s）")
    print()
    print("| 场景 | 中位耗时(ms) | 说明 |")
    print("| ---- | ------------ | ---- |")
    for label, cost, detail in bench(db_path, args.size):
        print(f"| {label} | {cost:.1f} | {detail} |")
    print()
    print("| 查询 | 执行计划 |")
    print("| ---- | -------- |")
    for label, plan in explain(db_path):
        print(f"| {label} | {plan} |")

    if not args.keep:
        try:
            db_path.unlink()
        except OSError:
            pass
        for suffix in ("-wal", "-shm"):
            Path(str(db_path) + suffix).exists() and Path(str(db_path) + suffix).unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
