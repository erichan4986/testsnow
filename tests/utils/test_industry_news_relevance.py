from scripts.utils.industry_news_relevance import (
    HIGH_CONFIDENCE_THRESHOLD,
    build_industry_relevance_manifest,
    classify_industry_news_relevance,
)
from scripts.utils.source_adapter import SynthesisItem


def test_company_event_is_allowed_in_events_catalysts():
    result = classify_industry_news_relevance(
        stock_name="复旦微电",
        title="复旦微电发布2025年度业绩快报",
        content="公司预计净利润同比下降。",
        stock_config={},
    )

    assert result["relevance_class"] == "company_event"
    assert result["confidence"] >= 0.9
    assert "4.3" in result["allowed_sections"]
    assert result["relevance_chain"]["chain_id"] == "company_direct"


def test_industry_chain_relevant_supports_multi_hop_cis_capacity_chain():
    result = classify_industry_news_relevance(
        stock_name="韦尔股份",
        title="存储产品涨价带动晶圆厂产能紧张",
        content="市场关注存储扩产与晶圆厂排产变化。",
        stock_config={
            "industry_relevance": {
                "products": ["CIS", "图像传感器"],
                "chain_rules": [
                    {
                        "chain_id": "memory_capacity_to_cis_pricing",
                        "target_product": "CIS",
                        "hops": [
                            {
                                "id": "memory_price",
                                "statement": "存储产品涨价",
                                "keywords": ["存储涨价", "存储产品涨价"],
                                "requires_news_support": True,
                            },
                            {
                                "id": "wafer_capacity",
                                "statement": "上游晶圆厂产能紧张",
                                "keywords": ["晶圆厂产能紧张", "排产变化"],
                                "requires_news_support": True,
                            },
                            {
                                "id": "cis_capacity",
                                "statement": "CIS 排产可能被挤占",
                                "keywords": ["CIS", "图像传感器"],
                            },
                            {
                                "id": "watch_variable",
                                "statement": "CIS 供给和涨价节奏成为待验证变量",
                                "keywords": ["涨价", "供给"],
                            },
                        ],
                    }
                ],
            }
        },
    )

    assert result["relevance_class"] == "industry_chain_relevant"
    assert result["confidence"] >= HIGH_CONFIDENCE_THRESHOLD
    assert result["allowed_sections"] == ["4.1"]
    assert result["relevance_chain"]["chain_id"] == "memory_capacity_to_cis_pricing"
    assert [hop["id"] for hop in result["relevance_chain"]["hops"]] == [
        "memory_price",
        "wafer_capacity",
        "cis_capacity",
        "watch_variable",
    ]
    assert all(hop["evidence_type"] in {"news_text", "stock_config"} for hop in result["relevance_chain"]["hops"])


def test_low_confidence_industry_chain_downgrades_to_sector_background():
    result = classify_industry_news_relevance(
        stock_name="韦尔股份",
        title="存储产品涨价",
        content="市场关注存储价格变化。",
        stock_config={
            "industry_relevance": {
                "products": ["CIS"],
                "chain_rules": [
                    {
                        "chain_id": "memory_capacity_to_cis_pricing",
                        "target_product": "CIS",
                        "hops": [
                            {"id": "memory_price", "statement": "存储产品涨价", "keywords": ["存储产品涨价"], "requires_news_support": True},
                            {"id": "wafer_capacity", "statement": "上游晶圆厂产能紧张", "keywords": ["晶圆厂产能紧张"], "requires_news_support": True},
                            {"id": "cis_capacity", "statement": "CIS 排产可能被挤占", "keywords": ["CIS"]},
                        ],
                    }
                ],
            }
        },
    )

    assert result["relevance_class"] == "sector_background"
    assert result["confidence"] < HIGH_CONFIDENCE_THRESHOLD
    assert "4.3" not in result["allowed_sections"]


def test_generic_sector_news_is_not_allowed_in_events_catalysts():
    result = classify_industry_news_relevance(
        stock_name="复旦微电",
        title="半导体设备板块震荡走弱",
        content="多只半导体设备公司下跌。",
        stock_config={"industry_relevance": {"products": ["FPGA", "MCU"]}},
        matched_keywords=["半导体"],
    )

    assert result["relevance_class"] == "sector_background"
    assert result["allowed_sections"] == ["4.1"]


def test_build_manifest_excludes_industry_chains_not_allowed_in_4_3():
    items = [
        SynthesisItem(
            title="链条新闻",
            content="存储产品涨价带动晶圆厂产能紧张。",
            author="东方财富资讯",
            source_platform="行业资讯",
            url="http://news/chain",
            publish_time="2026-06-01",
            extra={
                "allowed_sections": ["4.1"],
                "relevance_class": "industry_chain_relevant",
                "relevance_chain": {
                    "chain_id": "memory_capacity_to_cis_pricing",
                    "confidence": 0.82,
                    "hops": [
                        {"canonical_statement": "存储产品涨价", "evidence_type": "news_text"},
                        {"canonical_statement": "晶圆厂产能紧张", "evidence_type": "news_text"},
                        {"canonical_statement": "CIS排产变化", "evidence_type": "stock_config"},
                    ],
                },
            },
        ),
        SynthesisItem(
            title="泛行业新闻",
            content="半导体板块波动。",
            author="东方财富资讯",
            source_platform="行业资讯",
            url="http://news/sector",
            publish_time="2026-06-01",
            extra={
                "allowed_sections": ["4.1"],
                "relevance_class": "sector_background",
                "relevance_chain": {"chain_id": "sector_background", "confidence": 0.25, "hops": []},
            },
        ),
    ]

    manifest = build_industry_relevance_manifest(items)

    assert manifest["schema"] == "industry_relevance_manifest.v1"
    assert manifest["events_catalysts_chains"] == []
