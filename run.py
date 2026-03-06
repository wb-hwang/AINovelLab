#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI小说工具启动脚本
"""

import os
import sys
import traceback


def main():
    """主入口函数"""
    # 将项目根目录加入 sys.path，使所有模块可以通过 src.xxx / config.xxx 导入
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    try:
        from src.main import main as start_app
        start_app()
    except ImportError as e:
        print(f"错误: 无法导入核心模块，请检查项目结构。详细错误: {e}")
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"启动错误: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()