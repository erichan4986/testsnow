# CODEX Handoff Document

> **Created**: 2026-06-10
> **Project**: testsnow — A-Stock/HK-Stock Deep Analysis Report Generator
> **For**: Codex (or any future AI assistant taking over this codebase)

---

## 1. What This Project Does

This is a **Chinese-language deep analysis report generation system** for A-shares (沪深) and Hong Kong stocks. It produces per-stock Markdown + HTML Dashboard + PDF reports covering:

- **Fundamental Analysis**: Snowball (Xueqiu) community sentiment, Zhihu deep articles, broker research (Eastmoney), company announcements, fund flows, news — synthesized into 5 thematic narratives (industry logic, earnings path, valuation debate, capital flow, event catalysts) via LLM.
- **Technical Analysis**: Pure pandas-based indicator computation (MA/MACD/RSI/BOLL/ATR/ADX/BIAS), trend structure detection, support/resistance zones, K-line patterns, price targets, divergence signals.
- **Composite Output**: Radar chart (5-dimension scoring), bull-bear view chart, valuation comparison chart, risk score with trigger factors.

**Pipeline flow**:
```
Data Collection (mootdx/akshare/Tencent/Xueqiu/Eastmoney)
    → Content Quality Gate + SourceAdapter (normalize to SynthesisItem)
    → KnowledgeSynthesizer (LLM 5-pillar narrative + core facts)
    → ScoringEngine (5-dimension score + EV model + risk score)
    → TechnicalAnalyzer (pandas OHLCV → indicators → signals)
    → ChartGenerator (Plotly → base64 embed)
    → SectionRenderers (8 modular renderers → markdown)
    → ReportAssemblySkill (assemble + HTML Dashboard + PDF)
```

---

## 2. Dependency Installation

```bash
# 1. Python dependencies (11 packages)
pip install -r requirements.txt

# 2. Playwright browsers (required for Xueqiu scraping)
playwright install chromium

# 3. Environment variables (required at runtime)
export DEEPSEEK_API_KEY="..."
export MOONSHOT_API_KEY="..."
# export DEEPSEEK_MODEL="deepseek-chat"  # optional
# export IWENCAI_API_KEY="..."            # optional, for NL research search
```

**Note**: Do NOT install Django/FastAPI/Flask or any large web frameworks. The project intentionally keeps dependencies minimal.

---

## 3. How to Run Report Generation

### Quick single-stock test (recommended for validation)
```bash
cd scripts
python run_黑芝麻智能.py
# Output: reports/黑芝麻智能_report.md + .html
```

Other single-stock scripts:
- `run_圣邦股份.py`
- `run_中简科技技术分析_真实数据.py`
- `run_乐鑫科技技术分析_真实数据.py`
- `run_澜起科技技术分析_真实数据.py`

### Full pipeline (6 stocks, weekly manual run)
```bash
cd scripts
python xueqiu_monitor_v2.py
```

With Snowball community scraping (requires logged-in Chrome + CDP):
```bash
# 1. Start Chrome with remote debugging
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/chrome_dev"

# 2. Run with --xueqiu flag
cd scripts
python xueqiu_monitor_v2.py --xueqiu
```

**HK stocks** (e.g., 黑芝麻智能 `02533`) are auto-skipped for technical/fund-flow/news collection via `is_hk` flag.

---

## 4. How to Run Tests

### Smoke test (fast, no network, ~1-2s)
```bash
cd scripts
bash smoke_test.sh
# Validates technical analysis end-to-end with synthetic data
```

### Unit tests
```bash
# Full suite (some tests require PYTHONPATH set)
PYTHONPATH=/Users/erichan/testsnow pytest

# Specific modules
pytest tests/reporter/test_pipeline_integration.py -v
pytest tests/reporter/test_advanced_technical_e2e.py -v
pytest tests/reporter/test_technical_*.py -v
```

**Known test issue**: 10 test files fail collection with `ModuleNotFoundError: No module named 'scripts'`. Fix: add a `conftest.py` at repo root that adds the project root to `sys.path`, or always run with `PYTHONPATH=/path/to/testsnow`.

---

## 5. Key Files

### Entry Points
| File | Purpose |
|------|---------|
| `scripts/xueqiu_monitor_v2.py` | Main entry: collect → analyze → report → PDF (all 6 stocks) |
| `scripts/run_*.py` | Single-stock quick entry points |
| `scripts/run_technical_analysis.py` | Pure technical analysis (no pipeline, direct K-line fetch) |

### Core Framework
| File | Purpose | Lines |
|------|---------|-------|
| `scripts/utils/skill_pipeline.py` | `SkillContext` + `BaseSkill` + `SkillPipeline` | 106 |
| `scripts/utils/stock_reporter.py` | `PerStockReporter` facade, delegates to pipeline | 172 |
| `scripts/utils/report_skills/__init__.py` | Pipeline builder (11 skills in sequence) | ~50 |

### Data Layer
| File | Purpose |
|------|---------|
| `scripts/utils/data_collector.py` | `TechnicalCollector`, `ReportCollector`, `AnnouncementCollector`, `FundFlowCollector`, `NewsCollector`, `ZhihuCollector` |
| `scripts/utils/fetcher.py` | Xueqiu list-page scraping (Playwright) |
| `scripts/utils/source_adapter.py` | Multi-source normalization to `SynthesisItem` |
| `scripts/utils/content_quality_gate.py` | Hard metrics + LLM content quality scoring |
| `scripts/utils/knowledge_synthesizer.py` | 5-theme LLM synthesis + core facts extraction |

### Analysis & Scoring
| File | Purpose | Lines |
|------|---------|-------|
| `scripts/utils/reporter/technical_analyzer.py` | Technical indicator orchestration | **927** |
| `scripts/utils/reporter/scoring_engine.py` | 5-dimension scoring + EV model + risk | **619** |
| `scripts/utils/reporter/price_target.py` | Price target calculation | ~200 |
| `scripts/utils/reporter/price_adjustment_validator.py` | Dividend/split adjustment validation | ~150 |

### Renderers (SectionRenderer protocol)
| File | Section |
|------|---------|
| `scripts/utils/reporter/sections/executive_summary_renderer.py` | Executive summary + radar chart |
| `scripts/utils/reporter/sections/technical_renderer.py` | Technical analysis (trend/MA/RSI/MACD/BOLL/etc.) |
| `scripts/utils/reporter/sections/valuation_renderer.py` | Valuation comparison |
| `scripts/utils/reporter/sections/deep_analysis_renderer.py` | 5-pillar deep analysis narrative |
| `scripts/utils/reporter/sections/composite_score_renderer.py` | Composite score + bull-bear chart |
| `scripts/utils/reporter/sections/price_target_renderer.py` | Price target + time estimate |
| `scripts/utils/reporter/sections/risk_renderer.py` | Risk score + trigger factors |
| `scripts/utils/reporter/sections/html_dashboard_renderer.py` | HTML dashboard generation |

### Report Skills (Pipeline Steps)
| File | Purpose |
|------|---------|
| `scripts/utils/report_skills/data_skills.py` | Data loading skills |
| `scripts/utils/report_skills/technical_skills.py` | Technical analysis skill |
| `scripts/utils/report_skills/chart_skills.py` | Chart generation skills |
| `scripts/utils/report_skills/synthesis_skills.py` | LLM synthesis skill |
| `scripts/utils/report_skills/assembly_skills.py` | Report assembly skill |
| `scripts/utils/report_skills/analysis_skills.py` | Analysis skills |
| `scripts/utils/report_skills/knowledge_skills.py` | Knowledge persistence skill |

### Config
| File | Purpose |
|------|---------|
| `config/stocks.json` | 6-stock config (code, market, xueqiu_code) |

### Handoff Docs (this directory)
| File | Purpose |
|------|---------|
| `docs/codex_handoff/runbook.md` | Manual run commands reference |
| `docs/codex_handoff/claude_extensions_inventory.md` | Claude Code extension audit |
| `.agents/skills/a-stock-data/SKILL.md` | Data source reference skill |

---

## 6. Current Report Quality Issues

### High Priority
1. **Featured Posts Section (3.x) — Content Repetition**: Same author (e.g., 郭小松驾道) has multiple featured posts with **identical excerpts**. Root cause: Xueqiu list-page summaries are truncated and the author uses identical opening templates. The current `_extract_excerpt()` only captures conclusions, not the argument chain.
   - **Fix needed**: Extract full detail-page content for top-3 posts per stock, rewrite `_extract_excerpt()` to capture premise → evidence → reasoning → conclusion (≥200 chars).

2. **Section Numbering Confusion**: The "3.x 精品帖子深度解读" section has inconsistent numbering with unexplained Chinese characters in parentheses.
   - **Fix needed**: Clean `_featured_posts()` formatting, enforce strict "3.1 / 3.2 / 3.3" numbering.

3. **Excerpt Too Short**: Current excerpts are mostly conclusions without derivation process.
   - **Fix needed**: Refactor `_extract_excerpt()` into `_extract_argument_chain()` that records how the author reached the conclusion.

### Medium Priority
4. **Technical Analysis Report Completeness**: Ensure every report contains: trend background, daily structure, weekly structure, price position, volume confirmation, volatility condition, composite score, divergence warning, key observation levels (support/resistance), trend invalidation condition, trend structure, advisor indicator status.

5. **Fundamental Report Completeness**: Ensure every report contains: executive summary, core facts base, industry logic, earnings path, valuation bull-bear debate, capital flow & catalysts, citation sources.

6. **Risk Disclosure Completeness**: Risk score factor table, industry-specific risks (e.g., loss-making chip companies need special risk factor table), key watch points.

7. **LLM Synthesis Data Integrity**: When modifying `KnowledgeSynthesizer` prompts or synthesis logic, sample output MUST be shown to user for verification before committing. Prompt must include "do not fabricate data, only use the provided information".

---

## 7. Priority Task Order for Codex

When starting work on this codebase, follow this order:

1. **Audit Code & Tests** — Run `pytest`, identify failing tests, understand test coverage gaps. Fix the 10 `ModuleNotFoundError` collection failures first (missing `PYTHONPATH` or `conftest.py`).

2. **Add Quality Assessment** — Add automated checks for report completeness (must-have sections), score consistency (technical conclusion vs scoring engine output must agree), citation traceability (`[^n]` markers map to source list).

3. **Abstract AnalysisResult** — The `technical_analyzer.py` (927 lines) and `scoring_engine.py` (619 lines) are too large. Extract smaller, testable units with clear interfaces. Follow the existing `SectionRenderer` pattern.

4. **Improve Trend/Scoring Logic** — Ensure technical conclusions and scoring engine outputs are mutually consistent. No "trend weakening but score 10/10" conflicts. Add explicit cross-validation.

5. **Improve Chinese Report Templates** — Polish markdown template phrasing for professionalism. Ensure risk sections clearly state trigger factors and加分依据.

6. **Add Tests** — Increase coverage for: `ContentQualityGate`, `SourceAdapter`, `KnowledgeSynthesizer` (with mocked LLM), `ReportAssemblySkill`, and all `SectionRenderers`.

---

## 8. DO NOT Rewrite the Entire Repository

**Strict prohibition**: The codebase is stable and running in production. Changes must be:
- **Focused**: Target one skill, one renderer, or one collector at a time.
- **Tested**: Every change must pass `pytest` and generate at least one sample report (`python run_黑芝麻智能.py`).
- **Incremental**: Preserve existing entry points (`xueqiu_monitor_v2.py`, `run_*.py`, `run_technical_analysis.py`). Do not rename or delete them.
- **Validated**: For LLM prompt changes, show sample output to user for approval before committing.

**Never**:
- Introduce Django/FastAPI/Flask or large frameworks.
- Replace data sources without verifying field compatibility (mootdx for K-lines, Tencent for PE/PB, Eastmoney for research, akshare for news/announcements).
- Modify scoring thresholds or technical algorithms without writing tests first.

---

## 9. Known Issues and TODO

### Test Infrastructure
- [ ] **10 test files fail collection** with `ModuleNotFoundError: No module named 'scripts'`. Need `conftest.py` or `PYTHONPATH` fix.
- [ ] `test_pipeline_integration.py` passes but takes ~25s (slow due to LLM calls or chart generation). Consider mocking.

### Code Quality
- [ ] `scripts/utils/reporter/technical_analyzer.py` is 927 lines — should be slimmed to orchestration layer only.
- [ ] `scripts/utils/reporter/scoring_engine.py` is 619 lines — consider splitting into score calculators.
- [ ] `scripts/utils/reporter/price_target.py:TODO` — KDJ golden cross flag is hardcoded `False`, needs precise KDJ input from analyzer.

### Pending Features (from task tracker)
- [ ] BIAS extreme warning with direction (`evaluate_bias_extreme`)
- [ ] Candle signals at key levels (some tests pending)
- [ ] Support/resistance transformation rules
- [ ] Market resonance placeholder framework
- [ ] Profit-risk filter implementation
- [ ] Sell three-factors framework
- [ ] False rebound / false breakout detection tests

### Data Quality
- [ ] Xueqiu detail-page extraction is manual/CDP-only due to anti-bot. List-page summaries remain truncated.
- [ ] `settings.local.json` contains hardcoded API keys and is NOT in `.gitignore`. **Security risk** — should be added to `.gitignore` immediately.

### Report Quality
- [ ] Featured posts excerpts need argument-chain extraction (see Section 6).
- [ ] Section numbering needs cleanup.
- [ ] Some Phase 3 renderer improvements are pending (`test_risk_renderer.py`, `test_valuation_renderer.py` have import errors).

---

## 10. Suggested First Prompt for Codex

```
You are taking over a Chinese stock deep analysis report generation system.

Your first task: audit the test suite and fix all test collection errors.

Steps:
1. Run `PYTHONPATH=/Users/erichan/testsnow pytest --co` to see which tests fail collection.
2. Identify the root cause (likely missing `conftest.py` or `sys.path` issue).
3. Fix it with minimal changes — do not refactor unrelated code.
4. Run `pytest` again and confirm all tests collect successfully.
5. Run `pytest tests/reporter/test_pipeline_integration.py -v` and confirm it passes.

After tests are green, read `docs/codex_handoff/CODEX_HANDOFF.md` and `AGENTS.md` for project rules.

Do NOT rewrite the entire repository. Make focused, test-validated changes only.
```

---

## Appendix: Repository Skills for Codex

Codex should consult `.agents/skills/a-stock-data/SKILL.md` when working on:
- Adding new data collectors or fetchers
- Debugging empty/NaN values in report sections
- Evaluating new data source reliability
- Reviewing PRs that touch `data_fetcher.py`, `data_collector.py`, or API clients

This skill documents: three-tier data architecture (local TCP / HTTP APIs / scraped), verified field indices for Tencent API, common failure modes, and data source reliability matrix.

---

*End of handoff document. For questions, refer to `docs/codex_handoff/runbook.md` for commands and `AGENTS.md` for project rules.*
