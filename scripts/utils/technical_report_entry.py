"""Shared output path for standalone technical-analysis entries."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from reporter.sections.technical_renderer import TechnicalRenderer


logger = logging.getLogger(__name__)

_INDICATORS = (
    ("收盘价", "close"), ("MA5", "ma_5"), ("MA10", "ma_10"),
    ("MA20", "ma_20"), ("MA60", "ma_60"), ("BOLL上轨", "boll_upper"),
    ("BOLL中轨", "boll_mid"), ("BOLL下轨", "boll_lower"),
    ("BOLL状态", "boll_state"), ("RSI(14)", "rsi_14"),
    ("MACD", "macd"), ("MACD柱线", "macd_hist"), ("ADX", "adx"),
    ("BIAS(5)", "bias_5"), ("BIAS(10)", "bias_10"), ("成交量", "volume"),
)


def _section(title: str) -> None:
    logger.info("\n%s", "-" * 60)
    logger.info("【%s】", title)
    logger.info("%s", "-" * 60)


def _value(value) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def _log_diagnostics(indicators: dict, resonance: dict) -> None:
    _section("核心指标")
    for label, key in _INDICATORS:
        logger.info("  %-12s: %s", label, _value(indicators.get(key)))

    trend = resonance.get("trend_state", {})
    health = resonance.get("trend_health", {})
    weekly = resonance.get("weekly_background", {})
    daily = resonance.get("daily_structure", {})
    _section("趋势状态机")
    logger.info("  主要状态:   %s", trend.get("primary_state", "N/A"))
    logger.info("  阶段:       %s", trend.get("stage", "N/A"))
    logger.info("  健康度:     %s/100 (%s)", health.get("score", "N/A"), health.get("grade", "N/A"))
    logger.info("  可信度:     %s", resonance.get("analysis_confidence", {}).get("level", "N/A"))
    logger.info("  周线背景:   %s", weekly.get("trend", "N/A"))
    logger.info("  MA结构:     %s", weekly.get("ma_structure", "N/A"))
    logger.info("  MA20方向:   %s", daily.get("ma20_direction", "N/A"))
    logger.info("  MA60方向:   %s", daily.get("ma60_direction", "N/A"))
    logger.info("  价格vsMA20: %s", daily.get("price_vs_ma20", "N/A"))

    _section("Phase 2 增强信号")
    candle = daily.get("candle_signal")
    logger.info("  [K线形态] %s", (
        f"{candle.get('signal', 'N/A')}（位置：{candle.get('location', 'N/A')}）"
        if candle else "无关键位信号"
    ))
    bias = resonance.get("bias_extreme")
    logger.info("  [BIAS预警] %s", (
        f"{bias.get('warning', 'N/A')}（{bias.get('level', 'N/A')}，方向：{bias.get('direction', 'N/A')}）"
        if bias else "无极端偏离"
    ))
    for key, label in (("false_rebound", "假反弹"), ("false_breakout", "假突破")):
        signal = resonance.get(key)
        text = f"{signal.get('signal', 'N/A')}（{signal.get('confidence', 'N/A')}）" if signal else "未触发"
        logger.info("  [%s] %s", label, text)

    sell = resonance.get("sell_assessment") or {}
    if sell.get("met_count", 0) >= 1:
        logger.info("  [卖出三要素] 满足 %s/3 条：%s", sell["met_count"], sell.get("recommendation", "N/A"))
        for factor in sell.get("factors", []):
            logger.info("    - %s", factor)
    else:
        logger.info("  [卖出三要素] 不满足卖出条件")

    transformation = resonance.get("sr_transformation") or {}
    signals = transformation.get("signals", [])
    if signals:
        for signal in signals:
            logger.info("  [支撑阻力转化] %s", signal.get("signal", "N/A"))
    else:
        logger.info("  [支撑阻力转化] 无转化信号")

    market = resonance.get("market_resonance", {})
    logger.info(
        "  [市场共振] %s（%s）— %s", market.get("state", "N/A"),
        market.get("confidence", "N/A"), market.get("impact", "N/A"),
    )
    if market.get("missing"):
        logger.info("    数据备注: %s", market["missing"])
    corporate = resonance.get("corporate_action_warning")
    logger.info("  [除权提醒] %s", corporate.get("message", "N/A") if corporate else "无")

    _section("关键价位")
    levels = resonance.get("key_levels", {})
    for label, key in (("支撑区", "support_zone"), ("阻力区", "resistance_zone")):
        zone = levels.get(key)
        text = f"{zone.get('zone_low')} - {zone.get('zone_high')} ({zone.get('strength')})" if zone else "暂无"
        logger.info("  %s: %s", label, text)
    invalidation = resonance.get("invalidation", {})
    if invalidation.get("soft_warning"):
        logger.info("  第一警戒: %s", invalidation["soft_warning"])
    if invalidation.get("hard_invalid"):
        logger.info("  中期失效: %s", invalidation["hard_invalid"])


def write_technical_report(
    *, stock_name: str, stock_code: str, indicators: dict, resonance: dict,
    report_dir: Path, data_lines=(), price_target=None, fund_flow=None,
    concept_blocks=None, title_suffix: str = "真实数据", report_date: date | None = None,
) -> Path:
    logger.info("%s", "=" * 60)
    logger.info("%s (%s) — Phase 2 技术形态分析报告（%s）", stock_name, stock_code, title_suffix)
    logger.info("%s", "=" * 60)
    for line in data_lines:
        logger.info("%s", line)
    _log_diagnostics(indicators, resonance)

    technical = {"indicators": {**indicators, "_resonance": resonance}}
    for key, value in (
        ("price_target", price_target), ("fund_flow", fund_flow),
        ("concept_blocks", concept_blocks),
    ):
        if value is not None:
            technical[key] = value
    context = {
        "stock_name": stock_name,
        "stock_raw": {"technical": technical},
        "technical_render_mode": "full",
        "chart_paths": {},
    }
    content = TechnicalRenderer().render(context)
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = (report_date or date.today()).strftime("%Y%m%d")
    path = report_dir / f"{stock_name}_技术形态分析_真实数据_{stamp}.md"
    path.write_text(content, encoding="utf-8")
    logger.info("\n%s\n报告已保存: %s\n%s", "=" * 60, path, "=" * 60)
    logger.info("\n%s\n【完整报告内容】\n%s\n%s", "=" * 60, "=" * 60, content)
    return path
