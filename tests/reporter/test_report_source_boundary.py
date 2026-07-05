import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from report_source_boundary import check_report_source_boundary_text


def _codes(result):
    return {issue.code for issue in result.issues}


def test_flags_social_source_in_4_1_to_4_3_reference_list():
    text = """
## 四、深度分析

### 4.1 产业逻辑与竞争格局

正式分析正文引用知乎来源[^1]。

**本节引用来源：**
- [^1] 知乎 | 作者: A | 《社区观点》

### 4.2 业绩路径与多空分歧

业绩分析只应使用正式来源。

### 4.3 资金面与催化剂时间线

资金面分析。

### 4.4 精选外部观察（Preview）

> 精选外部材料仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

外部观点可以留在这里[^2]。

**本节引用来源：**
- [^2] 雪球专栏观察 | 《外部观点》
"""

    result = check_report_source_boundary_text(text)

    assert not result.passed
    assert "social_source_in_formal_analysis" in _codes(result)


def test_allows_external_sources_inside_4_4_when_disclaimed():
    text = """
## 四、深度分析

### 4.1 产业逻辑与竞争格局

正式分析正文引用公告来源[^1]。

**本节引用来源：**
- [^1] 公告 | 《2026年一季度报告》

### 4.2 业绩路径与多空分歧

业绩分析。

### 4.3 资金面与催化剂时间线

资金面分析。

### 4.4 精选外部观察（Preview）

> 精选外部材料仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

外部观点只在这里展示[^2]。

**本节引用来源：**
- [^2] 雪球专栏观察 | 《外部观点》

## 引用来源

- [^2] | **雪球专栏观察** | 《外部观点》

## 五、技术面分析
"""

    result = check_report_source_boundary_text(text)

    assert result.passed
    assert not result.issues


def test_formal_thin_external_map_region_is_allowed():
    text = """
## 四、深度分析

<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.1 正式材料要点

已确认：营业收入10亿元。

### 4.2 外部观点地图（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

#### 4.2.1 外部观点标题

**外部观点链**：外部材料讨论技术路线仍有分歧[^1]。
**支持线索**：知乎文章提到多款新品[^1]。
**反方约束**：雪球评论称官方未确认量产进度[^1]。
**待验证证据**：需等待正式公告验证[^1]。

**本节引用来源：**
- [^1] 知乎精选观察 | 《产业观察》

### 4.3 待验证清单

| 变量 | 为什么重要 | 需要什么证据 | 来源层级 |
|---|---|---|---|
| 量产进度 | 影响收入确认 | 正式公告 | 需正式验证 |
"""

    result = check_report_source_boundary_text(text)

    assert result.passed
    assert "social_source_in_formal_analysis" not in _codes(result)
    assert "external_viewpoint_leak_outside_4_4" not in _codes(result)


def test_formal_thin_social_token_in_4_1_still_fails():
    text = """
## 四、深度分析

<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.1 正式材料要点

雪球专栏观察认为公司营收增长确定。

### 4.2 外部观点地图（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**外部观点链**：外部材料讨论技术路线仍有分歧[^1]。

**本节引用来源：**
- [^1] 知乎精选观察 | 《产业观察》

### 4.3 待验证清单

| 变量 | 为什么重要 | 需要什么证据 | 来源层级 |
|---|---|---|---|
| 量产进度 | 影响收入确认 | 正式公告 | 需正式验证 |
"""

    result = check_report_source_boundary_text(text)

    assert not result.passed
    assert "social_source_in_formal_analysis" in _codes(result)


def test_formal_thin_social_token_in_4_3_still_fails():
    text = """
## 四、深度分析

<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich", "formal_section_support": {"industry": 0, "fundamentals": 0, "funding_support": 0, "catalyst_support": 0}} -->

### 4.1 正式材料要点

已确认：营业收入10亿元。

### 4.2 外部观点地图（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**外部观点链**：外部材料讨论技术路线仍有分歧[^1]。

**本节引用来源：**
- [^1] 知乎精选观察 | 《产业观察》

### 4.3 待验证清单

| 变量 | 为什么重要 | 需要什么证据 | 来源层级 |
|---|---|---|---|
| 量产进度 | 知乎精选观察认为影响收入确认 | 正式公告 | 需正式验证 |
"""

    result = check_report_source_boundary_text(text)

    assert not result.passed
    assert "social_source_in_formal_analysis" in _codes(result)


def test_flags_4_4_missing_display_only_disclaimer():
    text = """
## 四、深度分析

### 4.1 产业逻辑与竞争格局

正式分析正文引用公告来源[^1]。

**本节引用来源：**
- [^1] 公告 | 《2026年一季度报告》

### 4.4 精选外部观察（Preview）

外部观点展示但缺少免责声明[^2]。

**本节引用来源：**
- [^2] 微信公众号精选观察 | 《外部文章》
"""

    result = check_report_source_boundary_text(text)

    assert not result.passed
    assert "missing_4_4_disclaimer" in _codes(result)


def test_flags_external_viewpoint_label_outside_4_4_but_ignores_static_data_banner():
    text = """
**数据来源**: 雪球/社区讨论、公告、知乎、研报

## 一、执行摘要

本段错误泄漏了雪球专栏观察里的观点。

## 四、深度分析

### 4.1 产业逻辑与竞争格局

正式分析正文引用公告来源[^1]。

**本节引用来源：**
- [^1] 公告 | 《2026年一季度报告》

### 4.4 精选外部观察（Preview）

> 精选外部材料仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

外部观点展示[^2]。

**本节引用来源：**
- [^2] 雪球专栏观察 | 《外部观点》
"""

    result = check_report_source_boundary_text(text)

    assert not result.passed
    assert "external_viewpoint_leak_outside_4_4" in _codes(result)
