# Evidence Note Writer Phase 2 — Design Review Notes

**日期**: 2026-06-12  
**任务**: 设计 Evidence Note Writer Phase 2，将 Agent-Reach source-credit 标注后的数据写入知识库 evidence notes，供后续 LLM wiki / claim verification / KnowledgeSynthesizer 使用。  
**设计文档**: `docs/agent_workflow/2026-06-12-evidence-note-writer-design.md`

---

## Status

**Ready to implement with minor clarifications.**

---

## Findings

### High

- 无高优先级问题。Phase 2 的范围、边界和护栏设计是合理的，严格限定在“独立纯模块 + 单元测试”，不接入 pipeline，不影响现有 report/KnowledgeSynthesizer/quality gate。

### Medium

1. **`topics` 来源需要明确**
   设计文档建议“优先复用 `classify_agent_reach_topic()`”，但该函数位于 `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`。虽然只读导入不会修改 renderer，却会在 evidence note writer 与 renderer 之间建立耦合。如果未来 renderer 的主题关键字调整，evidence note writer 的行为会随之变化。
   - **建议**：在 `evidence_note_writer.py` 内保留一份最小关键字表作为 fallback，当导入 renderer 失败或返回空时仍能提供稳定的主题标签。

2. **`claim_status` 语义需在模块 docstring 中显式声明**
   `fact_candidate` 容易被 downstream 消费者误读为“已验证事实”。必须在代码注释和 frontmatter 模板中强调：Phase 2 的 `fact_candidate` 仅表示“来源信用足够高，可作为事实候选”，不等于已证实。

3. **无 URL item 的去重兜底键稳定性不足**
   使用 `source_platform + title + publish_time` 作为 canonical key 时，若 title 或 publish_time 在不同采集轮次有微小差异（如空格、标点、时区），会导致重复写入。Phase 2 可接受，但应在文档中标注这是已知限制。

4. **与 `agent_reach_quality_skill` 的交互边界**
   evidence note writer 应消费 `agent_reach_keep_items` + `agent_reach_demote_items`，而不消费原始 `agent_reach_items`。这一点设计文档已说明，但需要在函数签名和测试命名中反复强调，避免未来实现者把 quality gate 之前的原始 items 直接传入。

### Low

1. **文件名中的 `source_domain` 可能为空**
   对于无 URL 的 social item，`source_domain` 为空字符串，生成的文件名会出现连续连字符（如 `20260612-social_discussion--a1b2c3d4.md`）。这不影响功能，但略显不雅，建议空 domain 时替换为 `no-domain`。

2. **正文“后续核查问题”为固定模板**
   Phase 2 使用固定问题列表即可，但应把这些问题作为常量放在模块顶部，便于 Phase 3 替换为 LLM 生成问题。

3. **是否写入 `report_eligible=False` 的高互动 social item？**
   设计明确“keep/demote 都写”，因此即使 `report_eligible=False`，只要 `knowledge_eligible=True` 且 quality action 为 keep/demote，就应写入。这一点合理，但需要在测试中用一条 `agent_reach_quality_score=70` 的 social item 验证。

---

## Recommendations

1. **保持 `evidence_note_writer.py` 为纯模块，不接 skill pipeline**
   当前设计把模块放在 `scripts/utils/` 而不是 `report_skills/`，且不使用 `@skill` 装饰器，是正确的。这样可以先在单元测试和手动脚本中验证，避免污染主流程。

2. **新增 `tests/utils/test_evidence_note_writer.py` 覆盖核心合约**
   测试应包括：
   - high-credit 官网 item → frontmatter 字段完整、`claim_status=fact_candidate`。
   - social low-credit item → `claim_status=unverified_claim`。
   - `knowledge_eligible=False` item（如 `missing_source`）→ 不写入。
   - 重复 URL → 第二次调用不写入。
   - 无 URL item → 使用兜底 canonical key 写入。
   - 安全文件名 → 无路径遍历、无非法字符。
   - dry_run=True → 返回计划但不写入磁盘。
   - 不改 KnowledgeSynthesizer / report output / quality gate。

3. **对外暴露最小 API**
   建议主入口为：
   ```python
   def write_evidence_notes(
       stock_name: str,
       stock_code: str,
       items: List[SynthesisItem],
       base_dir: Union[str, Path],
       collected_at: Optional[str] = None,
       dry_run: bool = False,
   ) -> EvidenceWritePlan:
       ...
   ```
   其中 `EvidenceWritePlan` 为 dataclass，含 `written`, `skipped_existing`, `filtered` 三个列表，便于测试和 dry-run 输出。

4. **文件名冲突处理采用“hash 后追加序号”**
   不覆盖已有文件是安全默认；在 short_hash 后追加 `-1`, `-2` 足够简单且可回滚。

5. **保持与 `source_credit.py` 的字段一致**
   frontmatter 中 `source_type`, `source_domain`, `source_credit`, `verification_status`, `credit_reasons`, `knowledge_eligible`, `report_eligible` 应直接从 `item.extra` 读取，不重新计算，避免与 Source Credit Framework 产生分歧。

---

## Test Gaps

1. **跨股票隔离**
   测试应验证不同股票的 evidence notes 写入各自 `knowledge/10-Stocks/<stock>/evidence/` 目录，不会串目录。

2. **`collected_at` 回退逻辑**
   当 `published_at` 和 `collected_at` 都缺失时，文件名应使用 `unknown-date` 前缀且 frontmatter 中 `published_at` 为空字符串。

3. **空 `source_domain` 文件名**
   验证 `source_domain=""` 时文件名不会出现路径问题。

4. **source-credit 字段直接透传**
   断言 frontmatter 中的 `source_credit`, `verification_status`, `credit_reasons` 与 `item.extra` 完全一致，不经过二次加工。

5. **无网络/无 LLM/无浏览器/无 subprocess**
   单元测试可通过 `tmp_path` 和 fixture 完成；不需要 monkeypatch 网络，因为模块本身不发起网络请求。但可在模块 docstring 中明确这一约束。

6. **renderer 未改变**
   运行 `tests/reporter/test_agent_reach_quality_skill.py` 和任何 renderer 相关测试作为回归，确认 evidence note writer 不影响现有输出。

---

## Final Recommendation

**Ready to implement with minor clarifications.**

- 设计方案符合“先进入知识库、区分高低信用来源、不调用 LLM、不改 pipeline”的目标。
- 模块边界清晰：`scripts/utils/evidence_note_writer.py` 作为纯函数模块，`tests/utils/test_evidence_note_writer.py` 保证合约。
- 不触碰任何禁止文件：quality gate、renderer、KnowledgeSynthesizer、scoring engine、pipeline、入口脚本、`config/stocks.json`、现有 `knowledge/posts/`、`reports/` 均保持不变。
- 风险可控：dry-run 机制、基于 canonical URL 的去重、安全文件名、默认不覆盖，能有效防止污染知识库。
- 实现前需明确的两个 minor 点：`topics` 是复用 renderer 分类器还是内建 fallback；`claim_status` 语义需在代码注释中显式强调为“候选/待验证”。

完成上述 minor 澄清后即可安全进入编码。
