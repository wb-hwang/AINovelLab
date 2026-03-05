#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI小说工具 - 版本信息
"""

# 版本号格式：主版本号.次版本号.修订号
VERSION = "0.0.9"
VERSION_INFO = (0, 0, 9)  # 用于程序内部比较2
# 构建信息
BUILD_DATE = "2025-09-07"  # 更新构建日期
BUILD_TYPE = "release"  # release, beta, alpha, dev

# 版本字符串
VERSION_STRING = f"AI小说工具 v{VERSION} ({BUILD_TYPE})"

def get_version():
    """获取版本号"""
    return VERSION

def get_version_info():
    """获取版本信息元组"""
    return VERSION_INFO

def get_version_string():
    """获取完整版本字符串"""
    return VERSION_STRING 