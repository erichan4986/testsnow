# 高级技术分析 Phase 3 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Phase 2 中期趋势提醒系统基础上，新增趋势结构健康度、通道/箱体识别、底部区域观察、分批观察框架、市场/行业/主题共振分析。

**Architecture:** 复用 Phase 2 的趋势状态机对指数做趋势判定；结构识别放在 `technical_structure.py`；策略信号放在 `technical_strategy.py`；共振放在 `technical_resonance.py`；渲染层只负责展示不做判断。

**Tech Stack:** Python 3.11, pandas, numpy, mootdx, pytest

---

## 文件结构

| 文件 | 动作 | 说明 |
|------|------|------|
| `scripts/utils/reporter/technical_structure.py` | 修改 | 新增 `detect_trend_structure_health`、`detect_channel_or_box_structure`、`evaluate_bottoming_region` |
| `scripts/utils/reporter/technical_strategy.py` | 新建 | `evaluate_dart_strategy` |
| `scripts/utils/reporter/technical_resonance.py` | 修改 | 新增 `evaluate_market_resonance`、`analyze_index_trend` |
| `scripts/utils/reporter/data_fetcher.py` | 修改 | 新增 `fetch_index_bars` |
| `config/market_index_map.json` | 新建 | 关注池股票→指数映射 |
| `scripts/utils/reporter/technical_analyzer.py` | 修改 | 集成 5 个新模块到 `_resonance` |
| `scripts/utils/reporter/sections/technical_renderer.py` | 修改 | 渲染 5 个新字段 |
| `tests/reporter/test_phase3_structure.py` | 新建 | 结构健康度 + 通道/箱体测试 |
| `tests/reporter/test_phase3_bottom_strategy.py` | 新建 | 底部观察 + 飞镖策略测试 |
| `tests/reporter/test_market_resonance.py` | 新建 | 共振分析 + 映射测试 |
| `tests/reporter/test_phase3_integration.py` | 新建 | Renderer + 集成测试 |

---

## Task 1：趋势结构健康度 `detect_trend_structure_health`

**Files:**
- Modify: `scripts/utils/reporter/technical_structure.py`
- Test: `tests/reporter/test_phase3_structure.py`

- [ ] **Step 1: Write the failing test**

```python
import pandas as pd
import numpy as np
from scripts.utils.reporter.technical_structure import (
    detect_trend_structure_health,
    detect_channel_or_box_structure,
)


def test_higher_lows():
    """低点逐步抬升"""
    dates = pd.date_range("2026-04-01", periods=60, freq="B")
    prices = np.ones(60) * 200
    # 构造3个低点：160, 170, 180，中间有间隔
    prices[10] = 160; prices[11] = 165; prices[12] = 170
    prices[30] = 170; prices[31] = 175; prices[32] = 180
    prices[50] = 180; prices[51] = 185; prices[52] = 190
    df = pd.DataFrame({
        "date": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices, "volume": np.ones(60) * 10000,
    })
    result = detect_trend_structure_health(df)
    assert result["state"] == "低点抬升"
    assert result["is_healthy"] is True
    assert result["last_low_relation"] == "higher"
    assert len(result["swing_lows"]) >= 2


def test_lower_lows():
    """低点逐步下移"""
    dates = pd.date_range("2026-04-01", periods=60, freq="B")
    prices = np.ones(60) * 200
    prices[10] = 190; prices[30] = 180; prices[50] = 170
    df = pd.DataFrame({
        "date": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices, "volume": np.ones(60) * 10000,
    })
    result = detect_trend_structure_health(df)
    assert result["state"] == "低点下移"
    assert result["is_healthy"] is False
    assert result["last_low_relation"] == "lower"


def test_flat_lows():
    """低点差异小于 tolerance"""
    dates = pd.date_range("2026-04-01", periods=60, freq="B")
    prices = np.ones(60) * 200
    prices[10] = 180; prices[30] = 180.5; prices[50] = 181
    df = pd.DataFrame({
        "date": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices, "volume": np.ones(60) * 10000,
    })
    result = detect_trend_structure_health(df, tolerance_pct=0.01)
    assert result["state"] == "低点走平"
    assert result["is_healthy"] is None


def test_insufficient_swings():
    """swing lows 不足 2 个"""
    dates = pd.date_range("2026-04-01", periods=10, freq="B")
    prices = np.ones(10) * 200
    df = pd.DataFrame({
        "date": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices, "volume": np.ones(10) * 10000,
    })
    result = detect_trend_structure_health(df)
    assert result["state"] == "无法判断"
    assert result["missing"] != []


def test_last_bar_not_confirmed():
    """最近一根 K 线不能作为 confirmed low"""
    dates = pd.date_range("2026-04-01", periods=60, freq="B")
    prices = np.ones(60) * 200
    prices[-1] = 150  # 最低点在最后，但无右侧确认
    df = pd.DataFrame({
        "date": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices, "volume": np.ones(60) * 10000,
    })
    result = detect_trend_structure_health(df)
    # 最后的低点不应被计入
    if result["swing_lows"]:
        last_swing_date = pd.Timestamp(result["swing_lows"][-1]["date"])
        assert last_swing_date != dates[-1]


def test_short_gap_lowers_confidence():
    """间隔 3 天的低点降低置信度"""
    dates = pd.date_range("2026-04-01", periods=60, freq="B")
    prices = np.ones(60) * 200
    prices[10] = 160
    prices[13] = 170  # 只隔3天
    prices[30] = 180
    df = pd.DataFrame({
        "date": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices, "volume": np.ones(60) * 10000,
    })
    result = detect_trend_structure_health(df, min_gap_days=3)
    # 只要存在间隔3天的对，confidence 不应为"高"
    if len(result.get("swing_lows", [])) >= 2:
        assert result["confidence"] != "高"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/reporter/test_phase3_structure.py -v`
Expected: `FAILED test_phase3_structure.py::test_higher_lows - NameError: name 'detect_trend_structure_health' is not defined`

- [ ] **Step 3: Write minimal implementation**

在 `scripts/utils/reporter/technical_structure.py` 末尾追加：

```python
def detect_trend_structure_health(
    df_daily: pd.DataFrame,
    lookback: int = 60,
    swing_left: int = 2,
    swing_right: int = 2,
    min_gap_days: int = 3,
    tolerance_pct: float = 0.01,
    atr_multiplier: float = 0.5,
) -> dict:
    """检测趋势结构健康度：回调低点是否抬升/走平/下移。"""
    if df_daily is None or len(df_daily) < lookback:
        return {
            "state": "无法判断",
            "is_healthy": None,
            "confidence": "低",
            "swing_lows": [],
            "last_low_relation": "unknown",
            "evidence": [],
            "missing": [f"数据不足，需要{lookback}根K线，实际{len(df_daily) if df_daily is not None else 0}根"],
            "action_hint": "证据不足，继续观察",
        }

    df = df_daily.iloc[-lookback:].copy().reset_index(drop=True)
    lows = df["low"].values
    dates = df["date"] if "date" in df.columns else pd.Series(df.index)

    # 计算 ATR（简化版，用 high-low）
    atr = (df["high"] - df["low"]).rolling(14).mean().iloc[-1]
    threshold = max(tolerance_pct, atr_multiplier * (atr / df["close"].iloc[-1] if df["close"].iloc[-1] != 0 else 0))

    # 找 confirmed swing lows
    swing_lows = []
    n = len(df)
    for i in range(swing_left, n - swing_right):
        is_low = True
        for j in range(1, swing_left + 1):
            if lows[i - j] <= lows[i]:
                is_low = False; break
        for j in range(1, swing_right + 1):
            if lows[i + j] <= lows[i]:
                is_low = False; break
        if is_low:
            swing_lows.append({"idx": i, "price": float(lows[i]), "date": str(dates.iloc[i]) if hasattr(dates.iloc[i], 'strftime') else str(dates.iloc[i])})

    if len(swing_lows) < 2:
        return {
            "state": "无法判断",
            "is_healthy": None,
            "confidence": "低",
            "swing_lows": [{"date": s["date"], "price": s["price"]} for s in swing_lows],
            "last_low_relation": "unknown",
            "evidence": [],
            "missing": ["confirmed swing lows 不足2个"],
            "action_hint": "证据不足，继续观察",
        }

    # 过滤间隔不足的（只保留间隔 >= min_gap_days 的）
    filtered = [swing_lows[0]]
    short_gaps = []
    for s in swing_lows[1:]:
        gap = s["idx"] - filtered[-1]["idx"]
        if gap >= min_gap_days:
            filtered.append(s)
        else:
            short_gaps.append(gap)
    swing_lows = filtered

    if len(swing_lows) < 2:
        return {
            "state": "无法判断",
            "is_healthy": None,
            "confidence": "低",
            "swing_lows": [{"date": s["date"], "price": s["price"]} for s in swing_lows],
            "last_low_relation": "unknown",
            "evidence": [],
            "missing": ["confirmed swing lows 间隔过短，不足2个有效低点"],
            "action_hint": "证据不足，继续观察",
        }

    # 比较最后两个低点
    prev = swing_lows[-2]["price"]
    last = swing_lows[-1]["price"]
    diff = (last - prev) / prev

    if diff > threshold:
        state = "低点抬升"
        is_healthy = True
        last_rel = "higher"
    elif diff < -threshold:
        state = "低点下移"
        is_healthy = False
        last_rel = "lower"
    else:
        state = "低点走平"
        is_healthy = None
        last_rel = "flat"

    # 置信度
    effective_gaps = [
        swing_lows[i]["idx"] - swing_lows[i - 1]["idx"]
        for i in range(1, len(swing_lows))
    ]
    min_effective_gap = min(effective_gaps) if effective_gaps else None

    if min_effective_gap is not None and min_effective_gap < 5:
        confidence = "中" if len(swing_lows) >= 3 else "低"
    elif len(swing_lows) >= 3:
        confidence = "高"
    else:
        confidence = "中"

    evidence = [f"最近两个回调低点：{prev:.2f} → {last:.2f}"]
    if state == "低点抬升":
        evidence.append("回调低点逐步抬高，上升趋势结构健康")
    elif state == "低点下移":
        evidence.append("回调低点下移，结构转弱")

    return {
        "state": state,
        "is_healthy": is_healthy,
        "confidence": confidence,
        "swing_lows": [{"date": s["date"], "price": s["price"]} for s in swing_lows],
        "last_low_relation": last_rel,
        "evidence": evidence,
        "missing": [],
        "action_hint": "结构健康，回调低点抬升" if is_healthy else ("结构转弱，低点下移" if is_healthy is False else "证据不足，继续观察"),
    }
```

同时更新 `__all__`：

```python
__all__ = [
    "compute_bias", "compute_boll_state", "compute_candle_features",
    "compute_ma_direction", "resample_daily_to_weekly",
    "compute_weekly_trend", "find_support_resistance",
    "evaluate_sr_transformation", "detect_trend_structure_health",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/reporter/test_phase3_structure.py::test_higher_lows -v`
Expected: PASS

Run: `pytest tests/reporter/test_phase3_structure.py -v`
Expected: 6/6 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/reporter/technical_structure.py tests/reporter/test_phase3_structure.py
git commit -m "feat(technical): add trend structure health detection"
```

---

## Task 2：通道/箱体识别 `detect_channel_or_box_structure`

**Files:**
- Modify: `scripts/utils/reporter/technical_structure.py`
- Modify: `tests/reporter/test_phase3_structure.py`

- [ ] **Step 1: Write the failing test**

在 `tests/reporter/test_phase3_structure.py` 中追加：

```python

def test_horizontal_box():
    """水平箱体"""
    dates = pd.date_range("2026-04-01", periods=30, freq="B")
    np.random.seed(42)
    closes = np.random.uniform(240, 260, 30)
    df = pd.DataFrame({
        "date": dates,
        "open": closes - 1,
        "high": closes + 2,
        "low": closes - 2,
        "close": closes,
        "volume": np.ones(30) * 10000,
    })
    result = detect_channel_or_box_structure(df)
    assert result["state"] == "水平箱体"
    assert result["position"] in ["中部", "接近上轨", "接近下轨"]


def test_ascending_channel():
    """上升通道：高低点均抬升"""
    dates = pd.date_range("2026-04-01", periods=40, freq="B")
    base = np.linspace(200, 250, 40)
    wave = np.sin(np.arange(40) / 2.0) * 6
    closes = base + wave
    highs = closes + 5
    lows = closes - 5
    df = pd.DataFrame({
        "date": dates,
        "open": closes - 1,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": np.ones(40) * 10000,
    })
    result = detect_channel_or_box_structure(df, window=30)
    assert result["state"] == "上升通道"


def test_breakout_above():
    """向上突破"""
    dates = pd.date_range("2026-04-01", periods=30, freq="B")
    closes = np.ones(30) * 250
    closes[-3:] = 265  # 连续3日站上上轨
    df = pd.DataFrame({
        "date": dates,
        "open": closes - 1,
        "high": closes + 2,
        "low": closes - 2,
        "close": closes,
        "volume": np.ones(30) * 10000,
    })
    result = detect_channel_or_box_structure(df, confirm_days=2)
    assert result["breakout_status"] in ["向上突破待确认", "向上突破确认"]


def test_no_channel_steep_slope():
    """斜率差过大，不识别为通道"""
    dates = pd.date_range("2026-04-01", periods=30, freq="B")
    base = np.linspace(200, 250, 30)
    highs = base + np.linspace(0, 50, 30)
    lows = base + np.linspace(0, 5, 30)
    df = pd.DataFrame({
        "date": dates,
        "open": base,
        "high": highs,
        "low": lows,
        "close": base,
        "volume": np.ones(30) * 10000,
    })
    result = detect_channel_or_box_structure(df)
    assert result["state"] == "无明显通道"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/reporter/test_phase3_structure.py -v`
Expected: `FAILED test_phase3_structure.py::test_horizontal_box - NameError: name 'detect_channel_or_box_structure' is not defined`

- [ ] **Step 3: Write minimal implementation**

在 `scripts/utils/reporter/technical_structure.py` 末尾追加：

```python
def detect_channel_or_box_structure(
    df_daily: pd.DataFrame,
    window: int = 20,
    confirm_days: int = 2,
    slope_tolerance_pct: float = 0.005,
) -> dict:
    """识别水平箱体、上升通道、下降通道，以及突破/跌破状态。"""
    if df_daily is None or len(df_daily) < window + confirm_days + 5:
        return {
            "state": "无明显通道",
            "confidence": "低",
            "upper": None,
            "lower": None,
            "position": "未知",
            "breakout_status": "未突破",
            "evidence": [],
            "missing": [f"数据不足，需要{window + confirm_days + 5}根K线"],
            "action_hint": "区间内观望",
        }

    # 用 channel_base 拟合通道，confirm_bars 检测突破，防止当前 K 线污染
    channel_base = df_daily.iloc[-window - confirm_days:-confirm_days].copy().reset_index(drop=True)
    confirm_bars = df_daily.iloc[-confirm_days:].copy()

    highs = channel_base["high"].values
    lows = channel_base["low"].values
    n = len(channel_base)

    # 找 confirmed swing highs/lows（简化：用局部极值）
    swing_highs = []
    swing_lows = []
    for i in range(2, n - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            swing_highs.append((i, float(highs[i])))
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            swing_lows.append((i, float(lows[i])))

    # 拟合上下轨
    def _fit_slope(points):
        if len(points) < 2:
            return None, None, None
        x = np.array([p[0] for p in points])
        y = np.array([p[1] for p in points])
        slope, intercept = np.polyfit(x, y, 1)
        avg_price = y.mean()
        norm_slope = slope / avg_price if avg_price != 0 else 0.0
        return slope, intercept, norm_slope

    upper_slope, upper_intercept, upper_norm_slope = _fit_slope(swing_highs)
    lower_slope, lower_intercept, lower_norm_slope = _fit_slope(swing_lows)

    # swing 点不足时降级用分位数
    use_quantile = upper_slope is None or lower_slope is None
    if use_quantile:
        upper = float(channel_base["high"].quantile(0.9))
        lower = float(channel_base["low"].quantile(0.1))
        upper_slope = 0.0
        lower_slope = 0.0
    else:
        upper = upper_intercept + upper_slope * (n - 1)
        lower = lower_intercept + lower_slope * (n - 1)

    # 判断通道类型
    norm_diff = abs(upper_norm_slope - lower_norm_slope) if not use_quantile else 0.0

    if norm_diff > 0.01:
        return {
            "state": "无明显通道",
            "confidence": "低",
            "upper": round(upper, 2) if upper else None,
            "lower": round(lower, 2) if lower else None,
            "position": "未知",
            "breakout_status": "未突破",
            "evidence": ["上下轨斜率差异过大，不构成平行通道"],
            "missing": [],
            "action_hint": "区间内观望",
        }

    # 判断方向
    if use_quantile or (abs(upper_norm_slope) < slope_tolerance_pct and abs(lower_norm_slope) < slope_tolerance_pct):
        state = "水平箱体"
        conf = "高" if not use_quantile else "中"
    elif upper_norm_slope > 0 and lower_norm_slope > 0:
        state = "上升通道"
        conf = "高" if norm_diff <= slope_tolerance_pct else "低"
    elif upper_norm_slope < 0 and lower_norm_slope < 0:
        state = "下降通道"
        conf = "高" if norm_diff <= slope_tolerance_pct else "低"
    else:
        state = "无明显通道"
        conf = "低"

    if state == "无明显通道":
        return {
            "state": state, "confidence": conf,
            "upper": round(upper, 2), "lower": round(lower, 2),
            "position": "未知", "breakout_status": "未突破",
            "evidence": [], "missing": [], "action_hint": "区间内观望",
        }

    # 当前位置
    last_close = float(df_daily["close"].iloc[-1])
    mid = (upper + lower) / 2
    if last_close > upper:
        position = "区间外"
    elif last_close > mid + (upper - mid) * 0.3:
        position = "接近上轨"
    elif last_close < mid - (mid - lower) * 0.3:
        position = "接近下轨"
    else:
        position = "中部"

    # 突破检测（用 confirm_bars）
    breakout_status = "未突破"
    if len(confirm_bars) >= confirm_days:
        above_upper = all(c > upper for c in confirm_bars["close"].values)
        below_lower = all(c < lower for c in confirm_bars["close"].values)
        if above_upper:
            breakout_status = "向上突破确认" if confirm_days >= 2 else "向上突破待确认"
        elif below_lower:
            breakout_status = "向下跌破确认" if confirm_days >= 2 else "向下跌破待确认"

    action_hint = "区间内观望"
    if "向上" in breakout_status:
        action_hint = "趋势跟随"
    elif "向下" in breakout_status:
        action_hint = "风险警戒"
    elif position == "接近下轨":
        action_hint = "等待突破确认"

    return {
        "state": state,
        "confidence": conf,
        "upper": round(upper, 2),
        "lower": round(lower, 2),
        "position": position,
        "breakout_status": breakout_status,
        "evidence": [f"上轨≈{upper:.2f}，下轨≈{lower:.2f}", f"当前位置：{position}"],
        "missing": ["使用分位数拟合"] if use_quantile else [],
        "action_hint": action_hint,
    }
```

更新 `__all__`：

```python
__all__ = [
    "compute_bias", "compute_boll_state", "compute_candle_features",
    "compute_ma_direction", "resample_daily_to_weekly",
    "compute_weekly_trend", "find_support_resistance",
    "evaluate_sr_transformation", "detect_trend_structure_health",
    "detect_channel_or_box_structure",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/reporter/test_phase3_structure.py -v`
Expected: 10/10 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/reporter/technical_structure.py tests/reporter/test_phase3_structure.py
git commit -m "feat(technical): add channel and box structure detection"
```

---

## Task 3：底部区域观察 `evaluate_bottoming_region`

**Files:**
- Modify: `scripts/utils/reporter/technical_structure.py`
- Test: `tests/reporter/test_phase3_bottom_strategy.py`

- [ ] **Step 1: Write the failing test**

```python
import pandas as pd
import numpy as np
from scripts.utils.reporter.technical_structure import evaluate_bottoming_region


def _make_bottoming_daily_df():
    """确定性底部日线数据：前40日大振幅，后40日小振幅收敛。"""
    dates = pd.date_range("2026-01-01", periods=80, freq="B")
    prices = np.zeros(80)
    prices[:40] = 200 + np.sin(np.arange(40)) * 25
    prices[40:] = 200 + np.sin(np.arange(40)) * 3
    return pd.DataFrame({
        "date": dates,
        "open": prices - 1,
        "high": prices + 2,
        "low": prices - 2,
        "close": prices,
        "volume": np.ones(80) * 10000,
    })


def _make_bottoming_weekly_df():
    """确定性底部周线数据。"""
    dates = pd.date_range("2025-01-03", periods=70, freq="W-FRI")
    prices = np.ones(70) * 200
    return pd.DataFrame({
        "date": dates,
        "open": prices - 1,
        "high": prices + 2,
        "low": prices - 2,
        "close": prices,
        "volume": np.ones(70) * 10000,
    })


def _make_structure_health():
    return {
        "state": "低点走平",
        "swing_lows": [
            {"date": "2026-05-15", "price": 190.0},
            {"date": "2026-06-01", "price": 191.0},
        ],
        "last_low_relation": "flat",
        "evidence": ["低点未继续下移"],
        "missing": [],
    }


def test_bottom_watch():
    """满足3条条件 → bottom_watch"""
    df_d = _make_bottoming_daily_df()
    df_w = _make_bottoming_weekly_df()
    indicators = {"bias_5": -2.0, "ma_5": 198, "ma_10": 199, "close": 200}
    trend_state = {"stage": "盘整期", "primary_state": "震荡趋势"}
    structure_health = _make_structure_health()
    weekly_background = {"trend": "震荡"}
    result = evaluate_bottoming_region(
        df_d, df_w, indicators, trend_state,
        structure_health=structure_health,
        weekly_background=weekly_background,
    )
    assert result["state"] == "bottom_watch"
    assert result["confidence"] == "低"


def test_bottom_candidate():
    """满足4条且周线非单边下跌 → bottom_candidate"""
    df_d = _make_bottoming_daily_df()
    df_w = _make_bottoming_weekly_df()
    indicators = {"bias_5": -2.0, "ma_5": 198, "ma_10": 199, "close": 200, "volume": 15000}
    trend_state = {"stage": "盘整期", "primary_state": "震荡趋势"}
    structure_health = _make_structure_health()
    weekly_background = {"trend": "震荡"}
    result = evaluate_bottoming_region(
        df_d, df_w, indicators, trend_state,
        structure_health=structure_health,
        weekly_background=weekly_background,
    )
    assert result["state"] == "bottom_candidate"
    assert result["confidence"] == "中"


def test_no_bottom_in_downtrend():
    """周线单边下跌时不得升级"""
    df_d = _make_bottoming_daily_df()
    df_w = _make_bottoming_weekly_df()
    indicators = {"bias_5": -2.0, "ma_5": 198, "ma_10": 199, "close": 200, "volume": 15000}
    trend_state = {"stage": "破坏期", "primary_state": "下降趋势"}
    structure_health = _make_structure_health()
    weekly_background = {"trend": "单边下跌"}
    result = evaluate_bottoming_region(
        df_d, df_w, indicators, trend_state,
        structure_health=structure_health,
        weekly_background=weekly_background,
    )
    # 即使满足4条，周线单边下跌也不得 bottom_candidate
    assert result["state"] != "bottom_candidate"


def test_swing_lows_missing():
    """structure_health 缺失时 swing_low 条件计入 missing"""
    df_d = _make_bottoming_daily_df()
    df_w = _make_bottoming_weekly_df()
    indicators = {"bias_5": -2.0, "ma_5": 198, "ma_10": 199, "close": 200}
    trend_state = {"stage": "盘整期", "primary_state": "震荡趋势"}
    result = evaluate_bottoming_region(
        df_d, df_w, indicators, trend_state,
        structure_health=None,
        weekly_background={"trend": "震荡"},
    )
    assert any(
        "swing" in str(m).lower() or "low" in str(m).lower()
        for m in result.get("missing", [])
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/reporter/test_phase3_bottom_strategy.py -v`
Expected: `FAILED test_phase3_bottom_strategy.py::test_bottom_watch - NameError`

- [ ] **Step 3: Write minimal implementation**

在 `scripts/utils/reporter/technical_structure.py` 末尾追加：

```python
def evaluate_bottoming_region(
    df_daily: pd.DataFrame,
    df_weekly: pd.DataFrame,
    indicators: dict,
    trend_state: dict,
    structure_health: dict | None = None,
    weekly_background: dict | None = None,
) -> dict:
    """评估是否进入底部区域观察。不直接输出买入建议。"""
    score = 0
    evidence = []
    missing = []

    # 条件1: 波动率收敛
    if len(df_daily) >= 40:
        recent_amp = (df_daily["high"].iloc[-20:].max() - df_daily["low"].iloc[-20:].min()) / df_daily["close"].iloc[-20:].mean()
        prev_amp = (df_daily["high"].iloc[-40:-20].max() - df_daily["low"].iloc[-40:-20].min()) / df_daily["close"].iloc[-40:-20].mean()
        if prev_amp > 0 and recent_amp < prev_amp * 0.4:
            score += 1
            evidence.append("过去20日振幅明显收敛")
    else:
        missing.append("历史数据不足，无法判断波动率收敛")

    # 条件2: 长期支撑附近（周线 MA20/MA60 附近）
    close = indicators.get("close")
    if df_weekly is not None and len(df_weekly) >= 5 and close:
        wma20 = df_weekly["close"].rolling(20).mean().iloc[-1] if len(df_weekly) >= 20 else None
        wma60 = df_weekly["close"].rolling(60).mean().iloc[-1] if len(df_weekly) >= 60 else None
        near = False
        for ma_val, name in [(wma20, "MA20"), (wma60, "MA60")]:
            if ma_val is not None and ma_val > 0 and abs(close - ma_val) / ma_val < 0.05:
                near = True
                evidence.append(f"价格位于周线{name}附近")
                break
        if near:
            score += 1
        else:
            missing.append("价格尚未回到周线长期支撑附近")
    else:
        missing.append("周线数据不足")

    # 条件3: BIAS 负偏离但不再创新低
    bias_5 = indicators.get("bias_5")
    if bias_5 is not None and len(df_daily) >= 20:
        if bias_5 < 0:
            recent_biases = []
            for i in range(1, 6):
                if len(df_daily) >= i + 5:
                    c = df_daily["close"].iloc[-i]
                    ma5_i = df_daily["close"].iloc[-i-4:-i+1].mean() if len(df_daily) >= i + 4 else None
                    if ma5_i and ma5_i > 0:
                        recent_biases.append((c - ma5_i) / ma5_i * 100)
            min_20 = min([
                (df_daily["close"].iloc[j] - df_daily["close"].iloc[max(0, j-4):j+1].mean()) / df_daily["close"].iloc[max(0, j-4):j+1].mean() * 100
                for j in range(-20, 0) if len(df_daily) >= abs(j) + 5
            ]) if len(df_daily) >= 25 else None
            if recent_biases and min_20 is not None and min(recent_biases) >= min_20 - 0.5:
                score += 1
                evidence.append("BIAS负偏离但不再创新低")
            elif bias_5 < 0:
                missing.append("BIAS仍在创新低")
        else:
            missing.append("BIAS未出现负偏离")
    else:
        missing.append("BIAS数据不足")

    # 条件4: 价格不再有效跌破最近 swing low
    if structure_health and structure_health.get("swing_lows"):
        swing_lows = structure_health["swing_lows"]
        if swing_lows:
            last_low = min(s["price"] for s in swing_lows)
            if close and close >= last_low * 0.99:
                score += 1
                evidence.append("价格未有效跌破最近回调低点")
            else:
                missing.append("价格已跌破最近回调低点")
        else:
            missing.append("swing_lows 为空")
    else:
        missing.append("structure_health 或 swing_lows 缺失，无法判断低点支撑")

    # 条件5: 短期修复迹象
    ma5 = indicators.get("ma_5")
    ma10 = indicators.get("ma_10")
    if close and ma5 and ma10:
        if close >= ma5:
            score += 1
            evidence.append("价格重新站上MA5")
        elif abs(ma5 - ma10) / ma10 < 0.01:
            score += 1
            evidence.append("MA5/MA10开始走平")
        else:
            missing.append("尚未出现短期修复迹象")
    else:
        missing.append("MA5/MA10 数据不足")

    # 状态分层
    weekly_trend = (weekly_background or {}).get("trend")
    if weekly_trend is None:
        is_weekly_downtrend = (
            trend_state.get("primary_state") == "下降趋势"
            and trend_state.get("stage") in ["破坏期", "转弱期"]
        )
    else:
        is_weekly_downtrend = weekly_trend == "单边下跌"

    if score >= 5 and indicators.get("volume", 0) > df_daily["volume"].iloc[-20:].mean() * 1.2 and close and indicators.get("ma_20") and close >= indicators["ma_20"]:
        state = "bottom_strengthened"
        conf = "高"
    elif score >= 4 and not is_weekly_downtrend:
        state = "bottom_candidate"
        conf = "中"
    elif score >= 3:
        state = "bottom_watch"
        conf = "低"
    else:
        state = "none"
        conf = "低"

    return {
        "state": state,
        "confidence": conf,
        "score": score,
        "total": 5,
        "evidence": evidence,
        "missing": missing,
        "action_hint": "仅作底部区域观察，不构成买入信号",
        "risk": "若跌破最近swing low，则底部观察失效",
    }
```

更新 `__all__`：

```python
__all__ = [
    "compute_bias", "compute_boll_state", "compute_candle_features",
    "compute_ma_direction", "resample_daily_to_weekly",
    "compute_weekly_trend", "find_support_resistance",
    "evaluate_sr_transformation", "detect_trend_structure_health",
    "detect_channel_or_box_structure", "evaluate_bottoming_region",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/reporter/test_phase3_bottom_strategy.py -v`
Expected: 4/4 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/reporter/technical_structure.py tests/reporter/test_phase3_bottom_strategy.py
git commit -m "feat(technical): add bottoming region observation"
```

---

## Task 4：分批观察框架 `evaluate_dart_strategy`

**Files:**
- Create: `scripts/utils/reporter/technical_strategy.py`
- Modify: `scripts/utils/reporter/technical_analyzer.py`（import）
- Test: `tests/reporter/test_phase3_bottom_strategy.py`

- [ ] **Step 1: Write the failing test**

在 `tests/reporter/test_phase3_bottom_strategy.py` 中追加：

```python
from scripts.utils.reporter.technical_strategy import evaluate_dart_strategy


def test_dart_strategy_active():
    """满足条件触发"""
    bottom = {"state": "bottom_candidate"}
    trend = {"stage": "盘整期", "primary_state": "震荡趋势"}
    indicators = {"close": 200, "ma_5": 198}
    inv = {"hard_invalid_price": 180}
    result = evaluate_dart_strategy(bottom, trend, indicators, inv)
    assert result is not None
    assert result["state"] == "active"
    for step in result["steps"]:
        assert "买入" not in step["action"]
        assert "建仓" not in step["action"]
        assert "加仓" not in step["action"]
        assert "满仓" not in step["action"]


def test_dart_strategy_no_buy_words():
    """不得出现买入/建仓/加仓/满仓"""
    bottom = {"state": "bottom_candidate"}
    trend = {"stage": "盘整期", "primary_state": "震荡趋势"}
    indicators = {"close": 200, "ma_5": 198}
    inv = {"hard_invalid_price": 180}
    result = evaluate_dart_strategy(bottom, trend, indicators, inv)
    text = str(result)
    assert "买入" not in text
    assert "建仓" not in text
    assert "加仓" not in text
    assert "满仓" not in text


def test_dart_strategy_not_triggered_below_ma5():
    """价格低于MA5不触发"""
    bottom = {"state": "bottom_candidate"}
    trend = {"stage": "盘整期", "primary_state": "震荡趋势"}
    indicators = {"close": 195, "ma_5": 198}
    inv = {"hard_invalid_price": 180}
    result = evaluate_dart_strategy(bottom, trend, indicators, inv)
    assert result is None


def test_dart_strategy_not_triggered_in_downtrend():
    """周线破坏期不触发"""
    bottom = {"state": "bottom_candidate"}
    trend = {"stage": "破坏期", "primary_state": "下降趋势"}
    indicators = {"close": 200, "ma_5": 198}
    inv = {"hard_invalid_price": 180}
    result = evaluate_dart_strategy(bottom, trend, indicators, inv)
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/reporter/test_phase3_bottom_strategy.py::test_dart_strategy_active -v`
Expected: `FAILED - ModuleNotFoundError: No module named 'scripts.utils.reporter.technical_strategy'`

- [ ] **Step 3: Write minimal implementation**

创建 `scripts/utils/reporter/technical_strategy.py`：

```python
"""策略信号模块 — 分批观察框架等策略判断。"""


def evaluate_dart_strategy(
    bottom_signal: dict,
    trend_state: dict,
    indicators: dict,
    invalidation: dict,
) -> dict | None:
    """分批观察框架。不直接输出买入建议。"""
    if not bottom_signal or bottom_signal.get("state") not in ["bottom_candidate", "bottom_strengthened"]:
        return None

    weekly_stage = trend_state.get("stage", "")
    if weekly_stage == "破坏期":
        return None

    close = indicators.get("close")
    ma5 = indicators.get("ma_5")
    if close is None or ma5 is None or close < ma5:
        return None

    hard_price = invalidation.get("hard_invalid_price") if invalidation else None
    if hard_price is None:
        return None

    evidence = []
    if bottom_signal["state"] == "bottom_strengthened":
        evidence.append("底部信号增强")
    else:
        evidence.append("底部候选信号出现")
    evidence.append("价格已站上MA5")
    evidence.append("周线非单边下跌")

    return {
        "state": "active",
        "confidence": "中",
        "evidence": evidence,
        "missing": [],
        "action_hint": "底部区域观察成立，可采用分批观察框架",
        "steps": [
            {"level": 1, "condition": "重新站上MA5", "action": "进入观察清单"},
            {"level": 2, "condition": "站上MA10且量能改善", "action": "提高关注度"},
            {"level": 3, "condition": "站上MA20", "action": "视为中期修复确认"},
        ],
        "invalid_if": "跌破最近swing low",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/reporter/test_phase3_bottom_strategy.py -v`
Expected: 8/8 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/reporter/technical_strategy.py tests/reporter/test_phase3_bottom_strategy.py
git commit -m "feat(technical): add dart observation strategy signal"
```

---

## Task 5：市场/行业/主题共振分析

**Files:**
- Create: `config/market_index_map.json`
- Modify: `scripts/utils/reporter/technical_resonance.py`
- Modify: `scripts/utils/reporter/data_fetcher.py`
- Test: `tests/reporter/test_market_resonance.py`

- [ ] **Step 1: Write the failing test**

```python
import json
import pandas as pd
from scripts.utils.reporter.technical_resonance import (
    evaluate_market_resonance,
    load_market_index_map,
    _prefix_fallback,
    analyze_index_trend,
)


def test_prefix_fallback_shanghai():
    """600/601 前缀 fallback 到上证综指"""
    result = _prefix_fallback("600519")
    assert result["market"]["code"] == "000001"


def test_prefix_fallback_star():
    """688 前缀 fallback 到科创50"""
    result = _prefix_fallback("688008")
    assert result["market"]["code"] == "000001"  # 上证综指
    assert result["thematic"]["code"] == "000688"


def test_load_map_missing_stock():
    """不在 map 中的股票走 prefix fallback"""
    result = load_market_index_map("999999", map_path=None)
    assert result["market"] is not None


def test_market_resonance_all_strong():
    """个股+行业+大盘均强 → 顺风共振"""
    stock = {"stage": "主升期", "primary_state": "上升趋势"}
    market = {"stage": "主升期", "primary_state": "上升趋势"}
    sector = {"stage": "主升期", "primary_state": "上升趋势"}
    result = evaluate_market_resonance(stock, market, sector)
    assert result["state"] == "顺风共振"
    assert result["confidence"] == "高"


def test_market_resonance_independent():
    """个股强，行业大盘弱 → 逆风独立"""
    stock = {"stage": "主升期", "primary_state": "上升趋势"}
    market = {"stage": "破坏期", "primary_state": "下降趋势"}
    sector = {"stage": "破坏期", "primary_state": "下降趋势"}
    result = evaluate_market_resonance(stock, market, sector)
    assert result["state"] == "逆风独立"


def test_market_resonance_missing_data():
    """数据缺失时降级"""
    stock = {"stage": "主升期", "primary_state": "上升趋势"}
    result = evaluate_market_resonance(stock, None, None)
    assert result["state"] == "未知"
    assert result["confidence"] == "低"


def test_market_resonance_theme_missing_still_works():
    """theme 缺失但 market/sector 存在时仍应输出有效共振状态"""
    stock = {"stage": "主升期", "primary_state": "上升趋势"}
    market = {"stage": "主升期", "primary_state": "上升趋势"}
    sector = {"stage": "主升期", "primary_state": "上升趋势"}
    result = evaluate_market_resonance(stock, market, sector, theme_trend_state=None)
    assert result["state"] != "未知"
    assert "theme index data missing" in result["missing"]


def test_analyze_index_trend_returns_trend_state():
    """指数趋势分析返回标准结构"""
    dates = pd.date_range("2026-01-01", periods=120, freq="B")
    prices = np.linspace(100, 130, 120)
    df = pd.DataFrame({
        "date": dates,
        "open": prices - 1,
        "high": prices + 1,
        "low": prices - 1,
        "close": prices,
        "volume": np.ones(120) * 10000,
    })
    result = analyze_index_trend(df)
    assert "trend_state" in result
    assert "weekly_background" in result
    assert "daily_structure" in result
    assert "trend_health" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/reporter/test_market_resonance.py -v`
Expected: `FAILED - ModuleNotFoundError` or `AttributeError`

- [ ] **Step 3: Write minimal implementation**

**3a. 创建 `config/market_index_map.json`：**

```json
{
  "_meta": {
    "updated": "2026-06-08",
    "source": "local_cache",
    "version": "phase3.market_resonance.v1"
  },
  "688008": {
    "name": "澜起科技",
    "exchange": "SH",
    "board": "STAR",
    "market": {"code": "000001", "name": "上证综指", "source": "fallback"},
    "sector": {"code": "801081", "name": "申万电子", "source": "sw"},
    "thematic": {"code": "000688", "name": "科创50", "source": "manual"},
    "updated": "2026-06-08",
    "confidence": "中"
  },
  "300003": {
    "name": "乐普医疗",
    "exchange": "SZ",
    "board": "CY",
    "market": {"code": "399006", "name": "创业板指", "source": "fallback"},
    "sector": {"code": "801153", "name": "申万医药生物", "source": "sw"},
    "thematic": {"code": "399006", "name": "创业板指", "source": "fallback"},
    "updated": "2026-06-08",
    "confidence": "中"
  }
}
```

**3b. 修改 `scripts/utils/reporter/technical_resonance.py`：**

在文件末尾追加：

```python
import json
from pathlib import Path


def _prefix_fallback(stock_code: str) -> dict:
    """代码前缀 fallback 判定所属市场/主题指数。"""
    prefix = stock_code[:3] if len(stock_code) >= 3 else stock_code
    result = {"market": None, "sector": None, "thematic": None, "source": "prefix_fallback"}

    if prefix in ["600", "601", "603", "605"]:
        result["market"] = {"code": "000001", "name": "上证综指", "source": "fallback"}
    elif prefix in ["000", "001", "002", "003"]:
        result["market"] = {"code": "399001", "name": "深证成指", "source": "fallback"}
    elif prefix == "300":
        result["market"] = {"code": "399006", "name": "创业板指", "source": "fallback"}
        result["thematic"] = {"code": "399006", "name": "创业板指", "source": "fallback"}
    elif prefix == "688":
        result["market"] = {"code": "000001", "name": "上证综指", "source": "fallback"}
        result["thematic"] = {"code": "000688", "name": "科创50", "source": "fallback"}
    else:
        result["market"] = {"code": "000001", "name": "上证综指", "source": "default"}

    return result


def load_market_index_map(stock_code: str, map_path: str | None = None) -> dict:
    """加载市场/行业/主题映射。优先本地 map，缺失走 prefix fallback。"""
    if map_path is None:
        map_path = str(Path(__file__).parent.parent.parent.parent / "config" / "market_index_map.json")

    try:
        with open(map_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"_meta": {"source": "prefix_fallback"}}

    entry = data.get(stock_code)
    if entry:
        return {
            "market": entry.get("market"),
            "sector": entry.get("sector"),
            "thematic": entry.get("thematic"),
            "source": "map",
            "confidence": entry.get("confidence", "中"),
        }

    return _prefix_fallback(stock_code)


def analyze_index_trend(
    df_daily: pd.DataFrame,
    df_weekly: pd.DataFrame | None = None,
) -> dict:
    """对指数复用中期趋势状态机。"""
    if df_daily is None or df_daily.empty:
        return {
            "trend_state": {"primary_state": "未知", "stage": "未知"},
            "weekly_background": {"trend": "未知"},
            "daily_structure": {},
            "trend_health": {"score": 0, "grade": "未知"},
            "missing": ["index daily data missing"],
        }

    try:
        from .technical_structure import (
            resample_daily_to_weekly,
            compute_weekly_trend,
            compute_ma_direction,
        )
        from .technical_state_machine import (
            classify_trend_state,
            compute_trend_health,
        )
    except ImportError:
        from technical_structure import (
            resample_daily_to_weekly,
            compute_weekly_trend,
            compute_ma_direction,
        )
        from technical_state_machine import (
            classify_trend_state,
            compute_trend_health,
        )

    if df_weekly is None or df_weekly.empty:
        df_weekly = resample_daily_to_weekly(df_daily)

    close = df_daily["close"]
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()

    indicators = {
        "close": float(close.iloc[-1]),
        "ma_20": float(ma20.iloc[-1]) if len(ma20.dropna()) else None,
        "ma_60": float(ma60.iloc[-1]) if len(ma60.dropna()) else None,
        "ma20_direction": compute_ma_direction(ma20),
        "ma60_direction": compute_ma_direction(ma60),
    }

    weekly = compute_weekly_trend(df_weekly)

    daily_structure = {
        "ma20_direction": indicators["ma20_direction"],
        "ma60_direction": indicators["ma60_direction"],
        "price_vs_ma20": (
            "站上" if indicators["ma_20"] and indicators["close"] >= indicators["ma_20"] else "跌破"
        ),
        "price_vs_ma60": (
            "站上" if indicators["ma_60"] and indicators["close"] >= indicators["ma_60"] else "跌破"
        ),
    }

    trend_state = classify_trend_state(
        weekly_trend=weekly.get("weekly_trend", "未知"),
        daily_structure=daily_structure,
        indicators=indicators,
        divergence=None,
    )

    try:
        trend_health = compute_trend_health(
            weekly_background={"trend": weekly.get("weekly_trend", "未知")},
            daily_structure=daily_structure,
            trend_state=trend_state,
            indicators=indicators,
            divergence=None,
        )
    except TypeError:
        trend_health = compute_trend_health(
            weekly_trend=weekly.get("weekly_trend", "未知"),
            daily_structure=daily_structure,
            indicators=indicators,
        )

    return {
        "trend_state": trend_state,
        "weekly_background": weekly,
        "daily_structure": daily_structure,
        "trend_health": trend_health,
        "missing": [],
    }


def evaluate_market_resonance(
    stock_trend_state: dict,
    market_trend_state: dict | None = None,
    sector_trend_state: dict | None = None,
    theme_trend_state: dict | None = None,
    mapping_meta: dict | None = None,
) -> dict:
    """个股 vs 市场/行业/主题趋势共振。"""
    critical_missing = []
    if market_trend_state is None:
        critical_missing.append("market index data missing")
    if sector_trend_state is None:
        critical_missing.append("sector index data missing")

    optional_missing = []
    if theme_trend_state is None:
        optional_missing.append("theme index data missing")

    if market_trend_state is None and sector_trend_state is None:
        return {
            "state": "未知",
            "confidence": "低",
            "market_trend": market_trend_state,
            "sector_trend": sector_trend_state,
            "theme_trend": theme_trend_state,
            "relative_strength": "未知",
            "evidence": [],
            "missing": critical_missing + optional_missing,
            "impact": "暂未接入完整市场/行业数据，本次共振分析仅作占位。",
            "action_hint": "继续观察",
        }

    missing = critical_missing + optional_missing

    def _strength(state):
        if not state:
            return 0
        stage = state.get("stage", "")
        primary = state.get("primary_state", "")
        if primary == "上升趋势":
            return 2 if stage in ["主升期", "加速期", "启动期"] else 1
        elif primary == "下降趋势":
            return -2 if stage in ["破坏期", "转弱期"] else -1
        return 0

    s_str = _strength(stock_trend_state)
    m_str = _strength(market_trend_state)
    c_str = _strength(sector_trend_state)
    t_str = _strength(theme_trend_state)

    # 相对行业强弱
    if c_str > 0:
        relative = "强于行业" if s_str >= c_str else "弱于行业"
    elif c_str < 0:
        relative = "强于行业" if s_str > c_str else "弱于行业"
    else:
        relative = "同步"

    # 共振规则矩阵
    if s_str > 0 and m_str > 0 and c_str > 0:
        state = "顺风共振"; impact = "趋势信号可信度上调"; conf = "高"
    elif s_str > 0 and m_str <= 0 and c_str <= 0:
        state = "逆风独立"; impact = "独立行情，波动风险上升"; conf = "中"
    elif s_str < 0 and c_str > 0:
        state = "弱于板块"; impact = "个股弱于行业，优先级下降"; conf = "中"
    elif s_str < 0 and m_str < 0 and c_str < 0:
        state = "系统性压力"; impact = "中期修复难度较大"; conf = "高"
    elif s_str == 0 and c_str > 0:
        state = "等待补涨确认"; impact = "观察是否突破 MA20"; conf = "中"
    elif s_str == 0 and c_str < 0:
        state = "震荡偏弱"; impact = "降低技术信号权重"; conf = "低"
    else:
        state = "未知"; impact = "信号复杂，继续观察"; conf = "低"

    evidence = [f"个股趋势：{stock_trend_state.get('stage', '未知')}"]
    if market_trend_state:
        evidence.append(f"大盘趋势：{market_trend_state.get('stage', '未知')}")
    if sector_trend_state:
        evidence.append(f"行业趋势：{sector_trend_state.get('stage', '未知')}")

    return {
        "state": state,
        "confidence": conf,
        "market_trend": market_trend_state,
        "sector_trend": sector_trend_state,
        "theme_trend": theme_trend_state,
        "relative_strength": relative,
        "evidence": evidence,
        "missing": missing,
        "impact": impact,
        "action_hint": "继续观察" if state in ["未知", "震荡偏弱"] else ("趋势跟随" if state == "顺风共振" else "保持谨慎"),
    }
```

**3c. 修改 `scripts/utils/reporter/data_fetcher.py`：**

追加：

```python
def fetch_index_bars(self, symbol: str, market: str = "std", days: int = 60) -> pd.DataFrame | None:
    """获取指数日K数据。"""
    if self.client is None:
        logger.warning("mootdx client 未初始化，无法获取指数数据")
        return None
    try:
        try:
            df = self.client.index_bars(symbol=symbol, market=market, frequency="9", offset=days)
        except TypeError:
            df = self.client.index_bars(symbol=symbol, frequency="9", offset=days)
        if df is None or df.empty:
            return None
        df = df.reset_index()
        if "datetime" in df.columns:
            df["date"] = pd.to_datetime(df["datetime"])
        elif "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception as e:
        logger.warning(f"获取指数 {symbol} 数据失败: {e}")
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/reporter/test_market_resonance.py -v`
Expected: 8/8 PASS

- [ ] **Step 5: Commit**

```bash
git add config/market_index_map.json scripts/utils/reporter/technical_resonance.py scripts/utils/reporter/data_fetcher.py tests/reporter/test_market_resonance.py
git commit -m "feat(technical): add market index mapping and resonance framework"
```

---

## Task 6：Renderer 接入最小输出契约

**Files:**
- Modify: `scripts/utils/reporter/sections/technical_renderer.py`
- Test: `tests/reporter/test_phase3_integration.py`

- [ ] **Step 1: Write the failing test**

```python
from scripts.utils.reporter.sections.technical_renderer import TechnicalRenderer


def test_renderer_shows_structure_health():
    """renderer 展示趋势结构"""
    ctx = {
        "stock_name": "测试",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {
                        "trend_state": {"stage": "主升期", "primary_state": "上升趋势"},
                        "trend_health": {"score": 80, "grade": "健康"},
                        "structure_health": {
                            "state": "低点抬升",
                            "confidence": "高",
                            "evidence": ["低点抬高"],
                            "missing": [],
                            "action_hint": "结构健康",
                        },
                        "invalidation": {},
                        "key_levels": {},
                    }
                }
            }
        },
        "technical_render_mode": "compact",
    }
    renderer = TechnicalRenderer()
    md = renderer.render(ctx)
    assert "低点抬升" in md
    assert "结构健康" in md


def test_renderer_no_bottom_confirmed():
    """renderer 不得输出底部确认"""
    ctx = {
        "stock_name": "测试",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {
                        "trend_state": {"stage": "盘整期"},
                        "trend_health": {"score": 50},
                        "bottom_signal": {
                            "state": "bottom_strengthened",
                            "evidence": ["信号增强"],
                            "action_hint": "底部区域进一步确认",
                        },
                        "invalidation": {},
                        "key_levels": {},
                    }
                }
            }
        },
        "technical_render_mode": "compact",
    }
    renderer = TechnicalRenderer()
    md = renderer.render(ctx)
    assert "底部确认" not in md
    assert "底部区域进一步确认" in md or "底部构筑" in md


def test_renderer_no_strategy_judgment():
    """renderer 不做策略判断"""
    ctx = {
        "stock_name": "测试",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {
                        "trend_state": {"stage": "盘整期"},
                        "trend_health": {"score": 50},
                        "dart_strategy": {
                            "state": "active",
                            "steps": [
                                {"level": 1, "condition": "站上MA5", "action": "进入观察清单"}
                            ],
                        },
                        "invalidation": {},
                        "key_levels": {},
                    }
                }
            }
        },
        "technical_render_mode": "compact",
    }
    renderer = TechnicalRenderer()
    md = renderer.render(ctx)
    assert "买入" not in md
    assert "建仓" not in md
    assert "观察清单" in md


def test_renderer_missing_phase3_fields_no_error():
    """缺少 Phase 3 字段时不应抛异常"""
    ctx = {
        "stock_name": "测试",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {
                        "trend_state": {"stage": "主升期", "primary_state": "上升趋势"},
                        "trend_health": {"score": 80, "grade": "健康"},
                        "invalidation": {},
                        "key_levels": {},
                    }
                }
            }
        },
        "technical_render_mode": "compact",
    }
    renderer = TechnicalRenderer()
    md = renderer.render(ctx)
    assert "技术面分析：中期趋势提醒" in md
    assert "趋势结构" not in md  # 因为 structure_health 缺失
    assert "底部区域" not in md  # 因为 bottom_signal 缺失
    assert "市场共振" not in md  # 因为 market_resonance 缺失
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/reporter/test_phase3_integration.py -v`
Expected: `FAILED - AssertionError`（因为 renderer 尚未渲染新字段）

- [ ] **Step 3: Write minimal implementation**

在 `scripts/utils/reporter/sections/technical_renderer.py` 的 `_render_compact` 方法中，在 `**结论**` 之前插入：

```python
        # Phase 3 新增模块渲染
        structure = resonance.get("structure_health")
        if structure and structure.get("state") != "无法判断":
            sh_state = structure.get("state", "")
            sh_conf = structure.get("confidence", "")
            lines.append(f"**趋势结构**：{sh_state}（置信度：{sh_conf}）")
            for ev in structure.get("evidence", [])[:3]:
                lines.append(f"- {ev}")
            lines.append(f"- 提示：{structure.get('action_hint', '')}")
            lines.append("")

        channel = resonance.get("channel_status")
        if channel and channel.get("state") not in ["无明显通道", "未知"]:
            ch_state = channel.get("state", "")
            ch_conf = channel.get("confidence", "")
            pos = channel.get("position", "")
            lines.append(f"**通道/箱体**：{ch_state}（置信度：{ch_conf}）")
            lines.append(f"- 位置：{pos}")
            if channel.get("breakout_status") != "未突破":
                lines.append(f"- 突破状态：{channel['breakout_status']}")
            lines.append(f"- 提示：{channel.get('action_hint', '')}")
            lines.append("")

        bottom = resonance.get("bottom_signal")
        if bottom and bottom.get("state") != "none":
            b_state = bottom.get("state", "")
            b_conf = bottom.get("confidence", "")
            # 文案替换：bottom_strengthened → 底部信号增强
            display_state = {"bottom_watch": "底部区域观察", "bottom_candidate": "底部候选", "bottom_strengthened": "底部信号增强"}.get(b_state, b_state)
            lines.append(f"**底部区域**：{display_state}（置信度：{b_conf}）")
            for ev in bottom.get("evidence", [])[:3]:
                lines.append(f"- {ev}")
            if bottom.get("missing"):
                lines.append(f"- 尚缺：{'; '.join(bottom['missing'][:2])}")
            lines.append(f"- 提示：{bottom.get('action_hint', '')}")
            lines.append("")

        dart = resonance.get("dart_strategy")
        if dart:
            lines.append("**底部区域观察框架**：")
            for step in dart.get("steps", []):
                lines.append(f"- 第{step['level']}层：{step['condition']} → {step['action']}")
            lines.append(f"- 失效条件：{dart.get('invalid_if', '')}")
            lines.append("")

        mr = resonance.get("market_resonance")
        if mr and mr.get("state") != "未知":
            mr_state = mr.get("state", "")
            mr_conf = mr.get("confidence", "")
            lines.append(f"**市场共振**：{mr_state}（置信度：{mr_conf}）")
            for ev in mr.get("evidence", [])[:3]:
                lines.append(f"- {ev}")
            lines.append(f"- 提示：{mr.get('action_hint', '')}")
            lines.append("")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/reporter/test_phase3_integration.py -v`
Expected: 4/4 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/reporter/sections/technical_renderer.py tests/reporter/test_phase3_integration.py
git commit -m "feat(technical): render phase3 structure signals via output contract"
```

---

## Task 7：主入口集成

**Files:**
- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Test: `tests/reporter/test_phase3_integration.py`

- [ ] **Step 1: Write the failing test**

```python
from scripts.utils.reporter.technical_analyzer import TechnicalAnalyzer


def _extract_resonance(result: dict) -> dict:
    return (
        result.get("_resonance")
        or result.get("resonance")
        or result.get("indicators", {}).get("_resonance")
        or {}
    )


def test_analyzer_returns_new_fields():
    """主入口返回包含 Phase 3 新字段"""
    from scripts.utils.reporter.technical_analyzer import advanced_medium_term_resonance

    df_daily = pd.DataFrame({
        "date": pd.date_range("2026-04-01", periods=60, freq="B"),
        "open": np.ones(60) * 200,
        "high": np.ones(60) * 205,
        "low": np.ones(60) * 195,
        "close": np.ones(60) * 200,
        "volume": np.ones(60) * 10000,
    })
    df_weekly = pd.DataFrame({
        "date": pd.date_range("2026-04-01", periods=12, freq="W-FRI"),
        "open": np.ones(12) * 200,
        "high": np.ones(12) * 205,
        "low": np.ones(12) * 195,
        "close": np.ones(12) * 200,
        "volume": np.ones(12) * 10000,
    })
    result = advanced_medium_term_resonance(
        df_daily=df_daily,
        df_weekly=df_weekly,
        quote={"code": "000001"},
    )
    resonance = _extract_resonance(result)
    assert "structure_health" in resonance
    assert "channel_status" in resonance
    assert "bottom_signal" in resonance
    assert "market_resonance" in resonance
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/reporter/test_phase3_integration.py::test_analyzer_returns_new_fields -v`
Expected: `FAILED - KeyError`（因为 `technical_analyzer.py` 尚未集成）

- [ ] **Step 3: Write minimal implementation**

在 `scripts/utils/reporter/technical_analyzer.py` 的 `analyze` 方法中，在 `compute_invalidation` 之后、写入 `_resonance` 之前插入：

```python
        # Phase 3: 趋势结构健康度
        from .technical_structure import (
            detect_trend_structure_health, detect_channel_or_box_structure,
            evaluate_bottoming_region,
        )
        structure_health = detect_trend_structure_health(df_daily)
        channel_status = detect_channel_or_box_structure(df_daily)
        bottom_signal = evaluate_bottoming_region(
            df_daily, df_weekly, indicators, ts, structure_health=structure_health
        )

        # Phase 3: 分批观察框架
        try:
            from .technical_strategy import evaluate_dart_strategy
        except ImportError:
            from technical_strategy import evaluate_dart_strategy
        dart_strategy = evaluate_dart_strategy(
            bottom_signal, ts, indicators, invalidation
        )

        # Phase 3: 市场共振
        try:
            from .technical_resonance import (
                evaluate_market_resonance, load_market_index_map
            )
        except ImportError:
            from technical_resonance import (
                evaluate_market_resonance, load_market_index_map
            )
        mapping = load_market_index_map(stock_code) if stock_code else {}
        market_resonance = {"state": "未知", "confidence": "低", "missing": ["market context not fetched"], "impact": "暂未接入完整市场/行业数据，本次共振分析仅作占位。"}
        # 注意：实际指数数据需在 DataCollector 层获取后传入
        # 这里先用占位，后续由调用方传入 market_context 后升级
```

在 `_resonance.update(...)` 中追加：

```python
            "structure_health": structure_health,
            "channel_status": channel_status,
            "bottom_signal": bottom_signal,
            "dart_strategy": dart_strategy,
            "market_resonance": market_resonance,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/reporter/test_phase3_integration.py -v`
Expected: 4/4 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/reporter/technical_analyzer.py tests/reporter/test_phase3_integration.py
git commit -m "feat(technical): integrate phase3 modules into analyzer"
```

---

## Task 8：全量回归测试

**Files:** 所有已修改文件

- [ ] **Step 1: 运行 Phase 1 + Phase 2 全量测试**

```bash
python -m pytest tests/reporter/ -v --tb=short
```

Expected: 所有 Phase 1/2 测试继续通过

- [ ] **Step 2: 运行 Phase 3 测试**

```bash
python -m pytest tests/reporter/test_phase3_structure.py tests/reporter/test_phase3_bottom_strategy.py tests/reporter/test_market_resonance.py tests/reporter/test_phase3_integration.py -v
```

Expected: 全部通过

- [ ] **Step 3: 运行澜起科技端到端验证**

```bash
python scripts/run_澜起科技技术分析_真实数据.py
```

Expected: 报告正常生成，包含 Phase 3 新字段（如有数据）

- [ ] **Step 4: Commit**

```bash
git commit -m "test(technical): phase3 integration and regression coverage"
```

---

## Self-Review Checklist

- [x] Spec coverage: 7.1 ✅ Task1, 7.4 ✅ Task2, 8.1 ✅ Task3, 8.2 ✅ Task4, 9.1 ✅ Task5, Renderer ✅ Task6, 集成 ✅ Task7
- [x] No placeholders: 所有函数签名、返回结构、测试代码均已具体化
- [x] Type consistency: `detect_trend_structure_health`、`detect_channel_or_box_structure`、`evaluate_bottoming_region` 签名与 spec 一致；`evaluate_dart_strategy` 在 `technical_strategy.py`；`evaluate_market_resonance` 在 `technical_resonance.py`

---

## Acceptance Criteria (12 项)

1. `detect_trend_structure_health` 返回的 `swing_lows` 中，相邻两个 swing low 的间隔必须 >= 3 个交易日才视为有效；3–4 个交易日的 swing low 可以参与判断，但 confidence 不得为“高”；>=5 个交易日的 swing low 才可作为正常置信度结构低点。
2. `detect_channel_or_box_structure` 检测上升/下降通道时，使用 `norm_slope = slope / avg_price` 进行斜率标准化；`abs(norm_slope)` 必须在 0.0001 到 0.01 之间才判定为通道，避免过大斜率被误判。
3. `evaluate_bottoming_region` 的 `confidence` 逻辑：当 `score >= 5`、成交量放大、价格站上 MA20 时输出 `高`；当 `score >= 4` 且周线非单边下跌时输出 `中`；否则（包括 `score >= 3`）统一输出 `低`。
4. `evaluate_bottoming_region` 绝不允许输出 `state == "bottom_confirmed"` 或任何含"底部确认"字样的文案；`action_hint` 固定为 `仅作底部区域观察，不构成买入信号`。
5. `evaluate_dart_strategy` 返回的 `steps` 中，所有 `action` 字段不得包含 `"买入"`、`"建仓"`、`"加仓"`、`"满仓"` 等直接交易指令；只允许 `"进入观察清单"`、`"提高关注度"`、`"视为中期修复确认"` 等观察性语言。
6. `evaluate_dart_strategy` 在 `trend_state["stage"] == "破坏期"` 或价格低于 MA5 时，必须返回 `None`（不触发策略）。
7. `_prefix_fallback("688008")` 返回的市场指数 `code` 必须是 `"000001"`（上证综指），主题指数 `code` 必须是 `"000688"`（科创50）；`_prefix_fallback("300003")` 返回的市场指数 `code` 必须是 `"399006"`（创业板指）。
8. `evaluate_market_resonance` 当 `market_trend_state` 和 `sector_trend_state` 同时为 `None` 时，返回 `state: "未知"`；当仅 `theme_trend_state` 缺失时，仍应输出有效共振状态（如 `顺风共振`），并将 `"theme index data missing"` 放入 `missing`。
9. `fetch_index_bars` 必须兼容 `mootdx` 的两种 API 签名：先尝试带 `market` 参数的调用，若抛出 `TypeError` 则降级为不带 `market` 参数的调用。
10. `TechnicalRenderer._render_compact` 在渲染 `structure_health`、`channel_status`、`bottom_signal`、`dart_strategy`、`market_resonance` 时，必须对所有字段使用 `.get()` 安全访问；当这些字段缺失时不得抛出 `KeyError` 或 `AttributeError`。
11. `test_renderer_missing_phase3_fields_no_error` 验证：当 `_resonance` 中不包含任何 Phase 3 新字段时，renderer 仍能正常输出 Phase 2 内容（如 `技术面分析：中期趋势提醒`），且不渲染 Phase 3 板块。
12. 端到端测试 `scripts/run_澜起科技技术分析_真实数据.py` 执行后，生成的 Markdown 报告中：
    - 不得出现 `"底部确认"`；
    - 不得出现 `"买入"`、`"建仓"`、`"加仓"`、`"满仓"`；
    - 必须出现 `"技术面分析：中期趋势提醒"`。

13. Phase 3 所有测试不得依赖随机数导致偶发失败。
14. 所有新增测试不得包含 `or True` 或弱断言；`evaluate_dart_strategy` 任意 step 和整体输出均不得包含“买入/建仓/加仓/满仓”。
15. `theme_trend_state` 缺失不得导致共振模块整体 `unknown`；`compute_trend_health()` 调用必须适配当前真实函数签名（含 try/except 降级）。
16. `evaluate_bottoming_region()` 必须区分 `missing` 与 `failed`；没有 `swing_lows` 时应计入 `missing`，不能当作反向证据。
17. `weekly_background["trend"]` 与 `trend_state["stage"]` 不得混用；周线趋势判断优先使用 `weekly_background`，缺失时才回退到 `trend_state`。
18. Renderer 缺少 Phase 3 字段时不得报错；文档中的测试预期数量必须与实际测试数量一致。

---

## 执行顺序建议

在正式执行 Phase 3 Task 1–7 前，先做 Commit 0：

```bash
git commit -m "fix(plan): apply final phase3 execution safety patch"
```

包含上述所有 import 修正、测试 fixture 替换、missing 返回修复、签名适配、断言强化、验收标准更新。

然后按原计划执行：

```
Task 1：趋势结构健康度
Task 2：通道 / 箱体识别
Task 3：底部区域观察
Task 4：分批观察框架
Task 5：市场 / 行业 / 主题共振
Task 6：Renderer 接入
Task 7：主入口集成
Task 8：全量回归测试
```

---

*计划版本：phase3.implementation.v1*
*基于 spec：docs/superpowers/specs/2026-06-08-technical-phase3-structure-bottom-resonance.md v2*
*补丁版本：phase3.final_safety_patch.v1*
