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
