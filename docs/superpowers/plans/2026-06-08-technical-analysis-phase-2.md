# 高级技术分析 Phase 2 改进后实施计划：重构 + 中期趋势体验增强

> For agentic workers: REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task.
>
> 所有步骤使用 checkbox 语法追踪。每个 Task 必须先写测试，再实现，再跑相关测试，再 commit。

---

## 0. Phase 2 总目标

Phase 2 的目标不是继续堆更多技术指标，而是：

1. 将 Phase 1 中已经跑通的高级技术分析逻辑模块化，降低 `technical_analyzer.py` 复杂度。
2. 保持所有 Phase 1 行为不变，保证旧报告、旧 `_resonance`、旧指标字段、雷达图不受影响。
3. 接入几个对报告体验立竿见影的中期趋势增强功能：

   * K线形态辅助信号
   * BIAS 极端值独立预警
   * 假突破 / 假反弹甄别
   * 卖出三要素决策框架
   * 支撑阻力转化
4. 预留大盘 / 板块共振框架，但本阶段不强依赖外部数据。
5. 暂缓复杂高级形态，避免 Phase 2 变成不可控的大重构。

---

## 1. Phase 2 执行范围

### 1.1 本阶段必须完成

```text
Phase 2A：无行为变化的模块拆分
- technical_indicators.py
- technical_structure.py
- technical_state_machine.py
- technical_patterns.py
- 精简 technical_analyzer.py

Phase 2B：报告体验增强
- K线形态辅助信号
- BIAS 极端值独立预警
- 假突破 / 假反弹甄别
- 卖出三要素决策框架
- 支撑阻力转化

Phase 2C：轻量框架预留
- market / sector resonance 框架，占位输出，不强依赖外部数据
```

### 1.2 本阶段暂不执行

以下功能移到 Phase 3，不纳入 Phase 2 验收：

```text
- 三重背离完整版
- 通道盘整识别
- 头肩顶 / 双底复杂形态完善
```

原因：

1. 当前实现草案仍然偏简化，不是真正完整形态识别。
2. 测试与实现存在不一致风险。
3. 这些模块独立性强，适合在 Phase 2 稳定后单独开发。
4. Phase 2 的优先目标是工程结构稳定、可维护、可回归。

---

## 2. 总体架构

### 2.1 拆分目标

当前：

```text
scripts/utils/reporter/technical_analyzer.py
```

职责过多，Phase 2 需要拆为：

```text
scripts/utils/reporter/technical_indicators.py
scripts/utils/reporter/technical_structure.py
scripts/utils/reporter/technical_state_machine.py
scripts/utils/reporter/technical_patterns.py
scripts/utils/reporter/technical_resonance.py
scripts/utils/reporter/technical_analyzer.py
```

### 2.2 模块职责

| 文件                           | 职责                                                     |
| ---------------------------- | ------------------------------------------------------ |
| `technical_indicators.py`    | 基础指标：SMA、EMA、ATR、ADX、MACD、RSI、BOLL、CCI、WR、StochRSI、OBV |
| `technical_structure.py`     | 结构分析：BIAS、BOLL状态、K线特征、MA方向、日线转周线、周线趋势、支撑阻力区间、支撑阻力转化    |
| `technical_state_machine.py` | 趋势状态机、previous_state、健康度评分、失效条件、BIAS极端预警、假突破/假反弹、卖出三要素 |
| `technical_patterns.py`      | 形态与预警：已有 double top/bottom、BOLL overextension、K线位置评估   |
| `technical_resonance.py`     | 大盘/板块共振框架预留                                            |
| `technical_analyzer.py`      | 主入口、组装 `_resonance`、旧兼容 re-export                      |

### 2.3 依赖方向

必须保持单向依赖：

```text
technical_indicators
    -> technical_structure
    -> technical_state_machine
    -> technical_patterns
    -> technical_resonance
    -> technical_analyzer
```

不允许下游模块反向 import 上游主入口。

---

## 3. 关键修正规则

### 3.1 Task 1-5 只做 refactor，不改行为

拆分阶段不得改变 Phase 1 的行为。

要求：

```text
1. 所有 Phase 1 测试必须继续通过。
2. 旧 import 路径必须继续可用。
3. `from technical_analyzer import compute_bias` 这类旧导入必须不破。
4. `technical_analyzer.py` 需要 re-export 旧符号。
5. 拆分完成前不要新增业务逻辑。
```

### 3.2 不删除旧测试

Phase 2 初期不要删除旧测试文件。

错误做法：

```bash
git rm tests/reporter/test_bias_computation.py
git rm tests/reporter/test_boll_state.py
...
```

正确做法：

```text
1. 新增模块级测试。
2. 保留原测试，继续验证 backward compatibility。
3. 全部稳定后再考虑是否清理重复测试。
```

### 3.3 import 需要兼容包运行和脚本运行

新模块内部 import 使用 fallback 形式：

```python
try:
    from .technical_indicators import sma, ema, atr
except ImportError:
    from technical_indicators import sma, ema, atr
```

所有新模块都遵守此规则，避免测试环境和生产包环境 import 不一致。

### 3.4 re-export 简化写法

推荐用 import alias 代替赋值别名，减少视觉噪音：

```python
try:
    from .technical_indicators import (
        sma as _sma, ema as _ema, atr as _atr, adx as _adx,
        cci as _cci, williams_r as _williams_r, stoch_rsi as _stoch_rsi,
        obv as _obv, macd as _macd, bollinger as _bollinger, rsi as _rsi,
    )
except ImportError:
    from technical_indicators import (
        sma as _sma, ema as _ema, atr as _atr, adx as _adx,
        cci as _cci, williams_r as _williams_r, stoch_rsi as _stoch_rsi,
        obv as _obv, macd as _macd, bollinger as _bollinger, rsi as _rsi,
    )
```

这样旧代码 `from technical_analyzer import _sma` / `_sma(series, 5)` 一行不改即可工作。

### 3.5 BOLL 常数序列测试修正

不要用常数价格序列测试 `upper > mid > lower`。

错误测试：

```python
close = pd.Series([100.0] * 30)
upper, mid, lower = bollinger(close, 20, 2)
assert upper.iloc[-1] > mid.iloc[-1] > lower.iloc[-1]
```

因为标准差为 0，三者相等。

正确测试：

```python
close = pd.Series([100.0 + i for i in range(30)])
upper, mid, lower = bollinger(close, 20, 2)
assert upper.iloc[-1] > mid.iloc[-1] > lower.iloc[-1]
```

或者：

```python
assert upper.iloc[-1] >= mid.iloc[-1] >= lower.iloc[-1]
```

优先使用非恒定序列。

### 3.6 `compute_weekly_trend` -> `compute_ma_direction` 依赖

`compute_weekly_trend` 内部调用了 `compute_ma_direction`。Task 2 拆分 `technical_structure.py` 时，两个函数必须一起迁移到同一文件。拆分完成后验证：

```bash
python -c "from technical_structure import compute_weekly_trend, compute_ma_direction; print('OK')"
```

### 3.7 假反弹检测必须使用成交量均值，不得混用成交额

错误：

```python
volume_ma20 = indicators.get("avg_amount_yi", 1) * 100000000
detect_false_rebound(df_recent, boll_state, volume_ma20)
```

因为函数内部比较的是 `df_recent["volume"]`。

正确：

```python
volume_ma20 = float(df_daily["volume"].tail(20).mean())
detect_false_rebound(df_daily.tail(10), boll_state, volume_ma20)
```

如果未来想使用成交额，另开参数：

```python
def detect_false_rebound(
    df_recent: pd.DataFrame,
    boll_state: str,
    volume_ma20: float | None = None,
    amount_ma20: float | None = None,
) -> dict | None:
    ...
```

### 3.8 卖出三要素必须保持"三要素"，不要变成四要素

三要素只能是：

```text
1. 估值定价
2. 均线信号
3. 强弱偏离度
```

RSI 不单独计数，应并入"强弱偏离度"。

正确逻辑：

```python
deviation_extreme = bias_extreme_high or (rsi_value is not None and rsi_value > 80)
```

然后：

```python
if deviation_extreme:
    factors.append("强弱偏离度：BIAS高位极端或RSI严重超买")
```

### 3.9 BIAS 只有高位极值参与卖出三要素

BIAS 低位极值是超跌，不得触发卖出。

`evaluate_bias_extreme()` 必须输出方向：

```python
{
    "direction": "high" | "low",
    "warning": "...",
    "level": "...",
}
```

卖出三要素只接入：

```python
bias_extreme_high = (
    bias_extreme is not None
    and bias_extreme.get("direction") == "high"
)
```

---

## 3.10 增加模块导入冒烟测试

Phase 2 拆分多个模块后，必须验证两种导入方式都可用：

1. 包内相对导入
2. 直接脚本路径导入

新增测试文件：

```text
tests/reporter/test_technical_imports.py
```

测试内容：

```python
def test_import_new_modules():
    import technical_indicators
    import technical_structure
    import technical_state_machine
    import technical_patterns
    import technical_resonance
    import technical_analyzer


def test_import_legacy_symbols_from_analyzer():
    from technical_analyzer import (
        _sma,
        _ema,
        _atr,
        _macd,
        _rsi,
        _bollinger,
        compute_bias,
        compute_boll_state,
        compute_weekly_trend,
        classify_trend_state,
        compute_trend_health,
        detect_boll_overextension,
        analyze,
        advanced_medium_term_resonance,
    )

    assert callable(_sma)
    assert callable(compute_bias)
    assert callable(classify_trend_state)
    assert callable(analyze)
```

验收命令：

```bash
pytest tests/reporter/test_technical_imports.py -v
pytest tests/reporter/ -v
```

---

## 3.11 Phase 2A 增加"无行为变化"快照测试

Phase 2A 的目标是只拆分、不改行为。建议增加一个轻量 schema 快照测试，确保 `analyze(df)` 的核心结构不变。

新增测试（可放在 `test_backward_compatibility.py` 中）：

```python
def test_analyze_schema_stable_after_refactor():
    df = make_sample_daily_df(180)
    result = analyze(df)

    assert "indicators" in result
    assert "resonance" in result
    assert "patterns" in result
    assert "levels" in result

    indicators = result["indicators"]
    resonance = result["resonance"]

    required_indicator_keys = [
        "close", "volume", "macd", "macd_signal", "macd_hist",
        "rsi_14", "adx", "plus_di", "minus_di",
        "ma_5", "ma_10", "ma_20", "ma_60",
        "boll_upper", "boll_mid", "boll_lower", "atr_14",
    ]

    for key in required_indicator_keys:
        assert key in indicators

    required_resonance_keys = [
        "trend", "momentum", "volume_price", "composite_score",
        "signals", "trend_state", "trend_health", "invalidation",
    ]

    for key in required_resonance_keys:
        assert key in resonance
```

要求：

```text
Task 1-5 每完成一个拆分任务后，都必须跑这个测试。
如果该测试失败，说明拆分改变了外部行为，必须先修复再继续。
```

---

## 4. Phase 2A：无行为变化的模块拆分

---

## Task 1：拆分基础指标到 `technical_indicators.py`

### Files

Create:

```text
scripts/utils/reporter/technical_indicators.py
```

Modify:

```text
scripts/utils/reporter/technical_analyzer.py
```

Test:

```text
tests/reporter/test_technical_indicators.py
```

### 移动函数

从 `technical_analyzer.py` 移动以下函数：

```text
_sma
_ema
_atr
_adx
_cci
_williams_r
_stoch_rsi
_obv
_macd
_bollinger
_rsi
```

在新模块中去掉下划线，作为公开 API：

```text
sma
ema
atr
adx
cci
williams_r
stoch_rsi
obv
macd
bollinger
rsi
```

### `technical_analyzer.py` 中 re-export

```python
try:
    from .technical_indicators import (
        sma as _sma, ema as _ema, atr as _atr, adx as _adx,
        cci as _cci, williams_r as _williams_r, stoch_rsi as _stoch_rsi,
        obv as _obv, macd as _macd, bollinger as _bollinger, rsi as _rsi,
    )
except ImportError:
    from technical_indicators import (
        sma as _sma, ema as _ema, atr as _atr, adx as _adx,
        cci as _cci, williams_r as _williams_r, stoch_rsi as _stoch_rsi,
        obv as _obv, macd as _macd, bollinger as _bollinger, rsi as _rsi,
    )
```

### 新增 `__all__`

```python
# technical_indicators.py
__all__ = [
    "sma", "ema", "atr", "adx", "cci",
    "williams_r", "stoch_rsi", "obv", "macd", "bollinger", "rsi",
]
```

### 必须新增测试

```python
def test_sma_basic():
    s = pd.Series([1, 2, 3, 4, 5])
    result = sma(s, 3)
    assert result.iloc[-1] == 4.0


def test_rsi_range():
    close = pd.Series([100.0] * 20 + [120.0])
    result = rsi(close, 14)
    assert 0 <= result.iloc[-1] <= 100


def test_bollinger_structure_non_constant():
    close = pd.Series([100.0 + i for i in range(30)])
    upper, mid, lower = bollinger(close, 20, 2)
    assert upper.iloc[-1] > mid.iloc[-1] > lower.iloc[-1]


def test_old_private_alias_still_available():
    from technical_analyzer import _sma
    s = pd.Series([1, 2, 3])
    assert _sma(s, 2).iloc[-1] == 2.5
```

### 验收

```bash
pytest tests/reporter/test_technical_indicators.py -v
pytest tests/reporter/ -v
```

全部通过。

---

## Task 2：拆分结构分析到 `technical_structure.py`

### Files

Create:

```text
scripts/utils/reporter/technical_structure.py
```

Modify:

```text
scripts/utils/reporter/technical_analyzer.py
```

Test:

```text
tests/reporter/test_technical_structure.py
```

### 移动函数

```text
compute_bias
compute_boll_state
compute_candle_features
compute_ma_direction
resample_daily_to_weekly
compute_weekly_trend
find_support_resistance
```

### import 兼容写法

```python
try:
    from .technical_indicators import sma, ema, atr
except ImportError:
    from technical_indicators import sma, ema, atr
```

### `technical_analyzer.py` re-export

```python
try:
    from .technical_structure import (
        compute_bias, compute_boll_state, compute_candle_features,
        compute_ma_direction, resample_daily_to_weekly,
        compute_weekly_trend, find_support_resistance,
    )
except ImportError:
    from technical_structure import (
        compute_bias, compute_boll_state, compute_candle_features,
        compute_ma_direction, resample_daily_to_weekly,
        compute_weekly_trend, find_support_resistance,
    )
```

### 测试策略

新增 `test_technical_structure.py`，但保留旧测试：

```text
tests/reporter/test_bias_computation.py
tests/reporter/test_boll_state.py
tests/reporter/test_daily_structure.py
tests/reporter/test_weekly_trend.py
tests/reporter/test_support_resistance.py
```

旧测试必须继续通过，验证旧路径兼容。

### 新增 `__all__`

```python
# technical_structure.py
__all__ = [
    "compute_bias", "compute_boll_state", "compute_candle_features",
    "compute_ma_direction", "resample_daily_to_weekly",
    "compute_weekly_trend", "find_support_resistance",
    "evaluate_sr_transformation",
]
```

---

## Task 3：拆分状态机到 `technical_state_machine.py`

### Files

Create:

```text
scripts/utils/reporter/technical_state_machine.py
```

Modify:

```text
scripts/utils/reporter/technical_analyzer.py
```

Test:

```text
tests/reporter/test_technical_state_machine.py
```

### 移动函数

```text
classify_trend_state
apply_previous_state
compute_trend_health
compute_invalidation
```

### 新增测试

保留旧测试的同时，新增模块测试：

```python
from technical_state_machine import (
    classify_trend_state,
    apply_previous_state,
    compute_trend_health,
    compute_invalidation,
)
```

### 验收

```bash
pytest tests/reporter/test_technical_state_machine.py -v
pytest tests/reporter/test_trend_state_machine.py -v
pytest tests/reporter/test_trend_health.py -v
pytest tests/reporter/ -v
```

### 新增 `__all__`

```python
# technical_state_machine.py
__all__ = [
    "classify_trend_state", "apply_previous_state",
    "compute_trend_health", "compute_invalidation",
    "evaluate_bias_extreme", "detect_false_rebound",
    "detect_false_breakout", "evaluate_sell_three_factors",
]
```

---

## Task 4：拆分形态预警到 `technical_patterns.py`

### Files

Create:

```text
scripts/utils/reporter/technical_patterns.py
```

Modify:

```text
scripts/utils/reporter/technical_analyzer.py
```

Test:

```text
tests/reporter/test_technical_patterns.py
```

### 移动函数

```text
detect_double_top
detect_double_bottom
_is_support_resistance
detect_boll_overextension
```

### 注意

本阶段不要实现完整三重背离，不要实现头肩顶，不要实现通道盘整。

这些移到 Phase 3。

### 新增 `__all__`

```python
# technical_patterns.py
__all__ = [
    "detect_double_top", "detect_double_bottom",
    "detect_boll_overextension", "evaluate_candle_at_key_levels",
]
```

---

## Task 5：精简 `technical_analyzer.py`

### 目标

拆分后 `technical_analyzer.py` 只保留：

```text
1. docstring
2. imports
3. re-export compatibility aliases
4. _compute_base_indicators()
5. advanced_medium_term_resonance()
6. analyze()
7. multi_indicator_resonance() legacy compatibility
```

目标行数：

```text
technical_analyzer.py < 300 行
```

不要追求一次压到 200 行，优先保证清晰和兼容。

### 验收

```bash
pytest tests/reporter/ -v
```

全部通过。

### 关键检查点：集成验证

Task 5 提交前，额外运行一次符号集成验证：

```bash
python -c "
from technical_analyzer import (
    analyze, advanced_medium_term_resonance,
    _compute_base_indicators,
    compute_bias, compute_boll_state, classify_trend_state,
    detect_boll_overextension,
)
print('All symbols import OK')
"
```

确保 re-export 没有遗漏任何旧符号，再进入 Phase 2B。

---

## 5. Phase 2B：中期趋势体验增强

---

## Task 6：K线形态辅助信号接入报告

### Files

Modify:

```text
scripts/utils/reporter/technical_patterns.py
scripts/utils/reporter/technical_analyzer.py
scripts/utils/reporter/sections/technical_renderer.py
```

Test:

```text
tests/reporter/test_technical_patterns.py
```

### 新增函数

```python
def evaluate_candle_at_key_levels(
    candle: dict,
    key_levels: dict,
    close: float,
    boll_state: str,
    boll_lower: float | None = None,
    boll_upper: float | None = None,
) -> dict | None:
    """
    在关键位置评估 K 线形态信号。
    只在支撑区、阻力区、BOLL 上轨/下轨附近输出提示。
    """
```

### 规则

```text
十字星 + 关键位：
    多空胶着，变盘可能增加

长下影 + 支撑区 / BOLL 下轨：
    下方承接力较强

长上影 + 阻力区 / BOLL 上轨：
    上方抛压较重
```

### 返回结构

```python
{
    "signal": "长下影，下方承接力较强",
    "strength": "support_confirm",
    "location": "支撑位",
}
```

### 接入主入口

在 `advanced_medium_term_resonance()` 中：

```python
candle_features = compute_candle_features(df_daily, atr_series)

candle_signal = evaluate_candle_at_key_levels(
    candle=candle_features,
    key_levels=sr_result,
    close=indicators["close"],
    boll_state=indicators.get("boll_state", "正常"),
    boll_lower=indicators.get("boll_lower"),
    boll_upper=indicators.get("boll_upper"),
)

if candle_signal:
    daily_structure["candle_signal"] = candle_signal
```

### Renderer 输出

compact 模式中加入：

```markdown
**K线形态**：【signal】（位置：【location】）
```

### K线形态信号不得改变趋势状态

`evaluate_candle_at_key_levels()` 的输出只能写入：

```python
daily_structure["candle_signal"]
```

不得直接修改：

```python
trend_state["stage"]
trend_state["primary_state"]
trend_health["score"]
```

Phase 2 中保持：

```text
K线形态 = 辅助解释，不改变核心趋势状态。
```

---

## Task 7：BIAS 极端值独立预警

### Files

Modify:

```text
scripts/utils/reporter/technical_state_machine.py
scripts/utils/reporter/technical_analyzer.py
scripts/utils/reporter/sections/technical_renderer.py
```

Test:

```text
tests/reporter/test_technical_state_machine.py
```

### 新增函数

```python
def evaluate_bias_extreme(
    bias_5: float | None,
    bias_5_extreme_high: bool,
    bias_5_extreme_low: bool,
    bias_10: float | None = None,
    bias_10_extreme_high: bool = False,
    bias_10_extreme_low: bool = False,
) -> dict | None:
    ...
```

### 必须返回 direction

```python
{
    "warning": "BIAS 创近120日新高，极端超买",
    "level": "严重",
    "direction": "high",
    "affects": "卖出三要素之强弱偏离度",
}
```

或：

```python
{
    "warning": "BIAS 创近120日新低，极端超卖",
    "level": "严重",
    "direction": "low",
    "affects": "买入参考，不构成买入信号",
}
```

### 注意

```text
BIAS 高位极值：
    可以进入卖出三要素的"强弱偏离度"。

BIAS 低位极值：
    不得进入卖出三要素。
```

---

## Task 8：假突破 / 假反弹甄别

### Files

Modify:

```text
scripts/utils/reporter/technical_state_machine.py
scripts/utils/reporter/technical_analyzer.py
```

Test:

```text
tests/reporter/test_technical_state_machine.py
```

### 新增函数

```python
def detect_false_rebound(
    df_recent: pd.DataFrame,
    boll_state: str,
    volume_ma20: float,
) -> dict | None:
    ...
```

### 规则

```text
冷不丁单根阳线 + BOLL 未张口 + 未放量 -> 疑似假反弹
```

### 假反弹检测的最小数据要求

`detect_false_rebound()` 需要明确最小数据长度，避免短序列误判。

规则：

```text
df_recent 少于 6 根 K 线：
    返回 None，不做判断。
```

建议：

```python
if df_recent is None or len(df_recent) < 6:
    return None
```

测试中也应使用至少 6 根数据。

### 正确接入

```python
volume_ma20 = float(df_daily["volume"].tail(20).mean())

false_rebound = detect_false_rebound(
    df_recent=df_daily.tail(10),
    boll_state=indicators.get("boll_state", "正常"),
    volume_ma20=volume_ma20,
)
```

不得传 `avg_amount_yi * 100000000` 给 `volume_ma20`。

### 新增函数

```python
def detect_false_breakout(
    close: float,
    ma5: float,
    prev_close: float,
    prev_ma5: float,
) -> dict | None:
    ...
```

规则：

```text
前一日突破 MA5，次日重新跌回 MA5 下方 -> 突破失败风险，停止加仓。
```

---

## Task 9：卖出三要素决策框架

### Files

Modify:

```text
scripts/utils/reporter/technical_state_machine.py
scripts/utils/reporter/technical_analyzer.py
scripts/utils/reporter/sections/technical_renderer.py
```

Test:

```text
tests/reporter/test_technical_state_machine.py
```

### 新增函数

```python
def evaluate_sell_three_factors(
    valuation_overpriced: bool | None,
    ma_breakdown: bool,
    bias_extreme_high: bool,
    rsi_value: float | None = None,
) -> dict:
    ...
```

### 三要素定义

只能有三类：

```text
1. 估值定价
2. 均线信号
3. 强弱偏离度
```

RSI 严重超买并入"强弱偏离度"，不得单独计数。

### 正确实现

```python
def evaluate_sell_three_factors(
    valuation_overpriced: bool | None,
    ma_breakdown: bool,
    bias_extreme_high: bool,
    rsi_value: float | None = None,
) -> dict:
    factors = []

    if valuation_overpriced:
        factors.append("估值定价：极度高估")

    if ma_breakdown:
        factors.append("均线信号：已触发破位")

    deviation_extreme = bias_extreme_high or (rsi_value is not None and rsi_value > 80)
    if deviation_extreme:
        if bias_extreme_high and rsi_value is not None and rsi_value > 80:
            factors.append(f"强弱偏离度：BIAS高位极端且RSI严重超买（RSI={rsi_value:.1f}）")
        elif bias_extreme_high:
            factors.append("强弱偏离度：BIAS创近120日高位极值")
        else:
            factors.append(f"强弱偏离度：RSI严重超买（RSI={rsi_value:.1f}）")

    met = len(factors)

    if met >= 2:
        recommendation = "建议卖出"
    elif met == 1:
        recommendation = "部分信号出现，建议减仓观察"
    else:
        recommendation = "观望，不满足卖出条件"

    return {
        "factors": factors,
        "met_count": met,
        "recommendation": recommendation,
        "rule": "卖出三要素：估值定价、均线信号、强弱偏离度；至少满足两条才给出明确卖出建议",
    }
```

### 主入口接入

```python
bias_extreme_high = (
    bias_extreme is not None
    and bias_extreme.get("direction") == "high"
)

sell_assessment = evaluate_sell_three_factors(
    valuation_overpriced=None,
    ma_breakdown=trend_state["stage"] == "破坏期",
    bias_extreme_high=bias_extreme_high,
    rsi_value=indicators.get("rsi_14"),
)
```

### 卖出三要素 renderer 显示规则

卖出三要素不应在没有信号时占用报告篇幅。

Renderer 规则：

```text
如果 sell_assessment.met_count == 0：
    compact 模式不渲染卖出三要素模块。

如果 sell_assessment.met_count >= 1：
    compact 模式显示简短结论。

如果 mode == "full"：
    显示完整 factors、met_count、recommendation、rule。
```

compact 示例：

```markdown
**卖出三要素**：满足 1/3 条，部分信号出现，建议减仓观察。
```

full 示例：

```markdown
### 卖出三要素评估

- 估值定价：未接入
- 均线信号：已触发破位
- 强弱偏离度：BIAS高位极端或RSI严重超买
- 结论：建议卖出（满足 2/3 条）
```

---

## Task 10：支撑阻力转化 + 操作应用

### Files

Modify:

```text
scripts/utils/reporter/technical_structure.py
scripts/utils/reporter/technical_analyzer.py
scripts/utils/reporter/sections/technical_renderer.py
```

Test:

```text
tests/reporter/test_technical_structure.py
```

### 新增函数

```python
def evaluate_sr_transformation(
    close: float,
    support_zone: dict | None,
    resistance_zone: dict | None,
    recent_closes: list[float],
) -> dict | None:
    ...
```

### 规则

#### 阻力转支撑

满足全部条件：

```text
1. resistance_zone 存在；
2. 最近 3 日收盘价均大于 resistance_zone.zone_high；
3. 最新收盘价大于 resistance_zone.zone_high * 1.01；
4. 输出 resistance_break。
```

代码逻辑：

```python
if resistance_zone and len(recent_closes) >= 3:
    rz_high = resistance_zone["zone_high"]
    stood_above = all(c > rz_high for c in recent_closes[-3:])
    strong_break = close > rz_high * 1.01

    if stood_above and strong_break:
        ...
```

#### 支撑转阻力

满足全部条件：

```text
1. support_zone 存在；
2. 最近 3 日收盘价均小于 support_zone.zone_low；
3. 输出 support_break。
```

代码逻辑：

```python
if support_zone and len(recent_closes) >= 3:
    sz_low = support_zone["zone_low"]
    stayed_below = all(c < sz_low for c in recent_closes[-3:])

    if stayed_below:
        ...
```

#### 注意

```text
不要只看最后一天。
不要只看盘中 high/low。
本规则使用收盘价确认。
```

### 返回结构

```python
{
    "signals": [
        {
            "signal": "阻力突破，原阻力转为新支撑",
            "type": "resistance_break",
            "new_support": 112.0,
        }
    ],
    "primary": {...}
}

---

## 6. Phase 2C：市场 / 板块共振框架预留

---

## Task 11：新增 `technical_resonance.py`

### Files

Create:

```text
scripts/utils/reporter/technical_resonance.py
```

Modify:

```text
scripts/utils/reporter/technical_analyzer.py
```

Test:

```text
tests/reporter/test_technical_resonance.py
```

### 新增函数

```python
def evaluate_market_resonance(
    stock_trend_state: dict,
    sector_trend: str | None = None,
    market_trend: str | None = None,
) -> dict:
    ...
```

### 第一版行为

如果未接入外部数据，返回：

```python
{
    "resonance_signals": [],
    "sector_trend": "未接入",
    "market_trend": "未接入",
    "impact": "暂未接入市场/行业数据，本次技术分析仅基于个股自身K线结构。",
}
```

如果未来传入数据：

```text
个股主升/启动/加速 + 板块上涨 + 大盘上涨：
    共振上涨，信号增强

个股上涨但板块/大盘弱：
    独立行情，注意共振回落风险
```

### market resonance 必须是纯占位，不得访问外部数据

Task 11 第一版只允许：

```python
evaluate_market_resonance(
    stock_trend_state,
    sector_trend=None,
    market_trend=None,
)
```

不得在函数内部主动拉取数据，不得引入网络请求，不得访问未定义的数据源。

如果没有外部数据，必须稳定输出：

```python
{
    "resonance_signals": [],
    "sector_trend": "未接入",
    "market_trend": "未接入",
    "impact": "暂未接入市场/行业数据，本次技术分析仅基于个股自身K线结构。",
}
```

---

## 7. 暂缓到 Phase 3 的任务

以下任务不要在 Phase 2 执行：

```text
1. 三重背离完整版
2. 通道盘整识别
3. 头肩顶 / 双底复杂形态完善
```

### 7.1 三重背离完整版暂缓原因

当前草案问题：

```text
1. 没有真正比较前一个高点对应的 MACD / RSI / BOLL。
2. 测试数据长度与 lookback 条件不匹配。
3. 名称叫"完整版"，但实现仍是简化代理逻辑。
```

Phase 3 再做时必须要求：

```text
1. 识别 confirmed swing high / swing low。
2. 记录前高和当前高点对应的 MACD、RSI、BOLL。
3. 比较价格创新高/新低但指标未确认。
4. 输出 evidence。
5. 背离只作为预警，不直接改变趋势状态。
```

### 7.2 通道盘整暂缓原因

当前草案问题：

```text
突破检测把突破当天 high 纳入通道上沿，容易导致突破判断失败。
```

Phase 3 再做时必须用：

```python
channel_base = df.iloc[-window-1:-1]
current = df.iloc[-1]
```

不要把当前突破 K 线纳入通道拟合。

### 7.3 头肩顶 / 双底暂缓原因

当前草案仍含：

```python
pass
```

不适合作为可执行计划。

Phase 3 再写完整规则与测试。

---

## 8. 测试策略

### 8.1 保留 Phase 1 测试

Phase 2 完成前，以下旧测试不要删除：

```text
test_bias_computation.py
test_boll_state.py
test_daily_structure.py
test_weekly_trend.py
test_support_resistance.py
test_trend_state_machine.py
test_trend_health.py
test_boll_overextension.py
test_backward_compatibility.py
test_technical_renderer.py
```

### 8.2 新增模块测试

新增：

```text
test_technical_indicators.py
test_technical_structure.py
test_technical_state_machine.py
test_technical_patterns.py
test_technical_resonance.py
```

### 8.3 每个 Task 的测试要求

每个 Task 完成后必须跑：

```bash
pytest tests/reporter/<对应测试文件>.py -v
```

每个 commit 前必须跑：

```bash
pytest tests/reporter/ -v
```

### 8.4 最终验收

```bash
pytest tests/reporter/ -v
```

必须全部通过。

---

## 9. 最终文件行数目标

Phase 2 完成后运行：

```bash
wc -l scripts/utils/reporter/technical_indicators.py \
      scripts/utils/reporter/technical_structure.py \
      scripts/utils/reporter/technical_state_machine.py \
      scripts/utils/reporter/technical_patterns.py \
      scripts/utils/reporter/technical_resonance.py \
      scripts/utils/reporter/technical_analyzer.py
```

目标：

```text
technical_analyzer.py < 300 行
每个子模块 < 500 行
```

不强求每个模块都很短，优先保证职责清晰、测试通过、兼容不破。

---

## 10. 最终验收标准

Phase 2 完成后必须满足：

```text
1. Phase 1 全部测试继续通过。
2. 旧 import 路径继续可用。
3. 旧 `_resonance` 渲染继续降级成功。
4. 雷达图依赖的 composite_score 不受影响。
5. `technical_analyzer.py` 精简为主入口和兼容层。
6. 新模块职责清晰，不产生循环依赖。
7. compact / full renderer 继续可用。
8. K线形态信号只在关键位置输出，不泛滥。
9. BIAS 高位/低位极端预警方向明确。
10. BIAS 低位极端不得进入卖出三要素。
11. RSI 严重超买并入强弱偏离度，不得成为第四个卖出要素。
12. 假反弹检测使用成交量均值，不得混用成交额单位。
13. 支撑阻力转化必须检查最近 3 日是否站稳/失守。
14. market resonance 缺失外部数据时应输出"未接入"，不得报错。
15. 本阶段不实现三重背离完整版、通道盘整、头肩顶/双底复杂形态。
16. `technical_indicators.py`、`technical_structure.py`、`technical_state_machine.py`、`technical_patterns.py` 每个模块都定义 `__all__`。
17. `tests/reporter/test_technical_imports.py` 存在并通过 — 同时验证包内相对导入和直接脚本路径导入。
18. `test_analyze_schema_stable_after_refactor` 存在并通过 — Task 1-5 每完成一个拆分任务后都必须通过。
19. `technical_renderer.py` compact 模式在 `sell_assessment.met_count == 0` 时不渲染卖出三要素；`met_count >= 1` 时显示简短结论；full 模式显示完整 factors、met_count、recommendation、rule。
20. `detect_false_rebound()` 在 `len(df_recent) < 6` 时返回 `None`，短序列不判断、不报错。
21. `evaluate_candle_at_key_levels()` 是纯辅助信号 — 输出只写入 `daily_structure["candle_signal"]`，不得修改 `trend_state["stage"]`、`trend_state["primary_state"]`、`trend_health["score"]`。
22. `evaluate_market_resonance()` 不得发起网络请求；无外部数据时稳定输出 "未接入"，不报错。
23. `technical_analyzer.py` re-export 使用 `from module import func as _func` 别名写法，不使用 `_func = func` 赋值别名。
24. 新模块测试中不使用恒定价格序列验证 BOLL `upper > mid > lower`；所有 BOLL 测试均使用非恒定序列或允许相等。
```

---

## 11. 推荐提交顺序

```text
Commit 0:
test(technical): add import smoke tests and phase2 schema stability checks

Commit 1:
refactor(technical): extract technical_indicators.py

Commit 2:
refactor(technical): extract technical_structure.py

Commit 3:
refactor(technical): extract technical_state_machine.py

Commit 4:
refactor(technical): extract technical_patterns.py

Commit 5:
refactor(technical): slim analyzer to orchestration layer

Commit 6:
feat(technical): add candle signals at key levels

Commit 7:
feat(technical): add BIAS extreme warning with direction

Commit 8:
feat(technical): add false rebound and false breakout checks

Commit 9:
feat(technical): add sell three-factors framework

Commit 10:
feat(technical): add support/resistance transformation rules

Commit 11:
feat(technical): add market resonance placeholder framework

Commit 12:
test(technical): phase 2 full regression

Commit 13:
test(technical): add final phase2 safety regression checks
```

---

## 12. Agent 执行摘要

请严格按以下顺序执行：

```text
第一步：
只做模块拆分，不改行为。拆 indicators、structure、state_machine、patterns，保留 re-export。

第二步：
跑全量测试，确认 Phase 1 行为完全不变。

第三步：
接入 K线形态辅助信号，只在支撑/阻力/BOLL轨附近输出。

第四步：
接入 BIAS 极端值预警，必须输出 direction=high/low。

第五步：
接入假突破/假反弹。假反弹检测使用 volume_ma20，不得混用 avg_amount_yi。

第六步：
接入卖出三要素。RSI 并入强弱偏离度，BIAS 只有 high 方向参与卖出判断。

第七步：
接入支撑阻力转化。最近 3 日站稳/失守才输出转化信号。

第八步：
添加 market resonance 占位框架，缺失外部数据时输出未接入。

第九步：
跑全量测试，检查文件行数，提交最终回归 commit。

第十步：
不要实现三重背离完整版、通道盘整、头肩顶/双底复杂形态；这些留到 Phase 3。
```

---

*设计版本：technical.phase2.refactor_and_experience_enhancement*
*适用范围：Phase 2A / Phase 2B / Phase 2C*
*不包含：Phase 3 高级形态识别*
