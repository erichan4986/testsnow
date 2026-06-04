"""价格目标与触发条件核心引擎 — 纯 pandas 实现。"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def zigzag(close: pd.Series, min_pct: float = 0.05) -> List[Dict]:
    """
    识别主要波段转折点（Zigzag）。
    min_pct: 最小转折幅度（日线5%，周线10%基线/芯片股12%）
    返回: [{idx, price, type: 'peak'/'valley'}, ...]
    """
    if len(close) < 3:
        return []

    pivots = []
    direction = 0  # 0=unknown, 1=up, -1=down
    last_pivot_idx = 0
    last_pivot_price = close.iloc[0]
    last_pivot_type = "valley"  # start as valley

    for i in range(1, len(close)):
        price = close.iloc[i]
        change = (price - last_pivot_price) / last_pivot_price

        if direction == 0:
            if abs(change) >= min_pct:
                direction = 1 if change > 0 else -1
                # Initial pivot type depends on first move direction
                initial_type = "valley" if direction == 1 else "peak"
                pivots.append({"idx": last_pivot_idx, "price": last_pivot_price, "type": initial_type})
                last_pivot_type = "peak" if direction == 1 else "valley"
                last_pivot_idx = i
                last_pivot_price = price
        elif direction == 1:
            if price > last_pivot_price:
                last_pivot_idx = i
                last_pivot_price = price
            elif (last_pivot_price - price) / last_pivot_price >= min_pct:
                pivots.append({"idx": last_pivot_idx, "price": last_pivot_price, "type": "peak"})
                direction = -1
                last_pivot_type = "valley"
                last_pivot_idx = i
                last_pivot_price = price
        elif direction == -1:
            if price < last_pivot_price:
                last_pivot_idx = i
                last_pivot_price = price
            elif (price - last_pivot_price) / last_pivot_price >= min_pct:
                pivots.append({"idx": last_pivot_idx, "price": last_pivot_price, "type": "valley"})
                direction = 1
                last_pivot_type = "peak"
                last_pivot_idx = i
                last_pivot_price = price

    # Add final pivot if different from last recorded
    if pivots and last_pivot_idx != pivots[-1]["idx"]:
        final_type = "peak" if last_pivot_price > pivots[-1]["price"] else "valley"
        pivots.append({"idx": last_pivot_idx, "price": last_pivot_price, "type": final_type})
    elif not pivots:
        pivots.append({"idx": last_pivot_idx, "price": last_pivot_price, "type": last_pivot_type})

    return pivots


def fib_extension(low: float, high: float, level: float) -> float:
    """从波段低点到高点的斐波那契扩展。"""
    return high + (high - low) * (level - 1)


def fib_targets_with_convergence(
    bands: List[Dict], level: float = 1.272, convergence_pct: float = 0.03
) -> List[Dict]:
    """
    计算多个波段的同向扩展位，检查是否形成汇聚区。
    bands: [{low, high}, ...]
    返回: [{price, band_idx, in_convergence: bool}, ...]
    """
    targets = []
    for i, band in enumerate(bands):
        price = fib_extension(band["low"], band["high"], level)
        targets.append({"price": round(price, 2), "band_idx": i, "in_convergence": False})

    # 检查汇聚：≥2个目标落在 convergence_pct 价格区间内
    n = len(targets)
    for i in range(n):
        for j in range(i + 1, n):
            p1, p2 = targets[i]["price"], targets[j]["price"]
            diff = abs(p1 - p2) / max(p1, p2, 1e-9)
            if diff <= convergence_pct:
                targets[i]["in_convergence"] = True
                targets[j]["in_convergence"] = True

    return targets
