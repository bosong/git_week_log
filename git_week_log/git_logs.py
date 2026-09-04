#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Git 日志获取与自动归纳为 4 条周报内容

从 get_git_commit_log.py 提取纯函数并复用，同时修正原脚本缺陷：
- get_commits 增加 cwd=repo_path 参数，确保在指定仓库目录执行 git log。
"""

import os
import subprocess
import sys
import re
from datetime import datetime, timedelta, date
from collections import OrderedDict


def is_git_repo(path="."):
    """检查指定路径是否为 Git 仓库（目录不存在/不是目录返回 False）。"""
    if not os.path.isdir(path):
        return False
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        raise RuntimeError("未找到 Git 命令，请确认 Git 已安装并在 PATH 中。")


def get_commits(author, since, repo_path):
    """使用 git log 获取提交记录（在 repo_path 目录内执行）"""
    cmd = [
        "git",
        "log",
        f"--author={author}",
        f"--since={since}",
        "--pretty=format:%h|%ad|%s",
        "--date=format:%Y-%m-%d %H:%M:%S",
    ]
    result = subprocess.run(
        cmd,
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def parse_commits(commits_raw):
    """将原始输出按行解析为 (hash, time, message) 列表"""
    if not commits_raw:
        return []
    parsed = []
    for line in commits_raw.split("\n"):
        parts = line.split("|", 2)
        if len(parts) == 3:
            parsed.append((parts[0], parts[1], parts[2]))
        else:
            parsed.append(("", "", line))
    return parsed


def get_week_monday():
    """返回本周一（date）"""
    today = date.today()
    return today - timedelta(days=today.weekday())


def get_week_friday():
    """返回本周周五（date）"""
    return get_week_monday() + timedelta(days=4)


def get_week_since_str():
    """返回本周一 00:00:00 的字符串，用于 git log --since"""
    monday = get_week_monday()
    since_dt = datetime(monday.year, monday.month, monday.day, 0, 0, 0)
    return since_dt.strftime("%Y-%m-%d %H:%M:%S")


# 提交信息类型标签，如 "dev:Feat: ..." / "dev:DFix: ..." / "dev:opt: ..."
_TAG_RE = re.compile(
    r"^\s*(?:[A-Za-z]+\s*[:：]\s*)?(Feat|DFix|Fix|opt|Bugfix|Hotfix|Chore|Refactor|Test|Docs|Feature|Featrue)\s*[:：]\s*",
    re.IGNORECASE,
)
_TAG_MAP = {
    "feat": "feat", "featrue": "feat", "feature": "feat",
    "opt": "opt",
    "fix": "fix", "dfix": "fix", "bugfix": "fix", "hotfix": "fix",
}

# 中文提交信息开头的"动作词"，用于剥离出主题关键词
_ACTION_PREFIX = (
    "修复", "新增", "增加", "优化", "补充", "调整", "完善", "支持", "实现",
    "添加", "移除", "解决", "处理", "修改", "更新", "完成", "删除", "重构",
)

# 主题关键词末尾的常见"功能/动作"后缀，用于把"生财有道界面优化"收敛为"生财有道"
_FEATURE_SUFFIX = (
    "界面", "权限", "功能", "模块", "逻辑", "列表", "详情", "页面", "入口",
    "优化", "修复", "打点", "补充", "三分钟", "新增", "调整", "完善", "支持",
    "实现", "添加", "bug", "Bug",
)


def _normalize(message: str) -> str:
    """去除全角/半角括号，便于把"生财有(道)"归一为"生财有道"。"""
    return re.sub(r"[()（）]", "", message).strip()


def _parse(message: str):
    """解析一条提交信息，返回 (tag, cleaned)。

    tag 取值：feat / opt / fix / other。
    cleaned 为去除类型标签与括号后的信息正文。
    """
    m = _TAG_RE.match(message)
    tag = "other"
    if m:
        tag = _TAG_MAP.get(m.group(1).lower(), "other")
    cleaned = _TAG_RE.sub("", message).strip()
    cleaned = _normalize(cleaned).strip(" :-：")
    return tag, cleaned


def _topic_of(message: str) -> str:
    """从一条提交信息中提取主题关键词（如"生财有道"、"明日提示"）。"""
    _, cleaned = _parse(message)
    if not cleaned:
        return "其他"

    msg = cleaned
    for w in _ACTION_PREFIX:
        if msg.startswith(w):
            msg = msg[len(w):]
            break
    msg = msg.strip(" :-：、")

    # 中文开头：取连续中文串，并剥离末尾功能后缀
    if re.match(r"^[\u4e00-\u9fff]", msg):
        feature = re.match(r"^[\u4e00-\u9fff]+", msg).group()
        changed = True
        while changed and len(feature) > 2:
            changed = False
            for suf in _FEATURE_SUFFIX:
                if feature.endswith(suf) and len(feature) - len(suf) >= 2:
                    feature = feature[:-len(suf)]
                    changed = True
                    break
        return feature or "其他"

    # 英文/数字开头：取第一个 token
    m = re.match(r"^([A-Za-z0-9_.\-]+)", msg)
    return m.group(1) if m else (msg[:8] or "其他")


def _detail_of(topic: str, cleaned: str) -> str:
    """从清洗后的信息中剥离主题，得到"动作/细节"部分。"""
    d = cleaned
    for w in _ACTION_PREFIX:
        if d.startswith(w):
            d = d[len(w):]
            break
    if d.startswith(topic):
        d = d[len(topic):]
    return d.strip(" :-：、")


def _dedup(tokens):
    """保持顺序去重，过滤空字符串。"""
    seen = set()
    out = []
    for t in tokens:
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def group_commits(commits):
    """将提交列表按主题分组。

    返回 OrderedDict{主题: [(tag, cleaned), ...]}，保持主题首次出现顺序。
    """
    grouped = OrderedDict()
    for commit in commits:
        message = commit[2]
        tag, cleaned = _parse(message)
        topic = _topic_of(message)
        grouped.setdefault(topic, []).append((tag, cleaned))
    return grouped


def summarize_group(topic, items):
    """将同一主题的一组提交归纳为一条周报描述。

    items 为 [(tag, cleaned), ...] 列表。
    """
    # 单条提交：直接使用清洗后的完整信息
    if len(items) == 1:
        return items[0][1]

    feat_tokens = []
    opt_tokens = []
    fix_tokens = []
    other_tokens = []
    has_feat_empty = False

    for tag, cleaned in items:
        detail = _detail_of(topic, cleaned)
        tokens = [t for t in re.split(r"[、,，]", detail) if t.strip()]
        if tag == "feat":
            if tokens:
                feat_tokens.extend(tokens)
            else:
                has_feat_empty = True
        elif tag == "opt":
            opt_tokens.extend(tokens if tokens else ["优化"])
        elif tag == "fix":
            fix_tokens.extend(tokens if tokens else ["修复"])
        else:
            other_tokens.extend(tokens if tokens else [detail])

    parts = []
    if feat_tokens or has_feat_empty:
        feat_final = []
        if has_feat_empty:
            feat_final.append("功能")
        feat_final.extend(feat_tokens)
        parts.append("新增" + "、".join(_dedup(feat_final)))

    all_rest = _dedup(opt_tokens + fix_tokens + other_tokens)
    parts.extend(all_rest)

    # 清理：若已含"修复bug"，去掉孤立的"bug"
    if any("修复bug" in p for p in parts):
        parts = [p for p in parts if p.strip().lower() != "bug"]

    return f"{topic}：" + "、".join(parts)


def build_weekly_lines(commits, limit=4):
    """将提交归纳为最多 limit 条周报内容，返回带序号的字符串列表。

    返回格式：['1.xxx', '2.xxx', ...]
    """
    if not commits:
        return []

    grouped = group_commits(commits)

    # 按提交数量降序、主题首次出现顺序稳定排序
    items = sorted(
        grouped.items(),
        key=lambda kv: (-len(kv[1]), list(grouped.keys()).index(kv[0])),
    )

    lines = []
    for topic, group in items[:limit]:
        lines.append(summarize_group(topic, group))

    # 带序号
    return [f"{i}. {line}" for i, line in enumerate(lines, start=1)]


def split_paths(raw):
    """拆分配置中的路径字符串，支持中英文分号（; ；）分隔多个目录。

    list/tuple 原样清洗返回；str 按分号拆分并去掉首尾空白。
    """
    if isinstance(raw, (list, tuple)):
        return [p.strip() for p in raw if p.strip()]
    if not raw:
        return []
    return [p.strip() for p in re.split(r"[;；]", str(raw)) if p.strip()]


def fetch_weekly_lines(paths, author, limit=4):
    """完整流程：从（可多个）Git 仓库获取本周提交并归纳为 limit 条带序号周报。

    返回 (commits, lines)。commits 为合并后的原始提交列表（按时间倒序，可能为空）。
    无效目录会被跳过（本函数不打印，调用方可先用 split_paths/is_git_repo 预检）。
    """
    dirs = split_paths(paths)
    if not dirs:
        raise ValueError("未配置有效的 Git 工作库目录")

    since = get_week_since_str()
    all_commits = []
    for d in dirs:
        if not is_git_repo(d):
            continue
        raw = get_commits(author, since, d)
        all_commits.extend(parse_commits(raw))
    # 跨仓库按提交时间倒序（新 → 旧）
    all_commits.sort(key=lambda c: c[1], reverse=True)
    lines = build_weekly_lines(all_commits, limit=limit)
    return all_commits, lines
