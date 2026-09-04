#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""git_week_log 命令行入口（供 console script `git_week_log` 调用）。"""

import argparse
import sys

from . import config
from . import workflow


def _mask_cookie(cookie):
    """脱敏显示 Cookie，仅显示前 12 个字符。"""
    if not cookie:
        return ""
    if len(cookie) <= 12:
        return "****"
    return cookie[:12] + "…"


def cmd_show(args):
    data = config.get_all()
    print("当前配置：")
    print(f"  Cookie      : {_mask_cookie(data['cookie'])}")
    print(f"  Git 目录    : {data['git_dir']}")
    print(f"  Git 用户    : {data['git_user']}")
    print(f"  周报姓名    : {data['weekly_name']}")
    print(f"  确认开关    : {'开启' if data['confirm'] else '关闭'}")
    print(f"  文档 URL    : {data['doc_url']}")
    return 0


def cmd_do(args):
    return workflow.run_do(mode=args.mode, content=args.content,
                           progress=args.progress, next_week=args.next_week,
                           force_yes=args.yes)


def _set(key, value):
    config.set(key, value)
    print(f"已保存 {key}。")
    return 0


def cmd_set_confirm(args):
    v = args.value.strip().lower()
    if v in ("on", "true", "1", "yes", "开启"):
        config.set("confirm", True)
        print("确认开关已开启。")
    elif v in ("off", "false", "0", "no", "关闭"):
        config.set("confirm", False)
        print("确认开关已关闭。")
    else:
        print("无效值，请输入 on 或 off。")
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="git_week_log",
        description="从 Git 提交自动归纳并写入企业微信周报。",
    )
    sub = parser.add_subparsers(dest="command", metavar="命令")

    # 各配置命令
    p = sub.add_parser("set-cookie", help="设置企业微信 Cookie")
    p.add_argument("value", help="Cookie 字符串")
    p.set_defaults(func=lambda a: _set("cookie", a.value))

    p = sub.add_parser("set-git-dir", help="设置 Git 工作库目录")
    p.add_argument("value", help="目录路径，多个目录用分号(;或；)分隔")
    p.set_defaults(func=lambda a: _set("git_dir", a.value))

    p = sub.add_parser("set-git-user", help="设置 Git 提交者用户名")
    p.add_argument("value", help="用户名")
    p.set_defaults(func=lambda a: _set("git_user", a.value))

    p = sub.add_parser("set-weekly-name", help="设置周报中的姓名")
    p.add_argument("value", help="姓名")
    p.set_defaults(func=lambda a: _set("weekly_name", a.value))

    p = sub.add_parser("set-confirm", help="设置是否确认日志内容 (on/off)")
    p.add_argument("value", help="on 或 off")
    p.set_defaults(func=cmd_set_confirm)

    p = sub.add_parser("set-doc-url", help="设置周报总文档 URL")
    p.add_argument("value", help="文档 URL")
    p.set_defaults(func=lambda a: _set("doc_url", a.value))

    # 查看配置
    sub.add_parser("show", help="查看当前配置").set_defaults(func=cmd_show)

    # 核心工作流
    p = sub.add_parser("do", help="写本周周报（auto 自动 / custom 自定义）")
    p.add_argument("mode", nargs="?", choices=["auto", "custom"],
                   help="模式：auto 自动总结（进度固定 100%%），custom 自定义录入；省略则交互选择")
    p.add_argument("content", nargs="?",
                   help="custom 模式的日志内容，多条用分号(;或；)分隔，自动加序号；"
                        "单条进度可在末尾用 - 或 － 指定，如 \"修复bug-80%\"；省略则进入交互录入")
    p.add_argument("--progress", default=None,
                   help="custom 传 content 参数时未带进度的条的默认进度（默认 100%%）")
    p.add_argument("--nextWeek", "--nextweek", dest="next_week", default=None,
                   help="下周重点计划，多条用分号(;或；)分隔，自动加序号。"
                        "auto 不带则不写入该列；custom 必填，缺省则交互询问")
    p.add_argument("--yes", action="store_true", help="跳过内容确认（仅 auto 模式）")
    p.set_defaults(func=cmd_do)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)