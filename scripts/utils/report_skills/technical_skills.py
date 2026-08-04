"""Technical data collection skill — wraps TechnicalCollector for pipeline use."""

import logging
import sys
from datetime import date, datetime
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

try:
    from reporter.technical_state_machine import ensure_technical_judgment
except ImportError:
    from utils.reporter.technical_state_machine import ensure_technical_judgment

try:
    from technical_ohlcv_cache import load_ohlcv_cache, write_ohlcv_cache
except ImportError:
    from utils.technical_ohlcv_cache import load_ohlcv_cache, write_ohlcv_cache


MAX_LOCAL_WIND_STALENESS_DAYS = 7
logger = logging.getLogger(__name__)


def _coerce_date(value):
    if value is None:
        return None
    if hasattr(value, "date"):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value[:10]).date()
        except ValueError:
            return None
    return None


def _wind_daily_stale_reason(df_daily, today: date | None = None) -> str:
    if df_daily is None or len(df_daily) == 0 or "date" not in df_daily:
        return "wind_excel_missing_latest_date"
    today = today or date.today()
    latest = _coerce_date(df_daily["date"].iloc[-1])
    if latest is None:
        return "wind_excel_missing_latest_date"
    age_days = (today - latest).days
    if age_days > MAX_LOCAL_WIND_STALENESS_DAYS:
        return f"wind_excel_stale:{latest.isoformat()}:{age_days}d"
    return ""


def _coerce_float(value, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_fund_flow_rows(rows) -> list[dict]:
    if not isinstance(rows, list):
        return []

    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        main_inflow = row.get("main_inflow")
        if main_inflow is None:
            main_inflow = row.get("main_in")
        if main_inflow is None:
            main_inflow = row.get("main_net")

        source = row.get("source")
        if not source:
            source = "eastmoney_push2his" if "main_net" in row else "baidu_pae"

        record = {
            "date": row.get("date", ""),
            "source": source,
            "main_inflow": _coerce_float(main_inflow),
            "main_outflow": _coerce_float(row.get("main_outflow")),
        }
        for key in (
            "main_in",
            "main_net",
            "super_net_in",
            "large_net_in",
            "medium_net_in",
            "small_net_in",
            "super_big_net",
            "big_net",
            "mid_net",
            "small_net",
            "main_pct",
            "change_pct",
            "close",
        ):
            if key in row:
                record[key] = _coerce_float(row.get(key))
        normalized.append(record)

    return normalized


def _bridge_technical_fund_flow(stock_raw: dict, tech_data: dict) -> None:
    if stock_raw.get("fundflow"):
        return
    fund_flow = _normalize_fund_flow_rows(tech_data.get("fund_flow"))
    if fund_flow:
        stock_raw["fundflow"] = fund_flow


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
            resonance = indicators.get("_resonance", {}) if isinstance(indicators, dict) else {}
            if isinstance(indicators, dict) and isinstance(resonance, dict):
                resonance["judgment"] = ensure_technical_judgment(
                    resonance.get("judgment"), resonance=resonance,
                    price_target=tech_data.get("price_target"),
                    indicators=indicators,
                    daily_data=tech_data.get("daily_data"),
                    market=tech_data.get("market"),
                )
                indicators["_resonance"] = resonance
            daily_data = _extract_daily_data(tech_data, indicators)
            stock_raw["technical"] = tech_data
            _bridge_technical_fund_flow(stock_raw, tech_data)
            ctx.set("stock_raw", stock_raw)
            ctx.set("fundflow", stock_raw.get("fundflow", []))
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
    cache_dir = ctx.get("technical_ohlcv_cache_dir")

    # 优先尝试本地 Wind Excel 数据
    try:
        wind_pkg = load_wind_package(stock_name, days=120)
    except Exception:
        wind_pkg = {}

    if wind_pkg and wind_pkg.get("daily") is not None and len(wind_pkg["daily"]) > 0:
        stale_reason = _wind_daily_stale_reason(wind_pkg["daily"])
        if stale_reason:
            ctx.set("technical_local_data_stale_reason", stale_reason)
        else:
            df_daily = wind_pkg["daily"]
            tech_collector = TechnicalCollector()
            technical_payload = tech_collector.build_technical_payload(
                df_daily, code=code, market=market, cache_dir=cache_dir,
            )
            if not isinstance(technical_payload, dict):
                indicators = tech_collector.compute_indicators(df_daily, code=code, market=market)
                technical_payload = {"indicators": indicators, "price_target": None}

            daily_data = _df_to_daily_data(df_daily)

            benchmark_data = {}
            for name, df_bench in wind_pkg.get("benchmarks", {}).items():
                if df_bench is not None and len(df_bench) > 0:
                    benchmark_data[name] = _df_to_daily_data(df_bench)

            tech_data = {
                "indicators": technical_payload.get("indicators", {}),
                "daily_data": daily_data,
                "benchmark_data": benchmark_data,
                "data_source": "wind_excel",
                "adjustment": "raw",
                "code": code,
                "market": market,
                "price_target": technical_payload.get("price_target"),
            }
            _set_technical_outputs(tech_data)
            return ctx

    cache = {"status": "missing"}
    if market != "hk":
        cache = load_ohlcv_cache("stock", code, market, cache_dir=cache_dir)

    def _use_cache(status: str) -> bool:
        tech_collector = TechnicalCollector()
        tech_data = tech_collector.build_collection_payload(
            cache["daily"], cache.get("weekly"), code=code, market=market,
            fetched_at=cache["fetched_at"], data_source=f"cache:{cache['source']}",
            include_optional=False, cache_dir=cache_dir,
        )
        if not tech_data:
            return False
        ctx.set("technical_cache_status", status)
        ctx.set("technical_cache_latest_date", cache.get("latest_date", ""))
        ctx.set("technical_cache_source", cache.get("source", ""))
        if status == "fallback_after_network_failure":
            ctx.set("technical_cache_fallback_reason", "network_collection_unavailable")
        _set_technical_outputs(tech_data)
        return True

    if cache.get("status") == "same_day" and _use_cache("same_day"):
        return ctx

    # 回退到网络采集
    tech_collector = TechnicalCollector()
    tech_data = tech_collector.collect(
        code, market=market, days=120, cache_dir=cache_dir,
    )

    if tech_data:
        if market != "hk":
            try:
                write_ohlcv_cache(
                    tech_data.get("daily_data"), weekly_data=tech_data.get("weekly_data"),
                    asset_type="stock", symbol=code, market=market,
                    source=tech_data.get("data_source", ""),
                    adjustment=tech_data.get("adjustment", ""),
                    fetched_at=tech_data.get("fetched_at"), cache_dir=cache_dir,
                )
            except OSError as exc:
                logger.warning("技术行情缓存写入失败: %s", exc)
        _set_technical_outputs(tech_data)
    elif cache.get("status") == "fallback_eligible" and _use_cache("fallback_after_network_failure"):
        return ctx
    else:
        _set_technical_outputs(None, "technical_data_unavailable")

    return ctx
