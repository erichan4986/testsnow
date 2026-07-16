# Annual Producer self-contained admission repair

## Goal

Recover concrete annual-report facts rejected as `not_self_contained` without
restoring legacy notes, adding stock-specific rules, or weakening existing
noise guards.

## Locked behavior

1. A source unit may start a card only when its canonical family predicate can
   prove a complete subject/relation pair. Numeric reported measures and
   concrete product/technology capabilities count as complete relations.
2. A dependent source unit may inherit the family of the immediately preceding
   bundle only when it is source-adjacent, passes every noise guard, and has an
   explicit continuation relation. It never starts a card by itself.
3. Usage remains a routing hint, not proof. A concrete cross-family fact may
   override a table-oriented usage such as `production_sales_inventory_table`.
4. Existing rejection behavior remains for governance/audit text, commitments,
   generic slogans, table/chart fragments, report/listing boilerplate, and OCR
   damage.

## Required fixtures

Positive A-share fixtures cover:

- a product-line composition fact and a dated revenue measure from Fudan;
- AI infrastructure capex growth from Zhongji;
- Wi-Fi/OFDMA capability facts and adjacent ecosystem continuations from
  Espressif;
- EDA product progress from Empyrean;
- an analog-product capability fact from SGMICRO.

Positive HK fixtures cover:

- a dated gross-margin measure;
- installed-device scale and an adjacent AI Agent technology continuation.

Negative fixtures keep zero cards for:

- board/governance procedure text;
- non-compete commitments;
- chart-axis/OCR fragments;
- listing boilerplate;
- generic innovation goals without a delivered product or measured result.

## Stop conditions

- The focused producer suite or downstream pack/material suites regress.
- Any negative fixture is admitted.
- Producer output is not deterministic across processes.
- In the 11-stock temp refresh, a previously preserved concrete fact still
  disappears without equivalent source-text coverage.
- Real Knowledge packs are not refreshed until all preceding checks pass.
