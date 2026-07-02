# Batch 2b 行业新闻相关性分类设计 — Claude 只读审查报告 Round 1

**审查日期**: 2026-07-02
**审查类型**: 只读设计审查（未修改任何文件）
**设计文档**: `docs/agent_workflow/2026-07-02-industry-news-relevance-classification-design.md`
**Branch**: `codex-report-quality-upgrade`（clean）

---

## Verdict

**needs_revision** — 三层防御（deterministic helper + synthesis guardrail + post-render gate）的整体架构方向正确，但第 2 层和第 3 层存在若干薄弱环节，可能在 LLM 编造产业链链条的场景下失效。需要在进入实现前补齐。

---

## Blocker

**无。** 所有问题都可以在当前框架内修复，不需要回退到完全不同的方案。

---

## Must Fix

### MF1. 第 2 层（synthesis guardrail）对 LLM 的 filter/skip 依赖 prompt 指令，而非硬过滤

**当前设计**: 第 139-146 行说 KnowledgeSynthesizer 的 4.3 prompt 看到"新闻条目和 relevance metadata"后，"4.3 输出必须遵守"几项规则，包括 `sector_background` 不得输出为催化剂。

**问题**: 这是一个**软约束**——LLM 在生成时可能忽略或遗忘指令，尤其当多条新闻中混入了一条 `sector_background` 条目而 LLM 判断它"看起来很重要"时。复旦微电上一轮显式 prompt 和 rule 未能阻止泛行业新闻进入 4.3，说明当前 synthesis prompt 不够健壮，不应重复依赖同一个薄弱环节。

**要求修复**: 4.3 的 LLM prompt 输入应该**在构建 prompt 时就按 `allowed_sections` 过滤**，而不是把过滤决策委托给 LLM：

```
# 当前（弱）:
prompt_input = all_news  # LLM 看到 sector_background，prompt 说不要用
# 应改为（强）:
prompt_input = [n for n in all_news if "4.3" in n.extra.allowed_sections]
```

设计文档第 186-194 行的数据流应该在第 3-4 步之间增加一个显式 filter 步骤：**"第 3a 步: synthesis input builder 根据 relevance metadata 过滤 4.3 输入，只保留 allowed_sections 含 '4.3' 的条目"**。这是阻止 sector_background 误入 4.3 最有效的防线。

---

### MF2. 渲染链追踪缺失 — LLM 可以编造不同于 deterministic chain 的链条

**当前设计**: deterministic helper 产出一个 `relevance_chain`（有序 node + evidence），但 post-render gate 只检查：
- 是否有链条词（"传导/对应/暴露/待验证/需跟踪"）
- 是否有强确认词
- 是否有 sector background 标题

**问题**: LLM 可以在 4.3 中写出一条**完全不同于** helper 产出链的链条，只要使用了审慎语言，gate 就检测不出。例如：

- Deterministic chain: `存储涨价 → 晶圆厂产能紧张`
- LLM 渲染: `存储涨价 → 晶圆厂产能紧张 → 华为手机出货量回升 → CIS 需求增长 → 公司受益`

前三跳 helper 没有输出，但使用了"需验证/可能"等审慎表达，gate 误判为通过。

**要求修复**: post-render gate 增加**链一致性验证（chain match validation）**。实现方向：

1. 定义 `relevance_chain` 中的每一跳为一个 `chain_link`，每个 link 包含 `canonical_statement`（规范表述）；
2. post-render gate 解析 4.3 正文中的"事件 A → 事件 B → 事件 C"结构（可以用正则或简单 NLP）；
3. 对每个解析出的因果链，与 deterministic helper 产出的 canonical chain 做匹配 —— 如果 4.3 正文中有 helper 定义的 chain 之外的 hops，发出 warning；
4. 如果正文出现的 hop 没有任何对应的 news/config 支持，发出 error。

设计文档第 150-154 行的 post-render gate 需要增加：
```python
# 新增 gate:
# - 4.3 出现 deterministic chain 之外的因果跳转时 warning
# - 4.3 出现无任何 news/config 支持的 hop 时 error
```

---

### MF3. 强确认词列表和链条词列表未定义

**当前设计**: 第 152-153 行提到"强确认词"和"链条词"，但只在括号中列举了示例（"传导/对应/暴露/待验证/需跟踪"）。

**问题**: post-render gate 的可靠性完全依赖这两个列表的完整定义。如果进入实现后再逐次补充，可能出现：
- 漏检：LLM 用了列表之外的强确认词（如"将推动/确定传导/必然传导/毫无疑问"）
- 误报：2-3 个字的容错不足，多字变体漏掉

**要求修复**: 在设计文档中明确定义两个列表，至少各 15-20 个变体：

**强确认词**（出现任一 + industry_chain_relevant → error）：
```
将受益, 将推动, 将提升, 必然, 必定, 确定, 确定催化, 锁定, 
已确认, 无疑, 毫无疑问, 必然传导, 将导致, 将实现, 将带来,
确定性的, 已落地, 必然涨价, 将增长, 将成为
```

**链条词**（industry_chain_relevant 在 4.3 中必须出现至少一个）：
```
传导, 对应, 暴露, 待验证, 需跟踪, 可能, 若, 预期, 可望,
需关注, 有待, 能否, 是否, 若...则, 假设, 情景, 取决于,
需观察, 待确认, 有不确定性, 需进一步验证
```

（以上是建议，团队可调整，但必须写出正式列表。）

---

### MF4. deterministic helper 置信度无阈值，低置信链可放行至 4.3

**当前设计**: deterministic helper 输出 `confidence: 0.72`（第 124 行），但 KnowledgeSynthesizer 不做阈值决策。

**问题**: 如果一条新闻的 `confidence` 是 0.25（链接薄弱），但仍被标注为 `industry_chain_relevant`，LLM 获得这条新闻后可能"确认地"写出链条，而使用者不知道这只是一个低置信猜测。

**要求修复**: 增加置信度阈值策略：

```
confidence >= 0.7: industry_chain_relevant 正常进入 4.3
0.4 <= confidence < 0.7: 可进入 4.3，但 synthesis output 必须使用审慎表达
confidence < 0.4: 降级为 sector_background，不进入 4.3
```

这个阈值应在 helper 中直接实现（不是事后 gate），写入 helper 的决策逻辑。同时阈值应可配置，不同股票可以有不同的链置信要求。

---

## Nice To Have

### N1. `relevance_chain` 需增加 `chain_id` 和 hop `id` 以支持 post-render 链追踪

当前 `relevance_chain` 格式（第 60-66 行）只有 node + evidence 对。为支持 MF2 的链匹配验证，chain 数据需要增加可寻址标识：

```json
{
  "chain_id": "news-uuid-chain-01",
  "hops": [
    {"id": 1, "node": "存储产品涨价", "evidence": "新闻标题/正文命中存储涨价", "evidence_type": "news_keyword"},
    {"id": 2, "node": "晶圆厂产能紧张", "evidence": "新闻提到上游产能/晶圆厂/代工产能", "evidence_type": "news_keyword"},
    {"id": 3, "node": "CIS 排产被挤占", "evidence": "公司产品属于 CIS，且 config 暴露上游为晶圆代工", "evidence_type": "config_chain_rule"},
    {"id": 4, "node": "公司 CIS 价格/交付变量", "evidence": "公司产品关键词命中 CIS", "evidence_type": "product_keyword"}
  ]
}
```

`evidence_type` 支持后端 gate 区分"这条 hop 有 config 或 news 支撑" vs "只有关键词匹配"。

---

### N2. `chain_rules` 的格式应支持 3+ hops

当前 `chain_rules`（第 166-173 行）固定为 `from → through → to` 三段式。但用户背景示例提到 5 跳链（存储涨价 → 晶圆厂产能紧张 → 产能被存储挤占 → CIS 排产变少 → CIS 涨价）。如果 chain_rules 只能表示 3 跳，部分多跳链可能被压缩或丢失中间环节。

建议改为无限制的节点序列：

```json
"chain_rules": [
  {
    "hops": [
      {"keyword_group": ["存储涨价", "存储扩产", "HBM扩产"]},
      {"keyword_group": ["晶圆厂产能", "代工产能"]},
      {"keyword_group": ["CIS排产", "CIS供给"]},
      {"keyword_group": ["CIS价格", "CIS交付", "CIS涨价"]}
    ],
    "target_product": "CIS"
  }
]
```

这样 chain_rules 本身就可以支撑 N 跳链的检测，无需强行压缩到 3 段。

---

### N3. `sector_background` 进入 4.1 需要长度约束

第 91 行说 `sector_background` 允许进入 4.1，"只能短句提及"。但"短句"没有量化标准，LLM 可能在 4.1 中用整段展开行业背景，压榨正式内容的篇幅。

建议给 4.1 的 `sector_background` 加长度约束：
- 不超过 2 句
- 不作为单独段落，仅在产业逻辑描述中嵌入一句
- post-render gate 可以检测 4.1 中过长的 `sector_background` 引用

---

### N4. 测试覆盖率中缺少"LLM 编造链"的反向测试

第 224-237 行的 focused tests 覆盖了 helper 的分类正确性，但缺少对"LLM 在 synthesis 中编造链"的对抗性测试。

建议增加：
- `test_4.3_synthesis_guardrail_rejects_fabricated_chain`：输入为 `sector_background` 但 LLM 试图写成催化剂的 edge case
- `test_post_render_gate_catches_new_hop`：post-render gate 检测到 deterministic chain 之外的新 hop 时产生 warning

---

## 最大的 LLM 编造风险在哪里

**风险 1（高）: synthesis 层接收到所有新闻后，LLM 忽视 `sector_background` 标签自行使用。**
这是当前设计中最紧迫的编造风险。LLM 收到全量新闻列表，即使每条都带了 `relevance_class=sector_background`，LLM 在"生成更好的催化剂时间线"的倾向下仍可能挑选其中看似相关的写入 4.3。**解决方案: MF1 的硬过滤。**

**风险 2（高）: LLM 在 deterministic chain 之外自由添加中间 hop。**
即使 deterministic chain 是 `存储涨价 → 晶圆厂产能紧张 → CIS 排产`,
LLM 可以自然地插入 `→ 8英寸晶圆厂产能利用率提升 → 代工价格上调 →` 这样的中间跳，这些跳不在任何 news/config 中，但听起来合理。
**解决方案: MF2 的链一致性验证。**

**风险 3（中）: LLM 将 `industry_chain_relevant` 的"待验证变量"写成"已发生事实"。**
即使使用审慎语言约束，LLM 仍可能在同一个段落中将两个事实并列，暗示因果关系。例如："存储涨价 → 晶圆厂产能紧张。公司 CIS 产品线将受益于 CIS 供给收缩提价。"第一句是行业事实，第二句是 LLM 推断，但阅读上没有明显的区分。
**解决方案: MF3 的强确认词检测 + MF4 的置信度阈值。**

**风险 4（低）: 确定性规则的 evidence 可能是关键词匹配，而非真实经济关系。**
这是 helper 级别的"表层编造"——关键词上了链但不代表逻辑成立。但这不是 LLM 的行为，而是 deterministic 规则的已知局限。**通过 fixture 测试和 config chain_rules 的手工审查来缓解，不依赖新机制。**

---

## 是否必须增加 Chain Evidence Validator

**是，但不需要作为独立的第 4 层。** 推荐将其整合到 post-render gate（第 3 层）中，形成增强后的第 3 层门禁：

### 当前三层防御
1. ✅ **Deterministic helper** — 分级 + 链生成（硬规则，可靠）
2. ⚠️ **Synthesis guardrail** — LLM 指令（需要 MF1 硬过滤增强）
3. ⚠️ **Post-render gate** — 表面关键词检查（需要 MF2 链匹配增强）

### 增强后的三层防御

1. ✅ **Deterministic helper** — 不变。增加置信度阈值（MF4）和 chain_id/hop_id（N1）。

2. **Synthesis input hard filter + guardrail**（MF1 修复后）:
   - 输入层硬过滤 `allowed_sections`；
   - 将 `relevance_chain` 以结构化方式注入 LLM prompt，描述为"唯一可用的产业链传导路径"；
   - prompt 中说"如果生成链未在此路径中，不能写入 4.3"。

3. **Post-render gate with chain match validation**（MF2 修复后）:
   - 原有：链条词 + 强确认词 + sector_background 标题检测；
   - 新增：解析 4.3 因果结构 → 匹配 deterministic chain hops → 发现新 hop 时 warning/error。

**这个验证器应该做**: 因果链提取 → canonical chain 匹配 → 未匹配 hop 标记，而不是从零判断链条的经济正确性。
**不应该做**: 验证链路的"经济合理性"——那是关于 LLM 幻觉的问题，超出本轮范围，且不可测试。

---

## 是否建议进入实现

**⚠️ 建议先修订设计，再进实现。**

| 项目 | 准备度 | 备注 |
|------|--------|------|
| Deterministic helper + classifier | ✅ 高 | 规则清晰，可测试，无歧义 |
| Config `industry_relevance`字段 | ✅ 高 | 格式已明确，只需增加 N2 的灵活 hops 支持 |
| 第 1 层 helper fixture tests | ✅ 高 | FM1-FM4 已覆盖反向场景 |
| 第 2 层 synthesis input hard filter | ⚠️ 需要 MF1 | 改 data flow，增加 explicit filter step |
| 第 3 层 sector_background 标题 gate | ✅ 高 | 规则已明确 |
| 第 3 层 chain match validation | ❌ 需要 MF2 | 需设计 canonical chain 格式和匹配算法 |
| 强确认词/链条词列表 | ❌ 需要 MF3 | 需明确定义 |
| 置信度阈值 | ❌ 需要 MF4 | 需写入 helper 逻辑 |
| 4.3 渲染的端到端 smoke test | ⚠️ 见下 | 需等 implementation 完成 |

**推进顺序**:
1. 先修设计文档：补齐 MF1（硬过滤）、MF2（链匹配）、MF3（词表）、MF4（阈值）
2. 再实现 helper 和 fixture tests（安全，与第 2/3 层改动独立）
3. 接入 synthesis input filter
4. 实现 chain match validation gate
5. 复旦微电 smoke 回归

### 主要风险汇总

| 风险 | 缓解 |
|------|------|
| LLM 编造并写入全链条 | MF1 硬过滤确保 LLM 只看到允许入 4.3 的条目 |
| LLM 在已知链上增加中间跳 | MF2 链匹配 gate 检测新增 hop |
| LLM 使用审慎语言掩盖编造 | MF2 + MF3 联检 — 词表 + 链结构双重门禁 |
| 确定性规则分类错误（误放行） | FM1/FM2 fixture tests + config chain_rules |
| 确定性规则分类错误（误过滤） | FM1 fixture tests — 可调阈值 |

---

## Git Status

**无变化。** 本审查为只读审查，未创建、修改或删除任何文件。

```
$ git status --short
   (clean)
```

---

## 汇总

| 类别 | 状态 |
|------|------|
| **Verdict** | needs_revision |
| **Blocker** | 0 |
| **Must fix** | 4（MF1~MF4） |
| **Nice to have** | 4（N1~N4） |
| **最大 LLM 编造风险** | synthesis 层未硬过滤 sector_background（MF1） |
| **必须增加 chain evidence validator?** | 是，整合到 post-render gate 作为链匹配检查（MF2） |
| **建议进入实现** | ⚠️ 先修订设计，再进实现 |
| **Git status** | clean（无改动） |
