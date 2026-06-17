"""Tests for periodic_report_llm_analysis helper."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_llm_analysis import (
    SCHEMA_VERSION,
    PeriodicReportLLMError,
    build_periodic_report_llm_prompt,
    render_periodic_report_llm_markdown,
    summarize_periodic_report_with_llm,
    validate_periodic_report_llm_output,
)


SAMPLE_EXTRACTOR_RESULT = {
    "schema_version": "periodic_report_extractor.v1",
    "report_type": "annual_report",
    "audit_status": "audited",
    "industry": "hardtech",
    "items": [
        {
            "usage": "financial_forensics",
            "severity": "high",
            "title": "应收账款增速显著高于营收增速",
            "evidence": "营业收入同比约4.14%，应收账款同比约-10.06%。",
            "interpretation": "营收增长可能伴随信用政策放宽或回款质量下降。",
        },
        {
            "usage": "management_view",
            "severity": "info",
            "title": "管理层行业判断",
            "evidence": "行业由规模竞争转向价值竞争，高端产品国产化提速。",
            "interpretation": "管理层观点可用于理解公司叙事。",
        },
        {
            "usage": "risk_disclosure",
            "severity": "medium",
            "title": "公司披露的重大风险",
            "evidence": "公司面临客户集中、产品价格下降、技术迭代及供应链波动风险。",
            "interpretation": "应与管理层展望交叉验证。",
        },
        {
            "usage": "capital_action",
            "severity": "info",
            "title": "CAPEX 与产能建设",
            "evidence": "近年来公司持续加大项目投入，固定资产上升较快。",
            "interpretation": "需要与现金流和产能利用率交叉验证。",
        },
    ],
}


class FakeChatClient:
    """Fake LLM client implementing .chat(prompt)."""

    def __init__(self, response_text: str):
        self.response_text = response_text

    def chat(self, prompt: str) -> str:
        return self.response_text


class FakeCompletionClient:
    """Fake LLM client implementing .chat.completions.create(...)."""

    def __init__(self, response_text: str):
        self.response_text = response_text

    class _Completions:
        def __init__(self, response_text: str):
            self.response_text = response_text

        def create(self, **kwargs):
            return {"choices": [{"message": {"content": self.response_text}}]}

    @property
    def chat(self):
        return self._Wrapper(self._Completions(self.response_text))

    class _Wrapper:
        def __init__(self, completions):
            self.completions = completions


def _valid_llm_response() -> str:
    return json.dumps({
        "schema_version": SCHEMA_VERSION,
        "report_type": "annual_report",
        "audit_status": "audited",
        "sections": [
            {
                "usage": "financial_red_flag",
                "title": "营收与应收剪刀差",
                "summary": "年报规则摘录显示营收与应收账款变动方向存在差异，需复核账龄与回款。",
                "evidence_refs": ["financial_forensics-0"],
                "confidence": 70,
            },
            {
                "usage": "management_narrative",
                "title": "管理层对行业竞争的判断",
                "summary": "年报称行业由规模竞争转向价值竞争，该表述属于管理层叙事。",
                "evidence_refs": ["management_view-2"],
                "confidence": 65,
            },
        ],
        "follow_up_questions": [
            {
                "question": "应收账款回款质量是否会在后续季度改善？",
                "evidence_refs": ["financial_forensics-0"],
            }
        ],
    })


def test_prompt_includes_extractor_items_and_not_full_report_text():
    prompt = build_periodic_report_llm_prompt(SAMPLE_EXTRACTOR_RESULT)
    user = prompt["user"]

    assert "financial_forensics-0" in user
    assert "management_view-2" in user
    assert "营业收入同比约4.14%" in user
    assert "行业由规模竞争转向价值竞争" in user
    # Full report text is not present.
    assert "第十节 财务报告" not in user
    assert "审计意见" not in user


def test_prompt_caps_item_count_and_evidence_length():
    many_items = []
    for i in range(30):
        many_items.append({
            "usage": "capital_action",
            "severity": "info",
            "title": f"事项{i}",
            "evidence": "x" * 1000,
        })
    result = {**SAMPLE_EXTRACTOR_RESULT, "items": many_items}
    prompt = build_periodic_report_llm_prompt(result)
    item_map = prompt["item_map"]

    assert len(item_map) <= 20
    # Evidence in the rendered prompt is truncated to <= 700 chars.
    evidence_in_prompt = prompt["user"].split("evidence: ")[1].split("\n")[0]
    assert len(evidence_in_prompt) <= 700


def test_prompt_prioritizes_financial_forensics_and_risk():
    items = [
        {"usage": "capital_action", "severity": "info", "title": "capex", "evidence": "a"},
        {"usage": "risk_disclosure", "severity": "medium", "title": "risk", "evidence": "b"},
        {"usage": "financial_forensics", "severity": "high", "title": "forensics", "evidence": "c"},
        {"usage": "management_view", "severity": "info", "title": "view", "evidence": "d"},
    ]
    result = {**SAMPLE_EXTRACTOR_RESULT, "items": items}
    prompt = build_periodic_report_llm_prompt(result, max_items=2)
    ids = list(prompt["item_map"].keys())

    assert ids[0].startswith("financial_forensics")
    assert ids[1].startswith("risk_disclosure")


def test_prompt_includes_forbidden_literal_markers():
    prompt = build_periodic_report_llm_prompt(SAMPLE_EXTRACTOR_RESULT)
    system = prompt["system"]

    assert "confirmed_fact" in system
    assert "fact_candidate" in system
    assert "核心事实" in system
    assert "已证实" in system
    assert "[^1]" in system
    assert "[^verified]" in system
    assert "[^supported]" in system
    assert "[^needs_review]" in system
    assert "[^unverified]" in system
    # Should not contain regex notation like [^\w+].
    assert r"[^\w+]" not in system


def test_prompt_mentions_section_and_question_caps():
    prompt = build_periodic_report_llm_prompt(SAMPLE_EXTRACTOR_RESULT)
    system = prompt["system"]

    assert "sections 最多 8 条" in system
    assert "follow_up_questions 最多 8 条" in system


def test_validate_accepts_valid_json_with_valid_refs():
    prompt = build_periodic_report_llm_prompt(SAMPLE_EXTRACTOR_RESULT)
    raw = _valid_llm_response()
    validated = validate_periodic_report_llm_output(raw, prompt["item_map"])

    assert validated["schema_version"] == SCHEMA_VERSION
    assert len(validated["sections"]) == 2
    assert validated["sections"][0]["evidence_refs"] == ["financial_forensics-0"]
    assert len(validated["follow_up_questions"]) == 1


def test_validate_rejects_schema_mismatch():
    prompt = build_periodic_report_llm_prompt(SAMPLE_EXTRACTOR_RESULT)
    raw = json.dumps({"schema_version": "wrong.version"})

    with pytest.raises(PeriodicReportLLMError, match="schema_version mismatch"):
        validate_periodic_report_llm_output(raw, prompt["item_map"])


def test_validate_rejects_invalid_evidence_refs():
    prompt = build_periodic_report_llm_prompt(SAMPLE_EXTRACTOR_RESULT)
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "sections": [{
            "usage": "financial_red_flag",
            "title": "x",
            "summary": "含有中文的无效引用描述。",
            "evidence_refs": ["nonexistent-0"],
            "confidence": 70,
        }],
        "follow_up_questions": [],
    })

    with pytest.raises(PeriodicReportLLMError, match="invalid evidence_refs"):
        validate_periodic_report_llm_output(raw, prompt["item_map"])


def test_validate_rejects_mixed_valid_and_invalid_section_refs():
    prompt = build_periodic_report_llm_prompt(SAMPLE_EXTRACTOR_RESULT)
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "sections": [
            {
                "usage": "financial_red_flag",
                "title": "valid",
                "summary": "有效引用的中文描述。",
                "evidence_refs": ["financial_forensics-0"],
                "confidence": 70,
            },
            {
                "usage": "management_narrative",
                "title": "invalid",
                "summary": "无效引用的中文描述。",
                "evidence_refs": ["missing-ref"],
                "confidence": 70,
            },
        ],
        "follow_up_questions": [],
    })

    with pytest.raises(PeriodicReportLLMError, match="invalid evidence_refs"):
        validate_periodic_report_llm_output(raw, prompt["item_map"])


def test_validate_rejects_mixed_valid_and_invalid_question_refs():
    prompt = build_periodic_report_llm_prompt(SAMPLE_EXTRACTOR_RESULT)
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "sections": [{
            "usage": "financial_red_flag",
            "title": "valid",
            "summary": "有效引用的中文描述。",
            "evidence_refs": ["financial_forensics-0"],
            "confidence": 70,
        }],
        "follow_up_questions": [
            {
                "question": "有效问题？",
                "evidence_refs": ["financial_forensics-0"],
            },
            {
                "question": "无效问题？",
                "evidence_refs": ["missing-ref"],
            },
        ],
    })

    with pytest.raises(PeriodicReportLLMError, match="invalid evidence_refs"):
        validate_periodic_report_llm_output(raw, prompt["item_map"])


def test_validate_rejects_illegal_citation_markers():
    prompt = build_periodic_report_llm_prompt(SAMPLE_EXTRACTOR_RESULT)
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "sections": [{
            "usage": "financial_red_flag",
            "title": "x",
            "summary": "营收增长[^1]，但应收增加。",
            "evidence_refs": ["financial_forensics-0"],
            "confidence": 70,
        }],
        "follow_up_questions": [],
    })

    with pytest.raises(PeriodicReportLLMError, match="no valid sections"):
        validate_periodic_report_llm_output(raw, prompt["item_map"])


def test_validate_rejects_confirmed_fact_and_fact_candidate():
    prompt = build_periodic_report_llm_prompt(SAMPLE_EXTRACTOR_RESULT)
    for bad in ["confirmed_fact", "fact_candidate"]:
        raw = json.dumps({
            "schema_version": SCHEMA_VERSION,
            "sections": [{
                "usage": "financial_red_flag",
                "title": bad,
                "summary": "summary here",
                "evidence_refs": ["financial_forensics-0"],
                "confidence": 70,
            }],
            "follow_up_questions": [],
        })

        with pytest.raises(PeriodicReportLLMError, match="illegal content"):
            validate_periodic_report_llm_output(raw, prompt["item_map"])


def test_validate_drops_section_with_confidence_out_of_range():
    prompt = build_periodic_report_llm_prompt(SAMPLE_EXTRACTOR_RESULT)
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "sections": [
            {
                "usage": "financial_red_flag",
                "title": "ok",
                "summary": "正常的中文描述。",
                "evidence_refs": ["financial_forensics-0"],
                "confidence": 120,
            },
            {
                "usage": "financial_red_flag",
                "title": "negative",
                "summary": "过低的中文描述。",
                "evidence_refs": ["financial_forensics-0"],
                "confidence": -1,
            },
        ],
        "follow_up_questions": [],
    })

    with pytest.raises(PeriodicReportLLMError, match="no valid sections"):
        validate_periodic_report_llm_output(raw, prompt["item_map"])


def test_validate_rejects_follow_up_question_as_section_usage():
    prompt = build_periodic_report_llm_prompt(SAMPLE_EXTRACTOR_RESULT)
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "sections": [{
            "usage": "follow_up_question",
            "title": "q",
            "summary": "问题描述？",
            "evidence_refs": ["financial_forensics-0"],
            "confidence": 70,
        }],
        "follow_up_questions": [],
    })

    with pytest.raises(PeriodicReportLLMError, match="no valid sections"):
        validate_periodic_report_llm_output(raw, prompt["item_map"])


def test_summarize_returns_credit_and_status_metadata_with_fake_chat_client():
    client = FakeChatClient(_valid_llm_response())
    result = summarize_periodic_report_with_llm(SAMPLE_EXTRACTOR_RESULT, client)

    assert result["source_type"] == "periodic_report_analysis"
    assert result["source_credit"] == 75
    assert result["verification_status"] == "professional_analysis"
    assert result["claim_status"] == "professional_analysis"
    assert result["knowledge_eligible"] is False
    assert result["report_eligible"] is True
    assert result["schema_version"] == SCHEMA_VERSION


def test_summarize_keeps_extractor_report_metadata_over_llm_metadata():
    raw = json.loads(_valid_llm_response())
    raw["report_type"] = "unknown"
    raw["audit_status"] = "unknown"
    client = FakeChatClient(json.dumps(raw))

    result = summarize_periodic_report_with_llm(SAMPLE_EXTRACTOR_RESULT, client)

    assert result["report_type"] == "annual_report"
    assert result["audit_status"] == "audited"


def test_summarize_returns_empty_analysis_for_empty_extractor_result():
    client = FakeChatClient(_valid_llm_response())
    result = summarize_periodic_report_with_llm({"items": []}, client)

    assert result["sections"] == []
    assert result["follow_up_questions"] == []
    assert result["source_credit"] == 75
    assert result["verification_status"] == "professional_analysis"


def test_summarize_works_with_completion_style_client():
    client = FakeCompletionClient(_valid_llm_response())
    result = summarize_periodic_report_with_llm(SAMPLE_EXTRACTOR_RESULT, client)

    assert len(result["sections"]) == 2
    assert result["source_credit"] == 75


def test_render_markdown_contains_no_numbered_citations():
    result = summarize_periodic_report_with_llm(
        SAMPLE_EXTRACTOR_RESULT, FakeChatClient(_valid_llm_response())
    )
    md = render_periodic_report_llm_markdown(result)

    assert "# 年报/半年报 LLM 分析预览" in md
    assert "营收与应收剪刀差" in md
    assert "[^" not in md
    assert "[1]" not in md


def test_import_does_not_require_openai_or_deepseek():
    """Import the helper in a subprocess with no LLM packages; must succeed."""
    helper_path = Path(__file__).parent.parent.parent / "scripts" / "utils"
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(helper_path)!r})\n"
        "sys.modules['openai'] = None\n"
        "sys.modules['deepseek'] = None\n"
        "import periodic_report_llm_analysis\n"
        "print('ok')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout
