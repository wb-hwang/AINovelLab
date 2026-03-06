#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Material Design 风格的样式定义 - 暗色调版本

说明：QSS 已抽离到 resources/material_dark.qss；此模块仅负责读取并返回样式字符串。
"""

from pathlib import Path

_QSS_FILE = Path(__file__).resolve().parents[2] / "resources" / "material_dark.qss"


def get_material_style() -> str:
    """返回 Material Design 风格的暗色调样式表（QSS）。"""
    try:
        return _QSS_FILE.read_text(encoding="utf-8")
    except Exception:
        # 资源缺失时降级为空样式，避免启动失败
        return ""
