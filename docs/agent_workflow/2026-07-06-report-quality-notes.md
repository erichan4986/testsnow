# Report Quality MF-1 / formal_medium 备注

日期：2026-07-06
分支：codex-report-quality-upgrade

## MF-1：check_report_file 的 snapshot gate 口径

**决策**：`check_report_file()` 保持 Markdown-only，不检查 in-memory `deep_analysis_material_snapshot`。

**原因**：
- `deep_analysis_material_snapshot` 由 `deep_analysis_renderer.py` 在渲染时内存构建/消费，未持久化为 sidecar。
- 用户明确反对新增大型 sidecar。
- snapshot 相关 gates（`deep_material_snapshot_*`）已由 `check_report_text(..., deep_analysis_material_snapshot=...)` 覆盖，这是 unit-test 和内存检查的自然入口。
- `check_report_file()` 的现有语义是读取 Markdown 和已有的三种 sidecar（industry relevance / peer comparison / fundflow）。把 in-memory snapshot 强加给它会破坏接口语义并需要新增持久化机制。

**代码体现**：
- `scripts/utils/report_quality.py` 中 `check_report_file()` 的 docstring 明确说明不加载/不检查 snapshot。
- `check_report_text()` 的 docstring 保留并强化了 `deep_analysis_material_snapshot` 参数说明。
- `tests/reporter/test_report_quality.py` 中新增 `test_check_report_file_does_not_run_snapshot_gates`，即使存在伪造的 snapshot sidecar，也断言 `check_report_file()` 不会产生任何 `deep_material_snapshot_*` issues。

## formal_medium evidence-depth gate

**目标**：给 `formal_medium` profile 增加轻量质量门，保证 4.1/4.2/4.3 不是空泛占位段落，但不要求 `formal_rich` 级别的完整性。

**实现**：`scripts/utils/report_quality.py` 新增 `_check_formal_medium_evidence_depth(text, profile)`。

**规则**（仅对 `profile == "formal_medium"` 生效）：
- 4.1/4.2/4.3 每个 section 若不存在，跳过（`missing_deep_analysis_subsection` 已负责）。
- 内容过薄（去除空白和引用后少于 40 字符）或命中 fallback 模式且少于 80 字符 → warning `formal_medium_section_too_thin`。
- 无 inline citation 且无具体数字/日期/产品/公司证据 → warning `formal_medium_section_lacks_evidence`。
- 级别为 warning，保持轻量。

**已验证不会误杀**：中际旭创 20260706 报告的 4.1/4.2/4.3 均有大量 inline citations 和具体数字/产品/公司证据，满足 gate 条件。

**测试覆盖**：
- `test_formal_medium_thin_sections_warn`
- `test_formal_medium_section_without_citations_but_specific_content_passes`
- `test_formal_medium_normal_report_with_citations_passes_evidence_depth`

## 相关文件

- `scripts/utils/report_quality.py`
- `tests/reporter/test_report_quality.py`
- `docs/agent_workflow/2026-07-06-report-quality-notes.md`
