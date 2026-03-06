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


def _pyinstaller_cmd(root: Path, name: str, console: bool) -> list[str]:
    sep = _data_sep()
    add_data = [
        (root / "resources", "resources"),
        (root / "data", "data"),
        (root / "config", "config"),
        (root / "src", "src"),
    ]

    cmd = ["pyinstaller", f"--name={name}"]
    if not console:
        cmd.append("--windowed")

    for src, dst in add_data:
        if src.exists():
            cmd.append(f"--add-data={src}{sep}{dst}")

    cmd.append(f"--specpath={root / 'build' / 'pyinstaller-spec'}")

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
            "--exclude-module=matplotlib",
            "--exclude-module=numpy",
            "--exclude-module=pandas",
            "--exclude-module=scipy",
            "--exclude-module=tensorboard",
            "--exclude-module=torch",
            "--noconfirm",
            "--clean",
            "run.py",
        ]
    )
    return cmd

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
