"""测试工具：每个用例一套独立的临时数据库。

注：临时目录用普通 mkdir 创建后放在仓库内，不用 tempfile.mkdtemp——
mkdtemp 会把目录权限收紧到 0o700，在受限的沙箱里反而导致 sqlite 无法在里面建库。
"""

from __future__ import annotations

import io
import shutil
import uuid
from contextlib import contextmanager, redirect_stderr, redirect_stdout

from common.config import ROOT, Config
from store import connection

TMP_ROOT = ROOT / ".tmp-tests"


def _make_dir(prefix: str):
    TMP_ROOT.mkdir(exist_ok=True)
    path = TMP_ROOT / f"{prefix}{uuid.uuid4().hex[:8]}"
    path.mkdir()
    return path


@contextmanager
def temp_dir():
    path = _make_dir("t-")
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class TempDatabase:
    """上下文管理器：建一个临时库并按 schema + seed 初始化。"""

    def __init__(self):
        self._dir = None

    def __enter__(self) -> Config:
        self._dir = _make_dir("db-")
        self.path = self._dir / "test.db"
        self.cfg = Config(
            root=ROOT,
            db_path=self.path,
            schema_path=ROOT / "db" / "schema.sql",
            seed_path=ROOT / "db" / "seed.sql",
        )
        connection.init_database(self.cfg.db_path, self.cfg.schema_path, self.cfg.seed_path)
        return self.cfg

    def __exit__(self, *exc_info):
        if self._dir is not None:
            shutil.rmtree(self._dir, ignore_errors=True)


def run_cli(cfg, argv) -> tuple[int, str, str]:
    """执行命令行子命令，返回 (退出码, 标准输出, 标准错误)。"""
    from ui.cli_app import run

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = run(cfg, argv)
    return code, out.getvalue(), err.getvalue()


def run_main(argv) -> tuple[int, str, str]:
    """执行 main.py 的入口，返回 (退出码, 标准输出, 标准错误)。"""
    import main

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main.main(argv)
    return code, out.getvalue(), err.getvalue()
