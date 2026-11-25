"""连接管理与建库：每个连接都必须打开外键开关。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from common.log import get as get_logger


def connect(db_path) -> sqlite3.Connection:
    """打开一个连接：行工厂 + 外键开关 + 忙等超时。"""
    path = str(db_path)
    if path != ":memory:":
        Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def session(db_path):
    """一次业务操作 = 一个事务：成功提交，异常回滚，最后关闭。"""
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database(db_path, schema_path, seed_path=None) -> dict:
    """按 schema.sql 重建库（表、视图、触发器、索引），可选灌入 seed.sql。"""
    schema = Path(schema_path).read_text(encoding="utf-8")
    seed = Path(seed_path).read_text(encoding="utf-8") if seed_path else None
    conn = connect(db_path)
    try:
        conn.executescript(schema)
        if seed:
            conn.executescript(seed)
        conn.commit()
        info = counts(conn)
        get_logger().info("建库完成 %s：%s", db_path, info)
        return info
    finally:
        conn.close()


def counts(conn: sqlite3.Connection) -> dict:
    """各表行数，用于建库后的自检与状态栏。"""
    result = {}
    for table in ("classes", "students", "courses", "scores"):
        result[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return result


def table_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'students'"
    ).fetchone()
    return row is not None
