# Technical Analysis v2 Phase 1 Design

日期：2026-07-14
分支：`codex/annual-producer-v2`

## 1. Objective

统一技术分析中的趋势状态、健康度、失效条件、目标结构置信度、交易触发和推荐降级语义。

Phase 1 不重写 MA、MACD、RSI、BOLL、ATR、ADX、形态识别、支撑压力和目标价计算公式。它只把现有计算结果整理成一份确定性的技术判断契约，并让报告与推荐层消费同一份判断。

## 2. Current Failures

当前技术结论有多个独立 owner：

- `technical_state_machine.py` 判定趋势阶段、健康度和失效位；
- `price_target.py` 独立判定方向、置信度、触发条件和盈亏比；
- `recommendation_decision.py` 再从字符串和健康度推断入场限制；
- `technical_renderer.py` 再次根据分数和阶段拼装结论；
- `PriceTargetRenderer` 与 `TechnicalRenderer` 各有一套目标展示逻辑，但正式报告实际只显示后者的内嵌目标部分。

已在 20260713 样本中观察到：

1. `confidence=观望` 仍展示三档精确目标和精确交易日预期；
2. producer 返回 `中线看多/中线看空`，renderer 只识别 `bullish/bearish`，最终显示为观望；
3. 现价已越过颈线，报告仍把该价位写成未满足条件；
4. ADX 触发条件使用当前 ADX 值作为未来阈值；
5. 现价在 MA60 上方 0-3% 时，失效文案写成“接近/略低于”并要求“收回”；
6. 市场与行业数据均缺失时仍输出占位式共振分析；
7. renderer 的 `_build_conclusion()` 以 `score < 50` 重新覆盖趋势状态机语义。

## 3. Non-goals

- 不改变评分引擎、EV、风险评分和基本面推荐算法；
- 不修改技术指标公式或形态识别算法；
- 不回测或重新校准目标价、ATR 时间模型；
- 不增加 LLM 判断、LLM prompt 或股票/行业专用规则；
- 不访问网络，不刷新行情，不生成正式报告；
- 不把外部观点或基本面材料用于技术目标价。

## 4. Architecture Decision

### 4.1 Existing owner, no new large module

扩展 `technical_state_machine.py`，新增纯函数 `build_technical_judgment(...)`，作为技术解释层唯一 owner。它只消费已存在的结构化结果，不读取文件、不访问网络、不重新计算指标。`price_target.py` 只拥有目标结构证据和基于数值的 raw trigger checks；它不直接决定报告操作结论。state machine 负责施加 data-quality cap、把 low confidence 的 raw price check 降为 `unknown`、解析 execution/action，并通过 `resolve_target_display_mode(...)` 生成唯一 display mode。

每条调用路径都必须在拿到自己的最终 `price_target` 后调用同一个 builder，并把结果写入：

```python
resonance["judgment"]
```

调用路径：

1. `technical_analyzer.analyze()`：给技术专用入口使用，在本函数生成的最终目标后构建 judgment；
2. `TechnicalCollector.build_technical_payload()`：新增单次编排 helper。主报告路径和 Wind 本地路径均通过它把日线、周线、代码和市场传给 `technical_analyzer.analyze()`，并直接采用该返回的 indicators、resonance、levels、price_target 和 judgment。Wind 只有日线时允许 analyzer 沿用现有日线重采样周线能力，但不得回到“只算 indicators、把 price_target 写成 None”的旧路径。该 helper 本身不新增 I/O，但底层 analyzer 保留现有市场/主题指数获取行为，因此不得称为纯函数；单元测试必须 patch 该既有外部边界；
3. `TechnicalCollector.collect()`：先取得日线与周线，再调用 `build_technical_payload()` 一次。删除其中独立的第二次 `analyze_price_target()` 调用；
4. `TechnicalCollector.compute_indicators()`：保留为兼容 wrapper，只返回 `build_technical_payload()` 的 indicators 平铺结果，不再拥有独立 target 计算；
5. `technical_fetching_skill._set_technical_outputs()`：对已缓存的 technical payload 调用 `ensure_technical_judgment()`。旧 payload 没有足够的结构证据时只能降级为 `effective_confidence=unavailable / execution_state=unavailable / display_mode=unavailable`，不得恢复旧的三档精确目标展示；技术章节仍可从既有 key levels 展示支撑压力，但 target 子模块不再冒充 observation 结构。

`technical_renderer.py`、`recommendation_decision.py` 和 HTML dashboard 优先消费该字段；旧缓存没有该字段时只允许安全降级 fallback。

collector 的外部 shape 不变。`build_technical_payload()` 必须把 analyzer 返回值组装为现有结构：基础指标仍在 `technical["indicators"]`，`resonance` 仍写入 `technical["indicators"]["_resonance"]`，patterns/levels 仍分别写入 `_patterns/_levels`，最终 target 仍位于 `technical["price_target"]`。不得新增一套平行 top-level resonance 作为主读取路径。

市场参数传播是显式契约：`compute_indicators(df, code=None, market=None)` 和 `build_technical_payload(df_daily, df_weekly, code=None, market=None, ...)` 都显式接收市场；主 collector 与 Wind 路径必须传入配置中的 `market`。固定调用链为：

```text
technical_fetching_skill(market)
  -> TechnicalCollector.build_technical_payload(..., market=market)
  -> technical_analyzer.analyze(..., quote={market, is_hk, ...})
  -> analyze_price_target(..., is_hk=quote["is_hk"])
```

`TechnicalCollector.collect()` 也必须把自己的 `market` 参数传入同一 builder，不得再直接调用未带 `is_hk` 的 `analyze_price_target()`。`market == "hk"` 时 `is_hk=True`，其他已知 A 股市场为 `False`；不得仅依靠股票代码在目标函数内部重新猜测市场。`market` 缺失时只能保留现有 A 股兼容默认值并在 limitations 记录市场未显式确认。港股 contract test 必须同时覆盖 collector 与 Wind 两条路径，并断言量比阈值为 `1.3` 而不是 `1.5`。

### 4.2 Judgment schema

```python
{
    "schema": "technical_judgment.v1",
    "trend": {
        "state": "strong_up|weak_up|transition|range|down|invalid|unknown",
        "label": str,
        "stage": str,
        "health_score": int | float | None,
        "health_grade": str,
        "invalidation_state": "safe|near_above|broken|unknown",
        "summary": str,
    },
    "target": {
        "direction": "bullish|bearish|neutral",
        "producer_status": "ready|observe|blocked|invalid|unavailable",
        "reason_code": str,
        "structure_confidence": "high|medium|low|observation|unavailable",
        "effective_confidence": "high|medium|low|observation|unavailable",
        "structure_label": "高|中|低|观察位|不可用",
        "effective_label": "高|中|低|观察位|不可用",
        "basis": list[str],
        "execution_state": "triggered|pending|blocked|invalid|observe|unavailable",
        "display_mode": "full_targets|core_targets|conditional_range|levels_only|blocked|unavailable",
        "trigger_checks": dict,
        "data_quality_cap": "high|medium|low|observation|unavailable",
        "reason": str,
    },
    "action": {
        "state": "follow|wait_for_entry|wait_for_confirmation|risk_control|unavailable",
        "summary": str,
    },
    "limitations": list[str],
}
```

`producer_status/reason_code` 是从 `price_target.status/reason_code` 复制进 judgment 的稳定生产者状态，和 `execution_state` 分工明确：前者说明“目标模块为何结束”，后者说明“当前是否可执行”。`build_technical_judgment()` 可以读取 raw price target 一次来构建它们，但 renderer、recommendation、dashboard 和 risk guardrail 之后只能读取 judgment，不能再回读 `price_target.error/reason` 中文文案。字段使用英文稳定 code，中文只用于 label 和 summary。下游不得再从中文 prose 反向推断状态。

## 5. Trend Reconciliation

判断优先级：

1. `invalidation.is_invalidated` 或 `status == broken`：`invalid`；
2. `primary_state == 下降趋势` 或 `stage == 破坏期`：`down`；
3. `primary_state == 震荡转弱`：`transition`；
4. `primary_state == 上升趋势` 且健康度 `>= 65`：`strong_up`；
5. `primary_state == 上升趋势` 且健康度 `50-64`：`weak_up`；
6. `primary_state == 上升趋势` 但健康度 `< 50`：`transition`，不得继续显示“主升期 + 趋势破坏风险高”；
7. 其余震荡状态：`range`。

底层 `trend_state` 和 `trend_health` 原始值继续保留用于诊断；报告主结论只使用 reconciled judgment。

### 5.1 MA60 wording fix

`compute_invalidation()` 使用以下状态：

- `close < hard_price`：`broken`，文案“已跌破”；
- `hard_price <= close < hard_price * 1.03`：`near_above`，文案“位于上方但安全垫不足”；
- 其他：`safe`。

禁止在 `close >= MA60` 时出现“略低于”“无法收回”。旧 code `near_or_slightly_broken` 仅作为输入兼容，不再产生。

`near_above` 是 `invalidation.status` 的正式替代枚举值。Phase 1 必须同步修改 `technical_renderer.py` 及所有读取 `resonance["invalidation"]["status"]` 的条件；legacy adapter 可以把旧 `near_or_slightly_broken` 映射到 `near_above`，但新 producer 和 renderer 不再输出或分支判断旧 code。

## 6. Target Structure Confidence

旧 `confidence_score` 和 `confidence` 保留为诊断兼容字段，但不再直接控制报告展示，也不再在新报告的目标标题中显示。新字段必须在 `analyze_price_target()` 的结构证据阶段写入每个适用 return payload；成功 return 同时保留旧六因子值作 diagnostics。若旧六因子 `confidence` 与新 `structure_confidence/effective_confidence` 冲突，合法 `technical_judgment.v1` 的 renderer 只显示 `judgment.target.structure_label/effective_label`，不得显示旧置信度；旧缓存无法重建 judgment 时目标模块整体 `unavailable`，也不得用旧 confidence 恢复目标表。

`price_target.py` 增加结构证据元数据：

```python
{
    "daily_pattern": bool,
    "weekly_pattern": bool,
    "patterns_aligned": bool | None,
    "weekly_direction_aligned": bool | None,
    "fib_convergence": bool,
    "method_family": "dual_pattern|single_pattern|fib_only|unavailable",
}
```

字段计算规则：

- `daily_pattern/weekly_pattern`：对应周期存在可由 `extract_pattern_info()` 解析的有效形态；
- `patterns_aligned`：仅在两个周期都有有效形态时比较方向；同向为 `True`、反向为 `False`，单周期或无形态时为 `None`；
- `weekly_direction_aligned`：目标方向与 `weekly_trend.direction` 都是明确多头/空头时比较；同向为 `True`、反向为 `False`，任一侧为震荡/未知/neutral 时为 `None`；
- `fib_convergence`：在调用 `synthesize_targets()` 之前，分别保留 `daily_fib_candidates` 与 `weekly_fib_candidates` 的原始 `1.0/1.272/1.618` candidate dict，并计算 `any(t["in_convergence"] for t in daily_fib_candidates + weekly_fib_candidates)`。之后才允许把候选压缩为单个价位；不得从 `synthesize_targets()` 的压缩结果反推 convergence。daily-only convergence 同样必须得到 `True`；
- `method_family`：双周期形态、单周期形态、无形态但有 Fibonacci/波段目标分别为 `dual_pattern/single_pattern/fib_only`；无任何目标结构为 `unavailable`。`fib_only -> structure_confidence=observation` 是恒等映射。保留两个字段是因为 `method_family` 只负责方法溯源，`structure_confidence` 才是决策输入；任何下游不得用 `method_family` 代替置信度或 action 判断。

`price_target.py` 的每个 return branch 都必须包含稳定的状态字段；旧中文 `error/reason` 只作兼容展示：

```python
{
    "status": "ready|observe|blocked|invalid|unavailable",
    "reason_code": str,
}
```

结果矩阵：

| Existing branch | status | reason_code |
|---|---|---|
| 日线不足 | unavailable | insufficient_daily_data |
| 周线不足 | unavailable | insufficient_weekly_data |
| 周线震荡、暂不生成方向目标 | observe | weekly_range |
| 日线/周线方向冲突 | invalid | timeframe_direction_conflict |
| 日周有效形态方向相反 | invalid | pattern_direction_conflict |
| 仅有 Fibonacci/波段推导 | observe | structure_observation |
| 与目标方向相反的 MACD 柱线扩张 | blocked | opposing_macd_expansion |
| 高/中/低结构但无法构造风险计划 | observe | risk_plan_unavailable |
| ATR 缺失、非有限数或不大于零 | unavailable | invalid_atr |
| 盈亏比低于阈值 | blocked | risk_reward_below_minimum |
| 目标结构成功生成 | ready | target_ready |

禁止 builder、renderer、recommendation 或 cache adapter 根据 `error/reason` 中文内容恢复上述状态。双周期形态方向相反时必须在 `synthesize_targets()` 之前返回 `pattern_direction_conflict`，不得先用第一个形态方向合成目标。

以下两类 payload 必须保留完整的结构化 `profit_risk`：`status=ready` 的成功目标，以及 `status=blocked / reason_code=risk_reward_below_minimum` 的盈亏比阻断目标。

```python
{
    "pass": bool,
    "ratio": float,
    "direction": "bullish|bearish",
    "neckline": float,
    "daily_atr": float,
    "trigger_price": float,
    "stop_price": float,
    "potential_gain": float,
    "initial_risk": float,
}
```

`profit_risk_filter()` 已经接收 neckline、ATR 和方向，必须把它们随结果一并返回；不得在 judgment 中重复计算。数据不足、周线震荡、周期冲突、观察位、风险计划缺失和 MACD 阻断路径不伪造 neckline、stop 或收益风险数据，只提供 `status/reason_code` 与已有结构化 diagnostics。`build_technical_judgment()` 只在 `profit_risk` 完整时判断触发与失效；缺少风险计划时按 target status 安全降级，禁止从 `stop_loss`、`reason` 等中文 prose 解析价格。

确定性分级：

- `high`：日线和周线均有同向有效形态，并且存在斐波那契汇聚或周线方向确认；
- `medium`：一个周期有有效形态，并且有周线方向确认或斐波那契汇聚；
- `low`：只有一个周期形态，没有独立确认；
- `observation`：无有效形态，仅有波段或斐波那契推导；
- `unavailable`：数据不足或没有可用结构。

日线、周线同时识别到有效形态但方向相反时，`patterns_aligned=False`，该目标结构直接进入 `invalid`；不得继续采用“第一个形态方向”合成跨周期目标。

激进目标过远只隐藏激进目标，不再把整组保守/基准目标的置信度一起降级。

### 6.1 Producer decision order

`analyze_price_target()` 必须按以下顺序执行，不得继续沿用当前“先盈亏比、后结构置信度”的顺序：

1. 检查日线/周线数据和周线震荡状态；
2. 检查日周趋势方向硬冲突；
3. 识别日周形态、确定方向，并在目标合成前拒绝双周期形态方向冲突；
4. 生成 Fibonacci 候选，同时保留 convergence 元数据，构造 `structure_evidence` 和 `structure_confidence`；
5. `structure_confidence == observation` 时立即返回 `observe/structure_observation`，不得执行盈亏比阻断，也不得产生 `wait_for_entry` 风险因子；
6. 对 high/medium/low 结构执行方向化 MACD blocker。用一个 `_opposing_macd_expanding(close, direction)` 替换现有 `_macd_dead_expanding()`：`bullish` 只在 `macd_line < signal`、柱线为负且最近 3 个值继续向负方向扩张时阻断；`bearish` 只在 `macd_line > signal`、柱线为正且最近 3 个值继续向正方向扩张时阻断。顺目标方向扩张不得阻断；
7. 验证 ATR、neckline 和 conservative target：ATR 无效返回 `unavailable/invalid_atr`；其余风险计划字段不足返回 `observe/risk_plan_unavailable`；
8. 构造完整 `profit_risk`：不通过则返回 `blocked/risk_reward_below_minimum`，通过才返回 `ready/target_ready`。

`ready` 是强不变量：必须同时具有非空 `structure_evidence`、完整 numeric `profit_risk`、方向和目标结构。任何缺项都不能以 `ready` 返回。

### 6.2 Data quality cap

`structure_confidence` 是纯结构事实，永不被数据质量改写。`effective_confidence` 用于展示和操作建议：

- `analysis_confidence.level == 低`：样本量 cap 为 `low`；
- `analysis_confidence.level == 中`：样本量 cap 为 `medium`；
- `analysis_confidence.level == 高`：样本量 cap 为 `high`；
- 数据不足、复权异常无法判定或价格序列存在未处理异常断点：`unavailable`；
- 无数据质量限制时，`effective_confidence == structure_confidence`。

使用固定序 `high > medium > low > observation > unavailable` 计算 cap：任一侧为 `unavailable` 时结果为 `unavailable`；否则取 `structure_confidence` 与 `data_quality_cap` 中较低者。这样 observation 不会被高数据质量升级，high 也不能绕过低质量 cap。

复权质量 cap 只读取结构字段，不匹配 warning 文案：

| Structured condition | Adjustment cap |
|---|---|
| `requires_qfq=True` 且 `price_adjustment_applied=False` | unavailable |
| `effective_adjustment == local_qfq_approx` | low |
| `effective_adjustment == qfq` 且仍有 `possible_exrights_gap` | low |
| `effective_adjustment in {qfq, hfq}` 且无残留断点 | high |
| `effective_adjustment == raw` 且 `requires_qfq=False`、无异常断点（含港股正常 raw） | high |
| validation/lineage 缺失，无法证明价格连续性 | unavailable |

最终 `data_quality_cap` 是样本量 cap 与 adjustment cap 的较低者；`local_qfq_approx` 和有残留断点的 qfq 不得高于 `low`，未修复但明确要求复权的数据必须为 `unavailable`。

这个 cap 只限制展示和仓位，不修改原始形态、趋势或目标计算。展示矩阵和 action 必须使用 `effective_confidence`，不得使用原始 `structure_confidence` 绕过 cap。

## 7. Execution State

结构置信度回答“目标依据是否充分”；执行状态回答“现在是否满足交易条件”。两者不得合并。

### 7.1 Trigger checks

每项检查输出 `pass|pending|fail|unknown`、观测值和要求。确定性公式如下：

- `price`：使用 `profit_risk.trigger_price`、颈线、最新 `open/close` 和日线 ATR。做多只有在 `close >= trigger_price`、`min(open, close) > neckline` 且 `abs(close-open) >= 0.3*ATR` 时为 `pass`；做空反向要求 `close <= trigger_price`、`max(open, close) < neckline` 且实体满足同一 ATR 条件。缺字段为 `unknown`，尚未越过触发位为 `pending`；
- `trend`：周线 `ADX >= 25`，且做多时 `+DI > -DI`、做空时反向；`trigger_checks.trend.detail` 使用固定阈值文案 `ADX>=25`，不得拼入当前 ADX 作为阈值。当前 ADX 只能作为单独 evidence value 展示；
- `volume`：`volume_ratio = latest_volume / mean(previous_20_sessions_volume)`，均值明确排除最新一日。A 股要求 `>=1.5`，港股要求 `>=1.3`。amount 使用最新一日原始成交额，A 股要求 `>=1亿元`、港股要求 `>=3000万港币`；amount 缺失时可仅按量比 `pass` 并记录“成交额未核验”，amount 存在但不足或量比不足均为 `pending`；不足 20 个历史样本为 `unknown`；
- `momentum`：做多要求 `MACD >= signal` 且 `40 <= RSI <= 70`；做空要求 `MACD <= signal` 且 `30 <= RSI <= 60`。缺字段为 `unknown`，方向未满足或 RSI 越界为 `pending`。只有与目标方向相反的 MACD 柱线连续扩张才是 hard blocker：做多对应负柱扩张，做空对应正柱扩张。

目标方向必须在 momentum hard blocker 之前确定。现有 `price_target.py` 中“方向尚未解析就对 MACD 死叉扩张提前 return”的分支必须下移到方向解析之后；只改变 blocker 的方向语义，不改变任何目标价公式。

当 `effective_confidence == low` 时，不执行精确 price trigger 判定：`trigger_checks.price.status="unknown"`，detail 为“结构精度不足，不判定精确突破位”；只保留 trend/volume/momentum 的结构化检查。因为 `unknown` 不能当作 `pass`，low 目标不能进入 `triggered`，只能在没有更高优先级阻断时进入 `pending`。报告中的条件区间表示“测算条件范围”，不表示已突破精确触发位。

### 7.2 State precedence

1. `target.producer_status == invalid`，包括日周趋势方向硬冲突或双周期有效形态方向相反：`invalid`；
2. 做多目标跌破已有风险计划的 stop，或多头中期结构已失效：`invalid`；做空目标升破已有风险计划的 stop：`invalid`；不得将多头 MA60 失效位直接用于否决做空目标；
3. `target.producer_status == blocked`，包括与目标方向相反的 MACD 柱线连续扩张或盈亏比 `< 1.5`：`blocked`；
4. `target.producer_status == unavailable` 或有效置信度为 `unavailable`：`unavailable`；`target.producer_status == observe` 或有效置信度为 `observation`：`observe`；
5. 所有 required checks 为 `pass`：`triggered`；
6. 其他：`pending`。

`unknown` 不能当成 `pass`。

## 8. Display Matrix

| Direction | Effective confidence | Execution | Display mode | Output |
|---|---|---|---|---|
| any | any | blocked/invalid | blocked | 不显示正常目标表，只显示阻断原因和恢复条件 |
| any | any | unavailable | unavailable | 不展示目标，只说明数据或结构不足 |
| any | unavailable | observe/pending/triggered | unavailable | confidence cap 不可用时 fail closed |
| bearish | high/medium/low/observation | triggered/pending/observe | levels_only | 现货多头视角只显示支撑、压力、下行失效与风险控制，不显示下行三档目标 |
| bullish | high | triggered | full_targets | 保守/基准/激进、触发证据、止损、失效条件 |
| bullish | high | pending | core_targets | 保守/基准、未满足条件，不显示激进目标 |
| bullish | medium | triggered | core_targets | 保守/基准、触发证据、止损 |
| bullish | medium | pending | conditional_range | 保守至基准的条件区间 |
| bullish | low | pending | conditional_range | 条件测算区间和待验证项，不称为精确目标价 |
| bullish/neutral | observation | observe | levels_only | 只显示支撑、压力和重新评估条件 |
| any | low/observation | triggered | unavailable | 非法组合 fail closed，不恢复目标表 |
| any | any | 其他未定义组合 | unavailable | fail closed，不恢复 legacy 目标表 |

匹配优先级固定为：`blocked/invalid` > execution/effective `unavailable` > `bearish` > `observation` > bullish high/medium/low > fail-closed。`observation+blocked` 必须为 blocked，`high+unavailable` 必须为 unavailable，`low+blocked` 必须为 blocked；low 不存在 triggered 合法组合。实现应使用单一 `resolve_target_display_mode(direction, effective_confidence, execution_state)` 纯函数，并用参数化测试遍历所有 direction/confidence/execution 组合，任何未列入的 cell 都返回 `unavailable`。

Phase 1 不展示精确交易日预期。`estimate_time()` 和 payload 中的 `time_estimate` 暂不删除，等待 Phase 2 回测后决定；合法 `technical_judgment.v1`、旧缓存、malformed cache 和 unavailable fallback 均不得渲染它。该字段仅保留为内部 diagnostics，不能进入正式 Markdown/HTML。

## 9. Recommendation Contract

`build_technical_judgment()` 必须按以下优先级明确生成 action，不由 recommendation 层猜测。报告推荐是 A/H 股现货多头持仓视角；bearish 目标可以展示下行结构，但不能产生 `follow_short`：

1. `trend_state` 为 `invalid/down`、`target.execution_state` 为 `invalid` 或 `target.direction` 为 `bearish`：`risk_control`；
2. 非 bearish 的 `target.producer_status/execution_state` 为 `blocked`：`wait_for_entry`，保持既有明确多头入场阻断的风险因子语义；bearish target 即使 blocked，现货多头视角仍保持 `risk_control`，不得产生“等待做空入场”文案；
3. `target.producer_status`、`target.execution_state`、`target.effective_confidence` 或 data quality 任一为 `unavailable`：`unavailable`；
4. `target.producer_status=observe`、`target.execution_state in {pending, observe}` 或 `trend_state=range`：`wait_for_confirmation`。low confidence 不存在合法 `triggered` 组合，见第 7.1 节；
5. `target.execution_state=triggered`、`effective_confidence in {high, medium}`、direction 为 `bullish` 且 trend 为 `strong_up/weak_up`：`follow`；
6. 其余：`unavailable`。

`recommendation_decision._classify_entry_constraint()` 优先读取完整合法的 `resonance.judgment`；一旦 schema 合法，绝不再混用 legacy trend/error fallback：

- `risk_control` 且 reconciled trend 已为 `down/invalid` -> 既有 `severe_technical`，保留既有风险因子；仅因 bearish target 产生的 `risk_control` -> 新的 display-only `risk_control` entry constraint，只限制仓位、不增加风险分；
- `wait_for_entry` -> 既有 `wait_for_entry`；只允许 target 明确 `blocked` 时使用；
- `wait_for_confirmation/unavailable` -> 新增 `wait_for_confirmation`，显示“看多但等待技术确认”或“技术证据不足，等待确认”；它不等同于趋势转弱，也不增加风险分；
- `follow` -> 继续检查既有 BIAS 过热限制；
- judgment 缺失 -> 保留旧 trend/price-target fallback。

新的 display-only `risk_control` 必须端到端落地：

- `_apply_entry_constraint()` 对正向 raw recommendation 输出“风险控制优先”；非正向 raw label 不得被升级；
- `build_risk_assessment()` 对 `risk_control` 应用 0-5% 防守仓位上限，规则与 `severe_technical` 一样优先于积极/谨慎仓位，但 `_entry_constraint_current_risk_factor()` 返回 `None`；
- `wait_for_confirmation` 对积极/谨慎仓位应用 5-10% 上限且同样不增加风险分；
- `risk_control`、`wait_for_confirmation` 的 renderer/header/position tests 必须分别断言标签、仓位和零新增风险分。

禁止继续依赖 `price_target.error == "关注/不操作"` 这样的中文字符串作为新 payload 的主判断条件。

`composite_score_section()` 在 Phase 1 内必须收敛为一条推荐路径：

- 调用者已传 `recommendation_decision`：直接使用；
- 调用者未传：使用现有 `build_recommendation_decision(..., pillar=pillar)` 构造 canonical decision，然后进入同一 header/recommendation rendering 分支；
- 删除 `_entry_quality_guardrail()`，不得在 path B 再从中文 target error 独立推断入场限制；
- legacy stock_raw 的兼容只存在于 `_classify_entry_constraint()` 内，且合法 `technical_judgment.v1` 永远优先于 legacy trend/error fallback。

因此传入与不传入 `recommendation_decision` 对同一 `stock_raw/pillar` 必须产生相同的 `display_recommendation`。不存在“新 schema path A”和“旧 guardrail path B”并行生效的过渡状态。

`wait_for_confirmation` 和 display-only `risk_control` 都不增加风险分：`_entry_constraint_current_risk_factor()` 对它们返回 `None`。后者固定把仓位限制为“技术方向偏空，以防守或观望为主，建议 0-5%”，但不能复用 `severe_technical` 的 4.0 分，除非 reconciled trend 本身已满足原有 severe 条件。风险章节必须把这些状态作为仓位 guardrail 使用，避免执行摘要与仓位建议漂移；不得改变任何风险分值、阈值或 EV/pillar 公式。

`wait_for_confirmation` 固定使用 `position_cap_note="技术目标尚未形成可执行确认，建议等待确认，仓位上限 5-10%"`；当原风险建议为“积极配置，最大仓位 20%”或“谨慎持有，仓位 10-15%”时应用该 guardrail。带合法 `technical_judgment.v1` 的新 payload 只有非 bearish target `blocked` 才能映射到 `wait_for_entry` 并沿用原有 1.5 分风险因子；pending、observe、unavailable、low-pending 和仅由 bearish target 产生的 risk_control 均不得进入该风险因子。legacy fallback 继续保持原行为。

本批不改变原始 EV、pillar score、risk-score 公式和权重，只统一展示推荐和仓位限制。Regression test 必须分别证明：既有明确 blocked 输入接入合法 judgment 前后仍保留同一 1.5 分因子；原先没有 entry-risk 因子的 pending/observe/unavailable 输入接入新 judgment 后风险分不变，唯一允许变化是仓位建议受 `wait_for_confirmation` 上限约束。

## 10. Renderer Rules

1. `TechnicalRenderer.render()` 在任何 target 分支前必须调用 `ensure_technical_judgment()`，随后只根据返回的合法 `technical_judgment.v1` 和 `display_mode` 渲染目标。现有 `if price_target and not error`、`elif price_target and error` 两套 target 展示分支都要被替换；旧 cache 的 `targets/conservative/base/aggressive/trigger_conditions/time_estimate` 只能保留为 diagnostics，不能被 renderer 直接消费。`_render_legacy()` 仅允许展示指标快照与独立 key levels，不得展示任何旧 target 表、阻断后“一旦满足条件”的三档目标或时间预期。
2. `TechnicalRenderer` 使用 `judgment.trend.summary` 和 target display matrix，不再用 `_build_conclusion()` 重新推断趋势强弱；旧缓存使用 `ensure_technical_judgment()` 的安全结果，不恢复完整 legacy 目标表。
3. 方向直接使用稳定 code，修复“中线看多被显示为观望”。bearish 在现货多头报告中固定使用 `levels_only + risk_control`，不展示下行三档精确目标。
4. 触发条件显示“已满足 / 待确认 / 不满足 / 数据不足”，而不是一组未判断的模板条件。ADX detail 使用固定 `ADX>=25`，当前 ADX 另列为 evidence；amount 缺失但量比通过时必须显示“成交额未核验”。
5. 市场和行业数据都缺失时，不渲染“市场/板块共振：未知”分析卡；只在分析限制中简短说明未参与判断。
6. 低置信度和观察位禁止精确三档目标及精确时间预期；新旧 payload 都不展示 `time_estimate`。
7. 正式 assembly 从 `RENDERERS` 删除 `("price_target", ..., "PriceTargetRenderer")`，由 `TechnicalRenderer` 唯一展示目标语义；该 class 和 export 暂保留给潜在独立调用者，但不得留在正式报告 registry。删除 registry 前，TechnicalRenderer contract tests 必须覆盖 ready、pending、blocked、invalid、observe、unavailable 的触发、止损、失效和恢复条件，证明没有丢失仍允许展示的信息。
8. HTML dashboard 只从 `stock_raw["technical"]` 读取 target，并从 `stock_raw["technical"]["indicators"]["_resonance"]["judgment"]` 读取 judgment，显示 action/有效置信度；不得继续从错误的顶层 `stock_raw["price_target"]` 读取。
9. 新 judgment 下只显示 `structure_label/effective_label`；旧六因子 `confidence/confidence_score` 即使更高也不能覆盖展示或 action。

## 11. Compatibility

- 保留旧 `price_target.direction/confidence/confidence_score/targets/error/reason` 字段；
- 新 renderer 只使用 `ensure_technical_judgment()` 的返回；不存在“judgment 为空时直接渲染 legacy target”的分支；
- `ensure_technical_judgment()` 必须总是返回结构完整且枚举合法的 `technical_judgment.v1`。它只信任原 payload 中 `schema == technical_judgment.v1`，并且 trend/target/action 的必需 code 均合法、`target.producer_status` 为合法枚举、`target.reason_code` 为非空稳定 code 的 judgment。版本不符或字段残缺时：若新 `structure_evidence + trigger_checks + trend_state` 完整则重建，否则生成 `target.direction=neutral / target.producer_status=unavailable / target.reason_code=untrusted_or_malformed_judgment / target.effective_confidence=unavailable / target.execution_state=unavailable / target.display_mode=unavailable / action.state=unavailable` 的安全 judgment；保留旧 target 字段作 diagnostics，技术章节只可继续展示独立 key levels，不得展示旧精确目标、旧 error 分支目标、`stop_loss`、触发条件、失效条件或 `time_estimate`；recommendation 必须把这个显式 `unavailable` action 映射到 `wait_for_confirmation`，不得再次读取 legacy 中文 target error；
- 旧 payload 无 error、旧 payload 有“关注/不操作”、weak-consensus 旧 cache、unknown schema 和 malformed schema 都必须通过同一安全 fallback。任何一种都不能恢复保守/基准/激进目标表；
- recommendation 同样保留旧 payload fallback；
- 保持 `TechnicalCollector.collect()` 与单股入口返回的顶层结构，但 collector 内部不得重复计算 target；
- 不修改技术专用入口脚本。

## 12. Failure Modes And Tests

| Failure mode | Observable failure | Required test |
|---|---|---|
| 观察位仍展示精确目标 | `观望/观察位` 下出现三档目标 | renderer test 禁止目标表和时间预期 |
| 方向 code 漂移 | bullish 被显示为观望 | contract + renderer test |
| 已越过颈线仍显示未触发 | 现价高于触发价但 price pending | price trigger unit test |
| amount 缺失未披露限制 | 仅量比通过但报告未说明成交额未核验 | amount-limitation test |
| amount 缺失导致永久 pending | 常规 OHLCV 样本永远无法 triggered | amount-optional test |
| ADX 当前值被写成阈值 | `ADX>47.4` | trigger rendering test |
| MA60 上方写成略低于 | close > MA60 且出现“略低于/收回” | state machine regression test |
| 趋势阶段与健康度冲突 | 主升期同时写趋势破坏 | judgment reconciliation test |
| recommendation 继续解析中文 error | 改文案后仓位限制失效 | explicit judgment precedence test |
| 市场数据缺失仍输出占位卡 | 报告出现“市场/板块共振：未知” | renderer omission test |
| 旧缓存无法渲染 | 无 judgment 时空白/异常 | legacy fallback test |
| 旧缓存回到旧三档表 | 无结构元数据仍显示精确目标 | cache-safe-fallback test |
| 旧 error 分支泄漏目标 | blocked/legacy error 下出现“一旦满足条件”三档目标 | renderer legacy-error target-hidden test |
| blocked payload 泄漏目标 | 盈亏比不足仍显示三档目标 | renderer blocked test |
| 主路径重算目标 | resonance judgment 与最终 target 不同 | collector final-target identity test |
| 港股错误用 A 股阈值 | 港股量比仍要求 1.5 | HK threshold propagation test |
| HTML 与 Markdown 漂移 | dashboard 显示 N/A 或旧目标 | dashboard nested-payload test |
| 数据质量 cap 被绕过 | raw high + quality low 仍 full/follow | effective-confidence action/display test |
| 等待确认与风险仓位漂移 | 摘要等待但风险仍积极配置 | wait-for-confirmation risk-position test |
| 成功目标缺少结构化 stop | judgment 被迫解析止损文案 | successful profit-risk payload test |
| observation 被盈亏比升级为阻断 | fib-only 目标增加 1.5 入场风险分 | observation-before-risk-filter test |
| ready 缺少风险计划 | 正常目标表没有 numeric trigger/stop | ready-risk-plan invariant test |
| 结构证据元数据含义漂移 | 单周期被标为双周期同向或 convergence 丢失 | structure-evidence derivation test |
| 早退状态依赖中文文案 | 修改 error 文案后状态或推荐变化 | target status/reason-code matrix test |
| unavailable 未进入安全约束 | 损坏缓存恢复积极推荐或仓位 | unavailable-action guardrail test |
| pending 被误当阻断并增加风险分 | judgment 接入后 risk score 增加 1.5 | pending risk-score invariance test |
| blocked 丢失既有风险因子 | 新 schema 下盈亏比阻断不再增加 1.5 | blocked risk-score parity test |
| bearish 被多头 MACD 规则误杀 | 空头趋势中死叉扩张仍 blocked | direction-aware momentum blocker test |
| 双周期形态冲突后仍合成目标 | 使用第一个形态生成三档目标 | pattern-conflict pre-synthesis test |
| 损坏缓存被半信任 | 残缺 judgment 恢复旧目标表 | malformed-schema cache fallback test |
| 两套推荐入口漂移 | 是否传 recommendation_decision 导致推荐不同 | composite unified-path test |
| 双置信度冲突 | 旧 confidence 高于 effective 仍显示高置信目标 | effective-confidence renderer precedence test |
| bearish 精确目标泄漏 | 风险控制结论下出现做空三档目标 | bearish levels-only renderer test |
| bearish 被误加 severe 风险分 | 非 down/invalid 的 bearish target 额外增加 4.0 分 | bearish display-only risk-control parity test |
| 近似复权被高估 | local_qfq_approx 仍输出 high/full | adjustment-cap matrix test |
| 低置信度伪精确触发 | low 结构被标为 triggered | low price-trigger unknown test |
| judgment 状态码丢失 | 下游重读中文 error/reason 或错误 fallback | producer-status/reason-code propagation test |
| display-only 风险控制未闭环 | 摘要写风险控制但仓位仍积极，或被误加 4.0 分 | risk-control header/position/zero-risk test |
| 旧缓存泄漏止损诊断 | 无法信任的旧 target 显示 stop/触发/失效条件 | unsafe-cache key-levels-only test |

### 12.1 Scenario fixtures

至少覆盖：

1. 双周期同向形态 + 汇聚 + 全部触发：high/triggered/full；
2. 单周期形态 + 周线确认但量能未知：medium/pending/conditional；
3. 单周期形态且无确认：low/conditional；
4. 纯斐波那契：observation/levels-only；
5. 与目标方向相反的 MACD 柱线扩张：blocked；
6. 盈亏比不足：blocked；
7. close 在 MA60 上方 0-3%；
8. 旧 payload 无 judgment；
9. amount 缺失但量比确认；
10. 做空目标的实体、stop 和失效；
11. 主报告 collector 只产生并消费一次最终 target；
12. 港股量比阈值为 1.3；
13. raw high 但 data quality low：effective low/conditional/wait；
14. bearish target triggered：下行结构可展示，action 为 risk_control；
15. 成功目标 payload 含 numeric trigger/stop，renderer 与 judgment 不解析 prose；
16. 缺字段或未知 schema 的缓存降级为 target unavailable，技术章节仅保留独立 key levels，推荐进入 wait_for_confirmation；
17. 每个 price-target early return 都有稳定 status/reason_code，修改中文文案不改变 judgment；
18. 新 schema 的 blocked 保留既有 wait_for_entry 风险因子，pending/observe/unavailable 只限制仓位、不增加风险分；
19. A 股与港股 collector/Wind 路径都显式传递 market/is_hk；
20. 日周形态方向相反时在目标合成前 invalid，payload 不含正常三档目标；
21. fib-only 即使测得盈亏比不足仍为 observation，不产生 wait_for_entry 风险因子；
22. high/medium/low 候选缺 neckline 或 conservative target 时为 risk_plan_unavailable，ATR 无效时为 invalid_atr；
23. 单周期 `patterns_aligned=None`，双周期同向/反向分别为 True/False，daily-only convergence 也能进入 `fib_convergence`；
24. 所有 `ready` payload 都有完整 numeric profit_risk，缺任一必需字段时测试失败；测试 helper 必须遍历全部 scenario fixture，而不是只检查一个成功样本；
25. 旧 cache 分别覆盖无 error、有 error、weak-consensus、unknown schema 和 malformed schema，Markdown/HTML 均不出现三档目标或时间预期；
26. `composite_score_section()` 传与不传 canonical recommendation decision 时输出同一 display recommendation；合法 judgment 的 path B 自动进入 canonical builder，旧 cache unavailable 仅保留独立 key levels，不渲染 stop、触发条件、失效条件、目标表或时间预期；
27. 参数化遍历 direction × effective_confidence × execution_state，验证 display resolver 的优先级与 fail-closed 行为，至少显式断言 high+unavailable、low+blocked、observation+blocked、bearish+ready；
28. 做多负柱扩张与做空正柱扩张各自 blocked，做多正柱扩张与做空负柱扩张均不 blocked；
29. amount 缺失但量比通过时，renderer 明示“成交额未核验”；
30. `local_qfq_approx -> low`、qfq residual gap -> low、clean qfq/raw -> high、required qfq unrepaired -> unavailable；
31. 旧六因子 confidence 与 effective_confidence 冲突时，Markdown/HTML 只显示 effective label；
32. `fib_only` 恒为 observation，并证明 method_family 只出现在 diagnostics，不参与 action 分支；
33. A 股与港股分别通过 collector 和 Wind 调用链验证 `quote.market/is_hk` 以及量比阈值；
34. low confidence 的 price check 固定 unknown，execution 不得为 triggered；
35. 新 judgment 的任何状态及旧 cache 都不渲染 `time_estimate`；
36. `near_or_slightly_broken` 仅能由 legacy adapter 映射为 `near_above`，新 producer/renderer 不再产生或判断旧 code。
37. bearish target 且 trend 非 down/invalid 时只限制仓位、风险分不变；trend 已 down/invalid 时继续沿用既有 severe risk factor，不重复计分。
38. 每个 price-target return branch 都把稳定的 `producer_status/reason_code` 复制进 judgment；只修改 legacy 中文 `error/reason` 不得改变 judgment、action、仓位或 renderer 输出。
39. 非 down/invalid 趋势下的 bearish `risk_control`：正向 raw recommendation 显示“风险控制优先”，仓位为 0-5%，新增风险因子为 0；down/invalid 趋势仍保留既有 severe 风险因子，且不重复计分。
40. 无 judgment、unknown schema 和 malformed schema 的 legacy cache 只能展示独立 key levels；Markdown/HTML 均不得展示 `stop_loss`、trigger conditions、invalidations、三档目标或 `time_estimate`。
41. `trend_state=range` 与 target/data quality unavailable 同时出现时 action 必须为 `unavailable`；只有数据可用时 range 才映射 `wait_for_confirmation`。

## 13. Allowed Scope

Runtime 候选文件：

- `scripts/utils/reporter/price_target.py`
- `scripts/utils/reporter/technical_state_machine.py`
- `scripts/utils/reporter/technical_analyzer.py`
- `scripts/utils/data_collector.py`
- `scripts/utils/report_skills/technical_skills.py`
- `scripts/utils/reporter/recommendation_decision.py`
- `scripts/utils/reporter/scoring_engine.py`（仅统一 `composite_score_section()` 到 canonical recommendation path、删除 `_entry_quality_guardrail()`、增加 `wait_for_confirmation` 仓位 guardrail；不得增加风险分或改阈值）
- `scripts/utils/reporter/sections/technical_renderer.py`
- `scripts/utils/reporter/sections/html_dashboard_renderer.py`
- `scripts/utils/report_skills/assembly_skills.py`

对应测试文件可修改。禁止修改：

- `scoring_engine.py` 的风险分、阈值、EV、pillar 计算（仅允许上面的仓位 guardrail 分支）
- 其他 `technical_*.py` 指标/形态算法
- `KnowledgeSynthesizer` 和任何 LLM prompt
- Chapter 4、引用、producer、memo、snapshot
- 数据采集与外部 API

`data_collector.py` 仅允许调整 technical payload 的编排和参数传播；不得修改任何行情、周线、资金流或概念板块 fetcher。Phase 1 不修改 `report_quality.py`，避免把技术判断任务与 Chapter 4/ref gate 产生耦合；Markdown 语义由 renderer focused tests 和正式报告人工验收覆盖。

## 14. Code Budget And Deletion Ledger

分两批控制 runtime：Batch A（target/judgment/collector/cache）目标净增 `<= +120`、hard stop `+160`；Batch B（renderer/recommendation/dashboard/quality）目标净增 `<= +80`、hard stop `+120`；合计目标 `<= +180`、hard stop `+240`。新增 judgment 契约时必须同步删除/收缩重复判断：

- 删除或收缩 `TechnicalRenderer._build_conclusion()` 的二次趋势分类；
- 替换 renderer 中目标方向、置信度、条件和时间的内联分支；
- recommendation 新 payload 不再解析中文 error，旧解析仅保留为 compact fallback；`composite_score_section()` 缺省时构造 canonical decision，删除 `_entry_quality_guardrail()`；
- 删除 collector 内重复的 `analyze_price_target()` 调用；
- 将 `compute_indicators()` 收缩为 `build_technical_payload()` 的兼容 wrapper；
- 从正式 assembly registry 删除 `PriceTargetRenderer`；
- 用 display resolver 替换 `TechnicalRenderer` 中 success/error 两套旧 target 分支，并删除旧 `time_estimate` 渲染；
- 不新增第二套目标 selector 或第二个状态机模块。

若任一批或合计超过对应 hard stop，停止并返回设计，不以继续堆 helper 解决。Batch A 的测试 fixture 必须先提供完整 mock `technical_judgment.v1`，供 Batch B renderer/recommendation TDD 使用；Batch B 不反向依赖尚未落地的 live collector 数据。Batch A 完成后先验证 schema、target status、HK 参数和 cache adapter，再启动 Batch B。

## 15. Verification

1. TDD：每批先 RED 再 GREEN；
2. focused：price target、state machine、technical renderer、recommendation tests；
3. downstream：technical skills contract、scoring/risk contract、report quality；
4. `bash tools/ci_grep_gates.sh`；
5. `git diff --check`；
6. 只在代码审查通过后重新生成复旦微电和中际旭创正式报告；
7. 新报告必须检查：无观望精确目标、无错误方向、无已满足触发仍待触发、无 MA60 方位矛盾、无精确时间预期。

## 16. Stop Conditions

- 需要修改评分、风险评分、EV 或目标价计算公式；
- 需要新增股票/行业专用 hardcode；
- 需要访问网络或刷新行情才能让单元测试通过；
- 旧 payload fallback 无法保留；
- runtime 合计净增超过 `+240`，或任一批超过第 14 节自己的 hard stop；
- focused/downstream 测试出现无法解释的跨模块回归。

## 17. Design Delta After Codex Self-review

- accepted：display/action 全部切换到 `effective_confidence`；低置信度不得 `follow`。
- accepted：成功目标持久化完整 numeric `profit_risk`，状态机禁止解析中文止损文案。
- accepted：锁定 price/volume/momentum 公式，并把 MACD blocker 改为方向化规则。
- accepted：允许 `scoring_engine.py` 仅增加 `wait_for_confirmation` 仓位 guardrail，风险分保持不变。
- accepted：明确 HK 参数传播、缓存 schema 校验、bearish 的多头持仓语义。
- accepted：统一合计 runtime hard stop 为 `+240`。
- accepted：所有 target return branch 使用稳定 `status/reason_code`；中文 `error/reason` 只作兼容展示。
- accepted：完整 numeric `profit_risk` 仅要求 ready 和风险收益比不足路径，其他早退不得伪造执行数据。
- accepted：action 使用 `wait_for_entry` 与 `wait_for_confirmation` 两个稳定 code；blocked 保持既有风险因子，pending/observe/unavailable 不新增风险分。
- accepted：`unavailable` judgment 必须约束推荐和仓位，禁止回退解析旧中文 target error。
- accepted：`compute_indicators`、统一 payload builder、collector 与 Wind 路径显式传播 market/is_hk。
- accepted：结构置信度必须先于盈亏比过滤；observation 永不因盈亏比进入 blocked/wait_for_entry。
- accepted：补充 `risk_plan_unavailable` 与 `invalid_atr`，并把完整 numeric profit_risk 设为 ready 强不变量。
- accepted：锁定 structure-evidence 字段的三态和 convergence 计算规则，避免压缩候选时丢失证据。
- deferred：目标价公式回测、ATR 时间模型校准和新增做空交易建议继续留在 Phase 2 之后。
- external Round 1 required：yes。此次修订触及 action、风险仓位展示和方向化 trigger blocker；Round 2 仅在 Round 1 存在 blocker、未关闭 must-fix 或高风险边界变化时触发。

## 18. Design Delta After Claude Round 1

### Accepted

- B1：renderer 在任何 target 分支前强制经过 `ensure_technical_judgment()`；旧 success/error、weak-consensus、unknown/malformed cache 均 fail closed，禁止三档目标和时间预期。
- B2：`composite_score_section()` 缺省时构造 canonical `RecommendationDecision`，删除 `_entry_quality_guardrail()`，消除两条推荐策略路径。
- B2 follow-up：仅由 bearish target 产生的 risk-control 是 display-only 仓位约束，不复用 severe 4.0 风险因子；只有 reconciled trend 已 down/invalid 时保留既有 severe 风险语义。
- B3：锁定 skill -> collector builder -> analyzer quote -> price target 的 `market/is_hk` 调用链，collector 与 Wind 都覆盖港股 1.3 量比阈值。
- M1：增加结构化 adjustment cap 矩阵；近似复权和有残留断点的 qfq 上限为 low，未修复必需复权为 unavailable。
- M2：用方向参数化 MACD expansion blocker 替换单向 `_macd_dead_expanding()`。
- M3：low confidence 不做精确 price trigger，price check 为 unknown，execution 不得 triggered。
- M4：bearish 在现货多头报告中固定 `levels_only + risk_control`。
- M5：新旧 payload 都不展示 `time_estimate`，字段仅保留 diagnostics。
- M6：新 schema renderer 只显示 structure/effective confidence，旧六因子 confidence 不再参与展示或 action。
- M7：convergence 在 target candidate 压缩前，从 daily + weekly 原始 candidate 集合保存。
- M8：明确 `fib_only -> observation` 恒等映射；method family 仅负责方法溯源。
- N1-N4：修正 dashboard nested path、`near_above` 下游枚举、ADX 固定阈值文案、正式 registry 删除 PriceTargetRenderer，并全部加入 contract tests。

### Rejected

- 无。

### Deferred

- 不删除 `PriceTargetRenderer` class/file，只从正式 registry 移除；独立调用兼容清理留待后续审计。
- 不删除旧六因子 confidence 和 `time_estimate` producer 字段，仅停止正式报告消费，等待 Phase 2 回测决定数据层清理。
- 不修改 `report_quality.py`；本轮用 renderer contract 和正式报告验收隔离 Chapter 4/ref gate。

### R2 required

yes。Round 1 有三个 blocker，且本轮修订明确改变了推荐入口统一、legacy target 安全降级和 HK 参数传播三条高风险边界；必须完成 Round 2 只读审查后才能写 implementation task。

## 19. Design Delta After Codex Second Self-review

### Accepted

- judgment 同时持久化稳定的 `target.producer_status/reason_code`；下游只能读 judgment code，不得重新解析中文 error/reason。
- display-only `risk_control` 明确接入 recommendation header、risk position guardrail 和零新增风险因子三条消费者路径；与真实 down/invalid 的 severe 风险语义分开。
- 删除“low confidence 仍可 triggered”的死分支；low 的 price check 恒为 unknown，最多 pending。
- 未知或损坏 legacy cache 只保留独立 key levels；旧 stop、触发/失效条件和所有 target diagnostics 一律不进入正式展示。
- 动作判定显式区分 `producer_status`、`execution_state`、`trend_state` 和 data quality；unavailable 高于 range，避免损坏数据被误写为等待确认。

### Self-review result

`ok for Claude Round 2`。本次只补齐状态、消费者路径和缓存 fail-closed 契约；未扩大 runtime scope、未改变技术公式、评分阈值、风险分值、EV/pillar 或数据采集边界。
