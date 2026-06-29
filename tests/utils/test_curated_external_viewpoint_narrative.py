from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from curated_external_full_body_viewpoint_claims import normalized_hash
from curated_external_viewpoint_narrative import (
    build_viewpoint_narrative,
    llm_narrative_composer_factory,
)


def _claim(claim_id: str, text: str, title: str = "外部文章") -> dict:
    return {
        "schema_version": "curated_external_viewpoint_claim.v1",
        "claim_id": claim_id,
        "stock_name": "测试股",
        "claim_type": "watch_variable",
        "topic": "supply_delivery_capacity",
        "claim": text,
        "source_quote": text,
        "source_quote_hash": normalized_hash(text),
        "why_incremental": "baseline未覆盖该变量。",
        "baseline_overlap": "none",
        "source_id": f"source:{claim_id}",
        "source_title": title,
        "source_account": "测试公众号",
        "source_ref": f"https://mp.weixin.qq.com/s/{claim_id}",
        "verification_status": "professional_observation",
        "source_credit": 55,
        "quality_action": "preview_only",
        "knowledge_eligible": False,
        "synthesis_display_only": True,
        "scoring_eligible": False,
        "risk_score_eligible": False,
    }


def _digest(claims: list[dict]) -> dict:
    return {
        "schema_version": "curated_external_viewpoint_digest.v1",
        "status": "ok",
        "stock_name": "测试股",
        "claims": claims,
        "claims_count": len(claims),
        "stats": {"theme_coverage_count": 3, "theme_coverage_total": 7},
    }


def test_build_viewpoint_narrative_from_fake_llm_paragraphs():
    claims = [
        _claim("c1", "市场传言800G交付计划下调，公司否认但供给变量仍需跟踪。", "上游材料预付款暴涨10倍"),
        _claim("c2", "预付款项大幅增长可能提示光芯片等核心物料紧张。", "上游材料预付款暴涨10倍"),
        _claim("c3", "NPO/XPO 预计2027年量产，可能打开新的技术路径。", "光模块行业延续高景气度"),
    ]

    def composer(_claims, _baseline, _stock):
        return {
            "paragraphs": [
                {
                    "heading": "供给约束先影响交付弹性",
                    "text": "外部材料把800G交付传言与预付款变化放在同一条线索下观察：前者提示交付节奏存在待验证扰动，后者提示上游物料可能仍偏紧。因此，这组证据更像是对交付确定性的约束变量，而不是单纯的财务数字重复。",
                    "claim_refs": ["c1", "c2"],
                },
                {
                    "heading": "技术路径决定中期增量空间",
                    "text": "在交付变量之外，NPO/XPO的量产时间表提供了另一条增量主线。若客户需求指引延续，公司的基本面判断需要同时观察供应链瓶颈和下一代光互连方案的放量节奏。",
                    "claim_refs": ["c3"],
                },
            ]
        }

    result = build_viewpoint_narrative(
        _digest(claims),
        "baseline synthesis",
        composer=composer,
        stock_name="测试股",
    )

    assert result["status"] == "ok"
    assert result["paragraphs_count"] == 2
    assert result["citations"]["1"]["title"] == "上游材料预付款暴涨10倍"
    assert "- **" not in result["preview_markdown"]
    assert "供给约束先影响交付弹性" in result["preview_markdown"]
    assert "[^1][^2]" in result["preview_markdown"]
    assert "不参与评分、风险评分或最终建议" in result["preview_markdown"]


def test_build_viewpoint_narrative_rejects_unresolved_claim_ref():
    claims = [_claim("c1", "市场传言800G交付计划下调。")]

    def composer(_claims, _baseline, _stock):
        return {
            "paragraphs": [
                {
                    "heading": "无效引用",
                    "text": "这段叙事引用了不存在的观点，因此应该被安全门拒绝而不是继续渲染。",
                    "claim_refs": ["missing"],
                }
            ]
        }

    result = build_viewpoint_narrative(
        _digest(claims),
        "baseline synthesis",
        composer=composer,
        stock_name="测试股",
    )

    assert result["status"] == "invalid_narrative"
    assert "unresolved claim_ref" in result["stats"]["drop_reasons"][0]


def test_build_viewpoint_narrative_lints_overclaim_paragraphs():
    claims = [_claim("c1", "外部文章提示客户导入仍需跟踪。")]

    def composer(_claims, _baseline, _stock):
        return {
            "paragraphs": [
                {
                    "heading": "过强断言",
                    "text": "外部材料确认客户已经锁定，因此公司成长确定。",
                    "claim_refs": ["c1"],
                }
            ]
        }

    result = build_viewpoint_narrative(
        _digest(claims),
        "baseline synthesis",
        composer=composer,
        stock_name="测试股",
    )

    assert result["status"] == "lint_failed"
    assert result["preview_markdown"] == ""


def test_llm_narrative_composer_factory_parses_json():
    payload = {
        "paragraphs": [
            {
                "heading": "主线",
                "text": "外部材料提示供应链变量需要继续跟踪。",
                "claim_refs": ["c1"],
            }
        ]
    }
    client = _FakeLLMClient(json.dumps(payload, ensure_ascii=False))
    composer = llm_narrative_composer_factory(
        model="test",
        base_url="http://localhost",
        api_key="dummy",
        client=client,
        prompt_path=None,
    )

    result = composer([_claim("c1", "外部材料提示供应链变量需要继续跟踪。")], "baseline", "测试股")

    assert result["paragraphs"][0]["claim_refs"] == ["c1"]
    assert "供应链变量" in client.prompts[0]


class _FakeChatCompletions:
    def __init__(self, response_text: str, prompts: list[str]):
        self._response_text = response_text
        self._prompts = prompts

    def create(self, **kwargs):
        messages = kwargs.get("messages") or []
        if messages:
            self._prompts.append(str(messages[0].get("content") or ""))
        return _FakeResponse(self._response_text)


class _FakeChat:
    def __init__(self, response_text: str, prompts: list[str]):
        self.completions = _FakeChatCompletions(response_text, prompts)


class _FakeLLMClient:
    def __init__(self, response_text: str):
        self.prompts: list[str] = []
        self.chat = _FakeChat(response_text, self.prompts)


class _FakeResponse:
    def __init__(self, text: str):
        self.choices = [type("Choice", (), {"message": type("Message", (), {"content": text})()})]
