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
