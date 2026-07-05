# scripts directory guide

This directory contains both production report entrypoints and historical
preview/smoke utilities. Keep the top-level directory stable until callers and
tests are migrated.

## Preferred report entrypoints

- `run_stock_report.py` is the generic single-stock report entrypoint.
- `run_黑芝麻智能.py`, `run_中际旭创.py`, and `run_圣邦股份.py` are stock-specific
  convenience entrypoints and compatibility wrappers.
- `check_report_quality.py` validates generated Markdown reports.

Use `run_stock_report.py --stock <name>` for formal report generation. Use
stock-specific `run_*.py --fast-test` only for focused smoke validation when the
script supports it.

## Standalone or legacy entrypoints

- `xueqiu_monitor_v2.py` is the legacy batch/light monitor path. Do not add new
  deep-report business logic here.
- `run_*技术分析_真实数据.py` scripts are standalone technical-analysis paths.
- There is currently no generic `run_technical_analysis.py` CLI in this
  checkout; use the stock-specific technical-analysis scripts instead.

## Preview and experiment scripts

Files ending in `_preview.py`, plus source-material exploration scripts such as
`wechat_*_preview.py`, live in `scripts/previews/`. They are prototype or manual
validation tools and should not be used as production report entrypoints.

Older curated-external preview experiments that are no longer current were
deleted after the active preview CLIs moved to `scripts/previews/`.

Older maintenance helpers that are not part of the current report path live in
`scripts/archive/legacy_maintenance/`. Keep them callable for manual recovery,
but do not document them as primary entrypoints.

## Smoke scripts

Smoke scripts live in `scripts/smoke/` and are focused integration checks. Keep
them small and deterministic. If a smoke script depends on live network,
browser, CDP, or login state, document that explicitly in the script header.

## High-risk collection scripts

Scripts that touch Xueqiu details, browser automation, CDP, or logged-in
sessions require explicit user authorization before use. This includes:

- `scripts/high_risk/extract_detail.py`
- `scripts/high_risk/extract_detail_via_cdp.py`
- `scripts/high_risk/fetch_xueqiu.py`
- `scripts/high_risk/batch_fetch_quality_posts.py`
- `scripts/high_risk/start_chrome_cdp.sh`
- `scripts/high_risk/start_chrome_cdp.command`
- any future script that controls Chrome, Playwright, or a logged-in session

Prefer cached/list-page data and official or lower-risk APIs for routine report
validation.

## Utilities

Reusable implementation code belongs under `scripts/utils/`. Avoid moving logic
from `utils/` into top-level scripts; top-level scripts should stay thin
orchestration wrappers.
