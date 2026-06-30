# Agent-Reach Phase 0 Runtime Validation Notes

## Status

Accepted with issues

## Environment

- Python: 3.10.12
- Working directory: /Users/erichan/testsnow
- Network available: yes (partial — SSL certificates required post-install)

## Test Results

| Command | Result |
| --- | --- |
| `pytest tests/reporter/test_agent_reach_skills.py` | 52 passed |
| `pytest tests/reporter/test_agent_reach_connector.py` | 15 passed |
| `pytest tests/reporter/test_agent_reach_quality_skill.py` | 26 passed |
| `pytest tests/reporter/test_agent_reach_evidence_renderer.py` | 13 passed |
| `pytest tests/reporter/test_pipeline_integration.py` | 4 passed |
| `pytest tests/reporter/test_synthesis_skills.py` | 4 passed |
| **Total focused tests** | **114 passed, 0 failed** |

## Dependency Probe

| Connector | Registered by default | Available | Reason |
| --- | --- | --- | --- |
| rss | yes | True | feedparser installed |
| web | yes | True | urllib.request available |
| youtube | no | True | yt-dlp and JS runtime found |
| exa_search | no | False | mcporter not found |
| wechat | no | False | mcporter not found |

## Live RSS Results

### Default feeds (黑芝麻智能 / 澜起科技)

| Stock | Fetch status | Items | Keep | Demote | Discard | Key warnings |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 黑芝麻智能 (02533) | empty | 0 | 0 | 0 | 0 | none |
| 澜起科技 (688008) | empty | 0 | 0 | 0 | 0 | none |

**Root cause:** All 3 default RSS feeds failed at network/parser level:
- `chinastock.com.cn` — SSL certificate verify failed
- `sina.com.cn/stock/focus/rss.xml` — XML mismatched tag (not a valid RSS feed)
- `cninfo.com.cn` — empty response / no entries

### Working feeds (validation with known-good feeds)

| Stock | Feed | Fetch status | Items | Keep | Demote | Discard | Key warnings |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| UK | BBC News | ok | 2 | 0 | 2 | 0 | none |
| 科技 | 36kr | ok | 5 | 0 | 5 | 0 | none |

### Notable RSS Items

| Title | Source | URL | Action | Score | Reasons |
| --- | --- | --- | --- | ---: | --- |
| 36氪首发 \| 创维独家投资数千万，这家企业将碳化硅切割损耗降至40微米内 | AgentReach(rss) | 36kr.com | demote | 56 | 包含股票名称; 含 6 个业务关键词; 有URL; 含 1 类数据指标; 含 1 个日期; 标题充实; 内容较长; 标题+内容完整 |
| 8点1氪丨世界杯门票遇冷，近18万张门票待转售；台积电释放涨价信号；但斌回应“被段永平拉黑” | AgentReach(rss) | 36kr.com | demote | 55 | 包含股票名称; 含 9 个业务关键词; 有URL; 含 6 类数据指标; 含 5 个日期; 标题充实; 内容较长; 标题+内容完整; 含 2 个炒作信号; 含 1 个垃圾信息信号 |
| Mis-Teeq on reuniting, UK garage and Alesha Dixon's ad libs | AgentReach(rss) | bbc.com | demote | 35 | 包含股票名称; 有URL; 标题充实; 内容中等; 标题+内容完整 |

## Live Web Results

| URL | Fetch status | Items | Quality action | Warnings |
| --- | --- | ---: | --- | --- |
| https://www.baidu.com | ok | 1 | discard (score=24) | none |
| https://finance.sina.com.cn/stock/ | ok | 1 | discard (score=25) | none |

- **百度**: Jina Reader returned portal/navigation HTML. Discarded because navigation links triggered `SPAM_SIGNALS` ("链接").
- **新浪股票首页**: Large navigation page (68KB). Discarded because dense link text triggered `SPAM_SIGNALS` and `PUMPING_SIGNALS`.

## Quality Gate Strictness Assessment

### Good items discarded or demoted

**Yes — quality gate is too strict for RSS/Web content.**

Example: 36kr article "创维独家投资数千万，这家企业将碳化硅切割损耗降至40微米内" scored **56** (demote) despite containing:
- Concrete investment data (数千万)
- Specific technology metrics (40微米切割损耗)
- Company names (创维, silicon carbide manufacturer)
- Industry keywords (碳化硅, investment)

This item missed the `keep` threshold (60) by 4 points solely due to lacking interaction score and author credentials.

### Demoted items useful as "待人工复核线索"

**Mixed.** The 36kr items are genuinely useful for stock research. The BBC items matched only because the filter term "UK" appeared in unrelated entertainment news — this is a **false positive from relevance scoring**, not a quality issue.

### Main false-negative dimension

1. **Interaction score penalty**: RSS/Web items have `interaction_score=0` by default, losing up to 10 engagement points that social posts would get.
2. **Content richness threshold**: The 50-character "content中等" vs 200-character "内容较长" split is binary. Items with 150 chars of dense data get only 5 points instead of 10.
3. **SPAM/PUMP false positives**: Portal/navigation pages and news headlines with words like "暴涨", "涨停" trigger negative penalties even in legitimate financial reporting contexts.

### Does RSS/Web content require different scoring?

**Yes.** Current scoring was designed for social posts (Twitter/Reddit/Xiaohongshu) where interaction metrics and author presence are strong signals. RSS and Web content should emphasize:
- Data density and specificity
- Source domain credibility
- Presence of financial/operational metrics
- Low weight on interaction score (inherently absent for RSS/Web)

### Suggested future scoring changes

1. **Lower KEEP threshold to 50** for RSS/Web sources, or add source-type-aware thresholds.
2. **Remove/reweight `interaction_score`** for RSS/Web — it is not applicable and unfairly penalizes these sources.
3. **Improve SPAM_SIGNALS context awareness** — "链接" in a navigation bar should not penalize an article. Consider penalizing only when spam signals exceed a density ratio.
4. **Add portal-page detection** — WebConnector reading a site homepage should be flagged differently from an article page.
5. **Add bonus for financial data patterns** in RSS/Web: revenue figures, investment amounts, technical metrics.

## Renderer Sample

- Markdown sample path: `/tmp/agent_reach_phase0_validation/agent_reach_live_section.md`
- Rendered length: 1669 chars
- Placement/readability: Markdown table renders correctly. Time column populated. Excerpts truncated with "...". Pipe characters escaped properly.
- Topic classification issues: No misclassification observed. Demote-only items correctly land in "待人工复核线索" section. Themed sections (产品/量产进展, 客户/定点/订单, etc.) do not appear because no items reached `keep` status.

## Blockers Or Follow-Ups

1. **Replace default RSS feeds**: The 3 hard-coded default feeds are all broken (SSL error, invalid XML, empty response). Need to find stable Chinese finance/news RSS feeds or make feed list fully user-configured.
2. **Quality gate calibration for non-social sources**: The current scoring engine assumes social-post signals (interaction, author presence). RSS/Web need a separate scoring profile or reduced threshold.
3. **Web connector URL validation**: Black Sesame official URL contained a space typo (`black sesame.cn`) — the connector handled it gracefully but the error message was cryptic. Consider adding basic URL validation.
4. **Jina Reader SSL issue**: Direct urllib calls to Jina Reader (`https://r.jina.ai/...`) failed with SSL certificate errors on some runs even after cert update. This may be intermittent network/environment specific.
5. **RSS filter term false positives**: Generic filter terms like "科技" or "UK" match broadly. For production use, filter terms should be more specific (stock_name + code + specific competitors only).
