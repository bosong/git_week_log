#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""setuptools 打包脚本：提供 console script `git_week_log`。"""
from setuptools import setup, find_packages

setup(
    name="git-week-log",
    version="0.1.5",
    description="从 Git 提交自动归纳并写入企业微信周报",
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=[
        # Playwright 各版本要求的 Python：
        #   <3.8 只能装 1.34~1.35（1.36 起要求 >=3.8）
        #   3.8   装 1.40~1.48（1.49 起要求 >=3.9）
        #   >=3.9 装最新
        "playwright>=1.34.0,<1.36; python_version < '3.8'",
        "playwright>=1.40.0,<1.49; python_version >= '3.8' and python_version < '3.9'",
        "playwright>=1.49.0; python_version >= '3.9'",
    ],
    entry_points={
        "console_scripts": [
            "git_week_log=git_week_log.cli:main",
        ],
    },
)