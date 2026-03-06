#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API密钥管理模块 - 基于每条配置的并发数分配请求
"""

import threading
import time
from typing import Dict, List, Optional, Tuple

from . import config
from ..utils import setup_logger

logger = setup_logger(__name__)


class APIKeyManager:
    """API密钥管理器：按配置实例的并发额度分配请求。"""

    def __init__(self, api_configs: List[Dict]):
        self.api_configs = api_configs

        for idx, api_config in enumerate(self.api_configs):
            concurrency = api_config.get("concurrency")
            if not isinstance(concurrency, int) or concurrency < 1:
                api_config["concurrency"] = config.DEFAULT_KEY_CONCURRENCY
            api_config["errors"] = 0
            api_config["consecutive_errors"] = 0
            api_config["cooling_until"] = 0
            if "_config_id" not in api_config:
                api_config["_config_id"] = f"cfg-{idx}"

        self.key_to_cfg_ids: Dict[str, set] = {}
        for api_config in self.api_configs:
            key_id = api_config.get("key")
            cfg_id = api_config.get("_config_id")
            if key_id and cfg_id:
                self.key_to_cfg_ids.setdefault(key_id, set()).add(cfg_id)

        self.key_usage = {api_config["_config_id"]: 0 for api_config in self.api_configs}
        self.success_rates = {api_config["_config_id"]: 1.0 for api_config in self.api_configs}
        self.success_counts = {api_config["_config_id"]: 0 for api_config in self.api_configs}
        self.error_counts = {api_config["_config_id"]: 0 for api_config in self.api_configs}
        self.next_key_index = 0
        self.skipped_keys = set()
        self.skipped_configs = set()
        self._local = threading.local()
        self.lock = threading.Lock()
        self.global_cooling_until = 0

        logger.info(
            f"已初始化API密钥管理器，共{len(api_configs)}个密钥，总并发额度:{self.get_max_concurrency()}"
        )

    def get_key_config(self):
        """获取可用的API密钥配置。"""
        max_wait_attempts = 60
        wait_attempts = 0
        backoff_count = 0

        while wait_attempts < max_wait_attempts:
            need_to_wait = True
            selected_key_config = None
            global_cooldown_remaining = 0.0

            with self.lock:
                current_time = time.time()
                if self.global_cooling_until > current_time:
                    global_cooldown_remaining = self.global_cooling_until - current_time
                else:
                    available_keys = []

                    for i, api_config in enumerate(self.api_configs):
                        cfg_id = api_config.get("_config_id")
                        if cfg_id in self.skipped_configs:
                            continue
                        if api_config.get("cooling_until", 0) > current_time:
                            continue

                        current_usage = self.key_usage.get(cfg_id, 0)
                        max_concurrency = api_config.get("concurrency", config.DEFAULT_KEY_CONCURRENCY)
                        if current_usage >= max_concurrency:
                            continue

                        load_ratio = current_usage / max_concurrency if max_concurrency > 0 else 1.0
                        success_rate = self.success_rates.get(cfg_id, 0.5)
                        rotation_weight = 1.0 - (((i - self.next_key_index) % len(self.api_configs)) / len(self.api_configs))
                        score = (success_rate * 0.5) - (load_ratio * 0.3) + (rotation_weight * 0.2)
                        available_keys.append((cfg_id, score, api_config, i))

                    if available_keys:
                        selected_cfg_id, _, selected_key_config, selected_index = max(
                            available_keys,
                            key=lambda item: item[1],
                        )
                        self.key_usage[selected_cfg_id] = self.key_usage.get(selected_cfg_id, 0) + 1
                        self.next_key_index = (selected_index + 1) % len(self.api_configs)
                        self._local.last_cfg_id = selected_cfg_id
                        need_to_wait = False
                    elif wait_attempts == 0:
                        logger.debug("当前所有API配置都已达到并发上限或处于冷却期，等待中...")

            if not need_to_wait and selected_key_config:
                return selected_key_config.copy()

            if global_cooldown_remaining > 0:
                if wait_attempts == 0:
                    logger.warning(f"所有密钥处于冷却或跳过状态，进入全局冷却，预计等待{int(global_cooldown_remaining)}秒...")
                time.sleep(min(5.0, global_cooldown_remaining))
                continue

            wait_attempts += 1
            wait_time = min(0.5 * (2 ** backoff_count), 5.0)
            if wait_attempts % 3 == 0:
                backoff_count += 1
            time.sleep(wait_time)

        logger.warning("等待可用API密钥超时，放弃处理...")
        return None

    def _resolve_cfg_target(self, key) -> Tuple[Optional[str], Optional[Dict]]:
        if isinstance(key, dict):
            cfg_id = key.get("_config_id")
            if cfg_id:
                for api_config in self.api_configs:
                    if api_config.get("_config_id") == cfg_id:
                        return cfg_id, api_config
            key_value = key.get("key")
            if key_value:
                for api_config in self.api_configs:
                    if api_config.get("key") == key_value:
                        return api_config.get("_config_id"), api_config
            return None, None

        cfg_id = getattr(self._local, "last_cfg_id", None)
        if cfg_id is None:
            return None, None
        for api_config in self.api_configs:
            if api_config.get("_config_id") == cfg_id:
                return cfg_id, api_config
        return None, None

    def release_key(self, key) -> None:
        """释放配置实例占用的并发额度。"""
        cfg_id, _ = self._resolve_cfg_target(key)
        if not cfg_id:
            return
        with self.lock:
            self.key_usage[cfg_id] = max(0, self.key_usage.get(cfg_id, 0) - 1)

    def report_success(self, key) -> None:
        """报告API密钥请求成功。"""
        cfg_id, target_config = self._resolve_cfg_target(key)
        if not cfg_id or not target_config:
            return

        with self.lock:
            current_rate = self.success_rates.get(cfg_id, 0.5)
            self.success_rates[cfg_id] = current_rate * 0.9 + 0.1
            self.success_counts[cfg_id] = self.success_counts.get(cfg_id, 0) + 1
            target_config["consecutive_errors"] = 0
            self.global_cooling_until = 0

    def report_error(self, key) -> None:
        """报告API密钥请求失败。"""
        cfg_id, target_config = self._resolve_cfg_target(key)
        if not cfg_id or not target_config:
            return

        with self.lock:
            current_rate = self.success_rates.get(cfg_id, 0.5)
            self.success_rates[cfg_id] = current_rate * 0.9
            self.error_counts[cfg_id] = self.error_counts.get(cfg_id, 0) + 1

            target_config["errors"] = target_config.get("errors", 0) + 1
            target_config["consecutive_errors"] = target_config.get("consecutive_errors", 0) + 1

            now_ts = time.time()
            if target_config["consecutive_errors"] >= 5:
                cooling_time = 600
                target_config["cooling_until"] = now_ts + cooling_time
                logger.warning("密钥连续失败超过5次，暂停使用10分钟")
            elif target_config["consecutive_errors"] >= 3:
                cooling_time = min(30 * (2 ** (target_config["consecutive_errors"] - 3)), 600)
                target_config["cooling_until"] = now_ts + cooling_time
                logger.warning(f"密钥连续失败{target_config['consecutive_errors']}次，进入冷却期{cooling_time}秒")

            if target_config["errors"] >= 20:
                self.skipped_configs.add(cfg_id)
                key_str = target_config.get("key")
                if key_str:
                    cfg_ids = self.key_to_cfg_ids.get(key_str, set())
                    if cfg_ids and cfg_ids.issubset(self.skipped_configs):
                        self.skipped_keys.add(key_str)
                logger.warning("密钥配置实例错误次数过多，本次脱水将跳过该实例")

            all_unavailable = True
            for api_config in self.api_configs:
                cfg = api_config.get("_config_id")
                if cfg in self.skipped_configs:
                    continue
                if api_config.get("cooling_until", 0) > now_ts:
                    continue
                all_unavailable = False
                break

            if all_unavailable:
                self.global_cooling_until = max(self.global_cooling_until, now_ts + 600)
                logger.warning("所有密钥暂不可用，进入全局冷却10分钟")

    def get_max_concurrency(self) -> int:
        """返回当前配置支持的总并发数。"""
        if not self.api_configs:
            return 1
        total = 0
        for api_config in self.api_configs:
            value = api_config.get("concurrency", config.DEFAULT_KEY_CONCURRENCY)
            total += value if isinstance(value, int) and value > 0 else config.DEFAULT_KEY_CONCURRENCY
        return max(1, total)

    def get_runtime_stats(self, api_type: str) -> List[Dict]:
        """返回当前任务周期内的配置运行状态快照。"""
        now_ts = time.time()
        snapshot: List[Dict] = []
        with self.lock:
            for index, api_config in enumerate(self.api_configs):
                cfg_id = api_config.get("_config_id")
                cooling_until = api_config.get("cooling_until", 0)
                cooling_seconds = max(0, int(cooling_until - now_ts))

                if cfg_id in self.skipped_configs:
                    status = "已跳过"
                elif cooling_until > now_ts:
                    status = f"冷却中({cooling_seconds}s)"
                elif self.key_usage.get(cfg_id, 0) > 0:
                    status = "运行中"
                else:
                    status = "空闲"

                key_value = api_config.get("key", "")
                key_preview = (key_value[:8] + "...") if key_value else "未配置"
                name = (api_config.get("name") or "").strip() or key_preview
                success_count = self.success_counts.get(cfg_id, 0)
                error_count = self.error_counts.get(cfg_id, 0)
                total_requests = success_count + error_count
                success_rate = round((success_count / total_requests) * 100, 1) if total_requests else 0.0

                snapshot.append({
                    "api_type": api_type,
                    "index": index,
                    "name": name,
                    "key_preview": key_preview,
                    "status": status,
                    "active_concurrency": self.key_usage.get(cfg_id, 0),
                    "configured_concurrency": api_config.get("concurrency", config.DEFAULT_KEY_CONCURRENCY),
                    "success_count": success_count,
                    "error_count": error_count,
                    "success_rate": success_rate,
                })
        return snapshot

    def reset_cooldowns(self) -> None:
        """重置所有密钥的冷却时间和错误计数。"""
        with self.lock:
            for api_config in self.api_configs:
                api_config["cooling_until"] = 0
                api_config["errors"] = 0
                api_config["consecutive_errors"] = 0
            self.skipped_configs.clear()
            self.skipped_keys.clear()
            self.global_cooling_until = 0
            for cfg_id in self.key_usage:
                self.key_usage[cfg_id] = 0
            for cfg_id in self.success_counts:
                self.success_counts[cfg_id] = 0
            for cfg_id in self.error_counts:
                self.error_counts[cfg_id] = 0
            logger.info("已重置所有API配置实例的冷却时间、错误计数和跳过标记")
