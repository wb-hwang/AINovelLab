#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统一打包脚本（PyInstaller）。

说明：
- 原 scripts/build_exe.py 与 scripts/quick_build.py 存在大量重复逻辑；
- 此脚本提供统一入口，旧脚本保留为 thin wrapper 以兼容现有使用方式。
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def _project_root() -> Path:
    # scripts/build.py -> scripts -> project root
    return Path(__file__).resolve().parents[1]


def _data_sep() -> str:
    return ";" if platform.system() == "Windows" else ":"


def _ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("未检测到 PyInstaller，请先安装 requirements.txt") from e


def _clean_artifacts(root: Path, name: str) -> None:
    for d in ("build", "dist"):
        p = root / d
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)

    spec = root / f"{name}.spec"
    if spec.exists():
        try:
            spec.unlink()
        except Exception:
            pass


def _pyinstaller_cmd(root: Path, name: str, console: bool) -> list[str]:
    sep = _data_sep()
    add_data = [
        (root / "resources", "resources"),
        (root / "data", "data"),
        (root / "config", "config"),
        (root / "api_keys.json", "."),
        (root / "src", "src"),
    ]

    cmd = ["pyinstaller", f"--name={name}"]
    if not console:
        cmd.append("--windowed")

    for src, dst in add_data:
        if src.exists():
            cmd.append(f"--add-data={src}{sep}{dst}")

    cmd.extend(
        [
            "--hidden-import=PyQt5",
            "--hidden-import=PyQt5.QtWidgets",
            "--hidden-import=PyQt5.QtCore",
            "--hidden-import=PyQt5.QtGui",
            "--hidden-import=ebooklib",
            "--hidden-import=ebooklib.epub",
            "--hidden-import=bs4",
            "--hidden-import=bs4.builder",
            "--hidden-import=tqdm",
            "--hidden-import=requests",
            "--hidden-import=lxml",
            "--noconfirm",
            "--clean",
            "run.py",
        ]
    )
    return cmd


def _write_api_keys_template(dist_dir: Path) -> None:
    template_config = {
        "gemini_api": [
            {
                "name": "",
                "key": "你的gemini 密钥",
                "redirect_url": "代理url 地址，可空。默认：https://generativelanguage.googleapis.com/v1beta/models",
                "model": "模型，可空。默认：gemini-2.0-flash",
                "rpm": 10,
            },
            {"name": "", "key": "最简配置demo"},
        ],
        "openai_api": [
            {
                "name": "",
                "key": "你的openai 密钥或其他一切兼容openai-api 格式的,如DeepSeek等",
                "redirect_url": "代理url，可空。默认：https://api.openai.com/v1/chat/completions",
                "model": "模型，可空。默认：gpt-3.5-turbo",
                "rpm": 10,
            },
            {"name": "", "key": "最简配置demo"},
        ],
        "max_rpm": 20,
    }

    dist_dir.mkdir(parents=True, exist_ok=True)
    template_path = dist_dir / "api_keys.json"
    try:
        template_path.write_text(json.dumps(template_config, ensure_ascii=False, indent=4), encoding="utf-8")
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AINovelLab PyInstaller 打包脚本")
    parser.add_argument("--name", default="AINovelLab", help="输出程序名（默认：AINovelLab）")
    parser.add_argument("--console", action="store_true", help="显示控制台窗口（默认不显示）")
    parser.add_argument("--no-clean", action="store_true", help="不清理 build/dist/spec（适合快速迭代）")
    args = parser.parse_args(argv)

    root = _project_root()
    os.chdir(root)

    _ensure_pyinstaller()
    if not args.no_clean:
        _clean_artifacts(root, args.name)

    cmd = _pyinstaller_cmd(root, args.name, console=args.console)
    subprocess.check_call(cmd)

    _write_api_keys_template(root / "dist" / args.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

