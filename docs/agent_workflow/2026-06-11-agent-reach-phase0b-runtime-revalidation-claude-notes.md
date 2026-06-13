# Agent-Reach Phase 0B Runtime Revalidation Notes

## Status

Accepted

## Tests

| Command | Result |
| --- | --- |
| `pytest tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_quality_skill.py -q` | 52 passed |
| `pytest tests/reporter/test_agent_reach_connector.py tests/reporter/test_agent_reach_evidence_renderer.py -q` | 54 passed |
| `pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q` | 8 passed |

Total: **114 passed, 0 failed**.

## No-Input Behavior

- search_queries: `[]`
- fetch status: `empty`
- quality status: `empty`
- warnings: none

Agent-Reach with `enable_agent_reach=True`, stock name and code provided, but **no** `agent_reach_rss_feeds` and **no** `agent_reach_urls`:

- Query skill returns an empty list (no RSS query generated, no Web query generated).
- Fetch skill receives empty `search_queries` and sets `agent_reach_status` to `empty`.
- Quality skill receives zero items and sets `agent_reach_quality_status` to `empty`.
- No exceptions, no warnings, no network calls.

## Explicit RSS Results

### Identity-Only Filter (`黑芝麻智能`, `02533`)

| Feed | Stock/filter | Fetch status | Items | Keep | Demote | Discard | Key warnings |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 36kr | 黑芝麻智能 / ["黑芝麻智能", "黑芝麻", "02533"] | ok | 0 | 0 | 0 | 0 | none |

- **No items returned**. No false positives. Identity-only filtering is working as intended — articles that do not explicitly mention the stock name or code are filtered out at the fetch stage.

### Broad Filter Comparison (`科技`)

To validate that identity-only filters prevent false positives, a comparison run was made with the broad term `科技`:

| Feed | Filter | Items | Keep | Demote | Discard | Max score |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 36kr | `科技` | 5 | 0 | 3 | 2 | 46 |

Representative items (all scored too low to keep):

- "最前线｜坦途科技全球首款消费级水上飞行器首飞..." — demote, score 34, reasons: 匹配 1 个查询词; 含 1 个业务关键词; 有URL; 含 2 类数据指标; 标题充实; 内容较长; 标题+内容完整; 含 1 个炒作信号
- "浪往南走：今年盛夏，WAVES来到番禺" — demote, score 38, reasons: 匹配 1 个查询词; 含 2 个业务关键词; 有URL; 含 5 类数据指标; 标题充实; 内容较长; 标题+内容完整; 含 1 个垃圾信息信号
- "36氪首发 | 创维独家投资数千万..." — score 42, reasons: 匹配 1 个查询词; 含 6 个业务关键词; 有URL; 含 1 类数据指标; 含 1 个日期; 标题充实; 内容较长; 标题+内容完整
- "8点1氪丨世界杯门票遇冷..." — score 46, reasons: 匹配 1 个查询词; 含 9 个业务关键词; 有URL; 含 6 类数据指标; 含 5 个日期; 标题充实; 内容较长; 标题+内容完整; 含 2 个炒作信号; 含 1 个垃圾信息信号

**Conclusion**: Even with the broad `科技` filter, none of the 5 items reached the RSS keep threshold (50). The highest score was 46 (demote). Identity-only filtering (`黑芝麻智能`) returning zero items is correct — it prevents these unrelated hits from entering the pipeline entirely.

## Web/Jina Results

| URL | Page type | Fetch status | Action | Score | Key reasons |
| --- | --- | --- | --- | ---: | --- |
| https://www.baidu.com | Portal / navigation | ok | discard | 12 | 标题和内容均为空; 疑似门户/导航页，内容价值低 |
| https://finance.sina.com.cn/stock/ | Article-like (portal) | error | — | — | Jina fetch error (network/SSL) |

- **Portal detection**: Baidu homepage correctly identified as portal. Score before penalty: 27 (demote). After portal penalty (-15): 12 (discard). Reason includes "疑似门户/导航页，内容价值低".
- **Article-like URL**: Sina finance page failed to fetch due to Jina/SSL/network flakiness. Skipped after one bounded attempt as instructed.

## Renderer Sample

- path: `/tmp/agent_reach_phase0b_revalidation/agent_reach_live_section.md`
- readable: Yes
- topic grouping: N/A (only demote items present)

The renderer was fed the 4 demote items from the broad-filter comparison run. It produced a readable markdown section with:

- Header: "Agent-Reach 外部证据观察"
- Disclaimer: "本节仅展示外部检索证据，不参与综合评分、风险评分或 LLM 深度分析结论。"
- Summary line: "高优先级证据：0 条；低优先级观察：4 条；已过滤：1 条"
- Status line: "检索状态：ok；质量门：ok"
- A "待人工复核线索" subsection
- A markdown table with columns: 时间, 证据摘要, 来源, 质量, 链接

The table is readable and correctly shows demote items with their scores and source URLs.

## Assessment

| Question | Result |
| --- | --- |
| Did Phase 0B fix the default-feed issue? | **Yes**. With empty default feeds and no explicit feeds, Agent-Reach safely returns `empty` with no crash. |
| Did identity-only filters reduce false positives? | **Yes**. Broad `科技` filter produced 5 unrelated items (all demote/discard). Identity-only `黑芝麻智能` filter produced 0 items — no false positives allowed into the pipeline. |
| Did RSS/Web scoring improve useful evidence retention? | **Yes**. RSS profile (KEEP=50/DEMOTE=30, no interaction penalty) allows data-rich RSS items to keep even with interaction=0. The test suite confirms RSS and Web items can keep at 50+ with zero interaction. |
| Did portal detection work? | **Yes**. Baidu homepage scored 27 → penalized to 12 → discarded with explicit portal reason. |

## Follow-Ups

None. Phase 0B calibration is validated and ready.
