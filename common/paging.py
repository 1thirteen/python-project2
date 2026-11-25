"""分页计算：把「第几页」夹到合法范围，并算出 offset。"""

from __future__ import annotations


def clamp(page, size, total: int) -> tuple[int, int, int]:
    """返回 (page, pages, offset)；total 为 0 时是 1 页。"""
    size = max(1, int(size))
    total = max(0, int(total))
    pages = max(1, (total + size - 1) // size)
    page = min(max(1, int(page)), pages)
    return page, pages, (page - 1) * size
