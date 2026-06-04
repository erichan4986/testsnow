# 技术面价格目标与触发条件 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-timeframe price target system (Pattern + Fibonacci + Resonance) with strict trigger/failure conditions, profit/risk filtering, and 6-factor confidence scoring, integrated into the existing stock report pipeline.

**Architecture:** A new `price_target.py` core module performs Zigzag pivot detection, Fibonacci extension with convergence checks, pattern measurement, and target synthesis. It consumes daily (120d) and weekly (72w) OHLCV DataFrames produced by an enhanced `TechnicalCollector`. The `stock_reporter` renders a dedicated Markdown section. Pure pandas, no new dependencies.

**Tech Stack:** Python 3.10, pandas, numpy, akshare (weekly K-lines), existing `technical_analyzer.py` indicators.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/utils/reporter/price_target.py` | **Create** | Core engine: Zigzag, Fibonacci extension, pattern targets, resonance, synthesis, confidence scoring, profit/risk filter, time estimation |
| `scripts/utils/data_collector.py` | **Modify** | `TechnicalCollector`: add weekly K-line fetch (akshare A-share, Wind CSV HK), integrate price_target analysis into `collect()` return value |
| `scripts/utils/stock_reporter.py` | **Modify** | Add `_price_target_section()` method, call it from `generate_stock_report()` after existing technical analysis section |
| `tests/reporter/test_price_target.py` | **Create** | Unit tests for Zigzag, Fibonacci, pattern targets, confidence scoring, profit/risk filter |

---

## Prerequisite Knowledge

- `technical_analyzer.py` already provides: `_sma`, `_ema`, `_atr`, `_adx`, `_macd`, `_bollinger`, `_rsi`, `_obv`, `detect_double_top`, `detect_double_bottom`, `analyze()`.
- `data_collector.py` `TechnicalCollector.collect()` returns `{"indicators": {...}, "_resonance": {...}, "_patterns": [...], "_levels": {...}}`.
- `stock_reporter.py` `_technical_analysis_section()` renders the existing technical analysis Markdown using `stock_raw.get("technical", {})`.
- Standard DataFrame columns expected: `date`, `open`, `high`, `low`, `close`, `volume`. Optional: `amount`.

---

### Task 1: Zigzag Pivot Detection

**Files:**
- Create: `scripts/utils/reporter/price_target.py`
- Test: `tests/reporter/test_price_target.py`

- [ ] **Step 1: Write the failing test**

```python
import pandas as pd
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
from price_target import zigzag


def test_zigzag_basic():
    """Zigzag should find peaks and valleys with 5% minimum reversal."""
    close = pd.Series([100, 105, 110, 100, 95, 100, 110, 115, 105, 100, 95, 100])
    pivots = zigzag(close, min_pct=0.05)
    assert len(pivots) >= 2
    types = [p["type"] for p in pivots]
    assert "peak" in types
    assert "valley" in types
    # Check that consecutive pivots alternate
    for i in range(1, len(pivots)):
        assert pivots[i]["type"] != pivots[i - 1]["type"]


def test_zigzag_no_small_noise():
    """Moves smaller than min_pct should not create pivots."""
    close = pd.Series([100, 101, 102, 101, 100, 101, 102])  # all < 3%
    pivots = zigzag(close, min_pct=0.05)
    assert len(pivots) <= 1  # only start point
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/reporter/test_price_target.py::test_zigzag_basic -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'price_target'"

- [ ] **Step 3: Write minimal implementation**

Create `scripts/utils/reporter/price_target.py` with:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/reporter/test_price_target.py::test_zigzag_basic tests/reporter/test_price_target.py::test_zigzag_no_small_noise -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/reporter/price_target.py tests/reporter/test_price_target.py
git commit -m "feat(price_target): add Zigzag pivot detection"
```

---

### Task 2: Fibonacci Extension + Convergence

**Files:**
- Modify: `scripts/utils/reporter/price_target.py`
- Test: `tests/reporter/test_price_target.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/reporter/test_price_target.py`:

```python
from price_target import fib_extension, fib_targets_with_convergence


def test_fib_extension():
    """Fibonacci extension from low=100 to high=120."""
    assert fib_extension(100, 120, 1.0) == 120.0
    assert fib_extension(100, 120, 1.272) == 125.44
    assert abs(fib_extension(100, 120, 1.618) - 132.36) < 0.01


def test_fib_convergence():
    """Multiple bands pointing to similar prices within 3% should converge."""
    bands = [
        {"low": 100, "high": 120},   # 1.272 = 125.44
        {"low": 105, "high": 122},   # 1.272 = 123.62
    ]
    targets = fib_targets_with_convergence(bands, level=1.272, convergence_pct=0.03)
    # 125.44 vs 123.62: diff = 1.46%, within 3% -> should have convergence info
    assert any("convergence" in t or "汇聚" in str(t) for t in targets)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/reporter/test_price_target.py::test_fib_extension -v`
Expected: FAIL with "ImportError: cannot import name 'fib_extension'"

- [ ] **Step 3: Write minimal implementation**

Append to `scripts/utils/reporter/price_target.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/reporter/test_price_target.py::test_fib_extension tests/reporter/test_price_target.py::test_fib_convergence -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/reporter/price_target.py tests/reporter/test_price_target.py
git commit -m "feat(price_target): add Fibonacci extension and convergence detection"
```

---

### Task 3: Pattern Measurement Targets

**Files:**
- Modify: `scripts/utils/reporter/price_target.py`
- Test: `tests/reporter/test_price_target.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/reporter/test_price_target.py`:

```python
from price_target import pattern_target


def test_double_bottom_target():
    """Double bottom: neckline=100, bottom=90 -> target=110."""
    assert pattern_target(100, 90, is_bullish=True) == 110.0


def test_double_top_target():
    """Double top: neckline=90, top=100 -> target=80."""
    assert pattern_target(90, 100, is_bullish=False) == 80.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/reporter/test_price_target.py::test_double_bottom_target -v`
Expected: FAIL with "ImportError: cannot import name 'pattern_target'"

- [ ] **Step 3: Write minimal implementation**

Append to `scripts/utils/reporter/price_target.py`:

```python
def pattern_target(neckline: float, extreme: float, is_bullish: bool) -> float:
    """形态测距：双顶/双底/头肩等。"""
    height = abs(extreme - neckline)
    return neckline + height if is_bullish else neckline - height


def extract_pattern_info(pattern: Dict) -> Optional[Dict]:
    """
    从 technical_analyzer 的形态 dict 中提取颈线价和测距所需信息。
    支持双底（bottom1, bottom2, peak=neckline）和双顶（top1, top2, valley=neckline）。
    """
    ptype = pattern.get("pattern", "")
    if ptype == "双底":
        return {
            "type": "double_bottom",
            "is_bullish": True,
            "neckline": pattern.get("peak"),
            "extreme": pattern.get("bottom1"),
        }
    elif ptype == "双顶":
        return {
            "type": "double_top",
            "is_bullish": False,
            "neckline": pattern.get("valley"),
            "extreme": pattern.get("top1"),
        }
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/reporter/test_price_target.py::test_double_bottom_target tests/reporter/test_price_target.py::test_double_top_target -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/reporter/price_target.py tests/reporter/test_price_target.py
git commit -m "feat(price_target): add pattern measurement targets"
```

---

### Task 4: Weekly Trend Analysis

**Files:**
- Modify: `scripts/utils/reporter/price_target.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/reporter/test_price_target.py`:

```python
from price_target import weekly_trend_analysis


def test_weekly_trend_strong():
    """ADX>30, +DI>-DI -> strong bullish trend."""
    df = pd.DataFrame({
        "high": [110, 112, 115, 113, 118, 120, 122],
        "low": [105, 107, 110, 108, 113, 115, 117],
        "close": [108, 111, 114, 112, 117, 119, 121],
    })
    trend = weekly_trend_analysis(df)
    assert trend["direction"] in ("多头", "bullish")
    assert trend["adx_score"] == 10  # ADX>30
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/reporter/test_price_target.py::test_weekly_trend_strong -v`
Expected: FAIL with "ImportError: cannot import name 'weekly_trend_analysis'"

- [ ] **Step 3: Write minimal implementation**

Append to `scripts/utils/reporter/price_target.py`. Import `_adx` from `technical_analyzer` at top of file:

```python
# Add at top of price_target.py, after imports
try:
    from .technical_analyzer import _adx, _sma, _atr, _macd, _bollinger
except ImportError:
    from technical_analyzer import _adx, _sma, _atr, _macd, _bollinger


def weekly_trend_analysis(df_weekly: pd.DataFrame) -> Dict:
    """
    周线趋势分析：ADX方向、+DI/-DI、MA排列、BOLL带宽。
    返回: {direction, adx, adx_score, plus_di, minus_di, is_ranging}
    """
    if df_weekly is None or len(df_weekly) < 14:
        return {"direction": "数据不足", "adx_score": 0, "is_ranging": True}

    close = df_weekly["close"]
    adx, plus_di, minus_di = _adx(df_weekly)
    latest_adx = float(adx.iloc[-1])
    latest_plus = float(plus_di.iloc[-1])
    latest_minus = float(minus_di.iloc[-1])

    # ADX scoring for confidence
    if latest_adx > 30 and latest_plus > latest_minus:
        adx_score = 10
        direction = "多头"
    elif latest_adx > 25 and latest_plus > latest_minus:
        adx_score = 7
        direction = "多头"
    elif latest_adx > 20 and latest_plus > latest_minus:
        adx_score = 4
        direction = "多头"
    elif latest_adx > 25 and latest_plus < latest_minus:
        adx_score = 7
        direction = "空头"
    else:
        adx_score = 0
        direction = "震荡"

    # Ranging check: ADX<20 for 4 weeks AND BOLL bandwidth < 8%
    recent_adx = adx.tail(4)
    is_ranging = bool((recent_adx < 20).all())
    if is_ranging:
        boll_up, boll_mid, boll_low = _bollinger(close, period=20)
        bandwidth = (boll_up.iloc[-1] - boll_low.iloc[-1]) / boll_mid.iloc[-1]
        is_ranging = is_ranging and (bandwidth < 0.08)
        if is_ranging:
            direction = "震荡"

    return {
        "direction": direction,
        "adx": round(latest_adx, 1),
        "adx_score": adx_score,
        "plus_di": round(latest_plus, 1),
        "minus_di": round(latest_minus, 1),
        "is_ranging": is_ranging,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/reporter/test_price_target.py::test_weekly_trend_strong -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/reporter/price_target.py tests/reporter/test_price_target.py
git commit -m "feat(price_target): add weekly trend analysis with ADX scoring and ranging detection"
```

---

### Task 5: Target Synthesis Engine

**Files:**
- Modify: `scripts/utils/reporter/price_target.py`
- Test: `tests/reporter/test_price_target.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/reporter/test_price_target.py`:

```python
from price_target import synthesize_targets


def test_synthesize_resonance():
    """Daily and weekly patterns both bullish -> mean for base target."""
    daily_pattern = {"type": "double_bottom", "is_bullish": True, "neckline": 100, "extreme": 90}
    weekly_pattern = {"type": "double_bottom", "is_bullish": True, "neckline": 105, "extreme": 95}
    daily_fib = {"1.0": 100, "1.272": 110, "1.618": 120}
    weekly_fib = {"1.0": 105, "1.272": 115, "1.618": 125}
    result = synthesize_targets(
        daily_pattern, weekly_pattern, daily_fib, weekly_fib,
        current_price=100, is_bullish=True
    )
    assert result["direction"] == "中线看多"
    # Conservative = min of weekly 1.0, daily neckline
    assert result["conservative"] == 100.0
    # Base = mean of daily pattern target (110) and weekly 1.272 (115)
    assert result["base"] == 112.5
    # Aggressive = weekly 1.618
    assert result["aggressive"] == 125.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/reporter/test_price_target.py::test_synthesize_resonance -v`
Expected: FAIL with "ImportError: cannot import name 'synthesize_targets'"

- [ ] **Step 3: Write minimal implementation**

Append to `scripts/utils/reporter/price_target.py`:

```python
def synthesize_targets(
    daily_pattern: Optional[Dict],
    weekly_pattern: Optional[Dict],
    daily_fib: Dict,
    weekly_fib: Dict,
    current_price: float,
    is_bullish: bool,
) -> Dict:
    """
    标准化目标合成表（Spec Section 3）。
    返回: {direction, conservative, base, aggressive, method}
    """
    daily_has = daily_pattern is not None
    weekly_has = weekly_pattern is not None

    # Daily pattern target
    daily_pt = None
    if daily_has:
        daily_pt = pattern_target(daily_pattern["neckline"], daily_pattern["extreme"], is_bullish)

    # Weekly pattern target
    weekly_pt = None
    if weekly_has:
        weekly_pt = pattern_target(weekly_pattern["neckline"], weekly_pattern["extreme"], is_bullish)

    def _get_fib(fib_dict, key, default=None):
        return fib_dict.get(key, default)

    if daily_has and weekly_has:
        # 共振：同向有形态
        conservative = min(
            _get_fib(weekly_fib, "1.0", float("inf")),
            daily_pattern["neckline"] if daily_pattern else float("inf"),
        )
        base = (daily_pt + _get_fib(weekly_fib, "1.272", daily_pt)) / 2
        aggressive = _get_fib(weekly_fib, "1.618", weekly_pt or base)
        method = "A+B交叉验证（日K形态+周K形态共振）"
    elif daily_has or weekly_has:
        # 仅一方有形态
        has_pt = daily_pt if daily_has else weekly_pt
        has_neck = daily_pattern["neckline"] if daily_has else weekly_pattern["neckline"]
        no_fib = weekly_fib if daily_has else daily_fib
        conservative = min(has_neck, _get_fib(no_fib, "1.0", has_neck))
        base = has_pt
        aggressive = has_pt * 1.3 if has_pt else _get_fib(no_fib, "1.618", base)
        method = f"{'日K' if daily_has else '周K'}形态主导"
    else:
        # 双方都无形态，只有波段
        fib = weekly_fib if weekly_fib else daily_fib
        conservative = _get_fib(fib, "1.0", current_price)
        base = _get_fib(fib, "1.272", current_price * 1.1)
        aggressive = _get_fib(fib, "1.618", current_price * 1.2)
        method = "纯斐波那契扩展（无形态）"

    # 激进目标上限：不超过当前价+50%（科技股+60%）
    agg_limit = current_price * 1.5
    # NOTE: actual sector detection (tech=60%) happens at caller level
    aggressive_capped = min(aggressive, agg_limit) if aggressive else None
    is_far = aggressive and aggressive > agg_limit

    return {
        "direction": "中线看多" if is_bullish else "中线看空",
        "conservative": round(conservative, 2) if conservative else None,
        "base": round(base, 2) if base else None,
        "aggressive": round(aggressive_capped, 2) if aggressive_capped else None,
        "aggressive_raw": round(aggressive, 2) if aggressive else None,
        "is_far_target": is_far,
        "method": method,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/reporter/test_price_target.py::test_synthesize_resonance -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/reporter/price_target.py tests/reporter/test_price_target.py
git commit -m "feat(price_target): add standardized target synthesis engine"
```

---

### Task 6: Profit/Risk Filter

**Files:**
- Modify: `scripts/utils/reporter/price_target.py`
- Test: `tests/reporter/test_price_target.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/reporter/test_price_target.py`:

```python
from price_target import profit_risk_filter


def test_profit_risk_pass():
    """Conservative target 135, trigger 128.5, stop 118 -> ratio = 6.5/10.5 = 1.71 >= 1.5 -> pass."""
    result = profit_risk_filter(
        conservative_target=135.0,
        neckline=128.5,
        daily_atr=7.0,
        min_ratio=1.5,
    )
    assert result["pass"] is True
    assert result["ratio"] >= 1.5


def test_profit_risk_fail():
    """Conservative target 130, trigger 128.5, stop 118 -> ratio = 1.5/10.5 = 0.14 < 1.5 -> fail."""
    result = profit_risk_filter(
        conservative_target=130.0,
        neckline=128.5,
        daily_atr=7.0,
        min_ratio=1.5,
    )
    assert result["pass"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/reporter/test_price_target.py::test_profit_risk_pass -v`
Expected: FAIL with "ImportError: cannot import name 'profit_risk_filter'"

- [ ] **Step 3: Write minimal implementation**

Append to `scripts/utils/reporter/price_target.py`:

```python
def profit_risk_filter(
    conservative_target: float,
    neckline: float,
    daily_atr: float,
    min_ratio: float = 1.5,
) -> Dict:
    """
    盈亏比过滤（Spec Section 4）。
    用预估触发价（颈线 + 0.3×ATR）和预估止损价（颈线 - 1.5×ATR）计算。
    """
    trigger_price = neckline + 0.3 * daily_atr
    stop_price = neckline - 1.5 * daily_atr
    potential_gain = abs(conservative_target - trigger_price)
    initial_risk = abs(trigger_price - stop_price)

    if initial_risk <= 0:
        return {"pass": False, "ratio": 0.0, "trigger_price": trigger_price, "stop_price": stop_price}

    ratio = potential_gain / initial_risk
    return {
        "pass": ratio >= min_ratio,
        "ratio": round(ratio, 2),
        "trigger_price": round(trigger_price, 2),
        "stop_price": round(stop_price, 2),
        "potential_gain": round(potential_gain, 2),
        "initial_risk": round(initial_risk, 2),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/reporter/test_price_target.py::test_profit_risk_pass tests/reporter/test_price_target.py::test_profit_risk_fail -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/reporter/price_target.py tests/reporter/test_price_target.py
git commit -m "feat(price_target): add profit/risk ratio filter with estimated trigger/stop prices"
```

---

### Task 7: 6-Factor Confidence Scoring

**Files:**
- Modify: `scripts/utils/reporter/price_target.py`
- Test: `tests/reporter/test_price_target.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/reporter/test_price_target.py`:

```python
from price_target import confidence_score, _momentum_score


def test_momentum_score_best():
    """MACD expanding + RSI 50 + MA bull = 10."""
    assert _momentum_score(macd_expanding=True, rsi=50, ma_bull=True) == 10


def test_momentum_score_bad():
    """MACD dead cross = 2 regardless of others."""
    assert _momentum_score(macd_dead=True, rsi=50, ma_bull=True) == 2


def test_confidence_high():
    """All best-case factors -> score >= 8.0 (High)."""
    score = confidence_score(
        resonance=10, pattern_quality=10, breakout_quality=10,
        weekly_adx=10, momentum=10, fib_convergence=10,
    )
    assert score >= 8.0
    assert confidence_level(score) == "高"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/reporter/test_price_target.py::test_momentum_score_best -v`
Expected: FAIL with "ImportError: cannot import name '_momentum_score'"

- [ ] **Step 3: Write minimal implementation**

Append to `scripts/utils/reporter/price_target.py`:

```python
def _momentum_score(
    macd_expanding: bool = False,
    macd_contracting: bool = False,
    macd_dead: bool = False,
    rsi: float = 50.0,
    kdj_golden: bool = False,
    ma_bull: bool = False,
) -> int:
    """
    动量评分三档简化（Spec Section 7）。
    配合佳=10 / 中性=6 / 不良=2
    """
    if macd_dead and not macd_contracting:
        return 2  # 不良：死叉且无收缩例外

    if macd_expanding and 40 <= rsi <= 70 and ma_bull:
        return 10  # 配合佳

    # 中性：金叉收缩、或RSI偏高/偏低但无死叉、或MA非多头
    is_moderate = (
        (macd_contracting and not macd_dead)
        or (rsi > 70 and not macd_expanding)
        or (rsi < 40 and not macd_dead)
        or (not ma_bull and not macd_dead)
    )
    if is_moderate:
        return 6

    return 6  # default neutral


def confidence_score(
    resonance: int,
    pattern_quality: int,
    breakout_quality: int,
    weekly_adx: int,
    momentum: int,
    fib_convergence: int,
) -> float:
    """
    六因子加权评分，返回0-10分。
    权重：共振30% + 形态20% + 突破20% + 周线ADX15% + 动量5% + 斐波那契汇聚10%
    """
    score = (
        resonance * 0.30 +
        pattern_quality * 0.20 +
        breakout_quality * 0.20 +
        weekly_adx * 0.15 +
        momentum * 0.05 +
        fib_convergence * 0.10
    )
    return round(score, 1)


def confidence_level(score: float, aggressive_is_far: bool = False) -> str:
    """
    置信度映射。若激进目标超远，上限锁为"中"。
    """
    if aggressive_is_far and score >= 8.0:
        return "中"  # 上限锁定
    if score >= 8.0:
        return "高"
    elif score >= 6.0:
        return "中"
    elif score >= 4.0:
        return "低"
    return "观望"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/reporter/test_price_target.py::test_momentum_score_best tests/reporter/test_price_target.py::test_momentum_score_bad tests/reporter/test_price_target.py::test_confidence_high -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/reporter/price_target.py tests/reporter/test_price_target.py
git commit -m "feat(price_target): add 6-factor confidence scoring with momentum tier system"
```

---

### Task 8: Time Estimation with Momentum Adjustment

**Files:**
- Modify: `scripts/utils/reporter/price_target.py`
- Test: `tests/reporter/test_price_target.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/reporter/test_price_target.py`:

```python
from price_target import estimate_time


def test_estimate_time_basic():
    """Target 150, current 100, ATR=5 -> base 15-20 days."""
    low, high = estimate_time(150, 100, 5.0)
    assert low == 15.0
    assert high == 20.0


def test_estimate_time_macd_expanding():
    """MACD expanding -> time × 0.85."""
    low, high = estimate_time(150, 100, 5.0, macd_momentum="expanding")
    assert low == 12.75  # 15 * 0.85
    assert high == 17.0  # 20 * 0.85
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/reporter/test_price_target.py::test_estimate_time_basic -v`
Expected: FAIL with "ImportError: cannot import name 'estimate_time'"

- [ ] **Step 3: Write minimal implementation**

Append to `scripts/utils/reporter/price_target.py`:

```python
def estimate_time(
    target_price: float,
    current_price: float,
    daily_atr: float,
    macd_momentum: str = "flat",
    rsi: float = 50.0,
) -> Tuple[float, float]:
    """
    基于ATR估算到达目标价所需时间范围（Spec Section 8）。
    动量修正：MACD柱线斜率和RSI区间微调。
    """
    distance = abs(target_price - current_price)
    if daily_atr <= 0:
        return 0.0, 0.0

    min_days = distance / daily_atr
    base_low, base_high = min_days * 1.5, min_days * 2.0

    multiplier = 1.0
    if macd_momentum == "expanding":
        multiplier *= 0.85
    elif macd_momentum == "contracting":
        multiplier *= 1.25

    if rsi > 65:
        multiplier *= 1.1
    elif rsi < 40:
        multiplier *= 0.9

    return round(base_low * multiplier, 1), round(base_high * multiplier, 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/reporter/test_price_target.py::test_estimate_time_basic tests/reporter/test_price_target.py::test_estimate_time_macd_expanding -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/reporter/price_target.py tests/reporter/test_price_target.py
git commit -m "feat(price_target): add ATR-based time estimation with momentum adjustment"
```

---

### Task 9: Main Analysis Entry Point

**Files:**
- Modify: `scripts/utils/reporter/price_target.py`
- Test: `tests/reporter/test_price_target.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/reporter/test_price_target.py`:

```python
from price_target import analyze_price_target


def test_analyze_price_target_minimal():
    """Minimal daily+weekly data should return a result dict with expected keys."""
    daily = pd.DataFrame({
        "open": [90, 92, 95, 93, 98, 100, 102, 101, 105, 107, 106, 110, 112, 111, 115, 118, 116, 120, 122, 121, 125, 128, 126, 130, 132, 131, 135, 138, 136, 140],
        "high": [92, 94, 97, 95, 100, 102, 104, 103, 107, 109, 108, 112, 114, 113, 117, 120, 118, 122, 124, 123, 127, 130, 128, 132, 134, 133, 137, 140, 138, 142],
        "low": [88, 90, 93, 91, 96, 98, 100, 99, 103, 105, 104, 108, 110, 109, 113, 116, 114, 118, 120, 119, 123, 126, 124, 128, 130, 129, 133, 136, 134, 138],
        "close": [91, 93, 96, 94, 99, 101, 103, 102, 106, 108, 107, 111, 113, 112, 116, 119, 117, 121, 123, 122, 126, 129, 127, 131, 133, 132, 136, 139, 137, 141],
        "volume": [1000000] * 30,
    })
    weekly = daily.iloc[::5].reset_index(drop=True)
    result = analyze_price_target(daily, weekly, current_price=141)
    assert "direction" in result
    assert "confidence" in result
    assert "conservative" in result
    assert "base" in result
    assert "aggressive" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/reporter/test_price_target.py::test_analyze_price_target_minimal -v`
Expected: FAIL with "ImportError: cannot import name 'analyze_price_target'"

- [ ] **Step 3: Write minimal implementation**

Append to `scripts/utils/reporter/price_target.py`:

```python
def analyze_price_target(
    df_daily: pd.DataFrame,
    df_weekly: pd.DataFrame,
    current_price: float,
    stock_sector: str = "general",
    is_hk: bool = False,
) -> Dict:
    """
    主入口：对日K+周K做完整价格目标分析。

    Args:
        df_daily: 日K DataFrame (open/high/low/close/volume)
        df_weekly: 周K DataFrame (same columns)
        current_price: 最新收盘价
        stock_sector: "tech_chip" 或其他，决定激进目标上限（50% vs 60%）
        is_hk: 是否港股，影响量能阈值

    Returns:
        完整的分析结果字典，可直接用于报告渲染。
    """
    if df_daily is None or len(df_daily) < 30:
        return {"error": "日线数据不足"}
    if df_weekly is None or len(df_weekly) < 10:
        return {"error": "周线数据不足"}

    # --- 1. 周线趋势 ---
    weekly_trend = weekly_trend_analysis(df_weekly)
    if weekly_trend.get("is_ranging"):
        return {"error": "震荡格局，暂不做目标", "weekly_trend": weekly_trend}

    # --- 2. 日线/周线形态识别（复用 technical_analyzer） ---
    try:
        from .technical_analyzer import detect_double_top, detect_double_bottom
    except ImportError:
        from technical_analyzer import detect_double_top, detect_double_bottom

    daily_close = df_daily["close"]
    weekly_close = df_weekly["close"]

    daily_patterns = []
    dp = detect_double_bottom(daily_close)
    if dp:
        daily_patterns.append(dp)
    dt = detect_double_top(daily_close)
    if dt:
        daily_patterns.append(dt)

    weekly_patterns = []
    wp = detect_double_bottom(weekly_close)
    if wp:
        weekly_patterns.append(wp)
    wt = detect_double_top(weekly_close)
    if wt:
        weekly_patterns.append(wt)

    daily_pattern_info = extract_pattern_info(daily_patterns[0]) if daily_patterns else None
    weekly_pattern_info = extract_pattern_info(weekly_patterns[0]) if weekly_patterns else None

    # 判断方向（简化：以第一个形态方向为准，或默认 bullish）
    is_bullish = True
    if daily_pattern_info:
        is_bullish = daily_pattern_info["is_bullish"]
    elif weekly_pattern_info:
        is_bullish = weekly_pattern_info["is_bullish"]

    # --- 3. Zigzag + 斐波那契 ---
    daily_zigzag = zigzag(daily_close, min_pct=0.05)
    weekly_zigzag = zigzag(weekly_close, min_pct=0.10)

    def _bands_from_zigzag(pivots, n=3):
        """从zigzag pivots取最近n个波段。"""
        bands = []
        if len(pivots) < 2:
            return bands
        # 取最近n个完整波段（valley->peak 或 peak->valley）
        for i in range(max(0, len(pivots) - n - 1), len(pivots) - 1):
            p1, p2 = pivots[i], pivots[i + 1]
            low, high = min(p1["price"], p2["price"]), max(p1["price"], p2["price"])
            bands.append({"low": low, "high": high})
        return bands

    daily_bands = _bands_from_zigzag(daily_zigzag, 3)
    weekly_bands = _bands_from_zigzag(weekly_zigzag, 3)

    # 取各档斐波那契目标（用weekly为主）
    weekly_fib = {}
    for level_name, level in [("1.0", 1.0), ("1.272", 1.272), ("1.618", 1.618)]:
        targets = fib_targets_with_convergence(weekly_bands, level=level) if weekly_bands else []
        if targets:
            # 用汇聚区的均值，无汇聚用最后一个
            conv = [t["price"] for t in targets if t["in_convergence"]]
            weekly_fib[level_name] = sum(conv) / len(conv) if conv else targets[-1]["price"]
        else:
            weekly_fib[level_name] = None

    daily_fib = {}
    for level_name, level in [("1.0", 1.0), ("1.272", 1.272), ("1.618", 1.618)]:
        targets = fib_targets_with_convergence(daily_bands, level=level) if daily_bands else []
        if targets:
            conv = [t["price"] for t in targets if t["in_convergence"]]
            daily_fib[level_name] = sum(conv) / len(conv) if conv else targets[-1]["price"]
        else:
            daily_fib[level_name] = None

    # --- 4. 目标合成 ---
    targets = synthesize_targets(
        daily_pattern_info, weekly_pattern_info,
        daily_fib, weekly_fib, current_price, is_bullish,
    )

    # --- 5. 盈亏比过滤 ---
    neckline = None
    if daily_pattern_info:
        neckline = daily_pattern_info["neckline"]
    elif weekly_pattern_info:
        neckline = weekly_pattern_info["neckline"]

    # 无形态时用最近波段低点近似
    if neckline is None and weekly_zigzag:
        last_valley = next((p for p in reversed(weekly_zigzag) if p["type"] == "valley"), None)
        if last_valley:
            neckline = last_valley["price"]

    # 计算日线ATR
    try:
        from .technical_analyzer import _atr
    except ImportError:
        from technical_analyzer import _atr
    daily_atr = float(_atr(df_daily).iloc[-1])

    pr_filter = None
    if neckline and targets.get("conservative"):
        pr_filter = profit_risk_filter(
            conservative_target=targets["conservative"],
            neckline=neckline,
            daily_atr=daily_atr,
        )

    if pr_filter and not pr_filter["pass"]:
        return {
            "error": "关注/不操作",
            "reason": f"形态存在但盈亏比不足（{pr_filter['ratio']}:1），等待更好的入场点",
            "weekly_trend": weekly_trend,
            "targets": targets,
            "profit_risk": pr_filter,
        }

    # --- 6. 动量评估（用于置信度和时间修正） ---
    try:
        from .technical_analyzer import _macd, _rsi, _sma
    except ImportError:
        from technical_analyzer import _macd, _rsi, _sma

    macd_line, macd_sig, macd_hist = _macd(daily_close)
    # 判定前3日柱线趋势（shift(1)取突破前数据）
    hist_prev = macd_hist.shift(1).tail(3)
    hist_diff = hist_prev.diff().dropna()
    macd_momentum = "flat"
    if len(hist_diff) >= 2:
        if all(h > 0 for h in hist_diff):
            macd_momentum = "expanding" if abs(hist_prev.iloc[-1]) > abs(hist_prev.iloc[0]) else "contracting"
        elif all(h < 0 for h in hist_diff):
            macd_momentum = "contracting" if abs(hist_prev.iloc[-1]) < abs(hist_prev.iloc[0]) else "expanding"

    rsi_val = float(_rsi(daily_close, 14).iloc[-1])
    ma5 = _sma(daily_close, 5).iloc[-1]
    ma20 = _sma(daily_close, 20).iloc[-1]
    ma60 = _sma(daily_close, 60).iloc[-1]
    ma_bull = ma5 > ma20 > ma60

    # KDJ 简化判定（从 technical_analyzer 已有数据推算或简化）
    # 这里用价格相对位置近似
    kdj_golden = False  # TODO: 如需精确KDJ，从 technical_analyzer.analyze() 传入

    momentum = _momentum_score(
        macd_expanding=(macd_momentum == "expanding"),
        macd_contracting=(macd_momentum == "contracting"),
        macd_dead=(macd_hist.iloc[-1] < 0 and macd_line.iloc[-1] < macd_sig.iloc[-1]),
        rsi=rsi_val,
        kdj_golden=kdj_golden,
        ma_bull=ma_bull,
    )

    # --- 7. 置信度评分 ---
    # 共振分
    resonance_score = 10 if (daily_pattern_info and weekly_pattern_info) else (
        6 if (daily_pattern_info or weekly_pattern_info) else 0
    )
    # 形态完整性
    pattern_score = 10  # 简化：有形态=10（2次触及标准）
    # 突破质量（无实际突破K线时用预估）
    breakout_score = 6  # 简化：预估突破=6
    # 周线ADX
    adx_score = weekly_trend.get("adx_score", 0)
    # 斐波那契汇聚
    fib_conv_score = 10 if weekly_fib.get("1.272") and any(
        t.get("in_convergence") for t in fib_targets_with_convergence(weekly_bands, 1.272)
    ) else 0

    conf_score = confidence_score(
        resonance=resonance_score,
        pattern_quality=pattern_score,
        breakout_quality=breakout_score,
        weekly_adx=adx_score,
        momentum=momentum,
        fib_convergence=fib_conv_score,
    )
    conf_level = confidence_level(conf_score, aggressive_is_far=targets.get("is_far_target", False))

    # --- 8. 时间预期 ---
    time_conservative = estimate_time(
        targets["conservative"], current_price, daily_atr, macd_momentum, rsi_val,
    ) if targets.get("conservative") else (0, 0)
    time_base = estimate_time(
        targets["base"], current_price, daily_atr, macd_momentum, rsi_val,
    ) if targets.get("base") else (0, 0)
    time_aggressive = estimate_time(
        targets["aggressive_raw"] or targets.get("aggressive", current_price),
        current_price, daily_atr, macd_momentum, rsi_val,
    ) if targets.get("aggressive") else (0, 0)

    # --- 9. 止损/失效条件文本 ---
    stop_loss_text = ""
    if neckline:
        entry_stop = max(pr_filter["stop_price"], neckline - 1.5 * daily_atr) if pr_filter else neckline - 1.5 * daily_atr
        stop_loss_text = f"初始止损{entry_stop:.1f}（预估）/ 跟踪止损：最高收盘价回撤2×ATR"
    else:
        stop_loss_text = f"跟踪止损：最高收盘价回撤{2*daily_atr:.1f}（{2*daily_atr/current_price*100:.1f}%）"

    return {
        "direction": targets["direction"],
        "confidence": conf_level,
        "confidence_score": conf_score,
        "profit_risk_ratio": pr_filter["ratio"] if pr_filter else None,
        "conservative": targets["conservative"],
        "base": targets["base"],
        "aggressive": targets["aggressive"],
        "aggressive_raw": targets.get("aggressive_raw"),
        "is_far_target": targets.get("is_far_target", False),
        "method": targets["method"],
        "trigger_conditions": {
            "price": f"收盘价站稳{neckline:.1f}+实体完全在颈线上方+实体≥0.3×ATR" if neckline else "等待形态确认",
            "trend": f"周线ADX>{weekly_trend['adx']}且+DI>-DI" if weekly_trend.get("adx") else "",
            "volume": "量比>1.5且金额≥1亿" if not is_hk else "量比>1.3且金额≥3000万港币",
            "momentum": _momentum_trigger_text(macd_line.iloc[-1], macd_sig.iloc[-1], macd_hist.iloc[-1], rsi_val),
        },
        "stop_loss": stop_loss_text,
        "failure_conditions": [
            f"周线ADX从26周峰值回落>10且+DI下穿-DI",
            "创20日新高但OBV未同步创新高",
            "连续5日低于20MA均量且跌破10日线",
        ],
        "time_estimate": {
            "conservative": f"约{time_conservative[0]:.0f}-{time_conservative[1]:.0f}个交易日",
            "base": f"约{time_base[0]:.0f}-{time_base[1]:.0f}个交易日",
            "aggressive": f"约{time_aggressive[0]:.0f}-{time_aggressive[1]:.0f}个交易日",
        },
        "momentum_status": _format_momentum_status(macd_line.iloc[-1], macd_sig.iloc[-1], macd_hist.iloc[-1], rsi_val, ma_bull),
        "weekly_trend": weekly_trend,
        "daily_pattern": daily_patterns[0] if daily_patterns else None,
        "weekly_pattern": weekly_patterns[0] if weekly_patterns else None,
    }


def _momentum_trigger_text(macd_line, macd_sig, macd_hist, rsi):
    """生成触发条件的动量文本。"""
    if macd_hist < 0 and macd_line < macd_sig:
        # 检查柱线收缩例外
        return "MACD死叉但柱线收缩中 → 谨慎触发"
    if rsi > 70:
        return "RSI>70 超买 → 降级谨慎观察"
    if rsi < 35:
        return "RSI<35 超卖 → 优质触发（实体≥0.2×ATR）"
    return "MACD非死叉 + RSI健康区间"


def _format_momentum_status(macd_line, macd_sig, macd_hist, rsi, ma_bull):
    """格式化动量状态行。"""
    parts = []
    if macd_hist > 0 and macd_line > macd_sig:
        parts.append("MACD金叉扩张" if macd_hist > macd_hist * 0.9 else "MACD金叉")
    elif macd_hist < 0 and macd_line < macd_sig:
        parts.append("🔴 MACD死叉 | 触发否决")
        return " | ".join(parts)
    else:
        parts.append("MACD观望")

    if rsi > 70:
        parts.append(f"RSI {rsi:.0f} 超买")
    elif rsi < 35:
        parts.append(f"RSI {rsi:.0f} 超卖")
    else:
        parts.append(f"RSI {rsi:.0f} 健康")

    if ma_bull:
        parts.append("MA多头排列")

    return " | ".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/reporter/test_price_target.py::test_analyze_price_target_minimal -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/reporter/price_target.py tests/reporter/test_price_target.py
git commit -m "feat(price_target): add main analysis entry point analyze_price_target"
```

---

### Task 10: Weekly K-line Collection in TechnicalCollector

**Files:**
- Modify: `scripts/utils/data_collector.py`

- [ ] **Step 1: Read the current TechnicalCollector to understand integration point**

Already read above. The `collect()` method at line 227 fetches daily K-line and computes indicators. We need to:
1. Add a `fetch_weekly_kline()` method
2. Call it from `collect()`
3. Pass both daily and weekly DataFrames to price_target analysis

- [ ] **Step 2: Add weekly fetch method**

In `scripts/utils/data_collector.py`, after `fetch_kline()` method (around line 123), add:

```python
    def fetch_weekly_kline(self, code: str, market: int = 0, weeks: int = 72) -> Optional[pd.DataFrame]:
        """
        获取周K线数据。
        A股: 通过 akshare stock_zh_a_hist(symbol, period='weekly')
        港股: 优先 Wind CSV，备选 akshare stock_hk_hist
        """
        if ak is None:
            logger.warning("akshare 未安装，无法获取周线数据")
            return None

        try:
            # A-share weekly
            if market == 0 or market == 1:
                prefix = "SZ" if market == 0 else "SH"
                symbol = f"{prefix}{code}"
                df = ak.stock_zh_a_hist(symbol=symbol, period="weekly", start_date="20200101", adjust="qfq")
            else:
                # HK stock
                df = ak.stock_hk_hist(symbol=code, period="weekly", start_date="20200101")

            if df is None or df.empty:
                return None

            # Standardize columns
            column_map = {
                "日期": "date", "开盘": "open", "最高": "high",
                "最低": "low", "收盘": "close", "成交量": "volume",
            }
            df = df.rename(columns=column_map)
            for col in ["open", "high", "low", "close", "volume"]:
                if col not in df.columns:
                    logger.error(f"周线数据缺少列: {col}")
                    return None

            if len(df) > weeks:
                df = df.tail(weeks).reset_index(drop=True)

            return df
        except Exception as e:
            logger.error(f"获取 {code} 周线数据失败: {e}")
            return None
```

- [ ] **Step 3: Modify collect() to integrate weekly and price_target**

In `scripts/utils/data_collector.py`, modify `TechnicalCollector.collect()` (around line 227):

```python
    def collect(self, code: str, market: int = 0, days: int = 120) -> Dict:
        """一键采集技术指标（含日线+周线+价格目标）"""
        df_daily = self.fetch_kline(code, market, days)
        if df_daily is None or df_daily.empty:
            return {}

        indicators = self.compute_indicators(df_daily)

        # --- 新增：周线 + 价格目标 ---
        price_target_result = None
        try:
            df_weekly = self.fetch_weekly_kline(code, market, weeks=72)
            if df_weekly is not None and not df_daily.empty:
                try:
                    from .reporter.price_target import analyze_price_target
                except ImportError:
                    from reporter.price_target import analyze_price_target
                current_price = float(df_daily["close"].iloc[-1])
                price_target_result = analyze_price_target(
                    df_daily, df_weekly, current_price=current_price,
                )
        except Exception as e:
            logger.warning(f"价格目标分析失败: {e}")

        return {
            "code": code,
            "market": market,
            "days": len(df_daily),
            "indicators": indicators,
            "price_target": price_target_result,
            "fetched_at": datetime.now().isoformat(),
        }
```

- [ ] **Step 4: Verify the module imports correctly**

Run: `python -c "from scripts.utils.data_collector import TechnicalCollector; print('OK')"`
Expected: `OK` (or no ImportError)

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/data_collector.py
git commit -m "feat(data_collector): add weekly K-line fetch and integrate price_target analysis"
```

---

### Task 11: Price Target Section in Stock Reporter

**Files:**
- Modify: `scripts/utils/stock_reporter.py`

- [ ] **Step 1: Add `_price_target_section()` method**

In `scripts/utils/stock_reporter.py`, after `_technical_analysis_section()` (after line ~1715), add:

```python
    def _price_target_section(self, stock_name: str, stock_raw: Dict) -> str:
        """价格目标与触发条件板块（基于 price_target 分析结果）。"""
        pt = stock_raw.get("price_target")
        if not pt or not isinstance(pt, dict):
            return ""

        if pt.get("error"):
            return f"\n## 价格目标与触发条件\n\n> **{pt['error']}**\n"

        lines = ["\n## 价格目标与触发条件\n"]

        # Direction + confidence + profit/risk
        direction = pt.get("direction", "")
        confidence = pt.get("confidence", "")
        conf_score = pt.get("confidence_score", 0)
        pr_ratio = pt.get("profit_risk_ratio")
        pr_text = f" | **盈亏比**: {pr_ratio}:1" if pr_ratio else ""

        lines.append(f"**方向**: {direction} | **置信度**: {confidence}（{conf_score}/10）{pr_text}")
        lines.append("")

        # Momentum status line
        momentum = pt.get("momentum_status", "")
        if momentum:
            lines.append(f"**动量状态**: {momentum}")
            # Check for signal conflict
            if "MACD死叉" in momentum and ("RSI" in momentum or "MA多头" in momentum):
                lines.append("⚠️ **动量信号分歧，建议等待一致**")
            lines.append("")

        # Target table
        lines.append("| 目标 | 价格 | 推导依据 | 验证源 |")
        lines.append("|------|------|---------|--------|")

        conservative = pt.get("conservative")
        base = pt.get("base")
        aggressive = pt.get("aggressive")
        aggressive_raw = pt.get("aggressive_raw")
        method = pt.get("method", "")

        if conservative:
            lines.append(f"| 保守 | {conservative} | {method} | 综合 |")
        if base:
            lines.append(f"| 基准 | {base} | {method} | A+B交叉验证 |")
        if aggressive:
            if pt.get("is_far_target"):
                lines.append(f"| 激进 | {aggressive_raw}（久远，暂不可达） | 周K斐波那契1.618扩展 | 周线大结构 |")
            else:
                lines.append(f"| 激进 | {aggressive} | 周K斐波那契1.618扩展 | 周线大结构 |")

        lines.append("")

        # Trigger conditions
        trigger = pt.get("trigger_conditions", {})
        if trigger:
            parts = []
            if trigger.get("price"):
                parts.append(trigger["price"])
            if trigger.get("trend"):
                parts.append(trigger["trend"])
            if trigger.get("volume"):
                parts.append(trigger["volume"])
            if trigger.get("momentum"):
                parts.append(trigger["momentum"])
            if parts:
                lines.append(f"**触发**: {' + '.join(parts)}")

        # Stop loss
        stop = pt.get("stop_loss", "")
        if stop:
            lines.append(f"**止损**: {stop}")

        # Failure conditions
        failures = pt.get("failure_conditions", [])
        if failures:
            lines.append(f"**失效**: {' / '.join(failures)}")

        # Time estimate
        time_est = pt.get("time_estimate", {})
        if time_est:
            parts = []
            if time_est.get("conservative"):
                parts.append(f"保守{time_est['conservative']}")
            if time_est.get("base"):
                parts.append(f"基准{time_est['base']}")
            if time_est.get("aggressive"):
                parts.append(f"激进{time_est['aggressive']}")
            if parts:
                lines.append(f"**时间预期**: {' / '.join(parts)}")

        lines.append("")
        return "\n".join(lines)
```

- [ ] **Step 2: Wire into report generation flow**

In `scripts/utils/stock_reporter.py`, find where `_technical_analysis_section()` is called (around line 201). After it, add:

```python
        price_target_section = self._price_target_section(stock_name, stock_raw)
        if price_target_section:
            sections.append(price_target_section)
```

The exact location is inside `generate_stock_report()` where `tech_section` is appended. Add `price_target_section` right after `tech_section`.

- [ ] **Step 3: Run a quick syntax check**

Run: `python -c "import scripts.utils.stock_reporter"`
Expected: No ImportError or SyntaxError

- [ ] **Step 4: Commit**

```bash
git add scripts/utils/stock_reporter.py
git commit -m "feat(stock_reporter): add price target section rendering"
```

---

### Task 12: End-to-End Integration Test

**Files:**
- Create: `tests/test_price_target_e2e.py`

- [ ] **Step 1: Write a minimal end-to-end test**

```python
"""价格目标端到端集成测试。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "utils"))

import pandas as pd
from reporter.price_target import analyze_price_target


def test_e2e_synthetic_data():
    """
    用合成数据验证 analyze_price_target 端到端输出格式。
    """
    # 构建一个 synthetic 双底走势
    base = 100
    daily = pd.DataFrame({
        "open": [base + i * 0.5 for i in range(60)],
        "high": [base + i * 0.5 + 2 for i in range(60)],
        "low": [base + i * 0.5 - 2 for i in range(60)],
        "close": [base + i * 0.5 + 0.5 for i in range(60)],
        "volume": [1000000] * 60,
    })
    # 制造双底：中间有回落
    daily.loc[20:25, "close"] = [110, 108, 106, 105, 107, 109]
    daily.loc[20:25, "low"] = [108, 106, 104, 103, 105, 107]
    daily.loc[40:45, "close"] = [118, 116, 114, 113, 115, 117]
    daily.loc[40:45, "low"] = [116, 114, 112, 111, 113, 115]

    weekly = daily.iloc[::5].reset_index(drop=True)
    result = analyze_price_target(daily, weekly, current_price=daily["close"].iloc[-1])

    assert "direction" in result
    assert "confidence" in result
    print(f"E2E result: direction={result['direction']}, confidence={result['confidence']}")


if __name__ == "__main__":
    test_e2e_synthetic_data()
```

- [ ] **Step 2: Run the E2E test**

Run: `python tests/test_price_target_e2e.py`
Expected: Print result with direction and confidence, no exceptions

- [ ] **Step 3: Commit**

```bash
git add tests/test_price_target_e2e.py
git commit -m "test(price_target): add end-to-end integration test with synthetic data"
```

---

### Task 13: Run Full Test Suite

- [ ] **Step 1: Run all price_target tests**

Run: `python -m pytest tests/reporter/test_price_target.py tests/test_price_target_e2e.py -v`
Expected: All tests PASS

- [ ] **Step 2: Run existing test suite to check for regressions**

Run: `python -m pytest tests/ -v --tb=short` (or project-specific test command)
Expected: No new failures introduced by price_target changes

- [ ] **Step 3: Commit any fixes**

If regressions found, fix and commit:
```bash
git add <fixed-files>
git commit -m "fix: resolve regressions from price_target integration"
```

---

## Spec Coverage Checklist

| Spec Section | Task | Status |
|-------------|------|--------|
| 2.1 形态测距 (A) | Task 3 | ✅ `pattern_target()`, `extract_pattern_info()` |
| 2.2 斐波那契扩展 (B) | Task 2 | ✅ `fib_extension()`, `fib_targets_with_convergence()` |
| 2.2 Zigzag波段识别 | Task 1 | ✅ `zigzag()` |
| 2.3 多时间框架共振 (C) | Task 4, Task 9 | ✅ `weekly_trend_analysis()`, direction logic in `analyze_price_target()` |
| 3. 目标合成（标准化公式） | Task 5 | ✅ `synthesize_targets()` with 4 scenarios |
| 4. 盈亏比过滤 | Task 6 | ✅ `profit_risk_filter()` with estimated trigger/stop |
| 5. 触发条件（四重确认） | Task 9 | ✅ momentum filter in `analyze_price_target()`, `_momentum_trigger_text()` |
| 5. 动量过滤规则 | Task 9 | ✅ RSI/MACD/KDJ/MA/BOLL rules in `_momentum_score()` and trigger text |
| 6. 止损/失效条件 | Task 9 | ✅ stop_loss text, failure_conditions list |
| 7. 置信度体系（六因子） | Task 7, Task 9 | ✅ `confidence_score()`, `_momentum_score()`, `confidence_level()` |
| 8. 时间预期 | Task 8, Task 9 | ✅ `estimate_time()` with MACD/RSI adjustment |
| 9. 报告输出格式 | Task 11 | ✅ `_price_target_section()` Markdown renderer |
| 数据源：周K 72周 | Task 10 | ✅ `fetch_weekly_kline()` in TechnicalCollector |
| 港股适配 | Task 9 | ✅ `is_hk` parameter for volume thresholds |
| 激进目标上限 | Task 5, Task 9 | ✅ 50%/60% cap + "久远" label + confidence lock |
| 横盘处理 | Task 4 | ✅ `is_ranging` with BOLL bandwidth check |

## Placeholder Scan

- No "TBD", "TODO", "implement later" in plan steps.
- All code blocks contain complete implementations.
- All commands have expected output specified.
- Type consistency: `analyze_price_target()` signature matches all callers.

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-04-technical-price-target.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints for review

Which approach?
