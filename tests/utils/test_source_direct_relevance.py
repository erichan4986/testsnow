from scripts.utils.source_adapter import SynthesisItem
from scripts.utils.source_direct_relevance import classify_direct_relevance


def _item(title, content="", platform="行业资讯", extra=None):
    return SynthesisItem(
        title=title,
        content=content,
        author="测试来源",
        source_platform=platform,
        url="",
        publish_time="2026-07-02",
        extra=extra or {},
    )


def test_mlcc_sector_news_for_fudan_is_sector_background():
    stock_config = {
        "product_exposure_terms": ["FPGA", "MCU", "EEPROM"],
        "competitors": ["紫光国微"],
    }
    result = classify_direct_relevance(
        _item("AI服务器带动 MLCC 需求增长", "复旦微电主要产品不直接涉及 MLCC。"),
        stock_name="复旦微电",
        stock_config=stock_config,
    )

    assert result["canonical_relevance_class"] == "sector_background"
    assert result["allowed_canonical_sections"] == []
    assert result["blocked_reason"] == "sector_background_no_direct_exposure"


def test_fudan_direct_product_news_is_allowed_in_41_and_42():
    stock_config = {
        "product_exposure_terms": ["FPGA", "MCU", "EEPROM"],
        "competitors": ["紫光国微"],
    }
    result = classify_direct_relevance(
        _item("FPGA 行业研究报告", "高可靠 FPGA 需求仍需跟踪。"),
        stock_name="复旦微电",
        stock_config=stock_config,
    )

    assert result["canonical_relevance_class"] == "direct_product"
    assert result["allowed_canonical_sections"] == ["4.1", "4.2"]
    assert result["matched_terms"] == ["FPGA"]


def test_peer_material_is_allowed_as_direct_peer():
    stock_config = {
        "product_exposure_terms": ["FPGA"],
        "competitors": ["紫光国微", "安路科技"],
    }
    result = classify_direct_relevance(
        _item("紫光国微与安路科技竞争格局", "紫光国微盈利能力更强。"),
        stock_name="复旦微电",
        stock_config=stock_config,
    )

    assert result["canonical_relevance_class"] == "direct_peer"
    assert "4.2" in result["allowed_canonical_sections"]


def test_keywords_fallback_strips_generic_terms():
    stock_config = {
        "keywords": ["半导体", "芯片", "光模块", "CPO"],
        "competitors": [],
    }

    direct = classify_direct_relevance(
        _item("光模块行业研究报告", "800G 光模块需求增长。"),
        stock_name="中际旭创",
        stock_config=stock_config,
    )
    generic = classify_direct_relevance(
        _item("半导体行业周报", "半导体板块震荡。"),
        stock_name="中际旭创",
        stock_config=stock_config,
    )

    assert direct["canonical_relevance_class"] == "direct_product"
    assert direct["matched_terms"] == ["光模块"]
    assert generic["canonical_relevance_class"] == "sector_background"
