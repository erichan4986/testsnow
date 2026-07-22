# External Producer v4 Batch C: Live Selector and Atomic Cutover

## Goal

Generate three fresh v4 packs from the prepared local source inputs, validate all three before changing production
data, atomically replace the canonical packs, and run report-level acceptance. Do not modify runtime code.

## Worktree

`/Users/erichan/testsnow/.worktrees/annual-producer-v2`

## Inputs

Use these stable local files only:

- `cache/curated_external/v3_1/zhongji-sources.jsonl`
- `cache/curated_external/v3_1/zhongji-baseline.txt`
- `cache/curated_external/v3_1/fudan-sources.jsonl`
- `cache/curated_external/v3_1/fudan-baseline.txt`
- `cache/curated_external/v3_1/heizhima-sources.jsonl`
- `cache/curated_external/v3_1/heizhima-baseline.txt`

The Zhongji comparison source has already been restored from a matching local recovery cache. Confirm source-document
validation reports 5/5, 4/4 and 5/5 valid documents before making any LLM request.

Expected SHA-256 values:

- `zhongji-sources.jsonl`: `33d1994412c58b3e9461424fcef8def0feefb3553b23caceb6a73887f636c518`
- `zhongji-baseline.txt`: `5fb645ba7089d08dae0b6cbf885d4be3b448475830761725aa8d622243be62c1`
- `fudan-sources.jsonl`: `d4f581bc9e83aab0254b7f22b0106cf59034574e392408789568c7e7f9ee1218`
- `fudan-baseline.txt`: `ecf5c9dd3a875e515d9bf5b369926f050bae9e634513059ca0e50d6b9a3d4fb1`
- `heizhima-sources.jsonl`: `e2afbef204e0ad023e7a93f6aa901ab1c1b001f800ed7f1bd45aac04e7012b05`
- `heizhima-baseline.txt`: `d9f0c338ef78803a2592d0f78d4c133729f88a3fd60f49b139a2d3e195d791a8`

## Allowed Changes

- `data/curated_external/argument_packs/zhongjixuchuang.json`
- `data/curated_external/argument_packs/fudan.json`
- `data/curated_external/argument_packs/heizhima.json`
- Natural report outputs under `reports/`
- `docs/agent_workflow/2026-07-22-external-producer-v4-batch-c-claude-notes.md`

## Forbidden

- Do not modify runtime, tests, config, prompts or source JSONL/baseline inputs.
- Do not edit cards, evidence, hashes, offsets, scope or LLM decisions by hand.
- Do not fetch webpages, crawl Xueqiu, or start/control Chrome/CDP.
- Do not copy any existing `/tmp/*external-v4-pilot.json`, migrated pack or skip-peer preflight pack.
- Do not replace even one canonical pack unless all three fresh candidates pass every pre-cutover gate.
- Do not commit or push.

## Execution

1. Require `ANTHROPIC_AUTH_TOKEN`; use model `deepseek-v4-flash`, base URL `https://api.deepseek.com`, and
   `--llm-api-key-env ANTHROPIC_AUTH_TOKEN`. Stop if the key is absent.
2. Run `scripts/previews/curated_external_full_body_viewpoint_preview.py` once per stock using the matching local
   source JSONL and baseline. Write fresh candidates under `/tmp/external-producer-v4-batch-c/`.
3. For every candidate require:
   - schema `curated_external_argument_pack.v4`, status `ready`;
   - `diagnostics.rejected_source_documents` empty;
   - strict reader `ok`, display `ok`, lint `ok`;
   - exact source hashes/offsets and no unused/missing citation;
   - no target fact in `peer_or_industry`, no peer fact in `target`, and no unsupported high-value target claim;
   - nonempty narrative plan covering every card exactly once.
4. Record cards, target/peer counts, families, selector request count and rejected reasons for all three stocks.
5. Only after all three pass, back up the current canonical files under `/tmp`, stage all three new JSON files in
   the canonical directory, then replace the three canonical paths as one all-or-nothing operation.
6. Run:
   - `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_stock_reporter_source_intake_config.py -q -p no:cacheprovider`
   - the focused v4/snapshot/renderer/synthesis suite from the implementation notes;
   - `bash tools/ci_grep_gates.sh` and `git diff --check`.
7. Generate fresh reports with `python3 scripts/run_stock_report.py --stock <股票名> --no-pdf` for 中际旭创,
   复旦微电 and 黑芝麻智能. Run report quality, source-boundary and prose checks for each output. Do not repair
   unrelated network or market-data degradation in this task.
8. Confirm Chapter 4.3 exists, uses `external_argument.v4`, has traceable citations, keeps target and peer context
   separated, and contains no raw metadata or editorial instructions.

## Stop Conditions

- Any source document is degraded or any candidate is not reader/display/lint ready.
- Any target/peer scope leak, unsupported high-value target statement, bad span/hash or citation mismatch.
- Selector output needs manual editing or another LLM request beyond the producer's built-in retry contract.
- Any runtime/test/config/prompt modification appears necessary.
- One candidate fails after another canonical file has been staged: restore all three backups and report blocked.

## Notes

Write `docs/agent_workflow/2026-07-22-external-producer-v4-batch-c-claude-notes.md` with commands, elapsed time,
candidate paths, per-stock diagnostics, validation results, canonical replacement evidence, report paths, quality
gates, git status, blockers/warnings/deviations and final verdict.
