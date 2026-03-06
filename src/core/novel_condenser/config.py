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
import config.config as project_config
from ..utils import setup_logger

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

def get_config_file_path() -> str:
    """获取当前使用的配置文件路径
    
    尝试按优先级查找配置文件，包括:
    1. 项目模块中的CONFIG_FILE_PATH
    2. 可能的配置路径列表中的已存在文件
    
    Returns:
        str: 配置文件路径，如果没有找到，返回默认位置
    """
    # 尝试从项目模块中获取配置路径
    if project_config and hasattr(project_config, 'CONFIG_FILE_PATH'):
        if os.path.exists(project_config.CONFIG_FILE_PATH):
            return project_config.CONFIG_FILE_PATH
    
    # 否则按优先级查找
    for path in get_possible_config_paths():
        if os.path.exists(path):
            return path
    
    # 如果没有找到，返回默认位置
    return get_possible_config_paths()[0]

# 配置文件默认路径
CONFIG_FILE_PATH = get_possible_config_paths()[0]  # 默认使用第一个路径

# Gemini API 默认设置
DEFAULT_GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_KEY_CONCURRENCY = 1  # 每个配置默认并发数
GEMINI_API_CONFIG = []  # 从配置文件加载，格式为 [{"key": "key1", "redirect_url": "url1", "model": "model1", "concurrency": 1}, ...]

# OpenAI API 默认设置
DEFAULT_OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-3.5-turbo"
OPENAI_API_CONFIG = []  # 从配置文件加载，格式为 [{"key": "key1", "redirect_url": "url1", "model": "model1", "concurrency": 1}, ...]

# 脱水比例常量
MIN_CONDENSATION_RATIO = 30  # 最小压缩比例（百分比）
MAX_CONDENSATION_RATIO = 50  # 最大压缩比例（百分比）
TARGET_CONDENSATION_RATIO = 40  # 目标压缩比例（百分比）

# =========================================================
# LLM通用请求参数配置
# =========================================================

# 通用生成参数
LLM_GENERATION_PARAMS = {
    # 通用参数
    "temperature": 0.2,        # 生成温度，较低的值会产生更确定性的输出
    "top_p": 0.8,              # 核采样阈值，控制多样性
    "top_k": 40,               # 仅用于Gemini，选择最有可能的K个词
    "max_tokens": 8192,        # 最大输出标记数
    
    # 超时和重试设置
    "timeout": {
        "official_api": 120,   # 官方API的超时时间（秒）
        "third_party_api": 180 # 第三方API的超时时间（秒）
    },
    "max_retries": 3,          # 最大重试次数
    "retry_delay": 5,          # 基础重试延迟（秒）
}

# 提示词模板
PROMPT_TEMPLATES = {
    # 小说压缩提示词模板
    "novel_condenser": '你是一位专业的小说内容整理与改写专家。你的任务是将下面的小说内容（原文 {original_count}字）调整为一个更简洁的版本。调整后版本的字数应在 {min_count} 字到 {max_count} 字之间，请务必严格控制产出字数在该范围内。\n\n请严格遵循以下要求：\n\n主线完整：完整保留故事的主线情节与所有关键转折点。不允许遗漏任何重要剧情推进环节。\n人物塑造：保留主要人物性格、形象发展至关重要的对话、内心活动和互动细节。\n环境氛围：保留对理解世界观、故事背景、气氛营造有核心作用的环境描写与关键细节（但避免无关冗余描写）。\n重要配角与线索：不遗漏任何对情节发展有显著影响的次要人物和叙事线索。\n风格连贯流畅：确保压缩后的文本连贯、流畅，逻辑清楚，尽量保持原作风格和叙事调性。\n动态回补机制：初步整理完成后，请统计自己整理后文本的字数。如果字数低于目标下限 {min_count}，请回溯补充之前可能略去的次要情节、气氛描写、对主配角的心理刻画、对话或有助主旨细节，直至内容字数达到要求。\n禁止输出范围外字数：不允许输出低于 {min_count}或高于 {max_count} 字的文本。\n\n输出格式与注意事项：\n直接输出脱水压缩后的文本本身，不要添加任何前言、说明、评论、总结、序号或标题。\n如果整理后确实已到目标范围上限，但仍有部分细节未能保留，在不影响主线流畅的前提下可以适当取舍，但必须优先保障上述 1-5 点。',
    
    # 分块处理前缀
    "chunk_prefix": "这是一个小说的第{chunk_index}段，共{total_chunks}段。"
}

# =========================================================
# 配置加载函数
# =========================================================


def _normalize_api_config_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """规范化单条 API 配置，移除旧字段并补齐默认值。"""
    normalized = dict(item or {})
    if "name" not in normalized:
        normalized["name"] = ""

    concurrency = normalized.get("concurrency")
    if not isinstance(concurrency, int) or concurrency < 1:
        concurrency = DEFAULT_KEY_CONCURRENCY
    normalized["concurrency"] = concurrency
    normalized.pop("rpm", None)
    normalized.pop("errors", None)
    normalized.pop("consecutive_errors", None)
    normalized.pop("cooling_until", None)
    normalized.pop("_config_id", None)
    return normalized


def _normalize_api_config_list_data(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_normalize_api_config_item(item) for item in items if isinstance(item, dict)]

def load_api_config(config_path: Optional[str] = None) -> bool:
    """加载API密钥配置文件
    
    Args:
        config_path: 自定义配置文件路径，如果为None则按优先级查找
        
    Returns:
        bool: 配置加载是否成功
    """
    global MIN_CONDENSATION_RATIO, MAX_CONDENSATION_RATIO, TARGET_CONDENSATION_RATIO
    global LLM_GENERATION_PARAMS, PROMPT_TEMPLATES
    
    if config_path:
        return _load_from_file(config_path)

    # 首先尝试从项目全局配置加载
    if project_config:
        # 加载Gemini API配置
        if hasattr(project_config, 'GEMINI_API_CONFIG'):
            try:
                GEMINI_API_CONFIG[:] = _normalize_api_config_list_data(list(project_config.GEMINI_API_CONFIG))
            except Exception:
                GEMINI_API_CONFIG[:] = []
        
        # 加载OpenAI API配置
        if hasattr(project_config, 'OPENAI_API_CONFIG'):
            try:
                OPENAI_API_CONFIG[:] = _normalize_api_config_list_data(list(project_config.OPENAI_API_CONFIG))
            except Exception:
                OPENAI_API_CONFIG[:] = []
            
        # 加载脱水比例配置
        if hasattr(project_config, 'MIN_CONDENSATION_RATIO'):
            MIN_CONDENSATION_RATIO = project_config.MIN_CONDENSATION_RATIO
        if hasattr(project_config, 'MAX_CONDENSATION_RATIO'):
            MAX_CONDENSATION_RATIO = project_config.MAX_CONDENSATION_RATIO
        if hasattr(project_config, 'TARGET_CONDENSATION_RATIO'):
            TARGET_CONDENSATION_RATIO = project_config.TARGET_CONDENSATION_RATIO
        
        # 加载LLM生成参数（如果存在）
        if hasattr(project_config, 'LLM_GENERATION_PARAMS'):
            LLM_GENERATION_PARAMS.update(project_config.LLM_GENERATION_PARAMS)
            
        # 加载提示词模板（如果存在）
        if hasattr(project_config, 'PROMPT_TEMPLATES'):
            PROMPT_TEMPLATES.update(project_config.PROMPT_TEMPLATES)
            
        # 如果至少加载了一种API配置，则返回成功
        if len(GEMINI_API_CONFIG) > 0 or len(OPENAI_API_CONFIG) > 0:
            return True
    
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
    global MIN_CONDENSATION_RATIO, MAX_CONDENSATION_RATIO, TARGET_CONDENSATION_RATIO
    global LLM_GENERATION_PARAMS, PROMPT_TEMPLATES
    
    if not os.path.exists(file_path):
        logger.warning(f"配置文件不存在: {file_path}")
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # 加载Gemini API配置    
        if 'gemini_api' in config_data and isinstance(config_data['gemini_api'], list):
            GEMINI_API_CONFIG[:] = _normalize_api_config_list_data(config_data['gemini_api'])
            logger.info(f"加载了 {len(GEMINI_API_CONFIG)} 个Gemini API密钥")
        
        # 加载OpenAI API配置
        if 'openai_api' in config_data and isinstance(config_data['openai_api'], list):
            OPENAI_API_CONFIG[:] = _normalize_api_config_list_data(config_data['openai_api'])
            logger.info(f"加载了 {len(OPENAI_API_CONFIG)} 个OpenAI API密钥")
            
        # 加载脱水比例配置（如果存在）
        if 'min_condensation_ratio' in config_data and isinstance(config_data['min_condensation_ratio'], int):
            MIN_CONDENSATION_RATIO = config_data['min_condensation_ratio']
            logger.info(f"加载了最小脱水比例: {MIN_CONDENSATION_RATIO}%")
            
        if 'max_condensation_ratio' in config_data and isinstance(config_data['max_condensation_ratio'], int):
            MAX_CONDENSATION_RATIO = config_data['max_condensation_ratio']
            logger.info(f"加载了最大脱水比例: {MAX_CONDENSATION_RATIO}%")
            
        if 'target_condensation_ratio' in config_data and isinstance(config_data['target_condensation_ratio'], int):
            TARGET_CONDENSATION_RATIO = config_data['target_condensation_ratio']
            logger.info(f"加载了目标脱水比例: {TARGET_CONDENSATION_RATIO}%")
        
        # 加载LLM生成参数（如果存在）
        if 'llm_generation_params' in config_data and isinstance(config_data['llm_generation_params'], dict):
            # 只更新配置中存在的参数，保留默认值
            for key, value in config_data['llm_generation_params'].items():
                if key in LLM_GENERATION_PARAMS:
                    if isinstance(LLM_GENERATION_PARAMS[key], dict) and isinstance(value, dict):
                        # 如果是嵌套字典，进行递归更新
                        LLM_GENERATION_PARAMS[key].update(value)
                    else:
                        # 直接更新普通值
                        LLM_GENERATION_PARAMS[key] = value
            logger.info("加载了LLM生成参数配置")
        
        # 加载提示词模板（如果存在）
        if 'prompt_templates' in config_data and isinstance(config_data['prompt_templates'], dict):
            PROMPT_TEMPLATES.update(config_data['prompt_templates'])
            logger.info("加载了提示词模板配置")
        
        # 加载自定义提示词（如果存在）- 优先级高于prompt_templates中的设置
        if 'customer_prompt' in config_data and isinstance(config_data['customer_prompt'], str):
            PROMPT_TEMPLATES["novel_condenser"] = config_data['customer_prompt']
            logger.info("加载了自定义提示词")
                
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
    
    # 检查文件是否已存在，避免覆盖
    if os.path.exists(config_path):
        logger.warning(f"配置文件已存在，跳过创建: {config_path}")
        return
    
    # 创建配置模板
    try:
        # 创建空的API密钥配置模板
        template = {
            "gemini_api": [
                {
                    "name": "",
                    "key": "你的gemini 密钥",
                    "redirect_url": "代理url 地址，可空。默认：https://generativelanguage.googleapis.com/v1beta/models",
                    "model": "模型，可空。默认：gemini-2.0-flash",
                    "concurrency": 1
                },{
                    "name": "",
                    "key":"最简配置demo"
                }
            ],
            "openai_api": [
                {
                    "name": "",
                    "key": "你的openai 密钥或其他一切兼容openai-api 格式的,如DeepSeek等",
                    "redirect_url": "代理url，可空。默认：https://api.openai.com/v1/chat/completions",
                    "model": "模型，可空。默认：gpt-3.5-turbo",
                    "concurrency": 1
                },{
                    "name": "",
                    "key":"最简配置demo"
                }
            ],
            "min_condensation_ratio": MIN_CONDENSATION_RATIO,
            "max_condensation_ratio": MAX_CONDENSATION_RATIO,
            "target_condensation_ratio": TARGET_CONDENSATION_RATIO,
            "llm_generation_params": LLM_GENERATION_PARAMS,
            "prompt_templates": {
                "novel_condenser": '你是一位专业的小说内容整理与改写专家。你的任务是将下面的小说内容（原文 {original_count}字）调整为一个更简洁的版本。调整后版本的字数应在 {min_count} 字到 {max_count} 字之间，请务必严格控制产出字数在该范围内。\n\n请严格遵循以下要求：\n\n主线完整：完整保留故事的主线情节与所有关键转折点。不允许遗漏任何重要剧情推进环节。\n人物塑造：保留主要人物性格、形象发展至关重要的对话、内心活动和互动细节。\n环境氛围：保留对理解世界观、故事背景、气氛营造有核心作用的环境描写与关键细节（但避免无关冗余描写）。\n重要配角与线索：不遗漏任何对情节发展有显著影响的次要人物和叙事线索。\n风格连贯流畅：确保压缩后的文本连贯、流畅，逻辑清楚，尽量保持原作风格和叙事调性。\n动态回补机制：初步整理完成后，请统计自己整理后文本的字数。如果字数低于目标下限 {min_count}，请回溯补充之前可能略去的次要情节、气氛描写、对主配角的心理刻画、对话或有助主旨细节，直至内容字数达到要求。\n禁止输出范围外字数：不允许输出低于 {min_count}或高于 {max_count} 字的文本。\n\n输出格式与注意事项：\n直接输出脱水压缩后的文本本身，不要添加任何前言、说明、评论、总结、序号或标题。\n如果整理后确实已到目标范围上限，但仍有部分细节未能保留，在不影响主线流畅的前提下可以适当取舍，但必须优先保障上述 1-5 点。',
                "chunk_prefix": "这是一个小说的第{chunk_index}段，共{total_chunks}段。"
            }
        }
        
        # 确保目录存在
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(template, f, ensure_ascii=False, indent=4)
            
        logger.info(f"已创建配置文件模板: {config_path}")
        logger.info("请编辑此文件并填入您的API密钥")
    except Exception as e:
        logger.error(f"创建配置文件模板出错: {e}")


def _normalize_api_config_list(api_configs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """规范化 API 配置列表，确保结构稳定。"""
    return _normalize_api_config_list_data(api_configs or [])


def _sync_runtime_api_configs(
    gemini_api: List[Dict[str, Any]],
    openai_api: List[Dict[str, Any]],
) -> None:
    """同步运行时内存中的 API 配置。"""
    normalized_gemini = _normalize_api_config_list(gemini_api)
    normalized_openai = _normalize_api_config_list(openai_api)

    GEMINI_API_CONFIG[:] = normalized_gemini
    OPENAI_API_CONFIG[:] = normalized_openai

    if project_config:
        if hasattr(project_config, "GEMINI_API_CONFIG") and isinstance(project_config.GEMINI_API_CONFIG, list):
            project_config.GEMINI_API_CONFIG[:] = [dict(item) for item in normalized_gemini]
        else:
            project_config.GEMINI_API_CONFIG = [dict(item) for item in normalized_gemini]

        if hasattr(project_config, "OPENAI_API_CONFIG") and isinstance(project_config.OPENAI_API_CONFIG, list):
            project_config.OPENAI_API_CONFIG[:] = [dict(item) for item in normalized_openai]
        else:
            project_config.OPENAI_API_CONFIG = [dict(item) for item in normalized_openai]


def save_api_config_lists(
    gemini_api: List[Dict[str, Any]],
    openai_api: List[Dict[str, Any]],
    config_path: Optional[str] = None,
) -> bool:
    """保存 API 配置列表，并同步内存中的运行时配置。"""
    target_path = config_path or get_config_file_path()

    try:
        config_data: Dict[str, Any] = {
            "gemini_api": [],
            "openai_api": [],
        }
        if os.path.exists(target_path):
            with open(target_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

        normalized_gemini = _normalize_api_config_list(gemini_api)
        normalized_openai = _normalize_api_config_list(openai_api)

        config_data["gemini_api"] = normalized_gemini
        config_data["openai_api"] = normalized_openai
        config_data.pop("max_rpm", None)

        os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)

        _sync_runtime_api_configs(normalized_gemini, normalized_openai)
        logger.info(f"已保存 API 配置到文件: {target_path}")
        return True
    except Exception as e:
        logger.error(f"保存 API 配置失败: {e}")
        return False


def save_config_to_file(custom_prompt: str) -> bool:
    """将自定义提示词保存到配置文件
    
    Args:
        custom_prompt: 自定义提示词
    
    Returns:
        bool: 保存是否成功
    """
    config_path = get_config_file_path()
    
    try:
        # 读取现有配置
        config_data = {}
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        config_data.pop('max_rpm', None)
        
        # 更新自定义提示词
        config_data['customer_prompt'] = custom_prompt
        
        # 保存回文件
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        
        logger.info(f"已保存自定义提示词到配置文件: {config_path}")
        return True
        
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")
        return False 
