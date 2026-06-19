import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from reporter.sections.source_intake_evidence_renderer import SourceIntakeEvidenceRenderer
from skill_pipeline import SkillContext
from source_adapter import SynthesisItem


def _make_item(**kwargs) -> SynthesisItem:
    defaults = {
        "title": "",
        "content": "",
        "author": "",
        "source_platform": "公告",
        "url": "",
        "publish_time": "",
        "interaction_score": 0,
        "extra": {},
    }
    defaults.update(kwargs)
    return SynthesisItem(**defaults)


def _make_ctx(
    enabled=True,
    status="ok",
    items=None,
    keep_items=None,
    demote_items=None,
    fulltext_items=None,
) -> SkillContext:
    return SkillContext(input={
        "stock_name": "测试股",
        "source_intake_enabled": enabled,
        "source_intake_status": status,
        "source_intake_items": items or [],
        "external_evidence_keep_items": keep_items or [],
        "external_evidence_demote_items": demote_items or [],
        "periodic_report_fulltext_items": fulltext_items or [],
        "source_intake_summary": {"status": status, "count": len(items or [])},
    })


def test_disabled_returns_empty():
    renderer = SourceIntakeEvidenceRenderer()
    ctx = _make_ctx(enabled=False)
    assert renderer.render(ctx) == ""


def test_enabled_but_empty_returns_empty():
    renderer = SourceIntakeEvidenceRenderer()
    ctx = _make_ctx(enabled=True, status="ok", items=[])
    assert renderer.render(ctx) == ""


def test_error_status_returns_empty():
    renderer = SourceIntakeEvidenceRenderer()
    ctx = _make_ctx(enabled=True, status="error", items=[_make_item()])
    assert renderer.render(ctx) == ""


def test_section_title_and_disclaimer_present():
    item = _make_item(
        title="一季度业绩预告",
        extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "## Source Intake 分层证据观察" in result
    assert "本节仅展示结构化外部证据来源分层" in result
    assert "官方公告可用于事实确认" in result
    assert "新闻与券商研报仅作为专业观察或背景线索" in result


def test_official_announcement_renders_as_confirmed_fact():
    item = _make_item(
        title="一季度业绩预告",
        publish_time="2026-04-15",
        extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "官方公告" in result
    assert "confirmed_fact" in result
    assert "一季度业绩预告" in result


def test_news_renders_as_professional_observation():
    item = _make_item(
        title="存储芯片概念下跌",
        source_platform="新闻",
        publish_time="2026-06-12",
        extra={"source_type": "news", "source_credit": 60, "verification_status": "professional_observation"},
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "东方财富新闻" in result
    assert "professional_observation" in result
    assert "confirmed_fact" not in result


def test_research_report_renders_as_professional_observation():
    item = _make_item(
        title="三季度收入同比增长",
        source_platform="研报",
        publish_time="2026-05-20",
        extra={"source_type": "research_report", "source_credit": 65, "verification_status": "professional_observation"},
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "券商研报摘要" in result
    assert "professional_observation" in result
    assert "confirmed_fact" not in result


def test_periodic_report_excerpt_renders_dedicated_section():
    item = _make_item(
        title="2025年年度报告 | 管理层观点",
        content="管理层认为，公司围绕航空航天领域高性能碳纤维需求推进产业化。",
        publish_time="2026-04-15",
        extra={
            "source_type": "periodic_report_excerpt",
            "source_credit": 75,
            "verification_status": "management_view",
            "periodic_report_excerpt_id": "abc-management_view-0",
        },
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "| 定期报告摘录 | 1 | 75 | management_view | 年报/半年报规则摘录 |" in result
    assert "### 定期报告关键摘录" in result
    assert "管理层观点" in result
    assert "航空航天领域高性能碳纤维需求" in result
    assert "confirmed_fact" not in result


def test_malformed_periodic_excerpt_confirmed_fact_is_guarded():
    item = _make_item(
        title="2025年年度报告 | 管理层观点",
        content="管理层讨论与分析摘录。",
        publish_time="2026-04-15",
        extra={
            "source_type": "periodic_report_excerpt",
            "source_credit": 75,
            "verification_status": "confirmed_fact",
            "periodic_report_excerpt_id": "abc-management_view-0",
        },
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "confirmed_fact" not in result
    assert "management_view" in result


def test_malformed_periodic_fulltext_analysis_confirmed_fact_is_guarded():
    item = _make_item(
        title="2025年年度报告 | 定期报告全文摘要（实验路径）",
        content="公司画像、主营业务表现和财务风险摘要。",
        publish_time="2026-04-15",
        extra={
            "source_type": "periodic_report_fulltext_analysis",
            "source_credit": 95,
            "verification_status": "confirmed_fact",
            "claim_status": "confirmed_fact",
        },
    )
    ctx = _make_ctx(items=[item], fulltext_items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "confirmed_fact" not in result
    assert "professional_analysis" in result


def test_periodic_report_fulltext_items_renders_dedicated_experimental_section():
    item = _make_item(
        title="2025年年度报告 | 定期报告全文摘要（实验路径）",
        content="# 定期报告全文判断摘要\n\n## 必备经营指标摘录\n\n收入情况。",
        publish_time="2026-04-15",
        extra={
            "source_type": "periodic_report_fulltext_analysis",
            "source_credit": 75,
            "verification_status": "professional_analysis",
            "claim_status": "professional_analysis",
            "experimental": True,
        },
    )
    ctx = _make_ctx(items=[item], fulltext_items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "### 定期报告全文摘要（实验路径）" in result
    assert "2026-04-15" in result
    assert "2025年年度报告" in result
    assert "定期报告全文摘要（实验路径）" in result
    assert "75" in result
    assert "professional_analysis" in result
    assert "experimental" in result.lower() or "实验" in result
    assert "| 定期报告全文摘要 | 1 | 75 | professional_analysis | 年报/半年报全文材料层 |" in result


def test_fulltext_metadata_markdown_is_sanitized_without_double_escaping():
    item = _make_item(
        title="2025年年度报告 | 已转义\\|字段\n下一行",
        content="摘要正文。",
        publish_time="2026-04-15 | 注入\n坏行",
        extra={
            "source_type": "periodic_report_fulltext_analysis",
            "source_credit": 75,
            "verification_status": "professional_analysis",
            "experimental": True,
        },
    )
    ctx = _make_ctx(items=[], fulltext_items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)

    assert "2026-04-15 \\| 注入 坏行" in result
    assert "2025年年度报告 \\| 已转义\\|字段 下一行" in result
    assert "\\\\|字段" not in result


def test_representative_table_cells_escape_unescaped_pipes_only():
    item = _make_item(
        title="公司|公告",
        content="已转义\\|字段，收入增长|毛利率提升。",
        publish_time="2026-04-15|bad",
        extra={
            "source_type": "exchange_announcement",
            "source_credit": 95,
            "verification_status": "confirmed_fact",
        },
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)

    assert "2026-04-15\\|bad" in result
    assert "公司\\|公告" in result
    assert "已转义\\|字段" in result
    assert "已转义\\\\|字段" not in result


def test_periodic_report_fulltext_items_render_without_source_intake_items():
    item = _make_item(
        title="2025年年度报告 | 定期报告全文摘要（实验路径）",
        content="全文摘要内容。",
        publish_time="2026-04-15",
        extra={
            "source_type": "periodic_report_fulltext_analysis",
            "source_credit": 75,
            "verification_status": "professional_analysis",
            "experimental": True,
        },
    )
    ctx = _make_ctx(items=[], fulltext_items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "### 定期报告全文摘要（实验路径）" in result
    assert "2025年年度报告" in result
    assert "professional_analysis" in result


def test_periodic_report_fulltext_section_renders_each_item():
    annual = _make_item(
        title="2025年年度报告 | 定期报告全文摘要（实验路径）",
        content="年度摘要。",
        publish_time="2026-04-15",
        extra={
            "source_type": "periodic_report_fulltext_analysis",
            "source_credit": 75,
            "verification_status": "professional_analysis",
            "experimental": True,
        },
    )
    interim = _make_item(
        title="2025年半年度报告 | 定期报告全文摘要（实验路径）",
        content="半年度摘要。",
        publish_time="2025-08-30",
        extra={
            "source_type": "periodic_report_fulltext_analysis",
            "source_credit": 75,
            "verification_status": "professional_analysis",
            "experimental": True,
        },
    )
    ctx = _make_ctx(items=[], fulltext_items=[annual, interim])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "2025年年度报告" in result
    assert "2025年半年度报告" in result
    assert "年度摘要" in result
    assert "半年度摘要" in result


def test_malformed_fulltext_item_confirmed_fact_still_renders_professional_analysis():
    item = _make_item(
        title="2025年年度报告 | 定期报告全文摘要（实验路径）",
        content="全文摘要内容。",
        publish_time="2026-04-15",
        extra={
            "source_type": "periodic_report_fulltext_analysis",
            "source_credit": 85,
            "verification_status": "confirmed_fact",
            "claim_status": "confirmed_fact",
            "experimental": True,
        },
    )
    ctx = _make_ctx(items=[item], fulltext_items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "confirmed_fact" not in result
    assert "fact_candidate" not in result
    assert "professional_analysis" in result


def test_fulltext_item_excluded_from_representative_rows():
    fulltext = _make_item(
        title="2025年年度报告 | 定期报告全文摘要（实验路径）",
        content="公司画像、主营业务表现和财务风险摘要。",
        publish_time="2026-04-15",
        extra={"source_type": "periodic_report_fulltext_analysis", "source_credit": 75, "verification_status": "professional_analysis"},
    )
    official = _make_item(
        title="2026年第一季度业绩预告",
        content="收入下降。",
        publish_time="2026-04-15",
        extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
    )
    ctx = _make_ctx(items=[official, fulltext], fulltext_items=[fulltext])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    representative = result.split("### 代表性证据摘录", 1)[1].split("### 定期报告全文摘要（实验路径）", 1)[0]
    assert "2026年第一季度业绩预告" in representative
    assert "定期报告全文摘要（实验路径）" not in representative


def test_fulltext_item_excluded_from_periodic_excerpt_table():
    fulltext = _make_item(
        title="2025年年度报告 | 定期报告全文摘要（实验路径）",
        content="全文摘要。",
        publish_time="2026-04-15",
        extra={"source_type": "periodic_report_fulltext_analysis", "source_credit": 75, "verification_status": "professional_analysis"},
    )
    excerpt = _make_item(
        title="2025年年度报告 | 管理层观点",
        content="管理层观点摘录。",
        publish_time="2026-04-15",
        extra={"source_type": "periodic_report_excerpt", "source_credit": 75, "verification_status": "management_view"},
    )
    ctx = _make_ctx(items=[excerpt, fulltext], fulltext_items=[fulltext])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    periodic = result.split("### 定期报告关键摘录", 1)[1].split("### 定期报告全文摘要（实验路径）", 1)[0]
    assert "管理层观点" in periodic
    assert "定期报告全文摘要（实验路径）" not in periodic


def test_fulltext_long_markdown_content_is_heading_downgraded_and_truncated():
    long_content = "# 定期报告全文判断摘要\n\n## 必备经营指标摘录\n\n" + "经营指标内容。" * 500
    item = _make_item(
        title="2025年年度报告 | 定期报告全文摘要（实验路径）",
        content=long_content,
        publish_time="2026-04-15",
        extra={"source_type": "periodic_report_fulltext_analysis", "source_credit": 75, "verification_status": "professional_analysis"},
    )
    ctx = _make_ctx(items=[item], fulltext_items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "# 定期报告全文判断摘要" not in result
    # Heading downgrade happens inside content preview, but source section heading stays as H3.
    assert "#### 必备经营指标摘录" in result
    assert "### 定期报告全文摘要（实验路径）" in result
    assert "..." in result
    assert len(result) < len(long_content) + 1000


def test_fulltext_preview_preserves_markdown_table_line_breaks():
    content = "\n".join([
        "# 定期报告全文判断摘要",
        "",
        "## 必备经营指标摘录",
        "",
        "### 分产品/业务毛利率",
        "| 项目 | 收入 | 毛利率 |",
        "|------|------|--------|",
        "| 碳纤维 | 44349.44万元 | 55.21% |",
    ])
    item = _make_item(
        title="2025年年度报告 | 定期报告全文摘要（实验路径）",
        content=content,
        publish_time="2026-04-15",
        extra={
            "source_type": "periodic_report_fulltext_analysis",
            "source_credit": 75,
            "verification_status": "professional_analysis",
        },
    )
    ctx = _make_ctx(items=[item], fulltext_items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)

    assert "\n##### 分产品/业务毛利率\n| 项目 | 收入 | 毛利率 |\n|------|------|--------|" in result
    assert "分产品/业务毛利率 | 项目 | 收入" not in result


def test_renderer_does_not_mutate_fulltext_ctx_or_item():
    item = _make_item(
        title="2025年年度报告 | 定期报告全文摘要（实验路径）",
        content="# 摘要\n\n正文。",
        publish_time="2026-04-15",
        extra={"source_type": "periodic_report_fulltext_analysis", "source_credit": 75, "verification_status": "professional_analysis"},
    )
    ctx = _make_ctx(items=[item], fulltext_items=[item])
    original_input = deepcopy(ctx.input)
    original_output = deepcopy(ctx.output)
    original_extra = deepcopy(item.extra)
    renderer = SourceIntakeEvidenceRenderer()
    renderer.render(ctx)
    assert ctx.input == original_input
    assert ctx.output == original_output
    assert item.extra == original_extra


def test_malformed_news_claiming_confirmed_fact_is_normalized_down():
    item = _make_item(
        title="新闻标题",
        source_platform="新闻",
        extra={"source_type": "news", "source_credit": 60, "verification_status": "confirmed_fact"},
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "professional_observation" in result
    assert "confirmed_fact" not in result


def test_malformed_research_report_claiming_confirmed_fact_is_normalized_down():
    item = _make_item(
        title="研报标题",
        source_platform="研报",
        extra={"source_type": "research_report", "source_credit": 65, "verification_status": "confirmed_fact"},
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "professional_observation" in result
    assert "confirmed_fact" not in result


def test_periodic_excerpts_are_excluded_from_representative_rows():
    official = _make_item(
        title="2026年第一季度业绩预告",
        content="报告期内，客户需求阶段性减少，其中收入下降约50%-60%。",
        publish_time="2026-04-15",
        extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
    )
    excerpt = _make_item(
        title="2025年年度报告 | 财报排雷观察",
        content="存货、应收账款和经营现金流需结合附注继续核查。",
        publish_time="2026-04-15",
        extra={
            "source_type": "periodic_report_excerpt",
            "source_credit": 75,
            "verification_status": "financial_forensics",
            "periodic_report_excerpt_id": "abc-financial_forensics-0",
        },
    )
    ctx = _make_ctx(items=[official, excerpt])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    representative = result.split("### 代表性证据摘录", 1)[1]
    assert "2026年第一季度业绩预告" in representative
    assert "财报排雷观察" not in representative
    assert "### 定期报告关键摘录" in result


def test_credit_tier_summary_uses_dynamic_counts():
    items = [
        _make_item(extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"}),
        _make_item(extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"}),
        _make_item(extra={"source_type": "news", "source_credit": 60, "verification_status": "professional_observation"}),
        _make_item(extra={"source_type": "research_report", "source_credit": 65, "verification_status": "professional_observation"}),
    ]
    ctx = _make_ctx(items=items)
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "| 官方公告 | 2 |" in result
    assert "| 东方财富新闻 | 1 |" in result
    assert "| 券商研报摘要 | 1 |" in result


def test_representative_rows_capped_at_six():
    items = [
        _make_item(
            title=f"公告{i}",
            publish_time="2026-04-15",
            extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
        )
        for i in range(10)
    ]
    ctx = _make_ctx(items=items)
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    # Count data rows in the representative table (rows starting with a date).
    data_rows = [ln for ln in result.splitlines() if ln.startswith("| 2026-04-15 |")]
    assert len(data_rows) == 6


def test_representative_rows_priority_order():
    items = [
        _make_item(title="新闻1", extra={"source_type": "news", "source_credit": 60, "verification_status": "professional_observation"}),
        _make_item(title="研报1", extra={"source_type": "research_report", "source_credit": 65, "verification_status": "professional_observation"}),
        _make_item(title="公告1", extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"}),
    ]
    ctx = _make_ctx(items=items)
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    marker_rows = [ln for ln in result.splitlines() if ln.startswith("| — |")]
    assert len(marker_rows) == 3
    assert "公告1" in marker_rows[0]
    assert "研报1" in marker_rows[1]
    assert "新闻1" in marker_rows[2]


def test_citation_markers_removed():
    item = _make_item(
        title="标题[^1]",
        content="正文[2] 内容",
        extra={"source_type": "news", "source_credit": 60, "verification_status": "professional_observation"},
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "[^1]" not in result
    assert "[2]" not in result
    assert "标题" in result


def test_agent_reach_text_removed():
    item = _make_item(
        title="AgentReach(web) 某标题",
        content="来自 AgentReach(twitter) 的内容",
        extra={"source_type": "news", "source_credit": 60, "verification_status": "professional_observation"},
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "AgentReach" not in result


def test_long_raw_urls_not_exposed_in_summary_text():
    item = _make_item(
        title="标题",
        content="https://www.cninfo.com.cn/new/disclosure/detail?stockCode=300661&announcementId=123456789 正文",
        url="https://www.cninfo.com.cn/new/disclosure/detail?stockCode=300661&announcementId=123456789",
        extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "https://www.cninfo.com.cn/new/disclosure/detail" not in result


def test_markdown_pipe_escaped():
    item = _make_item(
        title="a|b|c",
        content="x|y量产",
        extra={"source_type": "news", "source_credit": 60, "verification_status": "professional_observation"},
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "a\\|b\\|c" in result
    assert "x\\|y量产" in result


def test_unknown_source_type_fallback():
    item = _make_item(
        title="未知来源",
        extra={"source_type": "weird_source", "source_credit": 50, "verification_status": "professional_observation"},
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "其他来源" in result


def test_renderer_does_not_mutate_ctx():
    item = _make_item(
        title="标题",
        extra={"source_type": "news", "source_credit": 60, "verification_status": "professional_observation"},
    )
    ctx = _make_ctx(items=[item])
    original_input = deepcopy(ctx.input)
    original_output = deepcopy(ctx.output)
    renderer = SourceIntakeEvidenceRenderer()
    renderer.render(ctx)
    assert ctx.input == original_input
    assert ctx.output == original_output


def test_renderer_does_not_mutate_item_extra():
    extra = {"source_type": "news", "source_credit": 60, "verification_status": "professional_observation"}
    item = _make_item(title="标题", extra=extra)
    ctx = _make_ctx(items=[item])
    original_extra = deepcopy(item.extra)
    renderer = SourceIntakeEvidenceRenderer()
    renderer.render(ctx)
    assert item.extra == original_extra


def test_uses_merged_external_evidence_keep_items_when_source_intake_items_empty():
    item = _make_item(
        title="合并证据",
        extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
    )
    ctx = _make_ctx(items=[], keep_items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "合并证据" in result
    assert "官方公告" in result


def test_credit_range_rendered_when_multiple_credit_values():
    items = [
        _make_item(extra={"source_type": "news", "source_credit": 60, "verification_status": "professional_observation"}),
        _make_item(extra={"source_type": "news", "source_credit": 65, "verification_status": "professional_observation"}),
    ]
    ctx = _make_ctx(items=items)
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "60-65" in result


def test_jina_pdf_metadata_stripped_from_excerpt():
    item = _make_item(
        title="2026年第一季度报告",
        content=(
            "Title: 1225145344.PDF\n"
            "URL Source: http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777\n"
            "Published Time: Wed, 22 Apr 2026 09:11:39 GMT\n"
            "Number of Pages: 10\n"
            "Markdown Content:\n"
            "# 2026年第一季度报告\n"
            "营业收入同比下降54.6%。"
        ),
        publish_time="2026-04-22",
        extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "Title:" not in result
    assert "URL Source:" not in result
    assert "Published Time:" not in result
    assert "Number of Pages:" not in result
    assert "Markdown Content:" not in result
    assert "营业收入同比下降54.6%" in result


    item = _make_item(
        title="标题",
        extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)
    assert "| 时间 | 来源层级 | 证据摘要 | 信用 | 用途 |" in result


def test_official_announcement_excerpt_skips_boilerplate_for_business_fact():
    item = _make_item(
        title="2026年第一季度报告",
        content=(
            "2026年第一季度报告 1 证券代码：300777 证券简称：中简科技 "
            "公告编号：2026-018 本公司及董事会全体成员保证信息披露的内容真实、准确、完整，"
            "没有虚假记载、误导性陈述或者重大遗漏。报告期内，公司实现营业收入1.23亿元，"
            "归属于上市公司股东的净利润同比下降54.6%，研发费用同比增长182.4%。"
        ),
        publish_time="2026-04-23",
        extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)

    assert "营业收入1.23亿元" in result
    assert "净利润同比下降54.6%" in result
    assert "本公司及董事会全体成员保证" not in result
    assert "证券代码：300777" not in result


def test_representative_rows_prefer_informative_announcements_over_title_only_low_value_items():
    items = [
        _make_item(
            title="公司2025年年度权益分派实施公告",
            publish_time="2026-06-10",
            extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
        ),
        _make_item(
            title="2026年第一季度报告",
            content="报告期内，公司实现营业收入1.23亿元，研发费用同比增长182.4%。",
            publish_time="2026-04-23",
            extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
        ),
    ]
    ctx = _make_ctx(items=items)
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)

    data_rows = [line for line in result.splitlines() if line.startswith("| 2026-")]
    assert "营业收入1.23亿元" in data_rows[0]
    assert "年度权益分派实施公告" not in data_rows[0]


def test_representative_rows_prefer_medium_credit_excerpt_over_title_only_official_metadata():
    items = [
        _make_item(
            title="2025年年度报告",
            publish_time="2026-04-15",
            extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
        ),
        _make_item(
            title="券商研报关注研发投入",
            content="券商研报认为，公司研发投入同比增长182.4%，但该线索仍非官方确认。",
            publish_time="2026-05-10",
            extra={"source_type": "research_report", "source_credit": 65, "verification_status": "professional_observation"},
        ),
    ]
    ctx = _make_ctx(items=items)
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)

    data_rows = [line for line in result.splitlines() if line.startswith("| 2026-")]
    assert "券商研报关注研发投入" in data_rows[0]
    assert "2025年年度报告" not in data_rows[0]


def test_official_excerpt_normalizes_pdf_spacing_artifacts():
    item = _make_item(
        title="2026年一季度报告",
        content="3、研发费用同比上升 17 8.72 %，客户需求阶段性减 少导致收入下降。",
        publish_time="2026-04-23",
        extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
    )
    ctx = _make_ctx(items=[item])
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)

    assert "研发费用同比上升178.72%" in result
    assert "减少导致收入下降" in result
    assert "17 8.72 %" not in result


def test_representative_rows_prioritize_capex_investment_and_buyback_announcements():
    items = [
        _make_item(
            title="公司2025年年度权益分派实施公告",
            publish_time="2026-06-10",
            extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
        ),
        _make_item(
            title="关于对外投资建设新材料产业化项目的公告",
            content="公司拟投资8.5亿元建设新材料产业化项目，项目达产后将新增高性能碳纤维产能。",
            publish_time="2026-05-20",
            extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
        ),
        _make_item(
            title="关于回购公司股份方案的公告",
            content="公司拟使用自有资金以集中竞价方式回购股份，回购金额不低于1亿元。",
            publish_time="2026-05-10",
            extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
        ),
    ]
    ctx = _make_ctx(items=items)
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)

    data_rows = [line for line in result.splitlines() if line.startswith("| 2026-")]
    assert "对外投资建设新材料产业化项目" in data_rows[0]
    assert "回购公司股份方案" in data_rows[1]
    assert "年度权益分派" not in data_rows[0]
    assert "年度权益分派" not in data_rows[1]


def test_representative_rows_demote_market_wide_list_news():
    items = [
        _make_item(
            title="117股股东户数连续下降 （附股）",
            content="-2.69 7 -22.62 -23.96 002819 东方中科 26022 -2.69 8 -21.42 -18.68 300123 ST亚光",
            source_platform="新闻",
            publish_time="2026-06-09",
            extra={"source_type": "news", "source_credit": 60, "verification_status": "professional_observation"},
        ),
        _make_item(
            title="中简科技获机构调研关注",
            content="媒体报道显示，中简科技近期获机构调研关注，投资者关注公司新材料产能建设和订单节奏。",
            source_platform="新闻",
            publish_time="2026-06-08",
            extra={"source_type": "news", "source_credit": 60, "verification_status": "professional_observation"},
        ),
    ]
    ctx = _make_ctx(items=items)
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)

    data_rows = [line for line in result.splitlines() if line.startswith("| 2026-")]
    assert "获机构调研关注" in data_rows[0]
    assert "117股股东户数连续下降" not in data_rows[0]


def test_representative_rows_do_not_fill_cap_with_market_wide_list_news():
    items = [
        _make_item(
            title="2026年第一季度业绩预告",
            content="报告期内，客户需求阶段性减少，其中收入下降约50%-60%。",
            publish_time="2026-04-15",
            extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
        ),
        _make_item(
            title="2026年一季度报告",
            content="研发费用同比上升178.72%，公司持续加大研发投入。",
            publish_time="2026-04-23",
            extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
        ),
        _make_item(
            title="2025年三季度报告",
            content="应收账款同比增长22%，主要系报告期内营业收入增加所致。",
            publish_time="2025-10-29",
            extra={"source_type": "exchange_announcement", "source_credit": 95, "verification_status": "confirmed_fact"},
        ),
        _make_item(
            title="117股股东户数连续下降 （附股）",
            content="-2.69 7 -22.62 -23.96 002819 东方中科 26022 -2.69 8 -21.42 -18.68 300123 ST亚光",
            source_platform="新闻",
            publish_time="2026-06-09",
            extra={"source_type": "news", "source_credit": 60, "verification_status": "professional_observation"},
        ),
        _make_item(
            title="解密主力资金出逃股连续5日净流出661股",
            content="4.03 4.44 -23.25 002130 沃尔核材 6 4.01 7.72 -13.77 002400 省广集团",
            source_platform="新闻",
            publish_time="2026-06-11",
            extra={"source_type": "news", "source_credit": 60, "verification_status": "professional_observation"},
        ),
        _make_item(
            title="120股筹码连续3期集中",
            content="-2.69 7 -23.54 -24.46 002819 东方中科 26022 -2.69 8 -23.33 -20.18",
            source_platform="新闻",
            publish_time="2026-06-10",
            extra={"source_type": "news", "source_credit": 60, "verification_status": "professional_observation"},
        ),
        _make_item(
            title="14只创业板股最新股东户数降逾一成",
            content="300074 华平股份 25760 -2.79 -12.01 301233 盛帮股份 6363 -2.72 -12.66",
            source_platform="新闻",
            publish_time="2026-06-10",
            extra={"source_type": "news", "source_credit": 60, "verification_status": "professional_observation"},
        ),
    ]
    ctx = _make_ctx(items=items)
    renderer = SourceIntakeEvidenceRenderer()
    result = renderer.render(ctx)

    data_rows = [line for line in result.splitlines() if line.startswith("| 202")]
    assert len(data_rows) == 3
    assert "股东户数连续下降" not in result
    assert "主力资金出逃股" not in result
    assert "筹码连续3期集中" not in result
    assert "创业板股最新股东户数降" not in result
