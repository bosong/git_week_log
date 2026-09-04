#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""写周报工作流：数据校验 → Cookie 校验 → 归纳 → 定位/新建工作表 → 写入"""

from datetime import date
import re

from . import config
from . import git_logs
from .wecom_doc import WeComDoc

# 配置项 -> 中文提示
_KEY_PROMPTS = {
    "cookie": "企业微信 Cookie（浏览器登录 doc.weixin.qq.com 后复制）",
    "git_dir": "Git 工作库目录路径",
    "git_user": "Git 提交者用户名（git log --author）",
    "weekly_name": "周报中的姓名（如：宋X）",
    "doc_url": "周报总文档 URL",
}


def _prompt_missing():
    """检查缺失配置项，交互式引导用户补齐。"""
    missing = config.missing_keys()
    if not missing:
        return
    print("检测到以下配置缺失，请补充：")
    for key in missing:
        value = input(f"{_KEY_PROMPTS[key]}：").strip()
        if value:
            config.set(key, value)
        else:
            print(f"警告：{_KEY_PROMPTS[key]} 未填写，稍后可重新执行命令补充。")
    print()


def _input_new_cookie():
    """提示用户输入新的 Cookie。"""
    print("Cookie 已过期或无效，请提供新的 Cookie：")
    print("（在浏览器中登录 doc.weixin.qq.com 后，从开发者工具复制完整 Cookie）")
    cookie = input("新 Cookie：").strip()
    if cookie:
        config.set("cookie", cookie)
    return cookie


def _confirm_lines(lines):
    """展示归纳结果并询问是否写入。返回 True 表示继续。"""
    print("\n将写入以下周报内容：")
    for line in lines:
        print(f"  {line}")
    print()
    while True:
        ans = input("确认写入？(y/n)：").strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("请输入 y 或 n。")


def _normalize_progress(raw):
    """把进度统一为百分比字符串：100 -> 100%，None/空白默认 100%。"""
    if raw is None:
        return "100%"
    s = str(raw).strip()
    if not s:
        return "100%"
    if s.endswith("%"):
        return s
    return s + "%"


def _prompt_mode():
    """交互选择模式，返回 'auto' / 'custom'。"""
    print("请选择周报模式：")
    print("  1. auto   自动模式：自动总结 git 提交，进度固定 100%")
    print("  2. custom 自定义模式：手动录入日志内容与进度")
    while True:
        ans = input("请输入 1 或 2：").strip()
        if ans in ("1", "auto", "Auto"):
            return "auto"
        if ans in ("2", "custom", "Custom"):
            return "custom"
        print("无效输入，请输入 1(auto) 或 2(custom)。")


def _list_commits(commits):
    """列出 git 提交作为参考。"""
    if commits:
        print("\n本周 Git 提交参考：")
        for _, t, msg in commits:
            print(f"  - {t}  {msg}")
    else:
        print("\n本周暂无该用户的 Git 提交记录，可手动录入。")


def _run_custom_input(commits):
    """自定义模式：列出日志参考后，交互录入最多 4 条 (内容 + 进度)。

    返回 entries 列表（可能为空）。
    """
    _list_commits(commits)
    print("\n开始录入周报（最多 4 条，留空内容即结束）。")
    entries = []
    for i in range(4):
        print(f"\n--- 第 {i + 1} 条日志 ---")
        content = input(f"第 {i + 1} 条内容：").strip()
        if not content:
            print("未输入内容，结束录入。")
            break
        content = f"{i + 1}. {content}"
        progress = _normalize_progress(input("进度（输入数字会自动补 %，也可直接输入百分比）："))
        entries.append({"content": content, "progress": progress})

        if i == 3:
            break
        while True:
            choice = input("是否还有日志？[1] 还有日志  [2] 无更多，直接提交：").strip()
            if choice == "1":
                break
            if choice == "2":
                return entries
            print("请输入 1 或 2。")
    return entries


def _entries_from_text(content, progress=None):
    """把命令行传入的日志文本拆分为带序号的 entries。

    拆分规则：
    - 用中英文分号（; ；）切分多条日志；
    - 每条段尾可用 - 或 － 附带进度，如 "修复bug-80%"；
      未带进度时用 progress 参数，仍未给则默认 100%；
    - 自动加序号（1. / 2. / ...）。
    """
    default = _normalize_progress(progress)
    entries = []
    for i, seg in enumerate(
            [s.strip() for s in re.split(r"[;；]", content) if s.strip()],
            start=1):
        m = re.match(r"^(.*?)\s*[-－]\s*([0-9]+(?:\.[0-9]+)?%?)\s*$", seg)
        if m and m.group(1).strip():
            text = m.group(1).strip()
            item_progress = _normalize_progress(m.group(2))
        else:
            text = seg
            item_progress = default
        entries.append({"content": f"{i}. {text}", "progress": item_progress})
    return entries


def run_do(mode=None, content=None, progress=None, force_yes=False):
    """执行写周报工作流。

    mode: 'auto' 自动总结（进度固定 100%）/ 'custom' 自定义录入；None 则交互选择。
    """
    # 1. 数据完整性检查
    _prompt_missing()
    if config.missing_keys():
        print("仍有配置缺失，已终止。请补齐后重试。")
        return 1

    cookie = config.get("cookie")
    doc_url = config.get("doc_url")
    git_dir = config.get("git_dir")
    git_user = config.get("git_user")
    weekly_name = config.get("weekly_name")
    confirm = config.get("confirm")

    # 2. 模式选择
    if mode not in ("auto", "custom"):
        mode = _prompt_mode()

    # 3. Cookie 有效性检查
    print("正在校验 Cookie 并加载文档...")
    with WeComDoc(cookie, doc_url) as doc:
        if not doc.is_authorized():
            print("错误：Cookie 已过期或无效。")
            _input_new_cookie()
            print("请重新执行 do 命令。")
            return 1

        # 4. 计算本周周五日期
        friday = git_logs.get_week_friday()
        friday_str = friday.strftime("%Y-%m-%d")
        print(f"本周周五日期：{friday_str}")

        # 5. 获取 git 日志（auto 归纳，custom 仅作参考）
        print(f"正在从 {git_dir} 获取 {git_user} 本周提交...")
        commits, lines = git_logs.fetch_weekly_lines(git_dir, git_user, limit=4)

        if mode == "auto":
            if not commits:
                print("本周没有找到该用户的提交记录，无法生成周报。")
                return 1
            print(f"共 {len(commits)} 条提交，归纳为 {len(lines)} 条：")
            for line in lines:
                print(f"  {line}")
            entries = [{"content": line, "progress": "100%"} for line in lines]
            if confirm and not force_yes:
                if not _confirm_lines(lines):
                    print("已取消写入。")
                    return 1
        else:
            if content:
                entries = _entries_from_text(content, progress)
                print(f"已从参数解析出 {len(entries)} 条日志：")
                for e in entries:
                    print(f"  {e['content']}  (进度 {e['progress']})")
            else:
                entries = _run_custom_input(commits)
            if not entries:
                print("未录入任何日志，已取消。")
                return 1

        # 6. 定位或新建工作表
        sheets = doc.list_sheets()
        print(f"文档中已有 {len(sheets)} 个工作表。")
        if friday_str not in sheets:
            print(f"未找到 {friday_str} 工作表，将基于上一周模板新建。")
            created = doc.create_sheet_from_template(friday_str)
            if not created:
                print("错误：新建工作表失败。")
                return 1

        # 7. 写入
        print(f"正在将周报写入工作表 {friday_str} 的 {weekly_name} 区域...")
        ok = doc.write_weekly(friday_str, weekly_name, entries)
        if not ok:
            print("错误：写入失败。")
            return 1

        print("写入成功！")
        print("回读校验：")
        for i, entry in enumerate(entries):
            print(f"  {i + 1}. {entry['content']}  (进度 {entry['progress']})")

    return 0
