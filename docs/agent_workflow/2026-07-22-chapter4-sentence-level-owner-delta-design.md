# Chapter 4 Sentence-Level Owner Delta Projection

日期：2026-07-22  
状态：proposed

## 1. Goal

改善 Chapter 4.3 与 4.1/4.2 的事实级重复，同时保留外部材料提供的更新期间、新数值、新事件、因果解释和反方约束。

本批只改变 Chapter 4 显示 read-model。External Producer v4、canonical pack、完整 MaterialSnapshot、评分、目标价、风险、推荐和 LLM 边界均不变。

## 2. Current Failure

当前 `select_incremental_external_display_rows()` 以整张 `MaterialRow` 判断是否有增量。一张 card 只要包含一个新锚点，整张 card 就会进入 4.3；随后 `select_external_topic_narratives()` 恢复该 card 的全部 narrative parts。因此同一 card 中已经在 4.1/4.2 出现的背景事实，也会与真正新增事实一起重新展开。

不能用主题词去重。`800G`、`利润`、`车规` 同时出现于多个章节，可能分别代表正式基座、机构假设和较新的外部更新。仅凭主题词删除会丢失合法增量。

## 3. Locked Policy

1. 只隐藏与当前报告中**实际可见 owner rows** 等价的 external narrative part。
2. owner rows 复用当前 profile 已传给 row-level incremental selector 的 annual/broker 集合；不得另读完整 memo 或 canonical material 压掉 4.3 内容。formal-medium 使用已选 display rows，formal-thin 保持其现有 owner 集合不变。
3. 外部 part 含新期间、新数值、新产品阶段、新事件、否定/约束或更丰富事实时必须保留。
4. 外部 part 被隐藏时，其低信用引用不得迁移到 4.1/4.2。
5. canonical cards、narrative plan、MaterialSnapshot rows 和 source units 全部保留；过滤仅影响最终 4.3 消费的 narrative projection。
6. 不以消除 prose warning 为目标。合法的近期更新即使继续触发主题重叠 warning，也不得删除。

## 4. Architecture

### 4.1 Single Projection Owner

扩展 `select_external_topic_narratives()`：

```python
select_external_topic_narratives(narratives, external_rows, owner_rows=())
```

该函数仍是 narrative 显示投影的唯一 owner，顺序如下：

1. 按 `scope_bucket + primary_family` 找到已准入 external rows。
2. 在过滤前验证 narrative plan 与 external rows 的 `(argument_key, unit_id)` 完整覆盖。
3. 按 narrative plan 保持原始顺序。
4. 执行现有 external-to-external 跨来源事实去重并合并引用。
5. 将每个保留 part 与可见 owner fact units 比较，只删除 owner-equivalent part。
6. 重新把首个 part 的 `relation` 设为 `first`；若为空则省略整个 topic narrative。

不得新增第二个 selector，也不得在 renderer 中复制等价判断。

### 4.2 Owner Fact Units

owner row 按句号、问号、感叹号和分号边界拆成只读比较单元；external narrative part 已经是 canonical SourceUnit，继续作为不可拆分的比较与显示单元。拆分只用于 owner 比较，不产生新引用、不修改 owner row，也不改变 4.1/4.2 渲染。

比较前只做以下规范化：

- 移除 Markdown citation；
- 移除通用来源引导词；
- 合并空白与全半角标点差异；
- 保留数字、期间、产品型号和事件谓词。

### 4.3 Conservative Equivalence

`_same_owner_fact(external_quote, owner_unit)` 必须比 external-to-external 去重更保守。

满足以下任一路径才可判定等价：

1. 规范化文本完全相同；
2. 长度不少于 24 字的一方完整包含另一方，并且 external quote 没有新增 concrete anchor；
3. 文本高度相似、财务指标身份一致、期间一致、数值兼容，且 external quote 没有新增 concrete anchor 或事件谓词。

硬性保护：

- 同数字但不同指标不得合并，例如营收与归母净利润；
- 年份、季度、半年度和具体日期分别提取为 time anchors；2025 与 2026、Q1 与 H1 等期间不同必须保留；
- `样品/验证/认证/量产/交付/订单/下调/短缺/否认` 等阶段或事件新增必须保留；
- external quote 比 owner 更丰富时必须保留整句，不做非原文改写；
- 无数字的句子只允许 exact、containment 或极高相似度等价，不使用主题 token overlap。

### 4.4 Profiles and Citations

- `formal_medium` 在 `build_chapter4_view_model()` 中传入已选 annual/broker owner rows。
- `formal_thin_external_rich` 在 renderer 的既有适配路径传入其已选 annual/broker owner rows。
- formal-thin 的完整 MaterialSnapshot、broker/external renderer 和 citation offset 公式保持原样。
- citation 编号仍按 full snapshot 的既有公式计算，不因隐藏 part 重新编号。
- 全局来源表继续由现有 `_visible_citations_only()` 根据最终正文过滤；被隐藏 part 的引用不会成为 unused definition，但仍留在 canonical pack 和 snapshot。
- 本批不改变 selector 返回类型，也不新增第二条 diagnostics 数据流；过滤行为由投影测试和正式报告引用门证明。

## 5. Expected Report Behavior

### Fudan

- 4.1 已展示的 FPAI 处理单元/算力范围若与外部单元实质等价，重复单元隐藏；若外部单元同时增加处理架构、产品阶段或其他 concrete anchor，则整段原文保留。
- 2026H1 营收、归母净利润、扣非净利润、战略配售收益和 Q2 推算继续保留，因为它们是较新期间或新增事实。
- 车规 MCU 若只是产品目录背景则隐藏；若包含“已形成收入贡献”等新经营阶段则保留。

### Zhongji

- 年报已有的产品范围不应导致所有包含 `800G/1.6T/硅光` 的外部句被删除。
- 订单覆盖 2026/2027、需求上调/下调、认证、量产、交付、产能、良率和供应紧张均属于增量，继续保留。
- target 与 peer/industry 分区保持不变。

## 6. Failure Modes and Tests

| Failure mode | Observable failure | Required test |
|---|---|---|
| 主题词误删 | 含 `800G` 的新订单事实消失 | same theme + new period/event remains |
| 新期间被压掉 | 2026H1 被 2025 年报替代 | same metric, different period remains |
| 指标错配 | 相同数字的营收与利润被当作同一事实 | same number, different metric remains |
| 产品阶段误合并 | 样品、认证、量产被视为同一事实 | same product, new stage remains |
| 更丰富外部句被压掉 | owner 只有型号，external 还有客户/阶段 | richer external quote remains verbatim |
| 真重复未清理 | FPAI 同规格在 4.1 和 4.3 各展开一次 | equivalent owner part omitted |
| 引用越层 | external ref 被追加到 4.1/4.2 | owner citation refs unchanged |
| 全部 part 被删后空标题 | 4.3 出现空主题 | empty narrative omitted |
| plan coverage 被过滤掩盖 | 缺 unit 的 narrative 被误接受 | coverage validation runs before filtering |
| formal-thin offset 回归 | external footnote 编号错位 | full-snapshot offset regression test |
| scope 串区 | peer part 进入 target topic | target/peer partition regression test |
| 原文被改写 | 投影生成不存在于 source 的事实句 | retained quote remains exactly equal to input part quote |

## 7. Allowed Scope

Runtime：

- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`

Tests：

- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`

Workflow notes/task files可新增。

禁止修改：External Producer v4、canonical packs、`report_quality.py`、`report_prose_quality.py`、topic taxonomy、评分、技术分析、风险、目标价、推荐、LLM prompt、data/knowledge/reports。

## 8. Verification

1. 新测试先 RED 后 GREEN。
2. 两个 focused test files 全绿。
3. snapshot/source-boundary/report-quality/prose-quality downstream tests 全绿。
4. 默认离线 full suite 全绿。
5. `bash tools/ci_grep_gates.sh` 与 `git diff --check` 通过。
6. 代码完成后再正式复跑复旦微电与中际旭创；验收不使用 stale 报告。

## 9. Stop Conditions

- 需要修改 canonical pack、producer 或 LLM selector；
- 需要按股票名、股票代码或行业写 hardcode；
- 无法在不改写原文的情况下保留新增事实；
- formal-thin citation offset 或 target/peer 分区发生变化；
- focused/downstream 测试出现无法解释的跨模块回归。

## 10. Runtime Budget

优先复用 `_normalized_claim_body()`、`_concrete_anchors()`、`_EXTERNAL_EVENT_TERMS` 和财务指标身份规则。通过抽取共享比较 helper 替换重复逻辑，而非叠加第二套 classifier。

目标 runtime 净增不超过 70 行；超过 100 行停止并返回设计。
