#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置存储模块：负责读写 ~/.git_week_log/config.json"""

import json
import os

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".git_week_log")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

# 配置项默认值
DEFAULTS = {
    "cookie": "",
    "git_dir": "",
    "git_user": "",
    "weekly_name": "",
    "confirm": False,
    "doc_url": "",
}


def _load() -> dict:
    """读取配置，文件不存在或损坏时返回默认配置"""
    if not os.path.exists(CONFIG_PATH):
        return dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULTS)

    merged = dict(DEFAULTS)
    merged.update(data)
    return merged


def _save(data: dict) -> None:
    """保存配置到磁盘，目录权限 700、文件权限 600"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.chmod(CONFIG_PATH, 0o600)


def get(key: str):
    """读取单个配置项"""
    return _load().get(key, DEFAULTS.get(key))


def set(key: str, value) -> None:
    """写入单个配置项"""
    if key not in DEFAULTS:
        raise KeyError(f"未知配置项：{key}")
    data = _load()
    data[key] = value
    _save(data)


def get_all() -> dict:
    """读取全部配置"""
    return _load()


def missing_keys() -> list:
    """返回缺失（空值）的必填配置项列表"""
    required = ["cookie", "git_dir", "git_user", "weekly_name", "doc_url"]
    data = _load()
    missing = []
    for key in required:
        if not str(data.get(key, "")).strip():
            missing.append(key)
    return missing
