# 高级技术分析 Phase 3 设计文档

## 修订实施计划：结构识别 + 底部观察 + 市场共振

---

## 0. Phase 3 总目标

Phase 3 的目标不是继续堆指标，也不是直接做复杂交易信号，而是在 Phase 2 已有“中期趋势提醒系统”的基础上，增强三个能力：

1. **趋势结构识别**
   判断中期结构是否仍健康，例如回调低点是否抬升、结构是否破坏。

2. **区间/通道/底部区域观察**
   识别箱体、通道、波动收敛、疑似底部构筑等结构，但避免过早输出“底部确认”。

3. **市场 / 行业 / 主题共振分析**
   将个股技术状态放到大盘、行业、主题指数环境中解释，判断顺风、逆风、独立行情或系统性压力。

Phase 3 仍然坚持：

```text
周线定背景，日线做确认；
MA20/MA60 定中期结构；
技术指标是辅助，不是主帅；
底部区域只能观察，不能轻易确认；
Renderer 只负责展示，不负责判断。
```

---

## 1. Phase 3 执行范围

### 1.1 本阶段优先完成

```text
Phase 3A：结构与共振
- 7.1 趋势结构健康度
- 7.4 通道 / 箱体识别
- 9.1 市场 / 行业 / 主题共振分析
- 最小输出契约

Phase 3B：底部区域观察
- 8.1 底部区域观察
- 8.2 飞镖策略：仅作为分批观察框架，不直接写“买入/建仓”
```

### 1.2 本阶段暂不完成

```text
- 6.2 三重背离完整版
- 头肩顶复杂形态
- 完整输出格式标准化大改版
```

说明：三重背离完整版需要 confirmed swing high/low、历史 MACD/RSI/BOLL 对比和 evidence 体系。这部分复杂度高，容易误判，继续后置。

---

## 2. 模块边界

### 2.1 推荐模块归属

| 功能                 | 实现位置                                               | 原因                                      |
| ------------------ | -------------------------------------------------- | --------------------------------------- |
| 7.1 趋势结构健康度        | `technical_structure.py`                           | swing high/low、回调低点抬升属于结构分析，不属于 pattern |
| 7.4 通道 / 箱体识别      | `technical_structure.py`                           | 区间结构、通道边界、突破状态属于结构层                     |
| 8.1 底部区域观察         | `technical_structure.py`                           | 本质是区域/结构识别                           |
| 8.2 飞镖策略 signal 生成 | `technical_strategy.py`                            | 策略判断属于独立策略层，不应放状态机                     |
| 8.2 飞镖策略渲染         | `technical_renderer.py`                            | Renderer 只渲染已生成的 signal，不做判断            |
| 9.1 共振分析           | `technical_resonance.py`                           | 独立模块，负责个股 vs 市场/行业/主题                   |
| 指数数据获取             | `data_collector.py`                                | 数据层职责                                   |
| 股票→指数映射            | `config/market_index_map.json` + helper            | 配置与映射层                                  |

### 2.2 Renderer 边界

禁止在 renderer 中做策略判断。

错误：

```python
if bottom_signal["is_bottom_region"] and weekly_trend != "单边下跌":
    render_dart_strategy(...)
```

正确：

```python
dart_strategy = resonance.get("dart_strategy")
if dart_strategy:
    render_dart_strategy(dart_strategy)
```

策略判断应由 `evaluate_dart_strategy(...)` 完成。

---

## 3. 最小输出契约

Phase 3 暂不做完整输出格式标准化，但每个新增模块必须遵守最小输出契约，防止 renderer 猜字段、猜文案。

### 3.1 标准输出字段

每个新增结构必须尽量包含：

```python
{
    "state": "...",
    "confidence": "高" | "中" | "低",
    "evidence": [...],
    "missing": [...],
    "action_hint": "...",
}
```

### 3.2 适用模块

以下新增模块必须遵守：

```text
detect_trend_structure_health()
detect_channel_or_box_structure()
evaluate_bottoming_region()
evaluate_dart_strategy()
evaluate_market_resonance()
```

### 3.3 Renderer 规则

Renderer 不得自行推断业务结论，只能展示 `state`、`confidence`、`evidence`、`missing`、`action_hint`。

如果字段缺失，renderer 应降级显示：该模块证据不足，暂不输出结论。

---

## 4. Task 1：趋势结构健康度

### 4.1 文件

- Modify: `scripts/utils/reporter/technical_structure.py`
- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Test: `tests/reporter/test_trend_structure_health.py`

### 4.2 函数签名

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
```

### 4.3 规则

识别过去 60 日 confirmed swing lows：

1. 局部低点必须前后各 `swing_left` / `swing_right` 根 K 线确认。
2. **最近一根 K 线不能作为 confirmed low**，因为没有右侧确认。
3. 两个低点之间至少间隔 `min_gap_days`。
4. 后一个低点高于前一个低点超过 `max(tolerance_pct, atr_multiplier * ATR)` → 低点抬升。
5. 后一个低点低于前一个低点超过 `max(tolerance_pct, atr_multiplier * ATR)` → 低点下移 / 结构破坏。
6. 否则视为低点走平。

**间隔 3 天的低点降低置信度**：当两个 swing low 之间间隔仅为 3 天时，`confidence` 降为"低"；间隔 >=5 天时 `confidence` 为"中"或"高"。

### 4.4 返回结构

```python
{
    "state": "低点抬升" | "低点走平" | "低点下移" | "无法判断",
    "is_healthy": True | False | None,
    "confidence": "高" | "中" | "低",
    "swing_lows": [
        {"date": "2026-05-12", "price": 180.2},
        {"date": "2026-06-03", "price": 188.5}
    ],
    "last_low_relation": "higher" | "flat" | "lower" | "unknown",
    "evidence": [...],
    "missing": [...],
    "action_hint": "结构健康，回调低点抬升" | "结构转弱，低点下移" | "证据不足，继续观察"
}
```

当 `swing_lows` 数量不足 2 个时，`state`="无法判断"，`missing` 包含"confirmed swing lows 不足"，不作为失败条件。

### 4.5 测试场景

1. 构造低点逐步抬升 → state=低点抬升
2. 构造低点下移 → state=低点下移
3. 低点差异小于 tolerance → state=低点走平
4. swing lows 不足 2 个 → state=无法判断，missing=["swing_lows 不足"]
5. 最近一根 K 线是低点但无右侧确认 → 不得计入 confirmed low

---

## 5. Task 2：通道 / 箱体识别

### 5.1 文件

- Modify: `scripts/utils/reporter/technical_structure.py`
- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Test: `tests/reporter/test_channel_or_box_structure.py`

### 5.2 函数签名

```python
def detect_channel_or_box_structure(
    df_daily: pd.DataFrame,
    window: int = 20,
    confirm_days: int = 2,
    slope_tolerance_pct: float = 0.005,
) -> dict:
```

### 5.3 关键实现原则

不要直接用所有 high/low 拟合通道，避免被极端影线污染。

推荐流程：

1. 用 window 内 confirmed swing highs 拟合上轨。
2. 用 window 内 confirmed swing lows 拟合下轨。
3. 如果 swing 点不足，则降级用分位数区间：
   - `upper = high.quantile(0.9)`
   - `lower = low.quantile(0.1)`
4. 判断上轨/下轨斜率是否接近。
5. 根据 slope 差判断：
   - `abs(slope_diff) <= slope_tolerance_pct` → 水平箱体
   - `slope_diff` 在 `slope_tolerance_pct ~ 0.01` → 通道（低置信度）
   - `slope_diff > 0.01` → 不识别为平行通道
6. 根据斜率符号判断上升通道 / 下降通道。
7. 突破检测必须使用"通道基准区间"之外的最近 `confirm_days`，不得把突破确认 K 线纳入通道拟合。

**斜率容差分级**：
- `abs(slope_diff) <= 0.005` → confidence="高"
- `0.005 < abs(slope_diff) <= 0.01` → confidence="低"，state 为通道/箱体但标注低置信
- `abs(slope_diff) > 0.01` → state="无明显通道"

### 5.4 防止当前 K 线污染

必须使用：

```python
channel_base = df_daily.iloc[-window-confirm_days:-confirm_days]
confirm_bars = df_daily.iloc[-confirm_days:]
```

不要用 `df_daily.tail(window)` 直接包含突破 K 线做通道拟合。

### 5.5 返回结构

```python
{
    "state": "水平箱体" | "上升通道" | "下降通道" | "无明显通道",
    "confidence": "高" | "中" | "低",
    "upper": 260.0,
    "lower": 220.0,
    "position": "接近上轨" | "接近下轨" | "中部" | "区间外",
    "breakout_status": "未突破" | "向上突破待确认" | "向上突破确认" | "向下跌破待确认" | "向下跌破确认",
    "evidence": [...],
    "missing": [...],
    "action_hint": "区间内观望" | "等待突破确认" | "趋势跟随" | "风险警戒"
}
```

### 5.6 测试场景

1. 水平箱体：高低区间稳定，输出 state=水平箱体
2. 上升通道：上轨/下轨斜率均为正，输出 state=上升通道
3. 下降通道：上轨/下轨斜率均为负，输出 state=下降通道
4. 向上突破：最近 confirm_days 收盘站上上轨，输出 向上突破确认
5. 向下跌破：最近 confirm_days 收盘跌破下轨，输出 向下跌破确认
6. 突破 K 线不得参与通道拟合

---

## 6. Task 3：底部区域观察

### 6.1 命名要求

不要使用 `bottom_confirmed` 或“底部确认”。Phase 3 中只能使用：

```text
底部区域观察
疑似止跌区域
底部构筑中
底部信号增强
```

### 6.2 文件

- Modify: `scripts/utils/reporter/technical_structure.py`
- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Test: `tests/reporter/test_bottoming_region.py`

### 6.3 函数签名

```python
def evaluate_bottoming_region(
    df_daily: pd.DataFrame,
    df_weekly: pd.DataFrame,
    indicators: dict,
    trend_state: dict,
    structure_health: dict | None = None,
) -> dict:
```

### 6.4 条件设计

使用 5 条条件：

1. **波动率收敛**：过去 20 日振幅 < 前一段 20 日振幅的 40%。
2. **长期支撑附近**：价格位于周线 MA20 / MA60 附近（< 5%）。
3. **BIAS 负偏离但不再创新低**：当前 BIAS 为负；最近 5 日 BIAS 没有继续创 20 日新低。
4. **价格不再有效跌破最近 swing low**：最近 swing low 未被有效跌破。
   - 若 `structure_health` 缺失或 `swing_lows` 为空，此条件计为 **missing**，不视为"满足"或"不满足"。
5. **短期修复迹象**：MA5/MA10 开始走平，或价格重新站上 MA5。

### 6.5 状态分层

| 满足条件 | 状态 |
|---------|------|
| 0-2 条 | none |
| 3 条 | bottom_watch |
| 4 条 且 weekly_trend != "单边下跌" | bottom_candidate |
| 5 条 且 放量站上 MA20 | bottom_strengthened |

注意：即使 state = bottom_strengthened，报告里也不要写“底部确认”。只能写“底部区域进一步确认”或“底部构筑信号增强”。

### 6.6 返回结构

```python
{
    "state": "none" | "bottom_watch" | "bottom_candidate" | "bottom_strengthened",
    "confidence": "高" | "中" | "低",
    "score": 3,
    "total": 5,
    "evidence": [...],
    "missing": [...],
    "action_hint": "仅作底部区域观察，不构成买入信号",
    "risk": "若跌破最近swing low，则底部观察失效"
}
```

### 6.7 测试场景

1. 只满足 2 条 → state=none
2. 满足 3 条 → state=bottom_watch
3. 满足 4 条且周线不是单边下跌 → state=bottom_candidate
4. 周线单边下跌时不得升级为 bottom_candidate
5. 未站上 MA5/MA10 时不得输出强观察文案
6. structure_health 缺失时 swing_low 条件计入 missing

---

## 7. Task 4：飞镖策略改为分批观察框架

### 7.1 命名与边界

不要让 renderer 判断飞镖策略是否触发。Renderer 只展示 `resonance["dart_strategy"]`。

### 7.2 文件

- **Create**: `scripts/utils/reporter/technical_strategy.py`
- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Modify: `scripts/utils/reporter/sections/technical_renderer.py`
- Test: `tests/reporter/test_dart_strategy.py`

### 7.3 函数签名

```python
def evaluate_dart_strategy(
    bottom_signal: dict,
    trend_state: dict,
    indicators: dict,
    invalidation: dict,
) -> dict | None:
```

### 7.4 触发条件

全部满足才触发：

1. `bottom_signal.state` in `["bottom_candidate", "bottom_strengthened"]`
2. `weekly_trend != "单边下跌"`
3. `price >= MA5`
4. `invalidation` 中存在明确失效位

### 7.5 输出文案原则

禁止输出：分批买入、建仓、加仓、满仓。

允许输出：分批观察、分层验证、逐步提高关注度、等待确认。

### 7.6 返回结构

```python
{
    "state": "active",
    "confidence": "中",
    "evidence": [...],
    "missing": [...],
    "action_hint": "底部区域观察成立，可采用分批观察框架",
    "steps": [
        {
            "level": 1,
            "condition": "重新站上MA5",
            "action": "进入观察清单"
        },
        {
            "level": 2,
            "condition": "站上MA10且量能改善",
            "action": "提高关注度"
        },
        {
            "level": 3,
            "condition": "站上MA20",
            "action": "视为中期修复确认"
        }
    ],
    "invalid_if": "跌破最近swing low"
}
```

### 7.7 Renderer 输出

Renderer 只渲染：

```markdown
**底部区域观察框架**：
- 第一层：重新站上 MA5 → 进入观察清单
- 第二层：站上 MA10 且量能改善 → 提高关注度
- 第三层：站上 MA20 → 视为中期修复确认
- 失效条件：跌破最近 swing low
```

---

## 8. Task 5：市场 / 行业 / 主题共振分析

### 8.1 文件

- Create / Modify: `scripts/utils/reporter/technical_resonance.py`
- Modify: `scripts/utils/reporter/data_collector.py`
- Create: `config/market_index_map.json`
- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Test: `tests/reporter/test_market_resonance.py`

### 8.2 数据流

```text
DataCollector.collect(stock_code)
    ├─ 个股日K/周K
    ├─ load_market_index_map(stock_code)
    ├─ fetch_index_bars(index_code) for market / sector / thematic
    └─ 写入 tech_data["market_context"]

TechnicalAnalyzer.analyze()
    ├─ 个股趋势状态
    ├─ 市场指数趋势状态 (analyze_index_trend 复用 classify_trend_state)
    ├─ 行业指数趋势状态
    ├─ 主题指数趋势状态
    └─ evaluate_market_resonance()
```

### 8.3 映射加载顺序

报告生成时不要强依赖在线 akshare。

推荐顺序：

1. 用户/内部配置显式指定
2. 本地 `config/market_index_map.json`
3. 代码前缀 fallback
4. 单独维护 `update_market_index_map` 脚本用于在线刷新

不要在每次报告生成时主动在线更新映射表。在线刷新应是独立命令：

```bash
python scripts/utils/reporter/update_market_index_map.py
```

### 8.4 代码前缀 Fallback

不在 `market_index_map.json` 中的股票，用代码前缀判定：

| 前缀 | 所属市场 | 市场指数代码 |
|-----|---------|------------|
| 600/601/603/605 | 沪市主板 | 000001（上证综指） |
| 000/001/002/003 | 深市主板/中小板 | 399001（深证成指） |
| 300 | 创业板 | 399006（创业板指） |
| 688 | 科创板 | 000688（科创50） |

行业/主题映射缺失时：
- sector 置为 None，resonance 中标注 `missing: ["sector mapping missing"]`
- thematic 置为 market index（降级）

### 8.5 market_index_map.json 结构

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
  }
}
```

**原则**：只手动维护关注池中的股票（6只+新关注的），其余全部走前缀 fallback。

### 8.6 指数趋势复用

对指数数据也跑 `classify_trend_state()` + `compute_trend_health()`，复用 Phase 2 逻辑。

新增 `analyze_index_trend(df_index_daily, df_index_weekly)` 包装函数，返回与个股相同的趋势状态结构。

### 8.7 evaluate_market_resonance 签名

```python
def evaluate_market_resonance(
    stock_trend_state: dict,
    market_trend_state: dict | None = None,
    sector_trend_state: dict | None = None,
    theme_trend_state: dict | None = None,
    mapping_meta: dict | None = None,
) -> dict:
```

### 8.8 返回结构

```python
{
    "state": "顺风共振" | "逆风独立" | "弱于板块" | "系统性压力" | "等待补涨确认" | "未知",
    "confidence": "高" | "中" | "低",
    "market_trend": {...},
    "sector_trend": {...},
    "theme_trend": {...},
    "relative_strength": "强于行业" | "弱于行业" | "同步" | "未知",
    "evidence": [...],
    "missing": [...],
    "impact": "...",
    "action_hint": "..."
}
```

### 8.9 共振规则矩阵

| 个股 | 行业 | 大盘 | 状态 |
|-----|-----|------|------|
| 强 | 强 | 强 | 顺风共振 |
| 强 | 弱 | 弱 | 逆风独立 |
| 弱 | 强 | - | 弱于板块 |
| 弱 | 弱 | 弱 | 系统性压力 |
| 震荡 | 强 | - | 等待补涨确认 |
| 震荡 | 弱 | - | 震荡偏弱 |

### 8.10 缺数据降级

如果指数数据缺失：

```python
{
    "state": "未知",
    "confidence": "低",
    "missing": ["sector index data missing"],
    "impact": "暂未接入完整市场/行业数据，本次共振分析仅作占位。"
}
```

不得报错。

---

## 9. Task 6：Renderer 接入最小输出契约

### 9.1 文件

- Modify: `scripts/utils/reporter/sections/technical_renderer.py`
- Test: `tests/reporter/test_phase3_renderer_contract.py`

### 9.2 渲染模块

Renderer 应支持以下新字段：

```text
structure_health
channel_status
bottom_signal
dart_strategy
market_resonance
```

### 9.3 渲染原则

1. 如果 state 为 none 或 未知，可不渲染，或显示“证据不足”。
2. evidence 最多展示 3 条。
3. missing 最多展示 2 条。
4. action_hint 必须展示。
5. renderer 不得自行生成策略判断。

### 9.4 示例

```markdown
**趋势结构**：低点抬升（置信度：中）
- 证据：最近两个回调低点依次抬高
- 提示：结构健康，回调低点抬升

**通道/箱体**：水平箱体（置信度：中）
- 位置：接近下轨
- 提示：区间内观望，等待方向确认

**市场共振**：弱于板块（置信度：中）
- 证据：行业指数处于上升趋势，个股仍为震荡
- 提示：个股弱于行业，技术优先级下降
```

---

## 10. Task 7：主入口集成

### 10.1 文件

- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Test: `tests/reporter/test_phase3_integration.py`

### 10.2 集成顺序

在 `advanced_medium_term_resonance()` 中：

1. 计算 Phase 2 指标与状态
2. `detect_trend_structure_health()`
3. `detect_channel_or_box_structure()`
4. `evaluate_bottoming_region()`
5. `evaluate_dart_strategy()`
6. `evaluate_market_resonance()`
7. 写入 `_resonance`：
   - `structure_health`
   - `channel_status`
   - `bottom_signal`
   - `dart_strategy`
   - `market_resonance`

---

## 11. 测试策略

### 11.1 新增测试文件

```text
tests/reporter/test_phase3_structure.py       (结构健康度 + 通道箱体)
tests/reporter/test_phase3_bottom_strategy.py  (底部观察 + 飞镖策略)
tests/reporter/test_market_resonance.py       (市场共振 + 指数映射)
tests/reporter/test_phase3_integration.py     (Renderer + 主入口集成)
```

### 11.2 必测场景

1. 回调低点抬升 / 走平 / 下移 / 无法判断
2. 最近 K 线不能作为 confirmed swing low
3. 间隔 3 天的 swing low 降低置信度
4. 水平箱体 / 上升通道 / 下降通道
5. 突破 K 线不得参与通道拟合
6. 斜率差 >0.01 不识别为通道
7. 底部观察满足 2 条不得触发
8. 底部观察满足 3 条输出 bottom_watch
9. 周线单边下跌不得升级为 bottom_candidate
10. 飞镖策略不得输出“买入/建仓/加仓/满仓”
11. 飞镖策略未满足 price >= MA5 不得触发
12. market_index_map 缺失时 fallback 不报错
13. 指数数据缺失时 market_resonance 输出未知
14. Renderer 只展示 signal，不做策略判断
15. Phase 3 新字段缺失时旧报告仍可渲染

---

## 12. 验收标准

1. Phase 1 / Phase 2 全量测试继续通过。
2. 新增模块全部遵守最小输出契约。
3. Renderer 不做策略判断，只渲染 signal。
4. 趋势结构低点识别必须有右侧确认。
5. 通道突破检测不得把突破 K 线纳入通道拟合。
6. 底部模块不得输出“底部确认”强措辞。
7. 飞镖策略不得出现“买入/建仓/加仓/满仓”等词。
8. 市场共振缺数据时必须降级，不得报错。
9. 报告生成时不得强依赖在线 akshare。
10. market_index_map 只维护关注池，其余走前缀 fallback。
11. Phase 3 不实现三重背离完整版。
12. 新增字段必须写入 `_resonance`，并能被 renderer 安全忽略或渲染。

---

## 13. 推荐提交顺序

```text
Commit 1:
feat(technical): add trend structure health detection

Commit 2:
feat(technical): add channel and box structure detection

Commit 3:
feat(technical): add bottoming region observation

Commit 4:
feat(technical): add dart observation strategy signal

Commit 5:
feat(technical): add market index mapping and resonance framework

Commit 6:
feat(technical): render phase3 structure signals via output contract

Commit 7:
test(technical): add phase3 integration and regression coverage
```

---

## 14. Agent 执行摘要

请严格按以下顺序执行：

```text
第一步：
实现 detect_trend_structure_health()，识别回调低点抬升/走平/下移。

第二步：
实现 detect_channel_or_box_structure()，使用通道基准区间，避免突破K线污染。

第三步：
实现 evaluate_bottoming_region()，只输出“底部区域观察”，不得输出“底部确认”。

第四步：
实现 evaluate_dart_strategy()，输出分批观察框架，禁止“买入/建仓/加仓/满仓”等词。

第五步：
实现 market_index_map 本地映射与 evaluate_market_resonance()，缺数据时降级。

第六步：
Renderer 接入最小输出契约，展示 structure/channel/bottom/dart/resonance。

第七步：
主入口集成新增模块，写入 _resonance。

第八步：
跑 Phase 1 / Phase 2 / Phase 3 全量测试。

第九步：
不要实现三重背离完整版、头肩顶复杂形态或完整输出格式大改版。
```

---

*设计版本：technical.phase3.structure_bottom_resonance.v2*
*适用范围：Phase 3A / Phase 3B*
*不包含：三重背离完整版、复杂头肩形态、完整输出格式大改版*
