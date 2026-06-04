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
                pivots.append({"idx": last_pivot_idx, "price": last_pivot_price, "type": last_pivot_type})
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
        pivots.append({"idx": last_pivot_idx, "price": last_pivot_price, "type": last_pivot_type})
    elif not pivots:
        pivots.append({"idx": last_pivot_idx, "price": last_pivot_price, "type": last_pivot_type})

    return pivots
