"""CSV 导入：学生名册、成绩明细；逐行报错，不影响其它行。"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from common.errors import NotFoundError, ValidationError, translate_integrity
from common.log import get as get_logger
from service import students as student_service
from service import validation
from store import classes as class_store
from store import connection
from store import courses as course_store
from store import scores as score_store
from store import students as student_store

STUDENT_COLUMNS = {
    "学号": "sno", "姓名": "name", "性别": "gender", "班级": "class_name",
    "电话": "phone", "邮箱": "email", "出生日期": "birthday",
    "sno": "sno", "name": "name", "gender": "gender", "class_name": "class_name",
    "phone": "phone", "email": "email", "birthday": "birthday",
}

SCORE_COLUMNS = {
    "学号": "sno", "课程号": "cno", "学期": "term", "成绩": "score",
    "sno": "sno", "cno": "cno", "term": "term", "score": "score",
}

STUDENT_TEMPLATE = ["学号", "姓名", "性别", "班级", "电话", "邮箱", "出生日期"]
SCORE_TEMPLATE = ["学号", "课程号", "学期", "成绩"]


def _read(path, columns) -> tuple[list[tuple[int, dict]], dict]:
    text = Path(path).read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    headers = reader.fieldnames or []
    mapping = {}
    for header in headers:
        target = columns.get(header.strip())
        if target:
            mapping[header] = target
    if not mapping:
        raise ValidationError("CSV 没有可识别的列，请参考模板")
    rows = []
    for index, raw in enumerate(reader, start=2):   # 第 1 行是表头
        row = {target: (raw.get(header) or "").strip()
               for header, target in mapping.items()}
        if not any(row.values()):
            continue
        rows.append((index, row))
    return rows, mapping


def import_students(cfg, path) -> dict:
    """导入学生；返回 inserted / errors / total。"""
    rows, mapping = _read(path, STUDENT_COLUMNS)
    if "sno" not in mapping.values() or "name" not in mapping.values():
        raise ValidationError("学生 CSV 至少要有「学号」「姓名」两列")

    inserted, errors = 0, []
    with connection.session(cfg.db_path) as conn:
        class_map = {row["class_name"]: row["class_id"]
                     for row in class_store.options(conn)}
        for line, row in rows:
            class_name = row.get("class_name", "")
            payload = {
                "sno": row.get("sno", ""),
                "name": row.get("name", ""),
                "gender": row.get("gender", ""),
                "birthday": row.get("birthday", ""),
                "phone": row.get("phone", ""),
                "email": row.get("email", ""),
                "class_id": None,
            }
            try:
                if class_name:
                    if class_name not in class_map:
                        raise ValidationError(f"班级不存在：{class_name}")
                    payload["class_id"] = class_map[class_name]
                data = student_service.normalize_payload(payload, creating=True)
                student_store.create_student(conn, data)
                inserted += 1
            except (ValidationError, NotFoundError) as exc:
                errors.append((line, str(exc)))
            except sqlite3.IntegrityError as exc:
                errors.append((line, str(translate_integrity(exc))))
    get_logger().info("导入学生 %s：共 %s 行，成功 %s 行，失败 %s 行",
                      Path(path).name, len(rows), inserted, len(errors))
    return {"inserted": inserted, "errors": errors, "total": len(rows)}


def import_scores(cfg, path) -> dict:
    """导入成绩；学号 / 课程号 都要已存在，成绩留空表示未录入。"""
    rows, mapping = _read(path, SCORE_COLUMNS)
    missing = {"sno", "cno", "term"} - set(mapping.values())
    if missing:
        raise ValidationError("成绩 CSV 至少要有「学号」「课程号」「学期」三列")

    saved, errors = 0, []
    with connection.session(cfg.db_path) as conn:
        for line, row in rows:
            try:
                sno = validation.sno(row.get("sno"))
                cno = validation.text(row.get("cno"), "课程号", max_len=10).upper()
                term = validation.term(row.get("term"))
                value = validation.score(row.get("score"))
                student = student_store.find_by_sno(conn, sno)
                if student is None:
                    raise NotFoundError(f"学号 {sno} 不存在")
                course = course_store.find_by_cno(conn, cno)
                if course is None:
                    raise NotFoundError(f"课程号 {cno} 不存在")
                score_store.save_score(
                    conn, student["student_id"], course["course_id"], term, value
                )
                saved += 1
            except (ValidationError, NotFoundError) as exc:
                errors.append((line, str(exc)))
            except sqlite3.IntegrityError as exc:
                errors.append((line, str(translate_integrity(exc))))
    get_logger().info("导入成绩 %s：共 %s 行，成功 %s 行，失败 %s 行",
                      Path(path).name, len(rows), saved, len(errors))
    return {"saved": saved, "errors": errors, "total": len(rows)}


def write_template(path, kind: str) -> Path:
    """写一份带表头的 CSV 模板，方便直接照填。"""
    headers = STUDENT_TEMPLATE if kind == "students" else SCORE_TEMPLATE
    sample = (["20260301", "示例同学", "女", "2024级软件工程2班",
               "13800000010", "example@example.com", "2008-01-01"]
              if kind == "students"
              else ["20240101", "C001", "2024-2025-1", "88"])
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerow(sample)
    return target
