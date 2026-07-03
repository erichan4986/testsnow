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


def test_build_viewpoint_narrative_preserves_reasoning_cards_with_bounded_excerpt():
    claims = [
        _claim(
            "c1",
            "外部观点认为A股估值处于乐观情景上沿，需跟踪盈利修复假设。",
            "复旦微电估值分析",
        )
    ]
    long_excerpt = "估值原文片段" * 60

    def composer(_claims, _baseline, _stock):
        return {
            "paragraphs": [
                {
                    "heading": "估值分歧",
                    "text": "外部材料提示A股估值处于乐观情景上沿，需跟踪盈利修复假设。",
                    "claim_refs": ["c1"],
                }
            ],
            "reasoning_cards": [
                {
                    "claim_id": "c1",
                    "display_topic": "valuation_debate",
                    "claim": "外部观点认为A股估值处于乐观情景上沿",
                    "source_excerpt": long_excerpt,
                    "reasoning_steps": ["用同行盈利作参照", "用PE和PS交叉验证"],
                    "numbers_used": ["375-420亿", "46-52元"],
                    "assumptions": ["2026净利修复"],
                    "counterpoints": ["订单恢复不及预期"],
                    "verification_need": "跟踪半年报",
                }
            ],
        }

    result = build_viewpoint_narrative(
        _digest(claims),
        "baseline synthesis",
        composer=composer,
        stock_name="测试股",
    )

    assert result["status"] == "ok"
    card = result["reasoning_cards"][0]
    assert card["citation_refs"] == [1]
    assert len(card["source_excerpt"]) <= 200
    assert card["excerpt_truncated"] is True
    assert card["numbers_used"] == ["375-420亿", "46-52元"]


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


def test_build_viewpoint_narrative_repairs_unique_hash_suffix_claim_ref():
    full_claim_id = "curated-viewpoint:测试股:ee20044b67760ef2"
    claims = [_claim(full_claim_id, "外部材料提示客户导入节奏仍需跟踪。")]

    def composer(_claims, _baseline, _stock):
        return {
            "paragraphs": [
                {
                    "heading": "尾段引用修复",
                    "text": "外部材料提示客户导入节奏仍需跟踪，这一变量需要等待车型配置继续验证。",
                    "claim_refs": ["ee20044b67760ef2"],
                }
            ]
        }

    result = build_viewpoint_narrative(
        _digest(claims),
        "baseline synthesis",
        composer=composer,
        stock_name="测试股",
    )

    assert result["status"] == "ok"
    assert result["paragraphs"][0]["claim_refs"] == [full_claim_id]
    assert result["stats"]["claim_ref_repaired_count"] == 1
    assert result["stats"]["claim_ref_repairs"][0]["from"] == "ee20044b67760ef2"
    assert result["stats"]["claim_ref_repairs"][0]["to"] == full_claim_id


def test_build_viewpoint_narrative_rejects_ambiguous_hash_suffix_claim_ref():
    claims = [
        _claim("curated-viewpoint:测试股:duplicatehash", "外部材料提示客户导入节奏仍需跟踪。"),
        _claim("curated-viewpoint:另一股票:duplicatehash", "外部材料提示供应链变量仍需跟踪。"),
    ]

    def composer(_claims, _baseline, _stock):
        return {
            "paragraphs": [
                {
                    "heading": "歧义尾段引用",
                    "text": "外部材料提示客户导入节奏仍需跟踪，这一变量需要等待后续车型配置继续验证。",
                    "claim_refs": ["duplicatehash"],
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
    assert any("ambiguous claim_ref" in reason for reason in result["stats"]["drop_reasons"])


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


def test_build_viewpoint_narrative_drops_only_overclaim_paragraphs():
    claims = [
        _claim("c1", "外部文章提示客户导入仍需跟踪。"),
        _claim("c2", "外部文章提示代工限制仍需跟踪。"),
    ]

    def composer(_claims, _baseline, _stock):
        return {
            "paragraphs": [
                {
                    "heading": "保留的审慎段落",
                    "text": "外部材料提示客户导入节奏仍需跟踪，这一变量需要等待车型配置和量产节奏继续验证。",
                    "claim_refs": ["c1"],
                },
                {
                    "heading": "丢弃的强断言段落",
                    "text": "外部材料确认公司已锁定核心客户，因此成长路径确定。",
                    "claim_refs": ["c2"],
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
    assert result["paragraphs_count"] == 1
    assert result["stats"]["final_overclaim_dropped_count"] == 1
    assert "保留的审慎段落" in result["preview_markdown"]
    assert "丢弃的强断言段落" not in result["preview_markdown"]
    assert "锁定" not in result["preview_markdown"]


def test_build_viewpoint_narrative_lints_all_sentences_in_paragraph():
    claims = [
        _claim("c1", "外部文章提示A2000L进入客户方案仍需跟踪。"),
        _claim("c2", "外部文章提示出口管制影响高算力版本节奏。"),
    ]

    def composer(_claims, _baseline, _stock):
        return {
            "paragraphs": [
                {
                    "heading": "强词不应被段末脚注绕过",
                    "text": (
                        "外部信息显示A2000L或已锁定核心客户。"
                        "另一线索提示出口管制影响高算力版本节奏。"
                    ),
                    "claim_refs": ["c1", "c2"],
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
    assert any("锁定" in reason for reason in result["stats"]["drop_reasons"])


def test_build_viewpoint_narrative_rejects_unseen_model_tokens():
    claims = [
        _claim("c1", "外部文章提示C1296可能进入低价车型。", "C1296 车型线索"),
        _claim("c2", "外部文章提示A2000L客户导入仍需跟踪。", "A2000L 导入线索"),
    ]

    def composer(_claims, _baseline, _stock):
        return {
            "paragraphs": [
                {
                    "heading": "型号幻觉",
                    "text": "外部材料提示C1236和A2000L的推进仍需继续观察。",
                    "claim_refs": ["c1", "c2"],
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
    assert any("unsupported_model_token:C1236" in reason for reason in result["stats"]["drop_reasons"])


def test_build_viewpoint_narrative_rejects_unsupported_quantitative_claims():
    claims = [_claim("c1", "外部文章提示研发费用收缩可能影响技术投入。")]

    def composer(_claims, _baseline, _stock):
        return {
            "paragraphs": [
                {
                    "heading": "新增比例幻觉",
                    "text": "外部材料提示公司营收体量仅为地平线的约1/4，因此后续竞争仍需观察。",
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

    assert result["status"] == "invalid_narrative"
    assert any("unsupported_quantity:1/4" in reason for reason in result["stats"]["drop_reasons"])


def test_build_viewpoint_narrative_allows_supported_quantitative_claims():
    claims = [
        _claim("c1", "外部文章提示国产化率30%-40%传闻仍需跟踪。"),
        _claim("c2", "外部文章提示研发费用同比下降13.42%，研发费用率为0.99%。"),
        _claim("c3", "外部文章提示TTP 9000 与 4800 的代工限制差异。"),
    ]

    def composer(_claims, _baseline, _stock):
        return {
            "paragraphs": [
                {
                    "heading": "数字均有来源",
                    "text": (
                        "外部材料提示国产化率30%-40%传闻仍需跟踪；"
                        "研发费用同比下降13.42%、费用率0.99%，"
                        "同时TTP 9000与4800的代工限制差异可能影响高算力版本节奏。"
                    ),
                    "claim_refs": ["c1", "c2", "c3"],
                }
            ]
        }

    result = build_viewpoint_narrative(
        _digest(claims),
        "baseline synthesis",
        composer=composer,
        stock_name="测试股",
    )

    assert result["status"] == "ok"
    assert not any("unsupported_quantity" in reason for reason in result["stats"]["drop_reasons"])


def test_build_viewpoint_narrative_allows_model_like_stock_name():
    claims = [_claim("c1", "外部文章提示客户车型放量仍需跟踪。")]

    def composer(_claims, _baseline, _stock):
        return {
            "paragraphs": [
                {
                    "heading": "股票名含字母数字",
                    "text": "外部材料提示TEST123的客户车型放量仍需跟踪。",
                    "claim_refs": ["c1"],
                }
            ]
        }

    result = build_viewpoint_narrative(
        _digest(claims),
        "baseline synthesis",
        composer=composer,
        stock_name="TEST123",
    )

    assert result["status"] == "ok"
    assert "unsupported_model_token" not in " ".join(result["stats"]["drop_reasons"])


def test_build_viewpoint_narrative_uses_social_source_label():
    claim = _claim("c1", "雪球长文提示客户车型放量仍需跟踪。")
    claim["source_kind"] = "social_xueqiu"
    claim["source_platform"] = "xueqiu"
    claim["source_ref"] = "https://xueqiu.com/1/2"

    def composer(_claims, _baseline, _stock):
        return {
            "paragraphs": [
                {
                    "heading": "社媒来源标签",
                    "text": "外部材料提示客户车型放量仍需跟踪，这一变量需要等待后续车型配置和交付节奏验证。",
                    "claim_refs": ["c1"],
                }
            ]
        }

    result = build_viewpoint_narrative(
        _digest([claim]),
        "baseline synthesis",
        composer=composer,
        stock_name="测试股",
    )

    assert result["status"] == "ok"
    assert result["citations"]["1"]["source"] == "雪球精选观察"
    assert "微信公众号精选观察" not in result["preview_markdown"]


def test_build_viewpoint_narrative_distinguishes_xueqiu_column_and_reply_labels():
    column_claim = _claim("c1", "雪球专栏提示客户车型放量仍需跟踪。", "来自雪球 专栏 公司深度分析")
    column_claim["source_kind"] = "social_xueqiu"
    column_claim["source_platform"] = "xueqiu"
    column_claim["source_ref"] = "https://xueqiu.com/1/column"
    reply_claim = _claim("c2", "雪球回复提示代工限制仍需跟踪。", "来自Android 回复@用户: 机构调研信息")
    reply_claim["source_kind"] = "social_xueqiu"
    reply_claim["source_platform"] = "xueqiu"
    reply_claim["source_ref"] = "https://xueqiu.com/1/reply"

    def composer(_claims, _baseline, _stock):
        return {
            "paragraphs": [
                {
                    "heading": "社媒来源分层",
                    "text": "外部材料提示客户车型放量与代工限制都仍需继续跟踪。",
                    "claim_refs": ["c1", "c2"],
                }
            ]
        }

    result = build_viewpoint_narrative(
        _digest([column_claim, reply_claim]),
        "baseline synthesis",
        composer=composer,
        stock_name="测试股",
    )

    assert result["status"] == "ok"
    assert result["citations"]["1"]["source"] == "雪球专栏观察"
    assert result["citations"]["2"]["source"] == "雪球评论观察"


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


def test_llm_narrative_prompt_requires_dynamic_planner_before_writer():
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

    composer([_claim("c1", "外部材料提示供应链变量需要继续跟踪。")], "baseline", "测试股")

    prompt = client.prompts[0]
    assert "先做叙事规划" in prompt
    assert "2-4条" in prompt
    assert "不要平均分配 claims" in prompt
    assert "不要硬套固定分类" in prompt
    assert "不得计算、换算、推导或概括任何数字" in prompt
    assert "不得生成 claims 中未逐字出现的比例" in prompt
    assert "车型落地" not in prompt
    assert "换芯动因" not in prompt


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
