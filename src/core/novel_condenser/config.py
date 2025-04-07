#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
小说脱水工具配置模块
"""

import os
import json
import sys
import logging
from typing import Dict, List, Optional, Any

# 导入项目配置
try:
    import config as project_config
    from utils import setup_logger
except ImportError:
    # 如果无法导入项目配置，使用相对导入
    from ..utils import setup_logger
    project_config = None

# 设置日志记录器
logger = setup_logger(__name__)

# =========================================================
# 全局常量定义
# =========================================================

# 配置文件名
CONFIG_FILE_NAME = "api_keys.json"

# 可能的配置文件路径列表（按优先级排序）
def get_possible_config_paths():
    """获取可能的配置文件路径列表
    
    返回一个按优先级排序的路径列表，包括:
    1. 可执行文件所在目录（打包后的情况）
    2. 项目根目录（开发环境）
    3. 当前工作目录
    
    Returns:
        List[str]: 可能的配置文件路径列表
    """
    possible_paths = []
    
    # 1. 可执行文件所在目录（适用于打包成exe的情况）
    if getattr(sys, 'frozen', False):
        # 如果是打包后的可执行文件
        exe_dir = os.path.dirname(sys.executable)
        possible_paths.append(os.path.join(exe_dir, CONFIG_FILE_NAME))
    
    # 2. 项目根目录（当前文件的上级目录的上级目录）
    module_dir = os.path.dirname(os.path.abspath(__file__))  # novel_condenser目录
    core_dir = os.path.dirname(module_dir)                   # core目录
    src_dir = os.path.dirname(core_dir)                      # src目录
    project_root = os.path.dirname(src_dir)                  # 项目根目录
    possible_paths.append(os.path.join(project_root, CONFIG_FILE_NAME))
    
    # 3. 当前工作目录
    possible_paths.append(os.path.join(os.getcwd(), CONFIG_FILE_NAME))
    
    # 4. src目录
    possible_paths.append(os.path.join(src_dir, CONFIG_FILE_NAME))
    
    # 去重
    return list(dict.fromkeys(possible_paths))

# 配置文件默认路径
CONFIG_FILE_PATH = get_possible_config_paths()[0]  # 默认使用第一个路径

# Gemini API 默认设置
DEFAULT_GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_KEY_RPM = 5  # 每个密钥默认每分钟请求数
DEFAULT_MAX_RPM = 20  # 默认全局最大每分钟请求数
GEMINI_API_CONFIG = []  # 从配置文件加载，格式为 [{"key": "key1", "redirect_url": "url1", "model": "model1", "rpm": 5}, ...]

# OpenAI API 默认设置
DEFAULT_OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-3.5-turbo"
OPENAI_API_CONFIG = []  # 从配置文件加载，格式为 [{"key": "key1", "redirect_url": "url1", "model": "model1", "rpm": 5}, ...]

# 脱水比例常量
MIN_CONDENSATION_RATIO = 30  # 最小压缩比例（百分比）
MAX_CONDENSATION_RATIO = 50  # 最大压缩比例（百分比）
TARGET_CONDENSATION_RATIO = 40  # 目标压缩比例（百分比）

# =========================================================
# 配置加载函数
# =========================================================

def load_api_config(config_path: Optional[str] = None) -> bool:
    """加载API密钥配置文件
    
    Args:
        config_path: 自定义配置文件路径，如果为None则按优先级查找
        
    Returns:
        bool: 配置加载是否成功
    """
    global GEMINI_API_CONFIG, OPENAI_API_CONFIG, DEFAULT_MAX_RPM
    
    # 首先尝试从项目全局配置加载
    if project_config:
        # 加载Gemini API配置
        if hasattr(project_config, 'GEMINI_API_CONFIG'):
            GEMINI_API_CONFIG = project_config.GEMINI_API_CONFIG
        
        # 加载OpenAI API配置
        if hasattr(project_config, 'OPENAI_API_CONFIG'):
            OPENAI_API_CONFIG = project_config.OPENAI_API_CONFIG
            
        # 加载RPM配置
        if hasattr(project_config, 'DEFAULT_MAX_RPM'):
            DEFAULT_MAX_RPM = project_config.DEFAULT_MAX_RPM
            
        # 如果至少加载了一种API配置，则返回成功
        if len(GEMINI_API_CONFIG) > 0 or len(OPENAI_API_CONFIG) > 0:
            return True
    
    # 如果指定了配置文件路径，直接使用
    if config_path:
        return _load_from_file(config_path)
    
    # 否则尝试从可能的路径列表中加载
    for path in get_possible_config_paths():
        if os.path.exists(path):
            if _load_from_file(path):
                return True
    
    # 所有路径都无法加载，创建默认配置
    logger.warning("在所有可能的位置都未找到配置文件")
    return False

def _load_from_file(file_path: str) -> bool:
    """从指定文件加载配置
    
    Args:
        file_path: 配置文件路径
        
    Returns:
        bool: 加载是否成功
    """
    global GEMINI_API_CONFIG, OPENAI_API_CONFIG, DEFAULT_MAX_RPM
    
    if not os.path.exists(file_path):
        logger.warning(f"配置文件不存在: {file_path}")
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # 加载Gemini API配置    
        if 'gemini_api' in config_data and isinstance(config_data['gemini_api'], list):
            GEMINI_API_CONFIG = config_data['gemini_api']
            logger.info(f"加载了 {len(GEMINI_API_CONFIG)} 个Gemini API密钥")
        
        # 加载OpenAI API配置
        if 'openai_api' in config_data and isinstance(config_data['openai_api'], list):
            OPENAI_API_CONFIG = config_data['openai_api']
            logger.info(f"加载了 {len(OPENAI_API_CONFIG)} 个OpenAI API密钥")
            
        # 加载max_rpm值（如果存在）
        if 'max_rpm' in config_data and isinstance(config_data['max_rpm'], int):
            DEFAULT_MAX_RPM = config_data['max_rpm']
                
        logger.info(f"成功加载配置文件: {file_path}")
        
        # 至少有一种API配置加载成功
        return len(GEMINI_API_CONFIG) > 0 or len(OPENAI_API_CONFIG) > 0
            
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        
    return False

def create_config_template(config_path: Optional[str] = None) -> None:
    """创建配置文件模板
    
    Args:
        config_path: 自定义配置文件路径，如果为None则在项目根目录创建
    """
    # 如果没有指定路径，优先使用项目根目录
    if not config_path:
        # 获取项目根目录（固定使用这个位置）
        module_dir = os.path.dirname(os.path.abspath(__file__))  # novel_condenser目录
        core_dir = os.path.dirname(module_dir)                   # core目录
        src_dir = os.path.dirname(core_dir)                      # src目录
        project_root = os.path.dirname(src_dir)                  # 项目根目录
        config_path = os.path.join(project_root, CONFIG_FILE_NAME)
        
        # 如果是打包后的可执行文件，则使用可执行文件所在的目录
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            config_path = os.path.join(exe_dir, CONFIG_FILE_NAME)
    
    if not os.path.exists(config_path):
        try:
            template = {
                "gemini_api": [
                    {
                        "key": "在此处填入您的Gemini API密钥1",
                        "redirect_url": "https://generativelanguage.googleapis.com/v1beta/models",
                        "model": "gemini-2.0-flash",
                        "rpm": 10
                    },
                    {
                        "key": "在此处填入您的Gemini API密钥2",
                        "rpm": 5
                    }
                ],
                "openai_api": [
                    {
                        "key": "在此处填入您的OpenAI API密钥",
                        "redirect_url": "https://api.openai.com/v1/chat/completions",
                        "model": "gpt-3.5-turbo",
                        "rpm": 10
                    }
                ],
                "max_rpm": 20
            }
            
            # 确保目录存在
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(template, f, ensure_ascii=False, indent=4)
                
            logger.info(f"已创建配置文件模板: {config_path}")
            print(f"已创建配置文件模板: {config_path}")
            print("请编辑此文件并填入您的API密钥")
        except Exception as e:
            logger.error(f"创建配置文件模板出错: {e}")
            print(f"创建配置文件模板出错: {e}") 