# Claude Code Task: Xueqiu CDP Detail Extraction Consolidation

> **Design**: `docs/agent_workflow/2026-06-11-xueqiu-cdp-detail-extraction-design.md`
> **Notes Output**: `docs/agent_workflow/2026-06-11-xueqiu-cdp-detail-extraction-claude-notes.md`
> **Local Runner**: user runs this prompt from their local trusted terminal

You are implementing the locked design. Stay within scope. Use test-first development: write the failing tests, run them and observe the expected failure, then implement the minimal code to pass.

---

## 0. Local Command

The user is running this task from an already-open local Claude Code session. Record the actual local command or interaction mode in the notes output file.

---

## 1. Objective

Consolidate Xueqiu detail-page extraction so the canonical `scripts/extract_detail.py` path works with `DetailPageFetcher(cdp_url=...)`, the orphan `scripts/extract_detail_via_cdp.py` becomes a safe deprecation-only shim, and the runbook points users to the canonical command.

No real Xueqiu pages should be fetched. No Chrome/Playwright browser should be started by tests.

---

## 2. Allowed Changes

You may modify:

- `scripts/utils/detail_page_fetcher.py` — add `cdp_url` constructor support; defer CDP connection until `_init_browser()`; optionally add public `close()` while preserving `_close_browser()`.
- `scripts/extract_detail.py` — refactor `main(argv=None)` and use public `close()` if added.
- `scripts/extract_detail_via_cdp.py` — replace hard-coded extraction logic with deprecation-only CLI shim.
- `scripts/batch_fetch_quality_posts.py` — only if needed after `DetailPageFetcher(cdp_url=...)` support lands.
- `tests/utils/test_detail_page_fetcher.py` — add browser-free constructor/cleanup tests.
- `tests/utils/test_extract_detail_cli.py` — add browser-free CLI tests.
- `docs/codex_handoff/runbook.md` — replace orphan script instructions with canonical command.
- `docs/agent_workflow/2026-06-11-xueqiu-cdp-detail-extraction-claude-notes.md` — write concise execution notes.

---

## 3. Do Not Modify

Do not modify:

- `scripts/xueqiu_monitor_v2.py`
- `scripts/run_*.py`
- `scripts/run_technical_analysis.py`
- `scripts/utils/reporter/**`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/reporter/scoring_engine.py`
- `data/raw/**`
- `knowledge/10-Stocks/**`
- `reports/**`

Do not change data sources, scoring thresholds, technical-analysis algorithms, LLM prompts, report rendering, or generated report output.

---

## 4. Implementation Tasks

### Task 1: Add Failing Tests For `DetailPageFetcher(cdp_url=...)`

Modify `tests/utils/test_detail_page_fetcher.py`.

Add tests equivalent to:

```python
def test_accepts_cdp_url_without_connecting():
    fetcher = DetailPageFetcher(
        vault_base=Path("/tmp/test-vault"),
        cdp_url="http://localhost:9222",
    )

    assert fetcher.cdp_url == "http://localhost:9222"
    assert fetcher._context is None
    assert fetcher._playwright is None


def test_close_is_public_alias_for_browser_cleanup():
    fetcher = DetailPageFetcher(vault_base=Path("/tmp/test-vault"))

    assert hasattr(fetcher, "close")
    fetcher.close()
```

Run:

```bash
pytest tests/utils/test_detail_page_fetcher.py -v
```

Expected before implementation:

- `test_accepts_cdp_url_without_connecting` fails with unexpected keyword argument `cdp_url`.
- `test_close_is_public_alias_for_browser_cleanup` fails because `close` does not exist.

Record the failing output summary in the notes file.

### Task 2: Implement `DetailPageFetcher` CDP Support

Modify `scripts/utils/detail_page_fetcher.py`.

Required behavior:

- `__init__` accepts `cdp_url: Optional[str] = None`.
- Construction does not connect to a browser.
- `_init_browser()` uses `self._playwright.chromium.connect_over_cdp(self.cdp_url)` when `cdp_url` is provided.
- CDP mode reuses the first existing browser context when available, otherwise creates a new context from the connected browser.
- Non-CDP behavior remains unchanged.
- Add public `close()` that performs current cleanup.
- Keep `_close_browser()` as a compatibility alias calling `close()`.

Implementation sketch:

```python
def __init__(..., cdp_url: Optional[str] = None, ...):
    self.cdp_url = cdp_url
    ...
    self._browser = None

def _init_browser(self):
    from playwright.sync_api import sync_playwright
    self._playwright = sync_playwright().start()

    if self.cdp_url:
        self._browser = self._playwright.chromium.connect_over_cdp(self.cdp_url)
        self._context = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context(...)
        self._context.set_viewport_size(...)
        self._context.add_init_script(...)
        logger.info("Browser connected over CDP: %s", self.cdp_url)
        return

    # existing launch_persistent_context / launch behavior
```

Make cleanup robust:

```python
def close(self):
    if self._context:
        self._context.close()
        self._context = None
    if self._browser:
        self._browser.close()
        self._browser = None
    if self._playwright:
        self._playwright.stop()
        self._playwright = None

def _close_browser(self):
    self.close()
```

If closing a CDP-connected context/browser would close the user's Chrome session unexpectedly, preserve safer current behavior and document the choice in notes. Do not over-engineer.

Run:

```bash
pytest tests/utils/test_detail_page_fetcher.py -v
```

Expected after implementation: pass.

### Task 3: Refactor `extract_detail.py` For Testable CLI

Modify `scripts/extract_detail.py`.

Required behavior:

- Change `def main():` to `def main(argv=None):`.
- Change `parser.parse_args()` to `parser.parse_args(argv)`.
- If public `fetcher.close()` exists, use it in `finally` instead of `fetcher._close_browser()`.
- Preserve existing CLI behavior.

At bottom:

```python
if __name__ == "__main__":
    main()
```

Do not run extraction commands that would start a browser.

### Task 4: Replace `extract_detail_via_cdp.py` With Deprecation-Only Shim

Modify `scripts/extract_detail_via_cdp.py`.

Required behavior:

- Remove hard-coded `TARGET_URLS`, Playwright extraction logic, and output write logic.
- Add minimal `argparse` so `python scripts/extract_detail_via_cdp.py --help` works.
- Running the script without `--help` prints migration guidance and exits non-zero.
- The guidance points to `extract_detail.py` commands:

```bash
cd scripts
python extract_detail.py --stock 黑芝麻智能 --date YYYYMMDD --cdp-port 9222
python extract_detail.py --all --date YYYYMMDD --cdp-port 9222
```

Suggested structure:

```python
#!/usr/bin/env python3
"""Deprecated compatibility shim for Xueqiu detail extraction."""

import argparse
import sys


MESSAGE = """..."""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Deprecated: use extract_detail.py for Xueqiu detail extraction.",
        epilog=MESSAGE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.parse_args(argv)
    print(MESSAGE)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

### Task 5: Add Browser-Free CLI Tests

Create `tests/utils/test_extract_detail_cli.py`.

Tests should not start Playwright or fetch pages.

Add tests equivalent to:

```python
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run_script(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_extract_detail_help_does_not_start_browser():
    result = run_script("scripts/extract_detail.py", "--help")

    assert result.returncode == 0
    assert "雪球帖子详情页批量提取" in result.stdout


def test_deprecated_cdp_script_help_works():
    result = run_script("scripts/extract_detail_via_cdp.py", "--help")

    assert result.returncode == 0
    assert "Deprecated" in result.stdout or "deprecated" in result.stdout
    assert "extract_detail.py" in result.stdout


def test_deprecated_cdp_script_exits_nonzero_with_guidance():
    result = run_script("scripts/extract_detail_via_cdp.py")

    assert result.returncode == 1
    assert "extract_detail.py" in result.stdout
    assert "--cdp-port 9222" in result.stdout
```

Run:

```bash
pytest tests/utils/test_extract_detail_cli.py -v
```

Expected after implementation: pass.

### Task 6: Update Runbook

Modify `docs/codex_handoff/runbook.md`.

Replace the old instruction:

```bash
cd scripts
python extract_detail_via_cdp.py
```

With canonical examples:

```bash
cd scripts
python extract_detail.py --stock 黑芝麻智能 --date YYYYMMDD --cdp-port 9222
python extract_detail.py --all --date YYYYMMDD --cdp-port 9222
```

Mention that `extract_detail_via_cdp.py` is deprecated and retained only as a compatibility shim.

### Task 7: Verification

Run:

```bash
pytest tests/utils/test_detail_page_fetcher.py -v
pytest tests/utils/test_extract_detail_cli.py -v
python scripts/extract_detail.py --help
python scripts/extract_detail_via_cdp.py --help
```

Do not run commands that fetch real Xueqiu pages or start Chrome/Playwright.

If the focused tests pass and the full suite is affordable in your local environment, run:

```bash
pytest
```

If full `pytest` fails due unrelated existing worktree changes, record the failure summary and do not broaden the task.

---

## 5. Stop Conditions

Stop and write the blocker into the notes file if:

- Implementing requires modifying files outside the allowed list.
- A test requires real Xueqiu access, Chrome startup, or Playwright browser launch.
- Existing code contradicts the design in a way not covered by this task.
- You discover `DetailPageFetcher(cdp_url=...)` has additional call sites not covered here.
- You need to change report generation, scoring, LLM prompts, or data sources.

---

## 6. Required Notes Format

Write `docs/agent_workflow/2026-06-11-xueqiu-cdp-detail-extraction-claude-notes.md`:

```markdown
# Claude Notes: Xueqiu CDP Detail Extraction Consolidation

## Summary

- 

## Files Changed

| File | Change |
|------|--------|
|  |  |

## Red-Green Evidence

| Test | Red Result | Green Result |
|------|------------|--------------|
|  |  |  |

## Tests Run

| Command | Result | Notes |
|---------|--------|-------|
|  | Pass/Fail/Not Run |  |

## Local Command Used

Describe how the user triggered this local Claude Code task.

## Deviations From Task

- None.

## Blockers Or Follow-Ups

- None.
```
