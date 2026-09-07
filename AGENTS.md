# AGENTS.md

面向 AI 编码助手与本项目开发者的工作指南。修改代码前请先通读本文件，
确保改动符合项目的结构约定、兼容性约束与既有行为。

## 1. 项目简介

`git_week_log` 是一个 CLI 工具：拉取用户本周（周一 00:00 起）的 Git 提交 →
自动/手动归纳为周报条目 → 用 Playwright 驱动真实浏览器 UI，把内容写入
企业微信文档（腾讯文档）在线表格的周报工作表中。

- 入口 console script：`git_week_log`（定义于 [setup.py](file:///Users/songbo/Documents/trae_projects/git_week_log/setup.py)，指向 `git_week_log.cli:main`）
- 向后兼容入口：[main.py](file:///Users/songbo/Documents/trae_projects/git_week_log/main.py) 等价于 `python3 main.py ...`
- 版本号唯一来源：`git_week_log/__init__.py` 的 `__version__`（当前 `0.1.18`）

## 2. 环境与依赖

- Python **>= 3.7**：代码刻意保持 3.7 兼容（`f-string`、`subprocess.run(capture_output=...)`）。
  **新增代码禁止使用 3.8+ 语法**（如海象运算符 `:=`、仅位置参数 `/`）、
  3.9+ 语法（如 `dict | dict`、`str.removeprefix`、内置泛型 `list[str]` 注解等）。
- 唯一运行时依赖：**Playwright**（写入文档的核心），按 Python 版本选版本，
  见 [setup.py](file:///Users/songbo/Documents/trae_projects/git_week_log/setup.py) 的分发标记，与 [requirements.txt](file:///Users/songbo/Documents/trae_projects/git_week_log/requirements.txt) 一致。
  需安装浏览器内核：`playwright install chromium`。
- 项目**没有任何自动化测试**，也没有 lint/format 配置，靠手工验证。

## 3. 项目结构

```
git_week_log/
├── main.py                  # 兼容入口，转发到 cli.main
├── get_git_commit_log.py    # 早期独立脚本（交互式 git 报告），git_logs 从中提取并改进
├── setup.py / pyproject.toml / requirements.txt
└── git_week_log/
    ├── __init__.py          # __version__ 唯一来源
    ├── cli.py               # argparse 命令定义与分发
    ├── config.py            # ~/.git_week_log/config.json 读写（权限 700/600）
    ├── git_logs.py          # git 提交获取 + 纯函数归纳为周报行
    ├── workflow.py          # 顶层工作流 run_do：校验→模式→定位表→写入
    └── wecom_doc.py         # WeComDoc 类：Playwright 操作腾讯文档 sheet
```

## 4. 常用命令

```bash
# 本地可编辑安装（修改源码后建议用该方式，console script 即时生效）
pip3 install -e .

# 显示版本 / 查看已保存配置（Cookie 脱敏）
git_week_log --version
git_week_log show

# 配置命令
git_week_log set-cookie "<完整 Cookie>"
git_week_log set-git-dir "别名1:/path/a;别名2:/path/b"   # 中英文分号分隔；无别名直接写路径
git_week_log set-git-user "<git 用户名>"
git_week_log set-weekly-name "<表中姓名>"
git_week_log set-doc-url "<sheet URL>"
git_week_log set-confirm on|off          # 是否在 auto 写前确认
git_week_log set-nextweek-default "计划1; 计划2"

# 写周报
git_week_log do auto [--yes] [--nextWeek "..."] [--doc_date YYYY-MM-DD]
git_week_log do custom ["内容A-80%; 内容B"] [--progress N] [--nextWeek "..."] [--doc_date ...]
```

> 注意：若通过 `pip3 install git+...` 全局安装过，改动本地源码后 console script
> 仍是旧版本，必须重装（`pip3 install -e .` 或重新 install）后改动才生效。

## 5. 数据流与业务规则（改动前必读）

### 5.1 主流程（workflow.run_do，见 [workflow.py](file:///Users/songbo/Documents/trae_projects/git_week_log/git_week_log/workflow.py#L185-L324)）

1. 校验缺失配置（`config.missing_keys()`：cookie/git_dir/git_user/weekly_name/doc_url），
   缺失则交互补全。
2. 未显式 `--nextWeek` 时回退用配置项 `nextweek_default`。
3. `mode` 缺省时交互选择 auto/custom。
4. 打开 `WeComDoc`，校验 Cookie（页面存在 `window.SpreadsheetApp` 即有效）。
5. 计算目标日期：默认本周周五；`--doc_date` 可覆盖（格式 `YYYY-MM-DD`）。
6. 解析多仓库 → `git_logs.fetch_weekly_lines()` 取提交。
7. auto：无提交则终止；归纳为最多 4 条、进度固定 `100%`；
   **只有显式传 `--nextWeek` 才写下周计划列**；`confirm` 开启且未 `--yes` 时需确认。
8. custom：从参数 `content` 解析，或交互录入；**下周计划必填**（参数缺省则交互询问）。
9. 目标表不存在则基于模板新建；定位姓名行 → 逐格写入 → 返回码校验。

### 5.2 提交归纳规则（git_logs.py）

- 多仓库提交合并后按时间倒序；每条带可选仓库别名，归纳行加 `"别名："` 前缀。
- 类型标签解析 `_TAG_RE`/`_TAG_MAP`：`feat/opt/fix/other`。
- `_topic_of()` 提取主题（剥离动作词前缀与中文功能后缀），
  `summarize_group()` 把同主题多条合并为一条描述。
- `build_weekly_lines()` 输出 `["1.xxx", ...]`（最多 `limit=4` 条）。
- 仓库配置解析 `split_paths`/`parse_repo_entries`：中英文分号（`;；`）分隔，
  `别名:路径` 形式（冒号支持中英文）。

### 5.3 条目格式约定（workflow.py）

- **自动加序号**：每条日志 `f"{i}. {content}"`，下周计划同理。
- **进度归一化 `_normalize_progress`**：`100 → 100%`；已带 `%` 原样；空/None 默认 `100%`。
- 命令行 `content` 拆分 `_entries_from_text`：按 `;；` 分段，段尾 `-`/`－` 后跟数字可
  带进度（如 `功能A-80%`）；未带进度用 `--progress`，再缺省 `100%`。
- 交互录入 `_run_custom_input`：最多 4 条，内容留空结束，每条后问
  “还有日志？” 选 2 直接提交。

### 5.4 列映射（wecom_doc.write_weekly）

写入区域按表头约定。列参数默认值（**0 基索引**，与 README 的表头对应）：
`content_col=2`（重点工作内容）、`expect_col=3`（预期进度）、
`actual_col=4`（实际进度）、`plan_col=6`（下周重点计划）。
进度同时写入预期/实际两列。模板列位不同时在此函数调整，**不要**在别处硬编码。

## 6. 腾讯文档写入的技术约束（重要，改动 wecom_doc.py 前必读）

- 通过 `document.cookie` 注入登录态，headless Chromium（异常时回退 `channel="chrome"`）。
- 腾讯文档表格**懒加载**：读写非激活表前必须先 `activeSheetId` 切换 +
  `await dcs.loadSheetData({sheetId})` + 轮询 `getIsLoaded`（见 `_ensure_loaded`）。
- **禁止**调用内部 `setValue`/`setSingleValue` 之类 API 写入——不触发协同提交、
  数据不持久化。写入必须走 UI 流程 `_ui_set_cell`：滚入视口 → 双击进编辑态 →
  全选清空（headless 下 `Meta+A` 不可靠，优先 `_select_all_active_editor` 的
  focus+select 方案）→ 逐字输入 → 点击相邻单元格 blur 提交。
- 新建工作表走 UI 右键菜单“创建副本”+ 重命名，带多轮重试与超时轮询
  （`create_sheet_from_template`）。这些都依赖**固定 sleep 等待**，改动时要
  保留足够的等待时间，避免用即时断言替代。
- 方法内嵌大段 JS 字符串用 `page.evaluate`，坐标类用 `page.mouse`。

## 7. 常见改动点的“关联位置”

| 想改什么 | 需要动哪里 |
| --- | --- |
| 新增配置项 | `config.DEFAULTS` 加默认值；需要必填则加进 `missing_keys()` 的 required；`cli.py` 加 `set-xxx` 子命令；要交互补全就同步 `workflow._KEY_PROMPTS`；`cli.cmd_show` 展示 |
| 新增 CLI 参数 | `cli.main` 的 `do` 子命令解析后传 `workflow.run_do`；注意 argparse `%%` 转义 |
| 归纳/序号/进度逻辑 | `git_logs.py`（归纳）、`workflow.py`（序号、进度、拆分） |
| 列位/写入行为 | `wecom_doc.write_weekly` 默认参数 |
| UI 定位与等待 | `wecom_doc.py` 对应方法 |

## 8. 验证方式（无自动化测试）

1. 语法/导入：`python3 -m py_compile git_week_log/*.py`；
2. 离线功能：`git_week_log show`、`do` 前期的配置校验与 git 归纳路径可执行观察；
3. 端到端写入会真实改动线上周报文档且依赖有效 Cookie，**务必先与用户确认**，
   建议用临时/测试文档验证。
