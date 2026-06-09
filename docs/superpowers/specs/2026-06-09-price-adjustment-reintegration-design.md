# 复权检测与本地前复权修复设计

**Goal:** 恢复 Phase 2 的 `price_adjustment_validator` 集成，确保 analyzer 在 raw 数据上自动检测除权缺口并应用本地前复权，使支撑/阻力/结构健康度等结论基于正确的价格序列。

**Architecture:** Analyzer 入口增加数据质量校验层：先检测价格缺口，若 raw 数据存在除权则本地复权后再进入指标计算。数据采集侧优先 akshare qfq，降级 mootdx raw + 本地复权。

**Tech Stack:** pandas, akshare, mootdx, price_adjustment_validator (已有模块)

---

## 背景

Phase 2 中 `price_adjustment_validator` 已集成到 `technical_analyzer.py`，可在 raw 数据上检测除权缺口、限制 confidence、输出警告。Phase 3 重构 `advanced_medium_term_resonance` 时，该集成被完全遗漏。乐鑫科技 (688018) 数据中 6月5日存在 28.7% 的除权跳空，当前报告的支撑区、趋势结构等全部基于未复权数据，结论失真。

## 数据采集策略

| 优先级 | 来源 | 复权状态 | 接口 |
|--------|------|---------|------|
| 1 | akshare `stock_zh_a_hist` | `adjust="qfq"` 直接返回前复权 | `ak.stock_zh_a_hist(symbol=..., adjust="qfq")` |
| 2 | mootdx `bars` | raw（未复权） | `client.bars(...)` + 本地 `apply_qfq_adjustment` |

akshare 返回列名为中文（日期、开盘、收盘...），需映射为英文（date/open/close/...）。

## Analyzer 集成设计

### 入口层：`advanced_medium_term_resonance`

在计算指标之前插入以下步骤：

1. 从 `quote` 读取 `adjustment` 字段（默认 `"raw"`）
2. 调用 `validate_adjustment(df_daily, adjustment=adjustment)` 检测缺口
3. 若 `requires_qfq=True`（raw 且存在疑似除权缺口）：
   - 调用 `apply_qfq_adjustment(df_daily)` 生成复权后 DataFrame
   - 用复权后的 df 替换 `df_daily` 进入后续全部计算
   - 记录 `corporate_action_warning` 到 `_resonance`
4. 若 `adjustment="qfq"` 但数据仍检测到缺口（复权不完整）：
   - 仅输出警告，不降级 confidence
5. 若 `adjustment="raw"` 且无缺口：
   - confidence 不受影响

### confidence 规则恢复

```
if adjustment != "qfq" and possible_exrights_gap:
    confidence_level = "低"
elif adjustment == "qfq" and daily >= 250 and weekly >= 60:
    confidence_level = "高"
elif adjustment == "qfq" and daily >= 120 and weekly >= 20:
    confidence_level = "中"
else:
    confidence_level = "低"
```

### resonance 输出字段恢复

- `_resonance["corporate_action_warning"]` — 除权警告对象
- `_resonance["price_adjustment_validation"]` — 完整验证结果
- `limitation` 中追加 `"未使用前复权数据，技术指标可能失真"`

### divergence 限制恢复

若 `adjustment != "qfq"` 且存在 `divergence`：
- `divergence["confidence"] = "低可信度"`
- `divergence["action"] = "未使用前复权数据，此预警仅供参考"`

## Renderer 渲染

`TechnicalRenderer` 已有 `_render_compact` 逻辑需检查：
- 若 `corporate_action_warning` 存在，在报告头部输出数据口径提醒
- Phase 2 报告中的 `"**数据提醒**：当前价格序列疑似存在除权断点..."` 格式恢复

## 文件改动

| 文件 | 修改内容 |
|------|---------|
| `scripts/utils/reporter/technical_analyzer.py` | 恢复 adjustment 检测、本地复权、confidence 降级、警告输出 |
| `scripts/utils/reporter/sections/technical_renderer.py` | 恢复 corporate_action_warning 渲染 |
| `scripts/utils/data_collector.py`（可选） | `TechnicalCollector.collect` 增加 akshare qfq 优先分支 |
| `tests/reporter/test_price_adjustment_validator.py` | 已有，无需改动 |
| `tests/reporter/test_corporate_action_adjustment.py` | 解除 skip，验证 analyzer 集成 |

## 测试策略

1. 用乐鑫 raw 数据调用 `advanced_medium_term_resonance(quote={"adjustment":"raw"})`：
   - 验证 `analysis_confidence.level == "低"`
   - 验证 `corporate_action_warning` 不为 None
   - 验证支撑区/低点等数值与复权后一致
2. 用乐鑫 raw 数据调用 `advanced_medium_term_resonance(quote={"adjustment":"qfq"})`：
   - 验证 confidence 不低于"中"
   - 验证警告仅提示"已复权但存在断点"而非"未复权"
3. 用无除权股票测试：不影响正常结论

## 兼容性

- 新增 `quote.adjustment` 字段为可选，默认 `"raw"`，保持向后兼容
- `price_adjustment_validator` 已存在，不引入新依赖
