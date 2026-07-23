import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from report_prose_quality import check_report_prose_text


def _codes(result):
    return {issue.code for issue in result.issues}


def test_flags_long_paragraph_and_long_sentence_in_deep_analysis():
    long_sentence = (
        "在AI算力需求持续井喷的背景下，光模块行业正经历一场由技术架构升级驱动的结构性繁荣，"
        "公司深度绑定北美云厂商资本开支周期并受益于800G和1.6T持续放量，但这一判断仍需要"
        "回到订单兑现、毛利率变化、资本开支节奏和客户集中度等变量逐一验证，不能只停留在行业景气叙事上"
    )
    text = f"""
## 四、深度分析

### 4.1 产业逻辑与竞争格局

{long_sentence}。{long_sentence}。

### 4.2 业绩路径与多空分歧

业绩路径需要拆成营收、毛利率和费用率。

### 4.3 资金面与催化剂时间线

催化剂需要落到半年报和客户订单。
"""

    result = check_report_prose_text(text)

    assert result.passed
    assert "long_paragraph" in _codes(result)
    assert "long_sentence" in _codes(result)


def test_flags_theme_repetition_across_4_1_to_4_3():
    text = """
## 四、深度分析

### 4.1 产业逻辑与竞争格局

AI算力、800G、1.6T、硅光、CPO 是本节产业主线。

### 4.2 业绩路径与多空分歧

AI算力、800G、1.6T、硅光、CPO 又被完整重复成业绩解释。

### 4.3 资金面与催化剂时间线

AI算力、800G、1.6T、硅光、CPO 再次出现，导致资金面章节没有自己的信息边界。
"""

    result = check_report_prose_text(text)

    assert "repeated_theme_across_sections" in _codes(result)
    issue = next(i for i in result.issues if i.code == "repeated_theme_across_sections")
    assert "800G" in issue.evidence
    assert "4.1/4.2/4.3" in issue.message


def test_flags_aiish_transitions_and_strong_assertions():
    text = """
## 四、深度分析

### 4.1 产业逻辑与竞争格局

综合来看，在AI算力需求持续井喷的背景下，公司已经锁定近乎垄断级领先地位。

### 4.2 业绩路径与多空分歧

与此同时，核心驱动力仍然明确。

### 4.3 资金面与催化剂时间线

展望未来，结构性繁荣仍将延续。
"""

    result = check_report_prose_text(text)

    assert "aiish_transition_overuse" in _codes(result)
    assert "strong_assertion_wording" in _codes(result)


def test_flags_duplicate_4_4_citation_sources():
    text = """
## 四、深度分析

### 4.4 精选外部观察（Preview）

正文引用同一来源的两个脚注[^1][^2]。

**本节引用来源：**
- [^1] 微信公众号精选观察 | 作者: A | 《同一篇文章》 | https://example.com/a
- [^2] 微信公众号精选观察 | 作者: A | 《同一篇文章》 | https://example.com/a
"""

    result = check_report_prose_text(text)

    assert "duplicate_4_4_citation_source" in _codes(result)
    issue = next(i for i in result.issues if i.code == "duplicate_4_4_citation_source")
    assert "https://example.com/a" in issue.evidence


def test_table_rows_with_citations_are_not_long_prose():
    long_cell = (
        "这是一条非常长的表格单元格，用来承载财务变量、业务含义、验证指标和引用，"
        "它应该被视为结构化表格内容，而不是普通大段 prose，因此不应该触发长段落或长句 warning"
    )
    text = f"""
## 四、深度分析

### 4.2 业绩路径与多空分歧

| 变量 | 当前证据 | 对业绩路径的含义 | 来源 |
|------|----------|------------------|------|
| 订单 | {long_cell} | 需要看后续兑现 | [^1] |
"""

    result = check_report_prose_text(text)

    assert "long_paragraph" not in _codes(result)
    assert "long_sentence" not in _codes(result)


def test_necessary_one_line_context_does_not_trigger_repetition_warning():
    text = """
## 四、深度分析

### 4.1 产业逻辑与竞争格局

AI算力、800G、1.6T 是产业需求和技术路线的主线。

### 4.2 业绩路径与多空分歧

业绩路径主要看毛利率、费用率和订单兑现。

### 4.3 资金面与催化剂时间线

资金面只在一句话里提醒：若800G订单兑现不及预期，半年报催化会被削弱。
"""

    result = check_report_prose_text(text)

    assert "repeated_theme_across_sections" not in _codes(result)


def test_flags_theme_reexpanded_outside_owner_in_multiple_paragraphs():
    text = """
## 四、深度分析

### 4.1 产业逻辑与竞争格局

800G 是技术路线和产业需求的主线。

### 4.2 业绩路径与多空分歧

800G 放量带动营收增长，但还要看订单兑现。

800G 产品价格变化还会影响毛利率和利润弹性。

### 4.3 资金面与催化剂时间线

资金面等待半年报验证。
"""

    result = check_report_prose_text(text)

    assert "theme_reexpanded_outside_owner" in _codes(result)
    issue = next(i for i in result.issues if i.code == "theme_reexpanded_outside_owner")
    assert issue.section == "4.2"
    assert "高速光互连技术路线" in issue.evidence
    assert '"offending_section": "4.2"' in issue.evidence


def test_allows_multiple_cited_external_v2_deltas_with_adjacent_evidence():
    text = """
## 四、深度分析

### 4.1 官方材料确认

800G 是正式材料中的产品路线。

### 4.2 机构观点

机构假设需要订单兑现。

### 4.3 外部观察与待验证变量（Preview，不参与评分）

**供应链交付**

相对正式材料/机构假设，外部材料新增的待验证点：800G交付节奏仍需验证[^1]。

> **外部原文依据**：外部文章记录上游物料紧张和交付安排。

**同业路线**

外部新增待验证变量：NPO路线进入验证窗口[^2]。

> **缓存材料摘录**：缓存文章讨论同业NPO验证节奏。
"""

    result = check_report_prose_text(text)

    assert "theme_reexpanded_outside_owner" not in _codes(result)


def test_external_v2_delta_without_adjacent_evidence_still_warns():
    text = """
## 四、深度分析

### 4.1 官方材料确认

800G 是正式材料中的产品路线。

### 4.2 机构观点

机构假设需要订单兑现。

### 4.3 外部观察与待验证变量（Preview，不参与评分）

相对正式材料/机构假设，外部材料新增的待验证点：800G交付节奏仍需验证[^1]。

外部新增待验证变量：800G客户认证节奏仍需验证[^2]。
"""

    result = check_report_prose_text(text)

    assert "theme_reexpanded_outside_owner" in _codes(result)


def test_allows_single_borrowed_theme_table_row_without_reexpanded_warning():
    text = """
## 四、深度分析

### 4.1 产业逻辑与竞争格局

800G 是技术路线和产业需求的主线。

### 4.2 业绩路径与多空分歧

| 变量 | 当前证据 | 对业绩路径的含义 | 来源 |
|------|----------|------------------|------|
| 订单 | 800G 放量 | 支撑营收 | [^1] |

### 4.3 资金面与催化剂时间线

资金面等待半年报验证。
"""

    result = check_report_prose_text(text)

    assert "theme_reexpanded_outside_owner" not in _codes(result)


def test_allows_borrowed_theme_repeated_across_multiple_table_rows_without_reexpanded_warning():
    text = """
## 四、深度分析

### 4.1 产业逻辑与竞争格局

800G 和 1.6T 是技术路线和产业需求的主线。

### 4.2 业绩路径与多空分歧

| 变量 | 当前证据 | 对业绩路径的含义 | 来源 |
|------|----------|------------------|------|
| 订单 | 800G 放量 | 支撑营收 | [^1] |
| 利润 | 1.6T 放量 | 支撑毛利率 | [^2] |

### 4.3 资金面与催化剂时间线

资金面等待半年报验证。
"""

    result = check_report_prose_text(text)

    assert "theme_reexpanded_outside_owner" not in _codes(result)


def test_flags_nested_heading_inside_deep_analysis_section():
    text = """
## 四、深度分析

### 4.1 产业逻辑与竞争格局

## 产业需求与市场驱动

公司处于高速成长行业。

### 4.2 业绩路径与多空分歧

业绩路径需要看毛利率。

### 4.3 资金面与催化剂时间线

催化剂需要落到半年报。
"""

    result = check_report_prose_text(text)

    assert "nested_heading_in_deep_analysis" in _codes(result)
    issue = next(i for i in result.issues if i.code == "nested_heading_in_deep_analysis")
    assert issue.section == "4.1"
    assert "## 产业需求与市场驱动" in issue.evidence


def test_duplicate_4_4_citations_fall_back_to_source_author_title_when_url_missing():
    text = """
## 四、深度分析

### 4.4 精选外部观察（Preview）

正文引用同一无 URL 来源的两个脚注[^1][^2]。

**本节引用来源：**
- [^1] 雪球专栏观察 | 作者: 研究员A | 《同一篇无URL文章》
- [^2] 雪球专栏观察 | 作者: 研究员A | 《同一篇无URL文章》
"""

    result = check_report_prose_text(text)

    assert "duplicate_4_4_citation_source" in _codes(result)
    issue = next(i for i in result.issues if i.code == "duplicate_4_4_citation_source")
    assert "雪球专栏观察|研究员A|同一篇无URL文章" in issue.evidence


def test_flags_duplicate_4_4_sources_from_terminal_global_citations():
    text = """
## 四、深度分析

### 4.4 上行 / 下行条件与股价推演

同一来源被两个脚注分别引用[^1][^2]。

## 综合风险评分

风险正文。

## 引用来源

- [^1] | **微信公众号精选观察** | 作者: A | 《同一篇文章》 | https://example.com/a
- [^2] | **微信公众号精选观察** | 作者: A | 《同一篇文章》 | https://example.com/a
"""

    result = check_report_prose_text(text)

    issue = next(i for i in result.issues if i.code == "duplicate_4_4_citation_source")
    assert "https://example.com/a" in issue.evidence


def test_terminal_global_citations_use_source_author_title_without_url():
    text = """
## 四、深度分析

### 4.4 上行 / 下行条件与股价推演

同一无 URL 来源被两个脚注分别引用[^1][^2]。

## 综合风险评分

风险正文。

## 引用来源

- [^1] | **雪球专栏观察** | 作者: 研究员A | 《同一篇无URL文章》
- [^2] | **雪球专栏观察** | 作者: 研究员A | 《同一篇无URL文章》
"""

    result = check_report_prose_text(text)

    issue = next(i for i in result.issues if i.code == "duplicate_4_4_citation_source")
    assert "雪球专栏观察|研究员A|同一篇无URL文章" in issue.evidence


def test_repeated_4_4_use_of_one_ref_is_not_a_duplicate_source():
    text = """
## 四、深度分析

### 4.4 上行 / 下行条件与股价推演

同一脚注在不同条件中重复使用[^1]，但仍是同一个引用编号[^1]。

## 综合风险评分

风险正文。

## 引用来源

- [^1] | **微信公众号精选观察** | 作者: A | 《同一篇文章》 | https://example.com/a
"""

    result = check_report_prose_text(text)

    assert "duplicate_4_4_citation_source" not in _codes(result)


def test_terminal_duplicate_sources_unused_by_4_4_are_ignored():
    text = """
## 四、深度分析

### 4.4 上行 / 下行条件与股价推演

本节只引用独立来源[^1]。

## 综合风险评分

风险正文。

## 引用来源

- [^1] | **公司年报** | 《年度报告》 | https://example.com/annual
- [^2] | **微信公众号精选观察** | 作者: A | 《同一篇文章》 | https://example.com/a
- [^3] | **微信公众号精选观察** | 作者: A | 《同一篇文章》 | https://example.com/a
"""

    result = check_report_prose_text(text)

    assert "duplicate_4_4_citation_source" not in _codes(result)
