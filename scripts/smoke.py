#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
最小回归脚本（不依赖网络）：
- TXT -> EPUB：生成临时输入，调用核心合并函数，校验输出 epub 的基本结构
- 配置路径：校验能返回 api_keys.json 路径字符串
"""

from __future__ import annotations

import os
import shutil
import uuid
import zipfile
from pathlib import Path


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def smoke_config_paths() -> None:
    from src.core.novel_condenser import config as nc_config

    path = nc_config.get_config_file_path()
    _assert(isinstance(path, str) and path, "get_config_file_path() 应返回非空字符串")
    _assert(path.replace("\\", "/").endswith("/api_keys.json"), f"配置文件名应为 api_keys.json，实际: {path}")


def smoke_txt_to_epub() -> None:
    from src.core import txt_to_epub

    project_root = Path(__file__).resolve().parents[1]
    tmp_root = project_root / "tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    root = tmp_root / f"ainovellab-smoke-{uuid.uuid4().hex}"
    try:
        in_dir = root / "input"
        out_file = root / "out.epub"
        in_dir.mkdir(parents=True, exist_ok=True)

        # 使用项目默认解析器可识别的命名格式：小说名称_[序号]_章节名称.txt
        (in_dir / "示例小说_[1]_第一章.txt").write_text("第一章\n\n这是第一章内容。", encoding="utf-8")
        (in_dir / "示例小说_[2]_第二章.txt").write_text("第二章\n\n这是第二章内容。", encoding="utf-8")

        result = txt_to_epub.merge_txt_to_epub(str(in_dir), output_path=str(out_file), author="测试作者", novel_name="示例小说")
        _assert(result, "merge_txt_to_epub() 应返回输出路径")

        out_path = Path(result)
        _assert(out_path.exists(), f"输出 epub 不存在: {out_path}")
        _assert(out_path.stat().st_size > 1024, f"输出 epub 过小，可能写出失败: size={out_path.stat().st_size}")

        with zipfile.ZipFile(out_path, "r") as zf:
            names = set(zf.namelist())
            _assert("mimetype" in names, "epub zip 应包含 mimetype")
            # ebooklib 输出的 OPF/内容目录可能不同，但 container.xml 是必须的
            _assert("META-INF/container.xml" in names, "epub zip 应包含 META-INF/container.xml")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    # 让 src/ 可被直接导入（与 run.py 保持一致）
    project_root = Path(__file__).resolve().parents[1]
    os.sys.path.insert(0, str(project_root))

    smoke_config_paths()
    smoke_txt_to_epub()

    print("smoke: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
