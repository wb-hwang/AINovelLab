#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件处理工具模块 - 处理小说文件的读取和保存
"""

import os
import re
import glob
import hashlib
import json
import time  # 添加time模块的导入
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# 导入配置和工具函数
from . import config
from ..utils import setup_logger, ensure_dir, read_text_file, get_safe_filename

# 设置日志记录器
logger = setup_logger(__name__)

# 全局变量（兼容层）：优先使用函数参数传入的 output_dir；仅在未传参时才回退到此全局变量。
OUTPUT_DIR = None  # 脱水小说输出目录

def read_file(file_path: str) -> str:
    """读取小说文件内容

    Args:
        file_path: 小说文件路径

    Returns:
        文件内容
    """
    try:
        content = read_text_file(file_path)
        if content:
            return content
            
        # 如果read_text_file返回空，尝试直接读取
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        logger.error(f"读取文件时出错: {e}")
        return ""

def is_directory_file(content):
    """
    检查内容是否是目录文件（目录文件不进行脱水）
    
    Args:
        content: 文件内容
        
    Returns:
        bool: 是否是目录文件
    """
    # 目录文件特征：包含多个"第X章"或"第X回"并且每行都很短
    if not content:
        return False
    
    # 拆分为行
    lines = content.split('\n')
    
    # 如果行数少于5，不太可能是目录
    if len(lines) < 5:
        return False
    
    # 检查章节标记
    chapter_markers = ['第.{1,6}章', '第.{1,6}回', '第.{1,6}节', '序章', '序幕', '引子', '尾声']
    chapter_count = 0
    
    for line in lines:
        line = line.strip()
        # 跳过空行
        if not line:
            continue
        
        # 检查行长度，目录行通常较短
        if len(line) > 50:
            return False
        
        # 检查是否包含章节标记
        for marker in chapter_markers:
            if re.search(marker, line):
                chapter_count += 1
                break
    
    # 如果超过20%的非空行包含章节标记，则认为是目录文件
    non_empty_lines = sum(1 for line in lines if line.strip())
    if non_empty_lines > 0 and (chapter_count / non_empty_lines) > 0.2:
        return True
    
    return False

def save_to_output_dir(
    file_path: str,
    content: str,
    file_type: str = "condensed",
    output_dir: Optional[str] = None,
) -> Optional[str]:
    """保存内容到输出目录

    Args:
        file_path: 原始文件路径
        content: 要保存的内容
        file_type: 文件类型描述，用于输出消息

    Returns:
        保存后的文件路径，如果保存失败则返回None
    """
    file_name = os.path.basename(file_path)
    file_dir = os.path.dirname(file_path)
    
    # 使用自定义输出目录或默认的condensed子目录
    final_output_dir = output_dir or OUTPUT_DIR or os.path.join(file_dir, "condensed")
    
    # 确保输出目录存在
    if not os.path.exists(final_output_dir):
        try:
            os.makedirs(final_output_dir)
        except Exception as e:
            logger.error(f"创建输出目录失败: {e}")
            return None
    
    # 使用原始文件名保存到输出目录
    output_path = os.path.join(final_output_dir, file_name)
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"{file_type}文件已保存到: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"保存文件时出错: {e}")
        return None

def save_condensed_novel(
    original_path: str,
    condensed_content: str,
    output_dir: Optional[str] = None,
) -> Optional[str]:
    """保存脱水后的小说内容

    Args:
        original_path: 原始文件路径
        condensed_content: 脱水后的内容

    Returns:
        保存后的文件路径，如果保存失败则返回None
    """
    return save_to_output_dir(original_path, condensed_content, "脱水后的小说", output_dir=output_dir)

def get_output_file_path(file_path: str, output_dir: Optional[str] = None) -> Optional[str]:
    """获取文件的输出路径
    
    Args:
        file_path: 输入文件路径
        
    Returns:
        str: 输出文件路径
    """
    # 获取文件名
    file_name = os.path.basename(file_path)
    
    # 如果未指定输出目录，使用默认值
    if output_dir is not None:
        final_output_dir = output_dir
    elif OUTPUT_DIR is None:
        # 获取输入文件所在目录
        input_dir = os.path.dirname(file_path)
        # 在输入目录下创建condensed子目录
        final_output_dir = os.path.join(input_dir, "condensed")
    else:
        final_output_dir = OUTPUT_DIR
    
    # 确保输出目录存在
    if not os.path.exists(final_output_dir):
        try:
            os.makedirs(final_output_dir)
        except Exception as e:
            logger.error(f"创建输出目录失败: {e}")
            return None
    
    # 返回完整的输出文件路径
    return os.path.join(final_output_dir, file_name)

def save_directory_file(file_path: str, output_dir: Optional[str] = None) -> Optional[str]:
    """直接保存目录文件（不进行脱水）

    Args:
        file_path: 目录文件路径

    Returns:
        保存后的文件路径，如果保存失败则返回None
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as src_file:
            content = src_file.read()
        return save_to_output_dir(file_path, content, "目录文件", output_dir=output_dir)
    except Exception as e:
        logger.error(f"复制目录文件时出错: {e}")
        return None

def find_matching_files(file_pattern: str, num_range: Optional[Tuple[int, int]] = None, 
                      debug_mode: bool = False) -> List[str]:
    """查找匹配的文件

    Args:
        file_pattern: 文件路径模式
        num_range: 数字范围，用于批量处理
        debug_mode: 是否启用调试输出

    Returns:
        匹配的文件路径列表
    """
    file_paths = []
    
    # 批量处理模式
    if num_range and '[num]' in file_pattern:
        start, end = num_range
        if debug_mode:
            logger.debug(f"查找范围 {start} 到 {end} 的文件")
        
        # 逐个数字尝试替换并使用glob查找
        for num in range(start, end + 1):
            # 准备多种可能的替换模式
            patterns = []
            
            # 标准替换: [num] -> 数字
            patterns.append(file_pattern.replace('[num]', str(num)))
            
            # 方括号替换: [num] -> [数字]
            patterns.append(file_pattern.replace('[num]', f'[{num}]'))
            
            # 尝试双层方括号
            if '[[num]]' in file_pattern:
                patterns.append(file_pattern.replace('[[num]]', f'[{num}]'))
            
            if debug_mode:
                logger.debug(f"数字 {num} 的匹配模式: {patterns}")
            
            # 使用通配符查找匹配的文件
            for pattern in patterns:
                # 修复Windows路径问题
                fixed_pattern = pattern.replace('\\', '/')
                # 使用glob.glob()时不使用递归模式
                matched = glob.glob(fixed_pattern)
                if matched and debug_mode:
                    logger.debug(f"模式 '{fixed_pattern}' 匹配到 {len(matched)} 个文件")
                
                file_paths.extend(matched)
        
        # 如果仍未找到文件，尝试更宽松的搜索
        if not file_paths:
            file_paths = _find_files_by_wider_search(file_pattern, num_range, debug_mode)
    
    # 单文件或通配符模式
    else:
        if '*' in file_pattern or '?' in file_pattern:
            # 如果包含通配符，使用glob查找匹配的文件
            fixed_pattern = file_pattern.replace('\\', '/')
            matched_files = glob.glob(fixed_pattern)
            if matched_files:
                file_paths.extend(matched_files)
        else:
            # 常规文件路径
            if os.path.isfile(file_pattern):
                file_paths.append(file_pattern)
    
    # 去重和排序
    return sorted(list(set(file_paths)))

def _find_files_by_wider_search(file_pattern: str, num_range: Tuple[int, int], 
                               debug_mode: bool = False) -> List[str]:
    """当常规匹配失败时使用更宽松的搜索策略，只搜索当前目录

    Args:
        file_pattern: 文件路径模式
        num_range: 数字范围
        debug_mode: 是否启用调试输出

    Returns:
        匹配的文件路径列表
    """
    start, end = num_range
    file_paths = []
    
    logger.info("没有找到精确匹配的文件，尝试更宽松的搜索...")
    
    # 确定搜索目录
    base_dir = os.path.dirname(file_pattern) if os.path.dirname(file_pattern) else '.'
    if debug_mode:
        logger.debug(f"在目录 '{base_dir}' 中搜索")
    
    # 只列出当前目录中的文件，不递归
    try:
        # 只获取当前目录的文件列表
        files = [f for f in os.listdir(base_dir) if os.path.isfile(os.path.join(base_dir, f))]
        
        for filename in files:
            if not filename.endswith('.txt'):
                continue
                
            full_path = os.path.join(base_dir, filename)
            
            # 尝试从文件名中提取数字
            digits = re.findall(r'\[(\d+)\]', filename)
            if digits:
                for digit in digits:
                    try:
                        num = int(digit)
                        if start <= num <= end:
                            if debug_mode:
                                logger.debug(f"找到匹配文件 '{full_path}', 序号 {num}")
                            file_paths.append(full_path)
                            break
                    except ValueError:
                        continue
            
            # 也可以尝试从文件名中提取其他形式的数字
            if not digits:
                # 从文件名中提取数字
                number_match = re.search(r'(\d+)', filename)
                if number_match:
                    try:
                        num = int(number_match.group(1))
                        if start <= num <= end:
                            if debug_mode:
                                logger.debug(f"找到匹配文件 '{full_path}', 序号 {num}")
                            file_paths.append(full_path)
                    except ValueError:
                        continue
    except Exception as e:
        logger.error(f"搜索文件时出错: {e}")
    
    return sorted(list(set(file_paths)))

def create_cache_for_file(
    content: str,
    condensed_content: str,
    file_path: str,
    output_dir: Optional[str] = None,
) -> bool:
    """为文件创建缓存，用于避免重复处理
    
    Args:
        content: 原始内容
        condensed_content: 脱水后的内容
        file_path: 文件路径
        
    Returns:
        bool: 缓存创建是否成功
    """
    try:
        # 计算文件内容的哈希值
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        
        # 获取文件所在目录
        output_path = get_output_file_path(file_path, output_dir=output_dir)
        if not output_path:
            return False
            
        # 创建缓存目录
        cache_dir = os.path.join(os.path.dirname(output_path), ".cache")
        os.makedirs(cache_dir, exist_ok=True)
        
        # 创建缓存文件路径
        file_name = os.path.basename(file_path)
        cache_file = os.path.join(cache_dir, file_name + ".json")
        
        # 构造缓存数据
        cache_data = {
            'content_hash': content_hash,
            'condensed_content': condensed_content,
            'timestamp': time.time(),
            'content_length': len(content),
            'condensed_length': len(condensed_content)
        }
        
        # 保存缓存
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False)
            
        return True
    except Exception as e:
        logger.warning(f"保存缓存失败: {e}")
        return False

def get_cached_content(file_path: str, output_dir: Optional[str] = None) -> Optional[str]:
    """获取文件的缓存内容
    
    Args:
        file_path: 文件路径
        
    Returns:
        Optional[str]: 缓存的脱水内容，如果没有缓存则返回None
    """
    try:
        # 读取原始文件内容计算哈希值
        content = read_file(file_path)
        if not content:
            return None
            
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        
        # 尝试获取缓存文件
        output_path = get_output_file_path(file_path, output_dir=output_dir)
        if not output_path:
            return None
            
        cache_dir = os.path.join(os.path.dirname(output_path), ".cache")
        file_name = os.path.basename(file_path)
        cache_file = os.path.join(cache_dir, file_name + ".json")
        
        # 如果缓存文件不存在，返回None
        if not os.path.exists(cache_file):
            return None
            
        # 读取缓存
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
            
        # 检查内容哈希是否匹配
        if cache_data.get('content_hash') == content_hash and 'condensed_content' in cache_data:
            return cache_data['condensed_content']
            
    except Exception as e:
        logger.warning(f"读取缓存失败: {e}")
        
    return None 
