import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from source_adapter import SynthesisItem
from synthesis_display_deduper import dedupe_synthesis_display_items


def _item(title, content, source_type, source_credit, platform="材料层", url=""):
    return SynthesisItem(
        title=title,
        content=content,
        author="",
        source_platform=platform,
        url=url,
        publish_time="2026-06-01",
        extra={
            "source_type": source_type,
            "source_credit": source_credit,
            "synthesis_display_only": True,
        },
    )


def test_dedupe_prefers_higher_credit_duplicate_content():
    lower_credit = _item(
        "券商转载观点",
        "同一篇光模块深度分析，800G 与 1.6T 是核心方向。",
        "broker_research",
        72,
        platform="券商研报",
    )
    higher_credit = _item(
        "年报材料观点",
        "同一篇光模块深度分析，800G 与 1.6T 是核心方向。",
        "periodic_report_fulltext_analysis",
        75,
        platform="定期报告全文",
    )

    deduped, records = dedupe_synthesis_display_items([lower_credit, higher_credit])

    assert deduped == [higher_credit]
    assert records == [
        {
            "reason": "content_fingerprint",
            "kept": {
                "title": "年报材料观点",
                "source_platform": "定期报告全文",
                "source_type": "periodic_report_fulltext_analysis",
                "source_credit": 75,
                "url": "",
            },
            "duplicate": {
                "title": "券商转载观点",
                "source_platform": "券商研报",
                "source_type": "broker_research",
                "source_credit": 72,
                "url": "",
            },
        }
    ]


def test_dedupe_normalizes_mobile_and_desktop_urls():
    desktop = _item(
        "36kr PC",
        "PC 页面内容",
        "curated_external_analysis",
        65,
        url="http://www.36kr.com/p/123456?utm_source=x",
    )
    mobile = _item(
        "36kr Mobile",
        "移动页面内容不同也应先按 URL 去重",
        "curated_external_analysis",
        65,
        url="https://m.36kr.com/p/123456/",
    )

    deduped, records = dedupe_synthesis_display_items([desktop, mobile])

    assert deduped == [desktop]
    assert len(records) == 1
    assert records[0]["reason"] == "normalized_url"
    assert records[0]["duplicate"]["title"] == "36kr Mobile"
