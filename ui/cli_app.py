"""命令行界面：argparse 子命令 + 等宽表格输出。"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from common import tablefmt
from common.errors import AppError
from service import classes as class_service
from service import courses as course_service
from service import exports
from service import imports as import_service
from service import reports
from service import scores as score_service
from service import students as student_service


# ---------------------------------------------------------------- 输出工具
def _show(rows, headers, keys, footer=None) -> None:
    print(tablefmt.render(headers, [[row.get(key) for key in keys] for row in rows]))
    print(footer or f"共 {len(rows)} 条")
    print()


def _print_errors(errors) -> None:
    for line, message in errors[:10]:
        print(f"  第 {line} 行：{message}")


def _ok(message: str) -> None:
    print(message)


# ---------------------------------------------------------------- students
def cmd_students_list(cfg, args) -> int:
    if args.page or args.size:
        result = student_service.page(
            cfg, keyword=args.keyword or "", class_id=args.class_id,
            order=args.sort, descending=args.desc,
            page=args.page or 1, size=args.size or 50,
        )
        _show(
            result["rows"], ["学号", "姓名", "性别", "班级", "电话", "入学日期"],
            ["sno", "name", "gender", "class_name", "phone", "enroll_date"],
            footer=f"第 {result['page']} / {result['pages']} 页 · 共 {result['total']} 条",
        )
        return 0
    rows = student_service.list_students(
        cfg, keyword=args.keyword or "", class_id=args.class_id,
        order=args.sort, descending=args.desc,
    )
    _show(rows, ["学号", "姓名", "性别", "班级", "电话", "入学日期"],
          ["sno", "name", "gender", "class_name", "phone", "enroll_date"])
    return 0


def cmd_students_add(cfg, args) -> int:
    new_id = student_service.create(cfg, {
        "sno": args.sno, "name": args.name, "gender": args.gender,
        "birthday": args.birthday, "phone": args.phone,
        "email": args.email, "class_id": args.class_id,
    })
    _ok(f"已新增学生，student_id={new_id}")
    return 0


def cmd_students_edit(cfg, args) -> int:
    raw = {key: getattr(args, key) for key in
           ("sno", "name", "gender", "birthday", "phone", "email", "class_id")
           if getattr(args, key) is not None}
    if not raw:
        print("没有要修改的字段（用 --name / --phone 等指定）", file=sys.stderr)
        return 2
    student_service.update(cfg, args.student_id, raw)
    _ok(f"已更新学生 student_id={args.student_id}")
    return 0


def cmd_students_delete(cfg, args) -> int:
    student_service.delete(cfg, args.student_id)
    _ok(f"已删除学生 student_id={args.student_id}（其成绩一并删除）")
    return 0


def cmd_students_show(cfg, args) -> int:
    student = student_service.get(cfg, args.student_id)
    print(f"{student['sno']} {student['name']}（{student['class_name']}）")
    rows = score_service.transcript(cfg, args.student_id)
    if not rows:
        print("暂无成绩记录")
        return 0
    _show(rows, ["课程", "学期", "成绩", "状态"], ["course", "term", "score", "pass_state"])
    return 0


def cmd_students_import(cfg, args) -> int:
    result = import_service.import_students(cfg, args.file)
    print(f"共 {result['total']} 行，成功导入 {result['inserted']} 行")
    if result["errors"]:
        print(f"{len(result['errors'])} 行有问题：")
        _print_errors(result["errors"])
        return 1
    return 0


def cmd_students_template(cfg, args) -> int:
    path = import_service.write_template(args.out, "students")
    print(f"模板已写入 {path}")
    return 0


def cmd_students_transcript(cfg, args) -> int:
    path = Path(args.out)
    if path.suffix.lower() in (".html", ".htm"):
        target = exports.write_transcript_html(cfg, args.student_id, path)
    else:
        target = exports.write_transcript_csv(cfg, args.student_id, path)
    print(f"成绩单已写入 {target}")
    return 0


# ---------------------------------------------------------------- courses
def cmd_courses_list(cfg, args) -> int:
    rows = course_service.list_courses(cfg, keyword=args.keyword or "",
                                       order=args.sort, descending=args.desc)
    _show(rows, ["课程号", "课程名", "学分", "学时", "教师", "成绩条数"],
          ["cno", "title", "credit", "hours", "teacher", "records"])
    return 0


def cmd_courses_add(cfg, args) -> int:
    new_id = course_service.create(cfg, {
        "cno": args.cno, "title": args.title, "credit": args.credit,
        "teacher": args.teacher, "hours": args.hours,
    })
    _ok(f"已新增课程，course_id={new_id}")
    return 0


def cmd_courses_edit(cfg, args) -> int:
    raw = {key: getattr(args, key) for key in ("cno", "title", "credit", "teacher", "hours")
           if getattr(args, key) is not None}
    if not raw:
        print("没有要修改的字段", file=sys.stderr)
        return 2
    course_service.update(cfg, args.course_id, raw)
    _ok(f"已更新课程 course_id={args.course_id}")
    return 0


def cmd_courses_delete(cfg, args) -> int:
    course_service.delete(cfg, args.course_id)
    _ok(f"已删除课程 course_id={args.course_id}（相关成绩一并删除）")
    return 0


# ---------------------------------------------------------------- classes
def cmd_classes_list(cfg, args) -> int:
    rows = class_service.list_classes(cfg, keyword=args.keyword or "")
    _show(rows, ["班级", "专业", "年级", "班主任", "人数"],
          ["class_name", "major", "grade", "head_teacher", "students"])
    return 0


def cmd_classes_add(cfg, args) -> int:
    new_id = class_service.create(cfg, {
        "class_name": args.name, "major": args.major,
        "grade": args.grade, "head_teacher": args.teacher,
    })
    _ok(f"已新增班级，class_id={new_id}")
    return 0


def cmd_classes_edit(cfg, args) -> int:
    raw = {
        "class_name": args.name, "major": args.major,
        "grade": args.grade, "head_teacher": args.teacher,
    }
    raw = {key: value for key, value in raw.items() if value is not None}
    if not raw:
        print("没有要修改的字段", file=sys.stderr)
        return 2
    class_service.update(cfg, args.class_id, raw)
    _ok(f"已更新班级 class_id={args.class_id}")
    return 0


def cmd_classes_delete(cfg, args) -> int:
    class_service.delete(cfg, args.class_id)
    _ok(f"已删除班级 class_id={args.class_id}（学生保留，变成未分班）")
    return 0


# ---------------------------------------------------------------- scores
def cmd_scores_list(cfg, args) -> int:
    if args.page or args.size:
        result = score_service.page(
            cfg, student_id=args.student_id, course_id=args.course_id,
            term=args.term, keyword=args.keyword or "", only_missing=args.missing,
            order=args.sort, descending=args.desc,
            page=args.page or 1, size=args.size or 50,
        )
        _show(result["rows"], ["学号", "姓名", "课程", "学期", "成绩", "状态"],
              ["sno", "name", "course", "term", "score", "pass_state"],
              footer=f"第 {result['page']} / {result['pages']} 页 · 共 {result['total']} 条")
        return 0
    rows = score_service.list_scores(
        cfg, student_id=args.student_id, course_id=args.course_id,
        term=args.term, keyword=args.keyword or "", only_missing=args.missing,
        order=args.sort, descending=args.desc,
    )
    _show(rows, ["学号", "姓名", "课程", "学期", "成绩", "状态"],
          ["sno", "name", "course", "term", "score", "pass_state"])
    return 0


def cmd_scores_import(cfg, args) -> int:
    result = import_service.import_scores(cfg, args.file)
    print(f"共 {result['total']} 行，成功写入 {result['saved']} 行")
    if result["errors"]:
        print(f"{len(result['errors'])} 行有问题：")
        _print_errors(result["errors"])
        return 1
    return 0


def cmd_scores_set(cfg, args) -> int:
    action = score_service.save(cfg, args.student_id, args.course_id, args.term, args.score)
    word = "已录入" if action == "inserted" else "已更新"
    _ok(f"{word}成绩：student_id={args.student_id} course_id={args.course_id} "
        f"term={args.term} score={args.score if args.score is not None else '未录入'}")
    return 0


def cmd_scores_delete(cfg, args) -> int:
    score_service.delete(cfg, args.student_id, args.course_id, args.term)
    _ok("已删除该条成绩")
    return 0


# ---------------------------------------------------------------- stats
def cmd_stats_overview(cfg, args) -> int:
    info = reports.overview(cfg)
    rows = [
        {"k": "班级", "v": info["classes"]},
        {"k": "学生", "v": info["students"]},
        {"k": "课程", "v": info["courses"]},
        {"k": "成绩记录", "v": info["scores"]},
        {"k": "未录入", "v": info["missing"]},
        {"k": "总平均分", "v": info["avg_score"]},
    ]
    print(tablefmt.render(["项目", "数值"], [[r["k"], r["v"]] for r in rows]))
    print()
    return 0


def cmd_stats_classes(cfg, args) -> int:
    rows = reports.class_summary(cfg)
    _show(rows, ["班级", "年级", "人数", "已出分", "平均分"],
          ["class_name", "grade", "students", "graded", "avg_score"])
    return 0


def cmd_stats_courses(cfg, args) -> int:
    rows = reports.course_stats(cfg)
    _show(rows, ["课程号", "课程", "已出分", "平均", "最高", "最低", "及格率%"],
          ["cno", "course", "graded", "avg_score", "max_score", "min_score", "pass_rate"])
    return 0


def cmd_stats_ranking(cfg, args) -> int:
    rows = reports.ranking(cfg)
    _show(rows, ["学号", "姓名", "班级", "已出分", "学分", "加权平均"],
          ["sno", "name", "class_name", "graded", "credits", "weighted_avg"])
    return 0


# ---------------------------------------------------------------- export
def cmd_export(cfg, args) -> int:
    target = Path(args.out).expanduser().resolve()
    if args.what == "students":
        rows = student_service.list_students(cfg)
        headers = ["sno", "name", "gender", "class_name", "birthday", "phone", "email",
                   "enroll_date"]
    else:
        rows = score_service.list_scores(cfg)
        headers = ["sno", "name", "class_name", "course", "credit", "term", "score",
                   "pass_state"]
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    _ok(f"已导出 {len(rows)} 行 -> {target}")
    return 0


# ---------------------------------------------------------------- 解析
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="main.py cli", description="学生管理系统 · 命令行界面")
    sub = parser.add_subparsers(dest="group", required=True)

    # students
    students = sub.add_parser("students", help="学生管理")
    ssub = students.add_subparsers(dest="action", required=True)

    p = ssub.add_parser("list", help="浏览 / 搜索 / 排序")
    p.add_argument("--keyword", help="按学号、姓名、电话模糊搜索")
    p.add_argument("--class-id", type=int, help="只看某个班级")
    p.add_argument("--sort", default="sno", choices=["sno", "name", "gender", "class_name", "enroll_date"])
    p.add_argument("--desc", action="store_true", help="倒序")
    p.add_argument("--page", type=int, help="只看第 N 页（配合 --size）")
    p.add_argument("--size", type=int, help="每页条数，默认 50")
    p.set_defaults(func=cmd_students_list)

    p = ssub.add_parser("add", help="新增学生")
    p.add_argument("--sno", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--gender", required=True, choices=["男", "女"])
    p.add_argument("--birthday")
    p.add_argument("--phone")
    p.add_argument("--email")
    p.add_argument("--class-id", type=int)
    p.set_defaults(func=cmd_students_add)

    p = ssub.add_parser("edit", help="修改学生（只改给出的字段）")
    p.add_argument("student_id", type=int)
    p.add_argument("--sno")
    p.add_argument("--name")
    p.add_argument("--gender", choices=["男", "女"])
    p.add_argument("--birthday")
    p.add_argument("--phone")
    p.add_argument("--email")
    p.add_argument("--class-id", type=int)
    p.set_defaults(func=cmd_students_edit)

    p = ssub.add_parser("delete", help="删除学生（成绩级联删除）")
    p.add_argument("student_id", type=int)
    p.set_defaults(func=cmd_students_delete)

    p = ssub.add_parser("show", help="查看某学生的成绩单")
    p.add_argument("student_id", type=int)
    p.set_defaults(func=cmd_students_show)

    p = ssub.add_parser("import", help="从 CSV 批量导入学生")
    p.add_argument("--file", required=True, help="CSV 路径（列：学号,姓名,性别,班级,电话,邮箱,出生日期）")
    p.set_defaults(func=cmd_students_import)

    p = ssub.add_parser("template", help="导出学生导入模板")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_students_template)

    p = ssub.add_parser("transcript", help="导出成绩单（.csv 或 .html）")
    p.add_argument("student_id", type=int)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_students_transcript)

    # courses
    courses = sub.add_parser("courses", help="课程管理")
    csub = courses.add_subparsers(dest="action", required=True)

    p = csub.add_parser("list")
    p.add_argument("--keyword")
    p.add_argument("--sort", default="cno", choices=["cno", "title", "credit", "hours"])
    p.add_argument("--desc", action="store_true")
    p.set_defaults(func=cmd_courses_list)

    p = csub.add_parser("add")
    p.add_argument("--cno", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--credit", type=float)
    p.add_argument("--teacher")
    p.add_argument("--hours", type=int)
    p.set_defaults(func=cmd_courses_add)

    p = csub.add_parser("edit")
    p.add_argument("course_id", type=int)
    p.add_argument("--cno")
    p.add_argument("--title")
    p.add_argument("--credit", type=float)
    p.add_argument("--teacher")
    p.add_argument("--hours", type=int)
    p.set_defaults(func=cmd_courses_edit)

    p = csub.add_parser("delete")
    p.add_argument("course_id", type=int)
    p.set_defaults(func=cmd_courses_delete)

    # classes
    klasses = sub.add_parser("classes", help="班级管理")
    ksub = klasses.add_subparsers(dest="action", required=True)

    p = ksub.add_parser("list")
    p.add_argument("--keyword")
    p.set_defaults(func=cmd_classes_list)

    p = ksub.add_parser("add")
    p.add_argument("--name", required=True)
    p.add_argument("--major", required=True)
    p.add_argument("--grade", type=int, required=True)
    p.add_argument("--teacher")
    p.set_defaults(func=cmd_classes_add)

    p = ksub.add_parser("edit")
    p.add_argument("class_id", type=int)
    p.add_argument("--name")
    p.add_argument("--major")
    p.add_argument("--grade", type=int)
    p.add_argument("--teacher")
    p.set_defaults(func=cmd_classes_edit)

    p = ksub.add_parser("delete")
    p.add_argument("class_id", type=int)
    p.set_defaults(func=cmd_classes_delete)

    # scores
    scores = sub.add_parser("scores", help="成绩管理")
    ssub2 = scores.add_subparsers(dest="action", required=True)

    p = ssub2.add_parser("list")
    p.add_argument("--student-id", type=int)
    p.add_argument("--course-id", type=int)
    p.add_argument("--term")
    p.add_argument("--keyword")
    p.add_argument("--missing", action="store_true", help="只看未录入")
    p.add_argument("--sort", default="sno", choices=["sno", "name", "course", "term", "score", "class_name"])
    p.add_argument("--desc", action="store_true")
    p.add_argument("--page", type=int, help="只看第 N 页（配合 --size）")
    p.add_argument("--size", type=int, help="每页条数，默认 50")
    p.set_defaults(func=cmd_scores_list)

    p = ssub2.add_parser("set", help="录入或修改一条成绩（省略 --score 表示未录入）")
    p.add_argument("--student-id", type=int, required=True)
    p.add_argument("--course-id", type=int, required=True)
    p.add_argument("--term", required=True)
    p.add_argument("--score", type=float)
    p.set_defaults(func=cmd_scores_set)

    p = ssub2.add_parser("delete")
    p.add_argument("--student-id", type=int, required=True)
    p.add_argument("--course-id", type=int, required=True)
    p.add_argument("--term", required=True)
    p.set_defaults(func=cmd_scores_delete)

    p = ssub2.add_parser("import", help="从 CSV 批量导入成绩")
    p.add_argument("--file", required=True, help="CSV 路径（列：学号,课程号,学期,成绩）")
    p.set_defaults(func=cmd_scores_import)

    # stats
    stats = sub.add_parser("stats", help="统计报表")
    tsub = stats.add_subparsers(dest="action", required=True)
    for name, func, help_text in (
        ("overview", cmd_stats_overview, "总体概况"),
        ("classes", cmd_stats_classes, "按班级"),
        ("courses", cmd_stats_courses, "按课程"),
        ("ranking", cmd_stats_ranking, "加权平均分排行"),
    ):
        p = tsub.add_parser(name, help=help_text)
        p.set_defaults(func=func)

    # export
    export = sub.add_parser("export", help="导出 CSV")
    export.add_argument("--what", choices=["students", "scores"], default="students")
    export.add_argument("--out", required=True)
    export.set_defaults(func=cmd_export)

    return parser


def run(cfg, argv) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(cfg, args)
    except AppError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
