# 高级技术分析模块升级实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有技术分析系统从短线信号升级为日线-周线中期趋势提醒系统，输出趋势状态、健康度、失效条件和跟踪建议。

**Architecture:** 在 `technical_analyzer.py` 中新增分层计算函数（BIAS、BOLL状态、周线趋势、日线结构、支撑阻力区间、趋势状态机、健康度评分），通过新的 `advanced_medium_term_resonance()` 主入口组装完整 `_resonance`。`TechnicalRenderer` 支持 compact/full 双模式渲染。

**Tech Stack:** Python 3.11+, pandas, numpy. 不引入 scipy/sklearn（预留开关）。YAML 配置（PyYAML 已可用）。

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `config/technical_config.yaml` | Create | 所有技术分析阈值集中配置 |
| `scripts/utils/reporter/technical_config.py` | Create | Config loader，支持默认值回退 |
| `scripts/utils/reporter/technical_analyzer.py` | Modify（+~600 lines） | 新增 BIAS/BOLL/周线/日线/支撑阻力/状态机/健康度/风险预警/失效条件计算，复用旧指标 |
| `scripts/utils/reporter/sections/technical_renderer.py` | Rewrite | compact/full 双模式渲染，旧结构降级 |
| `tests/reporter/test_technical_config.py` | Create | Config loader 测试 |
| `tests/reporter/test_existing_indicators.py` | Create | 旧指标（MACD/RSI/BOLL/ADX/ATR）兼容测试 |
| `tests/reporter/test_bias_computation.py` | Create | BIAS 计算 + 防 look-ahead |
| `tests/reporter/test_boll_state.py` | Create | BOLL 开口/缩口/正常 |
| `tests/reporter/test_weekly_trend.py` | Create | 周线单边/震荡/修复中 |
| `tests/reporter/test_daily_structure.py` | Create | K线特征、MA方向、日线 resample 周线 |
| `tests/reporter/test_trend_state_machine.py` | Create | 状态冲突优先级 + previous_state |
| `tests/reporter/test_trend_health.py` | Create | 健康度评分 0-100 clamp + invalidation 拆分 |
| `tests/reporter/test_support_resistance.py` | Create | ATR 分箱 + 有效触及 + 缺失处理 |
| `tests/reporter/test_boll_overextension.py` | Create | BOLL 背离/超买预警（简化版） |
| `tests/reporter/test_backward_compatibility.py` | Create | 旧 `_resonance` 降级渲染 + 旧字段兼容 |
| `tests/reporter/test_technical_renderer.py` | Create | compact/full 渲染输出验证 |

---

### Task 1: Config File + Loader

**Files:**
- Create: `config/technical_config.yaml`
- Create: `scripts/utils/reporter/technical_config.py`
- Test: `tests/reporter/test_technical_config.py`

- [ ] **Step 1: Write config file**

Create `config/technical_config.yaml`:

```yaml
technical:
  horizon: medium_term

  data:
    min_daily_bars: 120
    recommended_daily_bars: 250
    min_weekly_bars: 20
    recommended_weekly_bars: 60

  ma:
    flat_threshold: 0.005
    ma20_warning_confirm_days: 3
    ma60_break_confirm_days: 2

  boll:
    open_ratio: 1.2
    squeeze_ratio: 0.8
    width_ma_window: 5

  bias:
    lookback: 120
    windows: [5, 10, 20]
    extreme_windows: [5, 10]

  volume:
    confirm_ratio: 1.3
    ma_window: 20

  support_resistance:
    lookback: 250
    local_extrema_window: 5
    min_touches: 3
    strong_touches: 5
    reverse_pct: 0.02
    reverse_atr_multiplier: 1.0
    bucket_pct: 0.005
    bucket_atr_multiplier: 0.5
    low_liquidity_downgrade: true

  # reserved for future full triple divergence scan (phase 1 uses simplified overextension only)
  divergence:
    swing_left: 3
    swing_right: 3
    min_matched: 2
    total_conditions: 3
    lookback: 80
    boll_upper_tolerance: 1.01

  scoring:
    weekly_structure_weight: 30
    daily_ma_weight: 25
    price_structure_weight: 15
    volume_weight: 10
    volatility_weight: 10
    risk_penalty_weight: 10

  renderer:
    default_mode: compact
    allow_full_mode: true
```

- [ ] **Step 2: Write the failing test**

Create `tests/reporter/test_technical_config.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

from technical_config import load_technical_config


def test_load_config_returns_dict():
    cfg = load_technical_config()
    assert isinstance(cfg, dict)
    assert "technical" in cfg
    assert cfg["technical"]["boll"]["open_ratio"] == 1.2


def test_missing_file_uses_defaults():
    cfg = load_technical_config("/nonexistent/path.yaml")
    assert isinstance(cfg, dict)
    assert cfg["technical"]["boll"]["open_ratio"] == 1.2


def test_config_overrides_defaults():
    cfg = load_technical_config()
    assert cfg["technical"]["bias"]["lookback"] == 120
```

Run: `pytest tests/reporter/test_technical_config.py -v`
Expected: FAIL with "function not defined" or import error

- [ ] **Step 3: Write minimal implementation**

Create `scripts/utils/reporter/technical_config.py`:

```python
"""技术分析阈值配置加载器。"""

import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = {
    "technical": {
        "horizon": "medium_term",
        "data": {
            "min_daily_bars": 120,
            "recommended_daily_bars": 250,
            "min_weekly_bars": 20,
            "recommended_weekly_bars": 60,
        },
        "ma": {
            "flat_threshold": 0.005,
            "ma20_warning_confirm_days": 3,
            "ma60_break_confirm_days": 2,
        },
        "boll": {
            "open_ratio": 1.2,
            "squeeze_ratio": 0.8,
            "width_ma_window": 5,
        },
        "bias": {
            "lookback": 120,
            "windows": [5, 10, 20],
            "extreme_windows": [5, 10],
        },
        "volume": {
            "confirm_ratio": 1.3,
            "ma_window": 20,
        },
        "support_resistance": {
            "lookback": 250,
            "local_extrema_window": 5,
            "min_touches": 3,
            "strong_touches": 5,
            "reverse_pct": 0.02,
            "reverse_atr_multiplier": 1.0,
            "bucket_pct": 0.005,
            "bucket_atr_multiplier": 0.5,
            "low_liquidity_downgrade": True,
        },
        "divergence": {
            "swing_left": 3,
            "swing_right": 3,
            "min_matched": 2,
            "total_conditions": 3,
            "lookback": 80,
            "boll_upper_tolerance": 1.01,
        },
        "scoring": {
            "weekly_structure_weight": 30,
            "daily_ma_weight": 25,
            "price_structure_weight": 15,
            "volume_weight": 10,
            "volatility_weight": 10,
            "risk_penalty_weight": 10,
        },
        "renderer": {
            "default_mode": "compact",
            "allow_full_mode": True,
        },
    }
}


def load_technical_config(path: str | None = None) -> Dict:
    """加载技术分析配置。文件缺失时使用内置默认值。"""
    if path is None:
        path = str(Path(__file__).parent.parent.parent.parent / "config" / "technical_config.yaml")

    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        merged = _deep_merge(dict(_DEFAULT_CONFIG), user_cfg)
        return merged
    except Exception as e:
        logger.warning(f"Config load failed ({e}), using defaults")
        return dict(_DEFAULT_CONFIG)


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """递归合并两个字典。override 覆盖 base。"""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/reporter/test_technical_config.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add config/technical_config.yaml scripts/utils/reporter/technical_config.py tests/reporter/test_technical_config.py
git commit -m "feat(technical): add technical_config.yaml and config loader"
```

---

### Task 2: Existing Indicator Preservation

**Files:**
- Modify: `scripts/utils/reporter/technical_analyzer.py` (extract `_compute_base_indicators()`)
- Test: `tests/reporter/test_existing_indicators.py`

**Goal:** 确保主入口里计算并保留 macd、macd_signal、macd_hist、rsi_14、adx、plus_di、minus_di、boll_upper/mid/lower、atr_14、williams_r、stoch_rsi_k/d、cci_20、obv 等旧字段。新版 advisors 和旧 renderer 都依赖它们。

- [ ] **Step 1: Write the failing test**

Create `tests/reporter/test_existing_indicators.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
from technical_analyzer import _compute_base_indicators


def _make_df(close_list):
    return pd.DataFrame({
        "close": close_list,
        "open": [c * 0.99 for c in close_list],
        "high": [c * 1.01 for c in close_list],
        "low": [c * 0.98 for c in close_list],
        "volume": [1000] * len(close_list),
    })


def test_base_indicators_contain_old_fields():
    close = [100.0 + i * 0.5 for i in range(150)]
    df = _make_df(close)
    indicators = _compute_base_indicators(df)
    required = [
        "close", "volume",
        "macd", "macd_signal", "macd_hist",
        "rsi_14", "adx", "plus_di", "minus_di",
        "boll_upper", "boll_mid", "boll_lower",
        "atr_14", "williams_r", "stoch_rsi_k", "stoch_rsi_d", "cci_20",
        "ma_5", "ma_10", "ma_20", "ma_60",
        "obv", "obv_slope_5", "price_slope_5",
    ]
    for key in required:
        assert key in indicators, f"missing {key}"
        assert indicators[key] is not None, f"{key} is None"
```

Run: `pytest tests/reporter/test_existing_indicators.py -v`
Expected: FAIL with "function not defined"

- [ ] **Step 2: Extract `_compute_base_indicators()`**

Add `def _compute_base_indicators(df: pd.DataFrame) -> Dict:` to `technical_analyzer.py`.

内容直接从现有 `analyze()` 的第 380-433 行提取，不做任何改动，只是封装成函数：

```python
def _compute_base_indicators(df: pd.DataFrame) -> Dict:
    """计算全部旧版指标。被 analyze() 和 advanced_medium_term_resonance() 复用。"""
    close = df["close"]
    volume = df["volume"]

    macd_line, macd_sig, macd_hist = _macd(close)
    boll_up, boll_mid, boll_low = _bollinger(close)
    adx, plus_di, minus_di = _adx(df)
    cci = _cci(df)
    williams = _williams_r(df)
    stoch_k, stoch_d = _stoch_rsi(close)
    atr = _atr(df)
    obv_series = _obv(close, volume)

    indicators = {
        "close": float(close.iloc[-1]),
        "volume": int(volume.iloc[-1]),
        "macd": float(macd_line.iloc[-1]),
        "macd_signal": float(macd_sig.iloc[-1]),
        "macd_hist": float(macd_hist.iloc[-1]),
        "rsi_14": float(_rsi(close, 14).iloc[-1]),
        "stoch_rsi_k": float(stoch_k.iloc[-1]),
        "stoch_rsi_d": float(stoch_d.iloc[-1]),
        "williams_r": float(williams.iloc[-1]),
        "cci_20": float(cci.iloc[-1]),
        "adx": float(adx.iloc[-1]),
        "plus_di": float(plus_di.iloc[-1]),
        "minus_di": float(minus_di.iloc[-1]),
        "atr_14": float(atr.iloc[-1]),
        "obv": int(obv_series.iloc[-1]),
        "obv_slope_5": float(obv_series.diff().tail(5).mean()),
        "price_slope_5": float(close.diff().tail(5).mean()),
        "ma_5": float(_sma(close, 5).iloc[-1]),
        "ma_10": float(_sma(close, 10).iloc[-1]),
        "ma_20": float(_sma(close, 20).iloc[-1]),
        "ma_60": float(_sma(close, 60).iloc[-1]),
        "ema_20": float(_ema(close, 20).iloc[-1]),
        "ema_60": float(_ema(close, 60).iloc[-1]),
        "boll_upper": float(boll_up.iloc[-1]),
        "boll_mid": float(boll_mid.iloc[-1]),
        "boll_lower": float(boll_low.iloc[-1]),
    }

    if len(df) >= 22:
        indicators["monthly_return_pct"] = round(
            (close.iloc[-1] - close.iloc[-22]) / close.iloc[-22] * 100, 2
        )
    if len(df) >= 20 and "amount" in df.columns:
        avg_amount = float(df["amount"].tail(20).mean())
        indicators["avg_amount_yi"] = round(avg_amount / 100000000, 2)
    elif len(df) >= 20:
        avg_vol = float(volume.tail(20).mean())
        avg_close = float(close.tail(20).mean())
        indicators["avg_amount_yi"] = round(avg_vol * avg_close / 100000000, 2)

    return indicators
```

然后修改现有 `analyze()`，让它调用 `_compute_base_indicators(df)`。

- [ ] **Step 3: Run tests**

Run: `pytest tests/reporter/test_existing_indicators.py -v`
Expected: 1 PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/utils/reporter/technical_analyzer.py tests/reporter/test_existing_indicators.py
git commit -m "feat(technical): extract _compute_base_indicators for reuse"
```

---

### Task 3: BIAS Computation

**Files:**
- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Test: `tests/reporter/test_bias_computation.py`

- [ ] **Step 1: Write the failing test**

Create `tests/reporter/test_bias_computation.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import numpy as np
import pandas as pd
from technical_analyzer import compute_bias


def _make_df(close_list):
    return pd.DataFrame({
        "close": close_list,
        "open": close_list,
        "high": close_list,
        "low": close_list,
        "volume": [1000] * len(close_list),
    })


def test_bias_basic():
    df = _make_df([100.0] * 30)
    result = compute_bias(df)
    assert "bias_5" in result
    assert result["bias_5"] == 0.0


def test_bias_extreme_no_lookahead():
    """BIAS 极值判断不应使用当天数据参与历史极值。"""
    close = list(range(1, 121))
    close.extend([150.0] * 10)
    df = _make_df(close)
    result = compute_bias(df)
    assert isinstance(result["bias_5_extreme_high"], bool)
    assert isinstance(result["bias_5_extreme_low"], bool)


def test_bias_extreme_high_detected():
    """构造一个 BIAS(5) 创历史新高的场景。"""
    np.random.seed(42)
    close = [100.0]
    for _ in range(1, 125):
        close.append(close[-1] * (1 + np.random.normal(0, 0.01)))
    close[-1] = close[-1] * 1.15
    df = _make_df(close)
    result = compute_bias(df, lookback=120)
    assert result["bias_5"] is not None
    assert result["bias_5"] > 0
```

Run: `pytest tests/reporter/test_bias_computation.py -v`
Expected: FAIL with "function not defined"

- [ ] **Step 2: Add compute_bias to analyzer**

```python
def compute_bias(df: pd.DataFrame, windows=(5, 10, 20), lookback=120) -> Dict:
    """计算 BIAS(5/10/20)，并标记120日极值（防 look-ahead）。"""
    close = df["close"].astype(float)
    out = {}
    for n in windows:
        ma = close.rolling(n, min_periods=n).mean()
        bias = (close / ma - 1.0) * 100
        cur = bias.iloc[-1]
        out[f"bias_{n}"] = None if pd.isna(cur) else round(float(cur), 2)
        if n in (5, 10):
            hist = bias.shift(1).rolling(lookback, min_periods=min(60, lookback))
            prev_max = hist.max().iloc[-1]
            prev_min = hist.min().iloc[-1]
            out[f"bias_{n}_extreme_high"] = bool(
                pd.notna(cur) and pd.notna(prev_max) and cur > prev_max
            )
            out[f"bias_{n}_extreme_low"] = bool(
                pd.notna(cur) and pd.notna(prev_min) and cur < prev_min
            )
    return out
```

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/reporter/test_bias_computation.py -v`
Expected: 3 PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/utils/reporter/technical_analyzer.py tests/reporter/test_bias_computation.py
git commit -m "feat(technical): add BIAS computation with look-ahead protection"
```

---

### Task 4: BOLL State Computation

**Files:**
- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Test: `tests/reporter/test_boll_state.py`

- [ ] **Step 1: Write the failing test**

Create `tests/reporter/test_boll_state.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
from technical_analyzer import compute_boll_state


def test_boll_open():
    boll_upper = pd.Series([102.0] * 10 + [110.0])
    boll_mid = pd.Series([100.0] * 11)
    boll_lower = pd.Series([98.0] * 10 + [90.0])
    df = pd.DataFrame({
        "boll_upper": boll_upper, "boll_mid": boll_mid, "boll_lower": boll_lower,
    })
    result = compute_boll_state(df)
    assert result["boll_state"] == "开口"
    assert result["boll_width"] is not None


def test_boll_squeeze():
    boll_upper = pd.Series([110.0] * 10 + [102.0])
    boll_mid = pd.Series([100.0] * 11)
    boll_lower = pd.Series([90.0] * 10 + [98.0])
    df = pd.DataFrame({
        "boll_upper": boll_upper, "boll_mid": boll_mid, "boll_lower": boll_lower,
    })
    result = compute_boll_state(df)
    assert result["boll_state"] == "缩口"


def test_boll_no_lookahead():
    width = [0.10] * 6 + [0.15]
    boll_mid = pd.Series([100.0] * 7)
    boll_upper = boll_mid * (1 + pd.Series(width) / 2)
    boll_lower = boll_mid * (1 - pd.Series(width) / 2)
    df = pd.DataFrame({
        "boll_upper": boll_upper, "boll_mid": boll_mid, "boll_lower": boll_lower,
    })
    result = compute_boll_state(df)
    assert result["boll_width_ma5"] is not None
```

- [ ] **Step 2: Add compute_boll_state to analyzer**

```python
def compute_boll_state(df: pd.DataFrame, config: Dict | None = None) -> Dict:
    """计算布林宽度、开口/缩口/正常状态。前5日均宽不含当天。"""
    if config is None:
        config = {"technical": {"boll": {"open_ratio": 1.2, "squeeze_ratio": 0.8, "width_ma_window": 5}}}
    boll_cfg = config.get("technical", {}).get("boll", {})
    open_ratio = boll_cfg.get("open_ratio", 1.2)
    squeeze_ratio = boll_cfg.get("squeeze_ratio", 0.8)
    width_ma_window = boll_cfg.get("width_ma_window", 5)

    upper = df["boll_upper"]
    mid = df["boll_mid"].replace(0, np.nan)
    lower = df["boll_lower"]
    width = (upper - lower) / mid
    width_ma5_prev = width.shift(1).rolling(window=width_ma_window, min_periods=width_ma_window).mean()

    cur_width = width.iloc[-1]
    ref_width = width_ma5_prev.iloc[-1]

    if pd.isna(cur_width) or pd.isna(ref_width):
        state = "未知"
    elif cur_width > ref_width * open_ratio:
        state = "开口"
    elif cur_width < ref_width * squeeze_ratio:
        state = "缩口"
    else:
        state = "正常"

    return {
        "boll_width": None if pd.isna(cur_width) else round(float(cur_width), 4),
        "boll_width_ma5": None if pd.isna(ref_width) else round(float(ref_width), 4),
        "boll_state": state,
    }
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/reporter/test_boll_state.py -v`
Expected: 3 PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/utils/reporter/technical_analyzer.py tests/reporter/test_boll_state.py
git commit -m "feat(technical): add BOLL state computation (open/squeeze/normal)"
```

---

### Task 5: K-line Features + MA Direction + Resample Weekly

**Files:**
- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Test: `tests/reporter/test_daily_structure.py`

- [ ] **Step 1: Write the failing test**

Create `tests/reporter/test_daily_structure.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
import numpy as np
from technical_analyzer import compute_candle_features, compute_ma_direction, resample_daily_to_weekly


def test_candle_features_basic():
    df = pd.DataFrame({
        "open": [100.0], "high": [105.0], "low": [98.0], "close": [103.0],
    })
    result = compute_candle_features(df)
    assert result["body_len"] == 3.0
    assert result["upper_shadow"] == 2.0
    assert result["lower_shadow"] == 2.0
    assert result["is_doji"] is False


def test_candle_features_long_shadow():
    df = pd.DataFrame({
        "open": [100.0], "high": [110.0], "low": [99.0], "close": [100.5],
    })
    result = compute_candle_features(df)
    assert result["is_long_upper_shadow"] is True
    assert result["is_long_lower_shadow"] is False


def test_ma_direction_up():
    ma = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
    assert compute_ma_direction(ma, lookback=5, flat_threshold=0.005) == "向上"


def test_ma_direction_flat():
    ma = pd.Series([100.0] * 6)
    assert compute_ma_direction(ma, lookback=5, flat_threshold=0.005) == "走平"


def test_ma_direction_down():
    ma = pd.Series([105.0, 104.0, 103.0, 102.0, 101.0, 100.0])
    assert compute_ma_direction(ma, lookback=5, flat_threshold=0.005) == "向下"


def test_resample_daily_to_weekly():
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "open": [100.0] * 30,
        "high": [105.0] * 30,
        "low": [95.0] * 30,
        "close": list(range(100, 130)),
        "volume": [1000] * 30,
    })
    weekly = resample_daily_to_weekly(df)
    assert len(weekly) >= 4
    assert "open" in weekly.columns
    assert "high" in weekly.columns
    assert "low" in weekly.columns
    assert "close" in weekly.columns
    assert "volume" in weekly.columns
```

- [ ] **Step 2: Add functions to analyzer**

```python
def compute_candle_features(df: pd.DataFrame, atr: pd.Series | None = None) -> Dict:
    """计算K线实体、影线长度（归一化）。"""
    row = df.iloc[-1]
    open_, high, low, close = row["open"], row["high"], row["low"], row["close"]
    body = abs(close - open_)
    upper_shadow = high - max(open_, close)
    lower_shadow = min(open_, close) - low
    full_range = high - low
    close_base = close if close else np.nan
    atr_cur = atr.iloc[-1] if atr is not None and len(atr) else np.nan
    return {
        "body_len": round(float(body), 4),
        "upper_shadow": round(float(upper_shadow), 4),
        "lower_shadow": round(float(lower_shadow), 4),
        "body_pct": None if not close_base else round(float(body / close_base), 4),
        "upper_shadow_pct": None if not close_base else round(float(upper_shadow / close_base), 4),
        "lower_shadow_pct": None if not close_base else round(float(lower_shadow / close_base), 4),
        "body_atr_ratio": None if pd.isna(atr_cur) or atr_cur == 0 else round(float(body / atr_cur), 2),
        "upper_shadow_atr_ratio": None if pd.isna(atr_cur) or atr_cur == 0 else round(float(upper_shadow / atr_cur), 2),
        "lower_shadow_atr_ratio": None if pd.isna(atr_cur) or atr_cur == 0 else round(float(lower_shadow / atr_cur), 2),
        "is_doji": full_range > 0 and body / full_range < 0.1,
        "is_long_upper_shadow": full_range > 0 and upper_shadow / full_range > 0.45,
        "is_long_lower_shadow": full_range > 0 and lower_shadow / full_range > 0.45,
    }


def compute_ma_direction(ma: pd.Series, lookback: int = 5, flat_threshold: float = 0.005) -> str:
    """判断均线方向：向上 / 向下 / 走平。"""
    if len(ma) < lookback + 1:
        return "未知"
    cur = ma.iloc[-1]
    prev = ma.iloc[-lookback - 1]
    if pd.isna(cur) or pd.isna(prev) or prev == 0:
        return "未知"
    change = cur / prev - 1
    if change > flat_threshold:
        return "向上"
    elif change < -flat_threshold:
        return "向下"
    else:
        return "走平"


def resample_daily_to_weekly(df: pd.DataFrame) -> pd.DataFrame | None:
    """从日线 resample 为周线（周五收盘）。"""
    if df is None or df.empty or len(df) < 5:
        return None
    df = df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    elif not isinstance(df.index, pd.DatetimeIndex):
        return None

    weekly = df.resample("W-FRI").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()
    weekly = weekly.reset_index(drop=True)
    return weekly
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/reporter/test_daily_structure.py -v`
Expected: 6 PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/utils/reporter/technical_analyzer.py tests/reporter/test_daily_structure.py
git commit -m "feat(technical): add candle features, MA direction, and daily-to-weekly resample"
```

---

### Task 6: Weekly Trend

**Files:**
- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Test: `tests/reporter/test_weekly_trend.py`

- [ ] **Step 1: Write the failing test**

Create `tests/reporter/test_weekly_trend.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
import numpy as np
from technical_analyzer import compute_weekly_trend


def make_weekly_df(close_list):
    return pd.DataFrame({
        "close": close_list,
        "open": [c * 0.99 for c in close_list],
        "high": [c * 1.01 for c in close_list],
        "low": [c * 0.98 for c in close_list],
        "volume": [1000] * len(close_list),
    })


def test_weekly_uptrend():
    close = [100.0]
    for _ in range(1, 30):
        close.append(close[-1] * 1.02)
    df = make_weekly_df(close)
    result = compute_weekly_trend(df)
    assert result["weekly_trend"] == "单边上涨"
    assert result["weekly_trend_evidence"]["weeks_above_ma5_ma10"] >= 5


def test_weekly_choppy():
    close = [100.0 + (i % 4 - 2) * 5 for i in range(30)]
    df = make_weekly_df(close)
    result = compute_weekly_trend(df)
    assert result["weekly_trend"] == "震荡"


def test_weekly_downtrend():
    close = [200.0]
    for _ in range(1, 30):
        close.append(close[-1] * 0.98)
    df = make_weekly_df(close)
    result = compute_weekly_trend(df)
    assert result["weekly_trend"] == "单边下跌"


def test_weekly_insufficient_data():
    df = make_weekly_df([100.0] * 5)
    result = compute_weekly_trend(df)
    assert result["weekly_trend"] == "未知"
```

- [ ] **Step 2: Add compute_weekly_trend to analyzer**

```python
def compute_weekly_trend(df_weekly: pd.DataFrame) -> Dict:
    """基于周线判定大背景。返回趋势 + evidence。"""
    close = df_weekly["close"].astype(float)
    ma5 = close.rolling(5, min_periods=5).mean()
    ma10 = close.rolling(10, min_periods=10).mean()
    ma20 = close.rolling(20, min_periods=20).mean()

    if len(df_weekly) < 20:
        return {
            "weekly_trend": "未知",
            "weekly_close": round(float(close.iloc[-1]), 4),
            "weekly_ma5": None, "weekly_ma10": None, "weekly_ma20": None,
            "ma20_direction": "未知",
            "weekly_trend_evidence": {"reason": "周线数据不足"},
        }

    weekly_close = close.iloc[-1]
    above_ma5_ma10_count = ((close > ma5) & (close > ma10)).tail(6).sum()
    below_ma5_ma10_count = ((close < ma5) & (close < ma10)).tail(6).sum()
    ma_order_up = ma5.iloc[-1] > ma10.iloc[-1] > ma20.iloc[-1]
    ma_order_down = ma5.iloc[-1] < ma10.iloc[-1] < ma20.iloc[-1]

    ma5_slope_4w = ma5.iloc[-1] / ma5.iloc[-4] - 1 if ma5.iloc[-4] else np.nan
    ma10_slope_4w = ma10.iloc[-1] / ma10.iloc[-4] - 1 if ma10.iloc[-4] else np.nan

    cross_count = 0
    for i in range(-10, 0):
        crossed = False
        for ma in [ma5, ma10]:
            if pd.isna(ma.iloc[i]) or pd.isna(ma.iloc[i - 1]):
                continue
            prev_side = close.iloc[i - 1] - ma.iloc[i - 1]
            cur_side = close.iloc[i] - ma.iloc[i]
            if prev_side * cur_side < 0:
                crossed = True
        if crossed:
            cross_count += 1

    ma5_ma10_gap = abs(ma5.iloc[-1] - ma10.iloc[-1]) / ma10.iloc[-1] if ma10.iloc[-1] != 0 else 0

    is_uptrend = (
        above_ma5_ma10_count >= 5
        and ma_order_up
        and pd.notna(ma5_slope_4w) and ma5_slope_4w > 0
        and pd.notna(ma10_slope_4w) and ma10_slope_4w > 0
    )
    is_downtrend = (
        below_ma5_ma10_count >= 5
        and ma_order_down
        and pd.notna(ma5_slope_4w) and ma5_slope_4w < 0
        and pd.notna(ma10_slope_4w) and ma10_slope_4w < 0
    )
    is_choppy = cross_count >= 3 or ma5_ma10_gap < 0.02

    if is_uptrend:
        trend = "单边上涨"
    elif is_downtrend:
        trend = "单边下跌"
    elif is_choppy:
        trend = "震荡"
    else:
        trend = "趋势修复中"

    return {
        "weekly_trend": trend,
        "weekly_close": round(float(weekly_close), 4),
        "weekly_ma5": round(float(ma5.iloc[-1]), 4),
        "weekly_ma10": round(float(ma10.iloc[-1]), 4),
        "weekly_ma20": round(float(ma20.iloc[-1]), 4),
        "ma20_direction": compute_ma_direction(ma20, lookback=5, flat_threshold=0.005),
        "weekly_trend_evidence": {
            "weeks_above_ma5_ma10": int(above_ma5_ma10_count),
            "weeks_below_ma5_ma10": int(below_ma5_ma10_count),
            "ma_order": (
                "MA5>MA10>MA20" if ma_order_up
                else "MA5<MA10<MA20" if ma_order_down
                else "均线未形成顺序排列"
            ),
            "ma5_slope_4w": round(float(ma5_slope_4w), 4) if pd.notna(ma5_slope_4w) else None,
            "ma10_slope_4w": round(float(ma10_slope_4w), 4) if pd.notna(ma10_slope_4w) else None,
            "cross_count_10w": int(cross_count),
            "ma5_ma10_gap": round(float(ma5_ma10_gap), 4),
        },
    }
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/reporter/test_weekly_trend.py -v`
Expected: 4 PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/utils/reporter/technical_analyzer.py tests/reporter/test_weekly_trend.py
git commit -m "feat(technical): add weekly trend computation with evidence"
```

---

### Task 7: Support/Resistance Zones with Valid Touch

**Files:**
- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Test: `tests/reporter/test_support_resistance.py`

- [ ] **Step 1: Write the failing test**

Create `tests/reporter/test_support_resistance.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
import numpy as np
from technical_analyzer import find_support_resistance


def _make_df(close_list):
    return pd.DataFrame({
        "close": close_list,
        "open": close_list,
        "high": [c * 1.01 for c in close_list],
        "low": [c * 0.99 for c in close_list],
        "volume": [1000] * len(close_list),
    })


def test_support_resistance_found():
    """构造有明显支撑阻力的价格序列。"""
    np.random.seed(42)
    close = []
    for _ in range(50):
        close.extend([100.0 + np.random.normal(0, 0.5) for _ in range(5)])
        close.extend([110.0 + np.random.normal(0, 0.5) for _ in range(5)])
    df = _make_df(close)
    result = find_support_resistance(df)
    assert result["support_zone"] is not None
    assert result["resistance_zone"] is not None
    assert result["support_zone"]["touches"] >= 3
    assert result["resistance_zone"]["touches"] >= 3


def test_support_resistance_none_for_new_stock():
    """新股数据不足时应返回 None。"""
    df = _make_df([100.0] * 10)
    result = find_support_resistance(df)
    assert result.get("support_zone") is None
    assert result.get("resistance_zone") is None
```

- [ ] **Step 2: Add find_support_resistance to analyzer**

```python
def find_support_resistance(
    df: pd.DataFrame,
    config: Dict | None = None,
) -> Dict:
    """基于ATR分箱识别支撑/阻力区间。要求触及后反向运行。"""
    if config is None:
        config = {"technical": {"support_resistance": {
            "lookback": 250, "local_extrema_window": 5,
            "min_touches": 3, "strong_touches": 5,
            "reverse_pct": 0.02, "reverse_atr_multiplier": 1.0,
            "bucket_pct": 0.005, "bucket_atr_multiplier": 0.5,
            "low_liquidity_downgrade": True,
        }}}}
    sr_cfg = config.get("technical", {}).get("support_resistance", {})
    lookback = sr_cfg.get("lookback", 250)
    min_touches = sr_cfg.get("min_touches", 3)
    reverse_pct = sr_cfg.get("reverse_pct", 0.02)
    reverse_atr_mult = sr_cfg.get("reverse_atr_multiplier", 1.0)
    bucket_pct = sr_cfg.get("bucket_pct", 0.005)
    bucket_atr_mult = sr_cfg.get("bucket_atr_multiplier", 0.5)

    if len(df) < 30:
        return {"support_zone": None, "resistance_zone": None}

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    recent = df.tail(min(lookback, len(df)))
    recent_close = recent["close"].astype(float)
    recent_high = recent["high"].astype(float)
    recent_low = recent["low"].astype(float)

    tr1 = recent_high - recent_low
    tr2 = (recent_high - recent_close.shift(1)).abs()
    tr3 = (recent_low - recent_close.shift(1)).abs()
    atr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14, min_periods=1).mean().iloc[-1]
    cur_price = close.iloc[-1]
    bin_size = max(cur_price * bucket_pct, atr * bucket_atr_mult)

    if bin_size == 0:
        return {"support_zone": None, "resistance_zone": None}

    window = sr_cfg.get("local_extrema_window", 5)
    local_max_mask = (recent_high == recent_high.rolling(window, center=True).max())
    local_min_mask = (recent_low == recent_low.rolling(window, center=True).min())

    # 有效触及：触及后反向运行 >= reverse_pct 或 >= reverse_atr_mult * ATR
    reverse_threshold = max(cur_price * reverse_pct, atr * reverse_atr_mult)

    def _valid_touches(prices: pd.Series, is_support: bool) -> pd.Series:
        """返回有效触及的价格序列。"""
        valid = []
        for idx, price in prices.items():
            # 找触及后 N 天的价格变动
            future = recent_close.loc[idx:].iloc[:6]
            if len(future) < 2:
                continue
            future_max = future.max()
            future_min = future.min()
            if is_support:
                # 支撑：触及低点后反弹
                rebound = future_max - price
                if rebound >= reverse_threshold:
                    valid.append(price)
            else:
                # 阻力：触及高点后回落
                drop = price - future_min
                if drop >= reverse_threshold:
                    valid.append(price)
        return pd.Series(valid)

    max_prices_raw = recent_high[local_max_mask].dropna()
    min_prices_raw = recent_low[local_min_mask].dropna()

    max_prices = _valid_touches(max_prices_raw, is_support=False)
    min_prices = _valid_touches(min_prices_raw, is_support=True)

    if len(max_prices) < min_touches or len(min_prices) < min_touches:
        return {"support_zone": None, "resistance_zone": None}

    max_buckets = (max_prices / bin_size).round()
    min_buckets = (min_prices / bin_size).round()

    from collections import Counter
    max_counts = Counter(max_buckets)
    min_counts = Counter(min_buckets)

    support_zone = None
    resistance_zone = None

    if min_counts:
        best_min_bucket = min_counts.most_common(1)[0]
        if best_min_bucket[1] >= min_touches:
            min_prices_in_bucket = min_prices[min_buckets == best_min_bucket[0]]
            support_zone = {
                "price": round(float(min_prices_in_bucket.mean()), 2),
                "zone_low": round(float(min_prices_in_bucket.min()), 2),
                "zone_high": round(float(min_prices_in_bucket.max()), 2),
                "strength": "强" if best_min_bucket[1] >= sr_cfg.get("strong_touches", 5) else "中",
                "touches": int(best_min_bucket[1]),
            }

    if max_counts:
        best_max_bucket = max_counts.most_common(1)[0]
        if best_max_bucket[1] >= min_touches:
            max_prices_in_bucket = max_prices[max_buckets == best_max_bucket[0]]
            resistance_zone = {
                "price": round(float(max_prices_in_bucket.mean()), 2),
                "zone_low": round(float(max_prices_in_bucket.min()), 2),
                "zone_high": round(float(max_prices_in_bucket.max()), 2),
                "strength": "强" if best_max_bucket[1] >= sr_cfg.get("strong_touches", 5) else "中",
                "touches": int(best_max_bucket[1]),
            }

    return {
        "support_zone": support_zone,
        "resistance_zone": resistance_zone,
    }
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/reporter/test_support_resistance.py -v`
Expected: 2 PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/utils/reporter/technical_analyzer.py tests/reporter/test_support_resistance.py
git commit -m "feat(technical): add support/resistance zone detection with valid-touch validation"
```

---

### Task 8: Trend State Machine + Previous State

**Files:**
- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Test: `tests/reporter/test_trend_state_machine.py`

- [ ] **Step 1: Write the failing test**

Create `tests/reporter/test_trend_state_machine.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

from technical_analyzer import classify_trend_state, apply_previous_state


def _base_indicators():
    return {
        "close": 100.0, "ma_5": 99.0, "ma_10": 98.0, "ma_20": 96.0, "ma_60": 90.0,
        "rsi_14": 55.0, "boll_state": "正常",
    }


def test_uptrend_main_rise():
    result = classify_trend_state(
        weekly_trend="单边上涨",
        daily_structure={"price_vs_ma20": "站上", "price_vs_ma60": "站上", "ma20_direction": "向上"},
        indicators=_base_indicators(),
        divergence=None,
    )
    assert result["stage"] == "主升期"
    assert result["primary_state"] == "上升趋势"


def test_destruction_priority():
    """破坏期应优先于其他状态。price_vs_ma60=='跌破' 即判定。"""
    indicators = _base_indicators()
    indicators["rsi_14"] = 75
    result = classify_trend_state(
        weekly_trend="单边上涨",
        daily_structure={"price_vs_ma20": "跌破", "price_vs_ma60": "跌破", "ma20_direction": "向下"},
        indicators=indicators,
        divergence=None,
    )
    assert result["stage"] == "破坏期"


def test_weak_over_pretty():
    """转弱期优先于高位钝化期。"""
    indicators = _base_indicators()
    indicators["rsi_14"] = 78
    indicators["boll_state"] = "开口"
    result = classify_trend_state(
        weekly_trend="单边上涨",
        daily_structure={"price_vs_ma20": "跌破", "price_vs_ma60": "站上", "ma20_direction": "走平"},
        indicators=indicators,
        divergence=None,
    )
    assert result["stage"] == "转弱期"


def test_apply_previous_state_first_time():
    """首次分析时 previous_state=None，state_changed=None。"""
    trend_state = {"stage": "主升期", "primary_state": "上升趋势"}
    apply_previous_state(trend_state, None)
    assert trend_state["state_changed"] is None
    assert trend_state["previous_state"] is None


def test_apply_previous_state_changed():
    """状态变化时标记 state_changed=True。"""
    trend_state = {"stage": "转弱期", "primary_state": "上升趋势"}
    prev = {"trend_state": {"stage": "主升期"}}
    apply_previous_state(trend_state, prev)
    assert trend_state["state_changed"] is True
    assert trend_state["previous_state"] == "主升期"
```

- [ ] **Step 2: Add functions to analyzer**

```python
def classify_trend_state(
    weekly_trend: str,
    daily_structure: Dict,
    indicators: Dict,
    divergence: Dict | None,
) -> Dict:
    """趋势状态机。按优先级判定唯一阶段。price_vs_ma60=='跌破' 直接判定破坏期。"""
    price_vs_ma20 = daily_structure.get("price_vs_ma20", "未知")
    price_vs_ma60 = daily_structure.get("price_vs_ma60", "未知")
    ma20_dir = daily_structure.get("ma20_direction", "未知")
    ma60_dir = daily_structure.get("ma60_direction", "未知")
    boll_state = indicators.get("boll_state", "正常")
    rsi = indicators.get("rsi_14", 50)
    close = indicators.get("close", 0)
    ma20 = indicators.get("ma_20", 0)
    ma60 = indicators.get("ma_60", 0)

    # 1. 破坏期（最高优先级）
    if price_vs_ma60 == "跌破" or weekly_trend in ["单边下跌"]:
        return {
            "primary_state": "下降趋势",
            "stage": "破坏期",
            "action_hint": "趋势失效",
            "state_changed": None,
            "previous_state": None,
            "summary": "中期趋势结构已破坏，日线有效跌破MA60或周线转弱。",
        }

    # 2. 转弱期
    if price_vs_ma20 == "跌破" and (ma20_dir == "走平" or ma20_dir == "向下"):
        return {
            "primary_state": "下降趋势",
            "stage": "转弱期",
            "action_hint": "降低预期",
            "state_changed": None,
            "previous_state": None,
            "summary": "日线跌破MA20，中期趋势进入观察。",
        }

    # 3. 高位钝化期
    if price_vs_ma20 == "站上" and rsi is not None and rsi > 70 and boll_state == "开口":
        if close > ma20 * 1.05:
            return {
                "primary_state": "上升趋势",
                "stage": "高位钝化期",
                "action_hint": "持有跟踪",
                "state_changed": None,
                "previous_state": None,
                "summary": "趋势仍在MA20上方，但RSI高位、BOLL扩张，警惕过热。",
            }

    # 4. 加速期
    if price_vs_ma20 == "站上" and boll_state == "开口" and close > ma20 * 1.03:
        return {
            "primary_state": "上升趋势",
            "stage": "加速期",
            "action_hint": "持有跟踪",
            "state_changed": None,
            "previous_state": None,
            "summary": "趋势加速，BOLL开口扩大，价格远离MA20。",
        }

    # 5. 主升期
    if price_vs_ma20 == "站上" and ma20_dir == "向上" and ma60_dir in ["向上", "走平"]:
        return {
            "primary_state": "上升趋势",
            "stage": "主升期",
            "action_hint": "持有跟踪",
            "state_changed": None,
            "previous_state": None,
            "summary": "周线多头结构完整，日线沿MA20稳步上行。",
        }

    # 6. 启动期
    if price_vs_ma20 == "站上" and weekly_trend in ["趋势修复中", "震荡"]:
        return {
            "primary_state": "上升趋势",
            "stage": "启动期",
            "action_hint": "趋势确认",
            "state_changed": None,
            "previous_state": None,
            "summary": "刚从震荡/下跌修复，均线刚开始多头排列。",
        }

    # 7. 盘整期
    return {
        "primary_state": "震荡趋势",
        "stage": "盘整期",
        "action_hint": "观察",
        "state_changed": None,
        "previous_state": None,
        "summary": "无明显趋势方向，以观望为主。",
    }


def apply_previous_state(trend_state: Dict, previous_state: Dict | None) -> None:
    """根据上一次分析结果更新 state_changed 和 previous_state。"""
    if previous_state is None:
        trend_state["state_changed"] = None
        trend_state["previous_state"] = None
        return
    old_stage = previous_state.get("trend_state", {}).get("stage")
    cur_stage = trend_state.get("stage")
    trend_state["state_changed"] = old_stage != cur_stage
    trend_state["previous_state"] = old_stage
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/reporter/test_trend_state_machine.py -v`
Expected: 5 PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/utils/reporter/technical_analyzer.py tests/reporter/test_trend_state_machine.py
git commit -m "feat(technical): add trend state machine with priority rules and previous_state"
```

---

### Task 9: Trend Health + Invalidation (fixed)

**Files:**
- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Test: `tests/reporter/test_trend_health.py`

- [ ] **Step 1: Write the failing test**

Create `tests/reporter/test_trend_health.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

from technical_analyzer import compute_trend_health, compute_invalidation


def test_trend_health_clamped():
    result = compute_trend_health(
        weekly_trend="单边上涨",
        daily_structure={"ma20_direction": "向上", "price_vs_ma20": "站上"},
        indicators={"rsi_14": 50, "boll_state": "正常"},
    )
    assert 0 <= result["score"] <= 100
    assert result["grade"] in ["趋势强健", "健康", "转弱观察", "破坏风险高", "趋势失效"]
    assert "components" in result
    assert "penalties" in result


def test_invalidation_basic():
    result = compute_invalidation(
        close=100.0, ma20=95.0, ma60=90.0,
        support_zone={"zone_low": 85.0},
    )
    assert "soft_warning" in result
    assert "hard_invalid" in result
    assert "hard_invalid_price" in result
    assert result["hard_invalid_price"] == 90.0
    assert result["current_distance_to_invalid"] is not None
```

- [ ] **Step 2: Add functions to analyzer**

```python
def compute_trend_health(
    weekly_trend: str,
    daily_structure: Dict,
    indicators: Dict,
    config: Dict | None = None,
) -> Dict:
    """计算趋势健康度评分（0-100）。"""
    if config is None:
        config = {"technical": {"scoring": {
            "weekly_structure_weight": 30, "daily_ma_weight": 25,
            "price_structure_weight": 15, "volume_weight": 10,
            "volatility_weight": 10, "risk_penalty_weight": 10,
        }}}}
    sc = config.get("technical", {}).get("scoring", {})

    score = 0
    components = {}
    penalties = {}
    deductions = []

    if weekly_trend == "单边上涨":
        components["weekly_structure"] = {"score": 25, "max": 30, "evidence": "周线多头排列"}
        score += 25
    elif weekly_trend == "震荡":
        components["weekly_structure"] = {"score": 10, "max": 30, "evidence": "周线震荡"}
        score += 10
    else:
        components["weekly_structure"] = {"score": 5, "max": 30, "evidence": f"周线{weekly_trend}"}
        score += 5

    ma20_dir = daily_structure.get("ma20_direction", "未知")
    ma60_dir = daily_structure.get("ma60_direction", "未知")
    price_vs_ma20 = daily_structure.get("price_vs_ma20", "未知")
    if ma20_dir == "向上" and price_vs_ma20 == "站上":
        components["daily_ma_alignment"] = {"score": 20, "max": 25, "evidence": "MA20向上，价格站上"}
        score += 20
    elif ma20_dir == "走平":
        components["daily_ma_alignment"] = {"score": 10, "max": 25, "evidence": "MA20走平"}
        score += 10
    else:
        components["daily_ma_alignment"] = {"score": 5, "max": 25, "evidence": "MA20向下或价格跌破"}
        score += 5

    structure_type = daily_structure.get("structure_type", "无明显结构")
    if structure_type in ["上升通道", "平台整理"]:
        components["price_structure"] = {"score": 12, "max": 15, "evidence": structure_type}
        score += 12
    else:
        components["price_structure"] = {"score": 5, "max": 15, "evidence": structure_type}
        score += 5

    components["volume_confirmation"] = {"score": 8, "max": 10, "evidence": "成交额温和"}
    score += 8

    boll_state = indicators.get("boll_state", "正常")
    if boll_state == "开口":
        components["volatility_condition"] = {"score": 7, "max": 10, "evidence": "BOLL开口，趋势波动放大"}
        score += 7
    else:
        components["volatility_condition"] = {"score": 5, "max": 10, "evidence": f"BOLL{boll_state}"}
        score += 5

    rsi = indicators.get("rsi_14")
    if rsi is not None and rsi > 75:
        penalties["overextension"] = {"score": -5, "min": -10, "evidence": f"RSI={rsi:.1f} 偏高"}
        score -= 5
        deductions.append("RSI偏高")

    bias_5 = indicators.get("bias_5")
    if bias_5 is not None and bias_5 > 5:
        penalties["overextension"] = penalties.get("overextension", {"score": 0, "min": -10, "evidence": ""})
        penalties["overextension"]["score"] -= 3
        penalties["overextension"]["evidence"] += f" BIAS(5)={bias_5:.1f}%"
        score -= 3
        deductions.append("BIAS偏高")

    score = max(0, min(100, score))

    if score >= 80:
        grade = "趋势强健"
    elif score >= 65:
        grade = "健康"
    elif score >= 50:
        grade = "转弱观察"
    elif score >= 30:
        grade = "破坏风险高"
    else:
        grade = "趋势失效"

    return {
        "score": score,
        "grade": grade,
        "summary": f"趋势健康度{score}/100，{grade}。",
        "components": components,
        "penalties": penalties,
        "deductions": deductions,
    }


def compute_invalidation(
    close: float,
    ma20: float | None,
    ma60: float | None,
    support_zone: Dict | None,
    config: Dict | None = None,
) -> Dict:
    """生成趋势失效条件。hard_invalid_price 是价格位，current_distance_to_invalid 是距离百分比。"""
    if config is None:
        config = {"technical": {"ma": {"ma20_warning_confirm_days": 3, "ma60_break_confirm_days": 2}}}
    ma_cfg = config.get("technical", {}).get("ma", {})

    soft = f"日线连续{ma_cfg.get('ma20_warning_confirm_days', 3)}日收盘跌破MA20"
    hard = "周线收盘跌破MA10，或日线有效跌破MA60"
    struct_break = "跌破前期平台下沿"

    hard_price = ma60 if ma60 and ma60 > 0 else None
    distance = None
    if hard_price and hard_price > 0:
        distance = f"{(close - hard_price) / hard_price * 100:.1f}%"
    elif support_zone and support_zone.get("zone_low"):
        hard_price = support_zone["zone_low"]
        distance = f"{(close - hard_price) / close * 100:.1f}%"

    return {
        "soft_warning": soft,
        "hard_invalid": hard,
        "hard_invalid_price": hard_price,
        "structure_break": struct_break,
        "current_distance_to_invalid": distance or "未知",
    }
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/reporter/test_trend_health.py -v`
Expected: 2 PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/utils/reporter/technical_analyzer.py tests/reporter/test_trend_health.py
git commit -m "feat(technical): add trend health scoring and invalidation with price/distance split"
```

---

### Task 10: BOLL Overextension Warning (Simplified Divergence)

**Files:**
- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Test: `tests/reporter/test_boll_overextension.py`

**Goal:** 第一版不做完整三重背离（2/3 触发）。只做简化版 BOLL 超买/超卖风险预警 + MACD/RSI 单点提醒。

- [ ] **Step 1: Write the failing test**

Create `tests/reporter/test_boll_overextension.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
from technical_analyzer import detect_boll_overextension


def _make_df(close_list):
    return pd.DataFrame({
        "close": close_list,
        "open": close_list,
        "high": [c * 1.01 for c in close_list],
        "low": [c * 0.99 for c in close_list],
        "volume": [1000] * len(close_list),
    })


def test_no_overextension():
    close = [100.0 + i * 0.5 for i in range(50)]
    df = _make_df(close)
    indicators = {
        "close": close[-1], "boll_upper": close[-1] * 1.02, "boll_mid": close[-1], "boll_lower": close[-1] * 0.98,
        "macd": 1.0, "macd_hist": 0.5, "rsi_14": 55.0,
    }
    result = detect_boll_overextension(df, indicators, weekly_trend="单边上涨")
    assert result is None


def test_boll_overextension_detected():
    """价格远高于上轨 + RSI 高位 = 预警。"""
    close = [100.0] * 30
    close.extend([110.0] * 5)
    df = _make_df(close)
    indicators = {
        "close": 110.0,
        "boll_upper": 105.0, "boll_mid": 102.0, "boll_lower": 100.0,
        "macd": 0.8, "macd_hist": 0.3,
        "rsi_14": 78.0,
    }
    result = detect_boll_overextension(df, indicators, weekly_trend="单边上涨")
    assert result is not None
    assert result["type"] == "超买预警"
    assert result["confidence"] in ["中度", "强烈"]
```

- [ ] **Step 2: Add detect_boll_overextension to analyzer**

```python
def detect_boll_overextension(
    df: pd.DataFrame,
    indicators: Dict,
    weekly_trend: str,
    config: Dict | None = None,
) -> Dict | None:
    """简化版背离/超买预警。检测价格突破 BOLL 上轨 + RSI 极端值。"""
    if config is None:
        config = {"technical": {"divergence": {
            "boll_upper_tolerance": 1.01,
        }}}}
    boll_tol = config.get("technical", {}).get("divergence", {}).get("boll_upper_tolerance", 1.01)

    close = indicators.get("close", 0)
    boll_upper = indicators.get("boll_upper")
    boll_lower = indicators.get("boll_lower")
    rsi = indicators.get("rsi_14")
    macd_hist = indicators.get("macd_hist")

    warnings = []
    evidence = {}

    # BOLL 超买/超卖
    if boll_upper and close > boll_upper * boll_tol:
        warnings.append("boll_overextension")
        evidence["boll"] = {"price": close, "upper": boll_upper, "state": "突破上轨"}
    elif boll_lower and close < boll_lower / boll_tol:
        warnings.append("boll_overextension")
        evidence["boll"] = {"price": close, "lower": boll_lower, "state": "跌破下轨"}

    # RSI 极端
    if rsi is not None and rsi > 75:
        warnings.append("rsi_overbought")
        evidence["rsi"] = {"value": rsi, "state": "超买区"}
    elif rsi is not None and rsi < 25:
        warnings.append("rsi_oversold")
        evidence["rsi"] = {"value": rsi, "state": "超卖区"}

    # MACD 柱线收缩
    if macd_hist is not None and macd_hist < 0:
        warnings.append("macd_hist_shrinking")
        evidence["macd"] = {"hist": macd_hist, "state": "柱线翻绿"}

    if len(warnings) >= 2:
        return {
            "type": "超买预警" if close > (boll_upper or close) else "超卖预警",
            "confidence": "强烈" if len(warnings) >= 3 else "中度",
            "matched": len(warnings),
            "total": 3,
            "evidence": evidence,
            "missing": [],
            "action": "均线为王，仅作中期风险预警" if weekly_trend == "单边上涨" else "建议减仓观察",
        }
    elif len(warnings) == 1:
        return {
            "type": "单一预警",
            "confidence": "轻度",
            "matched": 1,
            "total": 3,
            "evidence": evidence,
            "missing": [],
            "action": "观望",
        }

    return None
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/reporter/test_boll_overextension.py -v`
Expected: 2 PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/utils/reporter/technical_analyzer.py tests/reporter/test_boll_overextension.py
git commit -m "feat(technical): add simplified BOLL overextension warning (phase 1, not full triple divergence)"
```

---

### Task 11: Main Entry `advanced_medium_term_resonance`

**Files:**
- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Modify: `scripts/utils/data_collector.py`
- Test: `tests/reporter/test_backward_compatibility.py`

- [ ] **Step 1: Add main entry to analyzer**

Add at the end of `technical_analyzer.py`:

```python
def advanced_medium_term_resonance(
    df_daily: pd.DataFrame,
    df_weekly: pd.DataFrame | None = None,
    quote: Dict | None = None,
    previous_state: Dict | None = None,
    config: Dict | None = None,
) -> Dict:
    """中期趋势技术分析主入口。"""
    if config is None:
        from technical_config import load_technical_config
        config = load_technical_config()

    # 1. 数据质量
    daily_count = len(df_daily) if df_daily is not None else 0

    # 2. 自动 resample 周线（如果未传入）
    if df_weekly is None and df_daily is not None and len(df_daily) >= 5:
        df_weekly = resample_daily_to_weekly(df_daily)
    weekly_count = len(df_weekly) if df_weekly is not None else 0
    sufficient = daily_count >= 120 and weekly_count >= 20

    # 3. 计算全部旧指标（复用 Task 2）
    indicators = _compute_base_indicators(df_daily)

    # BIAS
    bias_result = compute_bias(df_daily)
    indicators.update(bias_result)

    # BOLL state
    close = df_daily["close"].astype(float)
    boll_up, boll_mid, boll_low = _bollinger(close)
    df_boll = pd.DataFrame({"boll_upper": boll_up, "boll_mid": boll_mid, "boll_lower": boll_low})
    boll_result = compute_boll_state(df_boll, config)
    indicators.update(boll_result)
    indicators["boll_upper"] = float(boll_up.iloc[-1])
    indicators["boll_mid"] = float(boll_mid.iloc[-1])
    indicators["boll_lower"] = float(boll_low.iloc[-1])

    # 成交额
    if "amount" in df_daily.columns:
        indicators["amount"] = float(df_daily["amount"].iloc[-1])
        indicators["amount_ma20"] = float(df_daily["amount"].tail(20).mean())
    elif "turnover" in df_daily.columns:
        indicators["turnover_ma20"] = float(df_daily["turnover"].tail(20).mean())

    # 4. 周线趋势
    weekly_result = compute_weekly_trend(df_weekly) if df_weekly is not None and len(df_weekly) >= 20 else {
        "weekly_trend": "未知", "weekly_close": None, "weekly_ma5": None,
        "weekly_ma10": None, "weekly_ma20": None, "ma20_direction": "未知",
        "weekly_trend_evidence": {"reason": "周线数据不足"},
    }
    indicators["weekly_close"] = weekly_result.get("weekly_close")
    indicators["weekly_ma5"] = weekly_result.get("weekly_ma5")
    indicators["weekly_ma10"] = weekly_result.get("weekly_ma10")
    indicators["weekly_ma20"] = weekly_result.get("weekly_ma20")
    indicators["weekly_trend"] = weekly_result.get("weekly_trend")

    # 5. 日线结构
    price_vs_ma20 = "站上" if indicators["close"] > indicators["ma_20"] else "跌破"
    price_vs_ma60 = "站上" if indicators["close"] > indicators["ma_60"] else "跌破"
    daily_structure = {
        "ma20_direction": indicators["ma20_direction"],
        "ma60_direction": indicators["ma60_direction"],
        "price_vs_ma20": price_vs_ma20,
        "price_vs_ma60": price_vs_ma60,
        "structure_type": "无明显结构",
        "boll_state": indicators.get("boll_state", "正常"),
        "price_position": "中轨附近",
    }

    # 6. 支撑阻力
    sr_result = find_support_resistance(df_daily, config)

    # 7. 简化背离扫描
    divergence = detect_boll_overextension(df_daily, indicators, weekly_result["weekly_trend"], config)

    # 8. 趋势状态机
    trend_state = classify_trend_state(
        weekly_trend=weekly_result["weekly_trend"],
        daily_structure=daily_structure,
        indicators=indicators,
        divergence=divergence,
    )
    apply_previous_state(trend_state, previous_state)

    # 9. 趋势健康度
    trend_health = compute_trend_health(
        weekly_trend=weekly_result["weekly_trend"],
        daily_structure=daily_structure,
        indicators=indicators,
        config=config,
    )

    # 10. 失效条件
    invalidation = compute_invalidation(
        close=indicators["close"],
        ma20=indicators.get("ma_20"),
        ma60=indicators.get("ma_60"),
        support_zone=sr_result.get("support_zone"),
        config=config,
    )

    # 11. 分析可信度
    limitations = []
    if daily_count < 120:
        limitations.append("日线数据不足120根")
    if weekly_count < 20:
        limitations.append("周线数据不足20根")
    if not sufficient:
        limitations.append("不满足完整中期趋势分析条件")

    analysis_confidence = {
        "level": "高" if sufficient and not limitations else ("中" if daily_count >= 60 else "低"),
        "reasons": [f"日线{daily_count}根", f"周线{weekly_count}根"] if sufficient else [],
        "limitations": limitations,
    }

    # 12. 组装 _resonance
    _resonance = {
        "trend": "多头" if trend_state["primary_state"] == "上升趋势" else ("空头" if trend_state["primary_state"] == "下降趋势" else "震荡"),
        "momentum": "偏强" if trend_health["score"] >= 65 else "偏弱",
        "volume_price": "确认",
        "composite_score": round(min(10, max(0, trend_health["score"] / 10)), 1),
        "signals": [f"趋势阶段：{trend_state['stage']}"],

        "analysis_horizon": "中期（日线-周线）",
        "analysis_confidence": analysis_confidence,
        "trend_state": trend_state,
        "weekly_background": {
            "trend": weekly_result["weekly_trend"],
            "ma_structure": weekly_result["weekly_trend_evidence"].get("ma_order", "未知"),
            "weekly_close_position": "站上MA10" if weekly_result.get("weekly_close") and weekly_result.get("weekly_ma10") and weekly_result["weekly_close"] > weekly_result["weekly_ma10"] else "未知",
            "evidence": weekly_result["weekly_trend_evidence"],
        },
        "daily_structure": daily_structure,
        "trend_health": trend_health,
        "key_levels": {
            "support_zone": sr_result.get("support_zone"),
            "resistance_zone": sr_result.get("resistance_zone"),
            "medium_term_invalid": invalidation.get("hard_invalid_price"),
        },
        "invalidation": invalidation,
        "market_regime": {
            "market_trend": "未知",
            "sector_trend": "未知",
            "relative_strength": "未知",
            "impact": "暂未接入市场/行业数据，本次技术分析仅基于个股自身K线结构。",
        },
        "advisors": {
            "macd": {"state": "多头延续" if indicators.get("macd", 0) > 0 else "空头延续",
                     "meaning": "仅作趋势确认，不单独构成买卖信号"},
            "rsi": {"value": indicators.get("rsi_14"),
                    "state": "强势钝化" if indicators.get("rsi_14", 50) > 70 else "正常",
                    "meaning": "强趋势中不单独构成卖出信号"},
            "bias": {"state": "偏高" if indicators.get("bias_5", 0) > 3 else "正常",
                     "meaning": "短线追高性价比下降，但中期趋势未破坏"},
            "boll": {"state": indicators.get("boll_state", "正常"),
                     "meaning": "开口=趋势加速，缩口=等待方向"},
        },
        "divergence_scan": divergence,
        "sell_assessment": None,
        "basis_rules": ["周线优先原则", "MA20/MA60 中期结构判定", "有效突破/跌破去抖动规则", "均线为王，谋士辅助"],
        "risk_reminder": "本模块用于日线—周线级别的中期趋势提醒，不用于日内或短线高频择时。",
    }

    return {
        "indicators": indicators,
        "resonance": _resonance,
        "patterns": [],
        "levels": {
            "support": sr_result["support_zone"]["price"] if sr_result.get("support_zone") else None,
            "resistance": sr_result["resistance_zone"]["price"] if sr_result.get("resistance_zone") else None,
        },
    }
```

- [ ] **Step 2: Modify analyze()**

Replace the body of `analyze()`:

```python
def analyze(df: pd.DataFrame, df_weekly: pd.DataFrame | None = None) -> Dict:
    """对日K DataFrame做完整技术分析（中期趋势版）。"""
    if df is None or df.empty or len(df) < 30:
        logger.warning("数据不足30条，无法做完整技术分析")
        return {}

    for col in ["open", "high", "low", "close", "volume"]:
        if col not in df.columns:
            logger.error(f"缺少必要列: {col}")
            return {}

    return advanced_medium_term_resonance(df_daily=df, df_weekly=df_weekly)
```

- [ ] **Step 3: Write backward compatibility test**

Create `tests/reporter/test_backward_compatibility.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
from technical_analyzer import analyze


def _make_df(close_list):
    return pd.DataFrame({
        "close": close_list,
        "open": [c * 0.99 for c in close_list],
        "high": [c * 1.01 for c in close_list],
        "low": [c * 0.98 for c in close_list],
        "volume": [1000] * len(close_list),
    })


def test_analyze_returns_backward_compatible_shape():
    close = [100.0]
    for _ in range(1, 150):
        close.append(close[-1] * (1 + (0.01 if _ % 2 == 0 else -0.005)))
    df = _make_df(close)
    result = analyze(df)
    assert "indicators" in result
    assert "resonance" in result
    assert "patterns" in result
    assert "levels" in result
    # backward compatible fields
    res = result["resonance"]
    assert "trend" in res
    assert "composite_score" in res
    assert "trend_state" in res
    # old indicator fields must exist
    ind = result["indicators"]
    assert "rsi_14" in ind
    assert "macd" in ind
    assert "ma_20" in ind
    assert "boll_upper" in ind
    assert "atr_14" in ind
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/reporter/test_backward_compatibility.py -v`
Expected: 1 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/reporter/technical_analyzer.py tests/reporter/test_backward_compatibility.py
git commit -m "feat(technical): add advanced_medium_term_resonance main entry, wire into analyze()"
```

---

### Task 12: TechnicalRenderer Compact/Full + Legacy Fallback

**Files:**
- Modify: `scripts/utils/reporter/sections/technical_renderer.py`
- Test: `tests/reporter/test_technical_renderer.py`

- [ ] **Step 1: Write the failing test**

Create `tests/reporter/test_technical_renderer.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter" / "sections"))

from technical_renderer import TechnicalRenderer


def _make_ctx(with_new_fields=True, mode="compact"):
    ctx = {
        "stock_name": "测试股",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {
                        "trend": "多头",
                        "composite_score": 7.2,
                    } if not with_new_fields else {
                        "trend": "多头",
                        "composite_score": 7.2,
                        "trend_state": {
                            "primary_state": "上升趋势",
                            "stage": "主升期",
                            "action_hint": "持有跟踪",
                            "summary": "测试摘要",
                        },
                        "trend_health": {
                            "score": 72,
                            "grade": "健康",
                            "summary": "健康",
                        },
                        "analysis_confidence": {"level": "高", "reasons": [], "limitations": []},
                        "weekly_background": {"trend": "单边上涨"},
                        "daily_structure": {
                            "ma20_direction": "向上", "ma60_direction": "向上",
                            "structure_type": "上升通道", "boll_state": "开口",
                        },
                        "key_levels": {
                            "support_zone": {"zone_low": 90, "zone_high": 92, "strength": "强"},
                            "resistance_zone": {"zone_low": 110, "zone_high": 112, "strength": "中"},
                        },
                        "invalidation": {
                            "soft_warning": "跌破MA20",
                            "hard_invalid": "跌破MA60",
                            "hard_invalid_price": 90.0,
                            "current_distance_to_invalid": "5%",
                        },
                        "advisors": {
                            "macd": {"state": "多头延续", "meaning": "仅参考"},
                            "rsi": {"value": 55, "state": "正常", "meaning": "仅参考"},
                            "bias": {"state": "正常", "meaning": "仅参考"},
                            "boll": {"state": "开口", "meaning": "仅参考"},
                        },
                    },
                },
            },
        },
        "chart_paths": {},
        "technical_render_mode": mode,
    }
    return ctx


def test_compact_rendering():
    renderer = TechnicalRenderer()
    ctx = _make_ctx(with_new_fields=True, mode="compact")
    output = renderer.render(ctx)
    assert "中期趋势提醒" in output
    assert "主升期" in output
    assert "72/100" in output
    assert "趋势失效条件" in output


def test_full_rendering():
    renderer = TechnicalRenderer()
    ctx = _make_ctx(with_new_fields=True, mode="full")
    output = renderer.render(ctx)
    assert "趋势背景" in output
    assert "日线结构" in output
    assert "健康度评分" in output


def test_fallback_to_legacy():
    renderer = TechnicalRenderer()
    ctx = _make_ctx(with_new_fields=False, mode="compact")
    output = renderer.render(ctx)
    assert "技术面分析" in output
    assert "composite_score" in output or "综合评分" in output


def test_missing_support_resistance():
    renderer = TechnicalRenderer()
    ctx = _make_ctx(with_new_fields=True, mode="compact")
    ctx["stock_raw"]["technical"]["indicators"]["_resonance"]["key_levels"]["support_zone"] = None
    output = renderer.render(ctx)
    assert "暂无可靠支撑区" in output
```

- [ ] **Step 2: Rewrite TechnicalRenderer**

Replace `scripts/utils/reporter/sections/technical_renderer.py`:

```python
"""技术面分析板块渲染器 — 支持中期趋势新版 + 旧版降级。"""

from typing import Any, Dict


class TechnicalRenderer:
    """技术面分析板块 — 中期趋势提醒系统。"""

    def render(self, ctx: Dict[str, Any]) -> str:
        stock_name = ctx.get("stock_name", "")
        stock_raw = ctx.get("stock_raw", {})
        tech = stock_raw.get("technical", {})
        indicators = tech.get("indicators", {})
        resonance = indicators.get("_resonance", {})

        if resonance.get("trend_state") and resonance.get("trend_health"):
            mode = ctx.get("technical_render_mode", "compact")
            if mode == "full":
                return self._render_full(resonance, stock_name, ctx)
            return self._render_compact(resonance, stock_name, ctx)

        return self._render_legacy(resonance, indicators, stock_name, ctx)

    def _render_compact(self, resonance: Dict, stock_name: str, ctx: Dict) -> str:
        ts = resonance.get("trend_state", {})
        th = resonance.get("trend_health", {})
        inv = resonance.get("invalidation", {})
        kl = resonance.get("key_levels", {})
        advisors = resonance.get("advisors", {})
        conf = resonance.get("analysis_confidence", {})

        lines = ["## 技术面分析：中期趋势提醒", ""]

        if conf.get("level"):
            lines.append(f"**分析可信度**：{conf['level']}")
            if conf.get("limitations"):
                lines.append(f"限制因素：{'；'.join(conf['limitations'])}")
            lines.append("")

        stage = ts.get("stage", "未知")
        primary = ts.get("primary_state", "未知")
        score = th.get("score", 0)
        grade = th.get("grade", "未知")
        summary = ts.get("summary", "")

        lines.append(
            f"当前处于【{primary} / {stage}】，趋势健康度【{score}/100，{grade}】。"
        )
        if summary:
            lines.append(summary)
        lines.append("")

        lines.append("**关键观察位**：")
        sz = kl.get("support_zone")
        rz = kl.get("resistance_zone")
        if sz:
            lines.append(f"- 支撑区：【{sz.get('zone_low', '—')} - {sz.get('zone_high', '—')}】（{sz.get('strength', '弱')}）")
        else:
            lines.append("- 支撑区：暂无可靠支撑区，原因：历史数据不足或有效触及次数不足。")
        if rz:
            lines.append(f"- 压力区：【{rz.get('zone_low', '—')} - {rz.get('zone_high', '—')}】（{rz.get('strength', '弱')}）")
        else:
            lines.append("- 压力区：暂无可靠压力区，原因：历史数据不足或有效触及次数不足。")
        if inv.get("current_distance_to_invalid"):
            lines.append(f"- 中期失效参考：【{inv['current_distance_to_invalid']}】")
        lines.append("")

        lines.append("**趋势失效条件**：")
        if inv.get("soft_warning"):
            lines.append(f"- 第一警戒：【{inv['soft_warning']}】")
        if inv.get("hard_invalid"):
            lines.append(f"- 中期失效：【{inv['hard_invalid']}】")
        lines.append("")

        deductions = th.get("deductions", [])
        if deductions:
            lines.append(f"**主要风险**：【{'，'.join(deductions)}】")
            lines.append("")

        lines.append("**结论**：趋势仍可跟踪，但不适合将 RSI 超买、BIAS 偏高或 MACD 背离单独视为卖出信号。")
        lines.append("")

        adv_lines = []
        for name, info in advisors.items():
            meaning = info.get("meaning", "")
            adv_lines.append(f"{name.upper()}：{info.get('state', '—')}（{meaning}）")
        if adv_lines:
            lines.append("**谋士团**：" + " | ".join(adv_lines))
            lines.append("")

        div = resonance.get("divergence_scan")
        if div:
            lines.append(f"**背离预警**：{div.get('type', '')}（{div.get('confidence', '')}）")
            lines.append(f"处置：{div.get('action', '观望')}")
            lines.append("")

        chart_paths = ctx.get("chart_paths", {})
        tech_chart = chart_paths.get("technical")
        if tech_chart:
            lines.append("### 技术面综合图")
            lines.append("")
            lines.append(f"![{stock_name} 技术面分析]({tech_chart})")
            lines.append("")

        return "\n".join(lines)

    def _render_full(self, resonance: Dict, stock_name: str, ctx: Dict) -> str:
        """完整版渲染，包含更多细节。"""
        lines = self._render_compact(resonance, stock_name, ctx).split("\n")
        # 插入更多细节到合适位置
        ts = resonance.get("trend_state", {})
        wb = resonance.get("weekly_background", {})
        ds = resonance.get("daily_structure", {})

        # 在 "## 技术面分析：中期趋势提醒" 后插入趋势背景
        insert_idx = 2
        lines.insert(insert_idx, "")
        lines.insert(insert_idx + 1, "### 1. 趋势背景")
        lines.insert(insert_idx + 2, f"- 周线大背景：{wb.get('trend', '未知')}")
        lines.insert(insert_idx + 3, f"- MA 结构：{wb.get('ma_structure', '未知')}")
        lines.insert(insert_idx + 4, "")
        lines.insert(insert_idx + 5, "### 2. 日线结构")
        lines.insert(insert_idx + 6, f"- MA20 方向：{ds.get('ma20_direction', '未知')}")
        lines.insert(insert_idx + 7, f"- MA60 方向：{ds.get('ma60_direction', '未知')}")
        lines.insert(insert_idx + 8, f"- 价格位置：{ds.get('price_vs_ma20', '未知')} MA20")
        lines.insert(insert_idx + 9, "")
        lines.insert(insert_idx + 10, "### 3. 健康度评分")
        th = resonance.get("trend_health", {})
        for name, comp in th.get("components", {}).items():
            lines.insert(insert_idx + 11, f"- {name}：{comp.get('score', 0)}/{comp.get('max', 0)} ({comp.get('evidence', '')})")
        lines.insert(insert_idx + 12, "")

        return "\n".join(lines)

    def _render_legacy(self, resonance: Dict, indicators: Dict, stock_name: str, ctx: Dict) -> str:
        """旧版技术指标快照渲染（降级）。"""
        lines = ["## 技术面分析", ""]

        if resonance:
            trend = resonance.get("trend", "")
            momentum = resonance.get("momentum", "")
            score = resonance.get("composite_score", 0)
            signals = resonance.get("signals", [])

            trend_icon = {"多头": "", "空头": "", "震荡": ""}.get(trend, "")
            mom_icon = {"超买": "", "超卖": "", "中性": ""}.get(momentum, "")
            lines.append(
                f"**趋势**: {trend_icon} {trend} | **动量**: {mom_icon} {momentum} | **综合评分**: {score}/10"
            )
            lines.append("")
            if signals:
                lines.append("**关键信号：**")
                for sig in signals:
                    lines.append(f"- {sig}")
                lines.append("")

        lines.append("### 指标快照")
        lines.append("")
        lines.append("| 指标 | 数值 | 状态 |")
        lines.append("|------|------|------|")

        def _status(val, bull, bear):
            if val is None:
                return "N/A", "—"
            s = f"{val:.1f}"
            if bull and bear:
                if val > bull:
                    return s, " 超买"
                elif val < bear:
                    return s, " 超卖"
                return s, " 中性"
            return s, "—"

        rsi = indicators.get("rsi_14")
        v, st = _status(rsi, 70, 30)
        lines.append(f"| RSI(14) | {v} | {st} |")

        macd = indicators.get("macd")
        macd_hist = indicators.get("macd_hist")
        if macd is not None:
            macd_str = f"{macd:+.2f}"
            if macd_hist is not None:
                macd_str += f" (柱{macd_hist:+.2f})"
            macd_state = " 金叉扩张" if macd > 0 and macd_hist and macd_hist > 0 else (" 死叉收缩" if macd < 0 and macd_hist and macd_hist < 0 else " 观望")
            lines.append(f"| MACD | {macd_str} | {macd_state} |")

        adx = indicators.get("adx")
        plus_di = indicators.get("plus_di")
        minus_di = indicators.get("minus_di")
        if adx is not None:
            adx_str = f"{adx:.1f}"
            if plus_di is not None and minus_di is not None:
                adx_str += f" (+{plus_di:.1f}/-{minus_di:.1f})"
            adx_state = " 强趋势" if adx > 25 else " 弱趋势"
            lines.append(f"| ADX(14) | {adx_str} | {adx_state} |")

        cci = indicators.get("cci_20")
        v, st = _status(cci, 100, -100)
        lines.append(f"| CCI(20) | {v} | {st} |")

        wr = indicators.get("williams_r")
        v, st = _status(wr, -20, -80)
        lines.append(f"| Williams %R(14) | {v} | {st} |")

        stoch_k = indicators.get("stoch_rsi_k")
        stoch_d = indicators.get("stoch_rsi_d")
        if stoch_k is not None:
            stoch_str = f"{stoch_k:.2f}"
            if stoch_d is not None:
                stoch_str += f" / D={stoch_d:.2f}"
            stoch_state = " 超买" if stoch_k > 0.8 else (" 超卖" if stoch_k < 0.2 else " 中性")
            lines.append(f"| StochRSI(14) | {stoch_str} | {stoch_state} |")

        atr = indicators.get("atr_14")
        close = indicators.get("close")
        if atr is not None and close:
            atr_pct = atr / close * 100
            atr_state = " 高波动" if atr_pct > 5 else (" 低波动" if atr_pct < 1.5 else " 正常")
            lines.append(f"| ATR(14) | {atr:.2f} ({atr_pct:.1f}%) | {atr_state} |")

        lines.append("")

        levels = indicators.get("_levels", {})
        support = levels.get("support")
        resistance = levels.get("resistance")
        if support or resistance:
            lines.append("### 关键价位")
            lines.append("")
            if support:
                lines.append(f"- **支撑位**: {support}")
            if resistance:
                lines.append(f"- **阻力位**: {resistance}")
            if close and support and resistance:
                position = (close - support) / (resistance - support) * 100 if resistance != support else 50
                lines.append(f"- **当前位置**: 处于支撑-阻力区间的 **{position:.0f}%**")
            lines.append("")

        patterns = indicators.get("_patterns", [])
        if patterns:
            lines.append("### 形态识别")
            lines.append("")
            for p in patterns:
                conf = p.get("confidence", "")
                desc = p.get("description", "")
                lines.append(f"- **{p['pattern']}** ({conf}置信): {desc}")
            lines.append("")

        chart_paths = ctx.get("chart_paths", ctx.get("_chart_paths", {}))
        tech_chart = chart_paths.get("technical")
        if tech_chart:
            lines.append("### 技术面综合图")
            lines.append("")
            lines.append(f"![{stock_name} 技术面分析]({tech_chart})")
            lines.append("")

        return "\n".join(lines)
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/reporter/test_technical_renderer.py -v`
Expected: 4 PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/utils/reporter/sections/technical_renderer.py tests/reporter/test_technical_renderer.py
git commit -m "feat(technical): rewrite TechnicalRenderer with compact/full modes and legacy fallback"
```

---

### Task 13: Full Test Suite + End-to-End

**Files:**
- Test: `tests/reporter/test_advanced_technical_e2e.py`

- [ ] **Step 1: Write end-to-end test**

Create `tests/reporter/test_advanced_technical_e2e.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
import numpy as np
from technical_analyzer import analyze
from technical_renderer import TechnicalRenderer


def _make_df(close_list):
    return pd.DataFrame({
        "close": close_list,
        "open": [c * 0.99 for c in close_list],
        "high": [c * 1.01 for c in close_list],
        "low": [c * 0.98 for c in close_list],
        "volume": [1000] * len(close_list),
    })


def test_e2e_uptrend_stock():
    """模拟一只上涨股票，验证完整流程。"""
    close = [100.0]
    for i in range(1, 150):
        close.append(close[-1] * (1 + 0.005 + np.random.normal(0, 0.005)))
    df = _make_df(close)
    result = analyze(df)

    assert "indicators" in result
    assert "resonance" in result
    res = result["resonance"]
    assert res["trend_state"]["stage"] in ["主升期", "加速期", "启动期"]
    assert 0 <= res["trend_health"]["score"] <= 100
    assert res["key_levels"]["medium_term_invalid"] is not None

    # renderer
    ctx = {
        "stock_name": "测试",
        "stock_raw": {"technical": {"indicators": {"_resonance": res}}},
        "chart_paths": {},
    }
    renderer = TechnicalRenderer()
    output = renderer.render(ctx)
    assert "中期趋势提醒" in output


def test_e2e_choppy_stock():
    """模拟震荡股票。"""
    close = [100.0 + (i % 10 - 5) * 2 for i in range(150)]
    df = _make_df(close)
    result = analyze(df)
    res = result["resonance"]
    assert res["weekly_background"]["trend"] in ["震荡", "未知", "趋势修复中"]
```

Run: `pytest tests/reporter/test_advanced_technical_e2e.py -v`
Expected: 2 PASS

- [ ] **Step 2: Commit**

```bash
git add tests/reporter/test_advanced_technical_e2e.py
git commit -m "test(technical): add end-to-end integration tests"
```

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-08-advanced-technical-analysis.md`.

Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
