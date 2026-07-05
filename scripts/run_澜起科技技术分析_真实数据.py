#!/usr/bin/env python3
"""澜起科技 Phase 2 技术形态分析报告 — 使用真实日K数据（mootdx + 本地前复权）"""

import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "utils" / "reporter"))

from sections.technical_renderer import TechnicalRenderer

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main():
    report_dir = Path(__file__).parent.parent / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    # 通过 TechnicalCollector 获取 qfq 数据
    sys.path.insert(0, str(Path(__file__).parent / "utils"))
    from data_collector import TechnicalCollector

    collector = TechnicalCollector()
    tech_data = collector.collect("688008", market=1, days=250, adjustment="qfq")

    indicators = tech_data["indicators"]
    resonance = indicators.get("_resonance", {})

    # --- 保存原始数据到 CSV ---
    data_dir = Path(__file__).parent.parent / "data" / "raw"
    data_dir.mkdir(parents=True, exist_ok=True)

    # 获取原始日K并保存
    df_daily_raw = collector.fetch_kline("688008", market=1, days=250)
    if df_daily_raw is not None and not df_daily_raw.empty:
        raw_csv = data_dir / f"lanqi_688008_daily_{datetime.now().strftime('%Y%m%d')}_raw.csv"
        df_daily_raw.to_csv(raw_csv, index=False, encoding="utf-8-sig")
        logger.info(f"[CSV] 原始日K已保存: {raw_csv}")

        # 前复权日K (xdxr 本地获取暂不可用，依赖 analyzer 内部 gap-based 修复)
        pass

    # 周线数据
    df_weekly = collector.fetch_weekly_kline("688008", market=1, weeks=72)
    if df_weekly is not None and not df_weekly.empty:
        weekly_csv = data_dir / f"lanqi_688008_weekly_{datetime.now().strftime('%Y%m%d')}.csv"
        df_weekly.to_csv(weekly_csv, index=False, encoding="utf-8-sig")
        logger.info(f"[CSV] 周线已保存: {weekly_csv}")

    logger.info("=" * 60)
    logger.info("澜起科技 (688008) — Phase 2 技术形态分析报告（qfq 真实数据）")
    logger.info("=" * 60)
    logger.info(f"\n[数据] adjustment={tech_data.get('adjustment')}, bars={tech_data.get('days')}")
    logger.info(f"  最新收盘价: {indicators.get('close'):.2f}")

    # 打印关键指标
    logger.info("\n" + "-" * 60)
    logger.info("【核心指标】")
    logger.info("-" * 60)
    for k, v in [
        ("收盘价", indicators.get("close")),
        ("MA5", indicators.get("ma_5")),
        ("MA10", indicators.get("ma_10")),
        ("MA20", indicators.get("ma_20")),
        ("MA60", indicators.get("ma_60")),
        ("BOLL上轨", indicators.get("boll_upper")),
        ("BOLL中轨", indicators.get("boll_mid")),
        ("BOLL下轨", indicators.get("boll_lower")),
        ("BOLL状态", indicators.get("boll_state")),
        ("RSI(14)", indicators.get("rsi_14")),
        ("MACD", indicators.get("macd")),
        ("MACD柱线", indicators.get("macd_hist")),
        ("ADX", indicators.get("adx")),
        ("BIAS(5)", indicators.get("bias_5")),
        ("BIAS(10)", indicators.get("bias_10")),
        ("成交量", indicators.get("volume")),
    ]:
        if isinstance(v, float):
            logger.info(f"  {k:12s}: {v:.2f}")
        else:
            logger.info(f"  {k:12s}: {v}")

    # 打印趋势状态
    ts = resonance.get("trend_state", {})
    th = resonance.get("trend_health", {})
    logger.info("\n" + "-" * 60)
    logger.info("【趋势状态机】")
    logger.info("-" * 60)
    logger.info(f"  主要状态:   {ts.get('primary_state', 'N/A')}")
    logger.info(f"  阶段:       {ts.get('stage', 'N/A')}")
    logger.info(f"  健康度:     {th.get('score', 'N/A')}/100 ({th.get('grade', 'N/A')})")
    logger.info(f"  可信度:     {resonance.get('analysis_confidence', {}).get('level', 'N/A')}")

    wb = resonance.get("weekly_background", {})
    logger.info(f"  周线背景:   {wb.get('trend', 'N/A')}")
    logger.info(f"  MA结构:     {wb.get('ma_structure', 'N/A')}")

    ds = resonance.get("daily_structure", {})
    logger.info(f"  MA20方向:   {ds.get('ma20_direction', 'N/A')}")
    logger.info(f"  MA60方向:   {ds.get('ma60_direction', 'N/A')}")
    logger.info(f"  价格vsMA20: {ds.get('price_vs_ma20', 'N/A')}")

    # Phase 2 增强信号
    logger.info("\n" + "-" * 60)
    logger.info("【Phase 2 增强信号】")
    logger.info("-" * 60)

    candle = ds.get("candle_signal")
    if candle:
        logger.info(f"  [K线形态] {candle['signal']}（位置：{candle['location']}）")
    else:
        logger.info("  [K线形态] 无关键位信号")

    bias_warn = resonance.get("bias_extreme")
    if bias_warn:
        logger.info(f"  [BIAS预警] {bias_warn['warning']}（{bias_warn['level']}，方向：{bias_warn['direction']}）")
    else:
        logger.info("  [BIAS预警] 无极端偏离")

    fr = resonance.get("false_rebound")
    if fr:
        logger.info(f"  [假反弹]   {fr['signal']}（{fr['confidence']}）")
    else:
        logger.info("  [假反弹]   未触发")

    fb = resonance.get("false_breakout")
    if fb:
        logger.info(f"  [假突破]   {fb['signal']}（{fb['confidence']}）")
    else:
        logger.info("  [假突破]   未触发")

    sell = resonance.get("sell_assessment")
    if sell and sell.get("met_count", 0) >= 1:
        logger.info(f"  [卖出三要素] 满足 {sell['met_count']}/3 条：{sell['recommendation']}")
        for f in sell.get("factors", []):
            logger.info(f"    - {f}")
    else:
        logger.info("  [卖出三要素] 不满足卖出条件")

    sr = resonance.get("sr_transformation")
    if sr:
        for sig in sr.get("signals", []):
            logger.info(f"  [支撑阻力转化] {sig['signal']}")
    else:
        logger.info("  [支撑阻力转化] 无转化信号")

    mr = resonance.get("market_resonance", {})
    logger.info(f"  [市场共振] {mr.get('state', 'N/A')}（{mr.get('confidence', 'N/A')}）— {mr.get('impact', 'N/A')}")
    if mr.get("missing"):
        logger.info(f"    数据备注: {mr['missing']}")

    corp = resonance.get("corporate_action_warning")
    if corp:
        logger.info(f"  [除权提醒] {corp['message']}")
    else:
        logger.info("  [除权提醒] 无")

    # 关键价位
    kl = resonance.get("key_levels", {})
    logger.info("\n" + "-" * 60)
    logger.info("【关键价位】")
    logger.info("-" * 60)
    sz = kl.get("support_zone")
    rz = kl.get("resistance_zone")
    if sz:
        logger.info(f"  支撑区: {sz.get('zone_low')} - {sz.get('zone_high')} ({sz.get('strength')})")
    else:
        logger.info("  支撑区: 暂无")
    if rz:
        logger.info(f"  阻力区: {rz.get('zone_low')} - {rz.get('zone_high')} ({rz.get('strength')})")
    else:
        logger.info("  阻力区: 暂无")

    inv = resonance.get("invalidation", {})
    if inv.get("soft_warning"):
        logger.info(f"  第一警戒: {inv['soft_warning']}")
    if inv.get("hard_invalid"):
        logger.info(f"  中期失效: {inv['hard_invalid']}")

    # 生成 Markdown 报告
    indicators_with_resonance = indicators.copy()
    indicators_with_resonance["_resonance"] = resonance
    ctx = {
        "stock_name": "澜起科技",
        "stock_raw": {
            "technical": {
                "indicators": indicators_with_resonance,
                "price_target": tech_data.get("price_target"),
                "fund_flow": tech_data.get("fund_flow"),
                "concept_blocks": tech_data.get("concept_blocks"),
            }
        },
        "technical_render_mode": "full",
        "chart_paths": {},
    }
    renderer = TechnicalRenderer()
    md_content = renderer.render(ctx)

    md_path = report_dir / f"澜起科技_技术形态分析_真实数据_{datetime.now().strftime('%Y%m%d')}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    logger.info("\n" + "=" * 60)
    logger.info(f"报告已保存: {md_path}")
    logger.info("=" * 60)

    logger.info("\n" + "=" * 60)
    logger.info("【完整报告内容】")
    logger.info("=" * 60)
    logger.info(md_content)

    return md_path


if __name__ == "__main__":
    main()
