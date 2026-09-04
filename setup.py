#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""setuptools 打包脚本：提供 console script `git_week_log`。"""
from setuptools import setup, find_packages

setup(
    name="git-week-log",
    version="0.1.0",
    description="从 Git 提交自动归纳并写入企业微信周报",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=["playwright>=1.40.0"],
    entry_points={
        "console_scripts": [
            "git_week_log=git_week_log.cli:main",
        ],
    },
)