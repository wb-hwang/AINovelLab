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
                           QPushButton, QGroupBox, QTableWidget, 
                           QTableWidgetItem, QHeaderView)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QColor
from pathlib import Path
import re

from src.core.novel_condenser import config as core_config
from src.core.novel_condenser import api_service as core_api_service

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
    ok = core_config.load_api_config()
    if not ok:
        logger.warning(f"加载配置文件失败或未找到有效配置: {get_config_file_path()}")
    return ok

# 初始加载配置
load_api_config()

class ApiTestSignals(QObject):
    """API测试信号类"""
    test_complete = pyqtSignal(str, bool, str)  # API标识, 是否通过, 错误信息

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
        
        self.init_ui()
    
    def init_ui(self):
        """初始化用户界面"""
        # 创建主布局
        main_layout = QVBoxLayout()
        
        # 创建说明标签
        info_label = QLabel("此功能用于测试配置文件中的API密钥是否有效。\n"
                             "点击'测试全部'按钮可以一次性测试所有API，或者点击各API右侧的'测试'按钮单独测试。")
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)
        
        # 创建配置文件路径显示
        config_path_label = QLabel(f"配置文件: {get_config_file_path()}")
        config_path_label.setStyleSheet("color: #666666; font-size: 10px;")
        main_layout.addWidget(config_path_label)
        
        # 创建按钮组
        button_layout = QHBoxLayout()
        self.test_all_button = QPushButton("测试全部API")
        self.test_all_button.clicked.connect(self.test_all_apis)
        self.reload_button = QPushButton("重新加载配置")
        self.reload_button.clicked.connect(self.reload_api_keys)
        
        button_layout.addWidget(self.test_all_button)
        button_layout.addWidget(self.reload_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)
        
        # 添加进度标签
        self.progress_label = QLabel("")
        main_layout.addWidget(self.progress_label)
        self.progress_label.hide()  # 初始隐藏进度标签
        
        # 创建API列表表格
        self.api_table = QTableWidget()
        self.api_table.setColumnCount(4)
        self.api_table.setHorizontalHeaderLabels(["API类型", "模型", "状态", "操作"])
        self.api_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.api_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.api_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        
        main_layout.addWidget(self.api_table)
        
        self.setLayout(main_layout)
        
        # 加载API密钥
        self.load_api_list()
    
    def create_test_button(self, api_type, index):
        """创建测试按钮，并正确设置其回调函数"""
        button = QPushButton("测试")
        
        # 创建一个特定的调用函数，避免lambda捕获问题
        def on_test_clicked(checked=False, a_type=api_type, idx=index):
            # 获取按钮所在的表格行
            for row in range(self.api_table.rowCount()):
                if self.api_table.cellWidget(row, 3) == button:
                    self.test_api(a_type, idx, row)
                    break
            else:
                # 如果未找到对应行，使用-1表示未知行
                self.test_api(a_type, idx, -1)
        
        button.clicked.connect(on_test_clicked)
        return button
    
    def load_api_list(self):
        """从配置文件加载API列表并显示在表格中"""
        self.api_table.setRowCount(0)  # 清空表格
        
        # 打印当前配置状态
        logger.debug(f"Gemini API配置数量: {len(GEMINI_API_CONFIG)}")
        logger.debug(f"OpenAI API配置数量: {len(OPENAI_API_CONFIG)}")
        
        row = 0
        api_count = 0
        
        # 存储已添加的API标识符，避免重复
        added_apis = set()
        
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
                
            api_identifier = f"Gemini:{model_name}:{url_domain}:{key_prefix}"
            
            # 检查是否已添加过相同的API
            if api_identifier in added_apis:
                logger.debug(f"跳过重复的API: {api_identifier}")
                continue
            
            added_apis.add(api_identifier)
            api_count += 1
            
            logger.debug(f"添加Gemini API #{i}, 模型: {model_name}, 域名: {url_domain}")
            self.api_table.insertRow(row)
            
            # API类型
            api_type_item = QTableWidgetItem("Gemini")
            api_type_item.setFlags(api_type_item.flags() & ~Qt.ItemIsEditable)
            self.api_table.setItem(row, 0, api_type_item)
            
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
            self.api_table.setItem(row, 2, status_item)
            
            # 测试按钮
            test_button = self.create_test_button("gemini", i)
            self.api_table.setCellWidget(row, 3, test_button)
            
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
                
            api_identifier = f"OpenAI:{model_name}:{url_domain}:{key_prefix}"
            
            # 检查是否已添加过相同的API
            if api_identifier in added_apis:
                logger.debug(f"跳过重复的API: {api_identifier}")
                continue
            
            added_apis.add(api_identifier)
            api_count += 1
            
            logger.debug(f"添加OpenAI API #{i}, 模型: {model_name}, 域名: {url_domain}")
            self.api_table.insertRow(row)
            
            # API类型
            api_type_item = QTableWidgetItem("OpenAI")
            api_type_item.setFlags(api_type_item.flags() & ~Qt.ItemIsEditable)
            self.api_table.setItem(row, 0, api_type_item)
            
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
            self.api_table.setItem(row, 2, status_item)
            
            # 测试按钮
            test_button = self.create_test_button("openai", i)
            self.api_table.setCellWidget(row, 3, test_button)
            
            row += 1
        
        logger.debug(f"总共添加了 {api_count} 个API, 行数: {row}")
        
        # 如果没有API配置，添加提示行
        if api_count == 0:
            self.api_table.insertRow(0)
            no_api_item = QTableWidgetItem("未找到API配置，请在api_keys.json文件中添加配置")
            no_api_item.setFlags(no_api_item.flags() & ~Qt.ItemIsEditable)
            self.api_table.setItem(0, 0, no_api_item)
            self.api_table.setSpan(0, 0, 1, 4)  # 合并单元格
        
        # 调整表格行高
        for i in range(self.api_table.rowCount()):
            self.api_table.setRowHeight(i, 40)
    
    def reload_api_keys(self):
        """重新加载API密钥配置"""
        # 重新加载配置
        load_api_config()
        logger.info("重新加载配置完成")
        
        # 更新配置文件路径显示
        for i in range(self.layout().count()):
            item = self.layout().itemAt(i).widget()
            if isinstance(item, QLabel) and item.text().startswith("配置文件:"):
                item.setText(f"配置文件: {get_config_file_path()}")
                break
        
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
        
        # 收集所有需要测试的API
        for row in range(self.api_table.rowCount()):
            # 跳过非API行（如提示行）
            if not self.api_table.cellWidget(row, 3):
                continue
                
            # 获取API类型和索引
            api_type = "gemini" if self.api_table.item(row, 0).text() == "Gemini" else "openai"
            
            # 从UserRole数据中获取原始模型名称
            model_item = self.api_table.item(row, 1)
            if not model_item:
                continue
                
            model_name = model_item.data(Qt.UserRole) or model_item.text()
            
            # 从显示文本中提取原始模型名称（如果没有存储在UserRole中）
            if not model_name and "(" in model_item.text():
                model_name = model_item.text().split(" (")[0]
            
            # 查找对应的API配置索引
            config_list = GEMINI_API_CONFIG if api_type == "gemini" else OPENAI_API_CONFIG
            
            found_matching_api = False
            for i, api in enumerate(config_list):
                if api.get("model", "未指定") == model_name:
                    # 将此API添加到测试队列，包含表格行索引
                    # 元组格式: (api_type, config_index, table_row_index)
                    self.test_queue.append((api_type, i, row))
                    
                    # 更新状态
                    status_item = self.api_table.item(row, 2)
                    if status_item:
                        status_item.setText("等待测试...")
                        status_item.setBackground(QColor(255, 255, 0, 100))  # 半透明黄色
                    # 禁用单个测试按钮
                    if self.api_table.cellWidget(row, 3):
                        self.api_table.cellWidget(row, 3).setEnabled(False)
                    
                    found_matching_api = True
                    break
            
            # 如果没有找到匹配的API配置，标记为"配置缺失"
            if not found_matching_api:
                status_item = self.api_table.item(row, 2)
                if status_item:
                    status_item.setText("配置缺失")
                    status_item.setBackground(QColor(255, 165, 0, 100))  # 半透明橙色
        
        # 设置总测试数量
        self.total_tests = len(self.test_queue)
        
        # 显示和更新进度标签
        self._update_test_progress()
        
        if self.total_tests == 0:
            # 没有找到任何API，恢复测试按钮
            self.test_all_button.setEnabled(True)
            self.test_all_button.setText("测试全部API")
            self.testing_all = False
            self.progress_label.setText("没有找到可测试的API")
            self.progress_label.show()
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
        
        if api_type == "gemini" and index < len(GEMINI_API_CONFIG):
            api_info = GEMINI_API_CONFIG[index]
            api_key = api_info.get("key", "")
            api_model = api_info.get("model", "gemini-pro")
        elif api_type == "openai" and index < len(OPENAI_API_CONFIG):
            api_info = OPENAI_API_CONFIG[index]
            api_key = api_info.get("key", "")
            api_model = api_info.get("model", "gpt-3.5-turbo")
        else:
            self.signals.test_complete.emit(api_id, False, "API配置无效")
            return
        
        # 更新状态为"测试中"
        if row_index >= 0 and row_index < self.api_table.rowCount():
            # 如果提供了有效的行索引，直接更新该行
            status_item = self.api_table.item(row_index, 2)
            if status_item:
                status_item.setText("测试中...")
                status_item.setBackground(QColor(173, 216, 230, 100))  # 半透明浅蓝色
            # 禁用测试按钮
            if self.api_table.cellWidget(row_index, 3):
                self.api_table.cellWidget(row_index, 3).setEnabled(False)
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
                            status_item.setText("测试中...")
                            status_item.setBackground(QColor(173, 216, 230, 100))  # 半透明浅蓝色
                        # 禁用测试按钮
                        if self.api_table.cellWidget(row, 3):
                            self.api_table.cellWidget(row, 3).setEnabled(False)
                        break
        
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
        
        if api_type == "gemini" and index < len(GEMINI_API_CONFIG):
            api_info = GEMINI_API_CONFIG[index]
            api_model = api_info.get("model", "gemini-pro")
            redirect_url = api_info.get("redirect_url", "")
        elif api_type == "openai" and index < len(OPENAI_API_CONFIG):
            api_info = OPENAI_API_CONFIG[index]
            api_model = api_info.get("model", "gpt-3.5-turbo")
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
                    status_item.setText("测试通过")
                    status_item.setBackground(QColor(0, 255, 0, 100))  # 半透明绿色
                else:
                    status_text = "测试失败"
                    if error_message:
                        status_text += f": {error_message}"
                    status_item.setText(status_text)
                    status_item.setBackground(QColor(255, 0, 0, 100))  # 半透明红色
            
            # 重新启用测试按钮
            if self.api_table.cellWidget(row_index, 3):
                self.api_table.cellWidget(row_index, 3).setEnabled(True)
            
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
                            status_item.setText("测试通过")
                            status_item.setBackground(QColor(0, 255, 0, 100))  # 半透明绿色
                        else:
                            status_text = "测试失败"
                            if error_message:
                                status_text += f": {error_message}"
                            status_item.setText(status_text)
                            status_item.setBackground(QColor(255, 0, 0, 100))  # 半透明红色
                    
                    # 重新启用测试按钮
                    if self.api_table.cellWidget(row, 3):
                        self.api_table.cellWidget(row, 3).setEnabled(True)
                    
                    # 找到匹配的行后就不再继续查找
                    row_found = True
                    break
        
        # 如果始终找不到行，记录错误信息
        if not row_found:
            logger.warning(f"无法找到匹配的表格行更新API测试状态: {api_id}, 类型:{api_type}, 模型:{api_model}")
        
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
                self.test_all_button.setText("测试全部API")
                self.progress_label.setText(f"测试完成: {self.completed_tests}/{self.total_tests}")
    
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
                    status_item.setText("测试状态未知，请重试")
                    status_item.setBackground(QColor(255, 165, 0, 100))  # 半透明橙色
                
                # 重新启用测试按钮
                if self.api_table.cellWidget(row, 3):
                    self.api_table.cellWidget(row, 3).setEnabled(True) 
