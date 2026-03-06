#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
小说脱水工具主模块 - 提供命令行接口和处理流程控制（极简版）
"""

import argparse
import concurrent.futures
import os
import sys
import threading
import time
import logging
from typing import Dict, List, Optional, Tuple

# 导入模块
from . import config
from .key_manager import APIKeyManager
from .file_utils import (
    read_file, is_directory_file, save_condensed_novel,
    save_directory_file, find_matching_files, get_output_file_path,
    get_cached_content, create_cache_for_file
)
from .api_service import condense_novel_gemini, condense_novel_openai, print_processing_stats
from .stats import statistics, reset_statistics, update_file_stats, finalize_statistics, print_processing_summary
from ..utils import setup_logger

# 创建日志记录器
logger = setup_logger(__name__)

# 全局变量（兼容层）：新路径优先通过参数/实例属性传递 output_dir。
OUTPUT_DIR = None

class NovelCondenser:
    """小说脱水处理器类，处理小说文件的脱水流程"""
    
    def __init__(
        self,
        api_type="gemini",
        workers=1,
        force_regenerate=False,
        output_dir=None,
        min_condensation_ratio=None,
        max_condensation_ratio=None,
        target_condensation_ratio=None,
    ):
        """初始化小说脱水处理器"""
        self.api_type = api_type.lower()
        self.workers = workers
        self.force_regenerate = force_regenerate
        self.output_dir = output_dir
        self.gemini_key_manager = None
        self.openai_key_manager = None

        # 将“每次运行的比例覆盖”收口到 core，避免 GUI 线程直接写 config.*。
        if min_condensation_ratio is not None:
            config.MIN_CONDENSATION_RATIO = min_condensation_ratio
        if max_condensation_ratio is not None:
            config.MAX_CONDENSATION_RATIO = max_condensation_ratio
        if target_condensation_ratio is not None:
            config.TARGET_CONDENSATION_RATIO = target_condensation_ratio
        
        # 初始化API密钥管理器
        if not config.load_api_config():
            logger.error("无法加载API密钥配置，请检查配置文件")
        
        # 根据API类型初始化对应的密钥管理器
        if self.api_type in ["gemini", "mixed"]:
            self.gemini_key_manager = APIKeyManager(config.GEMINI_API_CONFIG)
            
        if self.api_type in ["openai", "mixed"]:
            self.openai_key_manager = APIKeyManager(config.OPENAI_API_CONFIG)

        # 同步到模块级全局引用，确保 GUI 能读取当前任务实际使用的运行时状态
        try:
            import src.core.novel_condenser.main as current_main_module
            current_main_module.gemini_key_manager = self.gemini_key_manager
            current_main_module.openai_key_manager = self.openai_key_manager
        except Exception:
            pass
    
    def validate_api_keys(self):
        """验证API密钥是否有效"""
        # 初始化有效密钥标志
        valid_gemini_key = False
        valid_openai_key = False
        
        logger.info(f"API类型: {self.api_type}")
        
        # 测试API密钥
        if self.api_type in ["gemini", "mixed"] and self.gemini_key_manager:
            gemini_keys = self.gemini_key_manager.api_configs
            logger.info(f"正在测试 {len(gemini_keys)} 个Gemini API密钥...")
            
            for key_config in gemini_keys:
                is_valid = self._test_api_key("gemini", key_config)
                if is_valid:
                    valid_gemini_key = True
        
        if self.api_type in ["openai", "mixed"] and self.openai_key_manager:
            openai_keys = self.openai_key_manager.api_configs
            logger.info(f"正在测试 {len(openai_keys)} 个OpenAI API密钥...")
            
            for key_config in openai_keys:
                is_valid = self._test_api_key("openai", key_config)
                if is_valid:
                    valid_openai_key = True
        
        # 根据API类型检查结果
        if self.api_type == "gemini" and not valid_gemini_key:
            logger.error("所有Gemini API密钥都无效，无法继续")
            return False
            
        if self.api_type == "openai" and not valid_openai_key:
            logger.error("所有OpenAI API密钥都无效，无法继续")
            return False
            
        if self.api_type == "mixed" and not valid_gemini_key and not valid_openai_key:
            logger.error("Gemini和OpenAI的API密钥都无效，无法继续")
            return False
        
        return True
    
    def _test_api_key(self, api_type, key_config):
        """测试API密钥是否有效"""
        # 测试文本
        test_content = "这是一个测试。请将这句话压缩一下。"
        
        # 获取并遮蔽密钥信息（用于日志）
        key_id = key_config.get('key', '未指定')
        masked_key = key_id[:8] + "..." if len(key_id) > 8 else key_id
        
        try:
            # 根据API类型调用对应的测试函数
            key_manager = self.gemini_key_manager if api_type == "gemini" else self.openai_key_manager
            api_func = condense_novel_gemini if api_type == "gemini" else condense_novel_openai
            result = api_func(test_content, key_config, key_manager)
            
            if result:
                name = key_config.get('name') if isinstance(key_config, dict) else None
                display = name if name else masked_key
                logger.info(f"✓ {api_type.capitalize()}密钥 {display} 有效")
                return True
            else:
                name = key_config.get('name') if isinstance(key_config, dict) else None
                display = name if name else masked_key
                logger.error(f"✗ {api_type.capitalize()}密钥 {display} 无法获取有效响应")
                return False
        except Exception as e:
            name = key_config.get('name') if isinstance(key_config, dict) else None
            display = name if name else masked_key
            logger.error(f"✗ {api_type.capitalize()}密钥 {display} 测试失败: {e}")
            return False
    
    def process_files(self, files):
        """处理文件列表"""
        total_files = len(files)
        statistics["total_files"] = total_files
        logger.info(f"找到 {total_files} 个文件待处理")
        
        # 根据工作线程数选择处理模式
        if self.workers <= 1:
            return self._process_files_sequentially(files, total_files)
        else:
            return self._process_files_concurrently(files, total_files)
    
    def _process_files_sequentially(self, files, total_files):
        """顺序处理文件"""
        success_count = 0
        failed_files = {}
        
        for i, file_path in enumerate(files):
            try:
                status = self.process_single_file(file_path, file_index=i+1, total_files=total_files)
                
                if status:
                    success_count += 1
                else:
                    failed_files[file_path] = 0
                    
            except Exception as e:
                logger.error(f"处理文件 {file_path} 时发生错误: {str(e)}")
                failed_files[file_path] = 0
        
        return success_count, failed_files
    
    def _process_files_concurrently(self, files, total_files, stop_event=None):
        """并发处理文件

        Args:
            files: 待处理文件列表
            total_files: 文件总数
            stop_event: 可选的停止事件，用于外部请求中止处理
        """
        success_count = 0
        failed_files = {}
        completed_count = 0
        
        # 线程锁，用于更新计数
        lock = threading.Lock()
        
        # 用于标记是否所有密钥都被跳过
        all_keys_skipped = {"gemini": False, "openai": False}
        keys_skipped_lock = threading.Lock()
        
        # 停止事件（支持外部传入）
        stop_event = stop_event or threading.Event()
        
        # 处理函数
        def process_file(file_path, file_index):
            nonlocal success_count, completed_count
            
            # 检查是否应该停止
            if stop_event.is_set():
                with lock:
                    completed_count += 1
                    failed_files[file_path] = 0
                return False
                
            # 检查是否要跳过处理
            with keys_skipped_lock:
                skip_condition = (
                    (self.api_type == "gemini" and all_keys_skipped["gemini"]) or
                    (self.api_type == "openai" and all_keys_skipped["openai"]) or
                    (self.api_type == "mixed" and all_keys_skipped["gemini"] and all_keys_skipped["openai"])
                )
                if skip_condition:
                    with lock:
                        completed_count += 1
                        failed_files[file_path] = 0
                    return False
            
            # 处理单个文件
            status = self.process_single_file(file_path, file_index=file_index, total_files=total_files)
            
            # 更新计数
            with lock:
                completed_count += 1
                if status:
                    success_count += 1
                else:
                    failed_files[file_path] = 0
            
            # 检查密钥状态
            self._check_key_status(all_keys_skipped, keys_skipped_lock)
                
            return status
        
        # 计算有效并发度：不超过配置的workers，且不超过密钥能力
        try:
            effective_workers = int(self.workers)
        except Exception:
            effective_workers = 1
        effective_workers = max(1, effective_workers)
        try:
            if self.api_type == "gemini" and self.gemini_key_manager:
                effective_workers = min(effective_workers, max(1, self.gemini_key_manager.get_max_concurrency()))
            elif self.api_type == "openai" and self.openai_key_manager:
                effective_workers = min(effective_workers, max(1, self.openai_key_manager.get_max_concurrency()))
            elif self.api_type == "mixed":
                g = self.gemini_key_manager.get_max_concurrency() if self.gemini_key_manager else 0
                o = self.openai_key_manager.get_max_concurrency() if self.openai_key_manager else 0
                effective_workers = min(effective_workers, max(1, g + o if (g + o) > 0 else effective_workers))
        except Exception:
            pass
        effective_workers = max(1, effective_workers)

        # 使用tqdm显示进度条
        from tqdm import tqdm
        with tqdm(total=total_files, desc="处理进度") as pbar:
            try:
                # 使用ThreadPoolExecutor处理文件（分批提交，避免一次性提交全部任务）
                with concurrent.futures.ThreadPoolExecutor(max_workers=effective_workers) as executor:
                    futures = set()
                    # 预填充任务，不超过有效并发数
                    file_iter = ((idx + 1, path) for idx, path in enumerate(files))

                    def submit_next_batch(num_to_submit=1):
                        submitted = 0
                        while submitted < num_to_submit and not stop_event.is_set():
                            try:
                                file_index, file_path = next(file_iter)
                            except StopIteration:
                                break
                            futures.add(executor.submit(process_file, file_path, file_index))
                            submitted += 1
                        return submitted

                    # 初始提交
                    submit_next_batch(min(effective_workers, total_files))

                    # 处理完成的future并滚动提交新任务
                    while futures:
                        # 使用wait而不是as_completed，避免因超时抛出异常
                        done, _not_done = concurrent.futures.wait(
                            futures,
                            timeout=0.5,
                            return_when=concurrent.futures.FIRST_COMPLETED,
                        )
                        made_progress = len(done) > 0

                        for future in list(done):
                            if future in futures:
                                futures.remove(future)

                            # 吞掉可能的异常，避免静默失败
                            try:
                                _ = future.result()
                            except Exception as e:
                                logger.error(f"并发任务执行异常: {e}")

                            # 更新进度条
                            pbar.n = completed_count
                            pbar.refresh()

                            if stop_event.is_set():
                                break

                            # 每完成一个任务，补提一个新任务
                            submit_next_batch(1)

                        if stop_event.is_set():
                            # 取消未完成任务
                            for f in list(futures):
                                if not f.done():
                                    f.cancel()
                            break

                        # 如果没有完成的任务（超时），也检查一次进度
                        if not made_progress:
                            pbar.n = completed_count
                            pbar.refresh()
            
            except KeyboardInterrupt:
                logger.warning("用户中断处理")
                # 将未完成的文件标记为失败
                for file_path in files:
                    if file_path not in failed_files and files.index(file_path) >= completed_count:
                        failed_files[file_path] = 0
        
        # 打印最终统计信息
        logger.info(f"处理完成: 总计 {total_files} 个文件, 成功 {success_count} 个, 失败 {len(failed_files)} 个")
        
        return success_count, failed_files
    
    def _check_key_status(self, all_keys_skipped, keys_skipped_lock):
        """检查API密钥状态"""
        # 检查Gemini API密钥状态
        if self.api_type in ["gemini", "mixed"] and self.gemini_key_manager:
            if hasattr(self.gemini_key_manager, 'skipped_keys'):
                valid_keys = [conf['key'] for conf in self.gemini_key_manager.api_configs 
                            if conf['key'] not in self.gemini_key_manager.skipped_keys]
                if not valid_keys:
                    with keys_skipped_lock:
                        all_keys_skipped["gemini"] = True
                        logger.warning("所有Gemini API密钥都已因失败次数过多而被跳过")
        
        # 检查OpenAI API密钥状态
        if self.api_type in ["openai", "mixed"] and self.openai_key_manager:
            if hasattr(self.openai_key_manager, 'skipped_keys'):
                valid_keys = [conf['key'] for conf in self.openai_key_manager.api_configs 
                            if conf['key'] not in self.openai_key_manager.skipped_keys]
                if not valid_keys:
                    with keys_skipped_lock:
                        all_keys_skipped["openai"] = True
                        logger.warning("所有OpenAI API密钥都已因失败次数过多而被跳过")
    
    def _select_api_type(self, file_index=None):
        """选择使用的API类型"""
        if self.api_type != "mixed":
            return self.api_type
            
        has_gemini_keys = self.gemini_key_manager and len(self.gemini_key_manager.api_configs) > 0
        has_openai_keys = self.openai_key_manager and len(self.openai_key_manager.api_configs) > 0
        
        if has_gemini_keys and not has_openai_keys:
            return "gemini"
        elif has_openai_keys and not has_gemini_keys:
            return "openai"
        elif has_gemini_keys and has_openai_keys:
            # 根据文件索引选择API类型
            return "gemini" if (file_index is not None and file_index % 2 == 0) else "openai"
        else:
            # 如果没有任何API密钥配置，默认返回gemini
            logger.warning("混合模式下没有有效的API密钥配置")
            return "gemini"
    
    def process_single_file(self, file_path, file_index=None, total_files=None, retry_attempt=0):
        """处理单个文件"""
        # 获取开始时间和文件名
        start_time = time.time()
        base_name = os.path.basename(file_path)
        output_file = get_output_file_path(file_path, output_dir=self.output_dir)
        
        # 显示处理信息
        self._log_process_info(file_path, file_index, total_files, retry_attempt)
        
        # 1. 检查是否需要处理（已存在有效输出文件）
        if self._should_skip_file(file_path, output_file, start_time, retry_attempt):
            return True
        
        # 2. 读取文件内容
        try:
            content = read_file(file_path)
        except Exception as e:
            logger.error(f"无法读取文件内容: {file_path}, 错误: {str(e)}")
            return self._update_stats(file_path, "error", start_time, retry_attempt, error=str(e))
        
        if not content:
            logger.warning(f"文件内容为空: {file_path}")
            return self._update_stats(file_path, "empty", start_time, retry_attempt)
        
        # 3. 处理特殊情况（缓存、目录文件、短内容）
        status, result = self._handle_special_cases(file_path, content, start_time, retry_attempt)
        if status:
            return True
        
        # 4. 使用API处理内容
        # 选择API类型
        current_api_type = self._select_api_type(file_index) if self.api_type == "mixed" else self.api_type
        if self.api_type == "mixed":
            # 输出选择的API并尽量展示将要使用的密钥名称（从未被跳过的配置中挑选第一个）
            display_name = None
            try:
                km = self.gemini_key_manager if current_api_type == "gemini" else self.openai_key_manager
                if km and getattr(km, 'api_configs', None):
                    for ac in km.api_configs:
                        if hasattr(km, 'skipped_configs') and ac.get('_config_id') in km.skipped_configs:
                            continue
                        n = ac.get('name') or ''
                        key_mask = (ac.get('key','')[:8] + '...') if ac.get('key') else ''
                        display_name = n if n else key_mask
                        break
            except Exception:
                pass
            suffix = f"（{display_name}）" if display_name else ""
            logger.info(f"混合模式：为文件 {base_name} 选择 {current_api_type.upper()} API{suffix}")
        
        # 调用API处理
        success, result = self._process_with_api(current_api_type, content, file_path)
        
        # 5. 处理结果
        if success and result:
            # 保存脱水后的内容并创建缓存
            save_condensed_novel(file_path, result, output_dir=self.output_dir)
            create_cache_for_file(content, result, file_path, output_dir=self.output_dir)
            
            # 更新统计信息
            condensation_ratio = (len(result) / len(content)) * 100 if len(content) > 0 else 0
            self._update_stats(
                file_path, 
                "success", 
                start_time, 
                retry_attempt,
                original_length=len(content),
                condensed_length=len(result),
                condensation_ratio=condensation_ratio
            )
            
            # 输出完成信息
            if file_index is not None and total_files is not None:
                logger.info(f"[{file_index}/{total_files}] 处理完成")
            
            return True
        else:
            # 处理失败，保存错误信息
            error_msg = f"# 脱水处理失败\n\n原因: API处理失败\n\n时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n请重试或联系管理员。"
            logger.error(f"处理失败: {base_name}")
            
            try:
                save_condensed_novel(file_path, error_msg, output_dir=self.output_dir)
            except:
                pass
            
            # 更新统计信息
            self._update_stats(file_path, "failed", start_time, retry_attempt)
            
            return False
    
    def _log_process_info(self, file_path, file_index, total_files, retry_attempt):
        """记录处理信息"""
        base_name = os.path.basename(file_path)
        
        if file_index is not None and total_files is not None:
            prefix = f"\n第 {retry_attempt} 次重试处理" if retry_attempt > 0 else "\n处理文件"
            logger.info(f"{prefix} [{file_index}/{total_files}]: {base_name}")
        else:
            logger.info(f"\n处理文件: {base_name}")
    
    def _should_skip_file(self, file_path, output_file, start_time, retry_attempt):
        """检查是否应该跳过文件处理"""
        base_name = os.path.basename(file_path)
        
        if os.path.exists(output_file) and not self.force_regenerate:
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
                
                # 检查文件是否过小或包含错误信息
                if len(existing_content) < 300 or "错误" in existing_content[:100] or "失败" in existing_content[:100]:
                    reason = "小于300个字符" if len(existing_content) < 300 else "包含错误信息"
                    logger.info(f"已存在的脱水文件 {base_name} {reason}，将重新脱水")
                    try:
                        os.remove(output_file)
                    except:
                        logger.warning(f"删除已存在的文件失败: {output_file}")
                else:
                    # 文件存在且有效，跳过处理
                    logger.info(f"跳过{'第 '+str(retry_attempt)+' 次重试的' if retry_attempt > 0 else ''}已处理文件: {base_name}")
                    self._update_stats(file_path, "skipped", start_time, retry_attempt)
                    return True
            except Exception as e:
                logger.warning(f"检查已存在文件时出错: {str(e)}，将重新脱水")
                try:
                    os.remove(output_file)
                except:
                    pass
        
        return False
    
    def _handle_special_cases(self, file_path, content, start_time, retry_attempt):
        """处理特殊情况：缓存、目录文件和短内容"""
        base_name = os.path.basename(file_path)
        
        # 尝试使用缓存
        if not self.force_regenerate:
            cached_content = get_cached_content(file_path, output_dir=self.output_dir)
            if cached_content:
                logger.info(f"使用缓存的处理结果: {base_name}")
                save_condensed_novel(file_path, cached_content, output_dir=self.output_dir)
                self._update_stats(
                    file_path, "success-cached", start_time, retry_attempt,
                    original_length=len(content), condensed_length=len(cached_content)
                )
                return True, cached_content
        
        # 检查是否是目录文件
        if is_directory_file(content):
            logger.info(f"检测到目录文件，直接保存: {base_name}")
            save_directory_file(file_path, output_dir=self.output_dir)
            self._update_stats(file_path, "success-directory", start_time, retry_attempt)
            return True, content
        
        # 检查内容是否需要处理（太短的内容不处理）
        if len(content) < 100:
            logger.info(f"内容太短，不需要脱水: {base_name}")
            save_condensed_novel(file_path, content, output_dir=self.output_dir)
            self._update_stats(file_path, "success-short", start_time, retry_attempt)
            return True, content
        
        # 需要继续处理
        return False, None
    
    def _process_with_api(self, api_type, content, file_path):
        """使用API处理内容"""
        base_name = os.path.basename(file_path)
        max_api_attempts = 3
        
        # 获取对应的API管理器和函数
        key_manager = self.gemini_key_manager if api_type == "gemini" else self.openai_key_manager
        api_function = condense_novel_gemini if api_type == "gemini" else condense_novel_openai
        
        # 尝试API调用，最多尝试max_api_attempts次
        for api_attempt in range(max_api_attempts):
            if api_attempt > 0:
                logger.debug(f"尝试使用新的{api_type.upper()}密钥进行第{api_attempt+1}次尝试...")
            
            # 调用API服务
            result = api_function(content, None, key_manager)
            
            # 检查是否因为所有密钥都被跳过而失败
            if result is None and key_manager and hasattr(key_manager, 'skipped_keys'):
                valid_keys = [conf['key'] for conf in key_manager.api_configs 
                              if conf['key'] not in key_manager.skipped_keys]
                if not valid_keys:
                    logger.warning(f"处理文件 {base_name} 失败：所有{api_type.upper()}密钥都因失败次数过多而被跳过")
                    return False, None
            
            if result:
                return True, result
        
        return False, None
    
    def _update_stats(self, file_path, status, start_time, retry_attempt=0, **kwargs):
        """更新统计信息并返回结果"""
        process_time = time.time() - start_time
        update_file_stats(
            file_path, status, process_time, 
            is_first_attempt=(retry_attempt == 0), **kwargs
        )
        
        return status in ["success", "success-cached", "success-directory", "success-short", "skipped"]


def parse_and_find_files():
    """统一命令行参数解析和文件查找"""
    global OUTPUT_DIR
    
    parser = argparse.ArgumentParser(description="小说内容提取工具")
    
    # 文件和目录参数
    parser.add_argument("-i", "--input", help="输入文件或目录的路径")
    parser.add_argument("-o", "--output", help="输出目录的路径")
    parser.add_argument("-p", "--pattern", help="文件名匹配模式")
    parser.add_argument("-r", "--range", help="文件序号范围，格式为'start-end'")
    
    # API参数
    parser.add_argument("--api", help="使用的API类型", choices=["gemini", "openai", "mixed"], default="gemini")
    parser.add_argument("--validate-only", help="仅验证配置和API密钥，不执行处理", action="store_true")
    parser.add_argument("--gemini-key", help="直接指定Gemini API密钥")
    parser.add_argument("--openai-key", help="直接指定OpenAI API密钥")
    
    # 处理参数
    parser.add_argument("--workers", help="并发工作线程数", type=int, default=1)
    parser.add_argument("--force", help="强制重新生成已存在的文件", action="store_true")
    parser.add_argument("--test", help="测试模式，只处理前5个文件", action="store_true")
    parser.add_argument("--parse-dir", help="解析指定目录中的所有txt文件", action="store_true")
    parser.add_argument("--debug", help="启用调试日志", action="store_true")
    
    args = parser.parse_args()
    
    # 处理直接指定的API密钥
    if args.gemini_key:
        logger.info("使用命令行指定的Gemini API密钥")
        config.GEMINI_API_CONFIG = [{"key": args.gemini_key}]
        
    if args.openai_key:
        logger.info("使用命令行指定的OpenAI API密钥")
        config.OPENAI_API_CONFIG = [{"key": args.openai_key}]
        
    # 查找要处理的文件
    files_to_process = []
    
    if args.input:
        input_path = args.input
        if os.path.isfile(input_path):
            # 单个文件处理
            files_to_process = [input_path]
            # 默认输出目录
            if not args.output:
                file_dir = os.path.dirname(input_path) or "."
                file_base = os.path.splitext(os.path.basename(input_path))[0]
                OUTPUT_DIR = os.path.join(file_dir, f"{file_base}_脱水")
        elif os.path.isdir(input_path):
            # 目录处理
            if args.pattern:
                # 使用模式查找文件
                num_range = None
                if args.range:
                    try:
                        start, end = map(int, args.range.split("-"))
                        num_range = (start, end)
                    except ValueError:
                        logger.error(f"范围格式错误: {args.range}，应为'start-end'")
                        return args, [], None
                
                # 查找匹配的文件
                files_to_process = find_matching_files(
                    os.path.join(input_path, args.pattern),
                    num_range,
                    args.debug
                )
            else:
                # 处理目录下所有TXT文件
                for root, _, files in os.walk(input_path):
                    files_to_process.extend([os.path.join(root, f) for f in files if f.endswith(".txt")])
                
                # 按文件名排序
                files_to_process.sort()
            
            # 默认输出目录
            if not args.output:
                dir_name = os.path.basename(input_path.rstrip("/\\"))
                OUTPUT_DIR = os.path.join(input_path, f"{dir_name}_脱水")
        else:
            logger.error(f"输入路径不存在: {input_path}")
            return args, [], None
    else:
        # 仅指定了模式，在当前目录下查找
        num_range = None
        if args.range:
            try:
                start, end = map(int, args.range.split("-"))
                num_range = (start, end)
            except ValueError:
                logger.error(f"范围格式错误: {args.range}，应为'start-end'")
                return args, [], None
        
        # 查找匹配的文件
        files_to_process = find_matching_files(args.pattern, num_range, args.debug)
        
        # 默认输出目录
        if not args.output:
            OUTPUT_DIR = "脱水_输出"
    
    # 如果指定了输出目录，使用指定的
    if args.output:
        OUTPUT_DIR = args.output
    
    # 确保输出目录存在
    if OUTPUT_DIR:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        logger.info(f"输出目录: {OUTPUT_DIR}")
        
        # 更新输出目录到 file_utils（避免 sys.modules 注入）
        try:
            from . import file_utils as _file_utils_module
            _file_utils_module.OUTPUT_DIR = OUTPUT_DIR
        except Exception:
            pass
    
    # 测试模式只处理前5个文件
    if args.test and len(files_to_process) > 5:
        logger.info("测试模式: 只处理前5个文件")
        files_to_process = files_to_process[:5]
    
    return args, files_to_process, OUTPUT_DIR

def main():
    """主函数"""
    # 解析命令行参数并查找文件
    args, files_to_process, output_dir = parse_and_find_files()
    
    # 配置日志级别
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("已启用调试日志")
    
    # 初始化处理器
    condenser = NovelCondenser(
        api_type=args.api, 
        workers=args.workers, 
        force_regenerate=args.force
    )
    
    # 验证API密钥
    if not condenser.validate_api_keys():
        logger.error("API密钥验证失败，程序退出")
        return 1
    
    # 如果只是验证模式
    if args.validate_only:
        logger.info("API密钥验证成功，验证模式运行完成")
        return 0
    
    # 检查文件
    if not files_to_process:
        logger.error("未找到要处理的文件")
        return 1
    
    if args.input and os.path.isdir(args.input) and not args.parse_dir and not args.pattern:
        logger.error("输入路径是目录，但未指定 --parse-dir 参数或 --pattern 参数。如需处理目录，请添加参数")
        return 1
    
    # 处理文件
    success_count, failed_files = condenser.process_files(files_to_process)
    
    # 打印处理结果摘要
    total_files = len(files_to_process)
    logger.info(f"处理完成: 共 {total_files} 个文件，成功 {success_count} 个，失败 {len(failed_files)} 个")
    
    # 如果有失败的文件，打印它们
    if failed_files:
        logger.warning("失败的文件:")
        for file_path in failed_files:
            logger.warning(f"  - {file_path}")
    
    # 打印统计信息
    try:
        print_processing_summary()
    except:
        pass
    
    return 0 if len(failed_files) == 0 else 1

# 添加兼容层 - 为了保持与旧API的兼容性
def process_single_file(
    file_path,
    api_type="gemini",
    api_key_config=None,
    file_index=None,
    total_files=None,
    retry_attempt=0,
    force_regenerate=False,
    output_dir=None,
    min_condensation_ratio=None,
    max_condensation_ratio=None,
    target_condensation_ratio=None,
):
    """兼容层函数 - 处理单个文件
    
    此函数是为了保持与旧版API的兼容性而添加的，内部调用NovelCondenser.process_single_file方法
    """
    # 创建一个临时的NovelCondenser实例
    condenser = NovelCondenser(
        api_type=api_type,
        force_regenerate=force_regenerate,
        output_dir=output_dir,
        min_condensation_ratio=min_condensation_ratio,
        max_condensation_ratio=max_condensation_ratio,
        target_condensation_ratio=target_condensation_ratio,
    )
    
    # 调用实例方法处理文件
    return condenser.process_single_file(
        file_path=file_path,
        file_index=file_index,
        total_files=total_files,
        retry_attempt=retry_attempt
    )

def process_files_concurrently(
    file_paths,
    max_workers,
    api_type="gemini",
    force_regenerate=False,
    update_progress_func=None,
    output_dir=None,
    stop_event=None,
    min_condensation_ratio=None,
    max_condensation_ratio=None,
    target_condensation_ratio=None,
):
    """兼容层函数 - 并发处理文件
    
    此函数是为了保持与旧版API的兼容性而添加的，内部调用NovelCondenser._process_files_concurrently方法
    """
    # 创建一个临时的NovelCondenser实例
    condenser = NovelCondenser(
        api_type=api_type,
        workers=max_workers,
        force_regenerate=force_regenerate,
        output_dir=output_dir,
        min_condensation_ratio=min_condensation_ratio,
        max_condensation_ratio=max_condensation_ratio,
        target_condensation_ratio=target_condensation_ratio,
    )
    
    # 获取文件总数
    total_files = len(file_paths)
    
    # 为GUI停止按钮暴露一个可设置的停止事件
    stop_event = stop_event or threading.Event()
    try:
        # 将事件挂在函数对象上，方便外部通过引用设置
        process_files_concurrently.progress_stopped = stop_event
    except Exception:
        pass

    # 调用实例方法处理文件
    try:
        return condenser._process_files_concurrently(file_paths, total_files, stop_event=stop_event)
    finally:
        # 清理挂载的事件，避免影响后续调用
        try:
            delattr(process_files_concurrently, 'progress_stopped')
        except Exception:
            pass

if __name__ == "__main__":
    main() 
