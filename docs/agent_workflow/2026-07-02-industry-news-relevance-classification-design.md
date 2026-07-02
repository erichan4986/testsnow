# Batch 2b 设计：行业新闻相关性分类与 4.3 催化剂边界

## 背景

复旦微电 trial 的 4.3 催化剂时间线仍混入多条泛行业新闻。Batch 1 已修复硬一致性问题；本设计处理 Batch 2b：行业新闻如何进入 4.1/4.3，尤其是“行业事件与公司并非一跳直连，但存在多跳产业链传导”的场景。

核心原则：不一刀切删除行业新闻，但不允许泛行业新闻被包装成公司催化剂。行业新闻必须经过可解释链条，才能进入 4.3。

## 用户约束

行业相关性可能不止一层。例如一家专门做 CIS 的公司：

1. 存储产品涨价；
2. 上游晶圆厂产能紧张；
3. 晶圆厂产能被存储挤占；
4. CIS 排产变少；
5. CIS 供给收缩，价格上涨。

这类新闻虽然第一跳不是公司或 CIS，但多跳链条能解释到公司产品暴露，因此应可作为 `industry_chain_relevant`，而不是直接当 `sector_background/noise` 丢弃。

## 目标

- 为 `eastmoney_global_news` 等行业新闻增加 relevance metadata。
- 让 4.3 只渲染 `company_event` 和有明确链条的 `industry_chain_relevant`。
- 允许 1-hop 到 multi-hop 的产业链传导，但每一跳必须可解释。
- 保持 formal_first source boundary：新闻仍是正式/专业源；社媒仍不得进入 4.1-4.3。
- 避免频繁跑完整 LLM 报告，先用 deterministic helper + fixture tests 覆盖。

## 非目标

- 不在本轮引入新的 LLM 分类调用。
- 不做完整产业知识图谱。
- 不让行业新闻参与评分、EV、风险评分或最终建议。
- 不把行业新闻全部踢出报告；有业务链条的可保留。

## Relevance Class

### `company_event`

公司直接事件：

- 公司公告、财报、业绩预告；
- 公司订单/合同/中标；
- 公司调研、投资者关系、分红、股权变动；
- 公司明确被新闻标题或正文提及。

允许进入：

- 4.3 催化剂时间线；
- 4.2 业绩路径；
- 4.1 产业/竞争格局。

### `industry_chain_relevant`

行业事件通过产业链传导影响公司产品、产能、成本、价格或需求。

必须输出 `relevance_chain`，格式为有序节点：

```json
[
  {"node": "存储产品涨价", "evidence": "新闻标题/正文命中存储涨价"},
  {"node": "晶圆厂产能紧张", "evidence": "新闻提到上游产能/晶圆厂/代工产能"},
  {"node": "CIS 排产被挤占", "evidence": "公司产品属于 CIS，且 config 暴露上游为晶圆代工"},
  {"node": "公司 CIS 价格/交付变量", "evidence": "公司产品关键词命中 CIS"}
]
```

允许进入：

- 4.1：行业背景与供需链条；
- 4.3：只作为“待验证变量/观察窗口”，不能写成已发生公司催化。

4.3 写法要求：

- 必须出现“若/可能/需跟踪/待验证”等审慎表达；
- 必须写出“行业事件 -> 公司暴露 -> 待验证变量”；
- 不能写成“公司将受益/必然涨价/确定性催化”。

### `sector_background`

行业新闻与公司所在行业有关，但无法形成具体业务传导链。

例子：

- “半导体板块表现强”；
- “多家半导体公司 IPO 获受理”；
- “科技股领跑全球市场”。

允许进入：

- 4.1 的行业背景，且只能短句提及；
- 不允许进入 4.3 催化剂时间线。

### `noise`

与公司业务、产业链或时间窗口无关。

不进入 4.1-4.3。

## 分类方法

采用 hybrid，但本轮不新增 LLM 调用。

### 第 1 层：deterministic helper

新增或扩展 helper，例如：

`scripts/utils/industry_news_relevance.py`

输入：

- stock_name；
- stock config；
- news title/content/source/date；
- product keywords；
- upstream/downstream keywords；
- industry relevance keywords。

输出：

```json
{
  "relevance_class": "industry_chain_relevant",
  "confidence": 0.72,
  "relevance_chain": [...],
  "allowed_sections": ["4.1", "4.3"],
  "rendering_guardrails": ["tentative_language_required", "no_strong_confirmation"]
}
```

确定性规则优先级：

1. 新闻直接提到公司名/股票代码 -> `company_event`。
2. 新闻命中公司产品关键词 + 行业事件关键词 -> `industry_chain_relevant`。
3. 新闻命中上游/下游关键词，并能通过 config 的 `industry_chain_map` 连接到公司产品 -> `industry_chain_relevant`。
4. 新闻只命中行业大类，没有产品/上下游链条 -> `sector_background`。
5. 无匹配 -> `noise`。

### 第 2 层：synthesis guardrail

KnowledgeSynthesizer 的 4.3 输入可以看到新闻条目和 relevance metadata，但 4.3 输出必须遵守：

- `sector_background` 不得输出为催化剂；
- `industry_chain_relevant` 必须输出链条和待验证变量；
- `noise` 不输出；
- `company_event` 可作为公司催化。

### 第 3 层：post-render quality gate

`check_report_quality.py` 增加 warning/error：

- 4.3 出现来源为行业资讯，但没有链条词（如“传导/对应/暴露/待验证/需跟踪”）时 warning；
- 4.3 出现典型 sector background 标题（IPO 同日受理、板块表现、全球科技股等）且无公司名/产品链条时 warning；
- 强确认词搭配 `industry_chain_relevant` 时 error。

## Stock Config 增量

本轮只增加轻量字段，不做同行 Agent。

```json
{
  "industry_relevance": {
    "products": ["CIS", "CMOS图像传感器"],
    "upstream": ["晶圆代工", "晶圆厂", "产能", "8英寸", "12英寸"],
    "downstream": ["手机", "汽车电子", "安防", "机器视觉"],
    "chain_rules": [
      {
        "from": ["存储涨价", "存储扩产", "HBM扩产"],
        "through": ["晶圆厂产能紧张", "代工产能挤占"],
        "to": ["CIS排产", "CIS价格", "CIS交付"]
      }
    ]
  }
}
```

对于复旦微电，可先配置：

- products: FPGA, MCU, EEPROM, 非易失存储, 安全芯片；
- upstream: 晶圆代工, 封测, 存储产能；
- downstream: 智能电表, 车规, 卫星, 军工电子；
- chain rules: 存储供需/晶圆产能 -> EEPROM/存储器价格或交付变量。

## 数据流

1. `a_stock_source_intake` 采集 eastmoney/global news。
2. adapter 调用 deterministic relevance helper，为新闻写入：
   - `extra.relevance_class`;
   - `extra.relevance_chain`;
   - `extra.allowed_sections`;
   - `extra.rendering_guardrails`。
3. `SynthesisSkill` 将 relevance metadata 传给 `KnowledgeSynthesizer`。
4. `KnowledgeSynthesizer` 4.3 输出只使用允许进入 4.3 的条目。
5. `check_report_quality.py` 对最终 Markdown 做回扫，防止泛行业新闻又被写成催化剂。

## Failure Modes

### FM1: 过度过滤

表现：有明显多跳链条的新闻被丢掉，报告错过产业变量。

测试：CIS fixture 中“存储涨价 -> 晶圆厂产能 -> CIS 排产”应输出 `industry_chain_relevant`。

### FM2: 过度放行

表现：泛行业热度新闻进入 4.3 催化剂。

测试：“18 家半导体 IPO 同日受理”无公司名/产品链条，应为 `sector_background`，不得进入 4.3。

### FM3: LLM 将待验证变量写成确定事实

表现：“可能传导”被写成“公司确定受益/必然涨价”。

测试：4.3 中 `industry_chain_relevant` 搭配强确认词，quality gate error。

### FM4: 配置过拟合复旦微电

表现：其他股票没有 FPGA/存储关键词就全部分类失败。

测试：用 CIS 股票和通用半导体股票 fixture 覆盖不同产品链条。

## 测试计划

Focused tests:

- `tests/utils/test_industry_news_relevance.py`
  - direct company mention -> `company_event`
  - CIS multi-hop chain -> `industry_chain_relevant`
  - generic semiconductor IPO news -> `sector_background`
  - unrelated market noise -> `noise`
- `tests/utils/test_a_stock_source_intake.py`
  - eastmoney global news adapter 保留 relevance metadata。
- `tests/utils/test_knowledge_synthesizer.py`
  - 4.3 不展开 `sector_background` 为公司催化剂。
- `tests/reporter/test_report_quality.py`
  - 4.3 泛行业资讯无链条 warning；
  - `industry_chain_relevant` + 强确认词 error。

Report smoke:

- 复旦微电重新跑主入口，确认 4.3 泛行业新闻不再写成催化剂。
- 中际旭创或圣邦股份选一支回归，确认正式源边界不变。

## 实施顺序

1. 写 helper 和 fixture tests。
2. 接入 `a_stock_source_intake` adapter，只写 metadata，不改变 synthesis。
3. 修改 `KnowledgeSynthesizer` / synthesis input guardrail，让 4.3 按 relevance metadata 输出。
4. 增加 final report quality gate。
5. 复旦微电 smoke。

## Stop Conditions

- 如果需要新增 LLM 分类调用，停止，另开设计。
- 如果分类需要抓取新的外部网页，停止。
- 如果改动导致 4.1-4.3 混入社媒/雪球/知乎原文，停止。
- 如果多跳链条只能靠模型脑补、没有 config 或新闻证据支持，不允许输出到 4.3。
