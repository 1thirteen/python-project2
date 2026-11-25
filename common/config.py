"""配置加载：config.json + 命令行覆盖；相对路径一律相对仓库根目录解析。"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULTS = {
    "app": {"title": "学生管理系统", "version": "1.0"},
    "database": {"path": "data/student.db", "schema": "db/schema.sql", "seed": "db/seed.sql"},
    "ui": {"page_size": 50, "window": [1180, 740], "font": "Microsoft YaHei UI 10"},
}


class ConfigError(Exception):
    """配置文件缺失、格式错误或取值不合法。"""


@dataclass(frozen=True)
class Config:
    root: Path
    db_path: Path
    schema_path: Path
    seed_path: Path
    title: str = "学生管理系统"
    version: str = "1.0"
    page_size: int = 50
    window: tuple[int, int] = (1180, 740)
    font: str = "Microsoft YaHei UI 10"

    def with_db(self, db_path) -> "Config":
        return replace(self, db_path=Path(db_path).resolve())


def _merge(base: dict, extra: dict) -> dict:
    merged = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _resolve(root: Path, value, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field} 必须是非空字符串")
    path = Path(value)
    return path if path.is_absolute() else (root / path)


def load(config_path=None, db_path=None) -> Config:
    """读取配置；config_path 缺省时用仓库根目录的 config.json（不存在则用默认值）。"""
    raw = DEFAULTS
    path = Path(config_path) if config_path else (ROOT / "config.json")
    if config_path or path.exists():
        try:
            raw = _merge(DEFAULTS, json.loads(path.read_text(encoding="utf-8")))
        except FileNotFoundError:
            raise ConfigError(f"配置文件不存在：{path}") from None
        except json.JSONDecodeError as exc:
            raise ConfigError(f"配置文件不是合法 JSON：{path}（{exc}）") from None

    try:
        page_size = int(raw["ui"]["page_size"])
        window = tuple(int(v) for v in raw["ui"]["window"])
    except (KeyError, TypeError, ValueError):
        raise ConfigError("ui.page_size / ui.window 格式不正确") from None
    if page_size <= 0:
        raise ConfigError("ui.page_size 必须是正整数")
    if len(window) != 2:
        raise ConfigError("ui.window 必须是 [宽, 高]")

    cfg = Config(
        root=ROOT,
        db_path=_resolve(ROOT, raw["database"]["path"], "database.path"),
        schema_path=_resolve(ROOT, raw["database"]["schema"], "database.schema"),
        seed_path=_resolve(ROOT, raw["database"]["seed"], "database.seed"),
        title=str(raw["app"].get("title") or "学生管理系统"),
        version=str(raw["app"].get("version") or "1.0"),
        page_size=page_size,
        window=window,
        font=str(raw["ui"].get("font") or "Microsoft YaHei UI 10"),
    )
    return cfg if db_path is None else cfg.with_db(db_path)
