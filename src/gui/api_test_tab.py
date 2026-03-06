#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API测试标签页 - 简单测试配置文件中的API连接状态
"""

import json
import os
import sys
import threading
import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                           QPushButton, QDialog, QFormLayout, QLineEdit,
                           QSpinBox, QComboBox, QTableWidget, QSizePolicy,
                           QTableWidgetItem, QHeaderView, QAbstractItemView)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QColor
from pathlib import Path
import re

from src.core.novel_condenser import config as core_config
from src.core.novel_condenser import api_service as core_api_service
from .ui_components import (
    create_stat_card,
    set_label_state,
    show_error_message,
    show_warning_confirm,
    style_button,
)

logger = logging.getLogger(__name__)

# API配置（复用 core_config 的全局列表；core_config 已改为 in-place 更新，引用稳定）
GEMINI_API_CONFIG = core_config.GEMINI_API_CONFIG
OPENAI_API_CONFIG = core_config.OPENAI_API_CONFIG

def get_config_file_path():
    """获取配置文件路径"""
    return core_config.get_config_file_path()

def load_api_config():
    """加载API配置
    
    Returns:
        bool: 配置加载是否成功
    """
    ok = core_config.load_api_config(get_config_file_path())
    if not ok:
        logger.warning(f"加载配置文件失败或未找到有效配置: {get_config_file_path()}")
    return ok

# 初始加载配置
load_api_config()

class ApiTestSignals(QObject):
    """API测试信号类"""
    test_complete = pyqtSignal(str, bool, str)  # API标识, 是否通过, 错误信息


class ApiConfigDialog(QDialog):
    """API 配置编辑对话框。"""

    def __init__(self, parent=None, api_type="openai", config_data=None, is_new=False):
        super().__init__(parent)
        self._is_new = is_new
        self._config_data = dict(config_data or {})
        self.setWindowTitle("新增API配置" if is_new else "编辑API配置")
        self.setModal(True)
        self.resize(520, 0)
        self._init_ui(api_type)

    def _init_ui(self, api_type):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(10)

        self.api_type_combo = QComboBox()
        self.api_type_combo.addItem("Gemini", "gemini")
        self.api_type_combo.addItem("OpenAI", "openai")
        self.api_type_combo.setCurrentIndex(0 if api_type == "gemini" else 1)
        self.api_type_combo.setEnabled(self._is_new)
        form_layout.addRow("API类型", self.api_type_combo)

        self.name_input = QLineEdit(self._config_data.get("name", ""))
        self.name_input.setPlaceholderText("可选，便于区分多组密钥")
        form_layout.addRow("名称", self.name_input)

        self.model_input = QLineEdit(self._config_data.get("model", ""))
        self.model_input.setPlaceholderText("例如 gpt-4o-mini")
        form_layout.addRow("模型", self.model_input)

        self.redirect_url_input = QLineEdit(self._config_data.get("redirect_url", ""))
        self.redirect_url_input.setPlaceholderText("如：https://api.openai.com/v1/chat/completions")
        form_layout.addRow("请求地址", self.redirect_url_input)

        self.key_input = QLineEdit(self._config_data.get("key", ""))
        self.key_input.setPlaceholderText("必填")
        form_layout.addRow("API Key", self.key_input)

        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 999)
        self.concurrency_spin.setValue(int(self._config_data.get("concurrency") or core_config.DEFAULT_KEY_CONCURRENCY))
        form_layout.addRow("并发数", self.concurrency_spin)

        layout.addLayout(form_layout)

        button_row = QHBoxLayout()
        button_row.addStretch()

        cancel_button = QPushButton("取消")
        style_button(cancel_button, "secondary")
        cancel_button.clicked.connect(self.reject)

        save_button = QPushButton("保存")
        style_button(save_button, "primary")
        save_button.clicked.connect(self._on_save)

        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

    def _on_save(self):
        if not self.key_input.text().strip():
            show_error_message(self, "缺少必填项", "API Key 不能为空。")
            return
        self.accept()

    def get_payload(self):
        api_type = self.api_type_combo.currentData()
        payload = {
            "name": self.name_input.text().strip(),
            "key": self.key_input.text().strip(),
            "redirect_url": self.redirect_url_input.text().strip(),
            "model": self.model_input.text().strip(),
            "concurrency": int(self.concurrency_spin.value()),
        }
        return api_type, payload


class ApiTestTab(QWidget):
    """API测试标签页"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # 记录环境信息（避免 stdout 污染）
        logger.debug(f"当前工作目录: {os.getcwd()}")
        logger.debug(f"是否打包为exe: {getattr(sys, 'frozen', False)}")
        if getattr(sys, 'frozen', False):
            logger.debug(f"exe路径: {sys.executable}")
            logger.debug(f"exe目录: {os.path.dirname(sys.executable)}")
        
        self.signals = ApiTestSignals()
        self.signals.test_complete.connect(self.on_test_complete)
        
        # 添加测试状态跟踪变量
        self.testing_all = False        # 是否正在进行"测试全部"操作
        self.total_tests = 0            # 当前测试批次中的总测试数量
        self.completed_tests = 0        # 当前批次中已完成的测试数量
        self.test_queue = []            # 测试队列，存储待测试的API信息
        self.active_test_ids = set()    # 当前进行中的测试任务
        
        self.init_ui()
    
    def init_ui(self):
        """初始化用户界面"""
        # 创建主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)
        
        # 创建说明标签
        info_label = QLabel(
            "此功能用于管理并测试配置文件中的 API 配置。\n"
            "支持新增、编辑、删除配置；每条配置独立设置并发数。测试使用快速超时策略，避免长时间卡住。"
        )
        info_label.setObjectName("sectionDescription")
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)
        
        # 创建配置文件路径显示
        self.config_path_label = QLabel(f"配置文件: {self._compact_path(get_config_file_path())}")
        self.config_path_label.setObjectName("mutedMeta")
        self.config_path_label.setToolTip(get_config_file_path())
        main_layout.addWidget(self.config_path_label)

        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(8)
        self.summary_total_card = create_stat_card("已加载配置", "0 组")
        self.summary_passed_card = create_stat_card("通过", "0")
        self.summary_pending_card = create_stat_card("待处理", "0")
        self.summary_issue_card = create_stat_card("异常", "0")
        summary_layout.addWidget(self.summary_total_card, 2)
        summary_layout.addWidget(self.summary_passed_card, 1)
        summary_layout.addWidget(self.summary_pending_card, 1)
        summary_layout.addWidget(self.summary_issue_card, 1)
        main_layout.addLayout(summary_layout)
        
        # 创建按钮组
        button_layout = QHBoxLayout()
        self.test_all_button = QPushButton("测试全部")
        style_button(self.test_all_button, "primary")
        self.test_all_button.clicked.connect(self.test_all_apis)
        self.reload_button = QPushButton("刷新配置")
        style_button(self.reload_button, "secondary")
        self.reload_button.clicked.connect(self.reload_api_keys)
        self.add_button = QPushButton("新增配置")
        style_button(self.add_button, "secondary")
        self.add_button.clicked.connect(self.add_api_config)
        
        button_layout.addWidget(self.test_all_button)
        button_layout.addWidget(self.reload_button)
        button_layout.addWidget(self.add_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)
        
        # 添加进度标签
        self.progress_label = QLabel("")
        set_label_state(self.progress_label, "muted")
        main_layout.addWidget(self.progress_label)
        self.progress_label.hide()  # 初始隐藏进度标签
        
        # 创建API列表表格
        self.api_table = QTableWidget()
        self.api_table.setAlternatingRowColors(True)
        self.api_table.setColumnCount(4)
        self.api_table.setHorizontalHeaderLabels(["API类型", "模型", "状态", "操作"])
        self.api_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.api_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.api_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.api_table.setWordWrap(False)
        self.api_table.verticalHeader().setVisible(False)
        self.api_table.verticalHeader().setDefaultSectionSize(44)
        self.api_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.api_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.api_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.api_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        
        main_layout.addWidget(self.api_table)
        
        self.setLayout(main_layout)
        
        # 加载API密钥
        self.load_api_list()

    def resizeEvent(self, event):
        """窗口尺寸变化时，重新分配表格列宽。"""
        super().resizeEvent(event)
        self._apply_table_column_widths()

    def showEvent(self, event):
        """首次显示后，按最终可用宽度重新分配列宽。"""
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_table_column_widths)

    def _apply_table_column_widths(self):
        """让模型列保持在约三分之一宽度。"""
        viewport_width = self.api_table.viewport().width()
        if viewport_width <= 0:
            return

        type_width = 92
        action_width = 196
        model_width = max(220, viewport_width // 3)
        status_width = max(180, viewport_width - type_width - model_width - action_width - 8)

        self.api_table.setColumnWidth(0, type_width)
        self.api_table.setColumnWidth(1, model_width)
        self.api_table.setColumnWidth(2, status_width)
        self.api_table.setColumnWidth(3, action_width)

    def refresh_summary_cards(self):
        """刷新顶部摘要卡。"""
        total = 0
        passed = 0
        pending = 0
        issue = 0

        for row in range(self.api_table.rowCount()):
            if not self.api_table.item(row, 0):
                continue
            if self.api_table.cellWidget(row, 3) is None:
                continue

            total += 1
            status_text = self.api_table.item(row, 2).text() if self.api_table.item(row, 2) else "未测试"
            if status_text.startswith("测试通过"):
                passed += 1
            elif status_text.startswith("测试失败") or status_text in {"配置缺失", "测试状态未知，请重试"}:
                issue += 1
            else:
                pending += 1

        self._set_stat_value(self.summary_total_card, f"{total} 组")
        self._set_stat_value(self.summary_passed_card, str(passed))
        self._set_stat_value(self.summary_pending_card, str(pending))
        self._set_stat_value(self.summary_issue_card, str(issue))

    def _set_stat_value(self, card, text: str):
        value_label = card.findChild(QLabel, "statCardValue")
        if value_label is not None:
            value_label.setText(text)

    def _set_status_item(self, item: QTableWidgetItem, text: str, background: QColor | None = None):
        """统一更新状态单元格。"""
        item.setText(text)
        item.setToolTip(text)
        item.setTextAlignment(Qt.AlignCenter)
        item.setBackground(background or QColor(0, 0, 0, 0))

    def _compact_path(self, path: str) -> str:
        normalized = path.replace("\\", "/")
        if len(normalized) <= 80:
            return normalized
        return f".../{'/'.join(normalized.split('/')[-4:])}"

    def _set_row_metadata(self, row: int, api_type: str, config_index: int):
        item = self.api_table.item(row, 0)
        if item is None:
            return
        item.setData(Qt.UserRole, api_type)
        item.setData(Qt.UserRole + 1, config_index)

    def _get_row_metadata(self, row: int):
        item = self.api_table.item(row, 0)
        if item is None:
            return None, None
        api_type = item.data(Qt.UserRole)
        config_index = item.data(Qt.UserRole + 1)
        if api_type not in {"gemini", "openai"} or config_index is None:
            return None, None
        return api_type, int(config_index)

    def _get_config_list(self, api_type: str):
        return GEMINI_API_CONFIG if api_type == "gemini" else OPENAI_API_CONFIG

    def _sanitize_config_payload(self, payload: dict) -> dict:
        sanitized = {
            "key": payload.get("key", "").strip(),
            "concurrency": int(payload.get("concurrency") or core_config.DEFAULT_KEY_CONCURRENCY),
            "name": payload.get("name", "").strip(),
        }
        model = payload.get("model", "").strip()
        redirect_url = payload.get("redirect_url", "").strip()
        if model:
            sanitized["model"] = model
        if redirect_url:
            sanitized["redirect_url"] = redirect_url
        return sanitized

    def _persist_api_configs(self, gemini_configs, openai_configs, action_text: str) -> bool:
        confirmed = show_warning_confirm(
            self,
            "配置文件写入确认",
            f"即将{action_text} API 配置，并直接修改配置文件。\n\n"
            f"配置文件：{get_config_file_path()}\n"
            "请确认配置内容无误后继续。",
            confirm_text="确认写入",
        )
        if not confirmed:
            return False

        if not core_config.save_api_config_lists(gemini_configs, openai_configs, get_config_file_path()):
            show_error_message(self, "保存失败", "配置文件写入失败，请检查文件权限或 JSON 内容。")
            return False

        self.config_path_label.setText(f"配置文件: {self._compact_path(get_config_file_path())}")
        self.config_path_label.setToolTip(get_config_file_path())
        self.load_api_list()
        self.progress_label.setText(f"{action_text}完成")
        set_label_state(self.progress_label, "success")
        self.progress_label.show()
        return True

    def _ensure_config_file_exists(self) -> bool:
        config_path = get_config_file_path()
        if os.path.exists(config_path):
            return True

        created = core_config.save_api_config_lists(
            [dict(item) for item in GEMINI_API_CONFIG],
            [dict(item) for item in OPENAI_API_CONFIG],
            config_path,
        )
        if not created:
            show_error_message(self, "配置文件创建失败", "无法自动创建配置文件，请检查目标目录写入权限。")
            return False

        self.config_path_label.setText(f"配置文件: {self._compact_path(config_path)}")
        self.config_path_label.setToolTip(config_path)
        return True

    def _find_row_by_action_widget(self, action_widget) -> int:
        for row in range(self.api_table.rowCount()):
            if self.api_table.cellWidget(row, 3) == action_widget:
                return row
        return -1

    def _create_action_button(self, text: str, role: str, action_name: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(action_name)
        style_button(button, role)
        button.setProperty("compact", True)
        button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        return button

    def _create_action_widget(self, api_type, index):
        action_widget = QWidget()
        layout = QHBoxLayout(action_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignCenter)

        test_button = self._create_action_button("测试", "secondary", "test")
        edit_button = self._create_action_button("编辑", "secondary", "edit")
        delete_button = self._create_action_button("删除", "danger", "delete")

        test_button.clicked.connect(
            lambda checked=False, a_type=api_type, idx=index, widget=action_widget: self.test_api(
                a_type,
                idx,
                self._find_row_by_action_widget(widget),
            )
        )
        edit_button.clicked.connect(
            lambda checked=False, a_type=api_type, idx=index: self.edit_api_config(a_type, idx)
        )
        delete_button.clicked.connect(
            lambda checked=False, a_type=api_type, idx=index: self.delete_api_config(a_type, idx)
        )

        layout.addWidget(test_button, 0, Qt.AlignVCenter)
        layout.addWidget(edit_button, 0, Qt.AlignVCenter)
        layout.addWidget(delete_button, 0, Qt.AlignVCenter)
        return action_widget

    def _set_action_widgets_enabled(self, enabled: bool):
        for row in range(self.api_table.rowCount()):
            action_widget = self.api_table.cellWidget(row, 3)
            if action_widget is not None:
                action_widget.setEnabled(enabled)

    def _sync_interaction_state(self):
        locked = bool(self.active_test_ids)
        self.reload_button.setEnabled(not locked)
        self.add_button.setEnabled(not locked)
        self._set_action_widgets_enabled(not locked)
        if not self.testing_all:
            self.test_all_button.setEnabled(not locked)

    def add_api_config(self):
        if self.active_test_ids:
            return
        if not self._ensure_config_file_exists():
            return

        dialog = ApiConfigDialog(self, is_new=True)
        if dialog.exec_() != QDialog.Accepted:
            return

        api_type, payload = dialog.get_payload()
        sanitized = self._sanitize_config_payload(payload)
        gemini_configs = [dict(item) for item in GEMINI_API_CONFIG]
        openai_configs = [dict(item) for item in OPENAI_API_CONFIG]
        target_list = gemini_configs if api_type == "gemini" else openai_configs
        target_list.append(sanitized)
        self._persist_api_configs(gemini_configs, openai_configs, "新增配置")

    def edit_api_config(self, api_type, index):
        if self.active_test_ids:
            return

        config_list = self._get_config_list(api_type)
        if not (0 <= index < len(config_list)):
            show_error_message(self, "配置缺失", "未找到对应的 API 配置，建议先刷新列表。")
            return

        dialog = ApiConfigDialog(self, api_type=api_type, config_data=config_list[index], is_new=False)
        if dialog.exec_() != QDialog.Accepted:
            return

        _, payload = dialog.get_payload()
        sanitized = self._sanitize_config_payload(payload)
        gemini_configs = [dict(item) for item in GEMINI_API_CONFIG]
        openai_configs = [dict(item) for item in OPENAI_API_CONFIG]
        target_list = gemini_configs if api_type == "gemini" else openai_configs
        target_list[index] = sanitized
        self._persist_api_configs(gemini_configs, openai_configs, "更新配置")

    def delete_api_config(self, api_type, index):
        if self.active_test_ids:
            return

        config_list = self._get_config_list(api_type)
        if not (0 <= index < len(config_list)):
            show_error_message(self, "配置缺失", "未找到对应的 API 配置，建议先刷新列表。")
            return

        api_config = config_list[index]
        model_name = api_config.get("model") or "未指定模型"
        key_preview = api_config.get("key", "")[:8]
        confirmed = show_warning_confirm(
            self,
            "删除配置确认",
            f"即将删除 {api_type.upper()} 配置。\n\n"
            f"模型：{model_name}\n"
            f"Key前缀：{key_preview or '未提供'}\n\n"
            "删除后会立刻写回配置文件，且不可自动恢复。",
            confirm_text="确认删除",
        )
        if not confirmed:
            return

        gemini_configs = [dict(item) for item in GEMINI_API_CONFIG]
        openai_configs = [dict(item) for item in OPENAI_API_CONFIG]
        target_list = gemini_configs if api_type == "gemini" else openai_configs
        target_list.pop(index)
        self._persist_api_configs(gemini_configs, openai_configs, "删除配置")
    
    def load_api_list(self):
        """从配置文件加载API列表并显示在表格中"""
        self.api_table.setRowCount(0)  # 清空表格
        
        # 打印当前配置状态
        logger.debug(f"Gemini API配置数量: {len(GEMINI_API_CONFIG)}")
        logger.debug(f"OpenAI API配置数量: {len(OPENAI_API_CONFIG)}")
        
        row = 0
        api_count = 0
        
        # 添加Gemini API
        for i, api in enumerate(GEMINI_API_CONFIG):
            if not isinstance(api, dict) or "key" not in api:
                logger.debug(f"跳过无效的gemini_api配置 #{i}: {api}")
                continue
            
            model_name = api.get("model", "未指定")
            # 使用重定向URL和密钥前缀创建更具唯一性的标识符
            redirect_url = api.get("redirect_url", "")
            key_prefix = api.get("key", "")[:8] if api.get("key") else ""
            
            # 创建唯一标识符：类型+模型+URL域名+密钥前缀
            url_domain = ""
            try:
                if redirect_url:
                    from urllib.parse import urlparse
                    parsed_url = urlparse(redirect_url)
                    url_domain = parsed_url.netloc
            except:
                url_domain = "unknown"
                
            api_count += 1
            
            logger.debug(f"添加Gemini API #{i}, 模型: {model_name}, 域名: {url_domain}")
            self.api_table.insertRow(row)
            
            # API类型
            api_type_item = QTableWidgetItem("Gemini")
            api_type_item.setFlags(api_type_item.flags() & ~Qt.ItemIsEditable)
            self.api_table.setItem(row, 0, api_type_item)
            self._set_row_metadata(row, "gemini", i)
            
            # 模型 - 增强显示，添加来源域名
            # 创建增强版的模型显示文本
            display_model_name = model_name
            if url_domain:
                # 从完整域名中提取简短的来源名称
                source_name = url_domain.split('.')[0] if '.' in url_domain else url_domain
                # 对于googleapis，使用更友好的名称
                if source_name == "generativelanguage" and "googleapis" in url_domain:
                    source_name = "官方API"
                display_model_name = f"{model_name} ({source_name})"
            
            model_item = QTableWidgetItem(display_model_name)
            model_item.setFlags(model_item.flags() & ~Qt.ItemIsEditable)
            # 存储原始模型名作为item的数据，供搜索和匹配使用
            model_item.setData(Qt.UserRole, model_name)
            self.api_table.setItem(row, 1, model_item)
            
            # 状态
            status_item = QTableWidgetItem("未测试")
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            self._set_status_item(status_item, "未测试")
            self.api_table.setItem(row, 2, status_item)
            
            # 操作按钮
            self.api_table.setCellWidget(row, 3, self._create_action_widget("gemini", i))
            
            row += 1
        
        # 添加OpenAI API (如果存在)
        for i, api in enumerate(OPENAI_API_CONFIG):
            if not isinstance(api, dict) or "key" not in api:
                logger.debug(f"跳过无效的openai_api配置 #{i}: {api}")
                continue
            
            model_name = api.get("model", "未指定")
            # 使用重定向URL和密钥前缀创建更具唯一性的标识符
            redirect_url = api.get("redirect_url", "")
            key_prefix = api.get("key", "")[:8] if api.get("key") else ""
            
            # 创建唯一标识符：类型+模型+URL域名+密钥前缀
            url_domain = ""
            try:
                if redirect_url:
                    from urllib.parse import urlparse
                    parsed_url = urlparse(redirect_url)
                    url_domain = parsed_url.netloc
            except:
                url_domain = "unknown"
                
            api_count += 1
            
            logger.debug(f"添加OpenAI API #{i}, 模型: {model_name}, 域名: {url_domain}")
            self.api_table.insertRow(row)
            
            # API类型
            api_type_item = QTableWidgetItem("OpenAI")
            api_type_item.setFlags(api_type_item.flags() & ~Qt.ItemIsEditable)
            self.api_table.setItem(row, 0, api_type_item)
            self._set_row_metadata(row, "openai", i)
            
            # 模型 - 增强显示，添加来源域名
            # 创建增强版的模型显示文本
            display_model_name = model_name
            if url_domain:
                # 从完整域名中提取简短的来源名称
                source_name = url_domain.split('.')[0] if '.' in url_domain else url_domain
                # 对于openai官方API，使用更友好的名称
                if source_name == "api" and "openai.com" in url_domain:
                    source_name = "官方API"
                display_model_name = f"{model_name} ({source_name})"
            
            model_item = QTableWidgetItem(display_model_name)
            model_item.setFlags(model_item.flags() & ~Qt.ItemIsEditable)
            # 存储原始模型名作为item的数据，供搜索和匹配使用
            model_item.setData(Qt.UserRole, model_name)
            self.api_table.setItem(row, 1, model_item)
            
            # 状态
            status_item = QTableWidgetItem("未测试")
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            self._set_status_item(status_item, "未测试")
            self.api_table.setItem(row, 2, status_item)
            
            # 操作按钮
            self.api_table.setCellWidget(row, 3, self._create_action_widget("openai", i))
            
            row += 1
        
        logger.debug(f"总共添加了 {api_count} 个API, 行数: {row}")
        
        # 如果没有API配置，添加提示行
        if api_count == 0:
            self.api_table.insertRow(0)
            no_api_item = QTableWidgetItem("未找到API配置，可点击“新增配置”自动创建配置文件并添加首条配置")
            no_api_item.setFlags(no_api_item.flags() & ~Qt.ItemIsEditable)
            no_api_item.setTextAlignment(Qt.AlignCenter)
            self.api_table.setItem(0, 0, no_api_item)
            self.api_table.setSpan(0, 0, 1, 4)  # 合并单元格
            self.progress_label.setText("当前没有可测试的 API 配置，请点击“新增配置”补充。")
            set_label_state(self.progress_label, "warning")
            self.progress_label.show()
        else:
            self.progress_label.hide()
        
        # 调整表格行高
        for i in range(self.api_table.rowCount()):
            self.api_table.setRowHeight(i, 44)

        self._apply_table_column_widths()
        QTimer.singleShot(0, self._apply_table_column_widths)
        self.refresh_summary_cards()
        self._sync_interaction_state()
    
    def reload_api_keys(self):
        """重新加载API密钥配置"""
        if self.active_test_ids:
            return

        # 重新加载配置
        load_api_config()
        logger.info("重新加载配置完成")
        
        # 更新配置文件路径显示
        self.config_path_label.setText(f"配置文件: {self._compact_path(get_config_file_path())}")
        self.config_path_label.setToolTip(get_config_file_path())
        
        # 刷新API列表
        self.load_api_list()
    
    def test_all_apis(self):
        """测试所有API - 改进版，使用任务队列确保所有测试都能执行"""
        # 如果已经在测试中，不执行新的测试批次
        if self.testing_all:
            logger.info("已有测试正在进行中，请等待完成")
            return
            
        # 设置测试状态
        self.testing_all = True
        self.test_queue = []  # 清空测试队列
        self.completed_tests = 0
        
        # 禁用测试按钮
        self.test_all_button.setEnabled(False)
        self.test_all_button.setText("测试中...")
        self.reload_button.setEnabled(False)
        self.add_button.setEnabled(False)
        self._set_action_widgets_enabled(False)
        set_label_state(self.progress_label, "working")
        
        # 收集所有需要测试的API
        for row in range(self.api_table.rowCount()):
            # 跳过非API行（如提示行）
            if not self.api_table.cellWidget(row, 3):
                continue

            api_type, config_index = self._get_row_metadata(row)
            config_list = self._get_config_list(api_type) if api_type else []
            if api_type and config_index is not None and 0 <= config_index < len(config_list):
                self.test_queue.append((api_type, config_index, row))
                status_item = self.api_table.item(row, 2)
                if status_item:
                    self._set_status_item(status_item, "等待测试...", QColor(255, 255, 0, 100))
            else:
                status_item = self.api_table.item(row, 2)
                if status_item:
                    self._set_status_item(status_item, "配置缺失", QColor(255, 165, 0, 100))
        
        # 设置总测试数量
        self.total_tests = len(self.test_queue)
        
        # 显示和更新进度标签
        self._update_test_progress()
        self.refresh_summary_cards()
        
        if self.total_tests == 0:
            # 没有找到任何API，恢复测试按钮
            self.test_all_button.setEnabled(True)
            self.test_all_button.setText("测试全部")
            self.testing_all = False
            self.progress_label.setText("没有找到可测试的API")
            set_label_state(self.progress_label, "warning")
            self.progress_label.show()
            self._sync_interaction_state()
            return
        
        # 启动第一批测试（最多同时测试5个API）
        self._start_next_tests(min(5, self.total_tests))
    
    def _start_next_tests(self, count=1):
        """从队列中启动下一批测试
        
        Args:
            count: 要启动的测试数量
        """
        tests_started = 0
        
        # 启动指定数量的测试，或直到队列为空
        while tests_started < count and self.test_queue:
            api_type, index, row_index = self.test_queue.pop(0)
            self.test_api(api_type, index, row_index)
            tests_started += 1
    
    def _update_test_progress(self):
        """更新测试进度显示"""
        if self.total_tests > 0:
            progress_text = f"测试进度: {self.completed_tests}/{self.total_tests}"
            if self.completed_tests < self.total_tests:
                queue_left = len(self.test_queue)
                running = self.total_tests - self.completed_tests - queue_left
                progress_text += f" (运行中: {running}, 等待: {queue_left})"
            self.progress_label.setText(progress_text)
            set_label_state(self.progress_label, "working")
            self.progress_label.show()
        else:
            self.progress_label.hide()
    
    def test_api(self, api_type, index, row_index=-1):
        """测试指定的API
        
        Args:
            api_type: API类型 ("gemini" 或 "openai")
            index: API配置索引
            row_index: 表格行索引，用于直接更新状态
        """
        # 获取API信息
        api_key = ""
        api_model = ""
        api_id = f"{api_type}_{index}_{row_index}"  # 在API ID中包含行索引

        config_list = self._get_config_list(api_type)
        if 0 <= index < len(config_list):
            api_info = config_list[index]
            api_key = api_info.get("key", "")
            api_model = api_info.get(
                "model",
                "gemini-pro" if api_type == "gemini" else "gpt-3.5-turbo",
            )
        else:
            self.signals.test_complete.emit(api_id, False, "API配置无效")
            return

        # 更新状态为"测试中"
        if row_index >= 0 and row_index < self.api_table.rowCount():
            # 如果提供了有效的行索引，直接更新该行
            status_item = self.api_table.item(row_index, 2)
            if status_item:
                self._set_status_item(status_item, "测试中...", QColor(173, 216, 230, 100))
        else:
            # 否则使用原来的查找逻辑
            for row in range(self.api_table.rowCount()):
                api_type_text = self.api_table.item(row, 0).text()
                model_item = self.api_table.item(row, 1)
                if not model_item:
                    continue
                    
                api_model_text = model_item.text()
                
                if ((api_type == "gemini" and api_type_text == "Gemini") or 
                    (api_type == "openai" and api_type_text == "OpenAI")):
                    
                    # 从UserRole数据中获取原始模型名称
                    model_name = model_item.data(Qt.UserRole) or model_item.text()
                    
                    # 从显示文本中提取原始模型名称（如果没有存储在UserRole中）
                    if not model_name and "(" in model_item.text():
                        model_name = model_item.text().split(" (")[0]
                    
                    if model_name == api_model:
                        status_item = self.api_table.item(row, 2)
                        if status_item:
                            self._set_status_item(status_item, "测试中...", QColor(173, 216, 230, 100))
                        break

        self.active_test_ids.add(api_id)
        self._sync_interaction_state()
        self.refresh_summary_cards()
        
        # 在后台线程中测试API连接
        thread = threading.Thread(target=self._test_api_connection, 
                                args=(api_id, api_type, api_key, api_model))
        thread.daemon = True
        thread.start()
    
    def _test_api_connection(self, api_id, api_type, api_key, api_model):
        """在后台线程中测试API连接（复用 core api_service 的请求/解析逻辑）。"""
        try:
            parts = api_id.split("_")
            if len(parts) >= 2:
                api_index = int(parts[1])
            else:
                self.signals.test_complete.emit(api_id, False, "API标识无效")
                return

            if api_type == "gemini":
                configs = GEMINI_API_CONFIG
            elif api_type == "openai":
                configs = OPENAI_API_CONFIG
            else:
                self.signals.test_complete.emit(api_id, False, f"不支持的API类型: {api_type}")
                return

            if not (0 <= api_index < len(configs)):
                self.signals.test_complete.emit(api_id, False, "API配置无效：索引超出范围")
                return

            api_config = configs[api_index]
            ok, err = core_api_service.test_api_key(api_type, api_config)
            self.signals.test_complete.emit(api_id, ok, err)
        except Exception as e:
            self.signals.test_complete.emit(api_id, False, f"测试出错: {str(e)}")

    def on_test_complete(self, api_id, success, error_message):
        """测试完成后的回调"""
        # 解析API ID
        parts = api_id.split("_")
        if len(parts) != 3:
            return
        
        api_type = parts[0]
        index = int(parts[1])
        row_index = int(parts[2])
        
        # 获取API信息
        api_info = None
        api_model = ""
        redirect_url = ""

        config_list = self._get_config_list(api_type)
        if 0 <= index < len(config_list):
            api_info = config_list[index]
            api_model = api_info.get(
                "model",
                "gemini-pro" if api_type == "gemini" else "gpt-3.5-turbo",
            )
            redirect_url = api_info.get("redirect_url", "")
        
        # 获取API域名，用于更精确匹配
        url_domain = ""
        try:
            if redirect_url:
                from urllib.parse import urlparse
                parsed_url = urlparse(redirect_url)
                url_domain = parsed_url.netloc
        except:
            pass
        
        # 更新表格中的状态
        row_found = False
        if row_index >= 0 and row_index < self.api_table.rowCount():
            # 如果提供了有效的行索引，直接更新该行
            status_item = self.api_table.item(row_index, 2)
            if status_item:
                if success:
                    self._set_status_item(status_item, "测试通过", QColor(0, 255, 0, 100))
                else:
                    status_text = "测试失败"
                    if error_message:
                        status_text += f": {error_message}"
                    self._set_status_item(status_item, status_text, QColor(255, 0, 0, 100))
            
            row_found = True
        
        # 如果没有找到有效行，使用回退匹配逻辑
        if not row_found and api_model:
            for row in range(self.api_table.rowCount()):
                api_type_text = self.api_table.item(row, 0).text()
                model_item = self.api_table.item(row, 1)
                if not model_item:
                    continue
                
                # 从UserRole数据中获取原始模型名称
                model_name = model_item.data(Qt.UserRole) or model_item.text()
                
                # 从显示文本中提取原始模型名称（如果没有存储在UserRole中）
                if not model_name and "(" in model_item.text():
                    model_name = model_item.text().split(" (")[0]
                
                # 检查API类型和模型是否匹配
                type_matches = (api_type == "gemini" and api_type_text == "Gemini") or \
                              (api_type == "openai" and api_type_text == "OpenAI")
                
                model_matches = model_name == api_model
                
                # 如果有域名信息，则使用域名进一步确认匹配
                domain_matches = True
                if url_domain and "(" in model_item.text():
                    display_domain = model_item.text().split("(")[1].rstrip(")")
                    # 检查域名的第一部分是否匹配
                    domain_first_part = url_domain.split('.')[0] if '.' in url_domain else url_domain
                    if display_domain != "官方API" and display_domain != domain_first_part:
                        domain_matches = False
                
                if type_matches and model_matches and domain_matches:
                    # 更新状态
                    status_item = self.api_table.item(row, 2)
                    if status_item:
                        if success:
                            self._set_status_item(status_item, "测试通过", QColor(0, 255, 0, 100))
                        else:
                            status_text = "测试失败"
                            if error_message:
                                status_text += f": {error_message}"
                            self._set_status_item(status_item, status_text, QColor(255, 0, 0, 100))
                    
                    # 找到匹配的行后就不再继续查找
                    row_found = True
                    break
        
        # 如果始终找不到行，记录错误信息
        if not row_found:
            logger.warning(f"无法找到匹配的表格行更新API测试状态: {api_id}, 类型:{api_type}, 模型:{api_model}")

        self.active_test_ids.discard(api_id)
        self._sync_interaction_state()
        self.refresh_summary_cards()
        
        # 如果是在"测试全部"模式中，更新计数并继续测试
        if self.testing_all:
            self.completed_tests += 1
            self._update_test_progress()
            
            # 如果还有待测试的API，启动下一个测试
            if self.test_queue:
                self._start_next_tests(1)
            
            # 检查是否所有测试都已完成
            if self.completed_tests >= self.total_tests:
                # 验证所有行状态是否正确更新
                self._verify_all_tests_complete()
                
                # 重置测试状态
                self.testing_all = False
                self.test_all_button.setEnabled(True)
                self.test_all_button.setText("测试全部")
                self.progress_label.setText(f"测试完成: {self.completed_tests}/{self.total_tests}")
                set_label_state(self.progress_label, "success")
                self._sync_interaction_state()
                self.refresh_summary_cards()
    
    def _verify_all_tests_complete(self):
        """验证是否所有测试行都已正确更新状态"""
        pending_rows = []
        
        # 查找所有显示为"等待测试..."的行
        for row in range(self.api_table.rowCount()):
            status_item = self.api_table.item(row, 2)
            if status_item and status_item.text() == "等待测试...":
                pending_rows.append(row)
        
        if pending_rows:
            logger.warning(f"发现 {len(pending_rows)} 行显示为'等待测试...'但测试队列已空")
            
            # 将这些行标记为"测试状态未知"
            for row in pending_rows:
                status_item = self.api_table.item(row, 2)
                if status_item:
                    self._set_status_item(status_item, "测试状态未知，请重试", QColor(255, 165, 0, 100))
                
        self.refresh_summary_cards()
