"""配置加载：默认值、命令行覆盖、非法配置。"""

import json
import unittest
from pathlib import Path

from common import config
from common.config import ConfigError, ROOT
from tests.support import temp_dir


class ConfigTest(unittest.TestCase):
    def test_repo_config(self):
        cfg = config.load()
        self.assertEqual(cfg.db_path, ROOT / "data" / "student.db")
        self.assertEqual(cfg.schema_path, ROOT / "db" / "schema.sql")
        self.assertEqual(cfg.seed_path, ROOT / "db" / "seed.sql")
        self.assertEqual(cfg.page_size, 50)
        self.assertEqual(cfg.page_size_options, (20, 50, 100, 200))
        self.assertEqual(cfg.theme, "light")
        self.assertEqual(len(cfg.window), 2)

    def test_db_path_override(self):
        cfg = config.load(db_path="tmp/other.db")
        self.assertEqual(cfg.db_path.name, "other.db")
        self.assertTrue(cfg.db_path.is_absolute())

    def test_absolute_db_path_kept(self):
        with temp_dir() as tmp:
            target = tmp / "abs.db"
            self.assertEqual(config.load(db_path=str(target)).db_path, target)

    def test_missing_file(self):
        with self.assertRaises(ConfigError):
            config.load(str(ROOT / "nope" / "config.json"))

    def test_bad_json(self):
        with temp_dir() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{ not json", encoding="utf-8")
            with self.assertRaises(ConfigError):
                config.load(str(path))

    def test_invalid_page_size(self):
        with temp_dir() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps({"ui": {"page_size": 0}}), encoding="utf-8")
            with self.assertRaises(ConfigError):
                config.load(str(path))

    def test_partial_config_merges_defaults(self):
        with temp_dir() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps({"app": {"title": "另一个标题"}}), encoding="utf-8")
            cfg = config.load(str(path))
            self.assertEqual(cfg.title, "另一个标题")
            self.assertEqual(cfg.db_path, ROOT / "data" / "student.db")

    def test_invalid_theme(self):
        with temp_dir() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps({"ui": {"theme": "rainbow"}}), encoding="utf-8")
            with self.assertRaises(ConfigError):
                config.load(str(path))

    def test_invalid_page_size_options(self):
        with temp_dir() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps({"ui": {"page_size_options": []}}), encoding="utf-8")
            with self.assertRaises(ConfigError):
                config.load(str(path))

    def test_page_size_options_are_sorted_and_deduplicated(self):
        with temp_dir() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps({"ui": {"page_size_options": [100, 20, 100]}}),
                            encoding="utf-8")
            self.assertEqual(config.load(str(path)).page_size_options, (20, 100))


if __name__ == "__main__":
    unittest.main()
