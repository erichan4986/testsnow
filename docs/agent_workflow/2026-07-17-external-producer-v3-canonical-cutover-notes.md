# External Producer v3 Canonical Cutover Notes

Date: 2026-07-17
Branch: `codex/pipeline-stabilization`
Baseline: `62be6bf`

## Result

Code cutover: **PASS**

Formal local report gate: **PASS WITH INDEPENDENT HK DATA WARNING**

The production pipeline now reads only persisted
`curated_external_argument_pack.v3` files. Legacy viewpoint digest/narrative
runtime files, previews, tests, prompts, configs, and committed caches were
removed. Report-time code does not call the external selector LLM.

## Promoted Packs

| Stock | Production path | SHA-256 |
|---|---|---|
| 中际旭创 | `data/curated_external/argument_packs/zhongjixuchuang.json` | `f123edf40a0a1a77dd210983ecf74e8a87973db5fa52c176db10b0fafeaa3642` |
| 复旦微电 | `data/curated_external/argument_packs/fudan.json` | `3ea0e44eb02bbced3b199d9ca2abe0a1a1114677e7cbc45ac5ffd56eb17e5f22` |
| 黑芝麻智能 | `data/curated_external/argument_packs/heizhima.json` | `0ad4f2f3051a6bf4b00475240a45d43175252880cb934d07a71e37000f25b119` |

All three files are byte-identical to their approved Gate B2 samples.
Reader/display/lint returned `ok` / `ok` / `true` for every stock. Target
topic coverage is four canonical families for every stock.

## Production Configuration

Each stock now has only:

```text
curated_external_argument_pack_synthesis_display
```

No legacy curated external config key remains. A production-config contract
test opens every configured pack with the canonical reader.

## Deleted Legacy Surface

- viewpoint digest and narrative production caches
- narrative composer and old extractor prompt files
- narrative composer runtime and preview
- social viewpoint digest preview
- corresponding compatibility tests and fixtures
- runtime/test references to paragraphs, reasoning cards, topic groups,
  digest builders, fuzzy quote repair, theme profiles, and multipass specs

The source-packet builder remains because it is refresh-time input material,
not a report fallback.

## Report-Gate Narrow Fix

The first sandbox report run exposed two canonical-layout integration defects:

1. multiline source units placed the citation only on the final visible line;
2. the peer/industry disclaimer was a nested heading and its negated
   `已确认事实` wording was scanned as an assertive claim;
3. the quality gate still required the old claim-plus-evidence-block layout.

The renderer now keeps source text unchanged while attaching the same source
refs to every visible paragraph. Peer/industry context is a Preview blockquote,
and the quality gate recognizes the canonical cited source-unit narrative.
The fixes were developed with three failing regression tests, then made green.

## Verification

- focused canonical/report suite: `251 passed`
- full offline suite: `2427 passed, 9 skipped, 59 deselected`
- `tools/ci_grep_gates.sh`: PASS
- legacy runtime/config/test grep: zero matches
- `git diff --check`: clean
- runtime delta versus `62be6bf`: `+1115 / -3835`, net `-2720`

## Sandbox Report Run

Fresh `20260717` Markdown/HTML reports were generated for all three stocks,
but they are not the final acceptance samples. The sandbox could not resolve
the market-data endpoints and Chrome chart process, so technical-data quality
gates failed. Those reports also predate the final citation/layout narrow fix.

The final report gate must therefore run locally after this note, using the
persisted production packs and without invoking the live external selector.

## Local Formal Rerun Result

Claude regenerated all three `20260717` Markdown/HTML reports after the final
renderer change. The report runtime used persisted canonical packs, did not
call the external selector LLM, and did not read legacy digest/narrative files.

- Zhongji: quality/source/prose PASS (prose warnings only)
- Fudan: source/prose PASS; the initial quality failure came from scanning the
  peer/industry Preview suffix as a target-company claim
- Black Sesame: source/prose PASS; the same peer Preview scan produced the
  external framing failure, while separate HK market-data gaps remained

The quality gate was narrowed to scan target-company claims only before the
explicit `同业/行业背景（Preview）` boundary. It still rejects assertive target
claims. The new peer-boundary test and the existing target-assertion test both
pass.

After that checker fix:

- Zhongji `check_report_quality.py`: PASS
- Fudan `check_report_quality.py`: PASS
- Black Sesame external/citation gates: PASS; quality still reports only
  missing daily/weekly/volume/volatility/confidence due unavailable HK market
  data
- focused report tests: `172 passed`
- CI grep gates: PASS
- `git diff --check`: clean
- runtime delta versus `62be6bf`: net `-2715`

Canonical cutover status: **PASS**. The remaining Black Sesame market-data
failure is an independent HK technical-data availability issue.

## Stop Conditions for Local Rerun

- any report runtime calls the external selector LLM;
- any legacy digest/narrative file is read;
- canonical pack status is not `ok`;
- inline citation, source-boundary, or external framing quality errors remain;
- production code/config changes during the read-only report run.
