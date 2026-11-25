#!/usr/bin/env python3
"""学生管理系统入口。

    python main.py                 # 打开 Tkinter 图形界面
    python main.py init [--reset]  # 建库（--reset 重建表并灌入示例数据）
    python main.py cli ...         # 命令行界面，见 python main.py cli -h
"""

from __future__ import annotations

import argparse
import sys

from common import config, log as log_module
from common.config import ConfigError
from common.errors import AppError
from store import connection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="课题2 · 学生管理系统（SQLite + Tkinter）",
    )
    parser.add_argument("--db", help="数据库文件路径（默认取 config.json 的 database.path）")
    parser.add_argument("--config", help="配置文件路径（默认仓库根目录 config.json）")
    parser.add_argument("command", nargs="?", default="", help="init 或 cli")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="子命令参数")
    return parser


def _load(args) -> config.Config:
    try:
        return config.load(args.config, args.db)
    except ConfigError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        raise SystemExit(2)


def cmd_init(cfg, argv) -> int:
    reset = "--reset" in argv
    if not cfg.schema_path.exists():
        print(f"找不到建表脚本：{cfg.schema_path}", file=sys.stderr)
        return 2
    if cfg.db_path.exists() and not reset:
        conn = connection.connect(cfg.db_path)
        try:
            ready = connection.table_exists(conn)
            info = connection.counts(conn) if ready else {}
        finally:
            conn.close()
        if ready:
            print(f"数据库已存在：{cfg.db_path}")
            print(f"  班级 {info['classes']}，学生 {info['students']}，"
                  f"课程 {info['courses']}，成绩 {info['scores']}")
            print("如需重建并灌入示例数据，请加 --reset")
            return 0
    info = connection.init_database(
        cfg.db_path, cfg.schema_path, cfg.seed_path if cfg.seed_path.exists() else None
    )
    print(f"已初始化：{cfg.db_path}")
    print(f"  班级 {info['classes']}，学生 {info['students']}，"
          f"课程 {info['courses']}，成绩 {info['scores']}")
    return 0


def cmd_gui(cfg) -> int:
    from ui.tk_app import run

    return run(cfg)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = _load(args)
    log = log_module.setup()
    log.info("启动：command=%s db=%s", args.command or "gui", cfg.db_path)

    try:
        if args.command == "init":
            return cmd_init(cfg, args.args)
        if args.command == "cli":
            from ui.cli_app import run as run_cli

            return run_cli(cfg, args.args)
        if args.command in ("", "gui"):
            return cmd_gui(cfg)
        print(f"未知命令：{args.command}（可用：init / cli / gui）", file=sys.stderr)
        return 2
    except AppError as exc:
        log.warning("业务错误：%s", exc)
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n已取消", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
