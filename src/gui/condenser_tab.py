#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
小说处理工具的脱水处理标签页
"""

import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                           QFileDialog, QMessageBox, QProgressBar, QTextEdit,
                           QSpinBox, QGroupBox, QLineEdit, QCheckBox, QComboBox, QFrame,
                           QDialog, QDialogButtonBox, QSplitter, QTabWidget,
                           QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont

from src.core.novel_condenser import config, key_manager
import src.core.novel_condenser.main as main_module

from .worker import WorkerThread
from .prompt_edit_dialog import PromptEditDialog
from .ui_components import (
    create_stat_card,
    set_label_state,
    show_completion_dialog,
    show_error_message,
    style_button,
)

class CondenserTab(QWidget):
    """小说脱水标签页"""
    
    # 定义信号，脱水完成后发送书名目录和脱水结果目录
    condense_complete = pyqtSignal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("condenser_tab")
        self.txt_files = []
        self.worker_thread = None
        self.book_base_dir = ""  # 保存书名目录路径
        self.output_dir = ""  # 保存脱水输出目录
        self.target_ratio = (config.MIN_CONDENSATION_RATIO + config.MAX_CONDENSATION_RATIO) // 2
        self.init_ui()
        
        # 初始化时加载API配置
        try:
            config.load_api_config()
        except Exception as e:
            self.add_log(f"加载API配置时出错: {str(e)}")
    
    def init_ui(self):
        """初始化用户界面"""
        # 创建布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(8)
        self.summary_source_card = create_stat_card("输入目录", "尚未选择")
        self.summary_file_count_card = create_stat_card("待处理章节", "0 个")
        self.summary_ratio_card = create_stat_card("目标比例", f"{self.target_ratio}%")
        self.summary_output_card = create_stat_card("输出目录", "尚未设置")
        summary_layout.addWidget(self.summary_source_card, 3)
        summary_layout.addWidget(self.summary_file_count_card, 1)
        summary_layout.addWidget(self.summary_ratio_card, 1)
        summary_layout.addWidget(self.summary_output_card, 3)
        main_layout.addLayout(summary_layout)
        
        # 创建左右分栏布局
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setChildrenCollapsible(False)
        
        # 左侧面板 - 控制区域
        left_panel = QVBoxLayout()
        left_panel.setSpacing(8)
        
        top_path_layout = QHBoxLayout()
        top_path_layout.setSpacing(8)

        # 文件夹选择
        folder_group = QGroupBox("选择TXT文件夹")
        folder_group.setObjectName("folder_group")
        folder_layout = QHBoxLayout()
        folder_layout.setContentsMargins(6, 6, 6, 6)
        
        self.folder_path_edit = QLineEdit()
        self.folder_path_edit.setObjectName("folder_path_edit")
        self.folder_path_edit.setReadOnly(True)
        self.folder_path_edit.setPlaceholderText("请选择TXT文件所在文件夹...")
        
        browse_button = QPushButton("浏览...")
        browse_button.setObjectName("browse_button")
        style_button(browse_button, "secondary")
        browse_button.clicked.connect(self.browse_folder)
        
        folder_layout.addWidget(self.folder_path_edit)
        folder_layout.addWidget(browse_button)
        folder_group.setLayout(folder_layout)
        
        # 输出目录选择
        output_group = QGroupBox("脱水输出目录")
        output_group.setObjectName("output_group")
        output_layout = QHBoxLayout()
        output_layout.setContentsMargins(6, 6, 6, 6)
        
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setObjectName("output_dir_edit")
        self.output_dir_edit.setReadOnly(True)
        self.output_dir_edit.setPlaceholderText("脱水处理结果输出目录...")
        
        output_browse_button = QPushButton("浏览...")
        output_browse_button.setObjectName("output_browse_button")
        style_button(output_browse_button, "secondary")
        output_browse_button.clicked.connect(self.browse_output_dir)
        
        output_layout.addWidget(self.output_dir_edit)
        output_layout.addWidget(output_browse_button)
        output_group.setLayout(output_layout)
        top_path_layout.addWidget(folder_group, 1)
        top_path_layout.addWidget(output_group, 1)
        
        # 添加强制生成选项
        options_group = QGroupBox("脱水设置")
        options_group.setObjectName("options_group")
        options_layout = QVBoxLayout()
        options_layout.setContentsMargins(4, 4, 4, 4)
        
        # 添加章节范围控制到选项组
        range_layout = QHBoxLayout()
        
        self.start_chapter_label = QLabel("开始章节:")
        self.start_chapter_label.setObjectName("start_chapter_label")
        self.start_chapter_spin = QSpinBox()
        self.start_chapter_spin.setObjectName("start_chapter_spin")
        self.start_chapter_spin.setRange(1, 10000)
        self.start_chapter_spin.setValue(1)
        
        self.end_chapter_label = QLabel("结束章节:")
        self.end_chapter_label.setObjectName("end_chapter_label")
        self.end_chapter_spin = QSpinBox()
        self.end_chapter_spin.setObjectName("end_chapter_spin")
        self.end_chapter_spin.setRange(1, 10000)
        self.end_chapter_spin.setValue(9999)
        
        range_layout.addWidget(self.start_chapter_label)
        range_layout.addWidget(self.start_chapter_spin)
        range_layout.addWidget(self.end_chapter_label)
        range_layout.addWidget(self.end_chapter_spin)
        range_layout.addStretch()
        
        # 添加强制生成复选框
        self.force_regenerate_checkbox = QCheckBox("强制生成")
        self.force_regenerate_checkbox.setObjectName("force_regenerate_checkbox")
        self.force_regenerate_checkbox.setToolTip("勾选后将强制重新脱水，否则跳过已存在的文件")
        
        # 创建API类型组合框，始终使用混合模式
        self.api_type_combo = QComboBox()
        self.api_type_combo.setObjectName("api_type_combo")
        self.api_type_combo.addItem("Gemini", "gemini")
        self.api_type_combo.addItem("OpenAI", "openai") 
        self.api_type_combo.addItem("混合使用", "mixed")
        self.api_type_combo.setCurrentIndex(2)  # 默认选择混合模式
        
        # 脱水比例设置 - 使用滑动条
        ratio_layout = QVBoxLayout()
        
        # 脱水比例区间滑动条
        ratio_range_layout = QHBoxLayout()
        ratio_range_label = QLabel("脱水比例区间:")
        ratio_range_label.setObjectName("ratio_range_label")
        
        self.min_ratio_spin = QSpinBox()
        self.min_ratio_spin.setObjectName("min_ratio_spin")
        self.min_ratio_spin.setRange(10, 90)
        self.min_ratio_spin.setValue(config.MIN_CONDENSATION_RATIO)
        self.min_ratio_spin.setSuffix("%")
        self.min_ratio_spin.setToolTip("设置脱水后文本相对于原文的最小比例")
        self.min_ratio_spin.valueChanged.connect(self.update_min_ratio)
        
        self.max_ratio_spin = QSpinBox()
        self.max_ratio_spin.setObjectName("max_ratio_spin")
        self.max_ratio_spin.setRange(20, 95)
        self.max_ratio_spin.setValue(config.MAX_CONDENSATION_RATIO)
        self.max_ratio_spin.setSuffix("%")
        self.max_ratio_spin.setToolTip("设置脱水后文本相对于原文的最大比例")
        self.max_ratio_spin.valueChanged.connect(self.update_max_ratio)
        
        # 显示区间范围的标签和数值
        ratio_range_layout.addWidget(ratio_range_label)
        ratio_range_layout.addWidget(self.min_ratio_spin)
        ratio_range_layout.addWidget(QLabel("-"))
        ratio_range_layout.addWidget(self.max_ratio_spin)
        ratio_range_layout.addStretch()
        
        # 添加提示词调整按钮
        prompt_adjust_layout = QHBoxLayout()
        self.prompt_adjust_button = QPushButton("提示词调整")
        self.prompt_adjust_button.setObjectName("prompt_adjust_button")
        style_button(self.prompt_adjust_button, "secondary")
        self.prompt_adjust_button.setToolTip("调整脱水提示词并进行单次测试")
        self.prompt_adjust_button.clicked.connect(self.open_prompt_editor)
        prompt_adjust_layout.addWidget(self.prompt_adjust_button)
        prompt_adjust_layout.addStretch()
        
        # 将所有选项添加到选项布局中
        options_layout.addLayout(range_layout)  # 章节范围
        options_layout.addWidget(self.force_regenerate_checkbox)  # 强制生成选项
        options_layout.addLayout(ratio_range_layout)  # 脱水比例区间
        options_layout.addLayout(prompt_adjust_layout)  # 提示词调整按钮
        options_group.setLayout(options_layout)
        
        # 状态和进度
        status_group = QGroupBox("状态")
        status_group.setObjectName("status_group")
        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(4, 4, 4, 4)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progress_bar")
        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("status_label")
        set_label_state(self.status_label, "muted")
        
        status_layout.addWidget(self.progress_bar)
        status_layout.addWidget(self.status_label)
        status_group.setLayout(status_layout)
        
        # 文件列表显示
        files_group = QGroupBox("文件列表")
        files_group.setObjectName("files_group")
        files_layout = QVBoxLayout()
        files_layout.setContentsMargins(4, 4, 4, 4)
        
        self.files_text = QTextEdit()
        self.files_text.setObjectName("files_text")
        self.files_text.setReadOnly(True)
        self.files_text.setPlaceholderText("选择 TXT 目录后，这里会列出待处理章节。")
        
        files_layout.addWidget(self.files_text)
        files_group.setLayout(files_layout)
        
        # 添加所有组件到左侧面板
        left_panel.addLayout(top_path_layout)
        left_panel.addWidget(options_group)  # 已合并的脱水设置组
        left_panel.addWidget(files_group)
        
        # 右侧面板 - 日志区域
        right_panel = QVBoxLayout()
        right_panel.setSpacing(8)

        right_panel.addWidget(status_group)
        
        # 日志显示
        log_group = QGroupBox("运行日志")
        log_group.setObjectName("log_group")
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(6, 6, 6, 6)
        
        self.log_text = QTextEdit()
        self.log_text.setObjectName("log_text")
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("运行日志会实时显示模型调度、处理进度与失败重试信息。")
        
        # 添加换行模式切换
        wrap_layout = QHBoxLayout()
        self.wrap_checkbox = QCheckBox("自动换行")
        self.wrap_checkbox.setObjectName("wrap_checkbox")
        self.wrap_checkbox.setChecked(True)
        self.wrap_checkbox.toggled.connect(self.toggle_line_wrap)
        
        self.clear_log_button = QPushButton("清除日志")
        self.clear_log_button.setObjectName("clear_log_button")
        style_button(self.clear_log_button, "ghost")
        self.clear_log_button.clicked.connect(self.clear_log)

        self.key_stats_button = QPushButton("配置状态")
        self.key_stats_button.setObjectName("key_stats_button")
        style_button(self.key_stats_button, "ghost")
        self.key_stats_button.clicked.connect(self.show_key_runtime_status)
        
        wrap_layout.addWidget(self.wrap_checkbox)
        wrap_layout.addStretch()
        wrap_layout.addWidget(self.clear_log_button)
        wrap_layout.addWidget(self.key_stats_button)
        
        # 添加开始脱水按钮到日志框下方
        self.start_button = QPushButton("开始脱水")
        self.start_button.setObjectName("start_button")
        style_button(self.start_button, "primary")
        self.start_button.clicked.connect(self.start_condensing)
        
        right_layout.addWidget(self.log_text)
        right_layout.addLayout(wrap_layout)
        right_layout.addWidget(self.start_button)  # 将开始脱水按钮添加到右侧面板
        log_group.setLayout(right_layout)
        
        right_panel.addWidget(log_group, 1)
        
        # 添加左右面板到分栏布局
        left_frame = QFrame()
        left_frame.setObjectName("left_frame")
        left_frame.setLayout(left_panel)
        left_frame.setFrameShape(QFrame.StyledPanel)
        
        right_frame = QFrame()
        right_frame.setObjectName("right_frame")
        right_frame.setLayout(right_panel)
        right_frame.setFrameShape(QFrame.StyledPanel)
        
        # 左侧占45%，右侧占55%
        content_splitter.addWidget(left_frame)
        content_splitter.addWidget(right_frame)
        content_splitter.setStretchFactor(0, 4)
        content_splitter.setStretchFactor(1, 5)
        content_splitter.setSizes([480, 620])
        
        # 添加分栏布局到主布局
        main_layout.addWidget(content_splitter, 1)
        
        # 设置布局
        self.setLayout(main_layout)
        self.refresh_summary()
    
    def add_log(self, message):
        """添加日志到日志显示区域"""
        self.log_text.append(message.rstrip())
        
        # 只在启用自动滚动时，才滚动到底部
        if self.wrap_checkbox.isChecked():
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def clear_log(self):
        """清除日志显示区域的内容"""
        self.log_text.clear()

    def _collect_key_runtime_stats(self):
        stats = []
        gemini_manager = getattr(main_module, "gemini_key_manager", None)
        openai_manager = getattr(main_module, "openai_key_manager", None)

        if gemini_manager is not None:
            stats.extend(gemini_manager.get_runtime_stats("Gemini"))
        if openai_manager is not None:
            stats.extend(openai_manager.get_runtime_stats("OpenAI"))
        return stats

    def _create_key_status_dialog(self, stats):
        dialog = QDialog(self)
        dialog.setWindowTitle("API 配置运行状态")
        dialog.resize(920, 420)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        description = QLabel("显示当前任务周期内每个配置实例的状态、实际并发、配置并发、成功请求数、失败请求数等运行数据。")
        description.setWordWrap(True)
        description.setObjectName("mutedMeta")
        layout.addWidget(description)

        table = QTableWidget(len(stats), 8)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.verticalHeader().setVisible(False)
        table.setHorizontalHeaderLabels([
            "API类型",
            "名称",
            "本次任务状态",
            "实际并发数",
            "配置并发数",
            "成功请求数",
            "失败请求数",
            "成功率",
        ])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)

        for row, item in enumerate(stats):
            values = [
                item.get("api_type", ""),
                item.get("name", ""),
                item.get("status", ""),
                str(item.get("active_concurrency", 0)),
                str(item.get("configured_concurrency", 0)),
                str(item.get("success_count", 0)),
                str(item.get("error_count", 0)),
                f"{item.get('success_rate', 0)}%",
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column != 1:
                    cell.setTextAlignment(Qt.AlignCenter)
                table.setItem(row, column, cell)

        layout.addWidget(table, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        close_button = button_box.button(QDialogButtonBox.Close)
        if close_button:
            close_button.setText("关闭")
            style_button(close_button, "secondary")
        button_box.rejected.connect(dialog.reject)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        return dialog

    def show_key_runtime_status(self):
        stats = self._collect_key_runtime_stats()
        if not stats:
            QMessageBox.information(self, "暂无数据", "当前还没有可展示的配置运行状态。\n请先开始一次脱水任务。")
            return

        dialog = self._create_key_status_dialog(stats)
        dialog.exec_()

    def refresh_summary(self):
        """刷新顶部摘要信息。"""
        full_source_path = self.folder_path_edit.text().strip()
        full_output_path = self.output_dir_edit.text().strip()
        self._set_stat_value(
            self.summary_source_card,
            self._compact_path(full_source_path, "尚未选择"),
            full_source_path or None,
        )
        self._set_stat_value(self.summary_file_count_card, f"{len(self.txt_files)} 个")
        self._set_stat_value(
            self.summary_ratio_card,
            f"{self.min_ratio_spin.value()}% - {self.max_ratio_spin.value()}% / 目标 {self.target_ratio}%"
        )
        self._set_stat_value(
            self.summary_output_card,
            self._compact_path(full_output_path, "尚未设置"),
            full_output_path or None,
        )

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
    
    def on_split_path_changed(self, base_dir, split_dir):
        """处理EPUB分割完成的信号"""
        self.book_base_dir = base_dir
        
        # 设置输入目录为分割结果目录
        self.folder_path_edit.setText(split_dir)
        self.load_txt_files(split_dir)
        
        # 设置脱水输出目录为"书名目录/condensed"
        self._set_output_dir(os.path.join(self.book_base_dir, "condensed"), split_dir)
    
    def _set_output_dir(self, target_dir, fallback_dir):
        """设置脱水输出目录，如果目标目录不存在则创建"""
        if not os.path.exists(target_dir):
            try:
                os.makedirs(target_dir)
            except Exception as e:
                QMessageBox.warning(self, "警告", f"无法创建脱水输出目录: {str(e)}")
                target_dir = fallback_dir
        self.output_dir = target_dir
        self.output_dir_edit.setText(self.output_dir)
        self.refresh_summary()
        self.add_log(f"设置脱水输出目录: {self.output_dir}")

    def browse_folder(self):
        """浏览并选择TXT文件所在文件夹"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择TXT文件所在文件夹", ""
        )
        if dir_path:
            self.folder_path_edit.setText(dir_path)
            self.load_txt_files(dir_path)
            
            # 尝试推断书名目录
            parent_dir = os.path.dirname(dir_path)
            folder_name = os.path.basename(dir_path)
            
            if folder_name.lower() == "splitted":
                # 如果选择的是splitted目录，则其父目录可能是书名目录
                self.book_base_dir = parent_dir
                self._set_output_dir(os.path.join(parent_dir, "condensed"), dir_path)
            else:
                # 否则，使用选择的目录的同级目录"condensed"作为输出目录
                self.book_base_dir = parent_dir
                self._set_output_dir(os.path.join(parent_dir, "condensed"), dir_path)
    
    def browse_output_dir(self):
        """浏览并选择脱水输出目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择脱水输出目录", ""
        )
        if dir_path:
            self.output_dir = dir_path
            self.output_dir_edit.setText(dir_path)
            self.refresh_summary()
            self.add_log(f"已设置脱水输出目录: {dir_path}")
    
    def load_txt_files(self, folder_path):
        """加载文件夹中的TXT文件"""
        self.txt_files = []
        files_text = ""
        
        # 查找所有TXT文件
        for file_name in os.listdir(folder_path):
            if file_name.endswith('.txt'):
                file_path = os.path.join(folder_path, file_name)
                self.txt_files.append(file_path)
                files_text += f"{file_name}\n"
        
        # 更新文件列表显示
        self.files_text.setText(files_text)
        if not self.txt_files:
            self.files_text.setPlainText("当前目录下未发现 TXT 文件。\n请确认上一步输出目录是否正确。")
        
        # 更新章节范围
        if self.txt_files:
            self.end_chapter_spin.setValue(len(self.txt_files))
            self.start_chapter_spin.setMaximum(len(self.txt_files))
            self.end_chapter_spin.setMaximum(len(self.txt_files))
            self.start_chapter_spin.setValue(1)
        else:
            self.start_chapter_spin.setMaximum(1)
            self.end_chapter_spin.setMaximum(1)
            self.start_chapter_spin.setValue(1)
            self.end_chapter_spin.setValue(1)

        self.refresh_summary()
            
        # 添加日志
        self.add_log(f"已加载{len(self.txt_files)}个TXT文件")
    
    def start_condensing(self):
        """开始脱水处理"""
        # 检查API配置
        if not hasattr(config, 'GEMINI_API_CONFIG') or not config.GEMINI_API_CONFIG:
            # 尝试加载API配置
            if not config.load_api_config():
                # 如果加载失败，则显示警告
                QMessageBox.warning(self, "API配置缺失", 
                                  "未找到有效的API密钥配置。请先在设置中配置API密钥。")
                return
        
        # 获取当前选择的API类型，确保使用混合模式
        api_type = "mixed"  # 始终使用混合模式
        
        # 检查Gemini API密钥管理器
        gemini_initialized = False
        if not hasattr(main_module, 'gemini_key_manager') or main_module.gemini_key_manager is None:
            # 尝试初始化API密钥管理器
            if hasattr(config, 'GEMINI_API_CONFIG') and config.GEMINI_API_CONFIG:
                try:
                    main_module.gemini_key_manager = key_manager.APIKeyManager(
                        config.GEMINI_API_CONFIG
                    )
                    gemini_initialized = True
                except Exception as e:
                    self.add_log(f"Gemini API密钥管理器初始化失败: {str(e)}")
            else:
                self.add_log("未找到有效的Gemini API配置，将只使用OpenAI API")
        else:
            gemini_initialized = True
        
        # 检查OpenAI API密钥管理器
        openai_initialized = False
        if not hasattr(main_module, 'openai_key_manager') or main_module.openai_key_manager is None:
            # 尝试初始化API密钥管理器
            if hasattr(config, 'OPENAI_API_CONFIG') and config.OPENAI_API_CONFIG:
                try:
                    main_module.openai_key_manager = key_manager.APIKeyManager(
                        config.OPENAI_API_CONFIG
                    )
                    openai_initialized = True
                except Exception as e:
                    self.add_log(f"OpenAI API密钥管理器初始化失败: {str(e)}")
            else:
                self.add_log("未找到有效的OpenAI API配置，将只使用Gemini API")
        else:
            openai_initialized = True
        
        # 检查是否至少有一个API可用
        if not gemini_initialized and not openai_initialized:
            QMessageBox.warning(self, "API配置缺失", 
                              "未找到有效的API密钥配置。请先在设置中配置至少一种API密钥。")
            return
        
        # 检查输入参数
        folder_path = self.folder_path_edit.text()
        
        if not folder_path or not os.path.exists(folder_path):
            QMessageBox.warning(self, "错误", "请选择有效的TXT文件夹")
            return
        
        if not self.txt_files:
            QMessageBox.warning(self, "错误", "所选文件夹中未找到TXT文件")
            return
        
        if not self.output_dir or not os.path.exists(self.output_dir):
            QMessageBox.warning(self, "错误", "请选择有效的脱水输出目录")
            return
            
        # 计算当前的目标脱水比例
        target_ratio = (self.min_ratio_spin.value() + self.max_ratio_spin.value()) // 2
        
        # 准备参数
        args = {
            'input_files': self.txt_files,
            'start_chapter': self.start_chapter_spin.value(),
            'end_chapter': self.end_chapter_spin.value(),
            'output_dir': self.output_dir,
            'force_regenerate': self.force_regenerate_checkbox.isChecked(),
            'api_type': api_type,  # 始终使用混合模式
            'min_condensation_ratio': self.min_ratio_spin.value(),
            'max_condensation_ratio': self.max_ratio_spin.value(),
            'target_condensation_ratio': target_ratio
        }
        
        # 创建并启动工作线程
        self.worker_thread = WorkerThread('condense', args)
        self.worker_thread.update_progress.connect(self.update_progress)
        self.worker_thread.operation_complete.connect(self.operation_complete)
        self.worker_thread.log_message.connect(self.add_log)
        
        # 更新UI状态
        self.start_button.setEnabled(False)
        self.start_button.setText("脱水处理中...")
        self.progress_bar.setValue(0)
        self.status_label.setText("正在脱水处理...")
        set_label_state(self.status_label, "working")
        self.refresh_summary()
        
        # 添加开始日志
        self.add_log(f"开始脱水处理，章节范围: {self.start_chapter_spin.value()} - {self.end_chapter_spin.value()}")
        self.add_log(f"脱水输出目录: {self.output_dir}")
        self.add_log(f"强制生成模式: {'开启' if self.force_regenerate_checkbox.isChecked() else '关闭'}")
        self.add_log(f"API模式: 混合模式 (自动选择Gemini或OpenAI API)")
        self.add_log(f"脱水比例设置: 最小{self.min_ratio_spin.value()}% - 最大{self.max_ratio_spin.value()}% (目标{target_ratio}%)")
        
        # API可用性信息
        if gemini_initialized and openai_initialized:
            self.add_log("两种API均已成功初始化，将优化资源利用")
        elif gemini_initialized:
            self.add_log("注意: 仅初始化了Gemini API")
        elif openai_initialized:
            self.add_log("注意: 仅初始化了OpenAI API")
        
        # 启动线程
        self.worker_thread.start()
    
    def update_progress(self, value, message):
        """更新进度条和状态标签"""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
    
    def operation_complete(self, success, message):
        """操作完成的处理函数"""
        self.start_button.setEnabled(True)
        self.start_button.setText("开始脱水")
        
        if success:
            self.status_label.setText("脱水完成")
            set_label_state(self.status_label, "success")
            self.add_log("脱水处理成功完成")
            
            if show_completion_dialog(
                self,
                "脱水完成",
                message,
                accept_text="留在当前页",
                action_text="继续生成 EPUB",
            ):
                # 发送脱水完成信号，传递书名目录和脱水结果目录
                self.condense_complete.emit(self.book_base_dir, self.output_dir)
        else:
            self.status_label.setText("脱水失败")
            set_label_state(self.status_label, "error")
            self.add_log(f"脱水处理失败: {message}")
            show_error_message(self, "脱水失败", message)
            
    def toggle_line_wrap(self, state):
        """切换日志文本的自动换行模式"""
        if state:  # 如果勾选了自动换行
            self.log_text.setLineWrapMode(QTextEdit.WidgetWidth)
        else:  # 如果取消了自动换行
            self.log_text.setLineWrapMode(QTextEdit.NoWrap)
    
    def update_min_ratio(self, value):
        """更新最小脱水比例"""
        # 确保最小比例不大于最大比例
        if value > self.max_ratio_spin.value():
            self.max_ratio_spin.setValue(value)
        # 自动计算目标比例为最大和最小的中间值
        self.target_ratio = (value + self.max_ratio_spin.value()) // 2
        # 更新配置
        config.MIN_CONDENSATION_RATIO = value
        config.TARGET_CONDENSATION_RATIO = self.target_ratio
        self.refresh_summary()
    
    def update_max_ratio(self, value):
        """更新最大脱水比例"""
        # 确保最大比例不小于最小比例
        if value < self.min_ratio_spin.value():
            self.min_ratio_spin.setValue(value)
        # 自动计算目标比例为最大和最小的中间值
        self.target_ratio = (value + self.min_ratio_spin.value()) // 2
        # 更新配置
        config.MAX_CONDENSATION_RATIO = value
        config.TARGET_CONDENSATION_RATIO = self.target_ratio
        self.refresh_summary()
    
    def open_prompt_editor(self):
        """打开提示词编辑器对话框"""
        # 创建提示词编辑器对话框，传入txt_files（可能为空）
        dialog = PromptEditDialog(self.txt_files, self)
        dialog.exec_()
        
        # 如果提示词被修改了，更新日志
        if dialog.prompt_changed:
            self.add_log(f"提示词已更新: {dialog.prompt_preview()}") 
