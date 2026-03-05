#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置模块 - 统一管理应用程序配置
"""

import os
import logging
import sys
from pathlib import Path

# 兼容性处理：确保在不同环境下都能正确找到文件路径
def get_base_dir():
    """获取基础目录路径，确保兼容不同的目录结构"""
    # 当前文件所在目录
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 判断是新的项目结构还是旧的项目结构
    if os.path.basename(current_file_dir) == 'config':
        # 新结构: config目录位于项目根目录下
        return Path(os.path.dirname(current_file_dir))
    else:
        # 旧结构: 配置文件在项目根目录
        return Path(current_file_dir)

# 基础路径设置
BASE_DIR = get_base_dir()
PROJECT_ROOT = BASE_DIR

# 配置文件路径 - 按优先级检查
# 优先级：项目根目录 > 配置目录
CONFIG_FILE_PATH = os.path.join(PROJECT_ROOT, "api_keys.json")

# 资源目录
RESOURCES_DIR = os.path.join(BASE_DIR, "resources")

# 日志配置
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_LEVEL = logging.INFO

# Gemini API 配置
DEFAULT_GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_KEY_RPM = 5  # 每个密钥默认每分钟请求数
DEFAULT_MAX_RPM = 20  # 默认全局最大每分钟请求数
GEMINI_API_CONFIG = []  # 从配置文件加载

# OpenAI API 配置
DEFAULT_OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-3.5-turbo"
OPENAI_API_CONFIG = []  # 从配置文件加载

# 脱水比例常量
MIN_CONDENSATION_RATIO = 30  # 最小压缩比例（百分比）
MAX_CONDENSATION_RATIO = 50  # 最大压缩比例（百分比）
TARGET_CONDENSATION_RATIO = 40  # 目标压缩比例（百分比）

# EPUB处理配置
DEFAULT_CHAPTERS_PER_FILE = 100
DEFAULT_LANGUAGE = 'zh-CN'
DEFAULT_FILE_ENCODINGS = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin-1']

# GUI配置
GUI_WINDOW_TITLE = "小说处理工具"
GUI_MIN_WIDTH = 800
GUI_MIN_HEIGHT = 600

# 加载API密钥配置
def load_api_config():
    """加载API密钥配置文件
    
    Returns:
        bool: 配置加载是否成功
    """
    global GEMINI_API_CONFIG, OPENAI_API_CONFIG, DEFAULT_MAX_RPM
    
    import json
    
    if not os.path.exists(CONFIG_FILE_PATH):
        return False
    
    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            
        # 加载Gemini API配置
        if 'gemini_api' in config_data and isinstance(config_data['gemini_api'], list):
            GEMINI_API_CONFIG = config_data['gemini_api']
            # 确保每项存在 name 字段
            for item in GEMINI_API_CONFIG:
                if 'name' not in item:
                    item['name'] = ""
        
        # 加载OpenAI API配置
        if 'openai_api' in config_data and isinstance(config_data['openai_api'], list):
            OPENAI_API_CONFIG = config_data['openai_api']
            # 确保每项存在 name 字段
            for item in OPENAI_API_CONFIG:
                if 'name' not in item:
                    item['name'] = ""
            
        # 加载max_rpm值（如果存在）
        if 'max_rpm' in config_data and isinstance(config_data['max_rpm'], int):
            DEFAULT_MAX_RPM = config_data['max_rpm']
                
        # 至少有一种API配置加载成功即可
        return len(GEMINI_API_CONFIG) > 0 or len(OPENAI_API_CONFIG) > 0
            
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        
    return False 