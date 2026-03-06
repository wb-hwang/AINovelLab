#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""打包脚本（兼容入口）。

说明：原实现与 quick_build.py 重复度较高，已收敛到 scripts/build.py。
此文件保留为 wrapper，避免既有使用方式失效。
"""

import sys
from pathlib import Path

def main():
    # scripts 目录加入 sys.path，调用统一入口
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build  # type: ignore

    console_mode = input("是否需要显示控制台窗口以便调试(y/n)? [n]: ").lower() == 'y'
    argv = ["--name", "AINovelLab"]
    if console_mode:
        argv.append("--console")
    return build.main(argv)

if __name__ == "__main__":
    raise SystemExit(main())
