#!/usr/bin/env python3
"""雪球网帖子独立抓取脚本（交互式CDP模式）

用法:
    python scripts/high_risk/fetch_xueqiu.py --stock 黑芝麻智能
    python scripts/high_risk/fetch_xueqiu.py --all
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

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from utils.fetcher import XueqiuFetcher

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


def _start_chrome_cdp() -> tuple[subprocess.Popen, Path]:
    """启动 Chrome CDP 模式，返回 (进程对象, 临时 profile 目录)。"""
    logger.info("正在启动 Chrome CDP 模式...")

    # 如果 Chrome 正在运行，提示用户手动关闭
    try:
        result = subprocess.run(
            ["pgrep", "-x", "Google Chrome"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.warning("检测到 Chrome 正在运行。请先手动关闭所有 Chrome 窗口，然后按回车继续。")
            try:
                input()
            except KeyboardInterrupt:
                raise RuntimeError("用户取消")
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
    return process, tmp_profile


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

    raw_dir = REPO_ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 启动 Chrome CDP
    chrome_process = None
    tmp_profile = None
    try:
        chrome_process, tmp_profile = _start_chrome_cdp()
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
        if tmp_profile:
            logger.info(f"清理临时 profile 目录: {tmp_profile}")
            shutil.rmtree(tmp_profile, ignore_errors=True)

    logger.info("\n抓取完成")


if __name__ == "__main__":
    main()
