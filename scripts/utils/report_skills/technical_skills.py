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

try:
    from wind_kline_loader import load_wind_package
except ImportError:
    utils_dir = Path(__file__).parent.parent
    if str(utils_dir) not in sys.path:
        sys.path.insert(0, str(utils_dir))
    from wind_kline_loader import load_wind_package


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

    def _df_to_daily_data(df) -> dict:
        result = {}
        for col in ("date", "open", "high", "low", "close", "volume", "amount"):
            if col not in df.columns:
                continue
            values = df[col]
            if col == "date":
                result[col] = [str(v.date()) if hasattr(v, "date") else str(v) for v in values]
            else:
                result[col] = [float(v) for v in values]
        return result

    def _extract_daily_data(tech_data: dict, indicators: dict) -> dict:
        daily_data = tech_data.get("daily_data") or {}
        if daily_data:
            return daily_data

        # Backward-compatible fallback for older cached technical payloads.
        fallback = {}
        for key in ("open", "high", "low", "close", "volume"):
            value = indicators.get(key)
            if isinstance(value, list):
                fallback[key] = value
        return fallback

    def _set_technical_outputs(tech_data: dict | None, unavailable_reason: str = "") -> None:
        if tech_data:
            indicators = tech_data.get("indicators", {})
            daily_data = _extract_daily_data(tech_data, indicators)
            stock_raw["technical"] = tech_data
            ctx.set("stock_raw", stock_raw)
            ctx.set("technical", tech_data)
            ctx.set("price_target", tech_data.get("price_target"))
            ctx.set("daily_data", daily_data)
            ctx.set("indicators", indicators)
            ctx.set("technical_unavailable_reason", "")
        else:
            if unavailable_reason:
                stock_raw["technical_unavailable_reason"] = unavailable_reason
                ctx.set("stock_raw", stock_raw)
            ctx.set("technical", None)
            ctx.set("price_target", None)
            ctx.set("daily_data", {})
            ctx.set("indicators", {})
            ctx.set("technical_unavailable_reason", unavailable_reason)

    # 如果 raw_data 里已经有技术数据，直接复用
    if stock_raw and stock_raw.get("technical"):
        _set_technical_outputs(stock_raw["technical"])
        return ctx

    if not code:
        _set_technical_outputs(None, "missing_stock_code")
        return ctx

    # 判断市场
    market = "hk" if code.startswith("0") and len(code) == 5 else (
        0 if code.startswith(("00", "30")) else (1 if code.startswith(("60", "68")) else 0)
    )

    # 优先尝试本地 Wind Excel 数据
    try:
        wind_pkg = load_wind_package(stock_name, days=120)
    except Exception:
        wind_pkg = {}

    if wind_pkg and wind_pkg.get("daily") is not None and len(wind_pkg["daily"]) > 0:
        df_daily = wind_pkg["daily"]
        tech_collector = TechnicalCollector()
        indicators = tech_collector.compute_indicators(df_daily, code=code)

        daily_data = _df_to_daily_data(df_daily)

        benchmark_data = {}
        for name, df_bench in wind_pkg.get("benchmarks", {}).items():
            if df_bench is not None and len(df_bench) > 0:
                benchmark_data[name] = _df_to_daily_data(df_bench)

        tech_data = {
            "indicators": indicators,
            "daily_data": daily_data,
            "benchmark_data": benchmark_data,
            "data_source": "wind_excel",
            "adjustment": "raw",
            "code": code,
            "market": market,
            "price_target": None,
        }
        _set_technical_outputs(tech_data)
        return ctx

    # 回退到网络采集
    tech_collector = TechnicalCollector()
    tech_data = tech_collector.collect(code, market=market, days=120)

    if tech_data:
        _set_technical_outputs(tech_data)
    else:
        _set_technical_outputs(None, "technical_data_unavailable")

    return ctx
