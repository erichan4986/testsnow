# A股/港股选股报告技术分析模块升级方案：中期趋势提醒版

> **定位**：日线—周线级别的中期趋势提醒系统，不是短线择时系统。
>
> 核心原则：`周线定背景，日线做确认；MA20/MA60 定中期结构，MA5/MA10 只看短期节奏；均线为王，谋士辅助；少触发，慢确认，强解释，重失效条件。`

---

## 1. 总体数据结构升级

### 1.1 Pipeline 不变

现有执行顺序不变：

```text
technical_fetching_skill → TechnicalAnalysisSkill → ReportAssemblySkill
```

`stock_raw["technical"]["indicators"]` 继续作为核心数据载体。现有 `_resonance` 中 `trend`、`momentum`、`volume_price`、`composite_score`、`signals` 字段保留，保证 backward compatible。

### 1.2 分层结构（内部逻辑升级）

```python
stock_raw["technical"] = {
    "indicators": {...},      # 纯数值指标：MA、MACD、RSI、BIAS、BOLL、ATR 等
    "features": {...},        # 中间特征：K线实体、影线、穿越、突破、放量等
    "analysis": {
        "_resonance": {...},  # 技术解释结构（见 §15）
        "_patterns": [...],
        "_levels": {...},
    },
    "meta": {...},            # 市场类型、数据质量、schema 版本等
}
```

兼容策略：`analysis["_resonance"]` 镜像写回 `indicators["_resonance"]`，旧代码无需改动。

### 1.3 meta 字段

```python
"meta": {
    "schema_version": "technical.v2.medium_term",
    "analysis_horizon": "中期（日线-周线）",
    "market": "CN_A" | "HK" | "UNKNOWN",
    "board": "MAIN" | "STAR" | "CHINEXT" | "HK_MAIN" | "UNKNOWN",
    "adjustment": "qfq" | "hfq" | "raw" | "unknown",
    "daily_bars_count": 250,
    "weekly_bars_count": 60,
    "sufficient_for_medium_term": True,
    "data_quality": {
        "has_missing": False,
        "has_suspension": False,
        "has_limit_up_down": False,
        "insufficient_history": False,
        "limitations": [],
    }
}
```

---

## 2. 市场上下文：A股/港股差异处理

### 2.1 market_context

```python
def infer_market_context(code: str, name: str, quote: dict | None = None) -> dict:
    return {
        "market": "CN_A" | "HK" | "UNKNOWN",
        "board": "MAIN" | "STAR" | "CHINEXT" | "HK_MAIN" | "UNKNOWN",
        "price_limit_pct": 0.10 | 0.20 | 0.05 | None,
        "is_st": False,
        "is_recent_ipo": False,
        "has_price_limit": True | False | None,
        "liquidity_risk": "低" | "中" | "高" | "未知",
    }
```

### 2.2 对技术信号的影响

**A股**：
- 涨停突破 ≠ 自然放量突破，需降级处理
- 跌停破位 ≠ 主动卖盘确认
- ST/科创板/创业板/新股阶段应有不同涨跌停参数
- 涨跌停影响 ATR、K线实体、影线、突破强度

新增特征：
```python
"limit_state": {
    "is_limit_up": False, "is_limit_down": False,
    "near_limit_up": False, "near_limit_down": False,
}
```

**港股**：
- 无统一涨跌停，但流动性不足标的可能出现异常长影线
- 小成交额标的高低点不可靠
- 支撑阻力和影线形态应结合成交额过滤

新增特征：
```python
"liquidity_filter": {
    "turnover_ma20": ...,
    "is_low_liquidity": True | False,
    "extreme_wick_reliable": True | False,
}
```

---

## 3. 指标层升级

### 3.1 原有字段保留

`close`, `volume`, `macd`, `macd_signal`, `macd_hist`, `rsi_14`, `adx`, `plus_di`, `minus_di`, `ma_5`, `ma_10`, `ma_20`, `ma_60`, `boll_upper`, `boll_mid`, `boll_lower`, `williams_r`, `stoch_rsi_k`, `stoch_rsi_d`

### 3.2 新增中期趋势字段

```python
indicators.update({
    # BIAS
    "bias_5", "bias_10", "bias_20",
    "bias_5_extreme_high", "bias_5_extreme_low",
    "bias_10_extreme_high", "bias_10_extreme_low",

    # BOLL
    "boll_width", "boll_width_ma5", "boll_state",

    # MA direction
    "ma20_direction", "ma60_direction",

    # Weekly
    "weekly_close", "weekly_ma5", "weekly_ma10", "weekly_ma20", "weekly_trend",

    # ATR
    "atr_14",
})
```

---

## 4. 核心指标计算

### 4.1 BIAS（防 look-ahead）

```python
def compute_bias(df: pd.DataFrame, windows=(5, 10, 20), lookback=120) -> dict:
    close = df["close"].astype(float)
    out = {}
    for n in windows:
        ma = close.rolling(n, min_periods=n).mean()
        bias = (close / ma - 1.0) * 100
        cur = bias.iloc[-1]
        out[f"bias_{n}"] = None if pd.isna(cur) else round(float(cur), 2)
        if n in (5, 10):
            # 用 shift(1) 避免 look-ahead
            hist = bias.shift(1).rolling(lookback, min_periods=min(60, lookback))
            prev_max = hist.max().iloc[-1]
            prev_min = hist.min().iloc[-1]
            out[f"bias_{n}_extreme_high"] = bool(pd.notna(cur) and pd.notna(prev_max) and cur > prev_max)
            out[f"bias_{n}_extreme_low"] = bool(pd.notna(cur) and pd.notna(prev_min) and cur < prev_min)
    return out
```

### 4.2 BOLL 状态（前5日均宽不含当天）

```python
def compute_boll_state(df: pd.DataFrame) -> dict:
    upper, mid, lower = df["boll_upper"], df["boll_mid"].replace(0, np.nan), df["boll_lower"]
    width = (upper - lower) / mid
    width_ma5_prev = width.shift(1).rolling(5, min_periods=5).mean()
    cur_width = width.iloc[-1]
    ref_width = width_ma5_prev.iloc[-1]
    if pd.isna(cur_width) or pd.isna(ref_width):
        state = "未知"
    elif cur_width > ref_width * 1.2:
        state = "开口"
    elif cur_width < ref_width * 0.8:
        state = "缩口"
    else:
        state = "正常"
    return {
        "boll_width": None if pd.isna(cur_width) else round(float(cur_width), 4),
        "boll_width_ma5": None if pd.isna(ref_width) else round(float(ref_width), 4),
        "boll_state": state,
    }
```

### 4.3 K线特征（归一化）

```python
def compute_candle_features(df: pd.DataFrame, atr: pd.Series | None = None) -> dict:
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
```

---

## 5. 周线趋势判定

### 5.1 周线优先原则

```text
第一层：周线大背景
第二层：日线 MA20/MA60 结构
第三层：平台、通道、箱体
第四层：MACD / RSI / BIAS / BOLL 辅助确认
```

### 5.2 周线状态定义

```text
单边上涨：
- 近6周中至少5周收盘价位于周MA5和MA10之上
- 周线 MA5 > MA10 > MA20
- MA5、MA10 斜率为正，均线发散

单边下跌：
- 近6周中至少5周收盘价位于周MA5和MA10之下
- 周线 MA5 < MA10 < MA20
- MA5、MA10 斜率为负

震荡：
- 近10周收盘价多次穿越MA5或MA10
- 或 MA5与MA10差值 < 2%
- 或价格反复围绕MA20波动

趋势修复中：
- 此前下跌或震荡，当前重新站上周MA10或MA20
- 但均线尚未形成稳定多头排列
```

### 5.3 推荐实现

```python
def compute_weekly_trend(df_weekly: pd.DataFrame) -> dict:
    close = df_weekly["close"].astype(float)
    ma5 = close.rolling(5, min_periods=5).mean()
    ma10 = close.rolling(10, min_periods=10).mean()
    ma20 = close.rolling(20, min_periods=20).mean()

    if len(df_weekly) < 20:
        return {"weekly_trend": "未知", "weekly_close": float(close.iloc[-1]),
                "weekly_ma5": None, "weekly_ma10": None, "weekly_ma20": None}

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
            if (close.iloc[i - 1] - ma.iloc[i - 1]) * (close.iloc[i] - ma.iloc[i]) < 0:
                crossed = True
        if crossed:
            cross_count += 1

    ma5_ma10_gap = abs(ma5.iloc[-1] - ma10.iloc[-1]) / ma10.iloc[-1]

    is_uptrend = (above_ma5_ma10_count >= 5 and ma_order_up and ma5_slope_4w > 0 and ma10_slope_4w > 0)
    is_downtrend = (below_ma5_ma10_count >= 5 and ma_order_down and ma5_slope_4w < 0 and ma10_slope_4w < 0)
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
        "weekly_close": round(float(close.iloc[-1]), 4),
        "weekly_ma5": round(float(ma5.iloc[-1]), 4),
        "weekly_ma10": round(float(ma10.iloc[-1]), 4),
        "weekly_ma20": round(float(ma20.iloc[-1]), 4),
        "weekly_trend_evidence": {
            "weeks_above_ma5_ma10": int(above_ma5_ma10_count),
            "weeks_below_ma5_ma10": int(below_ma5_ma10_count),
            "ma_order": "MA5>MA10>MA20" if ma_order_up else "MA5<MA10<MA20" if ma_order_down else "均线未形成顺序排列",
            "ma5_slope_4w": round(float(ma5_slope_4w), 4),
            "ma10_slope_4w": round(float(ma10_slope_4w), 4),
            "cross_count_10w": int(cross_count),
            "ma5_ma10_gap": round(float(ma5_ma10_gap), 4),
        }
    }
```

---

## 6. 日线结构判定

### 6.1 MA 权重调整

```text
MA5：短线节奏线
MA10：短线节奏确认线
MA20：中期趋势生命线
MA60：中期结构分界线
```

信号解释：
```text
跌破MA5：短线回撤，不改变中期判断
跌破MA10：短期节奏转弱
跌破MA20：中期趋势进入观察
跌破MA60：中期趋势结构破坏
跌破周MA10/MA20：更高级别趋势失效
```

### 6.2 MA 方向

```python
def compute_ma_direction(ma: pd.Series, lookback: int = 5, flat_threshold: float = 0.005) -> str:
    if len(ma) < lookback + 1:
        return "未知"
    cur, prev = ma.iloc[-1], ma.iloc[-lookback - 1]
    if pd.isna(cur) or pd.isna(prev) or prev == 0:
        return "未知"
    change = cur / prev - 1
    if change > flat_threshold:
        return "向上"
    elif change < -flat_threshold:
        return "向下"
    else:
        return "走平"
```

### 6.3 有效突破/跌破（去抖动）

```text
有效突破：
1. 连续2~3日收盘站上关键均线或平台上沿；或
2. 单日突破幅度 > 1 ATR；或
3. 突破同时成交额 > 20日均成交额的1.3倍。

有效跌破：
1. 连续2~3日收盘跌破关键均线或平台下沿；或
2. 单日跌破幅度 > 1 ATR；或
3. 跌破同时成交额 > 20日均成交额的1.3倍。
```

---

## 7. 趋势状态机

### 7.1 不再以买卖信号为核心

原设计中的 `core_signal: 买入信号/加仓信号/警惕/破位信号` 升级为：

```python
"trend_state": {
    "primary_state": "上升趋势" | "震荡趋势" | "下降趋势" | "趋势修复中",
    "stage": "启动期" | "主升期" | "加速期" | "高位钝化期" | "转弱期" | "破坏期" | "盘整期",
    "action_hint": "观察" | "趋势确认" | "持有跟踪" | "降低预期" | "趋势失效",
    "state_changed": True | False,
    "previous_state": "...",
}
```

### 7.2 状态判定逻辑

```python
def classify_trend_state(weekly_trend: str, daily_structure: dict, indicators: dict, divergence: dict | None) -> dict:
    ...
```

规则骨架：
```text
上升趋势：
- 周线为单边上涨或趋势修复中
- 日线位于MA20上方
- MA20向上，MA60走平或向上

启动期：周线刚从震荡/下跌进入修复，日线突破平台或站上MA60，均线刚开始多头排列
主升期：周线MA5>MA10>MA20，日线MA20/MA60向上，价格沿MA20上行，无加速或背离
加速期：BOLL开口扩大，连续大阳线，价格显著远离MA20，成交额放大
高位钝化期：RSI高位钝化，BIAS偏高或极值，价格仍在MA20上方，不直接判断趋势结束
转弱期：日线跌破MA20或多次回踩MA20，MA20走平，MACD柱体走弱，成交额无法确认
破坏期：日线有效跌破MA60，或周线收盘跌破周MA10/MA20，或跌破重要平台下沿
```

---

## 8. 趋势健康度评分

```python
"trend_health": {
    "score": 72,            # 0-100
    "grade": "健康",       # 健康/偏强/转弱/失效
    "summary": "...",
    "components": {
        "weekly_structure": 25,
        "daily_ma_alignment": 20,
        "price_structure": 12,
        "volume_confirmation": 8,
        "volatility_condition": 7,
        "overextension_penalty": -5,
        "divergence_penalty": -3,
    },
    "deductions": ["BIAS偏高", "RSI高位钝化"],
}
```

权重：周线结构30%，日线MA20/MA60状态25%，价格结构15%，成交量确认10%，波动率10%，背离/过热惩罚10%。

分层：80-100趋势强健，65-79健康，50-64转弱观察，30-49破坏风险高，0-29趋势失效。

---

## 9. 趋势失效条件

```python
"invalidation": {
    "soft_warning": "日线连续3日收盘跌破MA20",
    "hard_invalid": "周线收盘跌破MA10，或日线有效跌破MA60",
    "structure_break": "跌破前期平台下沿",
    "current_distance_to_invalid": "4.8%",
}
```

---

## 10. 支撑阻力 / 关键区域识别

### 10.1 输出区间

```python
"support_zone": {
    "price": 45.2, "zone_low": 44.8, "zone_high": 45.6,
    "strength": "强", "touches": 5, "last_touched_at": "2026-05-21",
}
```

### 10.2 分箱逻辑（ATR 分箱 + 百分比兜底）

```python
bin_size = max(close.iloc[-1] * 0.005, atr_14.iloc[-1] * 0.5)
bucket = round(price / bin_size)
```

### 10.3 有效触及定义

1. 局部高点或低点
2. 触及后反向运行 ≥2% 或 ≥1 ATR
3. 至少3次有效触及
4. 成交额不能过低
5. 港股低流动性标的降低强度评级

---

## 11. 背离扫描

### 11.1 背离作为预警，不改变趋势判断

强趋势中 RSI超买/MACD背离/BIAS偏高，不单独构成趋势结束；只有背离 + 跌破MA20/MA60/周线转弱同时出现，才升级风险等级。

### 11.2 基于 swing high / swing low

1. 找最近两个有效摆动高点或低点
2. 当前高点需右侧2~3根K线确认
3. 比较价格、MACD DIF、MACD hist、RSI、BOLL上轨变化
4. 至少满足2/3条件才输出背离预警
5. 输出 evidence，便于报告解释和测试

### 11.3 布林超轨与背离分离

```python
"boll_overextension": True | False,
"boll_divergence": True | False,
```

---

## 12. 辅助指标解释原则

**MACD**：只作趋势确认，不独立决策。金叉=趋势修复或延续确认，死叉=动能减弱但不等于趋势失效，背离=风险预警需均线破位确认。

**RSI**：高位不直接看空。RSI>70=强势或轻度过热，RSI>80=严重过热，RSI>70且持续=强势钝化，RSI高位拐头+BIAS极值+顶背离=风险预警升级。

**BIAS**：衡量偏离和过热，不直接生成买卖信号。BIAS偏高=短线追高性价比下降，BIAS创120日高位极值=中期过热预警，BIAS回落但价格不破MA20=健康消化，BIAS回落且跌破MA20=趋势转弱。

**BOLL**：开口=趋势加速波动扩大，缩口=等待方向选择，价格贴上轨=强势不直接看空，价格远离上轨+BIAS极值+背离=过热预警，跌破中轨=趋势节奏转弱，跌破下轨=异常弱势或恐慌需结合MA60/周线判断。

---

## 13. 假突破风控

### 13.1 状态机替代4日推断

```python
"signal_state": {
    "current": "breakout_confirmed" | "breakout_watch" | "pullback_after_breakout" | "breakout_failed",
    "since": "2026-06-03",
    "days_in_state": 3,
    "prev_state": "watching",
    "invalidated": False,
    "invalidation_price": 46.8,
}
```

若无持久化能力：
```python
"fake_breakout_stage": {
    "stage": "day2_pullback",
    "inferred": True,
    "evidence": "昨日突破，今日收盘跌回 MA5 下方",
    "needs_persistence": True,
}
```

---

## 14. 形态识别优先级

中期系统优先实现：
1. 平台整理
2. 箱体震荡
3. 上升通道
4. 下降通道
5. 箱体突破
6. 平台跌破

复杂形态（头肩顶/双底）后置，只输出候选+置信度+等待确认。

```python
"structure": {
    "type": "上升通道" | "平台整理" | "箱体震荡" | "破位下行" | "无明显结构",
    "range_high": 52.8, "range_low": 45.2, "days_in_range": 36,
    "breakout_status": "未突破" | "有效突破" | "假突破" | "跌破",
}
```

---

## 15. 升级后的 `_resonance` 结构

```python
_resonance = {
    # backward compatibility
    "trend": "多头", "momentum": "偏强", "volume_price": "确认",
    "composite_score": 6.8, "signals": [...],

    # new medium-term trend system
    "analysis_horizon": "中期（日线-周线）",
    "trend_state": {
        "primary_state": "上升趋势", "stage": "主升期",
        "action_hint": "持有跟踪", "state_changed": False,
        "previous_state": "上升趋势",
        "summary": "周线多头结构完整，日线仍位于 MA20 上方，中期趋势尚未破坏。",
    },
    "weekly_background": {
        "trend": "单边上涨", "ma_structure": "MA5>MA10>MA20",
        "weekly_close_position": "站上MA10",
        "evidence": {...},
    },
    "daily_structure": {
        "ma20_direction": "向上", "ma60_direction": "向上",
        "price_vs_ma20": "站上", "price_vs_ma60": "站上",
        "structure_type": "上升通道", "boll_state": "开口",
        "price_position": "中轨与上轨之间",
    },
    "trend_health": {
        "score": 72, "grade": "健康",
        "summary": "周线结构完整，日线趋势仍在 MA20 上方运行。",
        "components": {...}, "deductions": ["BIAS偏高", "RSI高位钝化"],
    },
    "key_levels": {
        "support_zone": {...}, "resistance_zone": {...},
        "medium_term_invalid": 43.8,
    },
    "invalidation": {
        "soft_warning": "日线连续3日收盘跌破MA20",
        "hard_invalid": "周线收盘跌破MA10，或日线有效跌破MA60",
        "structure_break": "跌破前期平台下沿",
        "current_distance_to_invalid": "4.8%",
    },
    "advisors": {
        "macd": {"state": "多头延续", "meaning": "仅作趋势确认"},
        "rsi": {"value": 76.2, "state": "强势钝化", "meaning": "不单独构成卖出信号"},
        "bias": {"state": "偏高但未极端", "meaning": "短线追高性价比下降"},
        "boll": {"state": "开口扩张", "meaning": "趋势加速同时波动加大"},
    },
    "divergence_scan": None,     # 条件启用
    "sell_assessment": None,     # 条件启用
    "basis_rules": [...],
    "risk_reminder": "本模块用于日线—周线级别的中期趋势提醒，不用于日内或短线高频择时。",
}
```

---

## 16. 主入口

```python
def advanced_medium_term_resonance(
    df_daily: pd.DataFrame,
    df_weekly: pd.DataFrame,
    quote: dict | None = None,
    previous_state: dict | None = None,
) -> dict:
    """
    中期趋势技术分析主入口。
    输入：
    - df_daily: 日线 OHLCV，推荐 ≥250 根
    - df_weekly: 周线 OHLCV，推荐 ≥60 根
    - quote: 可选，用于市场、估值、成交额、板块信息
    - previous_state: 可选，用于状态机连续跟踪
    输出：完整 _resonance 结构
    """
```

主流程：
1. 检查数据质量
2. 推断 market_context
3. 计算基础指标（MA、MACD、RSI、BOLL、BIAS、ATR）
4. 计算 K线特征、成交量特征、涨跌停特征
5. 计算周线趋势
6. 计算日线结构
7. 识别关键支撑/阻力区间
8. 识别平台/箱体/通道结构
9. 扫描背离与过热
10. 判断趋势状态机
11. 计算趋势健康度
12. 生成趋势失效条件
13. 条件生成卖出三要素
14. 组装 _resonance
15. 回写 backward compatible 字段

---

## 17. 卖出三要素调整

触发条件（满足任一即计算）：
1. 趋势状态进入"转弱期"或"破坏期"
2. 日线有效跌破 MA20 或 MA60
3. 周线跌破 MA10 或 MA20
4. RSI > 80 且拐头向下
5. BIAS(5) 或 BIAS(10) 创 120 日高位极值
6. 出现中度以上顶背离

输出结论：
- RSI 超买不单独判定卖出
- BIAS 偏高不单独判定卖出
- 必须结合趋势结构和均线失效

---

## 18. TechnicalRenderer 新模板

### 18.1 降级策略

```text
如果 _resonance 包含 trend_state / trend_health / invalidation：
    使用中期趋势新版模板
否则：
    使用旧版技术指标快照模板
```

### 18.2 新版报告模板

```markdown
## 技术面分析：中期趋势提醒

**分析周期**：日线—周线级别，中期趋势跟踪，不用于日内或短线高频择时。

### 1. 趋势背景
- 周线状态：【单边上涨 / 单边下跌 / 震荡 / 趋势修复中】
- 周线均线结构：【MA5>MA10>MA20 / 均线缠绕 / MA5<MA10<MA20】
- 日线结构：【上升通道 / 平台整理 / 箱体震荡 / 破位下行 / 无明显结构】
- MA20 方向：【向上 / 向下 / 走平】
- MA60 方向：【向上 / 向下 / 走平】

### 2. 当前趋势状态
- 趋势状态：【上升趋势 / 震荡趋势 / 下降趋势 / 趋势修复中】
- 趋势阶段：【启动期 / 主升期 / 加速期 / 高位钝化期 / 转弱期 / 破坏期 / 盘整期】
- 技术动作提示：【观察 / 趋势确认 / 持有跟踪 / 降低预期 / 趋势失效】
- 简要说明：【summary】

### 3. 趋势健康度
- 趋势健康度：【72/100】
- 状态评级：【健康 / 偏强 / 转弱 / 失效】
- 主要支撑因素：【周线结构完整、日线仍在 MA20 上方】
- 主要扣分因素：【BIAS 偏高、RSI 高位钝化】

### 4. 关键观察区域
- 支撑区：【44.8 - 45.6】（强）
- 压力区：【52.4 - 53.1】（中）
- 中期失效参考位：【43.8】

### 5. 趋势失效条件
- 第一警戒：【日线连续 3 日收盘跌破 MA20】
- 中期失效：【周线收盘跌破 MA10，或日线有效跌破 MA60】
- 结构破坏：【跌破前期平台下沿】

### 6. 谋士团扫描
- MACD：【多头延续，仅作趋势确认】
- RSI：【76.2，强势钝化；强趋势中不单独构成卖出信号】
- BIAS：【偏高但未极端；短线追高性价比下降】
- BOLL：【开口扩张；趋势加速，同时波动加大】

### 7. 背离 / 过热预警（条件启用）
【三重顶背离 / BIAS 极值 / RSI 严重超买 / BOLL 过度扩张】
处置方式：均线为王，仅作中期风险预警；需等待 MA20 / MA60 / 周线结构确认

### 8. 卖出三要素评估（条件启用）
- 估值定价状态：【N/A】
- 均线信号状态：【跌破 MA20 但未跌破 MA60】
- 强弱偏离度状态：【BIAS(5) 创 120 日高位极值】
- 结论：【趋势进入风险观察，不等同于立即卖出】

### 9. 依据规则
- 周线优先原则
- MA20/MA60 中期结构判定
- 有效突破/跌破去抖动规则
- 均线为王，谋士辅助

### 10. 风险提示
本模块用于日线—周线级别的中期趋势提醒，不用于日内或短线高频择时。技术信号应与基本面、估值、行业景气度和市场环境结合使用。
```

---

## 19. 编码实现顺序

| Phase | 内容 | 文件 |
|---|---|---|
| P1 | 数据结构 + meta + market_context + 基础指标（BIAS、BOLL width、ATR、MA方向） | `technical_analyzer.py` |
| P2 | 周线趋势 `compute_weekly_trend()` + 日线结构 `compute_daily_structure()` | `technical_analyzer.py` |
| P3 | 趋势状态机 `classify_trend_state()` | `technical_analyzer.py` |
| P4 | 趋势健康度 `compute_trend_health()` | `technical_analyzer.py` |
| P5 | 支撑阻力区间（ATR分箱、有效触及、强度评级） | `technical_analyzer.py` |
| P6 | 背离扫描（swing high/low、2/3触发、evidence输出） | `technical_analyzer.py` |
| P7 | `TechnicalRenderer` 新模板 + 降级逻辑 | `technical_renderer.py` |
| P8 | 端到端测试（真实A股/港股/指数/边界样本） | `tests/reporter/` |
| P9 | 旧结构兼容测试（确保雷达图不受影响） | `tests/reporter/` |

---

## 20. 测试策略

### 20.1 推荐测试文件

```text
tests/reporter/test_bias_computation.py
tests/reporter/test_boll_state.py
tests/reporter/test_weekly_trend.py
tests/reporter/test_daily_structure.py
tests/reporter/test_trend_state_machine.py
tests/reporter/test_trend_health.py
tests/reporter/test_support_resistance.py
tests/reporter/test_triple_divergence.py
tests/reporter/test_effective_breakout_breakdown.py
tests/reporter/test_market_context.py
tests/reporter/test_technical_renderer.py
```

### 20.2 必测场景

1. BIAS 计算正确
2. BIAS 极值不使用当天数据（防 look-ahead）
3. BOLL 开口/缩口前5日均宽不含当天
4. 周线单边上涨/单边下跌/震荡/趋势修复中
5. 日线站上/跌破 MA20/MA60
6. 上升趋势启动期/主升期/加速期/高位钝化期/转弱期/破坏期
7. 支撑阻力 ATR 分箱正确
8. 港股低流动性长影线不误判强阻力
9. A股涨停突破不误判为自然突破
10. MACD 背离 2/3 触发，0/3 不触发
11. RSI 高位钝化不单独触发卖出
12. BIAS 高位极值只触发过热预警
13. 新版 renderer 渲染完整
14. 旧版 `_resonance` 自动降级
15. 数据不足时不抛异常并输出限制说明

### 20.3 边界条件

- **数据不足**：日线<120根或周线<20根时降级说明
- **复权问题**：raw price 时提示可靠性下降
- **停牌与缺失**：影响 ATR、成交量均值时记录 limitations
- **涨跌停**：涨停突破降级为"需观察后续是否打开空间"
- **低流动性**：港股支撑阻力强度下调一级

---

## 21. 最终设计原则

```text
1. 周线优先，日线确认。
2. MA20/MA60 是中期核心，MA5/MA10 只是节奏线。
3. 技术分析输出趋势状态，不输出机械买卖指令。
4. RSI、BIAS、MACD、BOLL 是谋士，不是主帅。
5. 背离和过热只做预警，不直接否定趋势。
6. 趋势失效条件必须清晰。
7. 有效突破/跌破必须去抖动。
8. 支撑阻力应输出区间，不输出神奇点位。
9. A股/港股市场机制差异必须进入算法层。
10. 所有结论都应有 evidence，方便 debug、测试和报告解释。
```

---

*设计日期：2026-06-08*
*关联文件：`scripts/utils/reporter/technical_analyzer.py`, `scripts/utils/reporter/sections/technical_renderer.py`*
