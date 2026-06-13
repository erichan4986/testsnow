import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from unittest.mock import MagicMock
from skill_pipeline import SkillContext
from report_skills.synthesis_skills import SynthesisSkill


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


def test_synthesis_skill_enabled_modern_path_passes_context_to_synthesizer():
    from unittest.mock import MagicMock

    fake = FakeSynthesizer()
    skill = SynthesisSkill(synthesizer=fake)
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "enable_claim_verification_context": True,
        "claim_verification_base_dir": "knowledge",
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
