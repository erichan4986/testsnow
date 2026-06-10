"""Technical data collection skill — wraps TechnicalCollector for pipeline use."""

import sys
from pathlib import Path

if __name__.startswith("utils."):
    from ..skill_pipeline import skill, SkillContext
else:
    from skill_pipeline import skill, SkillContext

# Module-level import so tests can patch
try:
    from data_collector import TechnicalCollector
except ImportError:
    utils_dir = Path(__file__).parent.parent
    if str(utils_dir) not in sys.path:
        sys.path.insert(0, str(utils_dir))
    from data_collector import TechnicalCollector


@skill(name="technical_fetching")
def technical_fetching_skill(ctx: SkillContext) -> SkillContext:
    """
    采集技术指标数据（日线+周线+价格目标）。
    支持 A 股（market=0/1）和港股（market=hk）。
    """
    stock_name = ctx.get("stock_name")
    stock_codes = ctx.get("stock_codes", {})
    code = stock_codes.get(stock_name, "")
    stock_raw = ctx.get("stock_raw", {})

    # 如果 raw_data 里已经有技术数据，直接复用
    if stock_raw and stock_raw.get("technical"):
        tech_data = stock_raw["technical"]
        ctx.set("technical", tech_data)
        ctx.set("price_target", tech_data.get("price_target"))
        indicators = tech_data.get("indicators", {})
        daily_data = {"close": indicators.get("close"), "volume": indicators.get("volume")}
        ctx.set("daily_data", daily_data)
        ctx.set("indicators", indicators)
        return ctx

    if not code:
        ctx.set("technical", None)
        ctx.set("price_target", None)
        return ctx

    # 判断市场
    is_hk = code.startswith("0") and len(code) == 5
    market = 0 if code.startswith(("00", "30")) else (1 if code.startswith(("60", "68")) else 0)

    tech_collector = TechnicalCollector()
    tech_data = tech_collector.collect(code, market=market, days=120)

    if tech_data:
        indicators = tech_data.get("indicators", {})
        # 为 chart generation 提取 daily_data
        daily_data = {}
        if "close" in indicators:
            daily_data["close"] = indicators.get("close")
        if "volume" in indicators:
            daily_data["volume"] = indicators.get("volume")

        ctx.set("technical", tech_data)
        ctx.set("daily_data", daily_data)
        ctx.set("indicators", indicators)
        ctx.set("price_target", tech_data.get("price_target"))
    else:
        ctx.set("technical", None)
        ctx.set("price_target", None)
        ctx.set("daily_data", {})
        ctx.set("indicators", {})

    return ctx
