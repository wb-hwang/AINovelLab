#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI小说工具 - 主程序入口

这个应用程序提供了图形用户界面，整合了以下三个功能：
1. 将EPUB文件分割为TXT文件
2. 对TXT文件进行脱水处理（压缩内容）
3. 将处理后的TXT文件重新转换为EPUB格式
"""

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from src.gui.main_window import MainWindow
from src.gui.style import get_material_style


def main():
    """主函数"""
    # 创建应用程序实例
    app = QApplication(sys.argv)

    # 设置应用程序属性
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)

    # 应用 Material Design 样式表
    app.setStyleSheet(get_material_style())

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    # 启动应用程序的事件循环
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()