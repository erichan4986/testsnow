from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))


def test_build_x_claw_headers_sets_required_auth_fields() -> None:
    from iwencai_industry_research import build_x_claw_headers

    headers = build_x_claw_headers("secret-key", trace_id="a" * 64)

    assert headers["Authorization"] == "Bearer secret-key"
    assert headers["Content-Type"] == "application/json"
    assert headers["X-Claw-Call-Type"] == "normal"
    assert headers["X-Claw-Skill-Id"] == "report-search"
    assert headers["X-Claw-Skill-Version"] == "2.0.0"
    assert headers["X-Claw-Plugin-Id"] == "none"
    assert headers["X-Claw-Plugin-Version"] == "none"
    assert headers["X-Claw-Trace-Id"] == "a" * 64


def test_fetch_iwencai_reports_posts_report_search_payload() -> None:
    from iwencai_industry_research import fetch_iwencai_reports

    calls = []

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"status_code": 0, "data": [{"uid": "r1", "title": "半导体行业深度报告"}]}

    def fake_post(url, json=None, headers=None, timeout=30):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse()

    rows = fetch_iwencai_reports(
        "半导体 行业深度 2026",
        api_key="secret-key",
        base_url="https://openapi.iwencai.com",
        size=50,
        post=fake_post,
        trace_id="b" * 64,
    )

    assert rows == [{"uid": "r1", "title": "半导体行业深度报告"}]
    assert calls[0]["url"] == "https://openapi.iwencai.com/v1/comprehensive/search"
    assert calls[0]["json"] == {
        "channels": ["report"],
        "app_id": "AIME_SKILL",
        "query": "半导体 行业深度 2026",
        "size": 50,
    }
    assert calls[0]["headers"]["Authorization"] == "Bearer secret-key"


def test_deduplicate_keeps_highest_score_per_uid() -> None:
    from iwencai_industry_research import deduplicate_iwencai_reports

    rows = [
        {"uid": "same", "title": "低分", "score": 0.1, "publish_date": "2026-06-01"},
        {"uid": "same", "title": "高分", "score": 0.3, "publish_date": "2026-06-02"},
        {"title": "无 uid", "score": 0.2, "publish_date": "2026-06-03"},
    ]

    deduped = deduplicate_iwencai_reports(rows)

    assert [row["title"] for row in deduped] == ["无 uid", "高分"]


def test_select_industry_reports_filters_noise_and_falls_back_to_180_days() -> None:
    from iwencai_industry_research import select_iwencai_industry_reports

    rows = [
        {
            "uid": "recent-industry",
            "title": "电子行业2026年中期策略：AI产业变革加速推进，半导体迎来发展新机遇",
            "publish_date": "2026-06-23",
            "organization": "中原证券",
            "url": "https://ms.10jqka.com.cn/report/recent",
            "summary": "半导体行业策略报告。",
            "score": 0.12,
        },
        {
            "uid": "stock-report",
            "title": "圣邦股份300661一季报点评：模拟芯片平台持续扩张",
            "publish_date": "2026-06-20",
            "organization": "国信证券",
            "url": "https://ms.10jqka.com.cn/report/stock",
            "summary": "个股研报。",
            "score": 0.18,
        },
        {
            "uid": "old-but-valid",
            "title": "半导体行业深度报告：设备材料国产化持续推进",
            "publish_date": "2026-03-01",
            "organization": "招商证券",
            "url": "https://ms.10jqka.com.cn/report/old",
            "summary": "产业链深度报告。",
            "score": 0.09,
        },
        {
            "uid": "unrelated",
            "title": "深度学习选股训练目标与回测方法",
            "publish_date": "2026-06-22",
            "organization": "量化团队",
            "url": "https://ms.10jqka.com.cn/report/noise",
            "summary": "与半导体主题无关。",
            "score": 0.2,
        },
    ]

    result = select_iwencai_industry_reports(
        rows,
        query="半导体 行业深度 2026",
        today=date(2026, 6, 24),
        recent_days=90,
        fallback_days=180,
        min_recent_items=3,
        max_items=5,
    )

    assert [item["uid"] for item in result["selected"]] == ["recent-industry", "old-but-valid"]
    assert result["window_days"] == 180
    dropped_reasons = {item["uid"]: item["drop_reason"] for item in result["dropped"]}
    assert dropped_reasons["stock-report"] == "stock_specific_or_code_title"
    assert dropped_reasons["unrelated"] == "theme_mismatch"


def test_select_industry_reports_keeps_series_and_theme_synonym_titles() -> None:
    from iwencai_industry_research import select_iwencai_industry_reports

    rows = [
        {
            "uid": "optical-series",
            "title": "光模块系列（一）：800G/1.6T光模块将成为主流",
            "publish_date": "2026-04-06",
            "organization": "西部证券",
            "url": "https://ms.10jqka.com.cn/report/optical",
            "summary": "AI推动数据中心光模块进入新一轮周期。",
            "score": 0.13,
        },
        {
            "uid": "analog-ic",
            "title": "模拟IC回归新周期，国产龙头的成长空间与路径",
            "publish_date": "2026-04-03",
            "organization": "招商证券",
            "url": "https://ms.10jqka.com.cn/report/analog",
            "summary": "模拟芯片行业报告，国产替代进程加速。",
            "score": 0.11,
        },
    ]

    optical = select_iwencai_industry_reports(
        rows[:1],
        query="光模块 800G CPO 行业研究报告",
        today=date(2026, 6, 24),
        recent_days=90,
        fallback_days=180,
        min_recent_items=1,
    )
    analog = select_iwencai_industry_reports(
        rows[1:],
        query="模拟芯片 行业研究报告",
        today=date(2026, 6, 24),
        recent_days=90,
        fallback_days=180,
        min_recent_items=1,
    )

    assert [item["uid"] for item in optical["selected"]] == ["optical-series"]
    assert [item["uid"] for item in analog["selected"]] == ["analog-ic"]


def test_select_industry_reports_rejects_summary_only_theme_match() -> None:
    from iwencai_industry_research import select_iwencai_industry_reports

    rows = [
        {
            "uid": "auto-strategy",
            "title": "汽车行业2026年度投资策略报告：不必悲观，结构存机会",
            "publish_date": "2025-12-27",
            "organization": "国海证券",
            "url": "https://ms.10jqka.com.cn/report/auto",
            "summary": "智能驾驶、robotaxi商业化加速，机器人领域进入1-10开端。",
            "score": 0.11,
        }
    ]

    result = select_iwencai_industry_reports(
        rows,
        query="人形机器人 白皮书",
        today=date(2026, 6, 24),
        recent_days=90,
        fallback_days=180,
        min_recent_items=1,
    )

    assert result["selected"] == []
    assert result["dropped"][0]["drop_reason"] == "theme_mismatch"


def test_select_industry_reports_drops_hk_code_and_daily_market_roundup_titles() -> None:
    from iwencai_industry_research import select_iwencai_industry_reports

    rows = [
        {
            "uid": "hk-stock",
            "title": "剑桥科技（06166）：首次覆盖报告：AI算力基建供应商，光模块业务迎来拐点",
            "publish_date": "2026-05-25",
            "organization": "光大证券",
            "url": "https://ms.10jqka.com.cn/report/hk-stock",
            "summary": "个股首次覆盖报告。",
            "score": 0.14,
        },
        {
            "uid": "daily-roundup",
            "title": "A股日评：光通信产业链领涨，能源板块再度活跃",
            "publish_date": "2026-06-04",
            "organization": "长江证券",
            "url": "https://ms.10jqka.com.cn/report/daily",
            "summary": "市场交易日评。",
            "score": 0.01,
        },
    ]

    result = select_iwencai_industry_reports(
        rows,
        query="光模块 800G CPO 行业研究报告",
        today=date(2026, 6, 24),
        recent_days=90,
        fallback_days=180,
        min_recent_items=1,
    )

    assert result["selected"] == []
    dropped_reasons = {item["uid"]: item["drop_reason"] for item in result["dropped"]}
    assert dropped_reasons["hk-stock"] == "stock_specific_or_code_title"
    assert dropped_reasons["daily-roundup"] == "low_value_market_roundup"


def test_preview_markdown_marks_industry_research_display_only() -> None:
    from iwencai_industry_research import build_iwencai_industry_preview_markdown

    summary = {
        "queries": [
            {
                "query": "半导体 行业深度 2026",
                "raw_count": 4,
                "dedup_count": 3,
                "window_days": 180,
                "selected": [
                    {
                        "title": "半导体行业深度报告：设备材料国产化持续推进",
                        "publish_date": "2026-03-01",
                        "organization": "招商证券",
                        "url": "https://ms.10jqka.com.cn/report/old",
                        "summary": "产业链深度报告。",
                        "score": 0.09,
                        "quality_action": "display_only",
                    }
                ],
                "dropped": [{"title": "圣邦股份300661一季报点评", "drop_reason": "stock_specific_or_code_title"}],
            }
        ]
    }

    markdown = build_iwencai_industry_preview_markdown(summary)

    assert "# iwencai 行业研报 Preview" in markdown
    assert "knowledge_eligible: `false`" in markdown
    assert "report_eligible: `true`" in markdown
    assert "半导体行业深度报告" in markdown
    assert "stock_specific_or_code_title" in markdown
