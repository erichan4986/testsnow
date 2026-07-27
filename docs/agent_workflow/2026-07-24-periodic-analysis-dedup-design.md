# Periodic Analysis Dedup Design

## Goal

Reduce repeated contract plumbing and repeated local-cache parsing introduced by
the four accepted annual-analysis batches, without changing any pack schema,
fact admission rule, finding, mapping, pipeline output, or report behavior.

## Baseline

Relative to `c406f77`, the accepted architecture has runtime net `+2422`, tests
net `+2711`, and workflow docs net `+3290`. This cleanup measures its own delta
against `d1be180`; historical architecture code is not rewritten wholesale.

## Batch A: Contract Primitives

Create `scripts/utils/periodic_report_contract_utils.py` with only two strict,
side-effect-free primitives:

1. `finite_decimal(value)` accepts a Decimal-compatible scalar and returns a
   finite `Decimal`, otherwise `None`. Callers remain responsible for commas,
   units, suffixes, regex shape, negative-zero policy, quantization, and source
   precision.
2. `dedupe_filing_evidence(*groups)` deduplicates the existing four-field filing
   evidence identity and returns deterministic sorted dictionaries. It does not
   validate evidence; producer/consumer boundary validation remains local.

MetricSeries, FinancialScan, and ExternalMap replace their equivalent private
helpers. Their different parsing and formatting rules remain separate.

Budget: runtime net must be negative; target `-20` or better. If extraction is
line-positive, stop and keep the existing local helpers.

## Batch B: Per-Run Cache Materialization

Refactor `periodic_report_fulltext_intake_skill.py` around one private cache
material loader. A material row records path, report year, raw text, and either
the structured evidence/fact packs or a deterministic diagnostic code.

The pipeline skill discovers matching files once and reads each file once. It
builds structured evidence once per valid cache. For the latest cache it also
builds the separate `annual_report`/`semiannual_report` display evidence needed
by the fulltext item; this remains distinct from the `annual`/`semiannual`
structured evidence contract.

One private projection returns the six existing outputs: fulltext items, filing
core facts, MetricSeries, FinancialScan, explanation pack, and narrative cards.
Existing public `*_from_cache` functions remain callable and preserve return
types, missing/read-failure behavior, cache selection, diagnostics, and source
ordering. They delegate to the same loader/projections rather than maintaining
independent read/parse implementations.

Budget: target runtime net `<= 0`; hard stop `+30`. A line-neutral change is
acceptable only if tests prove each matching file is read once and structured
evidence is built once per file during one skill run.

## Invariants

- No schema/version/id/formula/threshold changes.
- No reduction of coverage blocks, facts, findings, cards, or diagnostics.
- No changes to report/scoring/risk/target/technical/recommendation eligibility.
- No LLM prompt, network, Knowledge, report renderer, or formal profile changes.
- FinancialScan keeps strict MetricSeries revalidation; ExternalMap keeps exact
  scan rebound and exact evidence mapping.
- Public cache wrappers keep backward-compatible signatures and behavior.

## Failure Modes And Tests

| Failure | Observable symptom | Required test |
|---|---|---|
| Generic decimal helper weakens syntax | malformed or comma-bearing values become accepted in the wrong layer | existing malformed scalar suites plus direct primitive tests |
| Evidence merge drops provenance | fewer/different evidence identities or unstable order | direct identity/order test plus existing pack snapshots |
| Display and structured report types are conflated | fulltext item or filing facts change report type/audit behavior | annual and semiannual wrapper parity tests |
| Latest cache selection changes | a different file supplies item/core/narrative outputs | equal-mtime/path and newer-mtime fixtures |
| A read failure hides valid historical packs | MetricSeries loses valid years or diagnostics | mixed valid/unreadable cache fixture |
| Pipeline still reparses latest cache | repeated reads/evidence builds in one skill run | monkeypatch counters around `Path.read_text` and evidence builder |
| Public wrappers regress | direct callers return a different shape | existing wrapper suite remains green |

## Verification

Run new focused tests first, then all ten architecture test files, CI grep gates,
`git diff --check`, runtime numstat against `d1be180`, and the full offline suite.
Generate a representative fast/local report only after tests are green.
