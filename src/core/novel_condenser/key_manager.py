#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API密钥管理模块 - 管理API密钥的分配和使用频率
"""

import time
import threading
from collections import deque
from typing import Dict, List, Optional

# 导入配置
try:
    from . import config
    from ..utils import setup_logger
except ImportError:
    import config
    from utils import setup_logger

# 设置日志记录器
logger = setup_logger(__name__)

class APIKeyManager:
    """API密钥管理器：管理多个API密钥的分配和使用状态，并控制请求频率"""
    
    def __init__(self, api_configs: List[Dict], max_rpm: int = config.DEFAULT_MAX_RPM):
        """初始化密钥管理器

        Args:
            api_configs: API配置列表，每个配置包含key、redirect_url、model和rpm
            max_rpm: 全局最大每分钟请求数
        """
        self.api_configs = api_configs
        self.max_rpm = max_rpm
        
        # 为每个密钥添加默认rpm值和错误计数，并分配配置实例ID
        for idx, api_config in enumerate(self.api_configs):
            if "rpm" not in api_config or not api_config["rpm"]:
                api_config["rpm"] = config.DEFAULT_KEY_RPM
            api_config["errors"] = 0  # 初始化错误计数
            api_config["consecutive_errors"] = 0  # 连续错误计数
            api_config["cooling_until"] = 0  # 冷却期截止时间
            # 分配稳定的配置实例ID（用于在相同key下区分不同实例）
            if "_config_id" not in api_config:
                api_config["_config_id"] = f"cfg-{idx}"
        
        # 建立 key -> 配置实例ID 集合 的映射
        self.key_to_cfg_ids = {}
        for api_config in api_configs:
            key_id = api_config.get('key')
            cfg_id = api_config.get('_config_id')
            if key_id and cfg_id:
                self.key_to_cfg_ids.setdefault(key_id, set()).add(cfg_id)

        # 初始化按配置实例维度的使用追踪
        self.key_usage = {api_config['_config_id']: 0 for api_config in api_configs}
        
        # 用于RPM控制的请求时间队列（每个配置实例维护一个最近请求时间队列）
        self.request_timestamps = {api_config['_config_id']: deque(maxlen=max(api_config['rpm'], config.DEFAULT_KEY_RPM)) 
                                  for api_config in api_configs}
        
        # 每个配置实例的请求成功率
        self.success_rates = {api_config['_config_id']: 1.0 for api_config in api_configs}  # 初始成功率为100%
        
        # 全局请求时间队列
        self.global_request_timestamps = deque(maxlen=max_rpm)
        
        # 每个密钥的最大RPM限制
        self.max_key_rpm = max(api_config.get('rpm', config.DEFAULT_KEY_RPM) for api_config in api_configs) if api_configs else config.DEFAULT_KEY_RPM
        
        # 密钥轮换索引 - 用于实现简单的轮询策略
        self.next_key_index = 0
        
        # 标记本次脱水中应该跳过的密钥（兼容旧逻辑）与配置实例（新逻辑）
        self.skipped_keys = set()
        self.skipped_configs = set()

        # 线程局部存储：记录本线程最近一次选中的配置实例ID，用于后续success/error归属
        self._local = threading.local()
        
        self.lock = threading.Lock()
        # 全局冷却时间戳（当所有密钥均不可用时触发，单位：秒）
        self.global_cooling_until = 0

        # 打印初始化信息
        logger.info(f"已初始化API密钥管理器，共{len(api_configs)}个密钥，全局RPM上限:{max_rpm}")
    
    def get_key_config(self):
        """获取可用的API密钥配置
        
        使用更智能的密钥选择策略，考虑密钥的负载均衡、成功率和错误历史
        
        Returns:
            API密钥配置字典或者None（如果没有可用的密钥）
        """
        # 最大等待次数（60次 * 0.5秒 = 最多等待30秒）
        max_wait_attempts = 60
        wait_attempts = 0
        backoff_count = 0  # 用于指数退避
        
        while wait_attempts < max_wait_attempts:
            need_to_wait = True  # 标记是否需要等待
            selected_key_config = None
            global_cooldown_remaining = 0.0
            
            with self.lock:
                current_time = time.time()
                # 如果处于全局冷却期，记录剩余时间
                if self.global_cooling_until > current_time:
                    global_cooldown_remaining = self.global_cooling_until - current_time
                
                # 清理过期的请求记录
                self._clean_expired_requests(self.global_request_timestamps)
                
                # 检查全局RPM限制
                if len(self.global_request_timestamps) >= self.max_rpm:
                    # 全局请求限制逻辑
                    need_to_wait = True
                    if wait_attempts == 0:  # 只在第一次打印
                        logger.debug(f"当前全局API请求已达到并发上限({self.max_rpm})，等待中...")
                else:
                    # 找到当前可用且最优的配置实例
                    available_keys = []
                    
                    for i, api_config in enumerate(self.api_configs):
                        # 获取配置实例ID
                        cfg_id = api_config.get('_config_id')
                        key_id = api_config.get('key')
                        
                        # 检查密钥是否在冷却期
                        if api_config.get("cooling_until", 0) > current_time:
                            continue
                        
                        # 检查是否在跳过列表中（按配置实例）
                        if cfg_id in self.skipped_configs:
                            continue
                            
                        # 清理该配置实例的过期请求
                        if cfg_id in self.request_timestamps:
                            self._clean_expired_requests(self.request_timestamps[cfg_id])
                        
                        # 检查该密钥的RPM限制
                        key_rpm = len(self.request_timestamps.get(cfg_id, []))
                        max_key_rpm = api_config.get('rpm', config.DEFAULT_KEY_RPM)
                        
                        if key_rpm < max_key_rpm:
                            # 计算该密钥当前的负载率和得分
                            # 得分考虑三个因素：负载率、成功率、索引(为了轮询)
                            load_ratio = key_rpm / max_key_rpm if max_key_rpm > 0 else 0
                            success_rate = self.success_rates.get(cfg_id, 0.5)  # 默认50%成功率
                            
                            # 轮询权重 - 根据索引距离计算，越早轮到的索引得分越高
                            rotation_weight = 1.0 - (((i - self.next_key_index) % len(self.api_configs)) / len(self.api_configs))
                            
                            # 总分 = 成功率(50%) - 负载率(30%) + 轮询权重(20%)
                            score = (success_rate * 0.5) - (load_ratio * 0.3) + (rotation_weight * 0.2)
                            
                            available_keys.append((cfg_id, score, api_config, i))
                    
                    # 如果没有可用密钥，设置等待标志
                    if not available_keys:
                        need_to_wait = True
                        if wait_attempts == 0:  # 只在第一次打印
                            logger.debug("当前所有API密钥都已达到并发上限或在冷却期，等待中...")
                    else:
                        # 找到得分最高的配置实例
                        selected_key_info = max(available_keys, key=lambda x: x[1])
                        selected_cfg_id = selected_key_info[0]
                        selected_key_config = selected_key_info[2]
                        selected_index = selected_key_info[3]
                        
                        # 更新下一个密钥索引，实现轮询
                        self.next_key_index = (selected_index + 1) % len(self.api_configs)
                        
                        # 更新请求记录（按配置实例）
                        if selected_cfg_id not in self.request_timestamps:
                            self.request_timestamps[selected_cfg_id] = deque(maxlen=self.max_key_rpm)
                        
                        self.request_timestamps[selected_cfg_id].append(current_time)
                        self.global_request_timestamps.append(current_time)
                        # 记录本线程最近选中的配置实例ID
                        try:
                            self._local.last_cfg_id = selected_cfg_id
                            # 记录日志，优先使用name
                            name = selected_key_config.get('name') or ''
                            key_mask = (selected_key_config.get('key','')[:8] + '...') if selected_key_config.get('key') else ''
                            display = name if name else key_mask
                            logger.debug(f"选中API配置实例: {display}")
                        except Exception:
                            pass
                        
                        # 已找到配置，不需要等待
                        need_to_wait = False
            
            # 在锁外处理结果
            
            # 如果找到配置，返回
            if not need_to_wait and selected_key_config:
                if wait_attempts > 0:  # 如果之前有等待
                    # 打印当前选中实例的name/前缀
                    display = None
                    try:
                        cfg_id = getattr(self._local, 'last_cfg_id', None)
                        if cfg_id:
                            for ac in self.api_configs:
                                if ac.get('_config_id') == cfg_id:
                                    name = ac.get('name') or ''
                                    key_mask = (ac.get('key','')[:8] + '...') if ac.get('key') else ''
                                    display = name if name else key_mask
                                    break
                    except Exception:
                        pass
                    if display:
                        logger.debug(f"已获取可用API实例({display})，继续处理...")
                    else:
                        logger.debug(f"已获取可用API密钥，继续处理...")
                return selected_key_config.copy()
            
            # 需要等待的情况
            # 如果全局冷却中，则优先等待全局冷却结束（分段等待，不消耗尝试次数）
            if global_cooldown_remaining > 0:
                if wait_attempts == 0:
                    logger.warning(f"所有密钥处于冷却或跳过状态，进入全局冷却，预计等待{int(global_cooldown_remaining)}秒...")
                time.sleep(min(5.0, global_cooldown_remaining))
                continue

            wait_attempts += 1

            # 使用指数退避策略计算等待时间（最大5秒）
            wait_time = min(0.5 * (2 ** backoff_count), 5.0)

            # 每3次尝试增加退避计数
            if wait_attempts % 3 == 0:
                backoff_count += 1

            time.sleep(wait_time)
        
        # 超过最大等待次数，最终返回None
        logger.warning("等待可用API密钥超时，放弃处理...")
        return None
    
    def _clean_expired_requests(self, timestamp_queue: deque) -> None:
        """清理超过一分钟的请求记录

        Args:
            timestamp_queue: 时间戳队列
        """
        current_time = time.time()
        # 删除所有超过60秒的记录
        while timestamp_queue and current_time - timestamp_queue[0] > 60:
            timestamp_queue.popleft()
    
    def release_key(self, key) -> None:
        """释放API密钥的使用

        Args:
            key: 要释放的API密钥或配置
        """
        with self.lock:
            if isinstance(key, dict):
                cfg_id = key.get('_config_id')
            else:
                cfg_id = getattr(self._local, 'last_cfg_id', None)
            if cfg_id in self.key_usage:
                self.key_usage[cfg_id] = max(0, self.key_usage[cfg_id] - 1)
    
    def report_success(self, key) -> None:
        """报告API密钥请求成功
        
        Args:
            key: API密钥或配置字典
        """
        # 确定配置实例ID
        if isinstance(key, dict):
            cfg_id = key.get('_config_id')
            target_config = key
        else:
            cfg_id = getattr(self._local, 'last_cfg_id', None)
            target_config = None
            if cfg_id is None:
                return
            for api_config in self.api_configs:
                if api_config.get('_config_id') == cfg_id:
                    target_config = api_config
                    break
        if not cfg_id or not target_config:
            return
        
        with self.lock:
            # 更新成功率 (使用EMA-指数移动平均)
            current_rate = self.success_rates.get(cfg_id, 0.5)
            self.success_rates[cfg_id] = current_rate * 0.9 + 0.1  # 成功=1.0
            # 重置连续错误计数
            target_config["consecutive_errors"] = 0
            # 成功发生时，清除全局冷却（如果存在）
            self.global_cooling_until = 0
    
    def report_error(self, key) -> None:
        """报告API密钥请求失败
        
        Args:
            key: API密钥或配置字典
        """
        # 确定配置实例ID
        if isinstance(key, dict):
            cfg_id = key.get('_config_id')
            target_config = key
        else:
            cfg_id = getattr(self._local, 'last_cfg_id', None)
            target_config = None
            if cfg_id is None:
                return
            for api_config in self.api_configs:
                if api_config.get('_config_id') == cfg_id:
                    target_config = api_config
                    break
        if not cfg_id or not target_config:
            return
        
        with self.lock:
            # 更新成功率 (使用EMA-指数移动平均)
            current_rate = self.success_rates.get(cfg_id, 0.5)
            self.success_rates[cfg_id] = current_rate * 0.9  # 失败=0.0
            
            # 更新错误计数
            target_config["errors"] = target_config.get("errors", 0) + 1
            target_config["consecutive_errors"] = target_config.get("consecutive_errors", 0) + 1
            
            # 如果连续错误超过阈值，设置冷却期
            now_ts = time.time()
            if target_config["consecutive_errors"] >= 5:
                # 连续失败超过5次，直接暂停10分钟
                cooling_time = 600
                target_config["cooling_until"] = now_ts + cooling_time
                logger.warning("密钥连续失败超过5次，暂停使用10分钟")
            elif target_config["consecutive_errors"] >= 3:
                # 3-4次错误：采用指数退避冷却
                cooling_time = min(30 * (2 ** (target_config["consecutive_errors"] - 3)), 600)
                target_config["cooling_until"] = now_ts + cooling_time
                logger.warning(f"密钥连续失败{target_config['consecutive_errors']}次，进入冷却期{cooling_time}秒")
            
            # 如果总错误次数过多，加入跳过列表（按配置实例）
            if target_config["errors"] >= 20:
                self.skipped_configs.add(cfg_id)
                # 如果该key的所有实例都被跳过，则同步到skipped_keys（兼容旧逻辑）
                key_str = target_config.get('key')
                if key_str:
                    cfg_ids = self.key_to_cfg_ids.get(key_str, set())
                    if cfg_ids and cfg_ids.issubset(self.skipped_configs):
                        self.skipped_keys.add(key_str)
                logger.warning("密钥配置实例错误次数过多，本次脱水将跳过该实例")
                
                # 检查是否所有实例都被跳过
                remaining = [c for c in self.api_configs if c.get('_config_id') not in self.skipped_configs]
                if not remaining:
                    logger.warning("所有API配置实例都已因错误次数过多而被跳过，脱水过程将结束")

            # 如果所有密钥都不可用（被跳过或处于冷却期），触发全局冷却10分钟
            all_unavailable = True
            for c in self.api_configs:
                cfg = c.get('_config_id')
                if cfg in self.skipped_configs:
                    continue
                if c.get('cooling_until', 0) > now_ts:
                    continue
                # 发现至少一个可用
                all_unavailable = False
                break
            if all_unavailable:
                self.global_cooling_until = max(self.global_cooling_until, now_ts + 600)
                logger.warning("所有密钥暂不可用，进入全局冷却10分钟")
    
    def get_max_concurrency(self) -> int:
        """获取支持的最大并发数

        基于API密钥的数量和RPM限制计算最大并发数

        Returns:
            最大并发数
        """
        if not self.api_configs:
            return 1
        
        # 计算所有API密钥的RPM总和
        total_rpm = sum(api_config.get('rpm', config.DEFAULT_KEY_RPM) for api_config in self.api_configs)
        
        # 考虑每个密钥的实际限制
        adjusted_rpm = 0
        for api_config in self.api_configs:
            # 获取密钥的RPM设置
            key_rpm = api_config.get('rpm', config.DEFAULT_KEY_RPM)
            adjusted_rpm += key_rpm
        
        # 修改并发度计算逻辑，根据密钥数量和RPM值更合理地计算并发数
        # 1. 对于单个密钥，每5个RPM支持1个并发
        # 2. 对于多个密钥，根据密钥数量和总RPM值计算
        
        if len(self.api_configs) == 1:
            # 单个密钥时的计算逻辑：每5个RPM支持1个并发
            safest_concurrency = max(1, int(adjusted_rpm / 5))
        else:
            # 多个密钥时的计算逻辑：每10个RPM支持1个并发，但至少有密钥数量一半的并发数
            rpm_based = max(1, int(adjusted_rpm / 10))
            key_count_based = max(1, len(self.api_configs) // 2)
            safest_concurrency = max(rpm_based, key_count_based)
        
        # 确保至少返回1，如果密钥数量大于5，最大并发数也可以更高
        if len(self.api_configs) > 5:
            return min(max(safest_concurrency, len(self.api_configs)), 20) 
        else:
            return min(safest_concurrency, 10) 

    def reset_cooldowns(self) -> None:
        """重置所有密钥的冷却时间和错误计数，用于手动恢复所有密钥
        """
        with self.lock:
            for api_config in self.api_configs:
                api_config["cooling_until"] = 0
                api_config["errors"] = 0
                api_config["consecutive_errors"] = 0
            self.skipped_configs.clear()
            self.skipped_keys.clear()
            logger.info("已重置所有API配置实例的冷却时间、错误计数和跳过标记")