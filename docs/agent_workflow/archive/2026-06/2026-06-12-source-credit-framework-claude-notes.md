# Source Credit Framework Review Round 1

## Status

Ready with changes

## Findings

### High

- 无高优先级问题。Phase 1 的范围、边界和护栏设计是合理的。

### Medium

1. **检测优先级未显式文档化/测试化**
   当前设计列出了 9 种 source type，但没有说明当多个信号冲突时如何裁决。例如：
   - `source_platform="AgentReach(web)"` 但 URL 是 `blacksesame.com`
   - raw 里 `source_type="official"` 但域名未知
   - URL 含 `/ir/` 但平台被标为 social
   这些边界情况若不做成显式规则，会导致同一输入在不同实现者手中得到不同 `source_type`。

2. **`social_discussion` 的 `knowledge_eligible=True` 语义可能被误读**
   设计文档明确说明社交来源“可作为知识库输入，但默认 `report_eligible=False`”。然而 `knowledge_eligible=True` 对后续证据笔记（evidence note）消费者来说，容易被理解为“可信事实可入库”。需要在模块级文档和测试中强调：这表示“可作为待验证的 claim/hypothesis 入库”，而非“已验证事实”。

3. **`broker_research` 的 `report_eligible=True` 存在利益冲突风险**
   研报（broker research）虽然属于专业分析，但存在投行关系、评级偏向等利益冲突。Phase 1 不进入 LLM synthesis 和报告结论，因此当前 72 分 + report eligible 可接受；但应在代码注释中说明这是“需要交叉验证的专业分析”，为后续阶段留警示。

4. **公司域名白名单目前只 hard-code `blacksesame.com`**
   设计建议从常量开始，但应提供清晰的常量结构（如 `COMPANY_OFFICIAL_DOMAINS` 列表），并测试“新增第二个域名时无需修改判定逻辑”这一扩展路径。否则 Phase 2 支持多只股票时容易演变成散落的分支判断。

### Low

1. **`SourceCreditResult` 可考虑增加 `source_domain`**
   对后续知识库去重、交叉验证、按域名聚类会很有用。该字段可从 URL 推导，但显式携带更方便。Phase 1 非必需。

2. **URL 归一化未覆盖**
   当前 domain rules 使用精确匹配，若遇到 `http://blacksesame.com`、`www.blacksesame.com.cn`、带尾部斜杠或查询参数的 URL，可能漏判。建议在 `score_source_credit()` 内部先做一次归一化（去 scheme/www/尾部斜杠/查询参数）。

3. **`verification_status` 取值未固化为常量/枚举**
   `primary_source`、`professional_analysis`、`secondary_source`、`market_opinion`、`unverified` 这些字符串若散落在测试和实现中，容易漂移。建议模块内定义常量集合。

## Recommendations

1. **保持 `source_credit.py` 为独立模块，不要内联到 `source_adapter.py`**
   来源信用是跨来源（Agent-Reach、知乎、雪球、公告、研报）的横切关注点，与格式转换职责分离后更利于后续复用和单测。

2. **在 `source_credit.py` 模块顶部显式声明检测优先级**
   例如：
   ```text
   exchange/regulatory > company_ir > company_official > broker_research > mainstream_media > industry_media > social_discussion > unknown_web > missing_source
   ```
   并在单元测试中覆盖冲突信号场景。

3. **补充边界与冲突测试**
   增加以下用例后再视为 Phase 1 完成：
   - 社交平台字符串 + 官网 URL：应以 URL 为准判为 `company_official`
   - raw `source_type="ir"` + 普通 URL：应判为 `company_ir`
   - raw `is_official=True` + 未知域名：不应直接提升到 `company_official`
   - 缺少 URL 但 `source_platform="知乎"`：应判为 `social_discussion` 还是 `missing_source`？需明确规则并测试。

4. **文档化 `knowledge_eligible` 的语义**
   在模块 docstring 中说明：
   - `knowledge_eligible=True` 仅表示“可进入知识库作为候选证据/待验证观点”
   - `report_eligible=True` 仅表示“可在报告证据区展示”
   - 两者均不等于“已被证实为事实”

5. **保持 `AgentReachAdapter` 的最小改动**
   只需在 `extra` 字典中追加 source-credit 字段，不要改 `SynthesisItem` 构造签名。现有下游（quality skill、renderer）均只读取 `extra["raw"]` 或顶层字段，追加键值是向后兼容的。

6. **保持当前 `report_eligible` 默认分层不变**
   社交/行业/未知来源默认不进报告证据区，已足够保守；官方/交易所/研报/主流媒体可进报告，符合 A/H 股研究惯例。

## Test Gaps

1. **broker research 检测路径**
   设计只提到“platform/metadata indicates 研报/research/broker/institution”，但未给出具体触发条件。需要测试：
   - `source_platform="研报"`
   - raw `source_type="research"`
   - raw 含 `institution` 字段
   - 三者组合与优先级

2. **mainstream / industry media 域名白名单**
   设计未列出具体域名列表。若模块内部已有常量，应测试边界域名命中与未命中；若尚未定义，需在实现前补充。

3. **URL 归一化边界**
   - `https://www.blacksesame.com/zh/list_10/972.html`
   - `http://blacksesame.com/zh/list_10/972.html`
   - `blacksesame.com.cn/...`
   - 带 `?utm=...` 的官网 URL

4. **平台名称别名**
   - `知乎` / `zhihu`
   - `雪球` / `xueqiu`
   - `Twitter` / `X` / `twitter`
   - `Reddit` / `bilibili` / `weibo` / `xiaohongshu`

5. **原始元数据优先级**
   - `user_provided_url=True` 在官网域名上应添加原因，但在非官网域名上不应提升信用。
   - `is_official=True` 与未知域名的组合行为。
   - `source_type="official"` 与平台/URL 的交互。

6. **`adapt_all` 合约回归测试**
   设计已要求“existing `adapt_all(agent_reach_items=[...])` contract tests still pass”，但当前 `tests/utils/test_source_adapter.py` 中并未断言 `extra` 的具体内容。实现后应新增断言：`extra` 同时包含 `raw` 和 source-credit 字段，且原有字段未被覆盖。

7. **缺失来源场景**
   - 空 URL + 空 platform + 空 metadata → `missing_source`
   - 空 URL + platform="知乎" → 需明确规则
   - 有 URL 但无法解析域名 → `unknown_web`

8. **来源信用函数纯度验证**
   设计目标要求“pure and testable without network, browser, subprocess, or LLM”。单元测试可顺带断言 `score_source_credit()` 不依赖外部调用；虽然不需要做 import 黑名单测试，但实现时应避免引入 `urllib.request`、subprocess、LLM client。

## Final Recommendation

**Ready to implement with changes.**

- `scripts/utils/source_credit.py` 作为独立模块是正确的边界，与 `source_adapter.py` 的职责分离清晰。
- `SourceCreditResult` 的字段足以支撑 Phase 1 的元数据标注和未来的 evidence note / claim verification 入口；`source_domain` 可在后续阶段按需添加。
- 来源信用分层适合 A/H 股研究：交易所公告 > 公司 IR/官网 > 券商研报 > 主流媒体 > 行业媒体 > 社交/未知，符合投资者的信息优先级。
- 在 `AgentReachAdapter.to_synthesis_item()` 中仅扩展 `extra` 字典追加 source-credit 字段，不会破坏现有下游；`agent_reach_quality_skill.py` 和 renderer 只读 `extra["raw"]` 或顶层字段，不受影响。
- 当前护栏足够：Phase 1 不改 `KnowledgeSynthesizer`、不改质量门阈值、不改 renderer、不写 knowledge/ 文件、不调用网络/LLM，source-credit 仅作为 inert metadata 存在。

**必须在实现前补充的工作**：显式检测优先级文档、冲突信号测试、URL 归一化、以及 `knowledge_eligible` 语义注释。完成这些后 Phase 1 可以安全进入编码。
