"""Data loading and quality gate skills."""

import sys
from pathlib import Path

if __name__.startswith("utils."):
    from ..skill_pipeline import skill, SkillContext
else:
    from skill_pipeline import skill, SkillContext

# Module-level imports so tests can patch them via unittest.mock
try:
    from content_quality_gate import ContentQualityGate
except ImportError:
    utils_dir = Path(__file__).parent.parent
    if str(utils_dir) not in sys.path:
        sys.path.insert(0, str(utils_dir))
    from content_quality_gate import ContentQualityGate

try:
    from reporter.data_fetcher import (
        fetch_tencent_quote,
        fetch_consensus_eps,
        industry_fwd_pe,
        fetch_ps,
        fetch_competitor_metrics,
    )
except ImportError:
    utils_dir = Path(__file__).parent.parent
    if str(utils_dir) not in sys.path:
        sys.path.insert(0, str(utils_dir))
    from reporter.data_fetcher import (
        fetch_tencent_quote,
        fetch_consensus_eps,
        industry_fwd_pe,
        fetch_ps,
        fetch_competitor_metrics,
    )


@skill(name="data_loading")
def data_loading_skill(ctx: SkillContext) -> SkillContext:
    """从 stocks_data / raw_data 加载单只股票的数据。"""
    stock_name = ctx.get("stock_name")
    stocks_data = ctx.get("stocks_data", {})
    raw_data = ctx.get("raw_data", {})

    all_posts = stocks_data.get(stock_name, [])
    stock_raw = raw_data.get(stock_name, {})

    ctx.set("all_posts", all_posts)
    ctx.set("stock_raw", stock_raw)
    return ctx


@skill(name="quality_gate")
def quality_gate_skill(ctx: SkillContext) -> SkillContext:
    """统一质量门筛选。"""
    all_posts = ctx.get("all_posts", [])

    gate = ContentQualityGate()
    results = gate.process_xueqiu_posts(all_posts)

    keep = [r.item.extra for r in results if r.action == "keep"]
    demote = [r.item.extra for r in results if r.action == "demote"]
    discard = [r.item.extra for r in results if r.action == "discard"]

    ctx.set("keep_posts", keep)
    ctx.set("demote_posts", demote)
    ctx.set("discard_posts", discard)
    return ctx


@skill(name="quote_fetching")
def quote_fetching_skill(ctx: SkillContext) -> SkillContext:
    """获取实时行情、一致预期、行业PE。"""
    stock_name = ctx.get("stock_name")
    code = ctx.get("stock_codes", {}).get(stock_name, "")

    quote = None
    consensus = None
    ind_fwd_pe = None
    ps = None

    if code:
        quote = fetch_tencent_quote(code)
        consensus = fetch_consensus_eps(code)
        ind_fwd_pe = industry_fwd_pe(stock_name)

        # 亏损股：计算 PS 替代 PE
        if quote and quote.get("pe_ttm", 0) <= 0:
            ps = fetch_ps(code, quote)
            if ps:
                quote["ps"] = ps

    ctx.set("quote", quote)
    ctx.set("consensus", consensus)
    ctx.set("ind_fwd_pe", ind_fwd_pe)
    ctx.set("ps", ps)
    return ctx


@skill(name="competitor_fetching")
def competitor_fetching_skill(ctx: SkillContext) -> SkillContext:
    """获取同业竞争对手估值指标。"""
    stock_name = ctx.get("stock_name")
    stock_codes = ctx.get("stock_codes", {})

    competitor_metrics = None
    if stock_name and stock_codes:
        competitor_metrics = fetch_competitor_metrics(stock_name, stock_codes)

    ctx.set("competitor_metrics", competitor_metrics)
    return ctx
