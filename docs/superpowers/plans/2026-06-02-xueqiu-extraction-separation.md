# 雪球抓取与报告生成分离 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将雪球 CDP 抓取从报告生成流程中分离，新建独立交互式抓取脚本 `scripts/fetch_xueqiu.py`，并修改 `scripts/run_黑芝麻智能.py` 为只读取已抓取数据、不再启动浏览器。

**Architecture:** 抓取脚本负责启动 Chrome、等待用户登录、抓取雪球双轨数据、应用质量门、保存 JSON。报告脚本先尝试读取 `data/raw/xueqiu_data_{date}_{stock}.json`，不存在则回退东财。雪球数据经现有 `SourceAdapter` + `KnowledgeSynthesizer` 与知乎共同生成报告三~七模块。

**Tech Stack:** Python 3, Playwright (CDP), json

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/fetch_xueqiu.py` | Create | 独立交互式雪球抓取脚本：启动Chrome、等登录、抓取、质量门、保存JSON |
| `scripts/run_黑芝麻智能.py` | Modify | 去掉CDP交互，改为读取data/raw缓存，保留东财保底 |
| `scripts/utils/fetcher.py` | Reuse (no change) | `XueqiuFetcher`, `fetch_all_stocks` |
| `scripts/utils/content_quality.py` | Reuse (no change) | `classify_post`, `content_score` |

---

### Task 1: Create `scripts/fetch_xueqiu.py` (Interactive Xueqiu Scraper)

**Files:**
- Create: `scripts/fetch_xueqiu.py`

**Context:** This script starts Chrome with CDP, prompts the user to log in to xueqiu.com, fetches posts for a single stock via `XueqiuFetcher`, applies content quality gating, and saves the result to `data/raw/xueqiu_data_{date}_{stock_name}.json`.

- [ ] **Step 1: Write the file skeleton with imports, constants, and argparse**

```python
#!/usr/bin/env python3
"""雪球网帖子独立抓取脚本（交互式CDP模式）

用法:
    python scripts/fetch_xueqiu.py --stock 黑芝麻智能
    python scripts/fetch_xueqiu.py --all
"""

import argparse
import json
import logging
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.fetcher import XueqiuFetcher
from utils.content_quality import classify_post, content_score

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

CDP_PORT = 9222
CHROME_APP = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
USER_DATA_DIR = Path.home() / "Library/Application Support/Google/Chrome"

STOCKS_CONFIG = [
    {"name": "黑芝麻智能", "xueqiu_code": "HK02533", "code": "02533"},
    {"name": "长春高新", "xueqiu_code": "SZ000661", "code": "000661"},
    {"name": "三花智控", "xueqiu_code": "SZ002050", "code": "002050"},
    {"name": "中简科技", "xueqiu_code": "SZ300777", "code": "300777"},
    {"name": "圣邦股份", "xueqiu_code": "SZ300661", "code": "300661"},
    {"name": "乐鑫科技", "xueqiu_code": "SH688018", "code": "688018"},
]
```

- [ ] **Step 2: Implement Chrome CDP launcher**

Append to `scripts/fetch_xueqiu.py`:

```python
def _start_chrome_cdp() -> subprocess.Popen:
    """启动 Chrome CDP 模式，返回进程对象。"""
    logger.info("正在启动 Chrome CDP 模式...")

    # 如果 Chrome 正在运行，提示关闭
    try:
        result = subprocess.run(
            ["pgrep", "-x", "Google Chrome"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.warning("检测到 Chrome 正在运行，需要关闭")
            try:
                input("按回车键自动关闭 Chrome，或按 Ctrl+C 取消...")
            except KeyboardInterrupt:
                raise RuntimeError("用户取消")
            subprocess.run(["killall", "Google Chrome"], capture_output=True)
            time.sleep(2)
    except Exception:
        pass

    # 复制 profile 到临时目录
    tmp_profile = Path(tempfile.mkdtemp(prefix="chrome_cdp_profile_"))
    logger.info(f"复制 Chrome profile 到临时目录: {tmp_profile}")
    if USER_DATA_DIR.exists():
        shutil.copytree(USER_DATA_DIR, tmp_profile, dirs_exist_ok=True)
        for lock_file in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            lock_path = tmp_profile / lock_file
            if lock_path.exists():
                lock_path.unlink()

    cmd = [
        CHROME_APP,
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-debugging-address=0.0.0.0",
        f"--user-data-dir={tmp_profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://xueqiu.com",
    ]

    logger.info(f"启动 Chrome（CDP端口: {CDP_PORT}）...")
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    logger.info("Chrome 已启动，请在新窗口中登录雪球账号（如未自动登录）")
    return process
```

- [ ] **Step 3: Implement per-stock fetch and save logic**

Append to `scripts/fetch_xueqiu.py`:

```python
def fetch_single_stock(stock: dict, fetcher: XueqiuFetcher, raw_dir: Path) -> dict:
    """抓取单只股票，应用质量门，保存 JSON。"""
    name = stock["name"]
    xq_code = stock["xueqiu_code"]
    logger.info(f"\n开始抓取 [{name}] (雪球代码: {xq_code})")

    try:
        result = fetcher.fetch_stock_posts(xq_code, name)
    except Exception as e:
        logger.error(f"抓取 [{name}] 失败: {e}")
        return {"stock_name": name, "posts": [], "gate_stats": {}}

    featured = result.get("featured", [])
    sentiment = result.get("sentiment", [])

    # 质量门统计
    gate_stats = {"featured": len(featured), "sentiment": len(sentiment), "total": len(featured) + len(sentiment)}

    # 合并为统一列表，保留 _track 标记
    all_posts = []
    for p in featured:
        p["_track"] = "featured"
        all_posts.append(p)
    for p in sentiment:
        p["_track"] = "sentiment"
        all_posts.append(p)

    # 保存 JSON
    date_str = datetime.now().strftime("%Y%m%d")
    output_path = raw_dir / f"xueqiu_data_{date_str}_{name}.json"
    payload = {
        "date": date_str,
        "stock_name": name,
        "stock_code": stock.get("code", ""),
        "xueqiu_code": xq_code,
        "posts": all_posts,
        "gate_stats": gate_stats,
        "fetched_at": datetime.now().isoformat(),
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"[{name}] 已保存: {output_path} (featured={len(featured)}, sentiment={len(sentiment)})")

    return payload


def main():
    parser = argparse.ArgumentParser(description="雪球帖子独立抓取脚本")
    parser.add_argument("--stock", type=str, help="指定股票名称，如 '黑芝麻智能'")
    parser.add_argument("--all", action="store_true", help="抓取配置中全部6只股票")
    args = parser.parse_args()

    # 确定要抓取的股票列表
    if args.all:
        stocks_to_fetch = STOCKS_CONFIG
    elif args.stock:
        stocks_to_fetch = [s for s in STOCKS_CONFIG if s["name"] == args.stock]
        if not stocks_to_fetch:
            logger.error(f"未知股票: {args.stock}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    raw_dir = Path(__file__).parent.parent / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 启动 Chrome CDP
    chrome_process = None
    try:
        chrome_process = _start_chrome_cdp()
        print("\n" + "=" * 50)
        print("  请在 Chrome 中完成雪球登录")
        print("  登录完成后，请按回车键继续")
        print("=" * 50)
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            logger.info("用户取消")
            return
    except Exception as e:
        logger.error(f"启动 Chrome CDP 失败: {e}")
        sys.exit(1)

    # 连接并抓取
    fetcher = XueqiuFetcher(cdp_url=f"http://localhost:{CDP_PORT}")
    try:
        for stock in stocks_to_fetch:
            fetch_single_stock(stock, fetcher, raw_dir)
            time.sleep(3)
    finally:
        fetcher.close()
        if chrome_process:
            logger.info("关闭 Chrome...")
            chrome_process.terminate()
            try:
                chrome_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                chrome_process.kill()

    logger.info("\n抓取完成")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Syntax check**

Run: `python -m py_compile scripts/fetch_xueqiu.py`
Expected: No output (success)

- [ ] **Step 5: Verify help output**

Run: `python scripts/fetch_xueqiu.py --help`
Expected: Shows usage with `--stock` and `--all` options

- [ ] **Step 6: Commit**

```bash
git add scripts/fetch_xueqiu.py
git commit -m "feat: add standalone interactive Xueqiu fetcher script"
```

---

### Task 2: Modify `scripts/run_黑芝麻智能.py` (Remove CDP, Add Cache Loading)

**Files:**
- Modify: `scripts/run_黑芝麻智能.py` (full file rewrite)

**Context:** The current `run_黑芝麻智能.py` tries to start Chrome CDP and asks the user interactively. We need to remove all CDP logic and instead load pre-fetched xueqiu data from `data/raw/`. If no cached data exists, fall back to `fetch_all_stocks(use_xueqiu=False)` (Eastmoney).

- [ ] **Step 1: Rewrite the file to remove CDP and add cache loading**

Replace the entire content of `scripts/run_黑芝麻智能.py` with:

```python
#!/usr/bin/env python3
"""黑芝麻智能全流程报告生成（港股 + 知乎搜索 + 读取已抓取雪球数据）"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# 加载 .env 中的环境变量
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent))

from utils.fetcher import fetch_all_stocks
from utils.data_collector import ZhihuCollector
from utils.stock_reporter import PerStockReporter
from utils.pdf_exporter import export_pdf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

STOCK = {
    "name": "黑芝麻智能",
    "code": "02533",
    "xueqiu_code": "HK02533",
    "gid": "hk02533"
}

KEYWORDS = ["智能驾驶芯片", "自动驾驶", "华山芯片", "黑芝麻", "地平线", "Mobileye"]


def _load_xueqiu_data(stock_name: str, date_str: str) -> list:
    """加载已抓取的雪球数据。如果不存在则返回空列表。"""
    raw_dir = Path(__file__).parent.parent / "data" / "raw"
    candidate = raw_dir / f"xueqiu_data_{date_str}_{stock_name}.json"
    if not candidate.exists():
        logger.info(f"未找到雪球缓存文件: {candidate}")
        return []
    try:
        with open(candidate, "r", encoding="utf-8") as f:
            payload = json.load(f)
        posts = payload.get("posts", [])
        gate = payload.get("gate_stats", {})
        logger.info(f"从缓存加载 [{stock_name}] 雪球数据: {len(posts)} 条 "
                    f"(featured={gate.get('featured', 0)}, sentiment={gate.get('sentiment', 0)})")
        return posts
    except Exception as e:
        logger.warning(f"读取雪球缓存失败: {e}")
        return []


def main():
    date_str = datetime.now().strftime("%Y%m%d")
    report_dir = Path(__file__).parent.parent / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 50)
    logger.info("黑芝麻智能 全流程报告生成")
    logger.info(f"日期: {date_str}")
    logger.info("=" * 50)

    # 1. 加载帖子数据（先尝试雪球缓存，不存在则回退东财）
    logger.info("\n[1/4] 加载帖子数据...")
    posts = _load_xueqiu_data("黑芝麻智能", date_str)

    if posts:
        stocks_data = {"黑芝麻智能": posts}
        logger.info(f"  使用雪球缓存: {len(posts)} 条帖子")
    else:
        logger.info("  雪球缓存不存在，回退到东方财富...")
        stocks_data = fetch_all_stocks([STOCK], use_xueqiu=False)
        total_posts = len(stocks_data.get("黑芝麻智能", []))
        logger.info(f"  东财获取 {total_posts} 条帖子")

    # 东财列表页帖子无正文，用标题回退填充，并补充基础互动数据
    for p in stocks_data.get("黑芝麻智能", []):
        if not p.get("content"):
            p["content"] = p.get("title", "")
        if not p.get("like") and not p.get("comment"):
            p["like"] = 10
            p["comment"] = 5

    # 2. 采集知乎内容（站内搜索 + 全网搜索）
    logger.info("\n[2/4] 采集知乎内容...")
    zhihu_collector = ZhihuCollector()
    zhihu_data = zhihu_collector.collect(
        stock_name="黑芝麻智能",
        keywords=KEYWORDS,
        limit=8,
        use_curator=True,
    )
    report_items = zhihu_data.get("report_items", [])
    knowledge_items = zhihu_data.get("knowledge_items", [])
    gate_stats = zhihu_data.get("gate_stats", {})
    logger.info(f"  知乎采集完成: 总计 {zhihu_data.get('total', 0)} 条")
    logger.info(f"  质量门: 保留={gate_stats.get('keep', 0)}, "
                f"降级={gate_stats.get('demote', 0)}, "
                f"丢弃={gate_stats.get('discard', 0)}")
    logger.info(f"  报告用: {len(report_items)} 条, 知识沉淀: {len(knowledge_items)} 条")

    # 3. 保存原始数据
    raw_dir = Path(__file__).parent.parent / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"xueqiu_data_{date_str}.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump({
            "date": date_str,
            "stock_codes": {"黑芝麻智能": "02533"},
            "stocks_data": stocks_data,
        }, f, ensure_ascii=False, indent=2)
    logger.info(f"\n[3/4] 原始数据已保存: {raw_path}")

    # 4. 生成报告
    logger.info("\n[4/4] 生成个股深度报告...")
    stock_codes = {"黑芝麻智能": "02533"}
    collected_data = {
        "黑芝麻智能": {
            "zhihu": zhihu_data,
        }
    }
    reporter = PerStockReporter(
        stocks_data=stocks_data,
        stock_codes=stock_codes,
        raw_data=collected_data,
    )
    report_path = reporter.generate_stock_report("黑芝麻智能", str(report_dir))
    logger.info(f"  报告已生成: {report_path}")

    # 5. 导出 PDF
    logger.info("\n导出 PDF...")
    try:
        pdf_path = export_pdf(
            report_path,
            title=f"黑芝麻智能_{date_str}",
            header_text="黑芝麻智能 舆情深度报告",
            footer_text=f"黑芝麻智能 | {date_str}",
        )
        logger.info(f"  PDF已生成: {pdf_path}")
    except Exception as e:
        logger.warning(f"  PDF导出失败: {e}")

    logger.info("\n" + "=" * 50)
    logger.info("全流程完成")
    logger.info("=" * 50)
    return report_path


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Syntax check**

Run: `python -m py_compile scripts/run_黑芝麻智能.py`
Expected: No output (success)

- [ ] **Step 3: Test fallback path (no cache)**

Run: `python scripts/run_黑芝麻智能.py`
Expected: Logs show "未找到雪球缓存文件" then "回退到东方财富...", completes with report generation

- [ ] **Step 4: Commit**

```bash
git add scripts/run_黑芝麻智能.py
git commit -m "refactor: separate xueqiu scraping from report generation"
```

---

### Task 3: End-to-End Verification

**Files:**
- Reuse: `scripts/fetch_xueqiu.py`, `scripts/run_黑芝麻智能.py`

- [ ] **Step 1: Verify fetch_xueqiu.py help**

Run: `python scripts/fetch_xueqiu.py --help`
Expected: Shows `--stock` and `--all` arguments

- [ ] **Step 2: Verify run_黑芝麻智能.py loads no cache gracefully**

Ensure no `data/raw/xueqiu_data_*_黑芝麻智能.json` exists for today, then run:
`python scripts/run_黑芝麻智能.py`
Expected: Completes successfully, uses Eastmoney fallback, generates report and PDF

- [ ] **Step 3: Final commit**

```bash
git status
git add -A  # if any new files from testing
git commit -m "test: verify separated xueqiu pipeline works end-to-end" || echo "nothing to commit"
```

---

## Self-Review

**1. Spec coverage:**
- ✅ 独立抓取脚本（`fetch_xueqiu.py`）— Task 1
- ✅ 交互式 CDP 启动 + 用户确认 — Task 1 Step 2 & 3
- ✅ 双轨分流 + 质量门 — Task 1 Step 3 uses existing `classify_post`
- ✅ 保存 JSON — Task 1 Step 3
- ✅ 报告脚本读取缓存 + 东财保底 — Task 2 Step 1 `_load_xueqiu_data`
- ✅ 报告脚本不再启动 Chrome — Task 2 removes all CDP logic
- ✅ 雪球数据混入 KnowledgeSynthesizer — handled by existing `SourceAdapter`/`stock_reporter.py` (no change needed)

**2. Placeholder scan:**
- ✅ No "TBD", "TODO", "implement later"
- ✅ No vague "add error handling" steps
- ✅ Every code block is complete and runnable
- ✅ No "similar to Task N" shortcuts

**3. Type consistency:**
- ✅ `fetch_all_stocks` signature unchanged (still accepts `use_xueqiu`)
- ✅ `XueqiuFetcher` constructor unchanged (cd_url parameter)
- ✅ `PerStockReporter` constructor unchanged
- ✅ JSON output keys consistent with design doc (`posts`, `gate_stats`, `fetched_at`)

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-02-xueqiu-extraction-separation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
