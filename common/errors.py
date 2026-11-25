"""业务异常与数据库异常翻译：界面层只需要认识这里定义的几种错误。"""

from __future__ import annotations

import sqlite3


class AppError(Exception):
    """所有可直接展示给用户的错误的基类。"""


class ValidationError(AppError):
    """输入不合法（字段缺失、格式不对、超出取值范围）。"""


class NotFoundError(AppError):
    """按主键找不到记录。"""


class ConflictError(AppError):
    """与已有数据冲突（学号重复、外键不存在、成绩重复录入）。"""


def translate_integrity(exc: sqlite3.IntegrityError) -> AppError:
    """把 SQLite 的约束报错翻成中文提示，保留原文便于排查。"""
    message = str(exc)
    if "students.sno" in message:
        return ConflictError("学号已存在，请换一个")
    if "courses.cno" in message:
        return ConflictError("课程号已存在，请换一个")
    if "classes.class_name" in message:
        return ConflictError("班级名已存在，请换一个")
    if "scores.student_id, scores.course_id, scores.term" in message:
        return ConflictError("该学生在这个学期已经录过这门课的成绩")
    if "FOREIGN KEY" in message:
        return ConflictError("引用的班级、学生或课程不存在")
    if "NOT NULL" in message:
        return ValidationError("必填项没有填写")
    if "CHECK" in message:
        return ValidationError(f"数据不满足约束（{message}）")
    return AppError(f"数据库错误：{message}")
