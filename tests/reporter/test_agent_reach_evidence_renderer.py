import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from reporter.sections.agent_reach_evidence_renderer import (
    AgentReachEvidenceRenderer,
    classify_agent_reach_topic,
)
from source_adapter import SynthesisItem
from skill_pipeline import SkillContext


def _make_item(**kwargs) -> SynthesisItem:
    defaults = {
        "title": "",
        "content": "",
        "author": "",
        "source_platform": "AgentReach(twitter)",
        "url": "",
        "publish_time": "",
        "interaction_score": 0,
        "extra": {},
    }
    defaults.update(kwargs)
    return SynthesisItem(**defaults)


def _make_ctx(
    enabled=True,
    quality_status="ok",
    keep_items=None,
    demote_items=None,
    discard_items=None,
    quality_results=None,
    fetch_status="ok",
    warnings=None,
    core_facts=None,
) -> SkillContext:
    return SkillContext(input={
        "agent_reach_enabled": enabled,
        "agent_reach_status": fetch_status,
        "agent_reach_quality_status": quality_status,
        "agent_reach_keep_items": keep_items or [],
        "agent_reach_demote_items": demote_items or [],
        "agent_reach_discard_items": discard_items or [],
        "agent_reach_quality_results": quality_results or [],
        "agent_reach_warnings": warnings or [],
        "core_facts": core_facts or [],
        "agent_reach_quality_summary": {
            "keep": len(keep_items or []),
            "demote": len(demote_items or []),
            "discard": len(discard_items or []),
            "total": sum([
                len(keep_items or []),
                len(demote_items or []),
                len(discard_items or []),
            ]),
            "fetch_status": fetch_status,
            "quality_status": quality_status,
        },
    })


# --- Classification tests ---

def test_classify_product_progress_for_liangchan():
    item = _make_item(title="芯片量产进展", content="良率达到95%")
    assert classify_agent_reach_topic(item) == "product_progress"


def test_classify_customer_orders_for_dingdian():
    item = _make_item(title="黑芝麻智能获得新客户定点", content="与比亚迪达成合作")
    assert classify_agent_reach_topic(item) == "customer_orders"


def test_classify_competition_for_rivals():
    item = _make_item(title="黑芝麻智能 vs 地平线", content="竞争对手分析")
    assert classify_agent_reach_topic(item) == "competition"


def test_classify_earnings_for_caibao():
    item = _make_item(title="Q1财报公布", content="营收同比增长，毛利率提升")
    assert classify_agent_reach_topic(item) == "earnings_business"


def test_classify_market_sentiment_for_yuqing():
    item = _make_item(title="市场关注度提升", content="投资者热议")
    assert classify_agent_reach_topic(item) == "market_sentiment"


def test_classify_to_verify_fallback():
    item = _make_item(title="random title", content="nothing matches")
    assert classify_agent_reach_topic(item) == "to_verify"


def test_classify_priority_product_over_earnings():
    item = _make_item(title="量产营收双增长", content="量产交付同时营收增长")
    assert classify_agent_reach_topic(item) == "product_progress"


def test_classify_uses_quality_reasons():
    item = _make_item(title="some update", content="general news")
    quality_result = {"reasons": ["包含量产相关关键词", "有URL"]}
    assert classify_agent_reach_topic(item, quality_result) == "product_progress"


# --- Rendering tests ---

def test_disabled_returns_empty():
    renderer = AgentReachEvidenceRenderer()
    ctx = _make_ctx(enabled=False)
    assert renderer.render(ctx) == ""


def test_skipped_returns_empty():
    renderer = AgentReachEvidenceRenderer()
    ctx = _make_ctx(quality_status="skipped")
    assert renderer.render(ctx) == ""


def test_error_returns_empty():
    renderer = AgentReachEvidenceRenderer()
    ctx = _make_ctx(quality_status="error")
    assert renderer.render(ctx) == ""


def test_empty_renders_note():
    renderer = AgentReachEvidenceRenderer()
    ctx = _make_ctx(quality_status="empty")
    result = renderer.render(ctx)
    assert "Agent-Reach 外部证据观察" in result
    assert "未检索到可用外部证据" in result


def test_render_contains_overview():
    item = _make_item(
        title="黑芝麻智能量产",
        content="芯片量产良率95%",
        url="https://t.co/a",
        publish_time="2026-06-10",
        interaction_score=50,
    )
    quality_result = {
        "title": "黑芝麻智能量产",
        "source": "AgentReach(twitter)",
        "action": "keep",
        "score": 72,
        "reasons": ["包含股票名称", "有URL"],
        "url": "https://t.co/a",
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result])
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)
    assert "本期外部证据概览" in result
    assert "高优先级证据：1 条" in result
    assert "低优先级观察：0 条" in result


def test_render_contains_themed_evidence_section():
    item = _make_item(
        title="黑芝麻智能量产",
        content="芯片量产良率95%",
        url="https://t.co/a",
        publish_time="2026-06-10",
    )
    quality_result = {
        "title": "黑芝麻智能量产",
        "source": "AgentReach(twitter)",
        "action": "keep",
        "score": 72,
        "reasons": [],
        "url": "https://t.co/a",
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result])
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)
    assert "主题化证据观察" in result
    assert "产品/量产进展" in result
    assert "黑芝麻智能量产" in result


def test_keep_fallback_under_to_verify():
    item = _make_item(title="random update", content="no matching keywords at all")
    quality_result = {
        "title": "random update",
        "source": "AgentReach(twitter)",
        "action": "keep",
        "score": 60,
        "reasons": [],
        "url": "",
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result])
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)
    assert "待核查线索" in result
    assert "random update" in result


def test_demote_under_manual_review_not_in_keep_topics():
    item = _make_item(
        title="黑芝麻智能 新闻",
        content="看到消息",
        url="https://t.co/b",
        publish_time="2026-06-09",
        interaction_score=5,
    )
    quality_result = {
        "title": "黑芝麻智能 新闻",
        "source": "AgentReach(twitter)",
        "action": "demote",
        "score": 42,
        "reasons": ["包含股票名称"],
        "url": "https://t.co/b",
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(demote_items=[item], quality_results=[quality_result])
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)
    assert "待人工复核线索" in result
    assert "黑芝麻智能 新闻" in result
    assert "产品/量产进展" not in result
    assert "客户/定点/订单" not in result


def test_overview_excludes_demote_only_topics():
    item = _make_item(title="random weak item", content="no keywords")
    quality_result = {
        "title": "random weak item",
        "source": "AgentReach(twitter)",
        "action": "demote",
        "score": 40,
        "reasons": [],
        "url": "",
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(demote_items=[item], quality_results=[quality_result])
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)
    # Overview should not list any topic for demote-only items
    assert "主要主题" not in result or "待核查" not in result.split("主要主题")[1].split("\n")[0]


def test_overview_topics_follow_fixed_topic_order():
    customer_item = _make_item(title="新客户定点", content="客户订单落地", url="http://c")
    product_item = _make_item(title="芯片量产", content="产品量产推进", url="http://p")
    quality_results = [
        {
            "title": customer_item.title,
            "source": customer_item.source_platform,
            "action": "keep",
            "score": 70,
            "reasons": [],
            "url": customer_item.url,
            "fetch_status": "ok",
            "quality_status": "ok",
        },
        {
            "title": product_item.title,
            "source": product_item.source_platform,
            "action": "keep",
            "score": 72,
            "reasons": [],
            "url": product_item.url,
            "fetch_status": "ok",
            "quality_status": "ok",
        },
    ]
    ctx = _make_ctx(
        keep_items=[customer_item, product_item],
        quality_results=quality_results,
    )
    result = AgentReachEvidenceRenderer().render(ctx)
    topic_line = [line for line in result.splitlines() if line.startswith("- 主要主题：")][0]
    assert topic_line.index("产品/量产进展") < topic_line.index("客户/定点/订单")


def test_old_raw_headings_not_present():
    item = _make_item(title="量产进展", content="芯片量产")
    quality_result = {
        "title": "量产进展",
        "source": "AgentReach(twitter)",
        "action": "keep",
        "score": 70,
        "reasons": [],
        "url": "",
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result])
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)
    assert "### 高优先级证据" not in result
    assert "### 低优先级观察" not in result


def test_discard_items_do_not_render():
    item = _make_item(title="冲啊必涨", content="绝对涨停", url="https://t.co/c")
    quality_result = {
        "title": "冲啊必涨",
        "source": "AgentReach(twitter)",
        "action": "discard",
        "score": 15,
        "reasons": ["炒作信号"],
        "url": "https://t.co/c",
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(
        keep_items=[], demote_items=[], discard_items=[item], quality_results=[quality_result]
    )
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)
    assert "冲啊必涨" not in result
    assert "15" not in result


def test_quality_score_from_matching_result():
    item = _make_item(title="t1", content="量产芯片", url="http://a")
    quality_result = {
        "title": "t1",
        "source": "AgentReach(twitter)",
        "action": "keep",
        "score": 88,
        "reasons": ["高质量"],
        "url": "http://a",
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result])
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)
    assert "88" in result
    assert "高质量" in result


def test_out_of_sync_quality_results_show_placeholder():
    item = _make_item(title="t1", content="c1", url="http://a")
    ctx = _make_ctx(keep_items=[item], quality_results=[])
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)
    assert "t1" in result
    assert "—" in result
    assert "未评分" in result


def test_markdown_pipe_escaped():
    item = _make_item(title="a|b|c", content="x|y量产", url="http://a")
    quality_result = {
        "title": "a|b|c",
        "source": "AgentReach(twitter)",
        "action": "keep",
        "score": 70,
        "reasons": ["r1|r2"],
        "url": "http://a",
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result])
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)
    assert "a\\|b\\|c" in result
    assert "r1\\|r2" in result


def test_empty_publish_time_renders_dash():
    item = _make_item(title="t1", content="量产c1", url="http://a", publish_time="")
    quality_result = {
        "title": "t1",
        "source": "AgentReach(twitter)",
        "action": "keep",
        "score": 70,
        "reasons": [],
        "url": "http://a",
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result])
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)
    lines = [ln for ln in result.splitlines() if "t1" in ln and "|" in ln]
    assert lines
    assert "—" in lines[0]


def test_keep_and_demote_caps():
    keep = [_make_item(title=f"量产k{i}", content="c", url=f"http://k{i}") for i in range(8)]
    demote = [_make_item(title=f"d{i}", content="c", url=f"http://d{i}") for i in range(6)]
    quality_results = []
    for i, item in enumerate(keep):
        quality_results.append({
            "title": item.title,
            "source": item.source_platform,
            "action": "keep",
            "score": 70,
            "reasons": [],
            "url": item.url,
            "fetch_status": "ok",
            "quality_status": "ok",
        })
    for i, item in enumerate(demote):
        quality_results.append({
            "title": item.title,
            "source": item.source_platform,
            "action": "demote",
            "score": 40,
            "reasons": [],
            "url": item.url,
            "fetch_status": "ok",
            "quality_status": "ok",
        })
    ctx = _make_ctx(keep_items=keep, demote_items=demote, quality_results=quality_results)
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)
    for i in range(6, 8):
        assert f"量产k{i}" not in result
    for i in range(4, 6):
        assert f"d{i}" not in result
    for i in range(6):
        assert f"量产k{i}" in result
    for i in range(4):
        assert f"d{i}" in result


def test_long_excerpt_is_truncated():
    long_content = "量产" + "长" * 130
    item = _make_item(title="量产长文", content=long_content, url="http://long")
    quality_result = {
        "title": item.title,
        "source": item.source_platform,
        "action": "keep",
        "score": 70,
        "reasons": [],
        "url": item.url,
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result])
    result = AgentReachEvidenceRenderer().render(ctx)
    assert "..." in result
    assert "长" * 130 not in result


def test_jina_metadata_cleaned_in_table_row():
    title_text = "黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证"
    jina_content = (
        f"Title: {title_text}\n"
        "URL Source: https://www.blacksesame.com/zh/list_10/972.html\n"
        "Markdown Content:\n"
        f"# {title_text}\n"
        "黑芝麻智能宣布华山A2000U、A2000X芯片获得ISO 26262 ASIL-D最高功能安全认证。"
    )
    item = _make_item(
        title=f"Title: {title_text}",
        content=jina_content,
        source_platform="AgentReach(web)",
        url="https://www.blacksesame.com/zh/list_10/972.html",
    )
    quality_result = {
        "title": item.title,
        "source": item.source_platform,
        "action": "keep",
        "score": 51,
        "reasons": ["包含股票名称", "有URL"],
        "url": item.url,
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result])
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)

    rows = [ln for ln in result.splitlines() if ln.startswith("| — |")]
    assert rows, "expected an Agent-Reach table row"
    row = rows[0]

    assert "Title:" not in row
    assert "URL Source:" not in row
    assert "Markdown Content:" not in row
    assert "\n" not in row
    assert "黑芝麻智能宣布华山" in row
    assert "A2000U" in row


def test_title_not_duplicated_when_h1_matches_title():
    title = "黑芝麻智能量产进展"
    content = f"Title: {title}\nMarkdown Content:\n# {title}\n芯片良率达到95%。"
    item = _make_item(title=title, content=content, url="http://a")
    quality_result = {
        "title": item.title,
        "source": item.source_platform,
        "action": "keep",
        "score": 70,
        "reasons": [],
        "url": item.url,
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result])
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)

    rows = [ln for ln in result.splitlines() if ln.startswith("| — |")]
    assert rows
    row = rows[0]
    # Title should appear only once, not as "title — title"
    assert row.count(title) == 1
    assert "芯片良率达到95%" in row


def test_black_sesame_list9_nav_noise_removed():
    """Black Sesame /zh/list_9/ cooperation pages: nav boilerplate and duplicate H1 removed."""
    title = "黑芝麻智能与上实科技达成战略合作，共建具身智能生态，共筑香港机器人创新平台-黑芝麻智能科技有限公司"
    jina_content = (
        f"Title: {title}\n"
        "URL Source: https://www.blacksesame.com/zh/list_9/977.html\n"
        "Markdown Content:\n"
        f"# {title}\n"
        "[联系我们](javascript:;)\n"
        "[商务合作](mailto:mkt@bst.ai)[加入我们](mailto:recruiting@bst.ai)[媒体资讯](mailto:pr@bst.ai)\n"
        "[选择语言](javascript:;)\n"
        "[中文](https://www.blacksesame.com/zh/list_9/977.html#)[English](https://www.blacksesame.com/en/news-center)\n"
        "[![Image 2: 黑芝麻](https://www.blacksesame.com/template/default/images/500X160.png)](https://www.blacksesame.com/zh)\n"
        "[首页](https://www.blacksesame.com/zh)\n"
        "[公司信息](https://www.blacksesame.com/zh/company-profile/)\n"
        "2026年6月8日，黑芝麻智能与上海上实科技创业投资有限公司正式签署战略合作协议。双方将深度融合技术研发、资本布局、产业生态及跨境资源优势。\n"
        "此次合作，双方将充分发挥各自在产业资源、技术平台及资本运作等方面的优势，实现双向赋能与生态协同。\n"
        "[上一篇：黑芝麻智能加入理想星环OS开源生态](https://www.blacksesame.com/zh/list_9/966.html)\n"
    )
    item = _make_item(
        title=f"Title: {title}",
        content=jina_content,
        source_platform="AgentReach(web)",
        url="https://www.blacksesame.com/zh/list_9/977.html",
    )
    quality_result = {
        "title": item.title,
        "source": item.source_platform,
        "action": "keep",
        "score": 55,
        "reasons": ["包含股票名称", "有URL"],
        "url": item.url,
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result])
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)

    rows = [ln for ln in result.splitlines() if ln.startswith("| — |")]
    assert rows, "expected an Agent-Reach table row"
    row = rows[0]

    # No Jina metadata prefixes.
    assert "Title:" not in row
    assert "URL Source:" not in row
    assert "Markdown Content:" not in row
    # No nav boilerplate tokens.
    assert "联系我们" not in row
    assert "商务合作" not in row
    assert "加入我们" not in row
    assert "媒体资讯" not in row
    assert "选择语言" not in row
    assert "中文English" not in row
    assert "首页" not in row
    assert "公司信息" not in row
    # No duplicate H1 marker.
    assert "# 黑芝麻智能" not in row
    # No raw newlines inside the table row.
    assert "\n" not in row
    # Key article content preserved.
    assert "上实科技" in row
    assert "战略合作协议" in row
    assert "具身智能" in row


def test_black_sesame_list9_body_keeps_key_info():
    """Renderer should preserve chip model / partner / theme keywords from list_9 body."""
    title = "黑芝麻智能与东风汽车达成平台级合作，武当C1296芯片赋能东风天元智舱Plus-黑芝麻智能科技有限公司"
    jina_content = (
        f"Title: {title}\n"
        "URL Source: https://www.blacksesame.com/zh/list_9/964.html\n"
        "Markdown Content:\n"
        f"# {title}\n"
        "[首页](https://www.blacksesame.com/zh)\n"
        "[公司信息](https://www.blacksesame.com/zh/company-profile/)\n"
        "4月24日，黑芝麻智能在2026北京车展现场举办“芯连万物 智赋全域”发布会，宣布黑芝麻智能与东风汽车达成平台级深度合作，共同打造首个本土舱驾一体量产化平台——天元智舱Plus。\n"
        "**天元智舱Plus** 作为天元智舱系列主力平台，搭载黑芝麻智能 武当C1296芯片，以单芯片同时支持智能座舱、L2+行车辅助及FAPA泊车功能。\n"
        "[上一篇：黑芝麻智能加入理想星环OS开源生态](https://www.blacksesame.com/zh/list_9/966.html)\n"
    )
    item = _make_item(
        title=f"Title: {title}",
        content=jina_content,
        source_platform="AgentReach(web)",
        url="https://www.blacksesame.com/zh/list_9/964.html",
    )
    quality_result = {
        "title": item.title,
        "source": item.source_platform,
        "action": "keep",
        "score": 55,
        "reasons": ["包含股票名称", "有URL"],
        "url": item.url,
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result])
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)

    row = [ln for ln in result.splitlines() if ln.startswith("| — |")][0]
    assert "东风汽车" in row
    assert "武当C1296" in row
    assert "天元智舱Plus" in row
    assert "[首页" not in row
    assert "# 黑芝麻智能" not in row

    content = "Title: a|b\nURL Source: http://x\nMarkdown Content:\nbody x|y量产"
    item = _make_item(title="a|b", content=content, url="http://x")
    quality_result = {
        "title": item.title,
        "source": item.source_platform,
        "action": "keep",
        "score": 60,
        "reasons": ["r1|r2"],
        "url": item.url,
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result])
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)

    assert "a\\|b" in result
    assert "x\\|y量产" in result
    assert "r1\\|r2" in result


def test_cninfo_pdf_evidence_summary_uses_human_title_and_strips_pdf_metadata():
    title = "Title: 1225106812.PDF"
    content = (
        "Title: 1225106812.PDF\n"
        "Published Time: Wed, 15 Apr 2026 10:22:39 GMT\n"
        "Number of Pages: 2\n"
        "证券代码： 300777 证券简称：中简科技 公告编号： 2026 -017\n"
        "中简科技股份有限公司 2026 年第一季度业绩预告\n"
        "客户对公司部分产品的需求量阶段性减少导致发货暂时减少，其中收入下降约50%-60%。"
    )
    item = _make_item(
        title=title,
        content=content,
        source_platform="AgentReach(web)",
        url="http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225106812",
    )
    quality_result = {
        "title": item.title,
        "source": item.source_platform,
        "action": "keep",
        "score": 77,
        "reasons": ["官方/认证来源"],
        "url": item.url,
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result])

    result = AgentReachEvidenceRenderer().render(ctx)
    row = [ln for ln in result.splitlines() if ln.startswith("| — |")][0]

    assert "2026年第一季度业绩预告" in row
    assert "收入下降约50%-60%" in row
    assert "1225106812.PDF" not in row
    assert "Published Time" not in row
    assert "Number of Pages" not in row
    assert "证券代码" not in row
    assert "证券简称" not in row


def test_cninfo_pdf_fact_gap_uses_clean_summary():
    item = _make_item(
        title="Title: 1225145344.PDF",
        content=(
            "Title: 1225145344.PDF\n"
            "Published Time: Wed, 22 Apr 2026 09:11:39 GMT\n"
            "Number of Pages: 10\n"
            "中简科技股份有限公司 2026 年第一季度报告\n"
            "营业收入（元） 108,547,445.05 239,073,276.33 -54.60%"
        ),
        source_platform="AgentReach(web)",
        url="http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225145344",
    )
    quality_result = {
        "title": item.title,
        "source": item.source_platform,
        "action": "keep",
        "score": 77,
        "reasons": [],
        "url": item.url,
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result], core_facts=[])

    result = AgentReachEvidenceRenderer().render(ctx)
    gap_section = result.split("### 核心事实缺口观察")[1].split("### 主题化证据观察")[0]

    assert "2026年第一季度报告" in gap_section
    assert "营业收入" in gap_section
    assert "1225145344.PDF" not in gap_section
    assert "Published Time" not in gap_section
    assert "Number of Pages" not in gap_section


def test_cninfo_pdf_summary_removes_disclosure_boilerplate_and_preserves_fact():
    item = _make_item(
        title="Title: 1225145344.PDF",
        content=(
            "Title: 1225145344.PDF\n"
            "Published Time: Wed, 22 Apr 2026 09:11:39 GMT\n"
            "Number of Pages: 10\n"
            "中简科技股份有限公司 2026 年第一季度报告 1\n"
            "# 中简科技股份有限公司\n"
            "# 2026 年第一季度报告\n"
            "本公司及董事会全体成员保证信息披露的内容真实、准确、完整，没有虚假记载、误导性陈述或重大遗漏。\n"
            "# 重要内容提示： 1. 董事会及监事会已审议通过。\n"
            "营业收入（元） 108,547,445.05 239,073,276.33 -54.60%"
        ),
        source_platform="AgentReach(web)",
        url="http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225145344",
    )
    quality_result = {
        "title": item.title,
        "source": item.source_platform,
        "action": "keep",
        "score": 77,
        "reasons": [],
        "url": item.url,
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result])

    result = AgentReachEvidenceRenderer().render(ctx)
    row = [ln for ln in result.splitlines() if ln.startswith("| — |")][0]

    assert "营业收入（元）" in row
    assert "-54.60%" in row
    assert "本公司及董事会" not in row
    assert "虚假记载" not in row
    assert "重要内容提示" not in row
    assert "# 2026" not in row


def test_renderer_supports_six_black_sesame_keep_items():
    """Renderer table should display up to six keep items (Black Sesame URL cap)."""
    urls = [
        "https://www.blacksesame.com/zh/list_10/972.html",
        "https://www.blacksesame.com/zh/list_9/977.html",
        "https://www.blacksesame.com/zh/list_9/966.html",
        "https://www.blacksesame.com/zh/list_9/964.html",
        "https://www.blacksesame.com/zh/list_9/961.html",
        "https://www.blacksesame.com/zh/list_10/912.html",
    ]
    keep_items = []
    quality_results = []
    for i, url in enumerate(urls):
        title = f"黑芝麻智能官网动态 {i+1}-黑芝麻智能科技有限公司"
        content = f"Title: {title}\nURL Source: {url}\nMarkdown Content:\n# {title}\n[首页](https://www.blacksesame.com/zh)\n[联系我们](javascript:;)\n正文内容保留芯片与合作伙伴信息。"
        item = _make_item(title=f"Title: {title}", content=content, source_platform="AgentReach(web)", url=url)
        keep_items.append(item)
        quality_results.append({
            "title": item.title,
            "source": item.source_platform,
            "action": "keep",
            "score": 55,
            "reasons": ["包含股票名称", "有URL"],
            "url": item.url,
            "fetch_status": "ok",
            "quality_status": "ok",
        })
    ctx = _make_ctx(keep_items=keep_items, quality_results=quality_results)
    result = AgentReachEvidenceRenderer().render(ctx)

    for url in urls:
        assert url in result
    # Count only rows under the themed evidence section (exclude fact-gap rows).
    themed_section = result.split("### 主题化证据观察")[1].split("### 待人工复核线索")[0] if "### 待人工复核线索" in result else result.split("### 主题化证据观察")[1]
    assert themed_section.count("| — |") == 6
    assert "联系我们" not in result
    assert "首页" not in result
    assert "# 黑芝麻智能" not in result


# --- Fact gap audit tests ---

def test_fact_gap_subsection_renders_for_uncovered_topic():
    """When core_facts does not cover a keep item's topic, render a gap observation."""
    item = _make_item(title="黑芝麻智能量产进展", content="芯片量产良率达到95%", url="http://a")
    quality_result = {
        "title": item.title,
        "source": item.source_platform,
        "action": "keep",
        "score": 70,
        "reasons": [],
        "url": item.url,
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result], core_facts=[])
    result = AgentReachEvidenceRenderer().render(ctx)

    assert "### 核心事实缺口观察" in result
    assert "产品/量产进展" in result
    assert "核心事实基座未覆盖该主题" in result
    assert "人工复核是否需要补充事实基座" in result


def test_fact_gap_subsection_absent_when_topic_covered():
    """When core_facts already covers the topic, no gap observation is rendered."""
    item = _make_item(title="黑芝麻智能量产进展", content="芯片量产良率达到95%", url="http://a")
    quality_result = {
        "title": item.title,
        "source": item.source_platform,
        "action": "keep",
        "score": 70,
        "reasons": [],
        "url": item.url,
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    core_facts = [
        {"fact_id": 1, "fact": "量产进展顺利", "data": "芯片良率达到95%", "confidence": "高"},
    ]
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result], core_facts=core_facts)
    result = AgentReachEvidenceRenderer().render(ctx)

    assert "### 核心事实缺口观察" not in result
    assert "核心事实基座未覆盖该主题" not in result


def test_demote_items_do_not_create_fact_gaps():
    """Demoted items must not contribute to fact gap observations."""
    item = _make_item(title="黑芝麻智能量产进展", content="芯片量产良率达到95%", url="http://a")
    quality_result = {
        "title": item.title,
        "source": item.source_platform,
        "action": "demote",
        "score": 45,
        "reasons": [],
        "url": item.url,
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(demote_items=[item], quality_results=[quality_result], core_facts=[])
    result = AgentReachEvidenceRenderer().render(ctx)

    assert "### 核心事实缺口观察" not in result
    assert "核心事实基座未覆盖该主题" not in result


def test_fact_gap_disclaimer_present():
    """Gap subsection must include the read-only, non-impact disclaimer."""
    item = _make_item(title="黑芝麻智能量产进展", content="芯片量产良率达到95%", url="http://a")
    quality_result = {
        "title": item.title,
        "source": item.source_platform,
        "action": "keep",
        "score": 70,
        "reasons": [],
        "url": item.url,
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result], core_facts=[])
    result = AgentReachEvidenceRenderer().render(ctx)

    assert "以下仅提示外部证据与核心事实基座之间的覆盖差异" in result
    assert "不构成事实确认" in result
    assert "也不影响评分或结论" in result


def test_fact_gap_has_no_numbered_citations():
    """Gap subsection must not emit numbered citation markers like [^1]."""
    item = _make_item(title="黑芝麻智能量产进展", content="芯片量产良率达到95%", url="http://a")
    quality_result = {
        "title": item.title,
        "source": item.source_platform,
        "action": "keep",
        "score": 70,
        "reasons": [],
        "url": item.url,
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = _make_ctx(keep_items=[item], quality_results=[quality_result], core_facts=[])
    result = AgentReachEvidenceRenderer().render(ctx)

    gap_section = result.split("### 核心事实缺口观察")[1].split("### 主题化证据观察")[0]
    assert "[^" not in gap_section


def test_fact_gap_rows_capped_at_four():
    """At most four gap observations are rendered."""
    topic_specs = [
        ("黑芝麻智能芯片量产", "量产良率95%", "product_progress"),
        ("黑芝麻智能获客户定点", "主机厂订单落地", "customer_orders"),
        ("黑芝麻智能竞争格局", "对手英伟达压制", "competition"),
        ("黑芝麻智能财报营收", "收入增长亏损收窄", "earnings_business"),
        ("黑芝麻智能市场热度", "投资者关注提升", "market_sentiment"),
        ("黑芝麻智能产品发布", "新版本芯片发布", "product_progress"),
    ]
    items = []
    quality_results = []
    for i, (title, content, expected_topic) in enumerate(topic_specs):
        item = _make_item(title=title, content=content, url=f"http://a{i}")
        items.append(item)
        quality_results.append({
            "title": item.title,
            "source": item.source_platform,
            "action": "keep",
            "score": 70,
            "reasons": [],
            "url": item.url,
            "fetch_status": "ok",
            "quality_status": "ok",
        })
    ctx = _make_ctx(keep_items=items, quality_results=quality_results, core_facts=[])
    result = AgentReachEvidenceRenderer().render(ctx)

    gap_section = result.split("### 核心事实缺口观察")[1].split("### 主题化证据观察")[0]
    gap_rows = [ln for ln in gap_section.splitlines() if ln.startswith("|") and "核心事实基座未覆盖该主题" in ln]
    assert len(gap_rows) == 4
    # product_progress appears only once despite two items
    product_rows = [ln for ln in gap_rows if "产品/量产进展" in ln]
    assert len(product_rows) == 1
