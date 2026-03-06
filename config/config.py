#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置模块 - 统一管理应用程序配置
"""

import os
import logging
from pathlib import Path

# 基础路径设置：config/config.py → 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR

# 配置文件路径
CONFIG_FILE_PATH = str(PROJECT_ROOT / "api_keys.json")

# 资源目录
RESOURCES_DIR = str(PROJECT_ROOT / "resources")

# 日志配置
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_LEVEL = logging.INFO

# Gemini API 配置
DEFAULT_GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_KEY_CONCURRENCY = 1  # 每个配置默认并发数
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
    global GEMINI_API_CONFIG, OPENAI_API_CONFIG

    import json

    if not os.path.exists(CONFIG_FILE_PATH):
        return False

    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        # 加载Gemini API配置
        if 'gemini_api' in config_data and isinstance(config_data['gemini_api'], list):
            GEMINI_API_CONFIG = config_data['gemini_api']
            for item in GEMINI_API_CONFIG:
                if 'name' not in item:
                    item['name'] = ""
                if 'concurrency' not in item or not isinstance(item['concurrency'], int) or item['concurrency'] < 1:
                    item['concurrency'] = DEFAULT_KEY_CONCURRENCY

        # 加载OpenAI API配置
        if 'openai_api' in config_data and isinstance(config_data['openai_api'], list):
            OPENAI_API_CONFIG = config_data['openai_api']
            for item in OPENAI_API_CONFIG:
                if 'name' not in item:
                    item['name'] = ""
                if 'concurrency' not in item or not isinstance(item['concurrency'], int) or item['concurrency'] < 1:
                    item['concurrency'] = DEFAULT_KEY_CONCURRENCY

        # 至少有一种API配置加载成功即可
        return len(GEMINI_API_CONFIG) > 0 or len(OPENAI_API_CONFIG) > 0

    except Exception as e:
        print(f"加载配置文件失败: {e}")

    return False
