import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from unittest.mock import MagicMock, patch
from skill_pipeline import SkillContext
import report_skills.synthesis_skills as synthesis_skills_module
from report_skills.synthesis_skills import SynthesisSkill
from source_adapter import SynthesisItem

TEST_STOCK_CODES = {
    "复旦微电": "688385",
    "黑芝麻智能": "02533",
    "中简科技": "300777",
    "中际旭创": "300308",
    "圣邦股份": "300661",
    "韦尔股份": "603501",
    "测试股": "000001",
}
EMPTY_KNOWLEDGE_DIR = Path(__file__).resolve().parent / "_empty_knowledge"


def _with_stock_identity(payload):
    result = dict(payload)
    stock_name = str(result.get("stock_name") or "")
    if stock_name and "stock_codes" not in result:
        result["stock_codes"] = {stock_name: TEST_STOCK_CODES[stock_name]}
    result.setdefault("knowledge_base_dir", str(EMPTY_KNOWLEDGE_DIR))
    return result


def _test_context(payload):
    return SkillContext(input=_with_stock_identity(payload))


class FakeSynthesizer:
    def __init__(self):
        self.calls = []

    def synthesize(self, stock_name, all_data):
        self.calls.append((stock_name, all_data))
        return {
            "industry_logic": "行业逻辑来自雪球[^1]与研报[^2]。",
            "fundamentals": "业绩路径引用公告[^3]。",
            "valuation_debate": "估值存在分歧。",
            "funding_sentiment": "资金面谨慎。",
            "events_catalysts": "关注订单催化。",
            "core_facts": [
                {"fact_id": 1, "fact": "营收增长", "data": "来自公告", "confidence": "高"},
            ],
            "citations": {
                1: {"_placeholder": True, "ref_id": 1},
                2: {"_placeholder": True, "ref_id": 2},
                3: {"_placeholder": True, "ref_id": 3},
            },
        }


def test_synthesis_skill_disabled_claim_verification_does_not_call_builder():
    from unittest.mock import patch, MagicMock

    skill = SynthesisSkill(synthesizer=MagicMock())
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "stock_raw": {
            "technical": {"indicators": {"_resonance": {"composite_score": 7}}},
            "reports": [{"title": "研报", "content": "收入增长", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    with patch("report_skills.synthesis_skills.SynthesisSkill._build_claim_verification_context") as mock_build:
        skill.run(ctx)
        mock_build.assert_not_called()
    assert ctx.output.get("claim_verification_status") != "ok"


def test_synthesis_skill_passes_stock_config_to_synthesizer():
    fake = FakeSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    stock_config = {
        "product_exposure_terms": ["FPGA", "MCU"],
        "competitors": ["紫光国微"],
    }
    ctx = _test_context({
        "stock_name": "复旦微电",
        "stock_config": stock_config,
        "stock_raw": {
            "reports": [{"title": "FPGA 行业研究", "content": "高可靠 FPGA 需求", "institution": "测试证券"}],
            "announcements": [{"title": "一季报", "content": "营收增长", "date": "2026-04-30"}],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })

    skill.run(ctx)

    assert fake.calls
    _, all_data = fake.calls[0]
    assert all_data["stock_config"] == stock_config


def test_synthesis_skill_passes_formal_financial_fact_pack_to_synthesizer():
    fake = FakeSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    filing_core_facts = [
        {
            "fact": "营业收入",
            "data": "39.82亿元",
            "source_labels": ["2025年annual"],
            "evidence_type": "periodic_report_filing_fact",
        },
        {
            "fact": "归母净利润",
            "data": "2.32亿元",
            "source_labels": ["2025年annual"],
            "evidence_type": "periodic_report_filing_fact",
        },
    ]
    ctx = _test_context({
        "stock_name": "复旦微电",
        "periodic_report_filing_core_facts": filing_core_facts,
        "stock_raw": {
            "announcements": [{"title": "年报", "content": "公司披露年度报告", "date": "2026-04-30"}],
            "reports": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })

    skill.run(ctx)

    _, all_data = fake.calls[0]
    assert all_data["formal_financial_fact_pack"]["facts"][0]["metric"] == "营业收入"
    assert all_data["formal_financial_fact_pack"]["facts"][0]["value"] == "39.82亿元"
    assert all_data["formal_financial_fact_pack"]["facts"][1]["metric"] == "归母净利润"


def test_synthesis_skill_passes_formal_financial_explanation_pack_to_synthesizer():
    fake = FakeSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    explanation_pack = {
        "schema": "formal_financial_explanation_pack.v1",
        "rows": [
            {
                "topic": "revenue_change",
                "metric": "营业收入",
                "excerpt": "营业收入变动原因说明：主要系FPGA与MCU产品销售额增加所致。",
                "normalized_summary": "收入变化原因：主要系FPGA与MCU产品销售额增加所致。",
                "source_doc": "688385_2025_annual_jina.txt",
                "confidence": 0.85,
            }
        ],
    }
    ctx = _test_context({
        "stock_name": "复旦微电",
        "periodic_report_explanation_pack": explanation_pack,
        "stock_raw": {
            "announcements": [{"title": "年报", "content": "公司披露年度报告", "date": "2026-04-30"}],
            "reports": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })

    skill.run(ctx)

    _, all_data = fake.calls[0]
    assert all_data["formal_financial_explanation_pack"] is explanation_pack


def test_synthesis_skill_builds_fundflow_pack_and_keeps_raw_fundflow_items():
    fake = FakeSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _test_context({
        "stock_name": "复旦微电",
        "stock_raw": {
            "announcements": [{"title": "一季报", "content": "公司披露一季报", "date": "2026-04-30"}],
            "reports": [],
            "fundflow": [
                {"date": "2026-07-02", "main_in": "1200", "change_pct": "2.5"},
                {"date": "2026-07-01", "main_in": "-200", "change_pct": "-0.5"},
            ],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })

    skill.run(ctx)

    _, all_data = fake.calls[0]
    assert all_data["fundflow_material_pack"]["summary"]["main_net_total"] == 1000.0
    assert ctx.output["fundflow_material_pack"]["summary"]["signal"] == "inflow_with_price_up"
    assert any(item.source_platform == "资金流向" for item in all_data["items"])


def test_fundflow_pack_keeps_citable_fundflow_sources():
    fake = FakeSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _test_context({
        "stock_name": "复旦微电",
        "stock_raw": {
            "announcements": [{"title": "一季报", "content": "公司披露一季报", "date": "2026-04-30"}],
            "reports": [],
            "fundflow": [
                {"date": "2026-07-02", "main_in": "1200", "change_pct": "2.5"},
            ],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })

    skill.run(ctx)

    _, all_data = fake.calls[0]
    fundflow_items = [item for item in all_data["items"] if item.source_platform == "资金流向"]
    assert len(fundflow_items) >= 1
    # The raw fundflow row should be addressable by global source ids in the synthesizer.
    assert all_data["fundflow_material_pack"]["summary"]["signal"] == "inflow_with_price_up"


def test_synthesis_skill_replaces_financial_missing_contradiction_when_fact_pack_exists():
    class ContradictingSynthesizer(FakeSynthesizer):
        def synthesize(self, stock_name, all_data):
            self.calls.append((stock_name, all_data))
            return {
                "industry_logic": "产业逻辑。",
                "fundamentals": "当前已披露年报未提供营收、利润、毛利率等核心财务数据，需要等待半年报。",
                "valuation_debate": "估值分歧。",
                "funding_sentiment": "资金面。",
                "events_catalysts": "催化剂。",
                "core_facts": [],
                "citations": {},
            }

    fake = ContradictingSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    filing_core_facts = [
        {
            "fact": "营业收入",
            "data": "39.82亿元",
            "source_labels": ["2025年annual"],
            "evidence_type": "periodic_report_filing_fact",
        },
        {
            "fact": "归母净利润",
            "data": "2.32亿元",
            "source_labels": ["2025年annual"],
            "evidence_type": "periodic_report_filing_fact",
        },
    ]
    ctx = _test_context({
        "stock_name": "复旦微电",
        "periodic_report_filing_core_facts": filing_core_facts,
        "stock_raw": {
            "announcements": [{"title": "年报", "content": "公司披露年度报告", "date": "2026-04-30"}],
            "reports": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })

    skill.run(ctx)

    fundamentals = ctx.get("synthesis")["fundamentals"]
    assert "未提供营收、利润" not in fundamentals
    assert "营业收入39.82亿元" in fundamentals
    assert "归母净利润2.32亿元" in fundamentals
    assert "订单、客户、费用率或指引" in fundamentals


def test_formal_financial_fact_pack_drops_zero_amounts_and_sanitizer_uses_core_facts():
    class ContradictingSynthesizer(FakeSynthesizer):
        def synthesize(self, stock_name, all_data):
            self.calls.append((stock_name, all_data))
            return {
                "industry_logic": "产业逻辑。",
                "fundamentals": "当前公告未提供营收、利润数据，需要等待半年报。",
                "valuation_debate": "估值分歧。",
                "funding_sentiment": "资金面。",
                "events_catalysts": "催化剂。",
                "core_facts": [
                    {
                        "fact": "2025年营收",
                        "data": "36.93亿元，同比增长2.87%",
                        "confidence": "高",
                        "provenance_status": "supported",
                    },
                    {
                        "fact": "2025年归母净利润",
                        "data": "2.32亿元，同比下降59.42%",
                        "confidence": "高",
                        "provenance_status": "supported",
                    },
                ],
                "citations": {},
            }

    fake = ContradictingSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    filing_core_facts = [
        {
            "fact": "营业收入",
            "data": "0.00亿元",
            "source_labels": ["2025年annual"],
            "evidence_type": "periodic_report_filing_fact",
        },
        {
            "fact": "归母净利润",
            "data": "0.00亿元",
            "source_labels": ["2025年annual"],
            "evidence_type": "periodic_report_filing_fact",
        },
    ]
    ctx = _test_context({
        "stock_name": "复旦微电",
        "periodic_report_filing_core_facts": filing_core_facts,
        "stock_raw": {
            "announcements": [{"title": "年报", "content": "公司披露年度报告", "date": "2026-04-30"}],
            "reports": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })

    skill.run(ctx)

    _, all_data = fake.calls[0]
    assert "formal_financial_fact_pack" not in all_data
    fundamentals = ctx.get("synthesis")["fundamentals"]
    assert "未提供营收、利润" not in fundamentals
    assert "2025年营收36.93亿元" in fundamentals
    assert "2025年归母净利润2.32亿元" in fundamentals
    assert "0.00亿元" not in fundamentals


def test_synthesis_skill_removes_indirect_industry_citations_from_43_sections():
    result = {
        "industry_logic": "行业背景可保留存储价格信息[^10]。",
        "fundamentals": "业绩分析可保留公司数据。",
        "valuation_debate": "估值分析。",
        "funding_sentiment": (
            "| 资金变量 | 当前证据 | 含义 |\n"
            "|---|---|---|\n"
            "| 市场情绪 | 北京君正存储涨价进入超级周期[^10] | 可能传导至公司业绩 |\n"
            "| 机构持仓 | 复旦微电一季报披露[^2] | 关注调仓 |\n"
        ),
        "events_catalysts": (
            "* **AI基础设施需求**：内存价格进入超级周期[^10]，需验证是否传导至公司。\n"
            "* **公司季报**：复旦微电一季报已披露[^2]。\n"
        ),
        "citations": {
            2: {"source": "公告", "title": "2026年第一季度报告"},
            10: {"source": "行业资讯", "title": "北京君正：由于公司存储芯片持续在涨价"},
        },
    }

    sanitized = SynthesisSkill._sanitize_indirect_industry_citations_from_43(result, "复旦微电")

    assert "北京君正" not in sanitized["funding_sentiment"]
    assert "超级周期" not in sanitized["events_catalysts"]
    assert "传导至公司" not in sanitized["events_catalysts"]
    assert "复旦微电一季报" in sanitized["funding_sentiment"]
    assert "复旦微电一季报" in sanitized["events_catalysts"]
    assert "存储价格信息[^10]" in sanitized["industry_logic"]


def test_default_base_dir_resolves_to_repo_root_knowledge():
    """When claim_verification_base_dir is not provided, default resolves to repo root knowledge/."""
    from types import SimpleNamespace
    from unittest.mock import patch
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    expected = str(repo_root / "knowledge")

    captured = {}

    skill = SynthesisSkill(synthesizer=MagicMock())
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "enable_claim_verification_context": True,
        "stock_raw": {
            "reports": [{"title": "研报", "content": "收入增长", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })

    def fake_builder(stock_name, base_dir, dry_run=True):
        captured["base_dir"] = base_dir
        return SimpleNamespace(
            stock=stock_name,
            high_credit_claims=[],
            low_credit_claims=[],
            verifications=[],
            skipped_files=[],
        )

    def fake_summary(plan, **kwargs):
        return {
            "enabled": True,
            "counts": {
                "high_credit_claims": 0,
                "low_credit_claims": 0,
                "verified": 0,
                "supported": 0,
                "unverified": 0,
                "needs_review": 0,
            },
            "verified_claims": [],
            "supported_claims": [],
            "unverified_claims": [],
        }

    with patch("claim_verification.build_claim_verification_plan", fake_builder), \
         patch("claim_verification.summarize_claim_verification_plan", fake_summary):
        skill.run(ctx)

    assert captured["base_dir"] == expected
    assert ctx.output.get("claim_verification_status") == "empty"


def test_synthesis_skill_enabled_modern_path_passes_context_to_synthesizer(tmp_path):
    from unittest.mock import MagicMock

    fake = FakeSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _test_context({
        "stock_name": "黑芝麻智能",
        "enable_claim_verification_context": True,
        "claim_verification_base_dir": str(tmp_path / "empty_kb"),
        "claim_verification_max_verified": 6,
        "claim_verification_max_supported": 4,
        "claim_verification_max_unverified": 4,
        "stock_raw": {
            "reports": [{"title": "研报", "content": "内容", "institution": "测试证券"}],
            "announcements": [{"title": "公告", "content": "内容", "date": "2026-06-01"}],
            "fundflow": [{"date": "2026-06-01", "main_inflow": 100, "main_outflow": 50}],
            "news": [{"title": "新闻", "content": "内容", "date": "2026-06-01"}],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    result = skill.run(ctx)
    assert fake.calls
    stock_name, all_data = fake.calls[0]
    assert stock_name == "黑芝麻智能"
    # Empty knowledge for 黑芝麻智能 means no usable context, so the feature does not pass context.
    assert ctx.output.get("claim_verification_status") == "empty"
    assert "claim_verification_context" not in all_data


def test_synthesis_result_carries_industry_relevance_manifest():
    fake = FakeSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    chain_item = SynthesisItem(
        title="存储产品涨价带动晶圆厂产能紧张",
        content="CIS 排产变化仍需跟踪。",
        author="东方财富资讯",
        source_platform="行业资讯",
        url="http://news/chain",
        publish_time="2026-06-01",
        extra={
            "source_type": "mainstream_media",
            "verification_status": "secondary_source",
            "report_eligible": True,
            "allowed_sections": ["4.1", "4.3"],
            "relevance_class": "industry_chain_relevant",
            "relevance_chain": {
                "chain_id": "memory_capacity_to_cis_pricing",
                "confidence": 0.82,
                "hops": [
                    {"canonical_statement": "存储产品涨价", "evidence_type": "news_text"},
                    {"canonical_statement": "晶圆厂产能紧张", "evidence_type": "news_text"},
                    {"canonical_statement": "CIS排产变化", "evidence_type": "stock_config"},
                    {"canonical_statement": "待验证变量", "evidence_type": "stock_config"},
                ],
            },
        },
    )

    result = skill._synthesize("韦尔股份", {}, [], extra_items=[chain_item])

    manifest = result["_industry_relevance_manifest"]
    assert manifest["schema"] == "industry_relevance_manifest.v1"
    assert manifest["events_catalysts_chains"][0]["chain_id"] == "memory_capacity_to_cis_pricing"
    assert "待验证变量" in manifest["events_catalysts_chains"][0]["allowed_terms"]


def test_synthesis_skill_exposes_industry_relevance_manifest_on_context():
    class ChainSynthesizer(FakeSynthesizer):
        pass

    skill = SynthesisSkill(synthesizer=ChainSynthesizer())
    chain_item = SynthesisItem(
        title="存储产品涨价带动晶圆厂产能紧张",
        content="CIS 排产变化仍需跟踪。",
        author="东方财富资讯",
        source_platform="行业资讯",
        url="http://news/chain",
        publish_time="2026-06-01",
        extra={
            "source_type": "mainstream_media",
            "verification_status": "secondary_source",
            "report_eligible": True,
            "allowed_sections": ["4.1", "4.3"],
            "relevance_class": "industry_chain_relevant",
            "relevance_chain": {
                "chain_id": "memory_capacity_to_cis_pricing",
                "confidence": 0.82,
                "hops": [
                    {"canonical_statement": "存储产品涨价", "evidence_type": "news_text"},
                    {"canonical_statement": "晶圆厂产能紧张", "evidence_type": "news_text"},
                    {"canonical_statement": "CIS排产变化", "evidence_type": "stock_config"},
                    {"canonical_statement": "待验证变量", "evidence_type": "stock_config"},
                ],
            },
        },
    )
    ctx = SkillContext(input={
        "stock_name": "韦尔股份",
        "stock_raw": {},
        "keep_posts": [],
        "external_evidence_keep_items": [chain_item],
    })

    skill.run(ctx)

    manifest = ctx.output["industry_relevance_manifest"]
    assert manifest["events_catalysts_chains"][0]["chain_id"] == "memory_capacity_to_cis_pricing"


def test_periodic_report_excerpt_does_not_enter_synthesis_items():
    fake = FakeSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    periodic_excerpt = SynthesisItem(
        title="2025年年度报告 | 管理层观点",
        content="管理层讨论与分析摘录。",
        author="",
        source_platform="定期报告摘录",
        url="http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225000000",
        publish_time="2026-04-15",
        extra={
            "source_type": "periodic_report_excerpt",
            "source_credit": 75,
            "verification_status": "management_view",
        },
    )
    ctx = _test_context({
        "stock_name": "中简科技",
        "source_intake_enabled": True,
        "source_intake_items": [periodic_excerpt],
        "external_evidence_keep_items": [periodic_excerpt],
        "stock_raw": {
            "reports": [{"title": "研报", "content": "中简科技研发投入增加", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })

    skill.run(ctx)

    assert fake.calls
    _, all_data = fake.calls[0]
    assert all(item.extra.get("source_type") != "periodic_report_excerpt" for item in all_data["items"])
    assert all(item.source_platform != "定期报告摘录" for item in all_data["items"])


def test_source_intake_keep_items_enter_baseline_synthesis_items():
    fake = FakeSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    source_intake_item = SynthesisItem(
        title="中际旭创深度研报",
        content="光模块需求延续高景气，800G 与 1.6T 产品交付节奏是业绩弹性的核心变量。",
        author="测试证券",
        source_platform="研报",
        url="https://example.com/report",
        publish_time="2026-06-01",
        extra={
            "source_type": "broker_research",
            "source_credit": 80,
            "verification_status": "professional_analysis",
            "knowledge_eligible": True,
            "report_eligible": True,
        },
    )
    ctx = _test_context({
        "stock_name": "中际旭创",
        "source_intake_enabled": True,
        "external_evidence_keep_items": [source_intake_item],
        "stock_raw": {
            "reports": [],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })

    skill.run(ctx)

    assert fake.calls
    _, all_data = fake.calls[0]
    assert [item.title for item in all_data["items"]] == ["中际旭创深度研报"]


def test_formal_first_source_policy_excludes_social_from_canonical_synthesis():
    fake = FakeSynthesizer()
    skill = SynthesisSkill(synthesizer=fake, canonical_synthesis_source_policy="formal_first")
    source_intake_item = SynthesisItem(
        title="正式外部研报",
        content="800G 和 1.6T 交付节奏来自正式研报。",
        author="测试证券",
        source_platform="研报",
        url="https://example.com/report",
        publish_time="2026-06-01",
        extra={
            "source_type": "broker_research",
            "source_credit": 80,
            "verification_status": "professional_analysis",
            "knowledge_eligible": True,
            "report_eligible": True,
        },
    )
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "external_evidence_keep_items": [source_intake_item],
        "stock_raw": {
            "reports": [{"title": "券商研报", "content": "正式研报内容", "institution": "测试证券"}],
            "announcements": [{"title": "公司公告", "content": "正式公告内容", "date": "2026-06-01"}],
            "fundflow": [],
            "news": [{"title": "主流新闻", "content": "新闻内容", "date": "2026-06-01", "source": "财联社"}],
            "zhihu": {
                "report_items": [
                    {
                        "title": "知乎深度帖",
                        "content": "知乎观点内容",
                        "author_name": "知乎作者",
                        "url": "https://zhihu.com/question/1",
                    }
                ]
            },
        },
        "keep_posts": [{"title": "雪球帖", "content": "雪球观点内容", "source": "雪球"}],
    })

    skill.run(ctx)

    assert fake.calls
    _, all_data = fake.calls[0]
    platforms = [item.source_platform for item in all_data["items"]]
    titles = [item.title for item in all_data["items"]]
    assert "雪球" not in platforms
    assert "知乎" not in platforms
    assert "券商研报" in titles
    assert "公司公告" in titles
    assert "主流新闻" in titles
    assert "正式外部研报" in titles


def test_formal_first_with_only_social_sources_marks_formal_sources_insufficient():
    fake = FakeSynthesizer()
    skill = SynthesisSkill(synthesizer=fake, canonical_synthesis_source_policy="formal_first")
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "stock_raw": {
            "reports": [],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {
                "report_items": [
                    {
                        "title": "知乎深度帖",
                        "content": "知乎观点内容",
                        "author_name": "知乎作者",
                        "url": "https://zhihu.com/question/1",
                    }
                ]
            },
        },
        "keep_posts": [{"title": "雪球帖", "content": "雪球观点内容", "source": "雪球"}],
    })

    skill.run(ctx)

    assert not fake.calls
    synthesis = ctx.output["synthesis"]
    text = "\n".join(str(synthesis.get(key, "")) for key in (
        "industry_logic",
        "fundamentals",
        "valuation_debate",
    ))
    assert synthesis["_source_policy"] == "formal_first"
    assert synthesis["_formal_first_sources_insufficient"] is True
    assert "正式材料不足" in text
    assert "非正式材料" in text
    assert "雪球" not in text
    assert "知乎" not in text
    assert "微信" not in text


def test_formal_first_extra_items_keep_formal_display_and_reject_social_display():
    skill = SynthesisSkill(canonical_synthesis_source_policy="formal_first")
    ctx = SkillContext(input={"canonical_synthesis_source_policy": "formal_first"})
    formal_display = SynthesisItem(
        title="年报叙事卡片",
        content="年报管理层讨论摘要。",
        author="公司年报",
        source_platform="定期报告叙事卡片",
        url="",
        publish_time="2026",
        extra={
            "source_type": "periodic_report_narrative_evidence",
            "synthesis_display_only": True,
            "verification_status": "professional_analysis",
        },
    )
    social_display = SynthesisItem(
        title="知乎精选观察",
        content="知乎观点原文。",
        author="知乎作者",
        source_platform="知乎精选观察",
        url="https://zhihu.com/question/1",
        publish_time="2026-06-30",
        extra={
            "source_type": "social_viewpoint_analysis_evidence",
            "synthesis_display_only": True,
            "verification_status": "professional_observation",
        },
    )

    items = skill._build_synthesis_items(
        {"reports": [], "announcements": [], "fundflow": [], "news": [], "zhihu": {"report_items": []}},
        [],
        ctx=ctx,
        extra_items=[formal_display, social_display],
    )

    assert formal_display in items
    assert social_display not in items


def test_empty_synthesizer_result_falls_back_to_template_without_crashing():
    class EmptySynthesizer:
        def __init__(self):
            self.calls = []

        def synthesize(self, stock_name, all_data):
            self.calls.append((stock_name, all_data))
            return {}

    fake = EmptySynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "stock_raw": {
            "reports": [{"title": "券商研报", "content": "正式研报内容", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })

    skill.run(ctx)

    assert fake.calls
    synthesis = ctx.output["synthesis"]
    assert synthesis["_items_count"] == 1
    assert "基本面 LLM 合成未启用或未产生有效输出" in synthesis["fundamentals"]


def test_legacy_mixed_source_policy_keeps_social_sources_by_default():
    fake = FakeSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "stock_raw": {
            "reports": [],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {
                "report_items": [
                    {
                        "title": "知乎深度帖",
                        "content": "知乎观点内容",
                        "author_name": "知乎作者",
                        "url": "https://zhihu.com/question/1",
                    }
                ]
            },
        },
        "keep_posts": [{"title": "雪球帖", "content": "雪球观点内容", "source": "雪球"}],
    })

    skill.run(ctx)

    _, all_data = fake.calls[0]
    platforms = [item.source_platform for item in all_data["items"]]
    assert "雪球" in platforms
    assert "知乎" in platforms


def test_periodic_report_fulltext_items_do_not_enter_synthesis_items():
    fake = FakeSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    fulltext_item = SynthesisItem(
        title="2025年年度报告 | 定期报告全文摘要（实验路径）",
        content="这段全文摘要不应进入默认 synthesis items。",
        author="",
        source_platform="定期报告全文",
        url="http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225000000",
        publish_time="2026-04-15",
        extra={
            "source_type": "periodic_report_fulltext_analysis",
            "source_credit": 75,
            "verification_status": "professional_analysis",
            "claim_status": "professional_analysis",
            "knowledge_eligible": False,
            "report_eligible": False,
            "experimental": True,
        },
    )
    ctx = _test_context({
        "stock_name": "中简科技",
        "periodic_report_fulltext_items": [fulltext_item],
        "stock_raw": {
            "reports": [{"title": "研报", "content": "中简科技研发投入增加", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })

    skill.run(ctx)

    assert fake.calls
    _, all_data = fake.calls[0]
    assert all(
        item.extra.get("source_type") != "periodic_report_fulltext_analysis"
        for item in all_data["items"]
    )
    assert all(item.source_platform != "定期报告全文" for item in all_data["items"])


def test_synthesis_skill_error_in_context_build_falls_back_to_normal():
    from unittest.mock import patch, MagicMock

    fake = MagicMock()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "enable_claim_verification_context": True,
        "claim_verification_base_dir": "/nonexistent/kb",
        "stock_raw": {
            "reports": [{"title": "研报", "content": "收入增长", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    with patch("report_skills.synthesis_skills.SynthesisSkill._build_claim_verification_context", side_effect=RuntimeError("boom")):
        result = skill.run(ctx)
    assert ctx.output.get("claim_verification_status") == "error"
    assert "boom" in str(ctx.output.get("claim_verification_error", ""))
    # normal synthesis still produced something
    assert result.get("synthesis") is not None


def test_synthesis_skill_legacy_chat_path_includes_appendix():
    from unittest.mock import MagicMock, patch

    class ChatClient:
        def chat(self, prompt):
            self.last_prompt = prompt
            return {
                "industry_logic": "行业逻辑",
                "fundamentals": "基本面",
                "valuation_debate": "估值多空",
                "funding_sentiment": "资金情绪",
                "events_catalysts": "事件催化",
                "core_facts": [],
                "citations": {},
            }

    client = ChatClient()
    skill = SynthesisSkill(llm_client=client)
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "enable_claim_verification_context": True,
        "claim_verification_base_dir": "knowledge",
        "stock_raw": {
            "technical": {"indicators": {"_resonance": {"composite_score": 7}}},
            "reports": [{"title": "测试研报", "content": "测试内容", "institution": "测试证券"}],
            "announcements": [{"title": "测试公告", "content": "测试内容", "date": "2026-06-01"}],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    with patch("report_skills.synthesis_skills.SynthesisSkill._build_claim_verification_context") as mock_build:
        mock_build.return_value = (
            "ok",
            {
                "enabled": True,
                "stock": "测试股",
                "counts": {"verified": 0, "supported": 0, "unverified": 1, "needs_review": 0, "high_credit_claims": 0, "low_credit_claims": 1, "skipped_files": 0},
                "verified_claims": [],
                "supported_claims": [],
                "unverified_claims": [{"claim_text": "社区讨论", "action": "unverified", "reason": "no match"}],
            },
            "",
        )
        skill.run(ctx)

    assert "Claim Verification Context" in client.last_prompt
    assert "不是新的引用来源" in client.last_prompt
    assert ctx.output.get("claim_verification_status") == "ok"


# --- core fact provenance enrichment tests ---

def _build_result_for_provenance(core_facts, citations):
    """Build a minimal synthesis result dict for provenance enrichment tests."""
    return {
        "industry_logic": "行业逻辑",
        "core_facts": core_facts,
        "citations": citations,
    }


def test_enrich_supported_fact_int_citations():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1, 2]}],
        citations={
            1: {"source": "公告"},
            2: {"source": "官方"},
        },
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert fact["source_labels"] == ["公告", "官方"]
    assert fact["evidence_type"] == "mixed"
    assert fact["provenance_status"] == "supported"


def test_enrich_supported_fact_string_keyed_citations():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": ["1"]}],
        citations={"1": {"source": "公告"}},
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert fact["source_labels"] == ["公告"]
    assert fact["evidence_type"] == "announcement"
    assert fact["provenance_status"] == "supported"


def test_enrich_missing_ref():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": []}],
        citations={1: {"source": "雪球"}},
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert fact["source_labels"] == []
    assert fact["evidence_type"] == "unknown"
    assert fact["provenance_status"] == "missing_ref"


def test_enrich_peer_comparison_facts_use_structured_metric_label():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[
            {
                "fact_id": 8,
                "fact": "PE(TTM)对比新易盛",
                "data": "高于新易盛17.9倍（新易盛PE(TTM)为66.32）",
                "confidence": "中",
                "source_refs": [],
            },
            {
                "fact_id": 9,
                "fact": "产品订单增长",
                "data": "订单增长较快",
                "confidence": "中",
                "source_refs": [],
            },
        ],
        citations={},
    )
    peer_material = {
        "schema": "peer_comparison_material.v1",
        "rows": [
            {
                "peer": "新易盛",
                "metric": "pe_ttm",
                "comparison": "PE(TTM)高于新易盛17.9倍",
                "source_refs": ["指标:competitor_metrics"],
                "usage": "claim_eligible",
            },
        ],
    }

    enriched = skill._enrich_core_fact_provenance(result)
    enriched = skill._enrich_peer_comparison_fact_provenance(enriched, peer_material)

    peer_fact = enriched["core_facts"][0]
    ordinary_fact = enriched["core_facts"][1]
    assert peer_fact["source_labels"] == ["结构化同行估值数据"]
    assert peer_fact["evidence_type"] == "peer_comparison_metric"
    assert peer_fact["provenance_status"] == "supported"
    assert ordinary_fact["source_labels"] == []
    assert ordinary_fact["evidence_type"] == "unknown"
    assert ordinary_fact["provenance_status"] == "missing_ref"


def test_enrich_invalid_ref():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [99]}],
        citations={1: {"source": "雪球"}},
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert fact["source_labels"] == []
    assert fact["evidence_type"] == "unknown"
    assert fact["provenance_status"] == "invalid_ref"


def test_enrich_partially_supported_ref():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1, 99]}],
        citations={1: {"source": "公告"}},
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert fact["source_labels"] == ["公告"]
    assert fact["evidence_type"] == "announcement"
    assert fact["provenance_status"] == "partially_supported"


def test_enrich_normalizes_zhihu_family():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1]}],
        citations={1: {"source": "知乎全网(网易)"}},
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert fact["source_labels"] == []
    assert fact["evidence_type"] == "unknown"
    assert fact["provenance_status"] == "invalid_ref"


def test_enrich_community_sources_map_to_invalid_ref():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1]}],
        citations={1: {"source": "xueqiu"}},
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert fact["source_labels"] == []
    assert fact["evidence_type"] == "unknown"
    assert fact["provenance_status"] == "invalid_ref"


def test_enrich_excludes_agent_reach_from_support():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1]}],
        citations={1: {"source": "AgentReach(web)"}},
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert fact["source_labels"] == []
    assert fact["evidence_type"] == "unknown"
    assert fact["provenance_status"] == "invalid_ref"


def test_enrich_partially_supported_when_agent_reach_mixed():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1, 2]}],
        citations={1: {"source": "公告"}, 2: {"source": "AgentReach(web)"}},
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert fact["source_labels"] == ["公告"]
    assert fact["evidence_type"] == "announcement"
    assert fact["provenance_status"] == "partially_supported"


def test_enrich_caps_source_labels_at_two():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1, 2, 3]}],
        citations={
            1: {"source": "公告"},
            2: {"source": "官方"},
            3: {"source": "交易所"},
        },
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert len(fact["source_labels"]) == 2
    assert all(label in {"公告", "官方", "交易所"} for label in fact["source_labels"])


def test_enrich_still_marks_partial_when_invalid_ref_after_label_cap():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1, 2, 99]}],
        citations={
            1: {"source": "公告"},
            2: {"source": "官方"},
        },
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert fact["source_labels"] == ["公告", "官方"]
    assert fact["evidence_type"] == "mixed"
    assert fact["provenance_status"] == "partially_supported"


def test_enrich_drops_non_integer_refs():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1.8, True, "2"]}],
        citations={
            1: {"source": "雪球"},
            2: {"source": "公告"},
        },
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert fact["source_labels"] == ["公告"]
    assert fact["evidence_type"] == "announcement"
    assert fact["provenance_status"] == "supported"


def test_enrich_preserves_old_facts_without_source_refs():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高"}],
        citations={1: {"source": "雪球"}},
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert fact["source_labels"] == []
    assert fact["evidence_type"] == "unknown"
    assert fact["provenance_status"] == "missing_ref"


def test_enrich_preserves_fact_order():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[
            {"fact_id": 1, "fact": "a", "data": "", "confidence": "高", "source_refs": [1]},
            {"fact_id": 2, "fact": "b", "data": "", "confidence": "中", "source_refs": []},
        ],
        citations={1: {"source": "公告"}},
    )
    enriched = skill._enrich_core_fact_provenance(result)
    assert [f["fact_id"] for f in enriched["core_facts"]] == [1, 2]


def test_enrich_does_not_mutate_citations():
    skill = SynthesisSkill()
    citations = {1: {"source": "雪球"}}
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1]}],
        citations=citations,
    )
    skill._enrich_core_fact_provenance(result)
    assert citations == {1: {"source": "雪球"}}


def test_enrich_news_evidence_type_rejected():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1]}],
        citations={1: {"source": "news"}},
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert fact["source_labels"] == []
    assert fact["evidence_type"] == "unknown"
    assert fact["provenance_status"] == "invalid_ref"


def test_enrich_fundflow_evidence_type_rejected():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1]}],
        citations={1: {"source": "资金流向"}},
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert fact["source_labels"] == []
    assert fact["evidence_type"] == "unknown"
    assert fact["provenance_status"] == "invalid_ref"


def test_synthesis_skill_empty_context_sets_empty_status():
    from unittest.mock import MagicMock, patch

    fake = FakeSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "enable_claim_verification_context": True,
        "claim_verification_base_dir": "knowledge",
        "stock_raw": {
            "reports": [{"title": "研报", "content": "内容", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    with patch("report_skills.synthesis_skills.SynthesisSkill._build_claim_verification_context") as mock_build:
        mock_build.return_value = ("empty", None, "")
        skill.run(ctx)

    assert ctx.output.get("claim_verification_status") == "empty"
    stock_name, all_data = fake.calls[0]
    assert "claim_verification_context" not in all_data or not all_data["claim_verification_context"]


def test_synthesis_skill_basic():
    mock_llm = MagicMock()
    mock_llm.chat.return_value = {
        "industry_logic": "行业逻辑",
        "fundamentals": "基本面",
        "valuation_debate": "估值多空",
        "funding_sentiment": "资金情绪",
        "events_catalysts": "事件催化",
    }

    skill = SynthesisSkill(llm_client=mock_llm)
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "stock_raw": {
            "technical": {"indicators": {"_resonance": {"composite_score": 7}}},
            "reports": [],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    result = skill.run(ctx)
    synthesis = result.get("synthesis")
    assert synthesis is not None
    assert "industry_logic" in synthesis


def test_synthesis_skill_uses_source_adapter_and_knowledge_synthesizer():
    fake = FakeSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "stock_raw": {
            "reports": [{
                "title": "测试股深度报告",
                "institution": "测试证券",
                "content": "收入增长40%",
                "publish_date": "2026-06-01",
                "url": "https://example.com/report",
            }],
            "announcements": [{
                "title": "一季报公告",
                "content": "归母净利润增长20%",
                "date": "2026-04-30",
                "url": "https://example.com/ann",
            }],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [{
            "title": "社区分析",
            "content": "订单改善，因为客户导入加速。",
            "author": "雪球作者",
            "url": "https://xueqiu.com/test",
            "time": "2026-06-02",
            "like_count": 20,
            "comment_count": 5,
        }],
    })

    result = skill.run(ctx)
    synthesis = result.get("synthesis")
    items = fake.calls[0][1]["items"]

    assert len(items) == 3
    assert result.get("synthesis_items_count") == 3
    assert result.get("core_facts")[0]["fact"] == "营收增长"
    assert "行业逻辑来自雪球" in result.get("synthesis_text")
    assert synthesis["citations"][1]["source"] == "雪球"
    assert synthesis["citations"][2]["source"] == "研报"
    assert synthesis["citations"][3]["source"] == "公告"
    assert "雪球" in result.get("synthesis_sources")
    assert "研报" in result.get("synthesis_sources")


def test_synthesis_skill_template_is_explicit_when_no_llm_output():
    skill = SynthesisSkill(synthesizer=MagicMock(synthesize=MagicMock(return_value={
        "industry_logic": "",
        "fundamentals": "",
        "valuation_debate": "",
        "funding_sentiment": "",
        "events_catalysts": "",
        "core_facts": [],
        "citations": {},
    })))
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "stock_raw": {
            "technical": {"indicators": {"_resonance": {"composite_score": 4}}},
            "reports": [{"title": "研报", "content": "收入增长", "institution": "测试证券"}],
        },
        "keep_posts": [],
    })

    result = skill.run(ctx)
    synthesis = result.get("synthesis")

    assert "未启用或未产生有效输出" in synthesis["fundamentals"]
    assert result.get("core_facts") == []
    assert result.get("synthesis_items_count") == 1


# --- Credit-aware provenance hard-filter tests ---

def test_enrich_provenance_accepts_announcement():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1]}],
        citations={1: {"source": "公告"}},
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert fact["source_labels"] == ["公告"]
    assert fact["evidence_type"] == "announcement"
    assert fact["provenance_status"] == "supported"


def test_enrich_provenance_accepts_high_credit_metadata():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1]}],
        citations={1: {"source": "某来源", "source_credit": 90, "source_type": "exchange_announcement"}},
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert fact["source_labels"] == ["某来源"]
    assert fact["provenance_status"] == "supported"


def test_enrich_provenance_rejects_report_and_news_and_community():
    skill = SynthesisSkill()
    for source in ("研报", "新闻", "雪球", "知乎", "微信公众号", "AgentReach(web)", "资金流向"):
        result = _build_result_for_provenance(
            core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1]}],
            citations={1: {"source": source}},
        )
        enriched = skill._enrich_core_fact_provenance(result)
        fact = enriched["core_facts"][0]
        assert fact["source_labels"] == [], source
        assert fact["provenance_status"] == "invalid_ref", source


def test_enrich_provenance_mixed_announcement_and_report_is_partially_supported():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1, 2]}],
        citations={1: {"source": "公告"}, 2: {"source": "研报"}},
    )
    enriched = skill._enrich_core_fact_provenance(result)
    fact = enriched["core_facts"][0]
    assert fact["source_labels"] == ["公告"]
    assert fact["provenance_status"] == "partially_supported"

# --- curated external evidence card Phase 2 tests ---

import json as _json


def _normalized_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _write_viewpoint_digest_json(tmp_path, claims, status="ok", stock_name="测试股"):
    path = tmp_path / "viewpoint_digest.json"
    path.write_text(
        _json.dumps(
            {
                "schema_version": "curated_external_viewpoint_digest.v1",
                "status": status,
                "stock_name": stock_name,
                "claims": claims,
                "claims_count": len(claims),
                "stats": {
                    "theme_coverage_count": 1,
                    "theme_coverage_total": 7,
                    "theme_coverage_ratio": 1 / 7,
                    "covered_themes": ["800G_rumor"],
                    "missing_themes": [],
                },
                "wrote_knowledge": False,
                "connected_synthesis": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _write_viewpoint_narrative_json(tmp_path, paragraphs, citations, status="ok", stock_name="测试股"):
    path = tmp_path / "viewpoint_narrative.json"
    path.write_text(
        _json.dumps(
            {
                "schema_version": "curated_external_viewpoint_narrative.v1",
                "status": status,
                "stock_name": stock_name,
                "paragraphs": paragraphs,
                "paragraphs_count": len(paragraphs),
                "citations": citations,
                "stats": {"lint": {"ok": True, "violations": []}},
                "wrote_knowledge": False,
                "connected_synthesis": False,
                "connected_scoring": False,
                "connected_risk": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _make_viewpoint_narrative_paragraphs():
    return [
        {
            "heading": "供应链瓶颈与交付疑虑并存",
            "text": "外部材料提示供应链约束会影响交付弹性，需要和订单转化一起跟踪。",
            "claim_refs": ["vc1"],
            "citation_refs": [1],
        }
    ]


def _make_viewpoint_narrative_citations():
    return {
        "1": {
            "source": "微信公众号精选观察",
            "author": "测试账号",
            "title": "外部深度文章",
            "url": "https://mp.weixin.qq.com/s/viewpoint",
            "source_type": "curated_external_analysis_evidence",
            "source_credit": 55,
            "verification_status": "professional_observation",
            "claim_id": "vc1",
            "source_quote_hash": "hash",
        }
    }


def _make_viewpoint_claim(claim_id="vc1", claim_type="watch_variable", topic="supply_delivery_capacity"):
    quote = "外部文章提示800G交付计划下调传言仍需跟踪，公司曾否认相关情况。"
    return {
        "schema_version": "curated_external_viewpoint_claim.v1",
        "claim_id": claim_id,
        "stock_name": "测试股",
        "claim_type": claim_type,
        "topic": topic,
        "claim": "外部文章提示800G交付计划下调传言仍需跟踪。",
        "source_quote": quote,
        "source_quote_hash": _normalized_hash(quote),
        "why_incremental": "baseline未覆盖该交付传言变量。",
        "baseline_overlap": "none",
        "source_id": "curated-source:test:1",
        "source_ref": "https://example.com/viewpoint",
        "source_title": "中际旭创外部深度观点",
        "source_account": "测试公众号",
        "evidence_refs": ["curated-source:test:1"],
        "evidence_hashes": [
            {
                "source_id": "curated-source:test:1",
                "source_block_hash": "block-hash",
                "source_quote_hash": _normalized_hash(quote),
            }
        ],
        "verification_status": "professional_observation",
        "source_credit": 55,
        "claim_source_credit": 55,
        "quality_action": "preview_only",
        "knowledge_eligible": False,
        "synthesis_display_only": True,
        "scoring_eligible": False,
        "risk_score_eligible": False,
    }


def _make_viewpoint_claim_with_text(
    claim_id,
    claim,
    *,
    topic="supply_delivery_capacity",
    claim_type="watch_variable",
    title="外部深度观点",
):
    item = _make_viewpoint_claim(claim_id=claim_id, claim_type=claim_type, topic=topic)
    item["claim"] = claim
    item["source_quote"] = claim
    item["source_quote_hash"] = _normalized_hash(claim)
    item["source_title"] = title
    item["evidence_hashes"][0]["source_quote_hash"] = _normalized_hash(claim)
    return item


def test_legacy_curated_external_evidence_cards_flag_is_ignored():
    skill = SynthesisSkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "include_curated_external_evidence_cards_in_synthesis_display": True,
        "curated_external_evidence_cards_json": "/tmp/legacy_cards.json",
        "stock_raw": {
            "reports": [],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    skill.run(ctx)

    assert ctx.output.get("deep_analysis_display") is None
    assert ctx.output.get("curated_external_evidence_cards_status") is None
    assert ctx.output.get("synthesis_text_with_curated_external_evidence_cards") is None


def test_curated_external_viewpoint_digest_enabled_sets_deep_analysis_display(tmp_path):
    digest_path = _write_viewpoint_digest_json(tmp_path, [_make_viewpoint_claim()])

    skill = SynthesisSkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "include_curated_external_viewpoint_digest_in_deep_analysis_display": True,
        "curated_external_viewpoint_digest_json": str(digest_path),
        "stock_raw": {
            "reports": [],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    skill.run(ctx)

    display = ctx.output.get("deep_analysis_display")
    assert display
    assert ctx.output.get("curated_external_viewpoint_digest_status") == "ok"
    display_text = "\n".join(str(display.get(key, "")) for key in ("industry_logic", "fundamentals", "events_catalysts"))
    assert "800G交付计划下调传言" in display_text
    assert display["citations"][1]["source_type"] == "curated_external_analysis_evidence"
    assert display["citations"][1]["source"] == "微信公众号精选观察"
    assert display["_curated_external_taxonomy_version"] == "external_viewpoint.v1"
    assert "order_capacity_delivery" in display["_curated_external_topic_groups"]
    assert ctx.output.get("synthesis_display") is None
    assert "800G交付计划下调传言" not in ctx.output.get("synthesis_text", "")
    assert ctx.output.get("wrote_knowledge") is None


def test_curated_external_viewpoint_digest_rejects_mismatched_stock_identity(tmp_path):
    digest_path = _write_viewpoint_digest_json(
        tmp_path, [_make_viewpoint_claim()], stock_name="聚辰股份",
    )
    skill = SynthesisSkill()
    ctx = _test_context({
        "stock_name": "复旦微电",
        "include_curated_external_viewpoint_digest_in_deep_analysis_display": True,
        "curated_external_viewpoint_digest_json": str(digest_path),
        "stock_raw": {"reports": [], "announcements": [], "fundflow": [], "news": [], "zhihu": {"report_items": []}},
        "keep_posts": [],
    })

    skill.run(ctx)

    assert ctx.output.get("deep_analysis_display") is None
    assert ctx.output.get("curated_external_viewpoint_digest_status") == "stock_identity_mismatch"


def test_curated_external_viewpoint_digest_drops_foreign_only_target_claim(tmp_path):
    foreign = _make_viewpoint_claim_with_text(
        "foreign", "复旦微电子EEPROM业务已经进入客户供应链。",
        title="聚辰股份: EEPROM产品导入进展",
    )
    safe = _make_viewpoint_claim_with_text(
        "safe", "复旦微电子新产品认证节奏仍需验证。",
        title="复旦微电: 新产品认证观察",
    )
    digest_path = _write_viewpoint_digest_json(
        tmp_path, [foreign, safe], stock_name="复旦微电",
    )
    skill = SynthesisSkill()
    ctx = _test_context({
        "stock_name": "复旦微电",
        "include_curated_external_viewpoint_digest_in_deep_analysis_display": True,
        "curated_external_viewpoint_digest_json": str(digest_path),
        "stock_raw": {"reports": [], "announcements": [], "fundflow": [], "news": [], "zhihu": {"report_items": []}},
        "keep_posts": [],
    })

    skill.run(ctx)

    display = ctx.output["deep_analysis_display"]
    display_text = "\n".join(str(display.get(key) or "") for key in (
        "industry_logic", "fundamentals", "events_catalysts",
    ))
    assert "进入客户供应链" not in display_text
    assert "新产品认证节奏" in display_text
    assert len(display["citations"]) == 1


def test_curated_external_viewpoint_narrative_enabled_sets_deep_analysis_display(tmp_path):
    narrative_path = _write_viewpoint_narrative_json(
        tmp_path,
        _make_viewpoint_narrative_paragraphs(),
        _make_viewpoint_narrative_citations(),
    )

    skill = SynthesisSkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "include_curated_external_viewpoint_narrative_in_deep_analysis_display": True,
        "curated_external_viewpoint_narrative_json": str(narrative_path),
        "stock_raw": {
            "reports": [],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    skill.run(ctx)

    display = ctx.output.get("deep_analysis_display")
    assert display
    assert display["_curated_external_narrative"] is True
    assert display["_curated_external_narrative_paragraphs"][0]["heading"] == "供应链瓶颈与交付疑虑并存"
    assert display["citations"][1]["url"] == "https://mp.weixin.qq.com/s/viewpoint"
    assert ctx.output.get("curated_external_viewpoint_narrative_status") == "ok"
    assert ctx.output.get("synthesis_display") is None
    assert "供应链约束" not in ctx.output.get("synthesis_text", "")


def test_curated_external_viewpoint_narrative_hydrates_refs_from_claim_ids(tmp_path):
    narrative_path = _write_viewpoint_narrative_json(
        tmp_path,
        [
            {
                "heading": "估值分歧",
                "text": "外部材料提示A股估值处于乐观情景上沿，需跟踪盈利修复假设。",
                "claim_refs": ["fudan-xq-val-001"],
            }
        ],
        {
            "1": {
                "source": "雪球专栏观察",
                "author": "测试作者",
                "title": "复旦微电估值分析",
                "url": "https://xueqiu.com/1606930351/392467740",
                "source_type": "xueqiu_column_observation",
                "source_credit": 60,
                "verification_status": "professional_observation",
                "claim_id": "fudan-xq-val-001",
            }
        },
        stock_name="复旦微电",
    )

    skill = SynthesisSkill()
    ctx = _test_context({
        "stock_name": "复旦微电",
        "include_curated_external_viewpoint_narrative_in_deep_analysis_display": True,
        "curated_external_viewpoint_narrative_json": str(narrative_path),
        "stock_raw": {
            "reports": [],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    skill.run(ctx)

    display = ctx.output.get("deep_analysis_display")
    assert display
    assert display["citations"][1]["source"] == "雪球专栏观察"
    paragraph = display["_curated_external_narrative_paragraphs"][0]
    assert paragraph["citation_refs"] == [1]
    assert "盈利修复假设[^1]" in ctx.output.get("synthesis_text_with_curated_external_viewpoint_narrative", "")


def test_curated_external_viewpoint_narrative_preserves_reasoning_cards_and_truncates_excerpt(tmp_path):
    long_excerpt = "外部原文片段" * 60
    narrative_path = tmp_path / "viewpoint_narrative_cards.json"
    narrative_path.write_text(
        _json.dumps(
            {
                "schema_version": "curated_external_viewpoint_narrative.v1",
                "status": "ok",
                "stock_name": "复旦微电",
                "paragraphs": [
                    {
                        "heading": "估值分歧",
                        "text": "外部材料提示估值分歧。",
                        "claim_refs": ["fudan-xq-val-001"],
                    }
                ],
                "reasoning_cards": [
                    {
                        "claim_id": "fudan-xq-val-001",
                        "display_topic": "valuation_debate",
                        "claim": "外部观点认为A股估值处于乐观情景上沿",
                        "source_excerpt": long_excerpt,
                        "reasoning_steps": ["用紫光国微作盈利参照", "用2026净利和PE交叉验证"],
                        "numbers_used": ["375-420亿", "46-52元"],
                        "assumptions": ["2026净利修复到7.5亿"],
                        "counterpoints": ["军工订单恢复不及预期"],
                        "verification_need": "跟踪半年报和订单恢复",
                    }
                ],
                "citations": {
                    "1": {
                        "source": "雪球专栏观察",
                        "author": "测试作者",
                        "title": "复旦微电估值分析",
                        "url": "https://xueqiu.com/1606930351/392467740",
                        "source_type": "curated_external_analysis_evidence",
                        "source_credit": 60,
                        "verification_status": "professional_observation",
                        "claim_id": "fudan-xq-val-001",
                    }
                },
                "stats": {"lint": {"ok": True, "violations": []}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    skill = SynthesisSkill()
    ctx = _test_context({
        "stock_name": "复旦微电",
        "include_curated_external_viewpoint_narrative_in_deep_analysis_display": True,
        "curated_external_viewpoint_narrative_json": str(narrative_path),
        "stock_raw": {
            "reports": [],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    skill.run(ctx)

    display = ctx.output.get("deep_analysis_display")
    cards = display["_curated_external_reasoning_cards"]
    assert cards[0]["citation_refs"] == [1]
    assert len(cards[0]["source_excerpt"]) <= 201
    assert cards[0]["excerpt_truncated"] is True
    assert cards[0]["reasoning_steps"] == ["用紫光国微作盈利参照", "用2026净利和PE交叉验证"]


def test_curated_external_viewpoint_narrative_has_priority_over_digest(tmp_path):
    narrative_path = _write_viewpoint_narrative_json(
        tmp_path,
        _make_viewpoint_narrative_paragraphs(),
        _make_viewpoint_narrative_citations(),
    )
    digest_path = _write_viewpoint_digest_json(tmp_path, [_make_viewpoint_claim()])

    skill = SynthesisSkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "include_curated_external_viewpoint_narrative_in_deep_analysis_display": True,
        "curated_external_viewpoint_narrative_json": str(narrative_path),
        "include_curated_external_viewpoint_digest_in_deep_analysis_display": True,
        "curated_external_viewpoint_digest_json": str(digest_path),
        "stock_raw": {
            "reports": [],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    skill.run(ctx)

    assert ctx.output.get("deep_analysis_display", {}).get("_curated_external_narrative") is True
    assert ctx.output.get("curated_external_viewpoint_narrative_status") == "ok"


def test_curated_external_viewpoint_narrative_rejects_non_ok_status(tmp_path):
    narrative_path = _write_viewpoint_narrative_json(
        tmp_path,
        _make_viewpoint_narrative_paragraphs(),
        _make_viewpoint_narrative_citations(),
        status="lint_failed",
    )

    skill = SynthesisSkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "include_curated_external_viewpoint_narrative_in_deep_analysis_display": True,
        "curated_external_viewpoint_narrative_json": str(narrative_path),
        "stock_raw": {
            "reports": [],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    skill.run(ctx)

    assert ctx.output.get("deep_analysis_display") is None
    assert ctx.output.get("curated_external_viewpoint_narrative_status") == "lint_failed"


def test_curated_external_viewpoint_digest_rejects_non_ok_status(tmp_path):
    digest_path = _write_viewpoint_digest_json(tmp_path, [_make_viewpoint_claim()], status="theme_coverage_failed")

    skill = SynthesisSkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "include_curated_external_viewpoint_digest_in_deep_analysis_display": True,
        "curated_external_viewpoint_digest_json": str(digest_path),
        "stock_raw": {
            "reports": [],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    skill.run(ctx)

    assert ctx.output.get("deep_analysis_display") is None
    assert ctx.output.get("curated_external_viewpoint_digest_status") == "theme_coverage_failed"


def test_curated_external_viewpoint_digest_deduplicates_semantic_clusters(tmp_path):
    claims = [
        _make_viewpoint_claim_with_text(
            "vc1",
            "市场传言中际旭创因光芯片短缺将800G交付计划从1500万只下调至1200万只，公司虽已否认。",
            topic="800G交付计划下调传言",
            title="上游材料预付款暴涨10倍",
        ),
        _make_viewpoint_claim_with_text(
            "vc2",
            "市场传言光芯片短缺可能导致公司800G交付计划下调，公司否认但仍需跟踪。",
            topic="供应链风险",
            title="上游材料预付款暴涨10倍",
        ),
        _make_viewpoint_claim_with_text(
            "vc3",
            "外部文章指出中际旭创NPO方案预计2027年量产，XPO也有望同步量产。",
            topic="NPO/XPO新技术进展",
            claim_type="novel_mechanism",
            title="光模块行业延续高景气度",
        ),
        _make_viewpoint_claim_with_text(
            "vc4",
            "Scale Up场景中NPO方案因性能接近CPO且可维护性更好，有望成为主流。",
            topic="新增长逻辑",
            claim_type="novel_mechanism",
            title="ZIA Insight",
        ),
    ]
    digest_path = _write_viewpoint_digest_json(tmp_path, claims)

    skill = SynthesisSkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "include_curated_external_viewpoint_digest_in_deep_analysis_display": True,
        "curated_external_viewpoint_digest_json": str(digest_path),
        "stock_raw": {
            "reports": [],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    skill.run(ctx)

    display = ctx.output.get("deep_analysis_display")
    display_text = "\n".join(str(display.get(key, "")) for key in ("industry_logic", "fundamentals", "events_catalysts"))
    assert display_text.count("800G") == 1
    assert display_text.count("NPO") == 1
    assert display["_items_count"] == 2
    assert len(display["citations"]) == 2


def test_invalid_ref_core_fact_does_not_affect_output():
    skill = SynthesisSkill()
    result = _build_result_for_provenance(
        core_facts=[
            {"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1]},
            {"fact_id": 2, "fact": "公告事实", "data": "20%", "confidence": "高", "source_refs": [2]},
        ],
        citations={1: {"source": "雪球"}, 2: {"source": "公告"}},
    )
    enriched = skill._enrich_core_fact_provenance(result)
    facts = enriched["core_facts"]
    assert facts[0]["provenance_status"] == "invalid_ref"
    assert facts[1]["provenance_status"] == "supported"
    # invalid_ref is preserved but does not introduce new citations or scoring data.
    assert "invalid_ref" not in enriched.get("citations", {})


def test_legacy_chat_prompt_includes_credit_rules():
    from unittest.mock import MagicMock, patch

    class ChatClient:
        def chat(self, prompt):
            self.last_prompt = prompt
            return {
                "industry_logic": "行业逻辑",
                "fundamentals": "基本面",
                "valuation_debate": "估值多空",
                "funding_sentiment": "资金情绪",
                "events_catalysts": "事件催化",
                "core_facts": [],
                "citations": {},
            }

    client = ChatClient()
    skill = SynthesisSkill(llm_client=client)
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "enable_claim_verification_context": True,
        "claim_verification_base_dir": "knowledge",
        "stock_raw": {
            "technical": {"indicators": {"_resonance": {"composite_score": 7}}},
            "reports": [{"title": "测试研报", "content": "测试内容", "institution": "测试证券"}],
            "announcements": [{"title": "测试公告", "content": "测试内容", "date": "2026-06-01"}],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    with patch("report_skills.synthesis_skills.SynthesisSkill._build_claim_verification_context") as mock_build:
        mock_build.return_value = (
            "ok",
            {
                "enabled": True,
                "stock": "测试股",
                "counts": {"verified": 0, "supported": 0, "unverified": 1, "needs_review": 0, "high_credit_claims": 0, "low_credit_claims": 1, "skipped_files": 0},
                "verified_claims": [],
                "supported_claims": [],
                "unverified_claims": [{"claim_text": "社区讨论", "action": "unverified", "reason": "no match"}],
            },
            "",
        )
        skill.run(ctx)

    assert "证据信用与写法规则" in client.last_prompt
    assert "不得写成公司确认" in client.last_prompt
    assert "已验证讨论线索" in client.last_prompt
    assert "Phase 1 不使用 corroborated schema" in client.last_prompt


# --- periodic report fulltext as synthesis display material ---


def _make_fulltext_item():
    return SynthesisItem(
        title="2025年年度报告 | 定期报告全文摘要（实验路径）",
        content="管理层讨论：降价 毛利率承压 净流出 风险。",
        author="",
        source_platform="定期报告全文",
        url="",
        publish_time="2026-04-15",
        extra={
            "source_type": "periodic_report_fulltext_analysis",
            "source_credit": 75,
            "verification_status": "professional_analysis",
            "claim_status": "professional_analysis",
            "knowledge_eligible": False,
            "report_eligible": False,
            "experimental": True,
        },
    )


def test_synthesis_skill_reserves_freshness_refs_without_mutating_baseline_text():
    old_fulltext = _make_fulltext_item()
    old_fulltext.publish_time = "2026-01-01"
    display = {
        "_curated_external_narrative_paragraphs": [
            {
                "paragraph_index": 0,
                "text": "外部材料称客户订单节奏出现变化，需等待正式材料验证。",
                "topic_keys": ["order_customer"],
                "citation_refs": [1],
            }
        ],
        "citations": {
            "1": {
                "source": "微信公众号精选观察",
                "title": "订单观察",
                "url": "https://example.com/order",
                "date": "2026-07-01",
                "source_credit": 60,
                "synthesis_display_only": True,
                "scoring_eligible": False,
                "risk_score_eligible": False,
                "quality_action": "preview_only",
                "verification_status": "professional_observation",
            }
        },
    }
    ctx = SkillContext(input={
        "report_as_of_date": "2026-07-14",
        "periodic_report_fulltext_items": [old_fulltext],
        "broker_research_digest_items": [],
        "source_intake_items": [],
        "deep_analysis_evidence_profile": {"profile": "formal_medium"},
    })
    skill = SynthesisSkill()
    overlay = skill._build_evidence_freshness_overlay(
        ctx, ctx.get("deep_analysis_evidence_profile"), display
    )
    baseline = {"industry_logic": "baseline", "citations": {}}
    skill._reserve_freshness_citations(baseline, overlay, display)

    assert baseline["industry_logic"] == "baseline"
    assert overlay["summary_candidate"]["citation_refs"] == [1]
    assert baseline["citations"][1]["synthesis_display_only"] is True


def test_freshness_overlay_uses_today_when_report_as_of_date_is_missing():
    class FixedToday(date):
        @classmethod
        def today(cls):
            return cls(2026, 7, 14)

    old_fulltext = _make_fulltext_item()
    old_fulltext.publish_time = "2026-01-01"
    display = {
        "_curated_external_narrative_paragraphs": [{
            "paragraph_index": 0,
            "text": "外部材料称客户订单节奏出现变化，需等待正式材料验证。",
            "topic_keys": ["order_customer"],
            "citation_refs": [1],
        }],
        "citations": {1: {
            "source": "微信公众号精选观察",
            "url": "https://example.com/order",
            "date": "2026-07-01",
            "source_credit": 60,
            "synthesis_display_only": True,
            "scoring_eligible": False,
            "risk_score_eligible": False,
            "quality_action": "preview_only",
            "verification_status": "professional_observation",
        }},
    }
    ctx = SkillContext(input={
        "collected_at": "2024-01-01",
        "periodic_report_fulltext_items": [old_fulltext],
        "broker_research_digest_items": [],
        "source_intake_items": [],
        "deep_analysis_evidence_profile": {"profile": "formal_medium"},
    })

    with patch.object(synthesis_skills_module, "date", FixedToday):
        overlay = SynthesisSkill()._build_evidence_freshness_overlay(
            ctx, ctx.get("deep_analysis_evidence_profile"), display,
        )

    assert overlay["as_of_date"] == "2026-07-14"
    assert overlay["summary_candidate"]["citation_refs"] == [1]


def test_synthesis_skill_run_builds_freshness_overlay_from_context_display():
    old_fulltext = _make_fulltext_item()
    old_fulltext.publish_time = "2026-01-01"
    skill = SynthesisSkill()
    skill._build_evidence_profile = lambda *_args: {"profile": "formal_medium"}
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "report_as_of_date": "2026-07-14",
        "periodic_report_fulltext_items": [old_fulltext],
        "broker_research_digest_items": [],
        "source_intake_items": [],
        "deep_analysis_display": {
            "_curated_external_narrative_paragraphs": [{
                "paragraph_index": 0,
                "text": "外部材料称客户订单节奏出现变化，需等待正式材料验证。",
                "topic_keys": ["order_customer"],
                "citation_refs": [1],
            }],
            "citations": {1: {
                "source": "微信公众号精选观察",
                "url": "https://example.com/order",
                "date": "2026-07-01",
                "source_credit": 60,
                "synthesis_display_only": True,
                "scoring_eligible": False,
                "risk_score_eligible": False,
                "quality_action": "preview_only",
                "verification_status": "professional_observation",
            }},
        },
        "stock_raw": {"reports": [], "announcements": [], "fundflow": [], "news": [], "zhihu": {"report_items": []}},
        "keep_posts": [],
    })

    skill.run(ctx)

    assert ctx.get("evidence_freshness")["summary_candidate"] is not None


class DualSynthesizer:
    """Returns enhanced narrative iff annual-report or broker-research display material is present."""

    def __init__(self):
        self.calls = []

    def synthesize(self, stock_name, all_data):
        items = all_data["items"]
        self.calls.append(list(items))
        has_fulltext = any(
            (getattr(i, "extra", {}) or {}).get("source_type")
            == "periodic_report_fulltext_analysis"
            for i in items
        )
        has_narrative_card = any(
            (getattr(i, "extra", {}) or {}).get("source_type")
            == "periodic_report_narrative_evidence"
            for i in items
        )
        has_broker_digest = any(
            (getattr(i, "extra", {}) or {}).get("source_type")
            == "broker_research"
            for i in items
        )
        if has_fulltext or has_narrative_card or has_broker_digest:
            return {
                "industry_logic": (
                    ("fulltext 降价 毛利率承压 " if has_fulltext else "")
                    + ("narrative cards 客户流失 净流出 " if has_narrative_card else "")
                    + ("broker digest 券商观点 " if has_broker_digest else "")
                    + "narrative"
                ),
                "fundamentals": "enhanced 净流出 路径",
                "valuation_debate": "",
                "funding_sentiment": "",
                "events_catalysts": "",
                "core_facts": [
                    {"fact_id": 9, "fact": "enhanced fact", "data": "", "confidence": "高"},
                ],
                "citations": {},
            }
        return {
            "industry_logic": "baseline narrative",
            "fundamentals": "baseline fundamentals",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "core_facts": [
                {"fact_id": 1, "fact": "baseline fact", "data": "", "confidence": "高"},
            ],
            "citations": {},
        }


class EmptyCoreFactSynthesizer:
    def synthesize(self, stock_name, all_data):
        return {
            "industry_logic": "baseline narrative",
            "fundamentals": "",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "core_facts": [],
            "citations": {},
        }


class UnsupportedCoreFactSynthesizer:
    def synthesize(self, stock_name, all_data):
        return {
            "industry_logic": "baseline narrative",
            "fundamentals": "",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "core_facts": [
                {
                    "fact_id": 1,
                    "fact": "无引用事实",
                    "data": "无",
                    "confidence": "高",
                    "provenance_status": "missing_ref",
                }
            ],
            "citations": {},
        }


def _fulltext_ctx(switch, fake):
    return _test_context({
        "stock_name": "中简科技",
        "include_periodic_report_fulltext_in_synthesis": switch,
        "periodic_report_fulltext_items": [_make_fulltext_item()],
        "stock_raw": {
            "reports": [{"title": "研报", "content": "研发投入增加", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })


def _write_narrative_card_note(base_dir, stock_name="中简科技"):
    notes_dir = Path(base_dir) / "10-Stocks" / stock_name / "periodic_narrative_cards"
    notes_dir.mkdir(parents=True, exist_ok=True)
    path = notes_dir / "2025-annual-management-market-view-0.md"
    path.write_text(
        "---\n"
        f"stock: {stock_name}\n"
        "code: 300777\n"
        "source_type: periodic_report_narrative_evidence\n"
        "card_id: periodic:300777:2025:annual:narrative:management_market_view:0\n"
        "schema_version: periodic_report_narrative_evidence_card.v1\n"
        "card_type: management_market_view\n"
        "title: 管理层市场判断\n"
        "report_year: 2025\n"
        "report_type: annual\n"
        "source_credit: 75\n"
        "source_block_id: market_demand_outlook-0\n"
        "evidence_refs:\n"
        "  - market_demand_outlook-0\n"
        "source_excerpt_hash: \"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"\n"
        "knowledge_fact_status: narrative_evidence\n"
        "knowledge_eligible: false\n"
        "knowledge_persisted: true\n"
        "synthesis_eligible: false\n"
        "experimental: true\n"
        "---\n\n"
        "# 中简科技 2025 annual management_market_view\n\n"
        "## Narrative Evidence\n\n"
        "> 年报卡片显示客户流失与净流出风险词只应进入 display synthesis。\n\n"
        "## Source\n\n"
        "- source_credit: 75\n",
        encoding="utf-8",
    )
    return path


def _narrative_card_ctx(tmp_path, switch=True, include_fulltext=False):
    _write_narrative_card_note(tmp_path)
    ctx_input = {
        "stock_name": "中简科技",
        "knowledge_base_dir": str(tmp_path),
        "include_periodic_narrative_cards_in_synthesis_display": switch,
        "stock_raw": {
            "reports": [{"title": "研报", "content": "研发投入增加", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    }
    if include_fulltext:
        ctx_input["include_periodic_report_fulltext_in_synthesis"] = True
        ctx_input["periodic_report_fulltext_items"] = [_make_fulltext_item()]
    return SkillContext(input=ctx_input)


def test_periodic_report_fulltext_synthesis_default_off_excludes_fulltext():
    fake = DualSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _fulltext_ctx(False, fake)
    skill.run(ctx)

    # synthesizer only ever sees ordinary items
    assert len(fake.calls) == 1
    assert all(
        (getattr(i, "extra", {}) or {}).get("source_type")
        != "periodic_report_fulltext_analysis"
        for i in fake.calls[0]
    )
    assert ctx.output.get("synthesis_display") is None
    assert ctx.get("synthesis")["industry_logic"] == "baseline narrative"


def test_periodic_report_fulltext_synthesis_keeps_canonical_synthesis_baseline():
    fake = DualSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _fulltext_ctx(True, fake)
    skill.run(ctx)

    assert ctx.get("synthesis")["industry_logic"] == "baseline narrative"
    assert ctx.get("synthesis_display")["industry_logic"] == "fulltext 降价 毛利率承压 narrative"


def test_periodic_report_fulltext_synthesis_does_not_change_synthesis_text_or_core_facts():
    fake = DualSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _fulltext_ctx(True, fake)
    skill.run(ctx)

    synthesis_text = ctx.get("synthesis_text")
    assert "baseline narrative" in synthesis_text
    assert "降价" not in synthesis_text
    assert "毛利率承压" not in synthesis_text
    assert "净流出" not in synthesis_text

    assert ctx.get("core_facts")[0]["fact"] == "baseline fact"

    enhanced_flatten = ctx.get("synthesis_text_with_periodic_report_fulltext")
    assert "降价" in enhanced_flatten
    assert "净流出" in enhanced_flatten


def test_empty_core_facts_fall_back_to_periodic_filing_core_facts():
    skill = SynthesisSkill(synthesizer=EmptyCoreFactSynthesizer())
    fallback_fact = {
        "fact_id": 1,
        "fact": "营业收入",
        "data": "389805.46万元",
        "confidence": "高",
        "provenance_status": "supported",
        "source_labels": ["2025年annual"],
        "evidence_type": "periodic_report_filing_fact",
    }
    ctx = _test_context({
        "stock_name": "圣邦股份",
        "periodic_report_filing_core_facts": [fallback_fact],
        "stock_raw": {
            "reports": [],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    skill.run(ctx)

    assert ctx.get("core_facts") == [fallback_fact]
    assert ctx.get("synthesis")["core_facts"] == []


def test_unsupported_core_facts_fall_back_to_periodic_filing_core_facts():
    skill = SynthesisSkill(synthesizer=UnsupportedCoreFactSynthesizer())
    fallback_fact = {
        "fact_id": 1,
        "fact": "营业收入",
        "data": "389805.46万元",
        "confidence": "高",
        "provenance_status": "supported",
        "source_labels": ["2025年annual"],
        "evidence_type": "periodic_report_filing_fact",
    }
    ctx = _test_context({
        "stock_name": "圣邦股份",
        "periodic_report_filing_core_facts": [fallback_fact],
        "stock_raw": {
            "reports": [{"title": "测试研报", "content": "圣邦股份测试材料", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    skill.run(ctx)

    assert ctx.get("core_facts") == [fallback_fact]
    assert ctx.get("synthesis")["core_facts"][0]["provenance_status"] == "missing_ref"


def test_periodic_report_fulltext_knowledge_persistence_would_receive_baseline():
    """Knowledge writer reads ctx['synthesis'] which must stay baseline."""
    fake = DualSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _fulltext_ctx(True, fake)
    skill.run(ctx)

    knowledge_input = ctx.get("synthesis")
    flattened = "\n".join(str(v) for v in knowledge_input.values())
    assert "baseline" in flattened
    assert "降价" not in flattened
    assert "毛利率承压" not in flattened


def test_append_at_end_preserves_existing_source_order():
    fake = DualSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _fulltext_ctx(True, fake)
    skill.run(ctx)

    assert len(fake.calls) == 2
    baseline_items = fake.calls[0]
    enhanced_items = fake.calls[1]

    # ordinary items keep identical order at the front of the enhanced call
    assert enhanced_items[: len(baseline_items)] == baseline_items
    # fulltext item is appended last
    assert (
        (getattr(enhanced_items[-1], "extra", {}) or {}).get("source_type")
        == "periodic_report_fulltext_analysis"
    )
    assert len(enhanced_items) == len(baseline_items) + 1


def test_periodic_report_fulltext_synthesis_no_items_skips_display():
    """Switch on but no eligible fulltext item: behaves like default off."""
    fake = DualSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _test_context({
        "stock_name": "中简科技",
        "include_periodic_report_fulltext_in_synthesis": True,
        "periodic_report_fulltext_items": [],
        "stock_raw": {
            "reports": [{"title": "研报", "content": "研发投入增加", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    skill.run(ctx)

    assert len(fake.calls) == 1
    assert ctx.output.get("synthesis_display") is None


def test_periodic_report_fulltext_synthesis_rejects_malformed_fulltext_item():
    """A source_type match alone is not enough to enter display synthesis."""
    malformed = _make_fulltext_item()
    malformed.extra = {
        **malformed.extra,
        "source_credit": 95,
        "verification_status": "confirmed_fact",
        "experimental": False,
    }
    fake = DualSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _test_context({
        "stock_name": "中简科技",
        "include_periodic_report_fulltext_in_synthesis": True,
        "periodic_report_fulltext_items": [malformed],
        "stock_raw": {
            "reports": [{"title": "研报", "content": "研发投入增加", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    skill.run(ctx)

    assert len(fake.calls) == 1
    assert ctx.output.get("synthesis_display") is None


def test_periodic_narrative_cards_synthesis_default_off_excludes_cards(tmp_path):
    fake = DualSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _narrative_card_ctx(tmp_path, switch=False)
    skill.run(ctx)

    assert len(fake.calls) == 1
    assert all(
        (getattr(i, "extra", {}) or {}).get("source_type")
        != "periodic_report_narrative_evidence"
        for i in fake.calls[0]
    )
    assert ctx.output.get("synthesis_display") is None
    assert ctx.get("synthesis")["industry_logic"] == "baseline narrative"


def test_periodic_narrative_cards_synthesis_display_keeps_baseline_invariants(tmp_path):
    fake = DualSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _narrative_card_ctx(tmp_path, switch=True)
    skill.run(ctx)

    assert ctx.get("synthesis")["industry_logic"] == "baseline narrative"
    assert ctx.get("core_facts")[0]["fact"] == "baseline fact"
    assert "客户流失" not in ctx.get("synthesis_text")
    assert "净流出" not in ctx.get("synthesis_text")
    assert "narrative cards 客户流失" in ctx.get("synthesis_display")["industry_logic"]
    assert "客户流失" in ctx.get("synthesis_text_with_periodic_narrative_cards")

    knowledge_input = "\n".join(str(v) for v in ctx.get("synthesis").values())
    assert "客户流失" not in knowledge_input
    assert "narrative cards" not in knowledge_input


def test_periodic_narrative_display_reuses_context_material_pack(monkeypatch):
    card = {
        "card_id": "annual-argument:cached",
        "title": "已缓存年报材料",
        "excerpt": "公司产品完成客户验证。",
        "report_year": 2025,
        "report_type": "annual",
        "source_type": "periodic_report_narrative_evidence",
        "source_credit": 75,
        "argument_family": "technology_product_progress",
        "argument_complete": True,
        "source_unit_ids": ["rd-0:u0"],
        "source_units": [],
    }
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "annual_report_material_pack": {"selected_narrative_cards": [card]},
        "periodic_narrative_cards_max_display_items": 1,
    })

    def fail_if_reloaded(**_kwargs):
        raise AssertionError("should reuse the context material pack")

    monkeypatch.setattr(
        synthesis_skills_module,
        "load_periodic_narrative_card_synthesis_items",
        fail_if_reloaded,
    )

    items = SynthesisSkill._eligible_periodic_narrative_card_items(ctx)

    assert [item.extra["card_id"] for item in items] == ["annual-argument:cached"]


def test_periodic_narrative_display_keeps_default_limit_for_invalid_context_value():
    cards = [
        {
            "card_id": f"annual-argument:{index}",
            "title": f"已缓存年报材料 {index}",
            "excerpt": f"公司产品 {index} 完成客户验证。",
            "report_year": 2025,
            "report_type": "annual",
            "source_type": "periodic_report_narrative_evidence",
            "source_credit": 75,
        }
        for index in range(13)
    ]
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "annual_report_material_pack": {"selected_narrative_cards": cards},
        "periodic_narrative_cards_max_display_items": "invalid",
    })

    items = SynthesisSkill._eligible_periodic_narrative_card_items(ctx)

    assert len(items) == 12


def test_periodic_narrative_cards_and_fulltext_share_one_display_synthesis(tmp_path):
    fake = DualSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _narrative_card_ctx(tmp_path, switch=True, include_fulltext=True)
    skill.run(ctx)

    assert len(fake.calls) == 2
    baseline_items = fake.calls[0]
    display_items = fake.calls[1]
    assert display_items[: len(baseline_items)] == baseline_items
    tail_source_types = [
        (getattr(item, "extra", {}) or {}).get("source_type")
        for item in display_items[len(baseline_items):]
    ]
    assert tail_source_types == [
        "periodic_report_fulltext_analysis",
        "periodic_report_narrative_evidence",
    ]
    assert "fulltext 降价" in ctx.get("synthesis_display")["industry_logic"]
    assert "narrative cards 客户流失" in ctx.get("synthesis_display")["industry_logic"]
    assert "客户流失" in ctx.get("synthesis_text_with_periodic_narrative_cards")
    assert "降价" in ctx.get("synthesis_text_with_periodic_report_fulltext")


def _write_broker_digest_note(base_dir, stock_name="中简科技"):
    notes_dir = Path(base_dir) / "10-Stocks" / stock_name / "broker_research_digest"
    notes_dir.mkdir(parents=True, exist_ok=True)
    path = notes_dir / "2026-06-01-测试证券-broker_core_view.md"
    path.write_text(
        "---\n"
        f"stock: {stock_name}\n"
        "code: 300777\n"
        "source_type: broker_research\n"
        "card_type: broker_core_view\n"
        "title: 测试研报\n"
        "report_title: 测试报告\n"
        "institution: 测试证券\n"
        "publish_time: 2026-06-01\n"
        "source_credit: 72\n"
        "claim_status: professional_analysis\n"
        "confirmed_fact: false\n"
        "scoring_eligible: false\n"
        "risk_score_eligible: false\n"
        "display_only: false\n"
        "viewpoint_cluster: business_driver_product_mix\n"
        "report_length_class: short\n"
        "---\n\n"
        f"# {stock_name} broker research digest\n\n"
        "## Broker Research Excerpt\n\n"
        "> 券商研报显示公司新产品放量，盈利预测上调。\n\n"
        "## Source\n\n"
        "- institution: 测试证券\n",
        encoding="utf-8",
    )
    return path


def _broker_digest_ctx(tmp_path, switch=True, include_fulltext=False, include_narrative=False):
    _write_broker_digest_note(tmp_path)
    ctx_input = {
        "stock_name": "中简科技",
        "knowledge_base_dir": str(tmp_path),
        "include_broker_research_digest_in_synthesis_display": switch,
        "stock_raw": {
            "reports": [{"title": "研报", "content": "研发投入增加", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    }
    if include_fulltext:
        ctx_input["include_periodic_report_fulltext_in_synthesis"] = True
        ctx_input["periodic_report_fulltext_items"] = [_make_fulltext_item()]
    if include_narrative:
        _write_narrative_card_note(tmp_path)
        ctx_input["include_periodic_narrative_cards_in_synthesis_display"] = True
    return SkillContext(input=ctx_input)


def test_broker_research_digest_synthesis_default_off_excludes_digest(tmp_path):
    fake = DualSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _broker_digest_ctx(tmp_path, switch=False)
    skill.run(ctx)

    assert len(fake.calls) == 1
    assert all(
        (getattr(i, "extra", {}) or {}).get("source_type") != "broker_research"
        for i in fake.calls[0]
    )
    assert ctx.output.get("synthesis_display") is None
    assert ctx.get("synthesis")["industry_logic"] == "baseline narrative"


def test_broker_research_digest_synthesis_display_keeps_baseline_invariants(tmp_path):
    fake = DualSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _broker_digest_ctx(tmp_path, switch=True)
    skill.run(ctx)

    assert ctx.get("synthesis")["industry_logic"] == "baseline narrative"
    assert ctx.get("core_facts")[0]["fact"] == "baseline fact"
    assert "券商观点" not in ctx.get("synthesis_text")
    assert "broker digest" in ctx.get("synthesis_display")["industry_logic"]
    assert "券商观点" in ctx.get("synthesis_text_with_broker_research_digest")

    knowledge_input = "\n".join(str(v) for v in ctx.get("synthesis").values())
    assert "broker digest" not in knowledge_input
    assert "券商观点" not in knowledge_input


def test_broker_research_digest_notes_refresh_from_manifest_before_loading(tmp_path, monkeypatch):
    raw_root = tmp_path / "raw"
    stock_dir = raw_root / "broker_research_reports" / "中际旭创_300308"
    pdf_dir = stock_dir / "_downloads"
    pdf_dir.mkdir(parents=True)
    pdf_path = pdf_dir / "2026-06-01-测试证券-高速光模块放量.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test")
    (stock_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "broker_research_cache_manifest.v1",
                "stock_name": "中际旭创",
                "stock_code": "300308",
                "reports": [
                    {
                        "title": "高速光模块放量",
                        "institution": "测试证券",
                        "publish_time": "2026-06-01",
                        "url": "https://pdf.dfcfw.com/pdf/H3_TEST_1.pdf",
                        "path": str(pdf_path),
                        "status": "ok",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    notes_dir = tmp_path / "knowledge" / "10-Stocks" / "中际旭创" / "broker_research_digest"
    notes_dir.mkdir(parents=True)
    (notes_dir / "2026-06-01-测试证券-broker-core-view-old.md").write_text(
        "---\n"
        "source_type: broker_research\n"
        "card_id: broker:old\n"
        "card_type: broker_core_view\n"
        "institution: 测试证券\n"
        "source_credit: 72\n"
        "claim_status: professional_analysis\n"
        "confirmed_fact: false\n"
        "scoring_eligible: false\n"
        "risk_score_eligible: false\n"
        "display_only: false\n"
        "---\n\n"
        "## Broker Research Excerpt\n\n"
        "> 旧摘录。\n",
        encoding="utf-8",
    )

    def fake_extract_pdf_text(path):
        assert path == str(pdf_path)
        return (
            "核心观点\n"
            "测试证券认为高速光模块需求增长，800G与1.6T产品放量推动收入增长，"
            "毛利率和产品结构改善带来盈利弹性。\n"
        )

    monkeypatch.setattr(
        "broker_research_digest_note_writer.extract_pdf_text",
        fake_extract_pdf_text,
    )

    fake = DualSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = SkillContext(input={
        "stock_name": "中际旭创",
        "stock_codes": {"中际旭创": "300308"},
        "knowledge_base_dir": str(tmp_path / "knowledge"),
        "broker_research_cache_root": str(raw_root / "broker_research_reports"),
        "include_broker_research_digest_in_synthesis_display": True,
        "stock_raw": {
            "reports": [{"title": "研报", "content": "研发投入增加", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })

    skill.run(ctx)

    note_text = "\n".join(path.read_text(encoding="utf-8") for path in notes_dir.glob("*.md"))
    assert "## Selection Diagnostics" in note_text
    assert "selection_reason" in note_text
    assert "heading=`核心观点`" in note_text
    assert "高速光模块需求增长" in note_text
    display_items = fake.calls[-1]
    broker_text = "\n".join(
        str(getattr(item, "content", ""))
        for item in display_items
        if (getattr(item, "extra", {}) or {}).get("source_type") == "broker_research"
    )
    assert "高速光模块需求增长" in broker_text
    assert "旧摘录" not in broker_text


def test_broker_research_digest_fulltext_and_narrative_share_one_display_synthesis(tmp_path):
    fake = DualSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _broker_digest_ctx(tmp_path, switch=True, include_fulltext=True, include_narrative=True)
    skill.run(ctx)

    assert len(fake.calls) == 2
    baseline_items = fake.calls[0]
    display_items = fake.calls[1]
    assert display_items[: len(baseline_items)] == baseline_items
    tail_source_types = [
        (getattr(item, "extra", {}) or {}).get("source_type")
        for item in display_items[len(baseline_items):]
    ]
    assert tail_source_types == [
        "periodic_report_fulltext_analysis",
        "periodic_report_narrative_evidence",
        "broker_research",
    ]
    assert "fulltext 降价" in ctx.get("synthesis_display")["industry_logic"]
    assert "narrative cards 客户流失" in ctx.get("synthesis_display")["industry_logic"]
    assert "broker digest 券商观点" in ctx.get("synthesis_display")["industry_logic"]


def test_display_synthesis_dedupes_duplicate_material_before_synthesizer(tmp_path):
    duplicate_content = "同一篇光模块深度分析，800G 与 1.6T 是核心方向。"
    fulltext_item = _make_fulltext_item()
    fulltext_item.content = duplicate_content
    broker_item = SynthesisItem(
        title="测试证券 | 光模块点评",
        content=duplicate_content,
        author="测试证券",
        source_platform="券商研报",
        url="",
        publish_time="2026-06-01",
        extra={
            "source_type": "broker_research",
            "source_credit": 72,
            "verification_status": "professional_observation",
            "claim_status": "professional_analysis",
            "knowledge_eligible": False,
            "report_eligible": False,
            "synthesis_eligible": False,
            "synthesis_display_only": True,
            "confirmed_fact": False,
            "scoring_eligible": False,
            "risk_score_eligible": False,
        },
    )
    fake = DualSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _test_context({
        "stock_name": "中简科技",
        "include_periodic_report_fulltext_in_synthesis": True,
        "periodic_report_fulltext_items": [fulltext_item],
        "include_broker_research_digest_in_synthesis_display": True,
        "stock_raw": {
            "reports": [{"title": "研报", "content": "研发投入增加", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })

    from unittest.mock import patch

    with patch.object(SynthesisSkill, "_eligible_broker_research_digest_items", return_value=[broker_item]):
        skill.run(ctx)

    assert len(fake.calls) == 2
    baseline_items = fake.calls[0]
    display_items = fake.calls[1]
    tail_source_types = [
        (getattr(item, "extra", {}) or {}).get("source_type")
        for item in display_items[len(baseline_items):]
    ]
    assert tail_source_types == ["periodic_report_fulltext_analysis"]
    assert ctx.get("synthesis_display_deduped_sources")[0]["duplicate"]["source_type"] == "broker_research"


def test_broker_research_digest_synthesis_no_eligible_items_skips_display(tmp_path):
    fake = DualSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = SkillContext(input={
        "stock_name": "中简科技",
        "knowledge_base_dir": str(tmp_path),
        "include_broker_research_digest_in_synthesis_display": True,
        "stock_raw": {
            "reports": [{"title": "研报", "content": "研发投入增加", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    skill.run(ctx)

    assert len(fake.calls) == 1
    assert ctx.output.get("synthesis_display") is None


def test_fill_citation_metadata_preserves_credit_fields():
    skill = SynthesisSkill()
    items = [
        SynthesisItem(
            title="公告",
            content="内容",
            author="公司",
            source_platform="公告",
            url="",
            publish_time="",
            extra={
                "source_credit": 95,
                "source_type": "announcement",
                "verification_status": "primary_source",
            },
        ),
    ]
    synthesis = {
        "citations": {1: {"_placeholder": True}},
        "core_facts": [],
    }

    filled = skill._fill_citation_metadata(synthesis, items)
    meta = filled["citations"][1]
    assert meta["source_credit"] == 95
    assert meta["source_type"] == "announcement"
    assert meta["verification_status"] == "primary_source"


def test_formal_thin_external_rich_skips_legacy_synthesis_with_chat_client(tmp_path):
    """ formal_thin_external_rich must not call legacy deep-analysis prompts when llm_client.chat exists. """
    from unittest.mock import MagicMock

    digest_path = _write_viewpoint_digest_json(
        tmp_path,
        [
            _make_viewpoint_claim_with_text("vc1", "外部观点A", topic="technology_route", title="外部A"),
            _make_viewpoint_claim_with_text("vc2", "外部观点B", topic="order_capacity_delivery", title="外部B"),
            _make_viewpoint_claim_with_text("vc3", "外部观点C", topic="financial_quality", title="外部C"),
        ],
    )

    chat_client = MagicMock()
    chat_client.chat.return_value = {
        "industry_logic": "legacy 行业逻辑",
        "fundamentals": "legacy 基本面",
        "valuation_debate": "legacy 估值",
        "funding_sentiment": "legacy 资金",
        "events_catalysts": "legacy 催化",
        "core_facts": [],
        "citations": {},
    }

    fake = FakeSynthesizer()
    skill = SynthesisSkill(llm_client=chat_client, synthesizer=fake)
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "include_curated_external_viewpoint_digest_in_deep_analysis_display": True,
        "curated_external_viewpoint_digest_json": str(digest_path),
        "stock_raw": {
            "reports": [],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    skill.run(ctx)

    profile = ctx.output.get("deep_analysis_evidence_profile", {})
    assert profile.get("profile") == "formal_thin_external_rich"
    assert fake.calls == []
    assert chat_client.chat.call_count == 0
    synthesis = ctx.output.get("synthesis", {})
    assert synthesis.get("industry_logic", "") == ""
    assert synthesis.get("fundamentals", "") == ""
    assert "legacy" not in str(synthesis.get("valuation_debate", ""))


def test_evidence_profile_has_annual_memo_fields():
    fake = FakeSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = _test_context({
        "stock_name": "复旦微电",
        "stock_raw": {
            "announcements": [{"title": "年报", "content": "公司披露年度报告", "date": "2026-04-30"}],
            "reports": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })

    skill.run(ctx)

    profile = ctx.output.get("deep_analysis_evidence_profile", {})
    assert "annual_memo_status" in profile
    assert profile.get("broker_memo_status") == "absent"
    assert profile.get("broker_single_institution") is False
    assert "memo_refs_resolved" in profile
    assert "formal_thin_layout_variant" in profile


def test_evidence_profile_routes_partial_formal_material_to_formal_medium():
    skill = SynthesisSkill(synthesizer=MagicMock())
    ctx = SkillContext(input={"stock_name": "测试股"})
    ctx.set("formal_financial_fact_pack", {
        "facts": [
            {"metric": "营业收入", "value": "10亿元"},
            {"metric": "归母净利润", "value": "1亿元"},
        ]
    })
    ctx.set("annual_report_memo", {"status": "absent"})
    ctx.set("broker_research_memo", {"status": "absent"})
    item = SynthesisItem(
        title="公司公告",
        content="公司披露收入增长但材料不足以支撑完整产业和业绩分析。",
        author="公司公告",
        source_platform="公司公告",
        url="",
        publish_time="2026-04-30",
        interaction_score=0,
        extra={"source_type": "announcement", "source_credit": 90},
    )

    profile = skill._build_evidence_profile(ctx, [item])

    assert profile["profile"] == "formal_medium"
    assert "formal_support_partial" in profile["reasons"]
    assert "items_present_fallback" not in profile["reasons"]


def _broker_digest_item(
    *,
    card_type="broker_core_view",
    institution="测试证券",
    title="测试研报",
    content="券商认为公司产品升级带动收入增长。",
    cluster="broker-core",
):
    return SynthesisItem(
        title=f"{institution} | {title}",
        content=content,
        author=institution,
        source_platform="券商研报",
        url="",
        publish_time="2026-05-01",
        interaction_score=0,
        extra={
            "source_type": "broker_research",
            "source_credit": 72,
            "claim_status": "professional_analysis",
            "verification_status": "professional_observation",
            "confirmed_fact": False,
            "scoring_eligible": False,
            "risk_score_eligible": False,
            "institution": institution,
            "card_type": card_type,
            "viewpoint_cluster": cluster,
        },
    )


def test_build_broker_research_memo_admits_two_content_families():
    skill = SynthesisSkill(synthesizer=MagicMock())
    ctx = SkillContext(input={
        "stock_name": "中际旭创",
        "broker_research_digest_items": [
            _broker_digest_item(card_type="broker_core_view", content="券商认为 800G 放量支撑增长。", cluster="core"),
            _broker_digest_item(card_type="broker_product_driver", institution="另一个证券", content="研报认为 1.6T 进入增长接力。", cluster="driver"),
        ],
    })

    memo = skill._build_broker_research_memo(ctx)

    assert memo["status"] == "ready"
    assert memo["institutions"] == ["测试证券", "另一个证券"]
    assert memo["sections"][0]["citation_refs"]
    assert memo["sections"][0]["source_ref_ids"][0].startswith("broker_research_digest:")
    assert memo["validation"]["entered_scoring"] is False
    assert memo["validation"]["entered_target_price"] is False


def test_build_broker_research_memo_rejects_single_thin_card():
    skill = SynthesisSkill(synthesizer=MagicMock())
    ctx = SkillContext(input={
        "stock_name": "中际旭创",
        "broker_research_digest_items": [
            _broker_digest_item(card_type="broker_core_view", content="券商认为需求增长。", cluster="core"),
        ],
    })

    memo = skill._build_broker_research_memo(ctx)

    assert memo["status"] == "absent"
    assert memo["sections"] == []


def test_build_broker_research_memo_preserves_same_cluster_across_institutions():
    skill = SynthesisSkill(synthesizer=MagicMock())
    ctx = SkillContext(input={
        "stock_name": "中际旭创",
        "broker_research_digest_items": [
            _broker_digest_item(card_type="broker_core_view", institution="甲证券", content="券商认为需求增长。", cluster="same-view"),
            _broker_digest_item(card_type="broker_core_view", institution="乙证券", content="机构认为需求增长较快。", cluster="same-view"),
        ],
    })

    memo = skill._build_broker_research_memo(ctx)

    assert memo["status"] == "ready"
    assert memo["diagnostics"]["usable_card_count"] == 2
    assert memo["institutions"] == ["甲证券", "乙证券"]


def test_build_broker_research_memo_forecast_and_risk_rows_resolve_refs():
    skill = SynthesisSkill(synthesizer=MagicMock())
    ctx = SkillContext(input={
        "stock_name": "中际旭创",
        "broker_research_digest_items": [
            _broker_digest_item(card_type="broker_core_view", content="券商认为产品升级打开空间。", cluster="core"),
            _broker_digest_item(card_type="broker_earnings_forecast", content="研报预计 2026E 归母净利润上修。", cluster="forecast"),
            _broker_digest_item(card_type="broker_risk_note", content="下游需求不及预期。", cluster="risk"),
        ],
    })

    memo = skill._build_broker_research_memo(ctx)

    forecast = memo["forecast_ranges"][0]
    risk = memo["risks"][0]
    for row in (forecast, risk):
        assert row["internal_refs"]
        assert row["citation_refs"]
        assert row["source_ref_ids"]
        assert row["citation_refs"][0] in memo["citations"]
    assert memo["status"] == "single_institution"


def test_build_annual_report_memo_ready_vs_fallback():
    skill = SynthesisSkill(synthesizer=MagicMock())
    ctx = SkillContext(input={
        "stock_name": "复旦微电",
        "annual_report_material_pack": {
            "selected_narrative_cards": [
                {"card_type": "business_model", "title": "主营业务", "excerpt": "主营 FPGA。", "source_block_id": "b1", "report_year": "2025", "report_type": "annual"},
                {"card_type": "rd_product_progress", "title": "研发进展", "excerpt": "新品验证中。", "source_block_id": "b2", "report_year": "2025", "report_type": "annual"},
                {"card_type": "management_market_view", "title": "管理层判断", "excerpt": "需求稳健。", "source_block_id": "b3", "report_year": "2025", "report_type": "annual"},
                {"card_type": "market_outlook", "title": "市场前景", "excerpt": "行业增长。", "source_block_id": "b4", "report_year": "2025", "report_type": "annual"},
            ],
        },
        "formal_financial_fact_pack": {"facts": [{"metric": "营业收入", "value": "39.82亿元", "source": "2025年annual"}]},
    })
    memo = skill._build_annual_report_memo(ctx)
    assert memo["status"] == "ready"
    assert len(memo["sections"]["annual_report_explanation"]) >= 4

    ctx2 = SkillContext(input={
        "stock_name": "复旦微电",
        "annual_report_material_pack": {
            "selected_narrative_cards": [
                {"card_type": "business_model", "title": "主营业务", "excerpt": "主营 FPGA。", "source_block_id": "b1", "report_year": "2025", "report_type": "annual"},
            ],
        },
        "formal_financial_fact_pack": {"facts": []},
    })
    memo2 = skill._build_annual_report_memo(ctx2)
    assert memo2["status"] == "deterministic_fallback"


def test_build_annual_report_memo_preserves_all_canonical_v2_narrative_cards():
    skill = SynthesisSkill(synthesizer=MagicMock())
    families = (
        "business_structure",
        "operating_progress",
        "market_competition_outlook",
        "technology_product_progress",
        "financial_quality_explanation",
    )
    cards = []
    for index in range(14):
        family = families[index % len(families)]
        cards.append({
            "schema_version": "periodic_report_narrative_evidence_card.v2",
            "selection_version": "annual_argument_selection.v2",
            "card_id": f"periodic:v2:{index}",
            "argument_family": family,
            "argument_complete": index % 2 == 0,
            "title": f"年报论据 {index}",
            "source_block_id": f"block-{index}",
            "source_unit_ids": [f"unit-{index}"],
            "source_units": [{
                "unit_id": f"unit-{index}",
                "block_id": f"block-{index}",
                "ordinal": 0,
                "start_pos": 0,
                "end_pos": 10,
                "text": f"年报论据内容 {index}。",
            }],
            "source_excerpt": f"年报论据内容 {index}。",
            "excerpt": f"年报论据内容 {index}。",
            "fact_anchors": [f"事实锚点 {index}"],
            "secondary_signals": [],
            "score_parts": {"anchored_fact": 1},
            "quality_score": 1,
            "selection_reason": f"signal:{family}",
            "source_type": "periodic_report_narrative_evidence",
            "source_credit": 75,
            "report_year": 2025,
            "report_type": "annual",
        })
    ctx = SkillContext(input={
        "stock_name": "复旦微电",
        "annual_report_material_pack": {"selected_narrative_cards": cards},
        "formal_financial_fact_pack": {"facts": []},
        "periodic_narrative_cards_max_display_items": 3,
    })

    memo = skill._build_annual_report_memo(ctx)
    rows = memo["sections"]["annual_report_explanation"]
    legacy_groups = {
        "product_business",
        "operation_update",
        "management_view",
        "competitiveness_rd",
        "financial_explanation",
    }

    assert len(rows) == 14
    assert len(ctx.get("annual_report_material_pack")["selected_narrative_cards"]) == 14
    assert all(row["source_type"] == "periodic_report_narrative_evidence" for row in rows)
    assert all(row["display_group"] in families for row in rows)
    assert all("argument_complete" in row for row in rows)
    assert not legacy_groups.intersection(row["display_group"] for row in rows)
    assert [row["argument_family"] for row in rows] == [card["argument_family"] for card in cards]
    assert [row["argument_complete"] for row in rows] == [card["argument_complete"] for card in cards]


def test_build_annual_report_memo_marks_formal_financial_rows_as_incomplete_quality_explanations():
    skill = SynthesisSkill(synthesizer=MagicMock())
    ctx = SkillContext(input={
        "stock_name": "复旦微电",
        "annual_report_material_pack": {"selected_narrative_cards": []},
        "formal_financial_fact_pack": {
            "facts": [{"metric": "营业收入", "value": "39.82亿元", "source": "2025年annual"}],
        },
        "formal_financial_explanation_pack": {
            "rows": [{
                "metric": "营业收入变动原因",
                "normalized_summary": "收入变化主要系产品销售额增加所致。",
                "source_doc": "2025年annual",
                "source_ref": "annual:revenue",
            }],
        },
    })

    memo = skill._build_annual_report_memo(ctx)
    rows = memo["sections"]["confirmed"] + memo["sections"]["annual_report_explanation"]

    assert len(rows) == 2
    assert all(row["display_group"] == "financial_quality_explanation" for row in rows)
    assert all(row["argument_family"] == "financial_quality_explanation" for row in rows)
    assert all(row["argument_complete"] is False for row in rows)


def test_build_annual_report_memo_uses_in_memory_narrative_cards_without_notes():
    skill = SynthesisSkill(synthesizer=MagicMock())
    ctx = SkillContext(input={
        "stock_name": "复旦微电",
        "annual_report_material_pack": {"selected_narrative_cards": []},
        "periodic_report_narrative_evidence_cards": {
            "cards": [
                {
                    "card_id": "periodic:1",
                    "card_type": "business_model",
                    "title": "主营业务与产品",
                    "source_excerpt": "EEPROM产品在电表、手机摄像头模组、家电等领域稳步增长，车规级EEPROM产品已实现批量出货。",
                    "source_block_id": "operation-1",
                    "report_year": "2025",
                    "report_type": "annual",
                    "source_credit": 75,
                },
                {
                    "card_id": "periodic:2",
                    "card_type": "rd_product_progress",
                    "title": "研发与产品进展",
                    "source_excerpt": "新一代先进制程FPGA产品完成可靠性考核，开始量产准备。",
                    "source_block_id": "rd-1",
                    "report_year": "2025",
                    "report_type": "annual",
                    "source_credit": 75,
                },
                {
                    "card_id": "periodic:3",
                    "card_type": "management_market_view",
                    "title": "管理层市场判断",
                    "source_excerpt": "半导体行业景气度呈现结构性分化，FPGA产品在通信、工业控制、人工智能和高可靠领域应用良好。",
                    "source_block_id": "market-1",
                    "report_year": "2025",
                    "report_type": "annual",
                    "source_credit": 75,
                },
                {
                    "card_id": "periodic:4",
                    "card_type": "operation_update",
                    "title": "经营情况更新",
                    "source_excerpt": "安全与识别芯片各子线产品市场表现不同，在RFID与传感芯片带动下整体收入小幅增长。",
                    "source_block_id": "operation-2",
                    "report_year": "2025",
                    "report_type": "annual",
                    "source_credit": 75,
                },
            ],
        },
        "formal_financial_fact_pack": {"facts": []},
    })

    memo = skill._build_annual_report_memo(ctx)

    bodies = " ".join(r["body"] for r in memo["sections"]["annual_report_explanation"])
    assert memo["status"] == "ready"
    assert "车规级EEPROM" in bodies
    assert "先进制程FPGA" in bodies


def test_build_annual_report_memo_dedupes_duplicate_narrative_card_bodies():
    skill = SynthesisSkill(synthesizer=MagicMock())
    duplicate_body = "公司是国内领先的FPGA类产品供应商，提供FPGA、PSoC、FPAI等产品。"
    ctx = SkillContext(input={
        "stock_name": "复旦微电",
        "annual_report_material_pack": {
            "selected_narrative_cards": [
                {
                    "card_id": "periodic:1",
                    "card_type": "management_market_view",
                    "title": "管理层市场判断",
                    "excerpt": duplicate_body,
                    "source_block_id": "competitive-1",
                },
                {
                    "card_id": "periodic:2",
                    "card_type": "margin_competitiveness",
                    "title": "毛利率与竞争力",
                    "excerpt": duplicate_body,
                    "source_block_id": "competitive-1",
                },
                {
                    "card_id": "periodic:3",
                    "card_type": "operation_update",
                    "title": "经营情况更新",
                    "excerpt": "EEPROM产品在电表和车规领域稳步增长。",
                    "source_block_id": "operation-1",
                },
                {
                    "card_id": "periodic:4",
                    "card_type": "business_model",
                    "title": "主营业务与产品",
                    "excerpt": "公司建立健全FPGA、安全与识别芯片、非挥发存储器等产品线。",
                    "source_block_id": "business-1",
                },
            ],
        },
        "formal_financial_fact_pack": {"facts": []},
    })

    memo = skill._build_annual_report_memo(ctx)
    bodies = [r["body"] for r in memo["sections"]["annual_report_explanation"]]

    assert sum("公司是国内领先的FPGA类产品供应商" in body for body in bodies) == 1


def test_build_annual_report_memo_cleans_table_noise_from_narrative_cards():
    skill = SynthesisSkill(synthesizer=MagicMock())
    noisy_body = (
        "上海复旦微电子集团股份有限公司2025年年度报告 2025年，半导体行业的景气度呈现出明显的结构性分化。"
        " 产品类型 产品介绍 应用领域 产品或终端样图 12/ 产品类型 产品介绍 应用领域 产品或终端样图 "
        "公司拥有包括1xnm FinFET先进制程在内的SRAM型FPGA芯片，逻辑资源从50K至4000K，算力从4TOPS至128TOPS。"
        " 显示器及屏模组、智能电表、NOR Flash存储器 15/241。"
    )
    ctx = SkillContext(input={
        "stock_name": "复旦微电",
        "annual_report_material_pack": {
            "selected_narrative_cards": [
                {
                    "card_id": "periodic:1",
                    "card_type": "management_market_view",
                    "title": "管理层市场判断",
                    "excerpt": noisy_body,
                    "source_block_id": "market-1",
                },
                {
                    "card_id": "periodic:2",
                    "card_type": "operation_update",
                    "title": "经营情况更新",
                    "excerpt": "EEPROM产品在电表和车规领域稳步增长。",
                    "source_block_id": "operation-1",
                },
                {
                    "card_id": "periodic:3",
                    "card_type": "business_model",
                    "title": "主营业务与产品",
                    "excerpt": "公司建立健全FPGA、安全与识别芯片、非挥发存储器等产品线。",
                    "source_block_id": "business-1",
                },
                {
                    "card_id": "periodic:4",
                    "card_type": "rd_product_progress",
                    "title": "研发与产品进展",
                    "excerpt": "新一代先进制程FPGA产品完成可靠性考核。",
                    "source_block_id": "rd-1",
                },
            ],
        },
        "formal_financial_fact_pack": {"facts": []},
    })

    memo = skill._build_annual_report_memo(ctx)
    body = memo["sections"]["annual_report_explanation"][0]["body"]

    assert "上海复旦微电子集团股份有限公司2025年年度报告" not in body
    assert "产品类型 产品介绍 应用领域 产品或终端样图" not in body
    assert "12/" not in body
    assert "15/241" not in body
    assert "半导体行业的景气度呈现出明显的结构性分化" in body
    assert len(body) <= 320


def test_build_annual_report_memo_skips_table_fragment_cards():
    skill = SynthesisSkill(synthesizer=MagicMock())
    table_fragment = (
        "锁等网络通讯、物联网模块、电脑及周边产品、手机模组、主要由FM25/FM29系列构显示器及屏模组、"
        "智能电表、NOR Flash存储器成，支持SPI、通用并行接口，存储容量1Mbit-2Gbit。"
    )
    ctx = SkillContext(input={
        "stock_name": "复旦微电",
        "annual_report_material_pack": {
            "selected_narrative_cards": [
                {
                    "card_id": "periodic:1",
                    "card_type": "rd_product_progress",
                    "title": "研发与产品进展",
                    "excerpt": table_fragment,
                    "source_block_id": "rd-table-1",
                },
                {
                    "card_id": "periodic:2",
                    "card_type": "operation_update",
                    "title": "经营情况更新",
                    "excerpt": "EEPROM产品在电表和车规领域稳步增长。",
                    "source_block_id": "operation-1",
                },
                {
                    "card_id": "periodic:3",
                    "card_type": "business_model",
                    "title": "主营业务与产品",
                    "excerpt": "公司建立健全FPGA、安全与识别芯片、非挥发存储器等产品线。",
                    "source_block_id": "business-1",
                },
                {
                    "card_id": "periodic:4",
                    "card_type": "management_market_view",
                    "title": "管理层市场判断",
                    "excerpt": "半导体行业景气度呈现结构性分化。",
                    "source_block_id": "market-1",
                },
            ],
        },
        "formal_financial_fact_pack": {"facts": []},
    })

    memo = skill._build_annual_report_memo(ctx)
    bodies = " ".join(r["body"] for r in memo["sections"]["annual_report_explanation"])

    assert "FM25/FM29系列构显示器" not in bodies
    assert "EEPROM产品在电表和车规领域稳步增长" in bodies


def test_build_annual_report_memo_zero_revenue_warning():
    skill = SynthesisSkill(synthesizer=MagicMock())
    ctx = SkillContext(input={
        "stock_name": "复旦微电",
        "annual_report_material_pack": {"selected_narrative_cards": []},
        "formal_financial_fact_pack": {"facts": [{"metric": "营业收入", "value": "0.00亿元", "source": "2025年annual"}]},
        "periodic_report_filing_core_facts": [{"fact": "营业收入", "data": "0.00亿元", "source_labels": ["2025年annual"]}],
    })
    memo = skill._build_annual_report_memo(ctx)
    assert any("0.00亿元" in w or "营业收入" in w for w in memo["validation"]["warnings"])
    assert memo["status"] in ("blocked", "deterministic_fallback")


def test_build_annual_report_memo_zero_metric_does_not_block_explanation_rows():
    skill = SynthesisSkill(synthesizer=MagicMock())
    ctx = SkillContext(input={
        "stock_name": "复旦微电",
        "annual_report_material_pack": {"selected_narrative_cards": []},
        "formal_financial_fact_pack": {"facts": [{"metric": "营业收入", "value": "0.00亿元", "source": "2025年annual"}]},
        "formal_financial_explanation_pack": {
            "rows": [
                {
                    "metric": "营业收入变动原因",
                    "normalized_summary": "公司说明收入变化主要来自安全与识别芯片、智能电表芯片及 FPGA 销售额增加。",
                    "source_doc": "2025年annual",
                    "source_ref": "annual:explanation:revenue",
                }
            ]
        },
        "periodic_report_filing_core_facts": [{"fact": "营业收入", "data": "0.00亿元", "source_labels": ["2025年annual"]}],
    })
    memo = skill._build_annual_report_memo(ctx)

    assert memo["status"] == "deterministic_fallback"
    assert memo["sections"]["annual_report_explanation"]
    confirmed_body = " ".join(row["body"] for row in memo["sections"]["confirmed"])
    assert "0.00亿元" not in confirmed_body
    assert any("0.00亿元" in w for w in memo["validation"]["warnings"])


def test_build_annual_report_memo_skips_forbidden_source_cards():
    skill = SynthesisSkill(synthesizer=MagicMock())
    ctx = SkillContext(input={
        "stock_name": "复旦微电",
        "annual_report_material_pack": {
            "selected_narrative_cards": [
                {"card_type": "business_model", "title": "主营业务", "excerpt": "主营 FPGA。", "source_block_id": "b1", "report_year": "2025", "report_type": "annual"},
                {"card_type": "management_market_view", "title": "雪球观点", "excerpt": "雪球上有人认为订单饱满。", "source_block_id": "b2", "report_year": "2025", "report_type": "annual"},
                {"card_type": "rd_product_progress", "title": "研发进展", "excerpt": "券商认为新品将放量。", "source_block_id": "b3", "report_year": "2025", "report_type": "annual"},
                {"card_type": "market_outlook", "title": "市场前景", "excerpt": "行业增长。", "source_block_id": "b4", "report_year": "2025", "report_type": "annual"},
            ],
        },
        "formal_financial_fact_pack": {"facts": [{"metric": "营业收入", "value": "39.82亿元", "source": "2025年annual"}]},
    })
    memo = skill._build_annual_report_memo(ctx)
    bodies = " ".join(r["body"] for r in memo["sections"]["annual_report_explanation"])
    assert "雪球" not in bodies
    assert "券商认为" not in bodies
    assert any("雪球" in w or "券商认为" in w for w in memo["validation"]["warnings"])


def test_build_material_coverage_diagnostics_counts_raw_and_structured_layers(tmp_path):
    raw_root = tmp_path / "raw"
    manifest_dir = raw_root / "broker_research_reports" / "测试股_123456"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "manifest.json").write_text(
        json.dumps(
            {
                "reports": [
                    {"institution": "甲证券", "title": "报告一", "status": "ok"},
                    {"institution": "乙证券", "title": "报告二", "status": "ok"},
                    {"institution": "丙证券", "title": "报告三", "status": "ok"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    knowledge_dir = tmp_path / "knowledge"
    notes_dir = knowledge_dir / "10-Stocks" / "测试股" / "broker_research_digest"
    notes_dir.mkdir(parents=True)
    for institution in ("甲证券", "乙证券"):
        (notes_dir / f"2026-06-01-{institution}-broker-core-view.md").write_text(
            "---\n"
            "source_type: broker_research\n"
            "card_type: broker_core_view\n"
            f"institution: {institution}\n"
            "source_credit: 72\n"
            "claim_status: professional_analysis\n"
            "confirmed_fact: false\n"
            "scoring_eligible: false\n"
            "risk_score_eligible: false\n"
            "display_only: false\n"
            "viewpoint_cluster: broker_core_view\n"
            "---\n\n"
            "## Broker Research Excerpt\n\n"
            f"> {institution}认为：需求增长。\n",
            encoding="utf-8",
        )
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "stock_codes": {"测试股": "123456"},
        "knowledge_base_dir": str(knowledge_dir),
        "broker_research_cache_root": str(raw_root / "broker_research_reports"),
        "broker_research_digest_max_display_items": 3,
        "annual_report_material_pack": {
            "diagnostics": {
                "cards_seen": 10,
                "cards_selected": 4,
                "by_type_seen": {"business_model": 3},
                "by_type_selected": {"business_model": 1},
            },
        },
        "annual_report_memo": {
            "status": "ready",
            "sections": {
                "confirmed": [{"body": "营业收入：100亿元"}],
                "annual_report_explanation": [{"body": "主营业务说明"}],
            },
        },
        "broker_research_memo": {
            "status": "ready",
            "institutions": ["甲证券", "乙证券"],
            "sections": [{"body": "甲证券认为：需求增长"}],
            "risks": [{"body": "乙证券提示：风险"}],
            "diagnostics": {
                "input_item_count": 5,
                "usable_card_count": 2,
                "content_families": ["core_view", "risk_note"],
                "institution_count": 2,
            },
        },
        "deep_analysis_display": {
            "citations": {
                1: {"source": "微信公众号精选观察", "author": "作者A"},
                2: {"source": "知乎精选观察", "author": "作者B"},
            },
            "_curated_external_narrative_paragraphs": [{"heading": "供应链"}],
            "_curated_external_topic_groups": {"technology_route": [{"claim": "NPO"}]},
        },
    })

    coverage = SynthesisSkill._build_material_coverage_diagnostics(ctx)

    assert coverage["annual"]["narrative_cards_seen"] == 10
    assert coverage["annual"]["narrative_cards_selected"] == 4
    assert coverage["annual"]["memo_row_count"] == 2
    assert coverage["broker"]["raw_report_count"] == 3
    assert coverage["broker"]["raw_institution_count"] == 3
    assert coverage["broker"]["digest_note_count"] == 2
    assert coverage["broker"]["digest_note_institutions"] == ["乙证券", "甲证券"]
    assert coverage["broker"]["loader_max_items"] == 3
    assert coverage["broker"]["note_to_raw_gap_count"] == 1
    assert coverage["broker"]["uncovered_raw_institutions"] == ["丙证券"]
    assert coverage["broker"]["digest_item_count"] == 5
    assert coverage["broker"]["memo_usable_card_count"] == 2
    assert coverage["broker"]["memo_row_count"] == 2
    assert coverage["external"]["citation_source_count"] == 2
    assert coverage["external"]["narrative_paragraph_count"] == 1
    assert coverage["external"]["topic_group_count"] == 1


def test_broker_digest_loader_default_budget_matches_research_cache_width():
    ctx = SkillContext(input={})

    assert SynthesisSkill._broker_digest_loader_max_items(ctx) == 8
