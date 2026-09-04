# git_week_log

从 Git 提交记录自动归纳并写入「企业微信文档（腾讯文档）」周报的 CLI 工具。

## 功能特性

- **自动模式 `do auto`**：拉取本周（周一 00:00 至今）指定 git 用户的提交 → 自动按主题归纳为最多 4 条周报 → 写入本周周五日期对应工作表、对应人员区域。预期/实际进度固定填 `100%`。
- **自定义模式 `do custom`**：先列出本周 git 提交供参考，再逐条交互录入内容与进度（可少于 4 条），填写完后可随时选择直接提交。
- **配置命令**：Cookie、Git 仓库目录、git 用户名、周报姓名、文档 URL、确认开关均可单独设置并持久化保存。
- **自动建表**：若文档中没有本周五日期的工作表，会自动基于上一个工作表模板新建。
- **真实 UI 写入**：不是调用不稳定的内部 setValue API，而是模拟"双击单元格 → 输入 → 提交"的真实编辑操作，数据可持久化。

## 环境要求

- Python **>= 3.7**（实测 3.7 语法可完整运行；项目使用 `f-string`（3.6+）与 `subprocess.run(capture_output=...)`（3.7+），低于 3.7 无法运行）
- Playwright 是本工具写入文档的核心依赖，不同 Python 版本自动安装对应版本：
  - Python 3.7：Playwright 1.34~1.35（1.36 起不再支持 3.7）
  - Python 3.8：Playwright 1.40~1.48（1.49 起要求 ≥3.9）
  - Python ≥3.9：最新版 Playwright（推荐）

## 安装

```bash
pip3 install git+https://github.com/bosong/git_week_log.git

# 安装 Playwright 浏览器内核（写入腾讯文档需要）
playwright install chromium
```

## 快速开始

```bash
# 1. 设置基础配置（任意顺序，均可通过 set-* 命令单独修改）
git_week_log set-cookie "<浏览器复制出的完整 Cookie>"
git_week_log set-git-dir "后端:/repo1;前端:/repo2"   # 支持多个目录(分号;或；分隔)，可用 别名:路径 加前缀
git_week_log set-git-dir "/repo3"                    # 不加别名则保持原样输出
git_week_log set-git-user "AAXX"
git_week_log set-weekly-name "XXXX"
git_week_log set-doc-url "https://doc.weixin.qq.com/sheet/<docid>?scode=<scode>&tab=<tab>"

# 2. 查看当前配置（Cookie 脱敏显示）
git_week_log show

# 3. 写入周报：自动模式（省略 mode 会交互询问）
git_week_log do auto
git_week_log do auto --yes

# 4. 写入周报：自定义模式
git_week_log do custom

#   也可直接命令行传内容，多条用分号(;或；)分隔，自动加序号：
git_week_log do custom "修复登录 bug; 优化首页性能"
#   单条进度用 - 或 － 接在内容后，未写进度默认 100%：
git_week_log do custom "功能A-100%；功能B-80%; 功能C"
#   --progress 统一兜底未写进度的条：默认 100%
git_week_log do custom "A; B" --progress 80

#   下周重点计划（写入"下周重点计划"列，多条用分号分隔，自动加序号）：
#   自动模式：不加 --nextWeek 则不写入该列
git_week_log do auto --nextWeek "功能1接入; 功能2迭代"
#   自定义模式：必填；缺省 --nextWeek 会在录入日志后交互询问
git_week_log do custom "A-100%; B" --nextWeek "下周计划一; 下周计划二"
```

### Cookie 获取方法

1. 用 Chrome/Edge 登录 `doc.weixin.qq.com` 并打开周报文档；
2. 按 `F12` 打开开发者工具 → `Network`（网络）；
3. 刷新页面，任选一个请求 → `Request Headers` → 复制 `Cookie:` 后的整段内容。

> Cookie 仅保存在本机 `~/.git_week_log/config.json`（目录权限 700），不会上传。Cookie 过期时重新复制一份并执行 `git_week_log set-cookie "<新的>"` 即可。

## 自定义模式交互流程

```
1. 列出本周 Git 提交作为参考
2. 依次输入第 1/2/3/4 条日志：内容 → 进度
   进度直接输数字会自动补 %，如 100 → 100%，80 → 80%，也可直接输 80%
3. 每条录完后询问：
   [1] 还有日志   [2] 无更多，直接提交
   选 2 立即写入文档；选 1 继续下一条；最多 4 条
```

## 命令一览

| 命令 | 作用 |
| --- | --- |
| `git_week_log set-cookie <value>` | 保存企业微信 Cookie |
| `git_week_log set-git-dir <别名:path1;path2>` | 保存 Git 工作库目录（多个分号 ; 或 ；分隔，合并取日志；每条可用 `别名:路径`，归纳日志会带 `别名：` 前缀，如 `1.后端：xxx`） |
| `git_week_log set-git-user <name>` | 保存 Git 提交者用户名 |
| `git_week_log set-weekly-name <name>` | 保存周报中的姓名 |
| `git_week_log set-confirm <on\|off>` | 设置是否确认日志内容（auto 模式） |
| `git_week_log set-doc-url <url>` | 保存周报总文档 URL |
| `git_week_log show` | 查看当前配置 |
| `git_week_log --version` | 显示版本号 |
| `git_week_log do [auto\|custom] [--yes]` | 执行写周报工作流 |

## 工作原理

1. `git log --author=<git_user> --since=<本周一>` 拉取本周提交；
2. 按提交信息中的主题关键词自动分组、合并归纳（最多 4 条）；
3. 用 Playwright 打开文档页面并注入 Cookie，判断登录态；
4. 定位/新建「本周周五日期」工作表，扫描姓名列找到周报人所在行；
5. 在「重点工作内容 / 预期进度 / 实际进度」列按行写入内容与进度，并做读回校验。

周报写入区域基于表头约定：

| 列 | 表头 |
| --- | --- |
| C | 重点工作内容 |
| D | 预期进度 |
| E | 实际进度 |

如果你的模板列位不同，需在 `git_week_log/wecom_doc.py` 的 `write_weekly()` 中调整 `content_col/expect_col/actual_col` 参数。

## 开源协议

本项目仅供学习交流使用。请勿用于未经授权的数据抓取或任何违反企业微信/腾讯文档服务条款的场景。
