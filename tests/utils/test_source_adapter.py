import pytest
from scripts.utils.source_adapter import (
    SynthesisItem, SourceAdapter,
    XueqiuAdapter, ZhihuAdapter, ReportAdapter,
)


def test_xueqiu_adapter_maps_fields():
    raw = {
        "title": "模拟芯片涨价分析",
        "author": "张三",
        "content": "圣邦股份Q1收入增长40%...",
        "url": "https://xueqiu.com/123/456",
        "time": "2026-05-20 10:00",
        "like_count": 100,
        "comment_count": 20,
        "source": "雪球",
    }
    item = XueqiuAdapter.to_synthesis_item(raw)
    assert item.title == "模拟芯片涨价分析"
    assert item.author == "张三"
    assert item.source_platform == "雪球"
    assert item.interaction_score == 120
    assert "40%" in item.content


def test_zhihu_adapter_maps_platform():
    raw = {
        "title": "半导体行业观察",
        "author_name": "李四",
        "content_text": "杰华特竞争加剧...",
        "url": "https://zhuanlan.zhihu.com/p/123",
        "edit_time": 1747756800,
        "vote_up_count": 50,
        "comment_count": 10,
        "source_platform": "网易",
    }
    item = ZhihuAdapter.to_synthesis_item(raw)
    assert item.source_platform == "知乎全网(网易)"
    assert item.interaction_score == 60


def test_report_adapter_maps_institution():
    raw = {
        "title": "圣邦股份深度报告",
        "institution": "国信证券",
        "content": "目标价120元...",
        "url": "",
        "publish_date": "2026-05-15",
        "rating": "买入",
    }
    item = ReportAdapter.to_synthesis_item(raw)
    assert item.author == "国信证券"
    assert item.source_platform == "研报"
    assert item.content == "[评级: 买入] 目标价120元..."
