# Chapter 2 Gross-Margin Trend — Codex Review Notes

## Review Authority

- Review type: `user-approved waiver`
- User confirmation: `你自审两遍并修复，然后确认跳过仓库级只读审查并开始实现`
- External Claude Round 1: waived by the user under `AGENTS.md`
- Design, TDD, scope, stop conditions and final verification remain mandatory.

## Verdict

`ok`

## Self Review Round 1

### Finding R1-1: View contract was underspecified

The first design described a rendered row without defining its additive view-model
shape. That could force the renderer to reconstruct origins, markers or percentage-
point changes.

Status: closed. The design now defines one optional `gross_margin` object whose
formatted values, origins, latest change and derivation note are owned by the view.

### Finding R1-2: All-missing behavior was ambiguous

An all-`—` row would add noise and make old caches appear partially broken.

Status: closed. Individual missing years remain `—`, but an all-missing ratio omits
the additive object and row. Existing v1 views remain valid.

## Self Review Round 2

### Finding R2-1: Optional metric could become accidentally required

Appending `gross_margin` to the existing required metric loop would emit
`missing_metric`, potentially alter records and make old caches noisy.

Status: closed. The design requires separate required-amount and optional-ratio
constants and forbids missing-margin diagnostics.

### Finding R2-2: A-share indicator rows do not carry `REPORT_DATE`

Treating `stock_financial_abstract` like statement rows would silently admit no A
share ratios or could select a quarterly column.

Status: closed. The adapter must recognize exact `YYYY1231` columns and construct
source identity from the indicator label and selected date column.

### Finding R2-3: Derived provenance must be row-verifiable

Field names alone do not prove that numerator and denominator came from one row.

Status: closed. The cache source row stores every selected input field/value under
one row hash; the metric cell stores ordered input fields and formula version. The
reader must verify both before emitting a ratio point.

## Remaining Findings

- Blockers: 0
- Must-fix: 0
- Nice-to-have: defer generic ratio support until a second ratio is approved

## Scope And Budget

The five runtime files and corresponding tests are sufficient. MetricSeries and
FinancialScan remain no-change files. Net runtime target `+140`, hard stop `+200`.

## Implementation Ready

`yes`
