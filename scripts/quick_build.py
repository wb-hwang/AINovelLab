#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""临时打包脚本（兼容入口）。

说明：逻辑已收敛到 scripts/build.py；此文件保留为 wrapper。
"""

import sys
from pathlib import Path

def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build  # type: ignore

    return build.main(["--name", "AINovelLab_New", "--no-clean"])

if __name__ == "__main__":
    raise SystemExit(main())
