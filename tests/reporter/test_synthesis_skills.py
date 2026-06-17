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


def test_fill_citation_metadata_preserves_credit_fields():
    skill = SynthesisSkill()
    items = [
        SynthesisItem(
            title="公告", content="内容", author="公司",
            source_platform="公告", url="", publish_time="",
            extra={"source_credit": 95, "source_type": "announcement", "verification_status": "primary_source"},
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
