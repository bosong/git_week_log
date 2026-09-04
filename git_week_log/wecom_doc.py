#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""企业微信文档（腾讯文档 sheet）读写封装，基于 Playwright。

通过注入 Cookie 后调用页面内的 window.SpreadsheetApp JS API 完成：
- 读取工作表列表与单元格内容
- 定位指定姓名的区域
- 写入单元格内容

文档 URL 形如：
    https://doc.weixin.qq.com/sheet/<docid>?scode=<scode>&tab=<tab>
"""

import re
import json
from urllib.parse import urlparse, parse_qs


def parse_doc_url(url):
    """解析文档 URL，返回 dict：docid / scode / tab / origin"""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    docid = parsed.path.rstrip("/").split("/")[-1]
    return {
        "origin": f"{parsed.scheme}://{parsed.netloc}",
        "docid": docid,
        "scode": qs.get("scode", [""])[0],
        "tab": qs.get("tab", [""])[0],
    }


def parse_cookie_string(cookie_str, domain="doc.weixin.qq.com"):
    """将浏览器复制的 cookie 字符串解析为 Playwright add_cookies 所需的列表。

    cookie 字符串形如：`name1=value1; name2=value2; ...`
    """
    cookies = []
    for part in cookie_str.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        cookies.append({
            "name": name.strip(),
            "value": value.strip(),
            "domain": domain,
            "path": "/",
        })
    return cookies


class WeComDoc:
    """企业微信文档读写客户端（Playwright）。"""

    def __init__(self, cookie_str, doc_url):
        self.cookie_str = cookie_str
        self.doc_url = doc_url
        self.doc = parse_doc_url(doc_url)
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    def _inject_cookie_js(self):
        """生成通过 document.cookie 注入 Cookie 的 JS 语句（跨域注入更可靠）。"""
        parts = []
        for part in self.cookie_str.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            name, value = part.split("=", 1)
            parts.append("document.cookie = " + json.dumps(f"{name}={value}") + " + '; path=/;';")
        return "\n".join(parts)

    def _launch(self):
        """启动浏览器并注入 Cookie，加载文档页面。"""
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(headless=True)
        except Exception:
            self._browser = self._playwright.chromium.launch(headless=True, channel="chrome")
        self._context = self._browser.new_context(viewport={"width": 1500, "height": 1000})
        self._page = self._context.new_page()
        # 先访问同域主页，再借助 document.cookie 注入（比 add_cookies 对域更可靠）
        self._page.goto(f"{self.doc['origin']}/", wait_until="domcontentloaded", timeout=60000)
        self._page.evaluate(self._inject_cookie_js())
        self._page.goto(self.doc_url, wait_until="domcontentloaded", timeout=60000)
        self._page.wait_for_timeout(6000)

    def close(self):
        """关闭浏览器资源。"""
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        finally:
            self._context = None
            self._browser = None
            self._playwright = None
            self._page = None

    def __enter__(self):
        self._launch()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    # ---------------- 读取 ----------------

    def is_authorized(self):
        """判断当前 Cookie 是否有效（文档是否成功加载）。"""
        try:
            # 已登录时页面包含 SpreadsheetApp；未登录会跳转登录页
            ready = self._page.evaluate(
                "() => typeof window.SpreadsheetApp !== 'undefined'"
            )
            return bool(ready)
        except Exception:
            return False

    def _sheet_id(self, name):
        """返回指定名称的工作表 id，不存在返回 None。"""
        script = r"""
        (name) => {
            const wm = window.SpreadsheetApp && window.SpreadsheetApp.workbook
                && window.SpreadsheetApp.workbook.worksheetManager;
            if (!wm) return null;
            try {
                const names = wm.getSheetNameList();
                const i = names.indexOf(name);
                if (i < 0) return null;
                return wm.getSheetIdList()[i];
            } catch (e) {
                return null;
            }
        }
        """
        return self._page.evaluate(script, name)

    def _ensure_loaded(self, name):
        """切换到指定工作表并加载其数据，返回 {id, rowCount, colCount, loaded}。

        腾讯文档表格为懒加载：只有当前激活 sheet 才会从服务端拉取数据，
        其他 sheet 在加载前 getCellDataAtPosition 返回空、usedRange 为 -1。
        因此读取/写入任何非激活 sheet 前，必须先 activeSheetId 切换，
        再 await loadSheetData({sheetId}) 并等待 getIsLoaded 为 true。
        表不存在返回 None。
        """
        script = r"""
        async (name) => {
            const app = window.SpreadsheetApp;
            const wm = app && app.workbook && app.workbook.worksheetManager;
            const dcs = app && app.dataCenterService;
            if (!wm || !dcs) return null;
            const names = wm.getSheetNameList();
            const idx = names.indexOf(name);
            if (idx < 0) return null;
            const id = wm.getSheetIdList()[idx];
            try { wm.activeSheetId = id; } catch (e) {}
            try { await dcs.loadSheetData({ sheetId: id }); } catch (e) {}
            for (let i = 0; i < 40; i++) {
                if (dcs.getIsLoaded(id)) break;
                await new Promise(res => setTimeout(res, 500));
            }
            const s = wm.getSheetBySheetId(id);
            return {
                id: id,
                rowCount: s.getRowCount ? s.getRowCount() : null,
                colCount: s.getColCount ? s.getColCount() : null,
                loaded: dcs.getIsLoaded(id),
            };
        }
        """
        return self._page.evaluate(script, name)

    def list_sheets(self):
        """返回工作表名称列表（按顺序）。"""
        script = r"""
        () => {
            const wm = window.SpreadsheetApp && window.SpreadsheetApp.workbook
                && window.SpreadsheetApp.workbook.worksheetManager;
            if (!wm) return [];
            try { return wm.getSheetNameList(); } catch (e) { return []; }
        }
        """
        try:
            return self._page.evaluate(script)
        except Exception:
            return []

    def get_sheet_meta(self, name):
        """返回工作表基本元信息 {name, id, rowCount, colCount}，不存在返回 None。"""
        script = r"""
        (name) => {
            const wm = window.SpreadsheetApp && window.SpreadsheetApp.workbook
                && window.SpreadsheetApp.workbook.worksheetManager;
            if (!wm) return null;
            try {
                const idx = wm.getSheetNameList().indexOf(name);
                if (idx < 0) return null;
                const id = wm.getSheetIdList()[idx];
                const s = wm.getSheetBySheetId(id);
                return {
                    name: name,
                    id: id,
                    rowCount: s.getRowCount ? s.getRowCount() : null,
                    colCount: s.getColCount ? s.getColCount() : null,
                };
            } catch (e) {
                return null;
            }
        }
        """
        return self._page.evaluate(script, name)

    def get_cell(self, sheet_name, row, col):
        """读取指定工作表 (row, col) 的单元格文本。索引从 0 开始（会自动加载表）。"""
        script = r"""
        async (args) => {
            const app = window.SpreadsheetApp;
            const wm = app && app.workbook && app.workbook.worksheetManager;
            const dcs = app && app.dataCenterService;
            if (!wm || !dcs) return null;
            const idx = wm.getSheetNameList().indexOf(args.name);
            if (idx < 0) return null;
            const id = wm.getSheetIdList()[idx];
            try { wm.activeSheetId = id; } catch (e) {}
            try { await dcs.loadSheetData({ sheetId: id }); } catch (e) {}
            for (let i = 0; i < 40; i++) {
                if (dcs.getIsLoaded(id)) break;
                await new Promise(res => setTimeout(res, 500));
            }
            const s = wm.getSheetBySheetId(id);
            const d = s.getCellDataAtPosition(args.row, args.col);
            if (!d) return "";
            if (d.formattedValue != null) {
                const fv = d.formattedValue;
                return String(typeof fv === 'object' && fv.value != null ? fv.value : fv);
            }
            return d.value != null ? String(d.value) : "";
        }
        """
        return self._page.evaluate(script, {"name": sheet_name, "row": row, "col": col})

    def find_person_rows(self, sheet_name, person_name, name_col=1, start_row=0):
        """在指定工作表的 name_col 列中查找 person_name，返回所有匹配行号列表。

        默认 name_col=1（B 列），行号从 0 开始。
        """
        script = r"""
        async (args) => {
            const app = window.SpreadsheetApp;
            const wm = app && app.workbook && app.workbook.worksheetManager;
            const dcs = app && app.dataCenterService;
            if (!wm || !dcs) return [];
            const idx = wm.getSheetNameList().indexOf(args.name);
            if (idx < 0) return [];
            const id = wm.getSheetIdList()[idx];
            try { wm.activeSheetId = id; } catch (e) {}
            try { await dcs.loadSheetData({ sheetId: id }); } catch (e) {}
            for (let i = 0; i < 40; i++) {
                if (dcs.getIsLoaded(id)) break;
                await new Promise(res => setTimeout(res, 500));
            }
            const s = wm.getSheetBySheetId(id);
            function cellText(d) {
                if (!d) return "";
                if (d.formattedValue != null) {
                    const fv = d.formattedValue;
                    return String(typeof fv === 'object' && fv.value != null ? fv.value : fv);
                }
                return d.value != null ? String(d.value) : "";
            }
            const rows = [];
            const rc = s.getRowCount();
            for (let r = args.start_row; r < rc; r++) {
                if (cellText(s.getCellDataAtPosition(r, args.name_col)).trim() === args.person) {
                    rows.push(r);
                }
            }
            return rows;
        }
        """
        return self._page.evaluate(script, {
            "name": sheet_name,
            "person": person_name,
            "name_col": name_col,
            "start_row": start_row,
        })

    # ---------------- 写入（UI 操作方式） ----------------

    _CELL_CENTER_JS = r"""
    (args) => {
        const app = window.SpreadsheetApp;
        const view = app && app.view;
        const sv = view && view.spreadsheetView;
        const rca = view && view.canvas && view.canvas.rowColAccessor;
        if (!rca) return null;

        // 优先：spreadsheetView 直接给出单元格视口矩形（自动处理滚动/虚拟渲染）
        if (sv && typeof sv.getCellRect === 'function') {
            try {
                const r = sv.getCellRect(args.row, args.col);
                if (r) {
                    const w = r.width != null ? r.width : (r.right != null ? r.right - r.left : 0);
                    const h = r.height != null ? r.height : (r.bottom != null ? r.bottom - r.top : 0);
                    const x = r.x != null ? r.x : r.left;
                    const y = r.y != null ? r.y : r.top;
                    if (w > 0 && h > 0) return { x: x + w / 2, y: y + h / 2 };
                }
            } catch (e) {}
        }

        // 回退：.excel-container 原点 + 行头宽/列头高 + 行列累计偏移
        const ROW_HEADER_W = 50;
        const COL_HEADER_H = 24;
        let rect = null;
        document.querySelectorAll('.excel-container').forEach((c) => {
            if (rect) return;
            const r = c.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) rect = r;
        });
        if (!rect) {
            let maxArea = 0;
            document.querySelectorAll('canvas').forEach((c) => {
                const r = c.getBoundingClientRect();
                const a = r.width * r.height;
                if (a > maxArea) { maxArea = a; rect = r; }
            });
        }
        if (!rect) return null;

        const colOffset = args.col === 0 ? 0 : rca.getColsWidth(0, args.col - 1);
        const rowOffset = args.row === 0 ? 0 : rca.getRowsHeight(0, args.row - 1);
        const w = rca.getColsWidth(args.col, args.col);
        const h = rca.getRowsHeight(args.row, args.row);
        return {
            x: rect.left + ROW_HEADER_W + colOffset + w / 2,
            y: rect.top + COL_HEADER_H + rowOffset + h / 2,
        };
    }
    """

    def _cell_center(self, row, col):
        """计算当前激活工作表中 (row, col) 单元格中心的视口坐标，失败返回 None。"""
        try:
            return self._page.evaluate(self._CELL_CENTER_JS, {"row": row, "col": col})
        except Exception:
            return None

    def _scroll_cell_into_view(self, row, col):
        """尽力把 (row, col) 滚入可视区域，避免 UI 双击落空（腾讯文档为虚拟渲染）。"""
        script = r"""
        (args) => {
            const app = window.SpreadsheetApp;
            const view = app && app.view;
            const sv = view && view.spreadsheetView;
            const fns = ['scrollToCell', 'scrollCellIntoView'];
            for (const n of fns) {
                const fn = (sv && sv[n]) || (view && view[n]);
                if (typeof fn === 'function') {
                    try { fn(args.row, args.col); return true; } catch (e) {}
                }
            }
            return false;
        }
        """
        try:
            self._page.evaluate(script, {"row": row, "col": col})
        except Exception:
            pass
        self._page.wait_for_timeout(400)

    def _ui_set_cell(self, sheet_name, row, col, text):
        """按 UI 操作方式把 text 写入 (row, col)（0 基索引）。

        流程：切换并加载目标表 → 滚入视口 → 双击进入编辑 → Cmd+A 全选清空 →
        键盘输入 → 点击别处触发 blur 提交。返回是否完成整个流程。
        说明：不直接调用 setSingleValue，因为其不触发协同提交、数据不持久化。
        """
        meta = self._ensure_loaded(sheet_name)
        if not meta or not meta.get("loaded"):
            return False
        self._page.wait_for_timeout(500)

        self._scroll_cell_into_view(row, col)

        pt = self._cell_center(row, col)
        if not pt:
            return False

        # 双击进入编辑态
        self._page.mouse.dblclick(pt["x"], pt["y"])
        self._page.wait_for_timeout(700)

        # 全选清空 + 输入
        self._page.keyboard.press("Meta+a")
        self._page.keyboard.type(text, delay=20)
        self._page.wait_for_timeout(300)

        # 提交：点击相邻单元格触发 blur（比回车更可靠地触发协同提交）
        commit_pt = self._cell_center(row + 1, col) or self._cell_center(row, col + 1)
        if commit_pt:
            self._page.mouse.click(commit_pt["x"], commit_pt["y"])
        else:
            self._page.keyboard.press("Enter")
        self._page.wait_for_timeout(1500)
        return True

    def write_weekly(self, sheet_name, person_name, entries, content_col=2,
                     expect_col=3, actual_col=4):
        """定位 person_name 所在行，向下连续写入周报内容与进度。

        entries 为 [{"content": str, "progress": str}, ...] 列表。
        content 写入 content_col 列（重点工作内容），progress 同时写入
        expect_col（预期进度）与 actual_col（实际进度）两列。
        返回是否全部写入成功。
        """
        rows = self.find_person_rows(sheet_name, person_name)
        if not rows:
            print(f"未在当前工作表中找到 {person_name}，无法定位写入区域。")
            return False

        start_row = rows[0]
        total = len(entries) * 3
        ok_count = 0
        for i, entry in enumerate(entries):
            r = start_row + i
            content = entry["content"]
            progress = entry["progress"]
            print(f"  写入 {person_name} 第 {i + 1} 条 -> 行 {r + 1} (内容+进度)...")
            if self._ui_set_cell(sheet_name, r, content_col, content):
                ok_count += 1
            if self._ui_set_cell(sheet_name, r, expect_col, progress):
                ok_count += 1
            if self._ui_set_cell(sheet_name, r, actual_col, progress):
                ok_count += 1
            self._page.wait_for_timeout(300)
        return ok_count == total

    def create_sheet_from_template(self, new_name):
        """基于最近一个工作表模板新建 new_name。

        尝试 worksheetManager 的复制/新建 API；失败返回 False。
        注意：具体 API 名称需在有效 Cookie 下实机确认，此处做多方法兼容尝试。
        """
        script = r"""
        async (args) => {
            const app = window.SpreadsheetApp;
            const wm = app && app.workbook && app.workbook.worksheetManager;
            if (!wm) return false;
            const names = wm.getSheetNameList();
            if (names.indexOf(args.name) >= 0) return 'exists';
            const templateId = wm.getSheetIdList()[names.length - 1];
            const fnNames = ['copySheet', 'duplicateSheet', 'cloneSheet', 'createSheet', 'addSheet'];
            for (const fnName of fnNames) {
                const fn = wm[fnName];
                if (typeof fn !== 'function') continue;
                try {
                    if (fnName === 'createSheet' || fnName === 'addSheet') {
                        fn(args.name);
                    } else {
                        fn(templateId, args.name);
                    }
                    return true;
                } catch (e) {}
            }
            return false;
        }
        """
        try:
            result = self._page.evaluate(script, {"name": new_name})
        except Exception:
            return False
        if not result:
            return False
        self._page.wait_for_timeout(2000)
        return new_name in self.list_sheets()
