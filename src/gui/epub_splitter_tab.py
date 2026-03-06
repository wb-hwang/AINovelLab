#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
小说处理工具的EPUB分割标签页
"""

import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                           QFileDialog, QMessageBox, QProgressBar, QTextEdit,
                           QSpinBox, QGroupBox, QLineEdit, QCheckBox, QFrame, QSplitter)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont

from .worker import WorkerThread
from .ui_components import (
    create_stat_card,
    set_label_state,
    show_completion_dialog,
    show_error_message,
    style_button,
)

class EpubSplitterTab(QWidget):
    """EPUB分割器标签页"""
    
    # 定义信号，分割完成后发送书名目录和分割结果目录
    split_complete = pyqtSignal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker_thread = None
        self.book_base_dir = ""  # 保存书名目录路径
        self.init_ui()
    
    def init_ui(self):
        """初始化用户界面"""
        # 创建布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(8)
        self.summary_source_card = create_stat_card("源文件", "尚未选择")
        self.summary_output_card = create_stat_card("输出目录", "尚未设置")
        self.summary_split_card = create_stat_card("分卷设置", f"{self.chapters_per_file_spin.value() if hasattr(self, 'chapters_per_file_spin') else 1} 章/文件")
        self.summary_status_card = create_stat_card("状态", "就绪")
        summary_layout.addWidget(self.summary_source_card, 3)
        summary_layout.addWidget(self.summary_output_card, 3)
        summary_layout.addWidget(self.summary_split_card, 1)
        summary_layout.addWidget(self.summary_status_card, 1)
        main_layout.addLayout(summary_layout)

        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setChildrenCollapsible(False)
        
        left_panel = QVBoxLayout()
        left_panel.setSpacing(8)

        # EPUB文件选择
        file_group = QGroupBox("选择EPUB文件")
        file_layout = QHBoxLayout()
        
        self.epub_path_edit = QLineEdit()
        self.epub_path_edit.setReadOnly(True)
        self.epub_path_edit.setPlaceholderText("请选择EPUB文件...")
        
        browse_button = QPushButton("浏览...")
        style_button(browse_button, "secondary")
        browse_button.clicked.connect(self.browse_epub_file)
        
        file_layout.addWidget(self.epub_path_edit)
        file_layout.addWidget(browse_button)
        file_group.setLayout(file_layout)
        
        # 输出目录选择
        output_group = QGroupBox("输出目录")
        output_layout = QHBoxLayout()
        
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setReadOnly(True)
        self.output_dir_edit.setPlaceholderText("请选择输出目录...")
        
        browse_output_button = QPushButton("浏览...")
        style_button(browse_output_button, "secondary")
        browse_output_button.clicked.connect(self.browse_output_dir)
        
        output_layout.addWidget(self.output_dir_edit)
        output_layout.addWidget(browse_output_button)
        output_group.setLayout(output_layout)
        
        # 选项设置
        options_group = QGroupBox("分割选项")
        options_layout = QHBoxLayout()
        
        self.chapters_per_file_label = QLabel("每个文件章节数:")
        self.chapters_per_file_spin = QSpinBox()
        self.chapters_per_file_spin.setRange(1, 1000)
        self.chapters_per_file_spin.setValue(1)
        self.chapters_per_file_spin.valueChanged.connect(self.refresh_summary)
        
        options_layout.addWidget(self.chapters_per_file_label)
        options_layout.addWidget(self.chapters_per_file_spin)
        options_layout.addStretch()
        options_group.setLayout(options_layout)
        
        # 状态和进度
        status_group = QGroupBox("状态")
        status_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.status_label = QLabel("就绪")
        set_label_state(self.status_label, "muted")
        
        status_layout.addWidget(self.progress_bar)
        status_layout.addWidget(self.status_label)
        status_group.setLayout(status_layout)

        # 操作按钮
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("开始分割")
        style_button(self.start_button, "primary")
        self.start_button.clicked.connect(self.start_splitting)
        
        button_layout.addStretch()
        button_layout.addWidget(self.start_button)
        
        left_panel.addWidget(file_group)
        left_panel.addWidget(output_group)
        left_panel.addWidget(options_group)
        left_panel.addWidget(status_group)
        left_panel.addLayout(button_layout)

        # 添加日志显示区域
        right_panel = QVBoxLayout()

        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier New", 9))
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        self.log_text.setPlaceholderText("运行后会在这里显示拆分进度、输出目录与异常信息。")
        
        log_buttons_layout = QHBoxLayout()
        self.auto_scroll_checkbox = QCheckBox("自动滚动")
        self.auto_scroll_checkbox.setToolTip("勾选后日志会自动滚动到底部，取消勾选则保持当前位置")
        self.auto_scroll_checkbox.setChecked(False)

        self.line_wrap_checkbox = QCheckBox("自动换行")
        self.line_wrap_checkbox.setToolTip("勾选后文本会自动换行显示，取消勾选则需要水平滚动查看")
        self.line_wrap_checkbox.setChecked(False)
        self.line_wrap_checkbox.stateChanged.connect(self.toggle_line_wrap)
        
        self.clear_log_button = QPushButton("清除日志")
        style_button(self.clear_log_button, "ghost")
        self.clear_log_button.clicked.connect(self.clear_log)
        
        log_buttons_layout.addWidget(self.auto_scroll_checkbox)
        log_buttons_layout.addWidget(self.line_wrap_checkbox)
        log_buttons_layout.addStretch()
        log_buttons_layout.addWidget(self.clear_log_button)
        
        log_layout.addWidget(self.log_text)
        log_layout.addLayout(log_buttons_layout)
        log_group.setLayout(log_layout)

        right_panel.addWidget(log_group, 1)

        left_frame = QFrame()
        left_frame.setObjectName("left_frame")
        left_frame.setLayout(left_panel)

        right_frame = QFrame()
        right_frame.setObjectName("right_frame")
        right_frame.setLayout(right_panel)

        content_splitter.addWidget(left_frame)
        content_splitter.addWidget(right_frame)
        content_splitter.setStretchFactor(0, 4)
        content_splitter.setStretchFactor(1, 5)
        content_splitter.setSizes([460, 640])

        main_layout.addWidget(content_splitter, 1)
        
        self.setLayout(main_layout)
        self.refresh_summary()

    def refresh_summary(self):
        """刷新顶部摘要信息。"""
        full_source_path = self.epub_path_edit.text().strip()
        full_output_path = self.output_dir_edit.text().strip()
        self._set_stat_value(
            self.summary_source_card,
            self._compact_path(full_source_path, "尚未选择"),
            full_source_path or None,
        )
        self._set_stat_value(
            self.summary_output_card,
            self._compact_path(full_output_path, "尚未设置"),
            full_output_path or None,
        )
        self._set_stat_value(self.summary_split_card, f"{self.chapters_per_file_spin.value()} 章/文件")
        self._set_stat_value(self.summary_status_card, self.status_label.text() or "就绪")

    def _set_stat_value(self, card: QFrame, text: str, tooltip: str | None = None):
        value_label = card.findChild(QLabel, "statCardValue")
        if value_label is not None:
            value_label.setText(text)
            value_label.setToolTip(tooltip or "")
        card.setToolTip(tooltip or "")

    def _compact_path(self, path: str, fallback: str) -> str:
        if not path:
            return fallback
        normalized = path.replace("\\", "/")
        if len(normalized) <= 42:
            return normalized
        return f".../{'/'.join(normalized.split('/')[-3:])}"
    
    def add_log(self, message):
        """添加日志到日志显示区域"""
        self.log_text.append(message.rstrip())
        
        # 只在启用自动滚动时，才滚动到底部
        if self.auto_scroll_checkbox.isChecked():
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def clear_log(self):
        """清除日志显示区域的内容"""
        self.log_text.clear()
    
    def browse_epub_file(self):
        """浏览并选择EPUB文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择EPUB文件", "", "EPUB文件 (*.epub)"
        )
        if file_path:
            self.epub_path_edit.setText(file_path)
            
            # 获取EPUB文件名（不含扩展名）
            file_dir = os.path.dirname(file_path)
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            
            # 创建书名目录
            self.book_base_dir = os.path.join(file_dir, file_name)
            
            # 设置默认输出目录为"文件路径\文件名\splitted"
            output_dir = os.path.join(self.book_base_dir, "splitted")
            
            # 如果目录不存在，创建目录
            if not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir)
                except Exception as e:
                    QMessageBox.warning(self, "警告", f"无法创建输出目录: {str(e)}")
                    # 如果创建失败，使用EPUB文件所在目录作为默认输出目录
                    output_dir = file_dir
                    self.book_base_dir = file_dir
            
            self.output_dir_edit.setText(output_dir)
            self.refresh_summary()
            # 添加日志
            self.add_log(f"设置默认输出目录: {output_dir}")
    
    def browse_output_dir(self):
        """浏览并选择输出目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择输出目录", ""
        )
        if dir_path:
            self.output_dir_edit.setText(dir_path)
            self.refresh_summary()
    
    def start_splitting(self):
        """开始EPUB分割操作"""
        # 检查输入参数
        epub_path = self.epub_path_edit.text()
        output_dir = self.output_dir_edit.text()
        
        if not epub_path or not os.path.exists(epub_path):
            QMessageBox.warning(self, "错误", "请选择有效的EPUB文件")
            return
        
        if not output_dir or not os.path.exists(output_dir):
            QMessageBox.warning(self, "错误", "请选择有效的输出目录")
            return
        
        # 准备参数
        args = {
            'epub_path': epub_path,
            'output_dir': output_dir,
            'chapters_per_file': self.chapters_per_file_spin.value()
        }
        
        # 创建并启动工作线程
        self.worker_thread = WorkerThread('split', args)
        self.worker_thread.update_progress.connect(self.update_progress)
        self.worker_thread.operation_complete.connect(self.operation_complete)
        self.worker_thread.log_message.connect(self.add_log)
        
        # 更新UI状态
        self.start_button.setEnabled(False)
        self.start_button.setText("分割中...")
        self.progress_bar.setValue(0)
        self.status_label.setText("正在分割EPUB文件...")
        set_label_state(self.status_label, "working")
        self.refresh_summary()
        
        # 添加开始日志
        self.add_log(f"开始分割EPUB文件: {epub_path}")
        self.add_log(f"输出目录: {output_dir}")
        self.add_log(f"每个文件章节数: {self.chapters_per_file_spin.value()}")
        
        # 启动线程
        self.worker_thread.start()
    
    def update_progress(self, value, message):
        """更新进度条和状态标签"""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
        self.refresh_summary()
    
    def operation_complete(self, success, message):
        """操作完成的处理函数"""
        self.start_button.setEnabled(True)
        self.start_button.setText("开始分割")
        
        if success:
            self.status_label.setText("分割完成")
            set_label_state(self.status_label, "success")
            self.refresh_summary()
            self.add_log("EPUB分割成功完成")
            show_completion_dialog(self, "分割完成", message)
            
            # 发送分割完成信号，传递书名目录和分割结果目录
            output_dir = self.output_dir_edit.text()
            self.split_complete.emit(self.book_base_dir, output_dir)
        else:
            self.status_label.setText("分割失败")
            set_label_state(self.status_label, "error")
            self.refresh_summary()
            self.add_log(f"EPUB分割失败: {message}")
            show_error_message(self, "分割失败", message) 

    def toggle_line_wrap(self, state):
        """切换自动换行选项"""
        if state == Qt.Checked:
            self.log_text.setLineWrapMode(QTextEdit.WidgetWidth)
        else:
            self.log_text.setLineWrapMode(QTextEdit.NoWrap) 
