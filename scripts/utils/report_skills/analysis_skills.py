"""Cross-source consolidation and scoring skills."""

from pathlib import Path

if __name__.startswith("utils."):
    from ..skill_pipeline import skill, SkillContext
else:
    from skill_pipeline import skill, SkillContext


@skill(name="cross_source_consolidation")
def cross_source_consolidation_skill(ctx: SkillContext) -> SkillContext:
    """雪球 + 知乎 跨来源内容去重。"""
    keep_posts = ctx.get("keep_posts", [])
    stock_raw = ctx.get("stock_raw", {})
    zhihu_items = stock_raw.get("zhihu", {}).get("report_items", [])

    try:
        from content_consolidator import ContentConsolidator
    except ImportError:
        import sys
        utils_dir = Path(__file__).parent.parent
        if str(utils_dir) not in sys.path:
            sys.path.insert(0, str(utils_dir))
        from content_consolidator import ContentConsolidator

    consolidator = ContentConsolidator(
        use_llm_topics=bool(ctx.get("report_llm_enabled", True)),
    )
    consolidated = consolidator.consolidate(keep_posts + zhihu_items)
    summary = consolidator.generate_cross_source_summary(consolidated) or ""

    ctx.set("consolidated", consolidated)
    ctx.set("cross_source_summary", summary)
    return ctx


@skill(name="scoring")
def scoring_skill(ctx: SkillContext) -> SkillContext:
    """五维评分 + 雷达图数据。"""
    stock_raw = ctx.get("stock_raw", {})
    keep_posts = ctx.get("keep_posts", [])
    quote = ctx.get("quote")
    consensus = ctx.get("consensus")
    ind_fwd_pe = ctx.get("ind_fwd_pe")
    ps = ctx.get("ps")

    try:
        from reporter.scoring_engine import compute_pillar_scores
    except ImportError:
        import sys
        utils_dir = Path(__file__).parent.parent
        if str(utils_dir) not in sys.path:
            sys.path.insert(0, str(utils_dir))
        from reporter.scoring_engine import compute_pillar_scores

    pillar = compute_pillar_scores(stock_raw, keep_posts, quote, consensus, ind_fwd_pe, ps)
    if pillar is not None:
        total_score = round(
            pillar["valuation"] * 0.30 +
            pillar["technical"] * 0.25 +
            pillar["sentiment"] * 0.20 +
            pillar["fundamental"] * 0.15 +
            pillar["fundflow"] * 0.10,
            1,
        )
    else:
        total_score = None
    ctx.set("pillar_scores", pillar)
    ctx.set("pillar", pillar)
    ctx.set("total_score", total_score)
    return ctx
