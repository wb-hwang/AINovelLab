#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
为应用程序提供基本的 Material Design 图标资源
"""

import sys
from pathlib import Path
from PyQt5.QtGui import QIcon


def _project_root() -> Path:
    # src/gui/resources.py -> gui -> src -> project root
    return Path(__file__).resolve().parents[2]


def _resource_base_dir() -> Path:
    # PyInstaller: 资源一般解包到 sys._MEIPASS；否则走项目根目录
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return _project_root()


def get_icon(name: str) -> QIcon:
    """按 name 从 resources/images 加载图标，找不到则返回空图标。

    说明：当前仓库未内置图标资源时，保持旧行为（返回空 QIcon），避免 UI 报错。
    """
    base = _resource_base_dir() / "resources" / "images"
    for ext in (".png", ".ico", ".svg"):
        p = base / f"{name}{ext}"
        if p.exists():
            return QIcon(str(p))
    return QIcon()
