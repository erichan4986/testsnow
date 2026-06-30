# Xueqiu CDP Detail Extraction Consolidation Design

> **Date**: 2026-06-11
> **Owner**: Codex
> **Status**: Under Claude Review

---

## 1. Goal

Consolidate the current Xueqiu detail-page extraction path so the project has one safe, documented, testable way to fetch full featured-post content through a logged-in Chrome CDP session.

The immediate goal is not to fetch more pages. The goal is to remove ambiguity around `scripts/extract_detail_via_cdp.py`, preserve the mature `scripts/extract_detail.py` + `DetailPageFetcher` path, and make the remaining workflow harder to misuse.

---

## 2. Non-Goals

- Do not batch-fetch Xueqiu detail pages during implementation or tests.
- Do not add a new crawler or data source.
- Do not change `scripts/xueqiu_monitor_v2.py` or report generation behavior in this task.
- Do not modify scoring, technical analysis, LLM synthesis, or report renderer logic.
- Do not delete an entry point unless the user explicitly approves deletion after design review.

---

## 3. Current Context

| Area | Current Behavior | Relevant Files |
|------|------------------|----------------|
| Main detail extraction CLI | Reads `data/raw/xueqiu_data_{date}_{stock}.json`, filters `_track == "featured"`, uses `DetailPageFetcher`, writes Vault post markdown | `scripts/extract_detail.py` |
| Mature fetcher | Playwright-based detail fetcher with delays, login checks, Vault writer, and existing unit tests | `scripts/utils/detail_page_fetcher.py`, `tests/utils/test_detail_page_fetcher.py` |
| Batch quality-post fetch CLI | Also instantiates `DetailPageFetcher(cdp_url=...)`; currently affected by the same constructor mismatch as `extract_detail.py` | `scripts/batch_fetch_quality_posts.py` |
| Orphan CDP script | Hard-coded URLs and output date; top comment says it is orphaned and `extract_detail.py` covers the same function | `scripts/extract_detail_via_cdp.py` |
| Existing audit | Explicitly records `extract_detail_via_cdp.py` as an orphan retained only as standalone CLI | `docs/codex_handoff/repo_audit.md` |
| Xueqiu safety rules | Detail pages require logged-in Chrome/CDP and 3-5 second request spacing | `AGENTS.md`, `CLAUDE.md`, `docs/agent_workflow/README.md` |

---

## 4. Proposed Design

### 4.1 Recommended Approach

Keep `scripts/extract_detail.py` as the canonical detail extraction command and turn `scripts/extract_detail_via_cdp.py` into a deprecation-only shim.

The deprecated shim should not contain hard-coded target URLs and should not run extraction logic. It should print a clear migration message that points to:

```bash
cd scripts
python extract_detail.py --stock 黑芝麻智能 --date YYYYMMDD --cdp-port 9222
python extract_detail.py --all --date YYYYMMDD --cdp-port 9222
```

This avoids maintaining two separate detail extraction implementations.

This task must also fix the current constructor mismatch: `extract_detail.py` and `batch_fetch_quality_posts.py` pass `cdp_url` to `DetailPageFetcher`, but `DetailPageFetcher.__init__` does not currently accept that parameter.

### 4.2 Components

| Component | Responsibility | Inputs | Outputs |
|-----------|----------------|--------|---------|
| `extract_detail.py` | Canonical CLI for detail extraction | stock/all, date, CDP port | Vault post markdown files |
| `DetailPageFetcher` | Browser extraction and Vault writing | featured post metadata | successful URL list |
| `extract_detail_via_cdp.py` | Deprecation surface | existing user invocation | exits with migration guidance |
| Tests | Protect CLI/helper behavior without network | unit-level command/format checks | deterministic pass/fail |

### 4.3 Data Flow

```text
data/raw/xueqiu_data_{date}_{stock}.json
  -> extract_detail.py filters featured posts
  -> DetailPageFetcher connects to logged-in browser
  -> knowledge/10-Stocks/{stock}/posts/{post_id}.md
```

`extract_detail_via_cdp.py` should no longer define a separate hard-coded target list or a separate extraction algorithm.

`DetailPageFetcher` should support both modes:

```text
cdp_url provided
  -> sync_playwright().start()
  -> chromium.connect_over_cdp(cdp_url)
  -> use existing browser context/page

cdp_url omitted
  -> existing launch_persistent_context / launch behavior
```

CDP URL validation should be deferred until connection time so constructing the class and running CLI `--help` never requires a browser.

### 4.4 Error Handling And Fallbacks

- Missing raw list file: log warning and skip stock.
- No featured posts: log and skip stock.
- CDP/browser failure: fail visibly and stop without retrying aggressively.
- Existing Vault file: keep current skip behavior.
- `extract_detail_via_cdp.py` invocation: explain the canonical command and exit non-zero without fetching pages.
- Invalid or unreachable `cdp_url`: fail visibly at browser initialization; do not retry aggressively.

---

## 5. Files Expected To Change

| File | Change Type | Reason |
|------|-------------|--------|
| `scripts/extract_detail_via_cdp.py` | Modify | Remove duplicate hard-coded extraction logic; make it a compatibility wrapper or explicit deprecation shim |
| `scripts/utils/detail_page_fetcher.py` | Modify | Add `cdp_url` constructor support and CDP browser initialization path; optionally expose public `close()` while preserving `_close_browser()` compatibility |
| `scripts/extract_detail.py` | Modify | Refactor to `main(argv=None)` for CLI testing; continue using canonical fetcher |
| `scripts/batch_fetch_quality_posts.py` | Maybe modify | Only if needed after `DetailPageFetcher(cdp_url=...)` support lands |
| `tests/utils/test_detail_page_fetcher.py` | Modify | Add constructor contract coverage for `cdp_url` without connecting to a browser |
| `tests/utils/test_extract_detail_cli.py` | Add | Test CLI help/deprecation behavior without network, following existing `tests/utils/` layout |
| `docs/codex_handoff/runbook.md` | Modify | Replace orphan script invocation with canonical `extract_detail.py` command |

---

## 6. Files That Must Not Change

| File/Area | Reason |
|-----------|--------|
| `scripts/xueqiu_monitor_v2.py` | Main weekly entry point; not needed for this consolidation |
| `scripts/utils/reporter/**` | Report output behavior is out of scope |
| `scripts/utils/knowledge_synthesizer.py` | No prompt or LLM behavior changes in this task |
| `scripts/utils/reporter/scoring_engine.py` | Scoring is unrelated |
| `data/raw/**`, `knowledge/10-Stocks/**`, `reports/**` | Implementation and tests must not generate or mutate real collected/report data |

---

## 7. Data And Reporting Constraints

- No real Xueqiu detail pages should be fetched during implementation or automated tests.
- Any future manual fetch requires a logged-in Chrome CDP session controlled by the user.
- Request spacing must remain at least 3-5 seconds; current canonical CLI uses `delay_range=(3, 5)` and `request_interval=5`.
- The task must preserve Vault output format compatibility for existing post markdown files.
- Since no LLM synthesis changes are proposed, no user sample-output confirmation is required for this task.

---

## 8. Acceptance Gates

### Tests

At minimum:

```bash
pytest tests/utils/test_detail_page_fetcher.py -v
```

If CLI tests are added:

```bash
pytest tests/utils/test_extract_detail_cli.py -v
```

Full test suite is preferred if the diff touches shared import paths:

```bash
pytest
```

### Manual Command Check

The canonical command help must work without starting a browser:

```bash
python scripts/extract_detail.py --help
python scripts/extract_detail_via_cdp.py --help
```

Constructor contract check must not connect to a browser:

```python
DetailPageFetcher(vault_base=Path("/tmp/test-vault"), cdp_url="http://localhost:9222")
```

### Report Generation

Not required. This task only consolidates the manual detail extraction CLI and does not affect report rendering.

### Manual Review

- Xueqiu safety language remains explicit.
- `extract_detail_via_cdp.py` no longer contains hard-coded URLs or extraction logic.
- Existing `extract_detail.py` workflow remains available.
- `DetailPageFetcher(cdp_url=...)` construction works without a browser and browser connection is deferred until `fetch_posts()`.
- No generated data files are produced by tests.

---

## 9. Open Questions

| Question | Owner | Decision |
|----------|-------|----------|
| Should `extract_detail_via_cdp.py` remain as a delegating wrapper or become a deprecation message only? | Codex after Round 1 | Deprecation-only shim |
| Should `extract_detail.py` accept `argv` for easier tests, or should tests invoke subprocess help only? | Codex after Round 1 | Add `main(argv=None)` |
| Should the runbook keep mentioning `extract_detail_via_cdp.py` after consolidation? | Codex after Round 1 | No; update to canonical `extract_detail.py` command |
| Should `DetailPageFetcher` validate `cdp_url` format at construction or defer until connection time? | Codex after Round 1 | Defer until connection time |
| Is user approval required to delete `extract_detail_via_cdp.py` entirely? | Codex after Round 1 | Do not delete; keep deprecation shim to preserve entry point |

---

## 10. Claude Review Log

### Round 1 Feedback

Status: Ready with changes

Findings:
- [Severity: High] `scripts/extract_detail.py:78` passes `cdp_url` to `DetailPageFetcher`, but `scripts/utils/detail_page_fetcher.py:31` does not accept this parameter. The canonical CDP path is currently a `TypeError` at runtime. The design must add CDP connection support to the fetcher, not just assume it exists.
- [Severity: Medium] `docs/codex_handoff/runbook.md:120` still instructs users to run `python extract_detail_via_cdp.py`. This contradicts the consolidation goal and should be updated to the canonical `extract_detail.py` command. Add `runbook.md` to the files-expected-to-change list.
- [Severity: Medium] `scripts/extract_detail_via_cdp.py` has no CLI arguments and hardcodes URLs/output paths. A "delegating wrapper" is impractical because there is no meaningful argument mapping. A deprecation-only shim is safer and simpler.
- [Severity: Low] `scripts/extract_detail.py:113` calls `fetcher._close_browser()`, a private method. Long-term this should be a public cleanup method.
- [Severity: Low] The proposed `tests/scripts/` directory does not exist in the current test layout (`tests/utils/`, `tests/reporter/`). The design should align with existing conventions or explicitly create the directory.

Recommendations:
1. Add `cdp_url: Optional[str] = None` to `DetailPageFetcher.__init__` and branch `_init_browser()` to use `chromium.connect_over_cdp(cdp_url)` when provided; otherwise keep existing persistent-context behavior. Move `detail_page_fetcher.py` from "Maybe modify" to "Modify" with this explicit reason.
2. Make `extract_detail_via_cdp.py` a deprecation-only shim that prints the canonical command and exits with code 1, removing all hardcoded URLs and extraction logic.
3. Refactor `extract_detail.py` to `def main(argv=None): ... parser.parse_args(argv)` for easier unit testing without subprocess.
4. Add `docs/codex_handoff/runbook.md` to "Files Expected To Change" and replace the `extract_detail_via_cdp.py` invocation example with `extract_detail.py --stock <name> --date YYYYMMDD --cdp-port 9222`.
5. Place the new CLI test in `tests/utils/test_extract_detail_cli.py` or document the intended new `tests/scripts/` convention.
6. Add an acceptance gate that instantiates `DetailPageFetcher(cdp_url=...)` without connecting, to prove the parameter contract exists and does not require a running browser.

Open Questions:
- Should `DetailPageFetcher` validate `cdp_url` format at construction or defer until connection time? (Deferral keeps `--help` fast.)
- Is user approval required to delete `extract_detail_via_cdp.py` entirely, or is a deprecation shim sufficient? AGENTS.md says not to delete existing entry points, but the file is already explicitly orphan and unused.

### Codex Response To Round 1

- Accepted the high-severity constructor mismatch. The design now explicitly requires `DetailPageFetcher(cdp_url=...)` support and notes that both `extract_detail.py` and `batch_fetch_quality_posts.py` are affected.
- Accepted the runbook finding. `docs/codex_handoff/runbook.md` is now a required change, not optional.
- Accepted the deprecation-only direction for `extract_detail_via_cdp.py`. Delegation is not useful because the orphan script has hard-coded stock URL lists and no meaningful CLI argument contract.
- Accepted `main(argv=None)` in `extract_detail.py` to keep CLI tests in-process and browser-free.
- Accepted the test-layout feedback. New CLI tests should live under `tests/utils/`.
- Partially accepted the private cleanup concern. Implementation may add a public `close()` method and preserve `_close_browser()` as a compatibility alias, but this should stay secondary to the CDP constructor fix.
- Decided to defer `cdp_url` validation until connection time and to keep `extract_detail_via_cdp.py` as a deprecation shim rather than deleting it.

### Round 2 Feedback

Status: Ready to implement

Findings:
- [Severity: Low] The acceptance gate `python scripts/extract_detail_via_cdp.py --help` assumes the deprecation shim parses arguments, but the current orphan script has no argument parser. The shim should add a minimal `argparse` or the manual check should drop `--help`.
- [Severity: Low] `extract_detail.py:113` calls `fetcher._close_browser()`. The design says "optionally expose public `close()`". If a public `close()` is added, `extract_detail.py` should also be updated to use it. This is within scope but not explicitly required.
- No blockers.

### Final Implementation Readiness

Ready to implement. The revised design resolves the `DetailPageFetcher(cdp_url=...)` constructor mismatch, limits changes to the agreed file list, and acceptance gates can be satisfied without a running browser or real Xueqiu access.
