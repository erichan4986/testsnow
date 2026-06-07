# 高级技术分析规则集成设计

> 目标：将用户提供的完整技术分析规则体系集成到现有 Skill Pipeline 中，增强报告技术面板块的信息密度和可操作性。

---

## 1. 数据流与接口

### 1.1 不变的部分

- Pipeline 执行顺序不变：`technical_fetching_skill` → `TechnicalAnalysisSkill` → `ReportAssemblySkill`
- `stock_raw["technical"]["indicators"]` 继续作为核心数据载体
- 现有 `_resonance` 中的 `trend`、`momentum`、`volume_price`、`composite_score`、`signals` 字段保留，确保 backward compatible（五维雷达图依赖 `composite_score`）

### 1.2 扩展的 indicators 字段

```python
indicators = {
    # --- 现有字段保留 ---
    "close", "volume", "macd", "macd_signal", "macd_hist",
    "rsi_14", "adx", "plus_di", "minus_di",
    "ma_5", "ma_10", "ma_20", "ma_60",
    "boll_upper", "boll_mid", "boll_lower",
    "williams_r", "stoch_rsi_k", "stoch_rsi_d",

    # --- 新增字段 ---
    "bias_5", "bias_10", "bias_20",           # BIAS偏离度
    "bias_5_extreme", "bias_10_extreme",      # 是否创120日极值
    "boll_width", "boll_width_ma5",           # 布林宽度 & 5日均宽
    "boll_state",                              # "开口"/"缩口"/"正常"
    "weekly_ma5", "weekly_ma10", "weekly_ma20", # 周线均线
    "weekly_close",                           # 最新周线收盘价
    "weekly_trend",                           # "单边上涨"/"单边下跌"/"震荡"
    "ma20_direction",                         # "向上"/"向下"/"走平"

    # --- 形态/结构字段 ---
    "_resonance": { ... },                    # 升级为高级结构（见1.3）
    "_patterns": [...],                        # 保留但内容更丰富
    "_levels": {
        "support": 45.2,
        "resistance": 52.8,
        "support_strength": "强",
        "resistance_strength": "中",
    },
}
```

### 1.3 升级后的 `_resonance` 结构

```python
_resonance = {
    # 保留（用于雷达图 backward compatibility）
    "trend": "多头",
    "momentum": "超买",
    "volume_price": "确认",
    "composite_score": 6.5,
    "signals": [...],

    # 新增（用于报告正文）
    "weekly_background": "单边上涨",
    "ma20_direction": "向上",
    "trend_stage": "中期",
    "boll_state": "开口",
    "price_position": "中轨与上轨之间",

    "signal_operation": {
        "core_signal": "买入信号",
        "confidence": "高",
        "position": "30%",
        "strategy": "初始仓位入场",
    },

    "key_levels": {
        "support": 45.2,
        "support_strength": "强",
        "resistance": 52.8,
        "resistance_strength": "中",
        "boll_upper": 51.0,
        "boll_lower": 46.0,
    },

    "advisors": {
        "macd": "金叉扩张 (仅参考)",
        "rsi": "72.3 超买区 (仅参考)",
        "bias": "BIAS(5)=3.2%, BIAS(10)=2.1%, BIAS(20)=1.5%, 未创极值 (仅参考)",
    },

    # 条件启用：只有当背离触发时才存在
    "divergence_scan": {
        "type": "三重顶背离",
        "confidence": "中度 (2/3)",
        "missing": ["RSI未背离"],
        "action": "均线为王，仅作预警",
    },

    # 条件启用：只有当用户问卖出或触发离场信号时才存在
    "sell_assessment": {
        "valuation": "N/A",
        "ma_signal": "未破位",
        "deviation": "BIAS(5)未创极值",
        "conclusion": "不满足卖出条件",
    },

    "basis_rules": ["3.1.1 突破定义", "3.2.1 周线单边上涨", "6.1.1 布林开口"],
    "risk_reminder": "着眼大趋势，忽略小波动。均线为王，谋士辅助。",
}
```

---

## 2. 计算模块（`technical_analyzer.py` 新增函数）

### 2.1 基础指标扩展

```python
def compute_bias(df: pd.DataFrame) -> Dict:
    """计算 BIAS(5/10/20)，并标记120日极值。
    返回: {"bias_5": 3.2, "bias_10": 2.1, "bias_20": 1.5,
           "bias_5_extreme": False, "bias_10_extreme": False}
    """


def compute_candle_features(df: pd.DataFrame) -> Dict:
    """计算K线实体、影线长度。
    返回: {"body_len": 1.5, "upper_shadow": 0.8, "lower_shadow": 0.3,
           "is_doji": False, "is_long_lower_shadow": False, "is_long_upper_shadow": False}
    """


def compute_boll_state(df: pd.DataFrame) -> Dict:
    """计算布林宽度、开口/缩口/正常状态。
    开口: 当日宽度 > 前5日均宽 × 1.2
    缩口: 当日宽度 < 前5日均宽 × 0.8
    返回: {"boll_width": 0.12, "boll_width_ma5": 0.10, "boll_state": "开口"}
    """
```

### 2.2 周线与趋势判定

```python
def compute_weekly_trend(df_weekly: pd.DataFrame) -> Dict:
    """基于周线判定大背景。
    单边上涨: 周K线收盘价持续在MA5和MA10之上，均线流畅发散
    单边下跌: 周K线收盘价持续在MA5和MA10之下，均线流畅发散
    震荡市: 周收盘价20日内穿越MA5/MA10 ≥3次，且MA5与MA10差值 < 2%
    返回: {"weekly_trend": "单边上涨", "weekly_ma5": 48.2, "weekly_ma10": 46.5,
           "weekly_ma20": 44.0, "weekly_close": 50.1, "ma20_direction": "向上"}
    """
```

**关键参数：**
- 均线走平判定：MA20 近5日方向变化 < 0.5%
- 周线震荡判定：20日内穿越 ≥3 次 + MA5/MA10 差值 < 2%

### 2.3 背离扫描

```python
def detect_triple_divergence(
    df: pd.DataFrame,
    indicators: Dict,
    weekly_trend: str,
) -> Optional[Dict]:
    """三重背离扫描。采用"2/3 触发"原则（而非必须3/3）。

    顶背离条件（需同时满足3项中的至少2项）：
    1. 布林背离: 股价创近20日新高，但布林上轨未创新高（差值 > 1%），或股价跑到上轨之外
    2. MACD顶背离: 股价创近20日新高，但DIF低于前一个高点的DIF值，且红柱缩短
    3. RSI顶背离: 股价创近20日新高，但RSI未创新高，反而拐头向下

    底背离条件同理。

    返回: {"type": "顶背离", "confidence": "中度", "matched": 2, "total": 3,
           "missing": ["RSI未背离"], "action": "均线为王，仅作预警"}
    若无背离则返回 None。
    """
```

### 2.4 支撑阻力识别

```python
def find_support_resistance(df: pd.DataFrame, use_scipy: bool = False) -> Dict:
    """基于120日数据找支撑/阻力位。

    识别方法:
    - 支撑位: 某个价格区间（均值±1%）至少有3次有效触及，
              触及后反向运行 ≥2% 或 ≥1个ATR 才计入有效
    - 阻力位: 同上

    强度分级:
    - 触及 ≥5次 或跨越时间超过半年 → "强"
    - 否则 → "中"/"弱"

    返回: {"support": 45.2, "support_strength": "强",
           "resistance": 52.8, "resistance_strength": "中"}
    """
```

**编码决策：** 先以纯 pandas + numpy 实现聚类。`use_scipy=False` 作为默认开关，若后续噪声过滤不够，可切换为 `scipy.signal.find_peaks`。

### 2.5 形态识别

```python
def detect_channel(df: pd.DataFrame) -> Optional[Dict]:
    """通道盘整识别。采用线性回归+R²判定平行度。
    若识别到返回: {"upper_slope": 0.1, "lower_slope": 0.08, "r2": 0.85,
                   "upper_intercept": 50, "lower_intercept": 45}
    否则返回 None
    """


def detect_head_shoulders(df: pd.DataFrame) -> Optional[Dict]:
    """头肩顶/双底候选检测。返回候选信息+置信度，等待颈线突破确认。

    采用"模糊检测 + 置信度"模式:
    - 检测到候选形态 → 输出"疑似头肩顶（置信度65%）"
    - 等待颈线突破 → 升级为"头肩顶确认"

    返回: {"pattern": "头肩顶候选", "confidence": 0.65, "neckline": 45.0,
           "head": 52.0, "left_shoulder": 48.0, "right_shoulder": 47.5}
    """
```

### 2.6 信号生成

```python
def generate_trading_signals(
    df: pd.DataFrame,
    indicators: Dict,
    weekly_trend: str,
    divergence: Optional[Dict],
    levels: Dict,
) -> Dict:
    """核心信号生成器。整合趋势、背离、支撑阻力，输出操作信号。

    信号定义（日线）:
    - 突破: 收盘价 > MA5 且 > MA10（同时 > MA20 为"强突破"）
    - 跟随: 连续2个交易日均满足"突破"
    - 警惕: 收盘价跌破 MA5，但仍 > MA10
    - 破位: 收盘价 < MA5 且 < MA10

    操作规则（仅适用于单边市背景）:
    - 首次入场 → "买入信号" 初始仓位30%
    - 加仓至满仓 → "加仓信号" 加仓至70%
    - 持仓不动 → "假摔确认"
    - 清仓离场 → "破位信号" 果断清仓

    震荡市特殊规则:
    - 日线突破但周线震荡 → 置信度"低"，只进行极小仓位（<10%）试探
    - 日线破位但周线震荡+底部 → 不执行清仓

    假突破风险控制:
    - 突破次日即回落跌破MA5 → 停止加仓
    - 第三日继续下跌 → 减仓
    - 第四日触发破位 → 直接清仓

    返回: {"core_signal": "买入信号", "confidence": "高",
           "position": "30%", "strategy": "初始仓位入场"}
    """
```

### 2.7 主入口

```python
def advanced_resonance(
    df: pd.DataFrame,
    df_weekly: pd.DataFrame,
) -> Dict:
    """主入口：调用以上所有函数，组装完整 _resonance 结构。
    被 data_collector 的 compute_indicators 调用，替换现有的 multi_indicator_resonance。
    """
```

---

## 3. 渲染逻辑（`TechnicalRenderer` 重写）

### 3.1 降级策略

- 若 `_resonance` 包含新字段 → 按高级模板渲染
- 若 `_resonance` 仅有旧字段（backward compatible）→ 回退到旧"指标快照"表格渲染

### 3.2 输出模板

```markdown
## 技术面分析

**标的类型**：【指数/个股】
**周线大背景**：【单边上涨/单边下跌/震荡市】
**均线方向(MA20)**：【向上/向下/走平】
**当前趋势阶段**：【早期/中期/末期/盘整】
**布林带状态**：【开口/缩口/正常】，价格位于【上轨之上/上轨附近/中轨与上轨之间/中轨附近/中轨与下轨之间/下轨附近/下轨之下】

**信号与操作**：
- 核心信号：【买入信号】（置信度：高）
- 建议仓位与策略：30%，初始仓位入场
- 关键价位：
  - 支撑位：45.2（强）
  - 阻力位：52.8（中）
  - 布林上轨：51.0 / 下轨：46.0

**谋士团扫描**：
- MACD：金叉扩张 (仅参考)
- RSI：72.3 超买区 (仅参考)
- BIAS：BIAS(5)=3.2%, BIAS(10)=2.1%, BIAS(20)=1.5%, 未创极值 (仅参考)

**卖出三要素评估**：（条件启用）
- 估值定价状态：N/A
- 均线信号状态：未破位
- 强弱偏离度状态：BIAS(5)未创极值
- 结论：不满足卖出条件

**背离扫描**：（条件启用）
三重顶背离（置信度：中度 (2/3)）
- 处置方式：均线为王，仅作预警

**依据**：
- 3.1.1 突破定义
- 3.2.1 周线单边上涨
- 6.1.1 布林开口

**风险提示与哲学提醒**：着眼大趋势，忽略小波动。均线为王，谋士辅助。

### 技术面综合图
![{stock_name} 技术面分析]({tech_chart_path})
```

### 3.3 标的类型判断

- `stock_name` 对应 `stock_codes`：code 以 `sh`, `sz` 开头 → "个股"
- `stock_name` 为 `上证指数`, `沪深300`, `创业板指` 等 → "指数"
- 其余未知 → "个股"

### 3.4 条件渲染规则

| 模块 | 触发条件 |
|---|---|
| 卖出三要素 | `resonance` 包含 `"sell_assessment"`，或检测到离场信号 |
| 背离扫描 | `divergence_scan` 不为 None |
| 关键价位 | `key_levels` 中 support/resistance 任一存在 |

---

## 4. 测试策略

| 测试文件 | 覆盖内容 |
|---|---|
| `tests/reporter/test_bias_computation.py` | BIAS(5/10/20) 计算、120日极值判定 |
| `tests/reporter/test_weekly_trend.py` | 周线单边/震荡判定边界条件 |
| `tests/reporter/test_triple_divergence.py` | 2/3、3/3、0/3 三种背离场景 |
| `tests/reporter/test_support_resistance.py` | 支撑阻力聚类、强/弱分级、转化规则 |
| `tests/reporter/test_trading_signals.py` | 突破→跟随→警惕→破位 全链路信号 |
| `tests/reporter/test_channel_pattern.py` | 通道识别（平行线、斜率判定） |
| `tests/reporter/test_technical_renderer.py` | 新模板渲染输出验证（含降级逻辑） |

**测试数据**：使用 pytest fixture 加载一个 120 日的 mock K线 DataFrame（随机游走或真实某股票截取数据），确保指标计算可复现。

---

## 5. 实施顺序

| Phase | 内容 | 预计耗时 |
|---|---|---|
| P1 | 扩展 `compute_indicators()`：新增 BIAS、BOLL width、K线实体、周线均线 | 20min |
| P2 | 新增 `advanced_resonance()` + 所有辅助函数（支撑阻力、背离、信号生成） | 40min |
| P3 | 重写 `TechnicalRenderer` | 15min |
| P4 | 编写测试（P1-P3 覆盖） | 30min |
| P5 | 运行端到端测试（选一只股票生成报告，验证输出格式） | 10min |

**总工作量约 2 小时。**

---

## 6. 关键编码决策汇总

| 决策 | 选择 | 理由 |
|---|---|---|
| 三重背离触发条件 | **2/3**（而非必须 3/3） | 提高实用性，避免长期不触发 |
| 形态识别模式 | **纯 pandas + 置信度** | 可预测、无依赖，符合"候选+确认"哲学 |
| scipy 引入 | **默认不引入，预留开关** | `use_scipy=False`，后续可切换 `find_peaks` |
| sklearn 引入 | **不引入** | 支撑阻力手写聚类已足够，避免黑盒 |
| 支撑阻力有效触及 | 反向运行 ≥2% 或 ≥1 ATR | 过滤噪声，提升质量 |
| 旧渲染 | **降级保留** | 确保 backward compatible |
| 卖出三要素 | **条件启用** | 平时隐藏，仅在触发时显示 |

---

*设计日期：2026-06-07*
*关联文件：`scripts/utils/reporter/technical_analyzer.py`, `scripts/utils/reporter/sections/technical_renderer.py`*
