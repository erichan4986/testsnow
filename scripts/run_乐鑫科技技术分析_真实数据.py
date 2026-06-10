#!/usr/bin/env python3
"""乐鑫科技 Phase 2 技术形态分析报告 — 使用真实日K数据（mootdx + 本地前复权）"""

import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "utils" / "reporter"))

from technical_analyzer import analyze
from sections.technical_renderer import TechnicalRenderer

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main():
    report_dir = Path(__file__).parent.parent / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    # 1. 通过 TechnicalCollector 获取 qfq 数据
    sys.path.insert(0, str(Path(__file__).parent / "utils"))
    from data_collector import TechnicalCollector

    collector = TechnicalCollector()
    tech_data = collector.collect("688018", market=1, days=250, adjustment="qfq")

    logger.info("=" * 60)
    logger.info("乐鑫科技 (688018) — Phase 2 技术形态分析报告（qfq 真实数据）")
    logger.info("=" * 60)

    indicators = tech_data["indicators"]
    resonance = indicators.get("_resonance", {})

    logger.info(f"\n[数据] adjustment={tech_data.get('adjustment')}, bars={tech_data.get('days')}")
    logger.info(f"  最新收盘价: {indicators.get('close'):.2f}")

    # 2. 打印关键指标
    logger.info("\n" + "-" * 60)
    logger.info("【核心指标】")
    logger.info("-" * 60)
    logger.info(f"  收盘价:     {indicators.get('close', 'N/A')}")
    logger.info(f"  MA5:        {indicators.get('ma_5', 'N/A'):.2f}")
    logger.info(f"  MA10:       {indicators.get('ma_10', 'N/A'):.2f}")
    logger.info(f"  MA20:       {indicators.get('ma_20', 'N/A'):.2f}")
    logger.info(f"  MA60:       {indicators.get('ma_60', 'N/A'):.2f}")
    logger.info(f"  BOLL上轨:   {indicators.get('boll_upper', 'N/A'):.2f}")
    logger.info(f"  BOLL中轨:   {indicators.get('boll_mid', 'N/A'):.2f}")
    logger.info(f"  BOLL下轨:   {indicators.get('boll_lower', 'N/A'):.2f}")
    logger.info(f"  BOLL状态:   {indicators.get('boll_state', 'N/A')}")
    logger.info(f"  RSI(14):    {indicators.get('rsi_14', 'N/A'):.1f}")
    logger.info(f"  MACD:       {indicators.get('macd', 'N/A'):.3f}")
    logger.info(f"  MACD柱线:   {indicators.get('macd_hist', 'N/A'):.3f}")
    logger.info(f"  ADX:        {indicators.get('adx', 'N/A'):.1f}")
    logger.info(f"  BIAS(5):    {indicators.get('bias_5', 'N/A')}")
    logger.info(f"  BIAS(10):   {indicators.get('bias_10', 'N/A')}")
    logger.info(f"  成交量:     {indicators.get('volume', 'N/A')}")

    # 3. 打印趋势状态
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

    # 4. 打印 Phase 2B 新增信号
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

    mr = resonance.get("market_regime", {})
    logger.info(f"  [市场共振] {mr.get('impact', 'N/A')}")

    # 除权提醒
    corp = resonance.get("corporate_action_warning")
    if corp:
        logger.info(f"  [除权提醒] {corp['message']}")
    else:
        logger.info("  [除权提醒] 无")

    # 5. 打印关键价位
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

    # 6. 生成 Markdown 报告
    indicators_with_resonance = indicators.copy()
    indicators_with_resonance["_resonance"] = resonance
    ctx = {
        "stock_name": "乐鑫科技",
        "stock_raw": {"technical": {"indicators": indicators_with_resonance}},
        "technical_render_mode": "full",
        "chart_paths": {},
    }
    renderer = TechnicalRenderer()
    md_content = renderer.render(ctx)

    md_path = report_dir / f"乐鑫科技_技术形态分析_真实数据_{datetime.now().strftime('%Y%m%d')}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    logger.info("\n" + "=" * 60)
    logger.info(f"报告已保存: {md_path}")
    logger.info("=" * 60)

    # 7. 同时打印完整报告内容
    logger.info("\n" + "=" * 60)
    logger.info("【完整报告内容】")
    logger.info("=" * 60)
    logger.info(md_content)

    return md_path


if __name__ == "__main__":
    main()
