import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from report_quality import check_report_file, check_report_text


def test_minimal_quality_report_passes():
    fixture = Path(__file__).parent.parent / "fixtures" / "minimal_quality_report.md"
    result = check_report_file(fixture)
    assert result.passed
    assert result.issues == []


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


def test_external_viewpoint_overcompressed_warns_when_4_4_has_no_reasoning_cards():
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

    assert "external_viewpoint_overcompressed" in codes


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
