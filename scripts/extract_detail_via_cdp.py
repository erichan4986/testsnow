#!/usr/bin/env python3
"""
通过 Chrome CDP 提取雪球帖子详情页完整内容
用户已登录 Chrome，使用本地 CDP 连接避免反爬

注意（2026-06-10）：
- 本脚本当前为孤儿状态，未被任何代码 import 或调用
- 同目录下 extract_detail.py 已覆盖相同功能
- 如需使用 CDP 模式提取详情页，可直接运行本脚本作为独立 CLI 工具
"""

import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

DATA_PATH = Path(__file__).parent.parent / "data" / "raw" / "xueqiu_data_20260520.json"
CDP_URL = "http://localhost:9222"

# 每只股票需要提取的详情页 URL（top3 精品帖子）
TARGET_URLS = {
    "黑芝麻智能": [
        ("https://xueqiu.com/8025337289/389734910", "黑芝麻智能（三）：平替英伟达，高阶智驾明年大规模量产"),
        ("https://xueqiu.com/8025337289/388652567", "黑芝麻智能（一）：AEB强制倒计时，舱驾一体打开10万级增量市场"),
    ],
    "长春高新": [
        ("https://xueqiu.com/3448047273/388421483", "长春高新股东会信息记录"),
        ("https://xueqiu.com/9926299616/387999629", "莫德纳暴涨12%：汉坦病毒事件驱动下的A股投资逻辑与真龙头梳理"),
        ("https://xueqiu.com/9573337236/387863697", "链思维拆解：长春高新从500元跌到86元，谁在讲故事？谁在算真账？"),
    ],
    "三花智控": [
        ("https://xueqiu.com/3945042689/387555498", "行情正在按照《5月投资思路》剧本演绎"),
        ("https://xueqiu.com/1155695148/388534017", "进攻看情绪，防守看估值"),
        ("https://xueqiu.com/3945042689/389230320", "其实当前阶段恰恰属于机器人最好时机"),
    ],
    "中简科技": [
        ("https://xueqiu.com/8019589642/384184563", "中简科技26Q1 | 始料不及，也只能耐心等待，相信确定性压到波动性"),
        ("https://xueqiu.com/8019589642/383894300", "25年算是一份脱水年报了"),
        ("https://xueqiu.com/4562991514/386713066", "恒神股份投资价值分析"),
    ],
    "圣邦股份": [
        ("https://xueqiu.com/6855532795/388411598", "这里绝对不是终点他是一个巨大的趋势出来了"),
        ("https://xueqiu.com/6855532795/386958374", "高位的盘旋之后，站上95之后，应该有一个巨大的趋势"),
        ("https://xueqiu.com/6855532795/389252799", "给他自由。这里绝对不是终点趋势会持续"),
    ],
    "乐鑫科技": [
        ("https://xueqiu.com/2704885039/387639520", "Anthropic 再度青睐 ESP32，Claude 开发者活动主推 M5Stack C..."),
        ("https://xueqiu.com/6518775321/388584188", "4月29日的集成电路集体业绩会的问答"),
        ("https://xueqiu.com/4756863557/389677293", "砸又不出力，才跌3个点就急吼吼拉"),
    ],
}


def extract_content(page, url):
    """从详情页提取完整正文"""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)  # 等待内容渲染

        content = page.evaluate("""() => {
            const selectors = ['.article__bd', '.article-content', 'article', '.detail'];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el) {
                    const text = el.innerText.trim();
                    if (text.length > 300) return text;
                }
            }
            // fallback
            let maxEl = null, maxLen = 0;
            document.querySelectorAll('div').forEach(div => {
                const t = (div.innerText || '').trim();
                if (t.length > maxLen && t.length < 50000) { maxLen = t.length; maxEl = div; }
            });
            return maxEl ? maxEl.innerText.trim() : '';
        }""")
        return content
    except Exception as e:
        print(f"    提取失败: {e}")
        return ""


def main():
    with sync_playwright() as p:
        # 连接已登录的 Chrome
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            print(f"已连接到 Chrome CDP: {CDP_URL}")
        except Exception as e:
            print(f"连接 CDP 失败: {e}")
            print("请确保 Chrome 已启动: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222")
            return

        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.pages[0] if context.pages else context.new_page()

        all_results = {}
        total = sum(len(urls) for urls in TARGET_URLS.values())
        current = 0

        for stock_name, urls in TARGET_URLS.items():
            print(f"\n{'='*60}")
            print(f"股票: {stock_name}")
            print(f"{'='*60}")
            stock_results = []

            for url, title in urls:
                current += 1
                print(f"\n[{current}/{total}] {title}")
                print(f"    URL: {url}")

                content = extract_content(page, url)
                if content and len(content) > 300:
                    print(f"    提取成功: {len(content)} 字")
                    stock_results.append({
                        "url": url,
                        "title": title,
                        "content": content,
                        "word_count": len(content),
                    })
                else:
                    print(f"    提取失败或内容太短 ({len(content) if content else 0} 字)")
                    stock_results.append({
                        "url": url,
                        "title": title,
                        "content": "",
                        "word_count": 0,
                    })

                if current < total:
                    time.sleep(3)  # 间隔 3 秒，避免触发风控

            all_results[stock_name] = stock_results

        browser.close()

    # 保存结果
    output_path = DATA_PATH.parent / "xueqiu_detail_full_20260521.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n提取完成，结果保存至: {output_path}")


if __name__ == "__main__":
    main()
