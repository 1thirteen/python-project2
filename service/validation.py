"""输入校验：接受界面传来的原始字符串，不合格就抛 ValidationError。"""

from __future__ import annotations

import re
from datetime import datetime

from common.errors import ValidationError

SNO_RE = re.compile(r"^[0-9]{4,20}$")
PHONE_RE = re.compile(r"^1[3-9][0-9]{9}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TERM_RE = re.compile(r"^[0-9]{4}-[0-9]{4}-[12]$")


def text(value, field: str, required: bool = True,
         min_len: int = 1, max_len: int = 50):
    if value is None or str(value).strip() == "":
        if required:
            raise ValidationError(f"{field}不能为空")
        return None
    value = str(value).strip()
    if len(value) < min_len:
        raise ValidationError(f"{field}至少 {min_len} 个字符")
    if len(value) > max_len:
        raise ValidationError(f"{field}最多 {max_len} 个字符")
    return value


def sno(value) -> str:
    value = text(value, "学号", max_len=20)
    if not SNO_RE.fullmatch(value):
        raise ValidationError("学号必须是 4–20 位数字")
    return value


def choice(value, field: str, options) -> str:
    value = text(value, field, max_len=20)
    if value not in options:
        raise ValidationError(f"{field}只能是：{' / '.join(options)}")
    return value


def date_text(value, field: str = "日期"):
    value = text(value, field, required=False, max_len=10)
    if value is None:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValidationError(f"{field}格式应为 YYYY-MM-DD") from None
    return value


def phone(value):
    value = text(value, "手机号", required=False, max_len=11)
    if value is None:
        return None
    if not PHONE_RE.fullmatch(value):
        raise ValidationError("手机号应为 11 位、以 1 开头")
    return value


def email(value):
    value = text(value, "邮箱", required=False, max_len=60)
    if value is None:
        return None
    if not EMAIL_RE.fullmatch(value):
        raise ValidationError("邮箱格式不正确")
    return value


def integer(value, field: str, minimum: int, maximum: int) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError(f"{field}必须是整数") from None
    if not minimum <= number <= maximum:
        raise ValidationError(f"{field}必须在 {minimum}–{maximum} 之间")
    return number


def real(value, field: str, minimum: float, maximum: float) -> float:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError(f"{field}必须是数字") from None
    if not minimum <= number <= maximum:
        raise ValidationError(f"{field}必须在 {minimum:g}–{maximum:g} 之间")
    return number


def score(value):
    """空值表示「未录入」，返回 None；否则 0–100 的浮点数。"""
    if value is None or str(value).strip() == "":
        return None
    return real(value, "成绩", 0, 100)


def term(value) -> str:
    value = text(value, "学期", max_len=11)
    if not TERM_RE.fullmatch(value):
        raise ValidationError("学期格式应为 2024-2025-1（学年起-学年止-学期）")
    return value


def ref_id(value, field: str):
    """可空外键：None / 空字符串 -> None；否则正整数。"""
    if value is None or str(value).strip() == "":
        return None
    number = integer(value, field, 1, 2 ** 31 - 1)
    return number
