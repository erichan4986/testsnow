import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from report_quality import check_report_file, check_report_text


def _snapshot_row(**overrides):
    data = {
        "row_id": "external:argument_cards:reasoning:0",
        "text": "外部观点A",
        "source_layer": "external",
        "claim_status": "external_observation",
        "citation_refs": (1,),
        "source_ref_ids": ("external-source:1",),
        "display_scope": ("deep_analysis",),
        "scoring_eligible": False,
        "risk_score_eligible": False,
        "section_hint": "external_map",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _snapshot(rows, citations=None):
    return SimpleNamespace(
        schema="deep_analysis_material_snapshot.v1",
        rows=tuple(rows),
        citations=citations or {1: {"source": "微信公众号精选观察", "title": "外部材料"}},
        diagnostics={},
    )


def test_minimal_quality_report_passes():
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    result = check_report_file(fixture)
    assert result.passed
    assert result.issues == []


def test_deep_report_empty_executive_summary_body_fails():
    text = """# 测试股 舆情深度报告

## 执行摘要

### 综合评分: 6.0/10 | EV: N/A（持有）

### 核心投资论点

**基本面判断**：

**估值与业绩预期**：

**交易状态与风险**：

> **一句话结论**：

### 多空论点对比

![多空图](chart.png)

## 一、综合评分与推荐
"""
    result = check_report_text(text)
    issue = next(i for i in result.issues if i.code == "empty_executive_summary_body")
    assert issue.severity == "error"


def test_deep_report_missing_executive_summary_fails():
    text = """# 测试股 舆情深度报告

## 一、综合评分与推荐

### 综合评分: 6.0/10 | EV: N/A（持有）
"""
    result = check_report_text(text)
    issue = next(i for i in result.issues if i.code == "empty_executive_summary_body")
    assert issue.severity == "error"


def test_deep_report_deterministic_executive_summary_body_passes_gate():
    text = """# 测试股 舆情深度报告

## 执行摘要

### 综合评分: 6.0/10 | EV: N/A（持有）

### 核心投资论点

**基本面判断**：当前基本面评分为 6/10。

## 一、综合评分与推荐
"""
    result = check_report_text(text)
    assert "empty_executive_summary_body" not in {i.code for i in result.issues}


def test_deep_report_image_first_executive_summary_body_passes_gate():
    text = """# 测试股 舆情深度报告

## 执行摘要

> **一句话结论**：谨慎持有，等待趋势确认。

![测试股 投资决策链](测试股_20260719_decision.png)

## 一、综合评分与推荐

### 综合评分: 5.3/10 | EV: +8.00%（谨慎持有）
"""
    result = check_report_text(text)
    assert "empty_executive_summary_body" not in {i.code for i in result.issues}


def test_freshness_summary_line_requires_preview_boundary_and_resolved_refs():
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    line = (
        "**近期待验证变量**：外部材料称，客户订单节奏出现变化[^4]"
        "（外部待验证，不替代官方确认，不参与评分、风险评分或目标价）。"
    )
    text = fixture.read_text(encoding="utf-8").replace(
        "## 技术面分析：中期趋势提醒", f"{line}\n\n## 技术面分析：中期趋势提醒", 1,
    ) + "\n## 引用来源\n\n- [^4] 微信公众号精选观察 | 《订单观察》\n"
    result = check_report_text(text)
    assert "freshness_summary_boundary" not in {issue.code for issue in result.issues}


def test_freshness_summary_line_rejects_confirmation_language():
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    line = (
        "**近期待验证变量**：外部材料称，订单已落地[^4]"
        "（外部待验证，不替代官方确认，不参与评分、风险评分或目标价）。"
    )
    text = fixture.read_text(encoding="utf-8").replace(
        "## 技术面分析：中期趋势提醒", f"{line}\n\n## 技术面分析：中期趋势提醒", 1,
    ) + "\n## 引用来源\n\n- [^4] 微信公众号精选观察 | 《订单观察》\n"
    result = check_report_text(text)
    assert "freshness_summary_unverified_confirmation" in {issue.code for issue in result.issues}


def test_freshness_summary_line_outside_executive_summary_fails():
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    text = fixture.read_text(encoding="utf-8") + (
        "\n**近期待验证变量**：外部材料称，客户订单节奏出现变化[^4]"
        "（外部待验证，不替代官方确认，不参与评分、风险评分或目标价）。\n"
        "\n## 引用来源\n\n- [^4] 微信公众号精选观察 | 《订单观察》\n"
    )

    result = check_report_text(text)

    assert "freshness_summary_outside_executive_summary" in {
        issue.code for issue in result.issues
    }


def test_freshness_summary_line_repeated_outside_executive_summary_fails():
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    line = (
        "**近期待验证变量**：外部材料称，客户订单节奏出现变化[^4]"
        "（外部待验证，不替代官方确认，不参与评分、风险评分或目标价）。"
    )
    text = fixture.read_text(encoding="utf-8").replace(
        "## 技术面分析：中期趋势提醒", f"{line}\n\n## 技术面分析：中期趋势提醒", 1,
    ) + f"\n{line}\n\n## 引用来源\n\n- [^4] 微信公众号精选观察 | 《订单观察》\n"

    result = check_report_text(text)

    assert "freshness_summary_outside_executive_summary" in {
        issue.code for issue in result.issues
    }


def test_lightweight_report_is_outside_executive_summary_body_contract():
    text = """# 测试股

## 执行摘要

### 综合评分: 6.0/10 | EV: N/A（持有）

## 技术面分析
"""
    result = check_report_text(text)
    assert "empty_executive_summary_body" not in {i.code for i in result.issues}


def test_material_snapshot_unresolved_ref_fails():
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    result = check_report_text(
        fixture.read_text(encoding="utf-8"),
        deep_analysis_material_snapshot=_snapshot([
            _snapshot_row(citation_refs=(9,)),
        ]),
    )
    codes = {issue.code for issue in result.issues}
    assert "deep_material_snapshot_unresolved_ref" in codes


def test_material_snapshot_external_row_without_citation_refs_fails():
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    text = fixture.read_text(encoding="utf-8") + "\n\n### 4.3 外部观点与待验证变量（Preview，不参与评分）\n\n**外部观点链**：外部材料称：外部观点A；该说法需以公告验证\n"
    result = check_report_text(
        text,
        deep_analysis_material_snapshot=_snapshot([
            _snapshot_row(text="外部观点A", citation_refs=()),
        ]),
    )
    codes = {issue.code for issue in result.issues}
    assert "deep_material_snapshot_external_missing_citation" in codes


def test_material_snapshot_malformed_citation_key_fails():
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    result = check_report_text(
        fixture.read_text(encoding="utf-8"),
        deep_analysis_material_snapshot=_snapshot([], citations={"bad-ref": {"source": "年报"}}),
    )
    codes = {issue.code for issue in result.issues}
    assert "deep_material_snapshot_malformed_citation_key" in codes


def test_material_snapshot_non_deep_scope_fails():
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    result = check_report_text(
        fixture.read_text(encoding="utf-8"),
        deep_analysis_material_snapshot=_snapshot([
            _snapshot_row(display_scope=("executive_summary",)),
        ]),
    )
    codes = {issue.code for issue in result.issues}
    assert "deep_material_snapshot_invalid_scope" in codes


def test_material_snapshot_external_scoring_leak_fails():
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    result = check_report_text(
        fixture.read_text(encoding="utf-8"),
        deep_analysis_material_snapshot=_snapshot([
            _snapshot_row(scoring_eligible=True),
        ]),
    )
    codes = {issue.code for issue in result.issues}
    assert "deep_material_snapshot_external_scoring_leak" in codes


def test_material_snapshot_framed_external_row_passes_snapshot_gate():
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    text = fixture.read_text(encoding="utf-8") + "\n\n### 4.3 外部观点与待验证变量（Preview，不参与评分）\n\n**外部观点链**：外部材料称：外部观点A；该说法需以公告验证[^1]\n"
    result = check_report_text(
        text,
        deep_analysis_material_snapshot=_snapshot([
            _snapshot_row(text="外部观点A"),
        ]),
    )
    codes = {issue.code for issue in result.issues}
    assert not {code for code in codes if code.startswith("deep_material_snapshot_")}


def test_material_snapshot_visible_unframed_external_row_fails():
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    text = fixture.read_text(encoding="utf-8") + "\n\n### 4.3 外部观点与待验证变量\n\nFPGA市占率95%以上[^1]\n"
    result = check_report_text(
        text,
        deep_analysis_material_snapshot=_snapshot([
            _snapshot_row(text="FPGA市占率95%以上"),
        ]),
    )
    codes = {issue.code for issue in result.issues}
    assert "deep_material_snapshot_external_unframed" in codes


def test_check_report_file_does_not_run_snapshot_gates(tmp_path):
    """check_report_file is Markdown-only and must not inspect in-memory snapshots."""
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    report_path = tmp_path / "report.md"
    report_path.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    # Place a malformed snapshot sidecar to prove it is ignored by check_report_file.
    sidecar = tmp_path / "report_deep_analysis_material_snapshot.json"
    sidecar.write_text(json.dumps({"citations": {"bad-key": {}}}), encoding="utf-8")

    result = check_report_file(report_path)
    snapshot_codes = {issue.code for issue in result.issues if issue.code.startswith("deep_material_snapshot_")}
    assert not snapshot_codes


def test_global_citation_table_missing_visible_refs_fails():
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    text = fixture.read_text(encoding="utf-8") + "\n\n## 四、深度分析\n\n正文使用外部引用[^2]\n\n## 引用来源\n\n- [^1] | **公告** | 《年报》\n"
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "global_citation_missing_refs" in codes


def test_global_citation_table_unused_refs_fails():
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    text = fixture.read_text(encoding="utf-8") + "\n\n## 四、深度分析\n\n正文使用正式引用[^1]\n\n## 引用来源\n\n- [^1] | **公告** | 《年报》\n- [^2] | **雪球精选观察** | 《未使用》\n"
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "global_citation_unused_refs" in codes


def test_malformed_citation_marker_fails():
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    text = fixture.read_text(encoding="utf-8") + "\n\n## 四、深度分析\n\n外部变量被截断为坏引用[^11...\n\n## 引用来源\n\n- [^11] | **知乎精选观察** | 《外部观点》\n"
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "malformed_citation_marker" in codes


def test_valid_multi_digit_citation_marker_does_not_trigger_malformed_gate():
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    text = fixture.read_text(encoding="utf-8") + "\n\n## 四、深度分析\n\n正文使用外部引用[^10]\n\n## 引用来源\n\n- [^10] | **知乎精选观察** | 《外部观点》\n"
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "malformed_citation_marker" not in codes


def test_missing_required_sections_fails():
    result = check_report_text("# 测试股\n\n只有标题。")
    codes = {issue.code for issue in result.issues}
    assert not result.passed
    assert "missing_trend" in codes
    assert "missing_risk" in codes
    assert "missing_score" in codes


def test_weak_trend_high_score_contradiction_fails():
    text = """
# 测试股 舆情深度报告

## 技术面分析：中期趋势提醒

**分析可信度**：中

### 1. 趋势背景
- 周线大背景：单边下跌

### 2. 日线结构
- MA20 方向：向下
- 价格位置：跌破MA60

当前处于【下降趋势 / 破坏期】，趋势健康度【35/100，D】。

| 维度 | 得分 | 说明 |
|------|------|------|
| 成交量确认 | 4/10 | 缩量 |
| 波动率条件 | 4/10 | BOLL开口，ATR高波动 |

### 综合评分: 8.6/10 | EV: +9.00%（强烈看多）

| 维度 | 权重 | 得分(0-10) | 说明 |
|------|------|------------|------|
| 技术面强度(M) | 25% | 8.5 | RSI 55, MACD 1.2 |

## 综合风险评分
### 风险等级: 6.0/10（高风险）
## 风险提示与关注要点
- 趋势失效后应降低仓位。
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert not result.passed
    assert "contradiction_weak_trend_high_total_score" in codes
    assert "contradiction_weak_trend_high_technical_score" in codes
    assert "contradiction_low_trend_health_high_total_score" in codes


def test_blocked_entry_strong_recommendation_warns():
    text = """
# 圣邦股份 舆情深度报告

## 执行摘要

**基本面判断**：当前基本面评分为 6/10。

## 一、综合评分与推荐

### 综合评分: 7.5/10 | EV: +10.25%（强烈看多）

> **AI 综合推荐**：**强烈看多** — 加权 EV +10.25%。

## 技术面分析：中期趋势提醒

**分析可信度**：中

### 1. 趋势背景
- 周线大背景：单边上涨
- MA 结构：MA5>MA10>MA20

### 2. 日线结构
- MA20 方向：向上
- 价格位置：站上MA20
- 成交量：量能正常
- 波动率条件：BOLL正常

**当前状态**：关注/不操作（形态存在但盈亏比不足（1.06:1），等待更好的入场点）
**结论**：趋势仍可跟踪。但当前不适合追高。
**主要风险**：【BIAS偏高】

## 综合风险评分
### 风险等级: 2.0/10（低风险）
> **仓位建议**: 积极配置，最大仓位 20%

## 风险提示与关注要点
- 追高风险需关注。
"""

    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert result.passed
    assert "contradiction_blocked_entry_strong_recommendation" in codes


def test_tempered_entry_guardrail_report_has_no_blocked_entry_warning():
    text = """
# 圣邦股份 舆情深度报告

## 一、综合评分与推荐

### 综合评分: 6.5/10 | EV: +7.66%（看多但等待入场）

> **AI 综合推荐**：**看多但等待入场** — 加权 EV +7.66%。技术面提示当前不适合追高，需等待回调或盈亏比改善。

## 技术面分析：中期趋势提醒

**分析可信度**：中

### 1. 趋势背景
- 周线大背景：单边上涨
- MA 结构：MA5>MA10>MA20

### 2. 日线结构
- MA20 方向：向上
- 价格位置：站上MA20
- 成交量：量能正常
- 波动率条件：BOLL正常

**当前状态**：关注/不操作（形态存在但盈亏比不足（1.06:1），等待更好的入场点）
**主要风险**：【BIAS偏高】

## 综合风险评分
### 风险等级: 2.0/10（低风险）
> **仓位建议**: 当前入场质量不足，建议等待回调或盈亏比改善，仓位 5-10%
> **入场约束**: 技术面提示关注/不操作或追高风险，仓位建议已按入场质量降级。

## 风险提示与关注要点
- 追高风险需关注。
"""

    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "contradiction_blocked_entry_strong_recommendation" not in codes


# ---------------------------------------------------------------------------
# Recommendation / EV / entry / risk consistency gates
# ---------------------------------------------------------------------------


def test_ev_na_percent_is_error():
    text = """
# 测试股 舆情深度报告

## 执行摘要

### 综合评分: 4.1/10 | EV: N/A%（N/A）

## 一、综合评分与推荐

### 综合评分: 4.1/10 | EV: N/A%（N/A）

## 综合风险评分
### 风险等级: 2.0/10（低风险）
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "ev_na_percent" in codes


def test_summary_section1_mismatch_is_error():
    text = """
# 测试股 舆情深度报告

## 执行摘要

### 综合评分: 6.2/10 | EV: +49.83%（N/A）

## 一、综合评分与推荐

### 综合评分: 6.2/10 | EV: +49.83%（强烈看多）

## 综合风险评分
### 风险等级: 2.0/10（低风险）
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "summary_score_label_mismatch" in codes


def test_summary_section1_match_passes():
    text = """
# 测试股 舆情深度报告

## 执行摘要

### 综合评分: 6.2/10 | EV: +49.83%（看多但等待入场）

## 一、综合评分与推荐

### 综合评分: 6.2/10 | EV: +49.83%（看多但等待入场）

## 综合风险评分
### 风险等级: 2.0/10（低风险）
> **仓位建议**: 当前入场质量不足，建议等待回调或盈亏比改善，仓位 5-10%
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "summary_score_label_mismatch" not in codes
    assert "risk_position_label_mismatch" not in codes


def _quality_shell(deep_analysis: str) -> str:
    return f"""
# 测试股 舆情深度报告

## 执行摘要
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

{deep_analysis}

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常，波动率 BOLL 正常。分析可信度：中。

## 综合风险评分
### 风险等级: 3.0/10（中风险）

## 风险提示与关注要点
- 风险因子需跟踪。
"""


def test_section_too_generic_warns_only_when_specific_content_missing():
    generic = _quality_shell(
        """
### 4.1 产业逻辑与竞争格局

供应链位置重要，后续需关注验证变量，产业链景气度有望带来结构性机会。

### 4.2 业绩路径与多空分歧

收入变化原因来自FPGA产品放量[^1]。

### 4.3 资金面与催化剂时间线

当前未取得可用主力资金流向数据。
"""
    )
    specific = _quality_shell(
        """
### 4.1 产业逻辑与竞争格局

供应链位置仍需关注，但FPGA产品在2025年收入增长25%，该变量已有引用支撑[^1]。

### 4.2 业绩路径与多空分歧

收入变化原因来自FPGA产品放量[^1]。

### 4.3 资金面与催化剂时间线

当前未取得可用主力资金流向数据。
"""
    )

    generic_codes = {issue.code for issue in check_report_text(generic).issues}
    specific_codes = {issue.code for issue in check_report_text(specific).issues}

    assert "section_too_generic" in generic_codes
    assert "section_too_generic" not in specific_codes


def test_vague_supply_chain_position_warns_when_no_operating_variable():
    text = _quality_shell(
        """
### 4.1 产业逻辑与竞争格局

公司供应链位置突出，产业链地位重要，后续需关注。

### 4.2 业绩路径与多空分歧

收入变化原因来自FPGA产品放量[^1]。

### 4.3 资金面与催化剂时间线

当前未取得可用主力资金流向数据。
"""
    )

    codes = {issue.code for issue in check_report_text(text).issues}

    assert "vague_supply_chain_position" in codes


def test_fundamentals_repeats_core_facts_without_explanation_warns():
    text = _quality_shell(
        """
### 4.1 产业逻辑与竞争格局

FPGA产品仍是核心变量[^1]。

### 4.2 业绩路径与多空分歧

营业收入39.82亿元，归母净利润2.32亿元，综合毛利率56.19%。

### 4.3 资金面与催化剂时间线

当前未取得可用主力资金流向数据。
"""
    )

    codes = {issue.code for issue in check_report_text(text).issues}

    assert "fundamentals_repeats_core_facts" in codes


def test_external_viewpoint_4_4_with_disclaimer_and_citations_passes():
    text = _quality_shell(
        """
### 4.1 产业逻辑与竞争格局

FPGA产品仍是核心变量[^1]。

### 4.2 业绩路径与多空分歧

收入变化原因主要系FPGA产品放量。

### 4.3 资金面与催化剂时间线

当前未取得可用主力资金流向数据。

### 4.4 精选外部观察（Preview）

> 精选外部材料仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**估值分歧**

外部材料认为估值存在分歧[^2]。

**本节引用来源：**
- [^2] 雪球专栏观察 | 《估值分析》
"""
    )

    codes = {issue.code for issue in check_report_text(text).issues}

    assert "external_viewpoint_overcompressed" not in codes


def test_external_viewpoint_4_4_missing_disclaimer_warns():
    text = _quality_shell(
        """
### 4.1 产业逻辑与竞争格局

FPGA产品仍是核心变量[^1]。

### 4.2 业绩路径与多空分歧

收入变化原因主要系FPGA产品放量。

### 4.3 资金面与催化剂时间线

当前未取得可用主力资金流向数据。

### 4.4 精选外部观察

外部材料认为估值存在分歧[^2]。

**本节引用来源：**
- [^2] 雪球专栏观察 | 《估值分析》
"""
    )

    codes = {issue.code for issue in check_report_text(text).issues}

    assert "external_viewpoint_overcompressed" in codes


def test_formal_thin_external_map_without_visible_cards_does_not_warn():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.1 正式材料要点

已确认：营业收入10亿元。

### 4.2 外部观点地图（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不参与评分。

#### 4.2.1 产业链与技术路线分歧

**外部观点链**：外部材料讨论技术路线仍有分歧[^1]。
**支持线索**：产业报告提到多款新品。
**反方约束**：官方未确认量产进度。
**待验证证据**：需等待正式公告验证。

**本节引用来源：**
- [^1] 微信公众号精选观察 | 《产业观察》

### 4.3 待验证清单

| 变量 | 为什么重要 | 需要什么证据 | 来源层级 |
|---|---|---|---|
| 量产进度 | 影响收入确认 | 正式公告 | 需正式验证 |
"""
    )

    codes = {issue.code for issue in check_report_text(text).issues}

    assert "external_viewpoint_overcompressed" not in codes
    assert "external_viewpoint_overcompressed" not in codes


def test_formal_thin_external_variable_narrative_does_not_warn():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_thin_layout_variant": "annual_broker_external_checklist"} -->

### 4.1 年报经营摘要

**一句话画像**：公司主营业务为 FPGA 芯片。

### 4.2 研报观点与假设

当前未取得足够可用研报 digest，不展开研报观点与假设。

### 4.3 外部观点与待验证变量（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**FPGA 订单弹性**
- 外部材料称：高可靠 FPGA 订单弹性需要与正式公告、财报拆分和研报假设交叉验证[^1]

**本节引用来源：**
- [^1] 微信公众号精选观察 | 《产业观察》
"""
    )

    codes = {issue.code for issue in check_report_text(text).issues}

    assert "external_viewpoint_overcompressed" not in codes


def test_formal_thin_external_argument_v2_narrative_does_not_warn():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_thin_layout_variant": "annual_broker_external_checklist"} -->

### 4.1 年报经营摘要

**一句话画像**：公司主营业务为 FPGA 芯片。

### 4.2 研报观点与假设

当前未取得足够可用研报 digest，不展开研报观点与假设。

### 4.3 外部观点与待验证变量（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**供应链观察**

外部新增待验证变量：上游供给节奏仍可能影响交付弹性[^1]。

> **外部原文依据**：部分原材料仍处于紧张状态。

**本节引用来源：**
- [^1] 微信公众号精选观察 | 《产业观察》
"""
    )

    codes = {issue.code for issue in check_report_text(text).issues}

    assert "external_viewpoint_overcompressed" not in codes


def test_formal_thin_canonical_source_units_pass_external_quality_gates():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_thin_layout_variant": "annual_broker_external_checklist"} -->

### 4.1 年报经营摘要

**一句话画像**：公司主营业务为 FPGA 芯片。

### 4.2 研报观点与假设

当前未取得足够可用研报 digest，不展开研报观点与假设。

### 4.3 外部观点与待验证变量（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**财务质量**

外部新增待验证变量：收入与毛利均实现增长[^1]。
同时，公司持续推进产品迭代并形成贡献[^1]。

> **同业/行业背景（Preview）**：以下内容仅描述同业或行业背景，不代表目标公司已确认事实。

**技术与产品**

同业/行业背景观察：同业产品进入验证窗口[^2]。

## 引用来源
- [^1] 微信公众号精选观察 | 《公司观察》
- [^2] 知乎精选观察 | 《行业观察》
"""
    )

    codes = {issue.code for issue in check_report_text(text).issues}

    assert "curated_external_missing_inline_footnotes" not in codes
    assert "external_viewpoint_overcompressed" not in codes
    assert "external_map_unverified_claim_framing" not in codes


def test_external_map_uncertainty_does_not_trigger_strong_confirmation():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_thin_layout_variant": "annual_broker_external_checklist"} -->

### 4.1 年报经营摘要

**一句话画像**：公司主营业务为光模块。

### 4.2 研报观点与假设

当前未取得足够可用研报 digest，不展开研报观点与假设。

### 4.3 外部观点与待验证变量（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**供应链观察**

外部新增待验证变量：供应不确定性可能影响交付[^1]。

> **外部原文依据**：部分原材料仍处于紧张状态。

**本节引用来源：**
- [^1] 微信公众号精选观察 | 《产业观察》
"""
    )

    codes = {issue.code for issue in check_report_text(text).issues}

    assert "external_map_unverified_claim_framing" not in codes


def test_formal_thin_external_map_missing_structure_warns():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.1 正式材料要点

已确认：营业收入10亿元。

### 4.2 外部观点地图（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不参与评分。

外部材料讨论技术路线仍有分歧。

### 4.3 待验证清单

| 变量 | 为什么重要 | 需要什么证据 | 来源层级 |
|---|---|---|---|
| 量产进度 | 影响收入确认 | 正式公告 | 需正式验证 |
"""
    )

    codes = {issue.code for issue in check_report_text(text).issues}

    assert "external_viewpoint_overcompressed" in codes


def test_formal_thin_external_map_only_chain_warns():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.1 正式材料要点

已确认：营业收入10亿元。

### 4.2 外部观点地图（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不参与评分。

**外部观点链**：外部材料讨论技术路线仍有分歧[^1]。

**本节引用来源：**
- [^1] 微信公众号精选观察 | 《产业观察》

### 4.3 待验证清单

| 变量 | 为什么重要 | 需要什么证据 | 来源层级 |
|---|---|---|---|
| 量产进度 | 影响收入确认 | 正式公告 | 需正式验证 |
"""
    )

    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}

    assert "external_viewpoint_overcompressed" in codes
    issue = next(i for i in result.issues if i.code == "external_viewpoint_overcompressed")
    assert "支持线索" in issue.evidence
    assert "反方约束" in issue.evidence
    assert "待验证证据" in issue.evidence


def test_formal_thin_external_map_full_structure_but_no_inline_citations_warns():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.1 正式材料要点

已确认：营业收入10亿元。

### 4.2 外部观点地图（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不参与评分。

**外部观点链**：外部材料讨论技术路线仍有分歧。
**支持线索**：产业报告提到多款新品。
**反方约束**：官方未确认量产进度。
**待验证证据**：需等待正式公告验证。

### 4.3 待验证清单

| 变量 | 为什么重要 | 需要什么证据 | 来源层级 |
|---|---|---|---|
| 量产进度 | 影响收入确认 | 正式公告 | 需正式验证 |
"""
    )

    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}

    assert "external_viewpoint_overcompressed" in codes
    issue = next(i for i in result.issues if i.code == "external_viewpoint_overcompressed")
    assert "inline citations" in issue.evidence


def test_formal_thin_external_map_full_structure_with_inline_citations_passes():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.1 正式材料要点

已确认：营业收入10亿元。

### 4.2 外部观点地图（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不参与评分。

**外部观点链**：外部材料讨论技术路线仍有分歧[^1]。
**支持线索**：产业报告提到多款新品[^1]。
**反方约束**：官方未确认量产进度[^1]。
**待验证证据**：需等待正式公告验证[^1]。

**本节引用来源：**
- [^1] 微信公众号精选观察 | 《产业观察》

### 4.3 待验证清单

| 变量 | 为什么重要 | 需要什么证据 | 来源层级 |
|---|---|---|---|
| 量产进度 | 影响收入确认 | 正式公告 | 需正式验证 |
"""
    )

    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}

    assert "external_viewpoint_overcompressed" not in codes


def test_unmatched_industry_chain_claim_is_error_when_manifest_is_available():
    text = """
# 测试股 舆情深度报告

## 执行摘要
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

### 4.3 资金面与催化剂时间线

存储产品涨价通过晶圆厂产能紧张传导至CIS排产，韦尔股份将直接受益。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常，波动率 BOLL 正常。分析可信度：中。

## 综合风险评分
### 风险等级: 3.0/10（中风险）

## 风险提示与关注要点
- 风险因子需跟踪。
"""
    manifest = {
        "events_catalysts_chains": [
            {
                "chain_id": "memory_capacity_to_cis_pricing",
                "confidence": 0.82,
                "canonical_text": "存储产品涨价 -> 晶圆厂产能紧张 -> CIS排产变化 -> 供给和涨价节奏成为待验证变量",
                "allowed_terms": ["存储产品涨价", "晶圆厂产能紧张", "CIS排产变化", "待验证变量"],
            }
        ]
    }

    result = check_report_text(text, industry_relevance_manifest=manifest)

    codes = {issue.code for issue in result.issues}
    assert "industry_chain_unmatched_claim" in codes


def test_check_report_file_loads_industry_relevance_manifest_sidecar(tmp_path):
    report_path = tmp_path / "测试股_20260604.md"
    report_path.write_text(
        """
# 测试股 舆情深度报告

## 执行摘要
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

### 4.3 资金面与催化剂时间线

存储产品涨价通过晶圆厂产能紧张传导至CIS排产，韦尔股份将直接受益。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常，波动率 BOLL 正常。分析可信度：中。

## 综合风险评分
### 风险等级: 3.0/10（中风险）

## 风险提示与关注要点
- 风险因子需跟踪。
""",
        encoding="utf-8",
    )
    sidecar_path = tmp_path / "测试股_20260604_industry_relevance_manifest.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "schema": "industry_relevance_manifest.v1",
                "events_catalysts_chains": [
                    {
                        "chain_id": "memory_capacity_to_cis_pricing",
                        "confidence": 0.82,
                        "allowed_terms": ["存储产品涨价", "晶圆厂产能紧张", "CIS排产变化", "待验证变量"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = check_report_file(report_path)

    codes = {issue.code for issue in result.issues}
    assert "industry_chain_unmatched_claim" in codes


def test_canonical_industry_chain_wording_passes_manifest_check():
    text = """
# 测试股 舆情深度报告

## 执行摘要
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

### 4.3 资金面与催化剂时间线

存储产品涨价与晶圆厂产能紧张形成行业背景，CIS排产变化仍属于待验证变量。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常，波动率 BOLL 正常。分析可信度：中。

## 综合风险评分
### 风险等级: 3.0/10（中风险）

## 风险提示与关注要点
- 风险因子需跟踪。
"""
    manifest = {
        "events_catalysts_chains": [
            {
                "chain_id": "memory_capacity_to_cis_pricing",
                "confidence": 0.82,
                "canonical_text": "存储产品涨价 -> 晶圆厂产能紧张 -> CIS排产变化 -> 供给和涨价节奏成为待验证变量",
                "allowed_terms": ["存储产品涨价", "晶圆厂产能紧张", "CIS排产变化", "待验证变量"],
            }
        ]
    }

    result = check_report_text(text, industry_relevance_manifest=manifest)

    codes = {issue.code for issue in result.issues}
    assert "industry_chain_unmatched_claim" not in codes


def test_wait_entry_with_aggressive_risk_advice_is_error():
    text = """
# 测试股 舆情深度报告

## 执行摘要

### 综合评分: 6.2/10 | EV: +49.83%（看多但等待入场）

## 综合风险评分
### 风险等级: 2.0/10（低风险）
> **仓位建议**: 积极配置，最大仓位 20%
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "risk_position_label_mismatch" in codes


def test_control_position_label_with_aggressive_risk_advice_is_error():
    text = """
# 测试股 舆情深度报告

## 执行摘要

### 综合评分: 6.2/10 | EV: +9.00%（看多但控制仓位）

## 综合风险评分
### 风险等级: 2.0/10（低风险）
> **仓位建议**: 积极配置，最大仓位 20%
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "risk_position_label_mismatch" in codes


def test_display_only_risk_without_explanation_warns():
    text = """
# 测试股 舆情深度报告

### 4.4 精选外部观察（Preview）

> 本节为 display-only。

- 硅料涨价带来上游成本压力，存在毛利率承压风险。

## 综合风险评分
### 风险等级: 2.0/10（低风险）
> **仓位建议**: 积极配置，最大仓位 20%
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "display_only_risk_without_explanation" in codes


def test_display_only_risk_with_explanation_passes():
    text = """
# 测试股 舆情深度报告

### 4.4 精选外部观察（Preview）

> 本节为 display-only。

- 硅料涨价带来上游成本压力，存在毛利率承压风险。

## 综合风险评分
### 风险等级: 2.0/10（低风险）
> **仓位建议**: 积极配置，最大仓位 20%
> **外部观察说明**: 4.4 外部观察为 display-only，不计入综合风险评分；相关变量仅作为人工跟踪项。
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "display_only_risk_without_explanation" not in codes


# ---------------------------------------------------------------------------
# Fudan trial pipeline quality gates
# ---------------------------------------------------------------------------


def test_missing_deep_analysis_subsection_is_error():
    text = """
# 测试股 舆情深度报告

## 四、深度分析

### 4.1 产业逻辑与竞争格局

产业逻辑清晰。

### 4.2 业绩路径与多空分歧

业绩路径清晰。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常，波动率 BOLL 正常。分析可信度：中。

## 综合风险评分
### 风险等级: 3.0/10（中风险）

## 风险提示与关注要点
- 风险因子需跟踪。
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "missing_deep_analysis_subsection" in codes


def test_thin_all_only_requires_4_1():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "thin_all"} -->

### 4.1 正式材料要点

当前可用于深度基本面分析的正式材料不足，未强制生成 4.2/4.3 推断性内容。
"""
    )
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "missing_deep_analysis_subsection" not in codes


def test_formal_rich_missing_4_2_and_4_3_still_error():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_rich"} -->

### 4.1 产业逻辑与竞争格局

产业逻辑清晰。
"""
    )
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "missing_deep_analysis_subsection" in codes


def test_formal_medium_missing_4_2_and_4_3_still_error():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_medium"} -->

### 4.1 产业逻辑与竞争格局

产业逻辑有限。
"""
    )
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "missing_deep_analysis_subsection" in codes


def test_formal_medium_thin_sections_warn():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_medium"} -->

### 4.1 产业逻辑与竞争格局

产业逻辑清晰。

### 4.2 业绩路径与多空分歧

业绩路径清晰。

### 4.3 资金面与催化剂时间线

当前正式材料未形成可验证的资金面或催化剂时间线。
"""
    )
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "formal_medium_section_too_thin" in codes


def test_formal_medium_section_without_citations_but_specific_content_passes():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_medium"} -->

### 4.1 产业逻辑与竞争格局

AI 算力集群对 800G/1.6T 光模块需求持续扩张，中际旭创处于产业链中游，负责光电器件集成与制造。2026 年 Q1 营收同比增长 192%。

### 4.2 业绩路径与多空分歧

2025 年全年营业收入 382.40 亿元，1.6T 产品推动一季度盈利高速增长。毛利率 46.06% 低于新易盛 49.16%。

### 4.3 资金面与催化剂时间线

2026-04-17 披露第一季度报告，2026-08 下旬预计披露半年度报告。下一个催化剂为 1.6T 出货量环比增速。
"""
    )
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "formal_medium_section_too_thin" not in codes
    assert "formal_medium_section_lacks_evidence" not in codes


def test_formal_medium_normal_report_with_citations_passes_evidence_depth():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_medium"} -->

### 4.1 产业逻辑与竞争格局

AI 算力集群对高速光模块的需求持续扩张[^1]。公司布局 NPO 等新技术[^2]。中际旭创处于光模块产业链中游。

### 4.2 业绩路径与多空分歧

2025 年全年营业收入 382.40 亿元[^3]。1.6T 产品推动一季度盈利高速增长[^4]。毛利率 46.06% 低于新易盛 49.16% 。

### 4.3 资金面与催化剂时间线

| 时间点 | 催化剂/事件 | 当前状态 |
|--------|------------|----------|
| 2026-04-17 | 披露第一季度报告[^5] | 已完成 |

当前正式材料未提供足够资金面数据。
"""
    )
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "formal_medium_section_too_thin" not in codes
    assert "formal_medium_section_lacks_evidence" not in codes


def test_formal_medium_official_section_rejects_non_official_attribution():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_medium"} -->

### 4.1 官方材料确认：业务与财务基座

券商认为公司 800G 光模块订单饱满，雪球用户称供应链弹性较强[^1]。

### 4.2 机构观点与盈利假设

券商认为：1.6T 放量支撑增长[^2]。

### 4.3 外部观察与待验证变量（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或目标价。

外部材料称：供应链变量仍需验证[^3]。
"""
    )
    codes = {issue.code for issue in check_report_text(text).issues}
    assert "formal_medium_official_section_source_leak" in codes


def test_formal_medium_broker_section_requires_attribution_for_confirmed_claims():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_medium"} -->

### 4.1 官方材料确认：业务与财务基座

公司披露 2025 年营业收入 382.40 亿元[^1]。

### 4.2 机构观点与盈利假设

公司已经进入 1.6T 核心客户供应链，盈利将持续高增[^2]。

### 4.3 外部观察与待验证变量（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或目标价。

外部材料称：供应链变量仍需验证[^3]。
"""
    )
    codes = {issue.code for issue in check_report_text(text).issues}
    assert "formal_medium_broker_claim_without_attribution" in codes


def test_formal_medium_source_layer_headings_pass_evidence_depth():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_medium"} -->

### 4.1 官方材料确认：业务与财务基座

公司披露 2025 年营业收入 382.40 亿元，800G/1.6T 光模块为主要增长线索[^1]。

### 4.2 机构观点与盈利假设

券商认为：800G 放量和 1.6T 导入支撑盈利增长，研报预计毛利率随产品结构改善[^2]。

### 4.3 外部观察与待验证变量（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或目标价。

外部材料称：供应链变量仍需验证[^3]。

### 4.4 上行 / 下行条件与股价推演

| 来源层级 | 上行条件 | 下行条件 | 观察证据 |
|---|---|---|---|
| 官方确认 | 收入增长延续 | 毛利率恶化 | 年报与季报 |
"""
    )
    codes = {issue.code for issue in check_report_text(text).issues}
    assert "formal_medium_section_too_thin" not in codes
    assert "formal_medium_section_lacks_evidence" not in codes
    assert "formal_medium_official_section_source_leak" not in codes
    assert "formal_medium_broker_claim_without_attribution" not in codes


def test_formal_medium_external_map_funding_terms_do_not_trigger_funding_gate():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_medium", "formal_section_support": {"funding_support": 0}} -->

### 4.1 官方材料确认：业务与财务基座

公司披露 2025 年营业收入 382.40 亿元[^1]。

### 4.2 机构观点与盈利假设

券商认为：800G 放量支撑增长[^2]。

### 4.3 外部观察与待验证变量（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或目标价。

外部材料称：主力净流入变化可能影响短线情绪，该说法需以正式资金面数据验证[^3]。

### 4.4 上行 / 下行条件与股价推演

| 来源层级 | 上行条件 | 下行条件 | 观察证据 |
|---|---|---|---|
| 外部待验证 | 外部变量被验证 | 外部变量被证伪 | 后续公告 |
"""
    )
    codes = {issue.code for issue in check_report_text(text).issues}
    assert "funding_claim_without_funding_support" not in codes


def test_formal_medium_price_path_external_row_does_not_trigger_legacy_external_warning():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_medium"} -->

### 4.1 官方材料确认：业务与财务基座

公司披露 2025 年营业收入 382.40 亿元，800G/1.6T 光模块为主要增长线索[^1]。

### 4.2 机构观点与盈利假设

国金证券研报认为：800G 放量支撑增长[^2]。

### 4.3 外部观察与待验证变量（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或目标价。

外部材料称：供应链变量仍需验证[^3]。

### 4.4 上行 / 下行条件与股价推演

> 本节只做股价方向的条件推演，不直接修改目标价、评分、风险评分或最终推荐。

| 来源层级 | 关键变量 | 上行条件 | 下行条件 | 观察证据 |
|---|---|---|---|---|
| 外部待验证 | 供应链与交付 | 外部变量被公告验证 | 外部变量被证伪 | 外部材料称：供应链变量仍需验证[^3] |
"""
    )
    codes = {issue.code for issue in check_report_text(text).issues}
    assert "external_viewpoint_overcompressed" not in codes


def test_product_industry_mismatch_is_error_for_negated_mlcc_chain():
    text = """
# 复旦微电 舆情深度报告

## 四、深度分析

### 4.1 产业逻辑与竞争格局

MLCC 需求受 AI 服务器和汽车电子驱动，公司主要产品为 FPGA 与存储芯片，不直接涉及 MLCC 技术路线。

### 4.2 业绩路径与多空分歧

业绩路径清晰。

### 4.3 资金面与催化剂时间线

当前正式材料未形成可验证的资金面或催化剂时间线。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常，波动率 BOLL 正常。分析可信度：中。

## 综合风险评分
### 风险等级: 3.0/10（中风险）

## 风险提示与关注要点
- 风险因子需跟踪。
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "product_industry_mismatch" in codes


def test_financial_fact_unit_conflict_is_error():
    text = """
# 复旦微电 舆情深度报告

## 三、核心事实基座

| # | 事实 | 数据/来源 | 证据 | 置信度 |
|---|---|-----------|------|--------|
| 1 | 营业收入 | 39.82万元 | 年报 | 高 |
| 2 | 归母净利润 | 2.32万元 | 年报 | 高 |

## 一、公司快照

2026Q1 营业收入 10.32亿，归母净利润 1.48亿。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常，波动率 BOLL 正常。分析可信度：中。

## 综合风险评分
### 风险等级: 3.0/10（中风险）

## 风险提示与关注要点
- 风险因子需跟踪。
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "financial_fact_unit_conflict" in codes


def test_financial_data_missing_contradiction_is_metric_specific_error():
    text = """
# 复旦微电 舆情深度报告

## 一、公司快照

2026Q1 营业收入 10.32亿，归母净利润 1.48亿。

## 四、深度分析

### 4.1 产业逻辑与竞争格局

产业逻辑清晰。

### 4.2 业绩路径与多空分歧

外部材料未提供最新营收数据，也未提供最新利润数据。客户结构和管理层指引未提供。

### 4.3 资金面与催化剂时间线

当前正式材料未形成可验证的资金面或催化剂时间线。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常，波动率 BOLL 正常。分析可信度：中。

## 综合风险评分
### 风险等级: 3.0/10（中风险）

## 风险提示与关注要点
- 风险因子需跟踪。
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "financial_data_missing_contradiction" in codes


def test_true_missing_order_and_guidance_text_does_not_trigger_financial_contradiction():
    text = """
# 测试股 舆情深度报告

## 一、公司快照

2026Q1 营业收入 10.32亿，归母净利润 1.48亿。

## 四、深度分析

### 4.2 业绩路径与多空分歧

订单、客户结构和管理层指引未提供，仍需后续公告验证。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常，波动率 BOLL 正常。分析可信度：中。

## 综合风险评分
### 风险等级: 3.0/10（中风险）

## 风险提示与关注要点
- 风险因子需跟踪。
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "financial_data_missing_contradiction" not in codes


def test_profit_growth_wording_conflicts_with_negative_net_profit_signal():
    text = """
# 复旦微电 舆情深度报告

## 执行摘要

- 2025年业绩预告利润高增，营收增长由核心产品线驱动。

## 四、深度分析

### 4.1 产业逻辑与竞争格局

公司公告显示，2025年营收与利润增长，反映下游需求稳定。

### 4.2 业绩路径与多空分歧

若2025年年报及后续季报持续验证利润高增，市场可能接受当前高PE。

### 4.3 资金面与催化剂时间线

当前正式材料未提供足够资金面数据。

### 4.4 精选外部观察（Preview）

外部材料指出，复旦微电2025年归母净利只有2.32亿，同比腰斩59%，需要跟踪盈利修复假设。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常，波动率 BOLL 正常。分析可信度：中。

## 综合风险评分
### 风险等级: 3.0/10（中风险）

## 风险提示与关注要点
- 风险因子需跟踪。
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "financial_profit_direction_contradiction" in codes


def test_profit_growth_wording_conflicts_with_net_profit_repair_signal():
    text = """
# 复旦微电 舆情深度报告

## 执行摘要

- 2025年业绩预告利润高增，营收增长由核心产品线驱动。

## 四、深度分析

### 4.1 产业逻辑与竞争格局

公司公告显示，2025年营收与利润增长，反映下游需求稳定。

### 4.2 业绩路径与多空分歧

若2025年年报及后续季报持续验证利润高增，市场可能接受当前高PE。

### 4.3 资金面与催化剂时间线

当前正式材料未提供足够资金面数据。

### 4.4 精选外部观察（Preview）

外部材料认为，核心假设在于2026年净利润能否修复至7.5亿元，券商预测区间分歧较大。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常，波动率 BOLL 正常。分析可信度：中。

## 综合风险评分
### 风险等级: 3.0/10（中风险）

## 风险提示与关注要点
- 风险因子需跟踪。
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "financial_profit_direction_contradiction" in codes


def test_profit_growth_wording_catches_yoy_large_growth_phrase():
    text = """
# 复旦微电 舆情深度报告

## 执行摘要

2025年归母净利润同比大幅增长。

## 四、深度分析

### 4.1 产业逻辑与竞争格局

公司产品线清晰。

### 4.2 业绩路径与多空分歧

2025年归母净利润同比大幅增长，Forward PE降至52.11倍。

### 4.3 资金面与催化剂时间线

当前正式材料未提供足够资金面数据。

### 4.4 精选外部观察（Preview）

外部材料认为，2026年净利润能否修复至7.5亿元仍是估值锚。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常，波动率 BOLL 正常。分析可信度：中。

## 综合风险评分
### 风险等级: 3.0/10（中风险）

## 风险提示与关注要点
- 风险因子需跟踪。
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "financial_profit_direction_contradiction" in codes


def test_financial_snapshot_yoy_growth_does_not_conflict_with_full_year_repair():
    text = """
# 复旦微电 舆情深度报告

## 执行摘要

估值分歧未解，需等待更多确认信号。

## 二、估值与财务快照

> 财务趋势: 营收同比增长16.2%，净利润同比增长8.9%。

## 四、深度分析

### 4.1 产业逻辑与竞争格局

当前仅完成技术面降级摘要。

### 4.2 业绩路径与多空分歧

基本面 LLM 合成未启用或未产生有效输出。

### 4.3 资金面与催化剂时间线

当前正式材料未提供足够资金面数据。

### 4.4 精选外部观察（Preview）

外部材料认为，2026年净利润能否修复至7.5亿元仍是估值锚。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常，波动率 BOLL 正常。分析可信度：中。

## 综合风险评分
### 风险等级: 3.0/10（中风险）

## 风险提示与关注要点
- 风险因子需跟踪。
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "financial_profit_direction_contradiction" not in codes


def test_header_config_missing_warns_when_header_shows_dash():
    text = """
# 测试股 舆情深度报告

**报告日期**: 2026年07月02日
**所属赛道**: —
**可比公司**: —

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常，波动率 BOLL 正常。分析可信度：中。

## 综合风险评分
### 风险等级: 3.0/10（中风险）

## 风险提示与关注要点
- 风险因子需跟踪。
"""
    result = check_report_text(text)
    issues = {issue.code: issue for issue in result.issues}
    assert "header_config_missing" in issues
    assert issues["header_config_missing"].severity == "warning"


def test_fundflow_claim_without_sidecar_catches_financial_data_inferred_buying_pressure():
    text = """
# 复旦微电 舆情深度报告

## 四、深度分析

### 4.1 产业逻辑与竞争格局

产业逻辑清晰。

### 4.2 业绩路径与多空分歧

营业收入变化已有公司解释。

### 4.3 资金面与催化剂时间线

| 资金变量 | 当前证据 | 对短期交易结构的含义 | 需跟踪 | 来源 |
| --- | --- | --- | --- | --- |
| 主力资金 | 2026年Q1营收7.82亿元，环比下降 | 可能压制主动买盘 | 后续交易数据 | [^1] |

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常，波动率 BOLL 正常。分析可信度：中。

## 综合风险评分
### 风险等级: 3.0/10（中风险）

## 风险提示与关注要点
- 风险因子需跟踪。
"""
    result = check_report_text(text)
    issues = {issue.code: issue for issue in result.issues}
    assert "fundflow_claim_without_fundflow_pack" in issues


# ---------------------------------------------------------------------------
# Peer comparison material quality gates
# ---------------------------------------------------------------------------


def _peer_comparison_report_text() -> str:
    """Return a report text with 4.1 and 4.2 sections for peer gate testing."""
    return """
# 测试股 舆情深度报告

## 执行摘要
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

### 4.1 行业逻辑与竞争格局

公司为国内该领域的龙头企业，具备较强的技术壁垒。

### 4.2 基本面与估值分析

公司毛利率显著优于同行，估值水平合理。

### 4.3 资金面与催化剂时间线

存储产品涨价通过晶圆厂产能紧张传导至CIS排产，韦尔股份将直接受益。

### 4.4 精选外部观察（Preview）

从雪球观点来看，公司估值在行业中偏高。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常，波动率 BOLL 正常。分析可信度：中。

## 综合风险评分
### 风险等级: 3.0/10（中风险）

## 风险提示与关注要点
- 风险因子需跟踪。
"""


def test_peer_pack_social_leak_is_error():
    """Peer material rows with social source refs cause error."""
    text = _peer_comparison_report_text()
    peer_material = {
        "schema": "peer_comparison_material.v1",
        "target": "测试股",
        "peers": ["同行A"],
        "rows": [
            {
                "dimension": "盈利能力",
                "target": "测试股",
                "peer": "同行A",
                "metric": "gross_margin",
                "target_value": 60.0,
                "peer_value": 65.0,
                "period": "latest",
                "unit": "%",
                "comparison": "毛利率低于同行A",
                "source_refs": ["雪球:某帖子"],
                "confidence": 0.80,
                "usage": "claim_eligible",
            }
        ],
        "warnings": [],
    }
    result = check_report_text(text, peer_comparison_material=peer_material)
    codes = {issue.code for issue in result.issues}
    assert "peer_pack_social_leak" in codes


def test_peer_pack_allowed_refs_pass():
    """Peer material rows with allowed source refs pass the social leak gate."""
    text = _peer_comparison_report_text()
    peer_material = {
        "schema": "peer_comparison_material.v1",
        "target": "测试股",
        "peers": ["同行A"],
        "rows": [
            {
                "dimension": "盈利能力",
                "target": "测试股",
                "peer": "同行A",
                "metric": "gross_margin",
                "target_value": 60.0,
                "peer_value": 65.0,
                "period": "latest",
                "unit": "%",
                "comparison": "毛利率低于同行A",
                "source_refs": ["指标:competitor_metrics"],
                "confidence": 0.85,
                "usage": "claim_eligible",
            }
        ],
        "warnings": [],
    }
    result = check_report_text(text, peer_comparison_material=peer_material)
    codes = {issue.code for issue in result.issues}
    assert "peer_pack_social_leak" not in codes


def test_peer_pack_unknown_source_prefix_is_error():
    """Peer material rows must use explicit formal/professional source prefixes."""
    text = _peer_comparison_report_text()
    peer_material = {
        "schema": "peer_comparison_material.v1",
        "target": "测试股",
        "peers": ["同行A"],
        "rows": [
            {
                "dimension": "盈利能力",
                "target": "测试股",
                "peer": "同行A",
                "metric": "gross_margin",
                "target_value": 60.0,
                "peer_value": 65.0,
                "period": "latest",
                "unit": "%",
                "comparison": "毛利率低于同行A",
                "source_refs": ["网页:某财经网站"],
                "confidence": 0.85,
                "usage": "claim_eligible",
            }
        ],
        "warnings": [],
    }

    result = check_report_text(text, peer_comparison_material=peer_material)

    codes = {issue.code for issue in result.issues}
    assert "peer_pack_social_leak" in codes


def test_unsupported_peer_superlative_is_error():
    """Strong peer comparison terms in 4.1/4.2 without high-confidence pack cause error."""
    text = _peer_comparison_report_text()
    # No peer_material provided -> no rows to support the strong claim "显著优于同行"
    result = check_report_text(text, peer_comparison_material=None)
    codes = {issue.code for issue in result.issues}
    assert "unsupported_peer_superlative" in codes


def test_high_confidence_sidecar_suppresses_superlative_error():
    """High-confidence peer material with matching dimension suppresses the error."""
    lines = [
        "### 4.1 行业逻辑与竞争格局",
        "",
        "公司为国内该领域的龙头企业，具备较强的技术壁垒。",
        "",
        "### 4.2 基本面与估值分析",
        "",
        "公司毛利率**显著优于**行业平均，PE估值略低于同行，整体竞争力突出。",
    ]
    text = _peer_comparison_report_text().replace(
        "公司毛利率显著优于同行，估值水平合理。",
        "公司毛利率**显著优于**行业平均，PE估值略低于同行，整体竞争力突出。",
    )
    peer_material = {
        "schema": "peer_comparison_material.v1",
        "target": "测试股",
        "peers": ["同行A"],
        "rows": [
            {
                "dimension": "盈利能力",
                "target": "测试股",
                "peer": "同行A",
                "metric": "gross_margin",
                "target_value": 60.0,
                "peer_value": 65.0,
                "period": "latest",
                "unit": "%",
                "comparison": "毛利率低于同行A",
                "source_refs": ["指标:competitor_metrics"],
                "confidence": 0.85,
                "usage": "claim_eligible",
            }
        ],
        "warnings": [],
    }
    result = check_report_text(text, peer_comparison_material=peer_material)
    codes = {issue.code for issue in result.issues}
    assert "unsupported_peer_superlative" not in codes


def test_peer_claim_without_peer_pack_warns():
    """Weak peer comparison terms in 4.1/4.2 without any sidecar cause warning."""
    text = """
# 测试股 舆情深度报告

## 执行摘要
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

### 4.1 行业逻辑与竞争格局

公司与同行存在一定差距，后续需观察产品结构改善。

### 4.2 基本面与估值分析

毛利率略低于同行，但估值并未明显偏离行业平均。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常。

## 综合风险评分
### 风险等级: 3.0/10（中风险）
"""
    result = check_report_text(text, peer_comparison_material=None)
    codes = {issue.code for issue in result.issues}
    assert "peer_claim_without_peer_pack" in codes
    assert "unsupported_peer_superlative" not in codes


def test_peer_claim_without_peer_pack_no_false_positive_with_sidecar():
    """Weak peer comparison terms pass when sidecar exists with rows."""
    text = """
# 测试股 舆情深度报告

## 执行摘要
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

### 4.1 行业逻辑与竞争格局

公司与同行存在一定差距，整体竞争格局稳定。

### 4.2 基本面与估值分析

毛利率略低于同行，但仍处于合理区间。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量正常。

## 综合风险评分
### 风险等级: 3.0/10（中风险）
"""
    peer_material = {
        "schema": "peer_comparison_material.v1",
        "target": "测试股",
        "peers": ["同行A"],
        "rows": [
            {
                "dimension": "盈利能力",
                "target": "测试股",
                "peer": "同行A",
                "metric": "gross_margin",
                "target_value": 60.0,
                "peer_value": 65.0,
                "period": "latest",
                "unit": "%",
                "comparison": "毛利率低于同行A",
                "source_refs": ["指标:competitor_metrics"],
                "confidence": 0.85,
                "usage": "claim_eligible",
            }
        ],
        "warnings": [],
    }
    result = check_report_text(text, peer_comparison_material=peer_material)
    codes = {issue.code for issue in result.issues}
    assert "peer_claim_without_peer_pack" not in codes


def test_no_peer_gate_false_positive_on_44_display_only():
    """4.4 display-only section with peer language should not trigger gates."""
    text = """
# 测试股 舆情深度报告

## 执行摘要
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

### 4.1 行业逻辑与竞争格局

公司是国内少数具有量产能力的企业之一。

### 4.2 基本面与估值分析

营收稳健增长，利润率保持稳定。

### 4.4 精选外部观察（Preview）

雪球观点认为公司与紫光国微相比有一定差距，毛利率落后于同行平均。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。

## 综合风险评分
### 风险等级: 3.0/10（中风险）
"""
    result = check_report_text(text, peer_comparison_material=None)
    codes = {issue.code for issue in result.issues}
    assert "unsupported_peer_superlative" not in codes
    assert "peer_claim_without_peer_pack" not in codes


def test_check_report_file_loads_peer_comparison_material_sidecar(tmp_path):
    """check_report_file auto-loads peer material sidecar from report path."""
    report_path = tmp_path / "测试股_20260702.md"
    report_path.write_text(
        _peer_comparison_report_text(),
        encoding="utf-8",
    )
    sidecar_path = tmp_path / "测试股_20260702_peer_comparison_material.json"
    sidecar_path.write_text(
        json.dumps({
            "schema": "peer_comparison_material.v1",
            "target": "测试股",
            "peers": ["同行A"],
            "rows": [
                {
                    "dimension": "盈利能力",
                    "target": "测试股",
                    "peer": "同行A",
                    "metric": "gross_margin",
                    "target_value": 60.0,
                    "peer_value": 65.0,
                    "period": "latest",
                    "unit": "%",
                    "comparison": "毛利率低于同行A",
                    "source_refs": ["雪球:某帖子"],
                    "confidence": 0.80,
                    "usage": "claim_eligible",
                }
            ],
            "warnings": [],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    result = check_report_file(report_path)

    codes = {issue.code for issue in result.issues}
    # Should detect the social leak in the sidecar
    assert "peer_pack_social_leak" in codes


def test_fundflow_claim_without_fundflow_pack_is_error():
    text = """
# 测试股 舆情深度报告

## 四、深度分析

### 4.1 产业逻辑与竞争格局

正式材料不足。

### 4.2 业绩路径与多空分歧

正式材料不足。

### 4.3 资金面与催化剂时间线

近5日主力净流入合计 1200万，超大单资金持续流入。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量温和，BOLL 波动率正常。评分 5/10，可信度中。

## 综合风险评分
### 风险等级: 4.0/10（中等风险）
"""
    result = check_report_text(text, fundflow_material_pack=None)
    codes = {issue.code for issue in result.issues}
    assert "fundflow_claim_without_fundflow_pack" in codes


def test_check_report_file_loads_fundflow_material_sidecar(tmp_path):
    report_path = tmp_path / "测试股_20260702.md"
    report_path.write_text(
        """
# 测试股 舆情深度报告

## 四、深度分析

### 4.1 产业逻辑与竞争格局

正式材料不足。

### 4.2 业绩路径与多空分歧

正式材料不足。

### 4.3 资金面与催化剂时间线

近5日主力净流入合计 1200万，超大单资金持续流入。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线结构：MA20 附近。周线结构：周线震荡。成交量温和，BOLL 波动率正常。评分 5/10，可信度中。

## 综合风险评分
### 风险等级: 4.0/10（中等风险）
""",
        encoding="utf-8",
    )
    sidecar_path = tmp_path / "测试股_20260702_fundflow_material.json"
    sidecar_path.write_text(
        json.dumps({
            "schema": "fundflow_material_pack.v1",
            "rows": [{"date": "2026-07-02", "main_net": 1200.0}],
            "summary": {"days": 1, "main_net_total": 1200.0},
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    result = check_report_file(report_path)

    codes = {issue.code for issue in result.issues}
    assert "fundflow_claim_without_fundflow_pack" not in codes


def test_curated_external_4_4_requires_inline_footnotes_when_sources_exist():
    text = """
# 测试股 舆情深度报告

## 四、深度分析

### 4.4 精选外部观察（Preview）

> 精选外部材料仅作为专业观察，不等同于官方确认事实。

**估值分歧**

外部材料提示估值处于乐观情景上沿，需跟踪盈利修复假设。

**本节引用来源：**
- [^1] 雪球专栏观察 | 《估值分析》 | https://xueqiu.com/1/2

## 综合风险评分
### 风险等级: 4.0/10（中等风险）
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "curated_external_missing_inline_footnotes" in codes


def test_profile_routing_trace_missing_catches_absent_profile():
    text = """
# 测试股 舆情深度报告

## 执行摘要
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

### 4.1 产业逻辑与竞争格局

产业逻辑清晰。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。

## 综合风险评分
### 风险等级: 3.0/10（中风险）
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "profile_routing_trace_missing" in codes


def test_formal_thin_forced_legacy_sections_is_error():
    text = """
# 测试股 舆情深度报告

## 执行摘要
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.1 产业逻辑与竞争格局

旧模板。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。

## 综合风险评分
### 风险等级: 3.0/10（中风险）
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "formal_thin_forced_legacy_deep_sections" in codes


def test_funding_claim_without_funding_support_is_error():
    text = """
# 测试股 舆情深度报告

## 执行摘要
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.3 资金面与催化剂时间线

近5日主力净流入合计 1200万。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。

## 综合风险评分
### 风险等级: 3.0/10（中风险）
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "funding_claim_without_funding_support" in codes


def test_useless_core_fact_warns():
    text = """
# 测试股 舆情深度报告

## 三、核心事实基座

| # | 事实 | 数据/来源 | 证据 | 置信度 |
|---|---|-----------|------|--------|
| 1 | 年报已发布 | 2025年年报 | 公告 | 高 |

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

<!-- deep_analysis_profile: {"profile": "formal_rich"} -->

### 4.1 产业逻辑与竞争格局

产业逻辑清晰。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。

## 综合风险评分
### 风险等级: 3.0/10（中风险）
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "useless_core_fact" in codes


def test_unknown_core_fact_evidence_warns():
    text = """
# 测试股 舆情深度报告

## 三、核心事实基座

| # | 事实 | 数据/来源 | 证据 | 置信度 |
|---|---|-----------|------|--------|
| 1 | PE(TTM)对比新易盛 | 高于新易盛17.9倍 | 未绑定引用 (unknown) | 中 |

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

<!-- deep_analysis_profile: {"profile": "formal_medium"} -->

### 4.1 官方材料确认：业务与财务基座

产业逻辑清晰。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。

## 综合风险评分
### 风险等级: 3.0/10（中风险）
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "core_fact_unknown_evidence" in codes


def test_external_map_disclaimer_confirmation_word_does_not_falsely_trigger():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.2 外部观点地图（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**外部观点链**：外部材料讨论技术路线仍有分歧[^1]。
**支持线索**：产业报告提到多款新品[^1]。
**反方约束**：官方未确认量产进度[^1]。
**待验证证据**：需等待正式公告验证[^1]。

**本节引用来源：**
- [^1] 知乎精选观察 | 《产业观察》
"""
    )

    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}

    assert "external_map_unverified_claim_framing" not in codes


def test_external_map_table_negative_confirmation_phrase_does_not_trigger():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_thin_layout_variant": "annual_broker_external_checklist", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.3 外部观点与待验证变量（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

| 待验证变量 | 外部材料在说什么 | 与正式材料 / 研报假设的关系 | 下一步看什么 |
|---|---|---|---|
| 星载芯片 | 外部材料称公司具备高可靠 FPGA 线索，该说法需正式验证[^1]。 | 只能作为外部待验证变量，不替代官方确认。 | 跟踪公告、订单和财报拆分。 |

**本节引用来源：**
- [^1] 知乎精选观察 | 《产业观察》
"""
    )

    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}

    assert "external_map_unverified_claim_framing" not in codes


def test_external_map_body_strong_confirmation_still_triggers():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.2 外部观点地图（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**外部观点链**：外部材料确认公司已经进入核心客户供应链[^1]。
**支持线索**：产业报告提到多款新品[^1]。
**反方约束**：官方未确认量产进度[^1]。
**待验证证据**：需等待正式公告验证[^1]。

**本节引用来源：**
- [^1] 知乎精选观察 | 《产业观察》
"""
    )

    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}

    assert "external_map_unverified_claim_framing" in codes


def test_external_map_peer_preview_strong_wording_does_not_block_target_claims():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_thin_layout_variant": "annual_broker_external_checklist"} -->

### 4.1 年报经营摘要

**一句话画像**：公司主营业务为智能驾驶芯片。

### 4.2 研报观点与假设

当前未取得足够可用研报 digest，不展开研报观点与假设。

### 4.3 外部观点与待验证变量（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**客户进展**

外部新增待验证变量：目标公司合作进度仍需后续数据验证[^1]。

> **同业/行业背景（Preview）**：以下内容仅描述同业或行业背景，不代表目标公司已确认事实。

**商业化进展**

同业/行业背景观察：根据双方确定的项目安排，L4 自动驾驶已经不再是单纯技术展示[^2]。

## 引用来源
- [^1] 微信公众号精选观察 | 《公司观察》
- [^2] 知乎精选观察 | 《行业观察》
"""
    )

    codes = {issue.code for issue in check_report_text(text).issues}

    assert "external_map_unverified_claim_framing" not in codes


def test_external_map_framed_market_share_claim_does_not_trigger():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.2 外部观点地图（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**外部观点链**：外部材料称国内高可靠卫星FPGA市占率95%以上，该说法需正式验证[^1]。
**支持线索**：外部材料提到星载芯片需求[^1]。
**反方约束**：官方未确认市占率口径[^1]。
**待验证证据**：需等待公告或第三方行业数据验证[^1]。

**本节引用来源：**
- [^1] 知乎精选观察 | 《产业观察》
"""
    )

    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}

    assert "external_map_unverified_claim_framing" not in codes


def test_external_topic_narrative_lead_frames_market_share_claim():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich"} -->

### 4.3 外部观点与待验证变量（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或目标价。

**竞争格局**

近期外部材料主要围绕竞争格局展开。国内高可靠卫星FPGA市占率95%以上[^1]。

## 引用来源
- [^1] 知乎精选观察 | 《产业观察》
"""
    )

    codes = {issue.code for issue in check_report_text(text).issues}

    assert "external_map_unverified_claim_framing" not in codes


def test_external_topic_narrative_frames_each_separate_paragraph():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich"} -->

### 4.3 外部观点与待验证变量（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或目标价。

**竞争格局**

近期外部材料主要围绕竞争格局展开。产品进入客户验证[^1]。

据外部材料，国内高可靠卫星FPGA市占率95%以上[^1]。

## 引用来源
- [^1] 知乎精选观察 | 《产业观察》
"""
    )

    codes = {issue.code for issue in check_report_text(text).issues}

    assert "external_map_unverified_claim_framing" not in codes


def test_external_map_unframed_market_share_claim_still_triggers():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.2 外部观点地图（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**外部观点链**：国内高可靠卫星FPGA市占率已达95%以上[^1]。
**支持线索**：外部材料提到星载芯片需求[^1]。
**反方约束**：官方未确认市占率口径[^1]。
**待验证证据**：需等待公告或第三方行业数据验证[^1]。

**本节引用来源：**
- [^1] 知乎精选观察 | 《产业观察》
"""
    )

    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}

    assert "external_map_unverified_claim_framing" in codes


def test_external_map_missing_disclaimer_is_error():
    text = """
# 测试股 舆情深度报告

## 执行摘要
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.2 外部观点地图（Preview，不参与评分）

外部观点认为公司将进入供应链。

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。

## 综合风险评分
### 风险等级: 3.0/10（中风险）
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "external_map_unverified_claim_framing" in codes


def test_external_map_with_disclaimer_passes():
    text = """
# 测试股 舆情深度报告

## 执行摘要
### 综合评分: 5.0/10 | EV: +5.00%（中性）
可信度：中。风险等级：3.0/10。

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.1 正式材料要点

**已确认**
- 营业收入：10亿元。

### 4.2 外部观点地图（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不参与评分。

**外部观点链**：外部材料讨论公司可能成为某头部客户供应链的潜在参与者，但仍需正式验证。[^1]

**支持线索**：供应商访谈提及样品验证进度符合预期，部分产能处于爬坡阶段[^1]。

**反方约束**：尚未有官方订单公告，且同行竞争可能压低份额预期[^1]。

**待验证证据**：关注后续财报、客户公告及行业出货量数据以交叉验证[^1]。

### 4.3 待验证清单

| 变量 | 为什么重要 | 需要什么证据 | 来源层级 |
|---|---|---|---|
| 供应链传闻 | 外部观点增量变量 | 后续财报、客户公告及行业出货量数据 | 来源层级：低信用论坛 / 单源长文 / 需正式验证 |

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线：股价位于MA20与MA60之间。周线：周线大背景仍为整理。成交量：成交额较前期持平。波动率：BOLL收口。

## 综合风险评分
### 风险等级: 3.0/10（中风险）
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "external_map_missing_display_only_disclaimer" not in codes
    assert "external_map_unverified_claim_framing" not in codes
    assert "external_viewpoint_overcompressed" not in codes


def test_external_map_new_annual_broker_layout_uses_4_3():
    text = """
# 测试股 舆情深度报告

## 执行摘要
### 综合评分: 5.0/10 | EV: +5.00%（中性）
可信度：中。风险等级：3.0/10。

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_thin_layout_variant": "annual_broker_external_checklist", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.1 年报经营摘要

**年报解释**
- 主营业务来自年报摘要。[^1]

### 4.2 研报观点与假设

当前未取得足够可用研报 digest，不展开研报观点与假设。

### 4.3 外部观点地图（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**外部观点链**：外部材料称公司具备高可靠 FPGA 线索，该说法需正式验证。[^2]

**支持线索**：知乎文章提到产品布局。[^2]

**反方约束**：尚未有官方订单公告。[^2]

**待验证证据**：关注后续财报、客户公告及行业出货量数据以交叉验证。[^2]

### 4.4 待验证清单

| 变量 | 为什么重要 | 需要什么证据 | 来源层级 |
|---|---|---|---|
| 产品放量 | 外部观点增量变量 | 后续财报、客户公告及行业出货量数据 | 需正式验证 |

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线：股价位于MA20与MA60之间。周线：周线大背景仍为整理。成交量：成交额较前期持平。波动率：BOLL收口。

## 综合风险评分
### 风险等级: 3.0/10（中风险）
"""
    result = check_report_text(text)
    codes = {issue.code for issue in result.issues}
    assert "external_map_missing_display_only_disclaimer" not in codes
    assert "external_map_unverified_claim_framing" not in codes
    assert "external_viewpoint_overcompressed" not in codes


def test_annual_broker_4_3_external_map_with_section_refs_requires_inline_footnotes():
    text = """
# 测试股 舆情深度报告

## 执行摘要
### 综合评分: 5.0/10 | EV: +5.00%（中性）
可信度：中。风险等级：3.0/10。

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_thin_layout_variant": "annual_broker_external_checklist", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.1 年报经营摘要

年报经营摘要。

### 4.2 研报观点与假设

当前未取得足够可用研报 digest，不展开研报观点与假设。

### 4.3 外部观点与待验证变量（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**外部观点链**：外部材料称公司具备高可靠 FPGA 线索，该说法需正式验证。

**支持线索**：知乎文章提到产品布局。

**反方约束**：尚未有官方订单公告。

**待验证证据**：关注后续财报、客户公告及行业出货量数据以交叉验证。

**本节引用来源：**
- [^2] 知乎精选观察 | 《产业观察》

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线：股价位于MA20与MA60之间。周线：周线大背景仍为整理。成交量：成交额较前期持平。波动率：BOLL收口。

## 综合风险评分
### 风险等级: 3.0/10（中风险）
"""
    codes = {issue.code for issue in check_report_text(text).issues}
    assert "curated_external_missing_inline_footnotes" in codes


def test_annual_broker_4_3_display_only_risk_without_explanation_warns():
    text = """
# 测试股 舆情深度报告

## 执行摘要
### 综合评分: 5.0/10 | EV: +5.00%（中性）
可信度：中。风险等级：1.5/10。

## 一、综合评分与推荐
### 综合评分: 5.0/10 | EV: +5.00%（中性）

## 四、深度分析

<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_thin_layout_variant": "annual_broker_external_checklist", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.1 年报经营摘要

年报经营摘要。

### 4.2 研报观点与假设

当前未取得足够可用研报 digest，不展开研报观点与假设。

### 4.3 外部观点与待验证变量（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**外部观点链**：外部材料称公司估值偏高，该说法需正式验证。[^2]

**支持线索**：知乎文章提到估值分歧。[^2]

**反方约束**：正式研报口径不足。[^2]

**待验证证据**：关注后续公告及研报估值口径。[^2]

## 技术面分析：中期趋势提醒
趋势背景：震荡趋势。日线：股价位于MA20与MA60之间。周线：周线大背景仍为整理。成交量：成交额较前期持平。波动率：BOLL收口。

## 综合风险评分
### 风险等级: 1.5/10（低风险）
"""
    codes = {issue.code for issue in check_report_text(text).issues}
    assert "display_only_risk_without_explanation" in codes


def test_new_external_variable_map_requires_inline_footnote_per_visible_variable():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_thin_layout_variant": "annual_broker_external_checklist"} -->

### 4.1 年报经营摘要

年报经营摘要[^1]。

### 4.2 研报观点与假设

研报预计盈利改善[^2]。

### 4.3 外部观点与待验证变量（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**供应链观察**

外部材料称上游供给节奏仍需验证。

**客户验证**

外部材料称客户验证节奏仍需观察。[^10]

## 引用来源

- [^1] 公司年报 | 《年度报告》
- [^2] 券商研报 | 《跟踪报告》
- [^10] 微信公众号精选观察 | 《客户观察》
"""
    )

    codes = {issue.code for issue in check_report_text(text).issues}

    assert "curated_external_missing_inline_footnotes" in codes


def test_new_external_variable_map_accepts_multi_digit_inline_footnote_without_local_source_list():
    text = _quality_shell(
        """
<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_thin_layout_variant": "annual_broker_external_checklist"} -->

### 4.1 年报经营摘要

年报经营摘要[^1]。

### 4.2 研报观点与假设

研报预计盈利改善[^2]。

### 4.3 外部观点与待验证变量（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**供应链观察**

外部材料称上游供给节奏仍需验证。[^10]

## 引用来源

- [^1] 公司年报 | 《年度报告》
- [^2] 券商研报 | 《跟踪报告》
- [^10] 微信公众号精选观察 | 《供应链观察》
"""
    )

    codes = {issue.code for issue in check_report_text(text).issues}

    assert "curated_external_missing_inline_footnotes" not in codes
