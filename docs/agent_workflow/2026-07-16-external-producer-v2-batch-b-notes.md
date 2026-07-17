# External Producer v2 Batch B Gate B1 Notes

## Result

- Gate B1: accepted
- Gate B2: not started
- Production config/cache cutover: not performed
- Network/LLM/report generation: not performed

## Self-review fixes

1. Removed stock/theme-specific extraction rules from the v2 contract; the prompt and validator are entity/topic generic.
2. Locked exact normalized source-quote matching and rejected unknown sources, unsupported numeric/model anchors, ambiguous entities, duplicate baseline claims, unsafe flags, stale versions, and dangling refs.
3. Fixed merged arguments so a fourth evidence unit cannot leak an unused citation.
4. Made malformed non-numeric refs fail closed instead of raising.
5. Preserved explicit legacy operation only while v2 is disabled; when v2 is enabled, any pack failure stops without narrative/digest fallback.
6. Corrected v2 profile routing so external-only material remains `thin_all`; annual-only plus rich external material is `formal_thin_external_rich`; annual plus usable broker material is `formal_medium`.
7. Kept explicit display-only risk inputs independent and added v2 structured cards without changing risk scores.
8. Reused one JSON request/retry helper for legacy and v2 extractors.

## Requirement-test matrix

| Requirement | Implementation | Verification |
|---|---|---|
| Candidate v2, 1-3 exact evidence units | `curated_external_argument_cards.py` | argument-card tests |
| No fuzzy quote repair | v2 extractor + pack validator | full-body extractor tests |
| Canonical persisted pack and fail-closed reader | pack builder/reader | missing/stale/invalid/mismatch/round-trip tests |
| No total argument-card cap | pack builder | nine-card fixture |
| Report reads pack only | `build_curated_external_argument_display()` | display state tests |
| Enabled-v2 failure has no legacy fallback | `SynthesisSkill` | synthesis skill regression test |
| Source Intake plumbing remains opt-in | pipeline/reporter args | reporter config test |
| Freshness uses v2 cards/citations | `evidence_freshness.py` | dated/missing-date tests |
| Display risk remains non-scoring | `assembly_skills.py` | recommendation/assembly test |
| Profile routes formal material, not external-only material | `_build_evidence_profile()` | three profile fixtures |
| Preview default writes one v2 pack in `/tmp` | preview CLI | CLI test |

## Verification

- Focused: `271 passed`
- Deep-analysis/quality/source-boundary downstream: `224 passed`
- `tools/ci_grep_gates.sh`: passed
- `git diff --check`: clean
- Gate B1 runtime delta vs `62be6bf`: `+507/-59`, net `+448`

The B1 temporary limit was calibrated from the measured coexistence implementation to `+450`; this intermediate state must not be merged as the final cutover. Gate B2 retains the final net `+120` hard stop after deleting legacy digest/narrative runtime.

## Stop condition

Gate B2 requires locally generated v2 packs for Zhongji Innolight, Fudan Microelectronics, and Black Sesame Intelligence plus user review of the claims/evidence/entity scope. Until that sample gate passes:

- do not edit `config/stocks.json`;
- do not delete legacy runtime, tests, or caches;
- do not commit or merge this B1 coexistence state.

## Gate B2 sample preparation

No configured LLM API key was available in the Codex shell, so production cutover was not attempted.
Local cached full-text material was used to exercise the validator and report-time reader without
network access.

The first mechanical migration sample was rejected during manual audit: it admitted too much generic
industry background, demonstrating that validator acceptance is not a substitute for extractor topic
selection. A second conservative review set uses exact cached source sentences as both claim and
evidence:

| Stock | Cards | Reader | Review pack |
|---|---:|---|---|
| 中际旭创 | 9 | ok | `/tmp/external-producer-v2-gate-b2/zhongji-curated-external-argument-pack-v2-review.json` |
| 复旦微电 | 8 | ok | `/tmp/external-producer-v2-gate-b2/fudan-curated-external-argument-pack-v2-review.json` |
| 黑芝麻智能 | 8 | ok | `/tmp/external-producer-v2-gate-b2/heizhima-curated-external-argument-pack-v2-review.json` |

All review cards pass exact quote, numeric/model alignment, pack reader, and display lint checks. The
sample audit is at `/tmp/external-producer-v2-gate-b2/manual-review-audit.json`.

Sample review exposed and closed two narrow Gate B1 defects:

1. canonical candidate topic families are now preserved instead of being overwritten by claim keywords;
2. target-name suffix fragments and generic `智能` phrases no longer create false peer entities.

Fresh verification after those fixes: focused `274 passed`, downstream `224 passed`, CI grep gates
passed, `git diff --check` clean, and runtime delta versus `62be6bf` is `+510/-61`, net `+449`.

Gate B2 remains not approved. These offline review packs validate evidence/entity/display boundaries,
but they do not validate the live `external_argument_extractor.v2` prompt. Before production cache or
config changes, run the configured LLM against the prepared source packets, show its accepted/rejected
cards to the user, and obtain explicit sample approval.

## Gate B2 first live run: rejected

The first configured-LLM run used `deepseek-v4-flash` and produced `1/2/2` accepted cards for 中际旭创、
复旦微电、黑芝麻智能. Pack reader and display lint returned `ok`, but content-level review found that
all five cards violated the intended grounding contract:

- target-company effects were inferred from industry or peer-only evidence;
- a 复旦微电 claim added `复旦大学、国盛投资` although those institutions were absent from its evidence;
- a 黑芝麻智能 evidence quote ended at the truncated source tail `黑芝`;
- the resulting two-topic 复旦微电 pack would also fail the current `external_rich` profile threshold.

The live packs are therefore invalid review artifacts and must not be promoted. The prompt and validator
were tightened without relaxing exact quote matching:

1. target claims now require the target in evidence or a target-specific source title;
2. institution names ending in `大学/投资` must appear in evidence;
3. quotes ending at an unterminated source-packet tail are rejected as `source_quote_truncated`;
4. the prompt requires byte-exact self-checking, complete quotes, evidence-grounded entities/causality,
   target scope only from target-bearing evidence, and traversal of every source without an arbitrary cap.

Rebuilding the five old live cards under the tightened validator accepts zero and reports:
`target_not_grounded` (3), `unsupported_claim_anchor` (1), and `source_quote_truncated` (1).
Fresh verification: focused `277 passed`, downstream `224 passed`, CI grep gates passed,
`git diff --check` clean, runtime delta `+515/-65`, net `+450` (the Gate B1 temporary hard limit).

Gate B2 remains blocked pending a second live run and explicit user approval. Exact quote matching must
not be relaxed to improve recall.

## Gate B2 second live run: correctness improved, recall gate still blocked

The second live run generated fresh packs for all three stocks. Reader, display, and lint checks passed,
and the accepted Zhongji/Fudan cards no longer showed the first-run hallucination or entity-binding
failures. The live acceptance counts were `1/2/6`, but the run still cannot approve Gate B2:

- Fudan covered only `financial_quality` and `technology_product`; the local source packet contains an
  explicit target-bearing competitive-landscape passage, so the missing third topic is extractor recall,
  not missing source material.
- Five of six Black Sesame target cards relied on a target-specific article title while their exact
  evidence quote omitted `黑芝麻智能`. That contradicts the prompt's evidence-only entity contract.
- Zhongji still returned only one accepted card because six of seven candidates failed exact quote
  matching. Exact quote validation remains unchanged.

Root-cause tracing showed that `llm-argument-v2` sent all long source packets in one request. Fudan had
22 packets but the model returned only five candidates concentrated in a few sources. The extractor now
processes source packets in deterministic batches of four and merges every returned candidate before the
single validator/dedupe path. This is traversal, not a second selector or a card cap. The v2 pack validator
also requires the target company in the evidence text itself; source title is no longer sufficient for a
target claim. The prompt asks the model to include adjacent complete source sentences when needed to keep
the subject explicit.

New contract tests cover multi-batch candidate retention and rejection of title-only target grounding.
Fresh verification: focused `279 passed`, downstream `224 passed`, CI grep gates passed, `git diff --check`
clean. Runtime delta versus `62be6bf` remains exactly `+450` (`+517/-67`), at but not above the Gate B1
temporary hard limit.

The second live packs are review artifacts and must not be promoted. Gate B2 requires a third live run
with the batched extractor. Approval requires exact evidence, no title-only target claims, and Fudan
retaining at least three useful topic families; do not lower the profile threshold or relax quote matching
to manufacture a pass.
