#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI小说工具 - 主程序入口

这个应用程序提供了图形用户界面，整合了以下三个功能：
1. 将EPUB文件分割为TXT文件
2. 对TXT文件进行脱水处理（压缩内容）
3. 将处理后的TXT文件重新转换为EPUB格式
"""

import os
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

# 导入辅助模块设置路径
try:
    from . import import_helper
except ImportError:
    import import_helper

# 设置导入路径
import_helper.setup_paths()

def main():
    """主函数"""
    try:
        # 导入GUI主窗口和样式
        from gui.main_window import MainWindow
        from gui.style import get_material_style
        
        # 创建应用程序实例
        app = QApplication(sys.argv)
        
        # 设置应用程序属性
        app.setAttribute(Qt.AA_UseHighDpiPixmaps)  # 使用高DPI图标
        
        # 应用 Material Design 样式表
        app.setStyleSheet(get_material_style())
        
        # 创建并显示主窗口
        window = MainWindow()
        window.show()
        
        # 启动应用程序的事件循环
        sys.exit(app.exec_())
    except ImportError as e:
        print(f"导入错误: {e}")
        print("请确保项目结构正确，并且所有依赖已安装")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"启动错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 