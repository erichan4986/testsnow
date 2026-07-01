# Implementation Review: Xueqiu Detail One-Time Refill

Date: 2026-07-01
Source design: `docs/agent_workflow/2026-07-01-xueqiu-detail-refill-design.md`
Design delta: `docs/agent_workflow/2026-07-01-xueqiu-detail-refill-design-delta.md`
Previous review: `docs/agent_workflow/2026-07-01-xueqiu-detail-refill-claude-review-notes.md`

Reviewed files:
- `scripts/utils/xueqiu_detail_selection.py` (NEW — 503 lines)
- `scripts/utils/fetcher.py` (MODIFIED — 83 lines added)
- `scripts/utils/social_viewpoint_source_packets.py` (MODIFIED — 14 lines added)
- `tests/utils/test_xueqiu_detail_selection.py` (NEW — 162 lines, 5 tests)
- `tests/utils/test_social_viewpoint_source_packets.py` (MODIFIED — 1 new test)
- `tests/utils/test_detail_page_fetcher.py` (UNCHANGED — 6 fixture-based tests)
- `tests/utils/test_extract_detail_cli.py` (UNCHANGED — 3 CLI tests)
- `tests/reporter/test_report_source_boundary.py` (UNCHANGED — 4 boundary tests)

---

## Verdict

**verdict: ok**

| 类别 | 数量 | 说明 |
|------|------|------|
| blocker | 0 | 无阻断项 |
| warning | 2 | 非功能性建议，不阻塞提交 |
| nice-to-have | 2 | 可优化项 |

---

## 逐项审查结果

### 1. Helper 是否完全无 Playwright/网络依赖

**✅ PASS.** `xueqiu_detail_selection.py` 仅依赖项目内已有的纯函数：

```python
try:
    from .content_quality import content_score
except ImportError:
    from content_quality import content_score

try:
    from .curated_external_full_body_viewpoint_claims import normalized_hash
except ImportError:
    from curated_external_full_body_viewpoint_claims import normalized_hash
```

无 `playwright`、`requests`、`aiohttp`、`selenium` 等任何网络库。所有函数为纯文本匹配 + 排序 + 条件判断。测试不启动 Chrome、不访问雪球。

### 2. `min_topic_coverage` 是否动态受实际候选桶限制

**✅ PASS.** 设计 delta 接受的 B1 修复已实现：

- 默认值改为 `min_topic_coverage: 2`（原设计 3）
- `_effective_topic_coverage()` 逻辑：`min(config.min_topic_coverage, populated_non_sentiment_buckets_count)`

```python
def _effective_topic_coverage(cfg, populated_buckets):
    populated_count = len([b for b in populated_buckets if b not in NON_TOPIC_BUCKETS])
    return min(int(cfg["min_topic_coverage"]), populated_count)
```

测试 `test_effective_topic_coverage_does_not_require_missing_extension_buckets` 验证：当仅有 2 个非 sentiment 桶时，`min_topic_coverage=3` 实际降为 2，不会误触发 refill。

### 3. Extension buckets 是否不会默认强制半导体/航天

**✅ PASS.** 关键设计：

- `DEFAULT_CONFIG["enabled_extension_buckets"] = ()`（空元组）— **默认不启用任何扩展桶**
- 扩展桶存储在 `EXTENSION_BUCKETS` 字典中，需显式通过 config 的 `enabled_extension_buckets` 启用
- `classify_detail_topics()` 只在 `cfg["enabled_extension_buckets"]` 中包含的扩展名时，才查询对应的关键字
- Fetcher 中为复旦微电硬编码启用 `["semiconductor_product", "aerospace"]`（通用股票不会被动获取半导体关键字）

**警告 W1:** fetcher.py 第 373 行硬编码了 `"enabled_extension_buckets": ["semiconductor_product", "aerospace"]`。这在复旦微电场景正确，但后续需通过 stock config 驱动而非硬编码。对当前代码库无影响（唯一调用者是 Fudan 测试和手动运行的 live fetch）。

### 4. `build_refill_plan` 是否真的只补录一次并受总 cap 限制

**✅ PASS.** 三重防护机制：

1. **`refill_already_used` 标志**：在 config 中设置后，`build_refill_plan` 立即返回 `should_refill=False`
2. **总 cap 计算**：`remaining_capacity = max(0, cfg["max_detail_pages_total"] - len(attempts))`，`batch_size = min(cfg["refill_batch_size"], remaining_capacity)`
3. **Fetcher 层**：只在 `refill_plan.get("should_refill")` 为 True 时才执行补录 batch，补录后不再递归

测试 `test_refill_is_one_time_capped_and_prioritizes_missing_topics` 验证：
- `max_detail_pages_total=3`，第一批用掉 1 个 → remaining_capacity=2 → refill batch 最多 2 个 ✓
- 第二次调用 `build_refill_plan` 带 `refill_already_used=True` → `should_refill=False` ✓

### 5. `evaluate_detail_attempts` 是否用内容 hash 去重

**✅ PASS.** 去重机制：

- `_content_key()` 函数：对 ≥20 字符的内容用 `normalized_hash(content)`；对短内容用 `normalized_hash(title + url)` 作为 fallback
- `evaluate_detail_attempts` 维护 `seen_content_hashes: set[str]`，每处理一个 attempt 先计算 `content_key`，已在集合中的标记为 `duplicate`
- `build_refill_plan` 在候选过滤时也检查 `dedupe_key in attempted_hashes`，避免 refill 再次选中已抓取过的内容

测试 `test_duplicate_content_counts_once_when_deciding_refill` 验证：
- 两个不同 URL（`/1/a`、`/1/b`）但相同 content → usable_count=2 中应有 1 个被去重 → usable_count=2? 

等等，让我再看一下这个测试的断言。两个相同内容 + 一个不同内容 = 3 个 attempts。两个相同中 1 个标记 duplicate → 1 usable + 1 个不同内容 = 2 usable。`min_usable_details=3` → `usable_below_minimum` → `should_refill=True`。测试正确。

### 6. `fetcher.py` 接入是否破坏原有 featured/sentiment 返回结构

**✅ PASS.** 返回结构变化分析：

- **旧结构**：`{"featured": [...], "sentiment": [...]}`
- **新结构**：`{"featured": [...], "sentiment": [...], "_selection_audit": {...}}`

关键点：
- `featured` 和 `sentiment` 的 key **完全保留**，类型不变
- `_selection_audit` 是 **新增可选 key**，不会破坏任何现有消费者
- `fetch_all_stocks()` 使用 `result.get("featured", [])` 和 `result.get("sentiment", [])`，安全兼容新增 key
- 降级逻辑正确：抓取失败或正文过短的 post 进入 sentiment，已抓取成功的进入 featured
- 剩余未进详情页的 featured candidates 降级到 sentiment（**旧实现只 truncate 后 max_detail_posts 个，新实现已所有 candidate 中未 attempt 的降级**，语义更精确）

**警告 W2:** `attempt_detail_batch` 闭包内闭包引用 `featured_posts`、`sentiment_posts`、`detail_attempts`、`detail_plan`、`refill_plan` 等外层变量。异常路径（`except Exception`）中 `detail_attempts.append(attempt)` 后抛出的 `logger.warning` 如果失败不会影响已有 append。但 `detail_attempts` 在 fetch 成功/失败/异常三种路径下都 append，确保 `evaluate_detail_attempts` 看到的 attempt 计数完整。当前实现正确。

### 7. `_selection_audit` 是否足够解释 first/refill/drop

**✅ PASS.** 当前 audit 结构：

```python
"_selection_audit": {
    "first_batch_urls": [...],        # 第一批已选 URL
    "refill_batch_urls": [...],        # 补录批 URL
    "attempted_urls": [...],           # 所有已尝试 URL
    "drop_reasons": {"url": "reason"}, # 每个失败的 drop 原因
    "refill_reasons": [...],           # 触发 refill 的原因列表
    "topic_buckets": [...],            # 候选集中的话题桶
    "total_detail_pages": N,           # 总抓取数
}
```

对比设计文档要求的 audit 字段：
| 设计要求 | 实现 | 状态 |
|---------|------|------|
| attempted detail URLs | `attempted_urls` | ✅ |
| first-batch URLs | `first_batch_urls` | ✅ |
| refill URLs | `refill_batch_urls` | ✅ |
| drop reasons per URL | `drop_reasons` | ✅ |
| topic buckets per URL | plan audit 中有 `populated_topic_buckets` | ✅ |
| dedupe groups | `duplicate_count` + `drop_reasons[url]="duplicate"` | ✅ |
| refill trigger reason | `refill_reasons` | ✅ |
| total detail pages fetched | `total_detail_pages` | ✅ |

### 8. `social_viewpoint_source_packets.py` 是否只增强 4.4 packet

**✅ PASS.** 所有 social packets 仍然具有：

```python
"synthesis_display_only": True,
"scoring_eligible": False,
"risk_score_eligible": False,
"verification_status": "professional_observation",
```

已添加的改动（14 行）：
1. `_xueqiu_like_candidates` 中传递 `source_detail_type` 字段（之前被丢弃）
2. `_social_source_profile` 中增加了 `explicit_detail_type` 优先匹配：如果 `source_detail_type == "xueqiu_column"`，直接返回 column profile，不再依赖启发式文本匹配

这意味着 `to_stocks_data_posts()` 产生的「refill post → stocks_data → 4.4 packet」链路完整且 display-only 属性正确。

测试 `test_build_social_source_packets_accepts_refill_stocks_data_shape` 验证了这个链路。

### 9. 测试是否覆盖复旦估值帖 `https://xueqiu.com/1606930351/392467740`

**✅ PASS.** 两个测试直接覆盖：

1. `test_first_plan_keeps_fudan_valuation_long_post_despite_hot_aerospace_posts`
   - 使用精确 URL `https://xueqiu.com/1606930351/392467740`
   - 使用 `VALUATION_POST` 内容（包含 PE、PS、港股折价、紫光国微可比等估值细节）
   - 8 个 aerospace 热门帖中混入 1 个估值帖
   - 断言估值帖在 first_batch 中，且 `valuation` topic 在 populated buckets 中

2. `test_refill_output_can_be_converted_to_stocks_data_shape`
   - 也使用该 URL 和内容
   - 验证 `to_stocks_data_posts()` 输出可被 `build_social_source_packets()` 消费
   - 断言 batch、topic、source 等字段正确传递

---

## 测试运行结果

### 第 1 组：核心测试 (23 tests)
```
python3 -m pytest tests/utils/test_xueqiu_detail_selection.py tests/utils/test_social_viewpoint_source_packets.py tests/utils/test_detail_page_fetcher.py tests/utils/test_extract_detail_cli.py tests/reporter/test_report_source_boundary.py -q
.......................
23 passed in 0.37s
```

### 第 2 组：报告源策略测试 (29 tests)
```
python3 -m pytest tests/reporter/test_stock_reporter_source_intake_config.py tests/reporter/test_formal_first_source_policy_preview.py -q
.............................
29 passed in 3.95s
```

### CI 门控
```
bash tools/ci_grep_gates.sh
[gate a] periodic report / broker research material-layer isolation ... ok
[gate c] curated external display-only isolation ... ok
[gate b] source safety AST checks ... ok
ci_grep_gates: all gates passed
```

### 空白差异检查
```
git diff --check
(无输出 — 无空白错误)
```

### Git 状态
```
 M scripts/utils/fetcher.py
 M scripts/utils/social_viewpoint_source_packets.py
 M tests/utils/test_social_viewpoint_source_packets.py
?? docs/agent_workflow/2026-07-01-xueqiu-detail-refill-claude-review-notes.md
?? docs/agent_workflow/2026-07-01-xueqiu-detail-refill-claude-review-round1.md
?? docs/agent_workflow/2026-07-01-xueqiu-detail-refill-design-delta.md
?? docs/agent_workflow/2026-07-01-xueqiu-detail-refill-design.md
?? scripts/utils/xueqiu_detail_selection.py
?? tests/utils/test_xueqiu_detail_selection.py
```

52/52 全部通过，3 个门控全部 ok，git diff --check 无输出。

---

## Nice-to-Have

### N1: `_content_key` 对短内容 fallback 可进一步优化

当前短内容（<20 chars）fallback 使用 `normalized_hash(title + url)`。如果两个不同 post 都短到 <20 chars，title 也不同但 url 不同，不会误判。ok。但如果同一个 post 的 content 偶发被截断到 <20 chars，再抓一次 content 可能变为 ≥20 chars — 第二次的 hash 会不同。建议对短内容的 hash seed 也加入 `normalized_hash` 的归一化处理（目前 fallback 已经正确，不会误去重，只是两次同内容 hash 可能因 <20 边界不同）。当前行为安全（宁可 false negative 不去重，不让 false positive 吞掉不同内容）。

### N2: `to_stocks_data_posts` 未被 fetcher 自动调用

Fetcher 返回 `{"featured": [...], "sentiment": [...], "_selection_audit": {...}}`，未调用 `to_stocks_data_posts()`。这意味着 refill 产出需要报告 composer 显式调用该 bridge 函数才能进入 4.4 packet builder。这是一个集成点，不是缺陷——设计要求和 review notes 都要求"可用"而非"自动"。当前 test 证明了链路正确。后续如果需要自动集成，可在 `extract_detail.py` 中调用 `to_stocks_data_posts()` 并合并到 report_input.json 的 `stocks_data`。

### N3: 测试未覆盖 FM8（refill 时零可用候选）

设计文档的 FM8（refill 时剩余 candidates 全部已尝试，batch_size=0）未在测试中明确覆盖。虽然 `build_refill_plan` 的 `if batch_size <= 0` 和 `_select_with_topic_quota` 的空列表行为已经隐式处理（返回空 refill_batch），但缺少一个专门测试。可以补一个：

```python
def test_refill_with_no_remaining_candidates_returns_empty():
    posts = [_post("https://xueqiu.com/1/done", "已尝试的帖子")]
    plan = build_detail_plan(posts, {"first_batch_size": 1, "max_detail_pages_total": 1})
    attempted = [{"url": p["url"], "content": "", "drop_reason": "fetch_failed"} for p in plan["first_batch"]]
    evaluation = evaluate_detail_attempts(attempted, {"min_usable_details": 1})
    refill = build_refill_plan(plan["candidates"], attempted, evaluation, {"max_detail_pages_total": 1})
    assert refill["should_refill"] is False
    assert refill["audit"]["remaining_capacity"] == 0
```

非阻塞——代码行为正确，只是缺少显式回归测试。

---

## 偏离点

无偏离。实现严格遵循了 design + design-delta 的规格：

| 设计要求 | 实现状态 |
|---------|---------|
| 第一批 TopN + topic quota | ✅ `_select_with_topic_quota` 优先 preferred_buckets 再按 score 填满 |
| 一次性补录（不递归） | ✅ `refill_already_used` 标志 + fetcher 不递归 |
| 总 page cap 约束 | ✅ `max_detail_pages_total` 在多个点约束 |
| 内容 hash 去重 | ✅ `_content_key()` + `seen_content_hashes` |
| 通用/扩展桶分离 | ✅ `GENERIC_BUCKETS` + `EXTENSION_BUCKETS` |
| min_topic_coverage 动态调整 | ✅ `_effective_topic_coverage()` |
| refill 输出可进 4.4 | ✅ `to_stocks_data_posts()` + `build_social_source_packets()` |
| display-only 隔离 | ✅ 所有 social packet 保持不变 |
| 无网络依赖 | ✅ 纯文本匹配 + fixture-only 测试 |
| 复旦估值帖被包含 | ✅ 测试覆盖 `https://xueqiu.com/1606930351/392467740` |

## 是否建议提交

**建议提交。** 实现正确，测试完整，门控全部通过。两个 warning 不阻塞：

- W1: extension bucket 硬编码在 `fetcher.py` — 不影响当前逻辑，后续接入 stock config 时重构即可
- W2: 闭包引用模式 — 当前正确但可读性一般，非功能问题

Review notes 的 B1（min_topic_coverage 阈值）和 M1-M3（去重、桶分层、4.4 pipeline）全部在实现中正确修复。

## 关键文件行号速查

| 位置 | 内容 |
|------|------|
| `xueqiu_detail_selection.py:22-80` | GENERIC_BUCKETS / EXTENSION_BUCKETS 定义 |
| `xueqiu_detail_selection.py:110` | DEFAULT_CONFIG, `min_topic_coverage: 2` |
| `xueqiu_detail_selection.py:125-139` | `classify_detail_topics()` — 带 extension 桶支持 |
| `xueqiu_detail_selection.py:142-166` | `build_detail_plan()` — 第一批 + topic quota |
| `xueqiu_detail_selection.py:169-254` | `evaluate_detail_attempts()` — 内容 hash 去重 + refill 判定 |
| `xueqiu_detail_selection.py:257-300` | `build_refill_plan()` — 一次性补录 + cap 约束 |
| `xueqiu_detail_selection.py:303-328` | `to_stocks_data_posts()` — bridge 到 4.4 packet |
| `xueqiu_detail_selection.py:421-423` | `_effective_topic_coverage()` — 动态阈值 |
| `xueqiu_detail_selection.py:439-443` | `_content_key()` — 内容 hash 去重 |
| `fetcher.py:360-374` | build_detail_plan 调用 + extension 桶启用 |
| `fetcher.py:424-445` | evaluate_detail_attempts + build_refill_plan 调用 |
| `fetcher.py:455-466` | `_selection_audit` 输出 |
| `social_viewpoint_source_packets.py:114` | source_detail_type 字段传递 |
| `social_viewpoint_source_packets.py:173-189` | explicit_detail_type 优先匹配 |
| `test_xueqiu_detail_selection.py:46-69` | FM1 复旦估值帖测试 |
| `test_xueqiu_detail_selection.py:72-81` | FM4 通用股票 topic coverage 测试 |
| `test_xueqiu_detail_selection.py:84-112` | FM5 内容 hash 去重测试 |
| `test_xueqiu_detail_selection.py:115-138` | FM3 一次性补录 + cap 测试 |
| `test_xueqiu_detail_selection.py:141-161` | M3 stocks_data bridge 测试 |
| `test_social_viewpoint_source_packets.py:149-180` | refill stocks_data → 4.4 packet 测试 |
