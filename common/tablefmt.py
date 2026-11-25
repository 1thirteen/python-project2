"""把查询结果打印成终端表格（按东亚字符宽度对齐）。"""

from __future__ import annotations

import unicodedata


def _width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def render(headers, rows) -> str:
    """返回可直接 print 的等宽表格文本。"""
    body = [[_cell(v) for v in row] for row in rows]
    cells = [list(headers)] + body
    widths = [max(_width(str(row[i])) for row in cells) for i in range(len(headers))]

    def line(values):
        return "| " + " | ".join(
            str(v) + " " * (widths[i] - _width(str(v))) for i, v in enumerate(values)
        ) + " |"

    separator = "| " + " | ".join("-" * w for w in widths) + " |"
    return "\n".join([line([str(h) for h in headers]), separator] + [line(r) for r in body])
