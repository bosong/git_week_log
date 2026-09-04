#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""向后兼容入口：等价于 `python3 main.py ...`。

真正实现见 git_week_log.cli；也通过 `git_week_log` console script 直接调用。
"""

import sys

from git_week_log.cli import main

if __name__ == "__main__":
    sys.exit(main())