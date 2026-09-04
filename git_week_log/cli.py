#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""git_week_log 命令行入口（供 console script `git_week_log` 调用）。"""

import argparse
import sys

from . import __version__
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
    print(f"  Cookie          : {_mask_cookie(data['cookie'])}")
    print(f"  Git 目录        : {data['git_dir']}")
    print(f"  Git 用户        : {data['git_user']}")
    print(f"  周报姓名        : {data['weekly_name']}")
    print(f"  确认开关        : {'开启' if data['confirm'] else '关闭'}")
    print(f"  文档 URL        : {data['doc_url']}")
    print(f"  下周默认计划    : {data.get('nextweek_default', '')}")
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
        description="从 Git 提交自动归纳并写入企业微信周报文档。\n"
                    "完整使用流程：\n"
                    '  git_week_log set-cookie   "TOK=xxx; wedoc_sid=xxx; ..."  # 先配置(一次性)\n'
                    '  git_week_log set-git-dir  "后端:/repo/mp;前端:/repo/h5"    # 多仓库可用 别名:路径\n'
                    '  git_week_log set-git-user "zhangsan"\n'
                    '  git_week_log set-weekly-name "张三"\n'
                    '  git_week_log set-doc-url "https://doc.weixin.qq.com/sheet/<docid>?scode=<scode>&tab=<tab>"\n'
                    '  git_week_log set-nextweek-default "预警H5接入; 自选持仓迭代"  # 可选：下周计划默认值\n'
                    "  git_week_log show            # 查看已保存配置\n"
                    "  git_week_log do auto --yes   # 自动模式：自动归纳提交并写入\n"
                    '  git_week_log do custom       # 自定义模式：手动录入内容与进度\n'
                    "  git_week_log do custom \"功能A-80%; 功能B\" --nextWeek \"下周计划1; 下周计划2\"",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="各子命令的详细格式与示例，请执行：git_week_log <命令> --help\n"
               "最简单的方式：直接执行  git_week_log do  按提示选择模式并填写即可。",
    )
    parser.add_argument(
        "--version", action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command", metavar="命令")

    def _sub(name, **kwargs):
        """创建子命令 parser，保留 help 中多行示例的换行。"""
        return sub.add_parser(
            name, formatter_class=argparse.RawDescriptionHelpFormatter, **kwargs
        )

    # 各配置命令
    p = _sub(
        "set-cookie", help="设置企业微信 Cookie",
        description="保存访问企业微信周报文档所需的完整 Cookie。",
        epilog="格式示例：\n"
               '  git_week_log set-cookie "TOK=xxx; wedoc_sid=xxx; wedoc_ticket=xxx; ..."\n'
               "提示：从浏览器开发者工具 Network/Application 中复制完整 Cookie，"
               "多个键值用英文分号(;)间隔，不要截断。",
    )
    p.add_argument("value", help="完整 Cookie 字符串（含 TOK、wedoc_sid 等全部键值）")
    p.set_defaults(func=lambda a: _set("cookie", a.value))

    p = _sub(
        "set-git-dir", help="设置 Git 工作库目录",
        description="保存 Git 仓库路径，支持多个目录与别名前缀。",
        epilog="格式示例：\n"
               '  git_week_log set-git-dir "后端:/repo/mp;前端:/repo/h5"   # 别名:路径，多条用分号(;或；)分隔\n'
               '  git_week_log set-git-dir "/repo/mp"                        # 单目录不加别名\n'
               "说明：带别名时归纳日志会输出为 “1.别名：内容”；取日志时多仓库合并、按提交时间倒序。",
    )
    p.add_argument("value",
                   help="仓库路径；多目录用分号(;或；)分隔，每条可用“别名:路径”加别名")
    p.set_defaults(func=lambda a: _set("git_dir", a.value))

    p = _sub("set-git-user", help="设置 Git 提交者用户名",
                       description="按 Git 提交作者过滤日志。",
                       epilog="格式示例：git_week_log set-git-user \"zhangsan\"")
    p.add_argument("value", help="Git 提交者用户名（git config user.name）")
    p.set_defaults(func=lambda a: _set("git_user", a.value))

    p = _sub("set-weekly-name", help="设置周报中的姓名",
                       description="在周报工作表中定位该姓名所在行进行写入。",
                       epilog="格式示例：git_week_log set-weekly-name \"张三\"")
    p.add_argument("value", help="周报文档中显示的姓名（须与表格中完全一致）")
    p.set_defaults(func=lambda a: _set("weekly_name", a.value))

    p = _sub("set-confirm", help="设置是否确认日志内容 (on/off)",
                       description="开启后 auto 模式在写入前会展示归纳结果请求确认。",
                       epilog="格式示例：\n"
                              '  git_week_log set-confirm on\n'
                              '  git_week_log set-confirm off')
    p.add_argument("value", help="on/true/1/yes/开启 或 off/false/0/no/关闭")
    p.set_defaults(func=cmd_set_confirm)

    p = _sub("set-doc-url", help="设置周报总文档 URL",
             description="保存企业微信周报总文档链接。",
             epilog="格式示例：\n"
                    '  git_week_log set-doc-url "https://doc.weixin.qq.com/sheet/<docid>?scode=<scode>&tab=<tab>"')
    p.add_argument("value", help="周报文档 URL（doc.weixin.qq.com/sheet/... 完整链接）")
    p.set_defaults(func=lambda a: _set("doc_url", a.value))

    p = _sub("set-nextweek-default", help="设置下周重点计划默认值",
             description="保存下周重点计划的默认内容；执行 do 时未传 --nextWeek 则自动采用该默认值。",
             epilog="格式示例：\n"
                    '  git_week_log set-nextweek-default "预警H5接入; 自选持仓迭代"\n'
                    "说明：多条用分号(;或；)分隔。auto/custom 未传 --nextWeek 时都会使用该默认值；"
                    "传了 --nextWeek 则覆盖默认值。执行 git_week_log show 可查看当前默认值。")
    p.add_argument("value", help="下周重点计划内容（多条用分号(;或；)分隔）")
    p.set_defaults(func=lambda a: _set("nextweek_default", a.value))

    # 查看配置
    _sub("show", help="查看当前配置",
                   description="显示已保存的 Cookie(脱敏)/Git 目录/用户名/周报姓名/确认开关/文档 URL。",
                   epilog="格式示例：git_week_log show").set_defaults(func=cmd_show)

    # 核心工作流
    p = _sub(
        "do", help="写本周周报（auto 自动 / custom 自定义）",
        description="执行写周报完整工作流：校验配置/Cookie → 定位或新建日期工作表 → 写入本周内容与下周计划。",
        epilog="格式示例：\n"
               '  git_week_log do auto --yes\n'
               '  git_week_log do custom\n'
               '  git_week_log do custom "修复登录bug-80%; 优化首页; 增加埋点"\n'
               '  git_week_log do custom "功能A" --progress 80\n'
               '  git_week_log do custom "A; B" --nextWeek "下周计划1; 下周计划2"\n'
               "说明：custom 内容多条用分号(;或；)分隔并自动加序号；"
               "每条末尾可用 - 或 － 指定进度（不填默认 100%）。",
    )
    p.add_argument("mode", nargs="?", choices=["auto", "custom"],
                   help="模式：auto 自动总结（进度固定 100%%，不带 --nextWeek 不写下周计划），"
                        "custom 自定义录入；省略则交互选择")
    p.add_argument("content", nargs="?",
                   help="custom 模式的日志内容，多条用分号(;或；)分隔，自动加序号；"
                        "每条可用末尾“-80%%”指定进度；省略则进入逐条交互录入")
    p.add_argument("--progress", default=None,
                   help="custom 模式传 content 参数时的默认进度（默认 100%%，未带进度的条生效）")
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