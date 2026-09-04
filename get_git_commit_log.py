#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git 提交日志报告生成器（支持多模板）
功能：
1. 自动检测当前目录是否为 Git 仓库，若不是则引导用户输入有效路径
2. 交互式输入作者名和时间范围（本周 / 自定义时间点）
3. 获取指定作者从某时间点开始的提交记录
4. 提供两种报告模板：详细模板（哈希+时间+信息）和简洁模板（仅提交信息带序号）
5. 美化输出报告到终端
"""

import os
import subprocess
import sys
from datetime import datetime, timedelta, date


def is_git_repo(path="."):
    """检查指定路径是否为 Git 仓库"""
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
        print("错误：未找到 Git 命令，请确认 Git 已安装并在 PATH 中。")
        sys.exit(1)


def get_author():
    """获取作者名称（禁止空输入）"""
    while True:
        author = input("请输入要查询的作者名称：").strip()
        if author:
            return author
        print("错误：作者名称不能为空，请重新输入。")


def get_since_time():
    """获取起始时间点，返回 (since_str, description)"""
    print("\n请选择起始时间：")
    print("1. 本周（从本周一 00:00:00 开始）")
    print("2. 自定义时间点")
    
    while True:
        choice = input("请输入选项 (1 或 2)：").strip()
        if choice == "1":
            today = date.today()
            monday = today - timedelta(days=today.weekday())
            since_dt = datetime(monday.year, monday.month, monday.day, 0, 0, 0)
            return since_dt.strftime("%Y-%m-%d %H:%M:%S"), f"本周 ({monday.strftime('%Y-%m-%d')} 00:00:00 起)"
        elif choice == "2":
            break
        else:
            print("无效选项，请输入 1 或 2。")

    # 自定义时间输入循环
    while True:
        print("\n支持的时间格式：")
        print("  例1: 2026-07-15 10:30:00  (精确到秒)")
        print("  例2: 2026-07-15            (自动补 00:00:00)")
        user_input = input("请输入起始时间点：").strip()
        
        if not user_input:
            print("错误：时间点不能为空。")
            continue
        
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(user_input, fmt)
                if fmt == "%Y-%m-%d":
                    dt = dt.replace(hour=0, minute=0, second=0)
                return dt.strftime("%Y-%m-%d %H:%M:%S"), user_input
            except ValueError:
                continue
        
        print("格式错误！请使用 YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD，例如 2026-07-15 10:30:00")


def get_commits(author, since):
    """使用 git log 获取提交记录"""
    cmd = [
        "git",
        "log",
        f"--author={author}",
        f"--since={since}",
        "--pretty=format:%h|%ad|%s",
        "--date=format:%Y-%m-%d %H:%M:%S",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"执行 git log 出错：{e.stderr}")
        sys.exit(1)


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
            # 异常情况：整行作为信息，哈希和时间留空
            parsed.append(("", "", line))
    return parsed


def print_report_detailed(author, since_desc, commits):
    """模板1：详细报告（哈希、时间、信息）"""
    print("\n" + "=" * 70)
    print(" GIT 提交报告 (详细模板) ".center(70, "="))
    print(f" 作者：{author}".ljust(69))
    print(f" 起始时间：{since_desc}".ljust(69))
    print("=" * 70)

    if not commits:
        print("\n🎉 在指定时间范围内没有该作者的提交记录。")
        return

    print(f"\n共找到 {len(commits)} 条提交记录：\n")
    print("-" * 70)
    print(f"{'提交哈希':<10} {'提交时间':<22} {'提交信息'}")
    print("-" * 70)

    for commit_hash, commit_time, message in commits:
        print(f"{commit_hash:<10} {commit_time:<22} {message}")

    print("-" * 70)
    print(f"\n报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


def print_report_simple(author, since_desc, commits):
    """模板2：简洁报告（仅提交信息，带序号）"""
    print("\n" + "=" * 70)
    print(" GIT 提交报告 (简洁模板) ".center(70, "="))
    print(f" 作者：{author}".ljust(69))
    print(f" 起始时间：{since_desc}".ljust(69))
    print("=" * 70)

    if not commits:
        print("\n🎉 在指定时间范围内没有该作者的提交记录。")
        return

    print(f"\n共找到 {len(commits)} 条提交记录：\n")
    for idx, (_, _, message) in enumerate(commits, start=1):
        print(f"{idx}. {message}")

    print("\n" + "-" * 70)
    print(f"报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


def choose_template():
    """选择输出模板"""
    print("\n请选择报告输出格式：")
    print("1. 详细模板（包含提交哈希、时间和信息）")
    print("2. 简洁模板（仅显示提交信息，每条带序号）")
    while True:
        choice = input("请输入选项 (1 或 2)：").strip()
        if choice in ("1", "2"):
            return choice
        print("无效选项，请输入 1 或 2。")


def main():
    # 1. 检查 Git 仓库，若当前目录不是则要求用户输入
    if not is_git_repo():
        print("当前目录不是 Git 仓库。")
        while True:
            repo_path = input("请输入 Git 仓库目录路径（输入 'q' 退出）：").strip()
            if repo_path.lower() == 'q':
                print("已退出。")
                sys.exit(0)
            if not os.path.isdir(repo_path):
                print("目录不存在，请重新输入。")
                continue
            if not is_git_repo(repo_path):
                print("该目录不是有效的 Git 仓库，请重新输入。")
                continue
            os.chdir(repo_path)
            print(f"已切换到 Git 仓库：{os.path.abspath(repo_path)}\n")
            break
    else:
        print("当前目录是有效的 Git 仓库。\n")

    # 2. 获取作者
    author = get_author()

    # 3. 获取时间点
    since, since_desc = get_since_time()

    # 4. 获取提交记录
    commits_raw = get_commits(author, since)
    commits = parse_commits(commits_raw)

    # 5. 选择输出模板并打印报告
    template_choice = choose_template()
    if template_choice == "1":
        print_report_detailed(author, since_desc, commits)
    else:
        print_report_simple(author, since_desc, commits)


if __name__ == "__main__":
    main()