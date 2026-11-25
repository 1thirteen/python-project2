"""浅色 / 深色两套主题：统一 ttk 样式，并把偏好记在 data/ui.json。"""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk

LIGHT = {
    "name": "light",
    "bg": "#f5f6f8",
    "panel": "#ffffff",
    "fg": "#1f2937",
    "muted": "#6b7280",
    "border": "#e5e7eb",
    "accent": "#2563eb",
    "accent_fg": "#ffffff",
    "hover": "#eef2ff",
    "stripe": "#eef2f8",
    "select_bg": "#dbeafe",
    "select_fg": "#1e3a8a",
    "heading_bg": "#f1f5f9",
    "heading_fg": "#475569",
    "danger": "#b91c1c",
    "warning": "#b45309",
    "success": "#047857",
    "entry_bg": "#ffffff",
    "pressed": "#dbe4f0",
}

DARK = {
    "name": "dark",
    "bg": "#0f172a",
    "panel": "#1e293b",
    "fg": "#e2e8f0",
    "muted": "#94a3b8",
    "border": "#334155",
    "accent": "#3b82f6",
    "accent_fg": "#ffffff",
    "hover": "#273449",
    "stripe": "#16203a",
    "select_bg": "#1d4ed8",
    "select_fg": "#ffffff",
    "heading_bg": "#1e293b",
    "heading_fg": "#cbd5e1",
    "danger": "#f87171",
    "warning": "#fbbf24",
    "success": "#34d399",
    "entry_bg": "#0f172a",
    "pressed": "#1e3a8a",
}

PALETTES = {"light": LIGHT, "dark": DARK}


def prefs_path(cfg) -> Path:
    return Path(cfg.db_path).parent / "ui.json"


def load_mode(cfg) -> str:
    path = prefs_path(cfg)
    try:
        mode = json.loads(path.read_text(encoding="utf-8")).get("theme", "light")
    except (OSError, ValueError):
        return "light"
    return mode if mode in PALETTES else "light"


def save_mode(cfg, mode: str) -> None:
    path = prefs_path(cfg)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data["theme"] = mode if mode in PALETTES else "light"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass   # 写不了偏好不影响使用


class Theme:
    """把调色板套到 ttk 样式上；切换时重新 configure 即可。"""

    def __init__(self, root, cfg, mode: str = "light"):
        self.root = root
        self.cfg = cfg
        self.style = ttk.Style(root)
        self.mode = "light"
        self.palette = LIGHT
        self.apply(mode)

    def apply(self, mode: str) -> dict:
        self.mode = mode if mode in PALETTES else "light"
        palette = self.palette = PALETTES[self.mode]
        style = self.style
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=palette["bg"], foreground=palette["fg"],
                        fieldbackground=palette["entry_bg"], font=("Microsoft YaHei UI", 10))
        style.configure("TFrame", background=palette["bg"])
        style.configure("Panel.TFrame", background=palette["panel"])
        style.configure("TLabel", background=palette["bg"], foreground=palette["fg"])
        style.configure("Muted.TLabel", background=palette["bg"], foreground=palette["muted"])
        style.configure("Title.TLabel", background=palette["bg"], foreground=palette["fg"],
                        font=("Microsoft YaHei UI", 14, "bold"))
        style.configure("Status.TLabel", background=palette["panel"],
                        foreground=palette["muted"], padding=(10, 5))
        style.configure("Head.TLabel", background=palette["bg"], foreground=palette["muted"],
                        font=("Microsoft YaHei UI", 9))
        style.configure("TLabelframe", background=palette["bg"], bordercolor=palette["border"])
        style.configure("TLabelframe.Label", background=palette["bg"],
                        foreground=palette["muted"])

        style.configure("TButton", background=palette["panel"], foreground=palette["fg"],
                        bordercolor=palette["border"], padding=(10, 4), relief="flat")
        style.map("TButton",
                  background=[("pressed", palette["pressed"]), ("active", palette["hover"])],
                  foreground=[("disabled", palette["muted"])])
        style.configure("Accent.TButton", background=palette["accent"],
                        foreground=palette["accent_fg"], bordercolor=palette["accent"],
                        padding=(12, 4), relief="flat")
        style.map("Accent.TButton",
                  background=[("pressed", palette["pressed"]), ("active", palette["hover"])],
                  foreground=[("disabled", palette["muted"])])

        style.configure("TEntry", fieldbackground=palette["entry_bg"],
                        foreground=palette["fg"], insertcolor=palette["fg"],
                        bordercolor=palette["border"], padding=3)
        style.map("TEntry", fieldbackground=[("readonly", palette["stripe"])])
        style.configure("TCombobox", fieldbackground=palette["entry_bg"],
                        background=palette["panel"], foreground=palette["fg"],
                        arrowcolor=palette["fg"], bordercolor=palette["border"], padding=3)
        style.map("TCombobox",
                  fieldbackground=[("readonly", palette["entry_bg"])],
                  selectbackground=[("readonly", palette["select_bg"])],
                  selectforeground=[("readonly", palette["select_fg"])])
        self.root.option_add("*TCombobox*Listbox.background", palette["entry_bg"])
        self.root.option_add("*TCombobox*Listbox.foreground", palette["fg"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", palette["select_bg"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", palette["select_fg"])

        style.configure("TCheckbutton", background=palette["bg"], foreground=palette["fg"])
        style.map("TCheckbutton", background=[("active", palette["bg"])])

        style.configure("Treeview", background=palette["panel"],
                        fieldbackground=palette["panel"], foreground=palette["fg"],
                        bordercolor=palette["border"], rowheight=26,
                        font=("Microsoft YaHei UI", 10))
        style.configure("Treeview.Heading", background=palette["heading_bg"],
                        foreground=palette["heading_fg"], relief="flat",
                        font=("Microsoft YaHei UI", 10, "bold"), padding=(6, 4))
        style.map("Treeview",
                  background=[("selected", palette["select_bg"])],
                  foreground=[("selected", palette["select_fg"])])
        style.map("Treeview.Heading", background=[("active", palette["hover"])])

        style.configure("TNotebook", background=palette["bg"], bordercolor=palette["border"])
        style.configure("TNotebook.Tab", background=palette["panel"],
                        foreground=palette["muted"], padding=(16, 6))
        style.map("TNotebook.Tab",
                  background=[("selected", palette["bg"])],
                  foreground=[("selected", palette["fg"])])
        style.configure("Vertical.TScrollbar", background=palette["panel"],
                        troughcolor=palette["bg"], arrowcolor=palette["muted"],
                        bordercolor=palette["border"])
        style.configure("TSeparator", background=palette["border"])

        self.root.configure(bg=palette["bg"])
        return palette

    def tag_colors(self, tree) -> None:
        palette = self.palette
        tree.tag_configure("odd", background=palette["stripe"])
        tree.tag_configure("even", background=palette["panel"])
        tree.tag_configure("fail", foreground=palette["danger"])
        tree.tag_configure("missing", foreground=palette["warning"])
