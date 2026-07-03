import pytest
import subprocess
import sys
from pathlib import Path
from scripts.utils.source_adapter import (
    SynthesisItem, SourceAdapter,
    XueqiuAdapter, ZhihuAdapter, ReportAdapter, adapt_all,
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


def test_adapt_all_accepts_single_fundflow_record():
    items = adapt_all(fundflow={
        "date": "2026-06-10",
        "main_inflow": 1200,
        "main_outflow": 300,
    })

    assert len(items) == 1
    assert items[0].source_platform == "资金流向"
    assert items[0].extra["net"] == 900


def test_fundflow_adapter_accepts_baidu_pae_fields():
    items = adapt_all(fundflow={
        "date": "2026-07-02",
        "main_in": "1200",
        "super_net_in": "500",
        "large_net_in": "300",
        "medium_net_in": "-100",
        "small_net_in": "-900",
        "change_pct": "2.5",
        "close": "65.40",
        "source": "baidu_pae",
    })

    assert len(items) == 1
    item = items[0]
    assert item.source_platform == "资金流向"
    assert "主力净流入 1200万" in item.content
    assert "超大单 500万" in item.content
    assert "大单 300万" in item.content
    assert "小单 -900万" in item.content
    assert "涨跌 2.5%" in item.content
    assert item.extra["net"] == 1200.0
    assert item.extra["super_net_in"] == 500.0
    assert item.extra["large_net_in"] == 300.0
    assert item.extra["small_net_in"] == -900.0
    assert item.extra["source"] == "baidu_pae"


def test_adapt_all_agent_reach_missing_fields():
    raw = {
        "platform": "twitter",
        "title": None,
        "content": None,
        "author": None,
        "url": None,
        "publish_time": None,
    }
    items = adapt_all(agent_reach_items=[raw])
    assert len(items) == 1
    item = items[0]
    assert item.title == ""
    assert item.content == ""
    assert item.author == ""
    assert item.url == ""
    assert item.publish_time == ""
    assert item.interaction_score == 0
    assert item.source_platform == "AgentReach(twitter)"
    # Source-credit metadata is attached even for missing-source records.
    assert "raw" in item.extra
    assert item.extra["source_type"] == "missing_source"
    assert item.extra["source_credit"] == 10
    assert item.extra["knowledge_eligible"] is False
    assert item.extra["report_eligible"] is False
    assert isinstance(item.extra["credit_reasons"], list)


def test_adapt_all_agent_reach_includes_source_credit():
    raw = {
        "_platform": "web",
        "title": "黑芝麻智能测试",
        "content": "正文",
        "url": "https://www.blacksesame.com/zh/list_10/972.html",
        "author": "",
        "publish_time": "2026-06-01",
        "user_provided_url": True,
    }
    items = adapt_all(agent_reach_items=[raw])
    assert len(items) == 1
    item = items[0]
    assert item.source_platform == "AgentReach(web)"
    assert item.extra["raw"] is raw
    assert item.extra["source_type"] == "company_official"
    assert item.extra["source_domain"] == "blacksesame.com"
    assert item.extra["source_credit"] == 85
    assert item.extra["verification_status"] == "primary_source"
    assert any("用户显式提供" in r for r in item.extra["credit_reasons"])
    assert item.extra["knowledge_eligible"] is True
    assert item.extra["report_eligible"] is True


def test_adapt_all_agent_reach_social_url_gets_credit():
    raw = {
        "_platform": "web",
        "title": "讨论",
        "url": "https://www.zhihu.com/question/123456789",
    }
    items = adapt_all(agent_reach_items=[raw])
    assert len(items) == 1
    item = items[0]
    assert item.extra["source_type"] == "social_discussion"
    assert item.extra["source_credit"] == 35
    assert item.extra["knowledge_eligible"] is True
    assert item.extra["report_eligible"] is False


def test_adapt_all_agent_reach_unknown_web_gets_credit():
    raw = {
        "_platform": "web",
        "title": "某博客",
        "url": "https://some-unknown-blog.com/post/123",
    }
    items = adapt_all(agent_reach_items=[raw])
    assert len(items) == 1
    item = items[0]
    assert item.extra["source_type"] == "unknown_web"
    assert item.extra["source_credit"] == 30
    assert item.extra["knowledge_eligible"] is True
    assert item.extra["report_eligible"] is False

    raw = {
        "platform": "reddit",
        "title": "竞品分析",
        "publish_time": "2026-05-20",
    }
    items = adapt_all(agent_reach_items=[raw])
    assert len(items) == 1
    assert items[0].title == "竞品分析"
    assert items[0].source_platform == "AgentReach(reddit)"


def test_adapt_all_agent_reach_empty_content_uses_summary():
    raw = {
        "platform": "xiaohongshu",
        "title": "t",
        "summary": "summary text",
        "content": "",
    }
    items = adapt_all(agent_reach_items=[raw])
    assert len(items) == 1
    assert items[0].content == "summary text"


def test_adapt_all_agent_reach_unknown_author():
    raw = {
        "platform": "bilibili",
        "title": "t",
    }
    items = adapt_all(agent_reach_items=[raw])
    assert len(items) == 1
    assert items[0].author == ""


def test_adapt_all_agent_reach_interaction_score_from_various_keys():
    raw = {
        "platform": "wechat",
        "likes": 42,
    }
    items = adapt_all(agent_reach_items=[raw])
    assert items[0].interaction_score == 42


def test_source_adapter_imports_from_scripts_working_directory():
    """Single-stock entry scripts import source_adapter as utils.source_adapter."""
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from utils.source_adapter import adapt_all; "
                "item = adapt_all(agent_reach_items=["
                "{'_platform':'web','url':'https://www.blacksesame.com/zh/list_10/972.html'}"
                "])[0]; "
                "print(item.extra['source_type'])"
            ),
        ],
        cwd=repo_root / "scripts",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "company_official"
