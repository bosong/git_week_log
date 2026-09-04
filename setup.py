#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""setuptools 打包脚本：提供 console script `git_week_log`。"""
from setuptools import setup, find_packages

setup(
    name="git-week-log",
    version="0.1.0",
    description="从 Git 提交自动归纳并写入企业微信周报",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        # Playwright 1.49 起要求 Python>=3.9；3.8 用户锁定 1.40~1.48
        "playwright>=1.40.0,<1.49; python_version < '3.9'",
        "playwright>=1.49.0; python_version >= '3.9'",
    ],
    entry_points={
        "console_scripts": [
            "git_week_log=git_week_log.cli:main",
        ],
    },
)