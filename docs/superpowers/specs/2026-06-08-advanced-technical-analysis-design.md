# A股/港股选股报告技术分析模块升级方案：中期趋势提醒版 v2.1

> **定位**：日线—周线级别的中期趋势提醒系统，不是短线择时系统，也不是机械买卖信号系统。
>
> 核心原则：`周线定背景，日线做确认；MA20/MA60 定中期结构，MA5/MA10 只看短期节奏；均线为王，谋士辅助；少触发，慢确认，强解释，重失效条件；所有趋势结论必须有 evidence 支撑。`

---

## 1. Pipeline 与兼容策略

### 1.1 Pipeline 不变

现有执行顺序保持不变：

```text
technical_fetching_skill → TechnicalAnalysisSkill → ReportAssemblySkill
```

继续保留 `stock_raw["technical"]["indicators"]` 作为旧版核心数据载体。

现有 `_resonance` 中以下字段必须保留：

```python
_resonance = {
    "trend": ...,
    "momentum": ...,
    "volume_price": ...,
    "composite_score": ...,
    "signals": ...,
}
```

说明：`composite_score` 继续供五维雷达图使用。新版结构必须 backward compatible，旧版报告不得因为新增字段而报错。

---

## 2. 总体数据结构

### 2.1 推荐内部结构

```python
stock_raw["technical"] = {
    "indicators": {...},      # 纯数值指标：MA、MACD、RSI、BIAS、BOLL、ATR 等
    "features": {...},        # 中间特征：K线实体、影线、穿越、突破、放量等
    "analysis": {
        "_resonance": {...},  # 技术解释结构
        "_patterns": [...],
        "_levels": {...},
    },
    "meta": {...},            # 市场类型、数据质量、schema 版本等
}
```

兼容策略：`analysis["_resonance"]` 镜像写回 `indicators["_resonance"]`，旧代码无需改动。

### 2.2 meta 字段

```python
"meta": {
    "schema_version": "technical.v2.1.medium_term",
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
        "has_zero_volume": False,
        "limitations": [],
    }
}
```

数据长度要求：日线最低120根（推荐250），周线最低20根（推荐60）。数据不足时系统不得报错，应降级输出。

---

## 3. 阈值配置文件

### 3.1 新增 technical_config.yaml

所有阈值必须集中配置，不要散落在函数中写死：

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

### 3.2 配置读取要求

```python
def load_technical_config(path: str | None = None) -> dict:
    ...
```

要求：不因 config 缺失导致系统失败；所有核心阈值优先读取 config；单元测试可传入 test config 覆盖边界条件。

---

## 4. 市场上下文：A股/港股差异

### 4.1 market_context

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

### 4.2 A股处理原则

涨停突破 ≠ 自然放量突破；跌停破位 ≠ 主动卖盘确认；涨跌停影响 ATR、K线实体、影线、突破强度。

新增特征：
```python
"limit_state": {
    "is_limit_up": False, "is_limit_down": False,
    "near_limit_up": False, "near_limit_down": False,
}
```

涨停型突破降级表达为：`涨停型突破，需观察后续是否打开空间并站稳关键均线。`

### 4.3 港股处理原则

无统一涨跌停；低流动性标的可能出现异常长影线；支撑阻力必须结合成交额过滤。

新增特征：
```python
"liquidity_filter": {
    "turnover_ma20": ...,
    "is_low_liquidity": True | False,
    "extreme_wick_reliable": True | False,
}
```

低流动性时：支撑阻力强度下调一级；长影线形态不单独作为强信号；analysis_confidence 下调。

---

## 5. 指标层升级

### 5.1 原有字段保留

`close`, `volume`, `macd`, `macd_signal`, `macd_hist`, `rsi_14`, `adx`, `plus_di`, `minus_di`, `ma_5`, `ma_10`, `ma_20`, `ma_60`, `boll_upper`, `boll_mid`, `boll_lower`, `williams_r`, `stoch_rsi_k`, `stoch_rsi_d`

### 5.2 新增字段

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

    # 成交额（优先于 volume）
    "amount", "amount_ma20", "turnover_ma20",
})
```

**成交额字段优先级**：
1. 若数据源提供 `amount` / `turnover`（元），优先使用成交额做确认；
2. 若不存在，降级使用 `volume`（股）× `close` 估算成交额；
3. 估算值在报告中不直接显示，仅用于内部突破/跌破确认逻辑。

---

## 6. 核心指标计算

### 6.1 BIAS（防 look-ahead）

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
            hist = bias.shift(1).rolling(lookback, min_periods=min(60, lookback))
            prev_max = hist.max().iloc[-1]
            prev_min = hist.min().iloc[-1]
            out[f"bias_{n}_extreme_high"] = bool(pd.notna(cur) and pd.notna(prev_max) and cur > prev_max)
            out[f"bias_{n}_extreme_low"] = bool(pd.notna(cur) and pd.notna(prev_min) and cur < prev_min)
    return out
```

要求：bias_extreme 必须拆分为 high / low；BIAS 高位极值只表示过热预警，不单独构成卖出；BIAS 低位极值只表示超跌或修复观察，不单独构成买入。

### 6.2 BOLL 状态（前 5 日均宽不含当天）

```python
def compute_boll_state(df: pd.DataFrame, config: dict) -> dict:
    upper = df["boll_upper"]
    mid = df["boll_mid"].replace(0, np.nan)
    lower = df["boll_lower"]
    width = (upper - lower) / mid
    width_ma5_prev = width.shift(1).rolling(
        config["technical"]["boll"]["width_ma_window"],
        min_periods=config["technical"]["boll"]["width_ma_window"],
    ).mean()
    cur_width = width.iloc[-1]
    ref_width = width_ma5_prev.iloc[-1]
    if pd.isna(cur_width) or pd.isna(ref_width):
        state = "未知"
    elif cur_width > ref_width * config["technical"]["boll"]["open_ratio"]:
        state = "开口"
    elif cur_width < ref_width * config["technical"]["boll"]["squeeze_ratio"]:
        state = "缩口"
    else:
        state = "正常"
    return {
        "boll_width": None if pd.isna(cur_width) else round(float(cur_width), 4),
        "boll_width_ma5": None if pd.isna(ref_width) else round(float(ref_width), 4),
        "boll_state": state,
    }
```

### 6.3 K线特征（归一化）

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

## 7. 周线趋势判定

### 7.1 周线优先原则

```text
第一层：周线大背景
第二层：日线 MA20/MA60 结构
第三层：平台、通道、箱体
第四层：MACD / RSI / BIAS / BOLL 辅助确认
```

### 7.2 周线状态定义

```text
单边上涨：近6周中至少5周收盘价位于周MA5和MA10之上；MA5>MA10>MA20；MA5/MA10斜率为正
单边下跌：近6周中至少5周收盘价位于周MA5和MA10之下；MA5<MA10<MA20；MA5/MA10斜率为负
震荡：近10周收盘价多次穿越MA5或MA10；或MA5与MA10差值<2%；或价格反复围绕MA20波动
趋势修复中：此前下跌或震荡，当前重新站上周MA10或MA20，但均线尚未形成稳定多头排列
```

### 7.3 输出 evidence

`compute_weekly_trend()` 必须返回 evidence：

```python
"weekly_trend_evidence": {
    "weeks_above_ma5_ma10": 5,
    "weeks_below_ma5_ma10": 0,
    "ma_order": "MA5>MA10>MA20",
    "ma5_slope_4w": 0.032,
    "ma10_slope_4w": 0.018,
    "cross_count_10w": 1,
    "ma5_ma10_gap": 0.024,
}
```

---

## 8. 日线结构判定

### 8.1 MA 权重

```text
MA5：短线节奏线
MA10：短线节奏确认线
MA20：中期趋势生命线
MA60：中期结构分界线
```

解释规则：跌破MA5=短线回撤；跌破MA10=短期节奏转弱；跌破MA20=中期趋势进入观察；跌破MA60=中期趋势结构破坏；跌破周MA10/MA20=更高级别趋势失效。

### 8.2 MA 方向

```python
def compute_ma_direction(ma: pd.Series, lookback: int = 5, flat_threshold: float = 0.005) -> str:
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
```

### 8.3 有效突破/跌破（去抖动）

有效突破：连续2~3日收盘站上关键均线或平台上沿；或单日突破幅度>1 ATR；或突破同时成交额>20日均成交额的1.3倍。

有效跌破：连续2~3日收盘跌破关键均线或平台下沿；或单日跌破幅度>1 ATR；或跌破同时成交额>20日均成交额的1.3倍。

---

## 9. 趋势状态机

### 9.1 核心结构

```python
"trend_state": {
    "primary_state": "上升趋势" | "震荡趋势" | "下降趋势" | "趋势修复中",
    "stage": "启动期" | "主升期" | "加速期" | "高位钝化期" | "转弱期" | "破坏期" | "盘整期",
    "action_hint": "观察" | "趋势确认" | "持有跟踪" | "降低预期" | "趋势失效",
    "state_changed": True | False | None,
    "previous_state": "...",
    "summary": "...",
}
```

### 9.2 状态冲突优先级

当多个状态同时满足时，按以下优先级判定：

```text
1. 破坏期（日线有效跌破MA60，或周线收盘跌破MA10/MA20，或跌破核心平台下沿）
2. 转弱期（日线有效跌破MA20，或MA20走平且多次回踩失败，或MACD/量能明显走弱）
3. 高位钝化期（价格仍在MA20上方，但RSI高位钝化、BIAS极值、BOLL过度扩张、背离预警）
4. 加速期（BOLL开口扩大，价格显著远离MA20，成交额确认）
5. 主升期（周线多头，日线MA20/MA60向上，价格沿MA20上行）
6. 启动期（刚从震荡/下跌修复，重新站上MA60或突破平台）
7. 盘整期/震荡趋势
```

要求：如果同时满足主升期和高位钝化期，应输出高位钝化期；如果同时满足高位钝化期和转弱期，应输出转弱期；如果满足破坏期，破坏期永远优先。

### 9.3 previous_state 持久化格式

主入口支持 `previous_state: dict | None = None`。

状态快照：
```python
"technical_state_snapshot": {
    "code": "00700.HK",
    "as_of": "2026-06-08",
    "trend_state": {"primary_state": "上升趋势", "stage": "主升期"},
    "signal_state": {
        "current": "breakout_confirmed",
        "since": "2026-06-03",
        "days_in_state": 3,
        "invalidation_price": 46.8,
    },
    "key_levels": {
        "support_zone": [44.8, 45.6],
        "resistance_zone": [52.4, 53.1],
    }
}
```

状态变化规则：
```text
previous_state 缺失 → state_changed = None, previous_state = None, fake_breakout_stage.inferred = True
previous_state 存在 → 对比 primary_state/stage/signal_state.current
    若变化 → state_changed = True, previous_state 写入旧状态
    若未变化 → state_changed = False
```

---

## 10. 假突破风控

### 10.1 优先使用状态机

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

### 10.2 无持久化时的降级输出

```python
"fake_breakout_stage": {
    "stage": "day2_pullback",
    "inferred": True,
    "evidence": "昨日突破，今日收盘跌回 MA5 下方",
    "needs_persistence": True,
}
```

要求：没有 previous_state 时，不得假装系统已经持续追踪，必须标记 inferred=True。

---

## 11. 趋势健康度评分

### 11.1 评分结构

```python
"trend_health": {
    "score": 72,
    "grade": "健康" | "偏强" | "转弱" | "失效",
    "summary": "...",
    "components": {
        "weekly_structure": {"score": 25, "max": 30, "evidence": "周线 MA5>MA10>MA20，近6周有5周站上 MA5/MA10"},
        "daily_ma_alignment": {"score": 20, "max": 25, "evidence": "日线位于 MA20/MA60 上方，MA20 向上"},
        "price_structure": {"score": 12, "max": 15, "evidence": "处于上升通道内"},
        "volume_confirmation": {"score": 6, "max": 10, "evidence": "成交额温和放大但未显著突破20日均值"},
        "volatility_condition": {"score": 7, "max": 10, "evidence": "BOLL 开口，趋势波动放大"},
    },
    "penalties": {
        "overextension": {"score": -5, "min": -10, "evidence": "BIAS 偏高"},
        "divergence": {"score": -3, "min": -10, "evidence": "MACD 柱体轻微收缩"},
    },
    "deductions": ["BIAS偏高", "RSI高位钝化"],
}
```

### 11.2 权重与分层

```text
周线趋势结构：30%；日线MA20/MA60状态：25%；价格结构：15%；成交量确认：10%；波动率状态：10%；背离/过热惩罚：10%

80-100：趋势强健；65-79：健康；50-64：转弱观察；30-49：破坏风险高；0-29：趋势失效
```

### 11.3 要求

components 必须有 max；penalties 必须有 min；score 必须 clamp 到 0～100；renderer 可根据 components 和 penalties 自动提取主要支撑/扣分因素。

---

## 12. 分析可信度 analysis_confidence

### 12.1 新增结构

```python
"analysis_confidence": {
    "level": "高" | "中" | "低",
    "reasons": ["日线数据超过250根", "周线数据超过60根", "无明显停牌缺口"],
    "limitations": [],
}
```

### 12.2 降级条件

日线不足120根；周线不足20根；复权状态 unknown/raw；存在停牌/缺失交易日；成交量为0或异常；港股低流动性；A股新股阶段；近期多次涨跌停导致ATR/K线结构失真。

### 12.3 Renderer 表达

```markdown
**分析可信度**：中
限制因素：近期存在缺失交易日，成交量和支撑阻力判断需谨慎。
```

---

## 13. 趋势失效条件

```python
"invalidation": {
    "soft_warning": "日线连续3日收盘跌破MA20",
    "hard_invalid": "周线收盘跌破MA10，或日线有效跌破MA60",
    "structure_break": "跌破前期平台下沿",
    "current_distance_to_invalid": "4.8%",
}
```

要求：soft_warning 是第一警戒；hard_invalid 是中期趋势失效；structure_break 是价格结构破坏；current_distance_to_invalid 衡量距离中期失效位还有多远。报告必须显示趋势失效条件。

---

## 14. 支撑阻力 / 关键区域识别

### 14.1 输出区间

```python
"support_zone": {
    "price": 45.2, "zone_low": 44.8, "zone_high": 45.6,
    "strength": "强", "touches": 5, "last_touched_at": "2026-05-21",
}
```

### 14.2 分箱逻辑（ATR 分箱 + 百分比兜底）

```python
bin_size = max(close.iloc[-1] * bucket_pct, atr_14.iloc[-1] * bucket_atr_multiplier)
bucket = round(price / bin_size)
```

默认 bucket_pct=0.005，bucket_atr_multiplier=0.5。

### 14.3 有效触及

1. 局部高点或低点；2. 触及后反向运行 ≥2% 或 ≥1 ATR；3. 至少3次有效触及；4. 成交额不能过低；5. 港股低流动性标的降低强度评级。

### 14.4 缺失处理

新股、低流动性、历史不足时可能找不到有效支撑/阻力：

```python
"support_zone": None
"resistance_zone": None
```

Renderer 遇到 None 时显示：

```markdown
- 支撑区：暂无可靠支撑区，原因：历史数据不足或有效触及次数不足。
- 压力区：暂无可靠压力区，原因：历史数据不足或有效触及次数不足。
```

---

## 15. 结构识别优先级

中期系统优先识别：平台整理、箱体震荡、上升通道、下降通道、箱体突破、平台跌破。

输出：
```python
"structure": {
    "type": "上升通道" | "平台整理" | "箱体震荡" | "破位下行" | "无明显结构",
    "range_high": 52.8, "range_low": 45.2, "days_in_range": 36,
    "breakout_status": "未突破" | "有效突破" | "假突破" | "跌破",
}
```

复杂形态如头肩顶、双底后置，只输出候选+置信度+等待确认。

---

## 16. 背离扫描

### 16.1 背离只作为预警

强趋势中 RSI超买/MACD背离/BIAS偏高，不单独构成趋势结束；只有背离 + 跌破MA20/MA60/周线转弱同时出现，才升级风险等级。

### 16.2 基于 swing high / swing low

1. 找最近两个有效摆动高点或低点；2. 当前高点需右侧2~3根K线确认；3. 比较价格、MACD DIF、MACD hist、RSI、BOLL上轨变化；4. 至少满足2/3条件才输出背离预警；5. 输出 evidence。

### 16.3 BOLL 超轨与背离分离

```python
"boll_overextension": True | False
"boll_divergence": True | False
```

### 16.4 输出结构

```python
"divergence_scan": {
    "type": "顶背离", "confidence": "中度", "matched": 2, "total": 3,
    "evidence": {
        "price": {"prev_high": 48.2, "cur_high": 50.1},
        "macd": {"prev_dif": 1.21, "cur_dif": 0.96, "hist_shrinking": True},
        "rsi": {"prev_rsi": 76.5, "cur_rsi": 72.1, "turning_down": True},
        "boll": {"prev_upper": 51.3, "cur_upper": 51.5, "boll_divergence": True, "boll_overextension": False},
    },
    "missing": ["RSI未背离"],
    "action": "均线为王，仅作中期风险预警",
}
```

---

## 17. 辅助指标解释原则

**MACD**：金叉=趋势修复或延续确认；死叉=动能减弱但不等于趋势失效；背离=风险预警需均线破位确认。

**RSI**：>70=强势或轻度过热；>80=严重过热；>70且持续=强势钝化；高位拐头+BIAS极值+顶背离=风险预警升级。RSI超买不单独触发卖出。

**BIAS**：偏高=短线追高性价比下降；创120日高位极值=中期过热预警；回落但价格不破MA20=健康消化；回落且跌破MA20=趋势转弱。BIAS偏高不单独触发卖出。

**BOLL**：开口=趋势加速波动扩大；缩口=等待方向选择；贴上轨=强势不直接看空；远离上轨+BIAS极值+背离=过热预警；跌破中轨=节奏转弱；跌破下轨=异常弱势需结合MA60/周线判断。

---

## 18. 卖出三要素评估

### 18.1 触发条件（满足任一即计算）

1. 趋势状态进入"转弱期"或"破坏期"；2. 日线有效跌破MA20或MA60；3. 周线跌破MA10或MA20；4. RSI>80且拐头向下；5. BIAS(5)或BIAS(10)创120日高位极值；6. 出现中度以上顶背离。

### 18.2 输出结构

```python
"sell_assessment": {
    "valuation": "N/A",
    "ma_signal": "跌破MA20但未跌破MA60",
    "deviation": "BIAS(5)创120日高位极值",
    "trend_state": "转弱期",
    "conclusion": "趋势进入风险观察，不等同于立即卖出；若进一步跌破MA60则视为中期趋势破坏。",
}
```

### 18.3 原则

RSI超买不单独判定卖出；BIAS偏高不单独判定卖出；MACD背离不单独判定卖出；必须结合趋势结构和均线失效。

---

## 19. 市场环境接口：预留但不强依赖

### 19.1 新增 market_regime

```python
def compute_market_regime(index_daily: pd.DataFrame | None = None, sector_daily: pd.DataFrame | None = None) -> dict:
    return {
        "market_trend": "强势" | "震荡" | "弱势" | "未知",
        "sector_trend": "强势" | "震荡" | "弱势" | "未知",
        "relative_strength": "强于大盘" | "弱于大盘" | "同步" | "未知",
    }
```

### 19.2 写入 _resonance

```python
"market_regime": {
    "market_trend": "未知",
    "sector_trend": "未知",
    "relative_strength": "未知",
    "impact": "暂未接入市场/行业数据，本次技术分析仅基于个股自身K线结构。",
}
```

第一版可以全部填"未知"，不影响主流程。

---

## 20. 升级后的 `_resonance` 结构

```python
_resonance = {
    # backward compatibility
    "trend": "多头", "momentum": "偏强", "volume_price": "确认",
    "composite_score": 6.8, "signals": [...],

    # new system
    "analysis_horizon": "中期（日线-周线）",
    "analysis_confidence": {
        "level": "高",
        "reasons": ["日线数据超过250根", "周线数据超过60根"],
        "limitations": [],
    },
    "trend_state": {
        "primary_state": "上升趋势", "stage": "主升期",
        "action_hint": "持有跟踪", "state_changed": False,
        "previous_state": "上升趋势",
        "summary": "周线多头结构完整，日线仍位于 MA20 上方，中期趋势尚未破坏。",
    },
    "signal_state": {
        "current": "breakout_confirmed", "since": "2026-06-03",
        "days_in_state": 3, "prev_state": "watching",
        "invalidated": False, "invalidation_price": 46.8,
    },
    "weekly_background": {
        "trend": "单边上涨", "ma_structure": "MA5>MA10>MA20",
        "weekly_close_position": "站上MA10",
        "evidence": {"weeks_above_ma5_ma10": 5, "cross_count_10w": 1,
                     "ma5_slope_4w": 0.032, "ma10_slope_4w": 0.018},
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
        "components": {
            "weekly_structure": {"score": 25, "max": 30, "evidence": "..."},
            "daily_ma_alignment": {"score": 20, "max": 25, "evidence": "..."},
            "price_structure": {"score": 12, "max": 15, "evidence": "..."},
            "volume_confirmation": {"score": 8, "max": 10, "evidence": "..."},
            "volatility_condition": {"score": 7, "max": 10, "evidence": "..."},
        },
        "penalties": {
            "overextension": {"score": -5, "min": -10, "evidence": "BIAS偏高"},
            "divergence": {"score": -3, "min": -10, "evidence": "MACD柱体轻微收缩"},
        },
        "deductions": ["BIAS偏高", "RSI高位钝化"],
    },
    "key_levels": {
        "support_zone": {"price": 45.2, "zone_low": 44.8, "zone_high": 45.6, "strength": "强", "touches": 5},
        "resistance_zone": {"price": 52.8, "zone_low": 52.4, "zone_high": 53.1, "strength": "中", "touches": 3},
        "medium_term_invalid": 43.8,
    },
    "invalidation": {
        "soft_warning": "日线连续3日收盘跌破MA20",
        "hard_invalid": "周线收盘跌破MA10，或日线有效跌破MA60",
        "structure_break": "跌破前期平台下沿",
        "current_distance_to_invalid": "4.8%",
    },
    "market_regime": {
        "market_trend": "未知", "sector_trend": "未知", "relative_strength": "未知",
        "impact": "暂未接入市场/行业数据，本次技术分析仅基于个股自身K线结构。",
    },
    "advisors": {
        "macd": {"state": "多头延续", "meaning": "仅作趋势确认，不单独构成买入信号"},
        "rsi": {"value": 76.2, "state": "强势钝化", "meaning": "不单独构成卖出信号"},
        "bias": {"state": "偏高但未极端", "meaning": "短线追高性价比下降，但中期趋势未破坏"},
        "boll": {"state": "开口扩张", "meaning": "趋势加速，同时波动加大"},
    },
    "divergence_scan": None,
    "sell_assessment": None,
    "basis_rules": [
        "周线优先原则", "MA20/MA60 中期结构判定",
        "有效突破/跌破去抖动规则", "均线为王，谋士辅助",
    ],
    "risk_reminder": "本模块用于日线—周线级别的中期趋势提醒，不用于日内或短线高频择时。",
}
```

---

## 21. 主入口设计

### 21.1 函数签名

```python
def advanced_medium_term_resonance(
    df_daily: pd.DataFrame,
    df_weekly: pd.DataFrame,
    quote: dict | None = None,
    previous_state: dict | None = None,
    config: dict | None = None,
    market_data: dict | None = None,
) -> dict:
    """中期趋势技术分析主入口。
    输入：df_daily（日线，推荐≥250根）、df_weekly（周线，推荐≥60根）
          quote（可选）、previous_state（可选，状态机连续跟踪）
          config（可选，阈值配置）、market_data（可选，指数/行业数据）
    输出：完整 _resonance 结构
    """
```

### 21.2 主流程

1. 加载 config
2. 检查数据质量
3. 推断 market_context
4. 计算基础指标（MA、MACD、RSI、BOLL、BIAS、ATR）
5. 计算 K线特征、成交量特征、涨跌停特征
6. 计算周线趋势
7. 计算日线结构
8. 识别关键支撑/阻力区间
9. 识别平台/箱体/通道结构
10. 扫描背离与过热
11. 计算 market_regime（缺失则填未知）
12. 按状态优先级判断 trend_state
13. 根据 previous_state 判断 state_changed
14. 生成 signal_state / fake_breakout_stage
15. 计算 trend_health
16. 生成 invalidation
17. 计算 analysis_confidence
18. 条件生成 sell_assessment
19. 组装 _resonance
20. 回写 backward compatible 字段

---

## 22. TechnicalRenderer 升级

### 22.1 降级策略

```text
如果 _resonance 包含 trend_state / trend_health / invalidation：使用中期趋势新版模板
否则：使用旧版技术指标快照模板
```

### 22.2 支持 compact / full 模式

```python
def render_technical_section(resonance: dict, mode: str = "compact") -> str:
    ...
```

默认 mode="compact"。正式报告使用 compact 避免篇幅过长；调试/详细报告使用 full。

### 22.3 compact 模式模板

```markdown
## 技术面分析：中期趋势提醒

当前处于【上升趋势 / 主升期】，趋势健康度【72/100，健康】。周线结构保持多头，日线仍位于 MA20/MA60 上方，中期趋势尚未破坏。

**关键观察位**：
- 支撑区：【44.8 - 45.6】（强）
- 压力区：【52.4 - 53.1】（中）
- 中期失效参考：【43.8】

**趋势失效条件**：
- 第一警戒：【日线连续 3 日收盘跌破 MA20】
- 中期失效：【周线跌破 MA10，或日线有效跌破 MA60】

**主要风险**：【BIAS 偏高，RSI 高位钝化，短线追高性价比下降】

**结论**：趋势仍可跟踪，但不适合将 RSI 超买、BIAS 偏高或 MACD 背离单独视为卖出信号。

**分析可信度**：【高 / 中 / 低】
【如有 limitations，在此显示】
```

### 22.4 full 模式模板

```markdown
## 技术面分析：中期趋势提醒

**分析周期**：日线—周线级别，中期趋势跟踪，不用于日内或短线高频择时。  
**分析可信度**：【高 / 中 / 低】

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
- 主要支撑因素：【由 components 自动生成】
- 主要扣分因素：【由 penalties / deductions 自动生成】

### 4. 关键观察区域
- 支撑区：【44.8 - 45.6】（强）
- 压力区：【52.4 - 53.1】（中）
- 中期失效参考位：【43.8】

### 5. 趋势失效条件
- 第一警戒：【日线连续 3 日收盘跌破 MA20】
- 中期失效：【周线收盘跌破 MA10，或日线有效跌破 MA60】
- 结构破坏：【跌破前期平台下沿】

### 6. 市场环境
- 大盘状态：【强势 / 震荡 / 弱势 / 未知】
- 行业状态：【强势 / 震荡 / 弱势 / 未知】
- 相对强弱：【强于大盘 / 弱于大盘 / 同步 / 未知】

### 7. 谋士团扫描
- MACD：【多头延续，仅作趋势确认】
- RSI：【76.2，强势钝化；强趋势中不单独构成卖出信号】
- BIAS：【偏高但未极端；短线追高性价比下降】
- BOLL：【开口扩张；趋势加速，同时波动加大】

### 8. 背离 / 过热预警（条件启用）

### 9. 卖出三要素评估（条件启用）

### 10. 依据规则
- 周线优先原则
- MA20/MA60 中期结构判定
- 有效突破/跌破去抖动规则
- 均线为王，谋士辅助

### 11. 风险提示
本模块用于日线—周线级别的中期趋势提醒，不用于日内或短线高频择时。
```

---

## 23. 编码实现顺序

| Phase | 内容 | 文件 |
|---|---|---|
| P1 | 新增 `technical_config.yaml` 与 config loader | `technical_analyzer.py` / config |
| P2 | 数据结构 + meta + market_context + analysis_confidence | `technical_analyzer.py` |
| P3 | 基础指标：BIAS、BOLL width、ATR、MA方向 | `technical_analyzer.py` |
| P4 | 周线趋势 `compute_weekly_trend()` + 日线结构 `compute_daily_structure()` | `technical_analyzer.py` |
| P5 | 趋势状态机 `classify_trend_state()` + 状态优先级 | `technical_analyzer.py` |
| P6 | previous_state / signal_state / fake_breakout_stage | `technical_analyzer.py` |
| P7 | 趋势健康度 `compute_trend_health()` | `technical_analyzer.py` |
| P8 | 趋势失效条件 invalidation | `technical_analyzer.py` |
| P9 | 支撑阻力区间（ATR分箱、有效触及、强度评级） | `technical_analyzer.py` |
| P10 | 背离扫描（swing high/low、2/3触发、evidence输出） | `technical_analyzer.py` |
| P11 | market_regime 预留接口 | `technical_analyzer.py` |
| P12 | `TechnicalRenderer` compact/full + 降级逻辑 | `technical_renderer.py` |
| P13 | 单元测试、状态迁移测试、端到端测试 | `tests/reporter/` |
| P14 | 旧结构兼容测试（确保雷达图不受影响） | `tests/reporter/` |

---

## 24. 测试策略

### 24.1 推荐测试文件

```text
tests/reporter/test_config_loader.py
tests/reporter/test_bias_computation.py
tests/reporter/test_boll_state.py
tests/reporter/test_weekly_trend.py
tests/reporter/test_daily_structure.py
tests/reporter/test_trend_state_machine.py
tests/reporter/test_previous_state.py
tests/reporter/test_signal_state.py
tests/reporter/test_trend_health.py
tests/reporter/test_analysis_confidence.py
tests/reporter/test_support_resistance.py
tests/reporter/test_triple_divergence.py
tests/reporter/test_effective_breakout_breakdown.py
tests/reporter/test_market_context.py
tests/reporter/test_market_regime.py
tests/reporter/test_technical_renderer.py
tests/reporter/test_backward_compatibility.py
```

### 24.2 必测场景

1. config 缺失时使用默认配置
2. config 中阈值可覆盖默认值
3. BIAS 计算正确
4. BIAS 极值不使用当天数据（防 look-ahead）
5. BOLL 开口/缩口前5日均宽不含当天
6. 周线单边上涨/单边下跌/震荡/趋势修复中
7. 日线站上/跌破 MA20/MA60
8. 有效突破/有效跌破去抖动
9. 上升趋势启动期/主升期/加速期/高位钝化期/转弱期/破坏期
10. 状态冲突时按优先级输出
11. previous_state 缺失时 state_changed=None
12. previous_state 存在时正确识别 state_changed
13. signal_state 可持续追踪
14. 无 previous_state 时 fake_breakout_stage.inferred=True
15. trend_health 分数在 0～100 之间
16. trend_health components 有 max，penalties 有 min
17. analysis_confidence 根据数据质量降级
18. 支撑阻力 ATR 分箱正确
19. 港股低流动性长影线不误判强阻力
20. A股涨停突破不误判为自然突破
21. MACD 背离 2/3 触发，0/3 不触发
22. RSI 高位钝化不单独触发卖出
23. BIAS 高位极值只触发过热预警
24. compact renderer 渲染完整
25. full renderer 渲染完整
26. 旧版 `_resonance` 自动降级
27. 数据不足时不抛异常并输出限制说明
28. market_regime 缺失时输出未知而不是失败

### 24.3 状态迁移测试

构造连续多日 fixture：Day 1-3 站上MA20（趋势修复中）→ Day 4-6 突破平台（启动期）→ Day 7-9 沿MA20上行（主升期）→ Day 10 BIAS极值但未破MA20（高位钝化期）→ Day 11-13 连续跌破MA20（转弱期）→ Day 14-16 有效跌破MA60（破坏期）。

测试目标：
```python
assert states[3]["stage"] == "启动期"
assert states[8]["stage"] == "主升期"
assert states[10]["stage"] == "高位钝化期"
assert states[13]["stage"] == "转弱期"
assert states[16]["stage"] == "破坏期"
assert states[16]["state_changed"] is True
```

---

## 25. 边界条件

- **数据不足**：日线<120根时 analysis_confidence 降级；周线<20根时 weekly_trend=未知
- **复权问题**：adjustment 为 raw/unknown 时提示可靠性下降
- **停牌与缺失**：记录 data_quality.limitations，影响成交量和波动率指标
- **涨跌停**：涨停突破降级为"需观察后续是否打开空间"
- **低流动性**：港股支撑阻力强度下调一级，analysis_confidence 降级

---

## 26. Agent 验收标准

完成实现后，必须满足：

1. 旧版报告不报错，旧版 `_resonance` 能自动降级渲染
2. 新版 `_resonance` 必须包含 trend_state、trend_health、invalidation、weekly_background、daily_structure、analysis_confidence
3. 所有新增函数在数据不足、NaN、停牌、成交量为0时不抛异常
4. BIAS、BOLL、背离扫描不得使用未来数据
5. 所有阈值必须支持从 technical_config.yaml 读取
6. Renderer 默认使用 compact 模式，full 模式可选
7. 至少通过一只 A股、一只港股、一个指数的端到端报告生成
8. 测试覆盖旧结构兼容、新结构渲染、状态迁移、数据不足、低流动性、涨跌停
9. 输出报告中不得直接把 RSI 超买、BIAS 偏高、MACD 背离单独解释为卖出
10. 所有趋势结论必须能在 evidence、components 或相关字段中找到依据
11. 如果 market_context、market_regime 或 previous_state 缺失，系统应降级输出而不是失败
12. trend_health.score 必须 clamp 到 0～100
13. support/resistance 必须输出区间，不得只输出单点
14. previous_state 缺失时不得伪装成已持续跟踪
15. 雷达图依赖的 composite_score 不受影响

---

## 27. 最终设计原则

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
11. 所有阈值必须配置化，方便后续回测和调参。
12. 状态机必须支持 previous_state，否则只能输出 inferred。
13. Renderer 必须支持 compact/full 两种模式。
14. 工程验收以稳定、可回归、可降级为准，不以指标数量为准。
```

---

## 28. Agent 执行摘要

请按以下顺序实施：

**重要：第一阶段不要实现头肩顶、双底等复杂形态；只实现平台、箱体、通道、突破/跌破。**

1. 新增 technical_config.yaml 和 config loader，统一管理阈值
2. 扩展 technical meta、market_context、analysis_confidence
3. 实现 BIAS、BOLL width、ATR、MA20/MA60 direction，注意防 look-ahead
4. 实现 compute_weekly_trend() 和 compute_daily_structure()
5. 实现 classify_trend_state()，按状态冲突优先级输出唯一阶段
6. 实现 previous_state / signal_state / fake_breakout_stage
7. 实现 compute_trend_health()，components 含 score/max/evidence，penalties 含 score/min/evidence
8. 实现 invalidation，明确 soft_warning / hard_invalid / structure_break
9. 实现 support/resistance zone，使用 ATR 分箱 + 百分比兜底
10. 实现背离扫描，只作为 warning，不改变核心趋势状态
11. 预留 market_regime 接口，缺失时填未知
12. 重写 TechnicalRenderer，默认 compact，支持 full，保留旧结构降级
13. 补齐单元测试、状态迁移测试、边界测试、真实样本端到端测试
14. 确认 backward compatibility，确保 radar图不受影响

---

*设计版本：technical.v2.1.medium_term*
*设计日期：2026-06-08*
*关联文件：scripts/utils/reporter/technical_analyzer.py, scripts/utils/reporter/sections/technical_renderer.py*
