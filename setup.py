#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""setuptools 打包脚本：提供 console script `git_week_log`。"""
import os
import re

from setuptools import setup, find_packages

# 版本号唯一来源：git_week_log/__init__.py 的 __version__
_here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_here, "git_week_log", "__init__.py"), encoding="utf-8") as _f:
    _version = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
        _f.read(), re.M,
    ).group(1)

setup(
    name="git-week-log",
    version=_version,
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