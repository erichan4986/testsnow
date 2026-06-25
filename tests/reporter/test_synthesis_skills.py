import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from unittest.mock import MagicMock
from skill_pipeline import SkillContext
from report_skills.synthesis_skills import SynthesisSkill
from source_adapter import SynthesisItem


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
    ctx = SkillContext(input={
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
    ctx = SkillContext(input={
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
    ctx = SkillContext(input={
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
            "reports": [],
            "announcements": [],
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
            "reports": [],
            "announcements": [],
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
    return SkillContext(input={
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
    ctx = SkillContext(input={
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
    ctx = SkillContext(input={
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
    ctx = SkillContext(input={
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
    ctx = SkillContext(input={
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
    ctx = SkillContext(input={
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
