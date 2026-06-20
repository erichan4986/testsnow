# Runbook: Local Report Validation

Purpose: run an existing single-stock report entry and verify output quality without changing code.

## When To Use

Use this when the task is "跑一家看看", "验收报告入口", or "确认报告能生成".

Do not use it for parser implementation, scoring changes, prompt changes, or data-source changes.

## Default Entry

Prefer a single-stock fast-test entry:

```bash
cd scripts && python3 run_黑芝麻智能.py --fast-test
```

For another configured stock, use the matching `scripts/run_*.py --fast-test` entry if it exists.

Avoid `scripts/xueqiu_monitor_v2.py` unless validating batch scheduling or the legacy monitor.

## Safety Rules

- Do not modify code during a validation-only run.
- Do not fetch Xueqiu detail pages.
- Do not start or control a logged-in Chrome/CDP session.
- Do not refresh Zhihu/LLM curator materials unless explicitly requested.
- Report outputs naturally written under `reports/` are acceptable, but do not stage them by default.

## Steps

1. Check whether the stock has a single-stock entry script.
2. Run the fast-test command.
3. Record generated Markdown/HTML/PDF paths and sizes.
4. Run report quality check on the generated Markdown:

```bash
python3 scripts/check_report_quality.py reports/<generated>.md
```

5. Briefly inspect whether the report includes:
   - executive summary;
   - technical trend context;
   - daily and weekly structure;
   - volume and volatility notes;
   - risk section;
   - Source Intake evidence section if relevant.

## Completion Report

Report:

- command run;
- generated files and sizes;
- quality check PASS/WARNING/FAIL;
- major warnings/errors;
- whether PDF generated;
- whether git status contains non-report changes.
