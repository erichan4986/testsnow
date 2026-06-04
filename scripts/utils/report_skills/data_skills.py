"""Data loading and quality gate skills."""

from pathlib import Path
from skill_pipeline import skill, SkillContext


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

    try:
        from content_quality_gate import ContentQualityGate
    except ImportError:
        import sys
        utils_dir = Path(__file__).parent.parent
        if str(utils_dir) not in sys.path:
            sys.path.insert(0, str(utils_dir))
        from content_quality_gate import ContentQualityGate

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

    try:
        from reporter.data_fetcher import (
            fetch_tencent_quote,
            fetch_consensus_eps,
            industry_fwd_pe,
            fetch_ps,
        )
    except ImportError:
        import sys
        utils_dir = Path(__file__).parent.parent
        if str(utils_dir) not in sys.path:
            sys.path.insert(0, str(utils_dir))
        try:
            from reporter.data_fetcher import (
                fetch_tencent_quote,
                fetch_consensus_eps,
                industry_fwd_pe,
                fetch_ps,
            )
        except ImportError:
            fetch_tencent_quote = None
            fetch_consensus_eps = None
            industry_fwd_pe = None
            fetch_ps = None

    quote = None
    consensus = None
    ind_fwd_pe = None
    ps = None

    if fetch_tencent_quote is not None:
        quote = fetch_tencent_quote(code) if code else None
        consensus = fetch_consensus_eps(code) if code else None
        ind_fwd_pe = industry_fwd_pe(stock_name)

        # 亏损股：计算 PS 替代 PE
        if quote and quote.get("pe_ttm", 0) <= 0 and code:
            ps = fetch_ps(code, quote)
            if ps:
                quote["ps"] = ps

    ctx.set("quote", quote)
    ctx.set("consensus", consensus)
    ctx.set("ind_fwd_pe", ind_fwd_pe)
    ctx.set("ps", ps)
    return ctx
