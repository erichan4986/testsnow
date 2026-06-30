# Social / Low-Credit Claim Sprint Design

Date: 2026-06-15

## Goal

Create a safe low-credit claim intake sprint for single-stock reports.

The pipeline already has high/medium-credit evidence:

- official announcements / official pages
- Eastmoney news
- Eastmoney broker research summaries

The missing piece is a reliable low-credit claim pool. This sprint should turn existing local community material and carefully probed social sources into conservative `unverified_claim` notes that `claim_verification` can compare against high-credit evidence.

This sprint is not about making social media part of scoring or final recommendations. It is about building a low-credit input layer that remains explicitly unverified until high-credit sources support it.

## Current Foundation

Existing code already supports much of this:

- `scripts/utils/community_claim_note_writer.py`
  - extracts conservative claims from cached posts
  - writes `source_type: social_discussion`
  - writes `source_credit: 35`
  - writes `verification_status: market_opinion`
  - writes `claim_status: unverified_claim`
- `scripts/smoke_cached_community_claims.py`
  - local-only smoke script
  - reads `data/raw/xueqiu_data_*` or local `knowledge/.../posts/*.md`
  - does not access Xueqiu, Chrome, CDP, Playwright, LLMs, or the network
- `claim_verification.py`
  - already treats `social_discussion` as low credit
  - does not allow social claims to verify other social claims
  - can verify low-credit claims against high-credit official evidence

## Non-Goals

- Do not run Xueqiu detail scraping.
- Do not connect to logged-in Chrome/CDP.
- Do not refresh Zhihu or call LLM curator.
- Do not add social media content to scoring, risk score, EV, technical analysis, or final recommendation.
- Do not let low-credit claims become `confirmed_fact`.
- Do not add a visible social media report section yet.
- Do not modify `KnowledgeSynthesizer` prompts.
- Do not add social media credentials or cookies to the repo.

## Sprint Scope

### Part A: Local Low-Credit Claim Notes

Use the existing local-only cached/community path first.

Targets:

- 黑芝麻智能
- 中简科技
- 圣邦股份

Inputs:

- latest `data/raw/xueqiu_data_*_<stock>.json` if available
- otherwise `knowledge/10-Stocks/<stock>/posts/*.md`

Outputs:

- one conservative note per stock:
  - `knowledge/10-Stocks/<stock>/<YYYYMMDD>-雪球缓存社区claims.md`

Rules:

- default dry-run for smoke
- write only with explicit `--write`
- preserve source URLs as raw metadata, not numbered citations
- every extracted item remains `unverified_claim`
- cap extracted claims to avoid noisy claim floods
- skip technical indicator / pure price-action notes unless they contain explicit verifiable fundamental or event claims

### Part B: Agent-Reach Social Inventory Smoke

Do not integrate social platforms into the report pipeline yet.

Run a capability inventory only:

- Which social/search channels are installed?
- Which can search stock-specific Chinese queries?
- Which return structured text safely?
- Which need login/cookies or are unstable?
- Which are irrelevant for A/H-share single-stock reports?

Candidate channels:

- Weibo via Jina Reader or web search result URLs
- Bilibili via metadata/subtitle when relevant videos exist
- Xiaohongshu only if already installed/logged in locally; no forced login
- Reddit/V2EX generally low relevance for A/H-share names, inventory only
- Twitter/X only if already configured; no credential setup in repo

This inventory must not write report inputs or knowledge notes by default.

Output:

- `docs/agent_workflow/2026-06-15-social-source-inventory.md`

For each source, record:

- availability
- authentication requirement
- query tested
- result count
- content usefulness
- anti-bot / rate-limit risk
- recommended status: `keep_for_later`, `needs_login`, `irrelevant`, `blocked`, or `safe_smoke_only`

### Part C: Optional Generic Social Claim Note Writer

Only implement if Part A exposes a clear need.

Potential change:

- Generalize `community_claim_note_writer.py` so it can render notes from:
  - cached Xueqiu posts
  - local Markdown posts
  - future Agent-Reach social result records

The output contract must stay the same:

- `source_type: social_discussion`
- `source_credit: 35`
- `verification_status: market_opinion`
- `claim_status: unverified_claim`

If this generalization would touch too many files, skip it and keep Part A local-only.

## Runtime Validation

Run local dry-run first:

```bash
python3 scripts/smoke_cached_community_claims.py --stock 黑芝麻智能 --code 02533 --json
python3 scripts/smoke_cached_community_claims.py --stock 中简科技 --code 300777 --json
python3 scripts/smoke_cached_community_claims.py --stock 圣邦股份 --code 300661 --json
```

Then, only after reviewing dry-run counts, write notes:

```bash
python3 scripts/smoke_cached_community_claims.py --stock <stock> --code <code> --write --overwrite --json
```

After note writing:

- run claim verification focused tests
- run claim plan / risk bridge smoke if available
- run one fast-test report for the stock with the most useful low-credit claims

Do not run all three full reports unless the dry-run output shows meaningful claims for all three.

## Required Tests

If code changes are needed:

- cached community smoke remains dry-run by default
- write mode requires explicit `--write`
- generated notes remain `social_discussion`, credit 35, `unverified_claim`
- social claims never verify other social claims
- high-credit official evidence can verify matching social claims
- generic social records, if supported, are capped and sanitized
- no numbered citation markers are written into claim notes

## Acceptance Criteria

- At least one stock produces a useful low-credit claim note from local cached/community material.
- The resulting claim verification plan contains low-credit claims.
- High-credit evidence can support or verify matching claims where applicable.
- Social / low-credit material does not enter scoring, risk scoring, EV, technical analysis, final recommendation, or numbered citations.
- Social source inventory is recorded for future expansion.
- Any platform requiring login/cookies is marked as `needs_login` and not forced.

## Suggested Next Sprint

After this sprint:

- connect useful low-credit claim notes into claim verification runtime more ergonomically
- then evaluate whether social inventory sources should become optional Source Intake adapters
- keep all such adapters disabled by default

## Round 1 Feedback

- **Status**: Run existing smoke first, then Ready to implement
- **R2 Needed**: No (design is safe; execution order should be smoke → write → verify → report)

### Findings by severity

#### Info / Clarifications

1. **Existing `community_claim_note_writer.py` already matches the sprint goal.**
   - It extracts conservative claims from cached posts, writes `source_type: social_discussion`, `source_credit: 35`, `verification_status: market_opinion`, `claim_status: unverified_claim`.
   - `smoke_cached_community_claims.py` is local-only and does not touch Xueqiu/CDP/Chrome/LLMs/network.
   - Therefore **Part A can be implemented by running the existing smoke**, not by writing new extraction code.

2. **Claim verification already supports high-credit verification of low-credit claims.**
   - `claim_verification.py` reads `evidence/` for high/medium-credit claims and stock-level social notes for low-credit claims.
   - Trust direction is one-way: `source_credit >= 80` can verify, `55-79` can support, `< 55` (social) never verifies another claim.
   - `test_claim_verification.py` already covers: social claims stay low-credit, social claims never verify each other, high-credit evidence can verify matching social claims, medium-credit produces `supported`, generic-only matches go to `needs_review`.

3. **Part A scope is well-constrained.**
   - Inputs are latest `data/raw/xueqiu_data_*_<stock>.json` or `knowledge/10-Stocks/<stock>/posts/*.md`.
   - Output is a single conservative note per stock under `knowledge/10-Stocks/<stock>/<YYYYMMDD>-雪球缓存社区claims.md`.
   - Default dry-run with explicit `--write` keeps the repo safe.

#### Minor / Suggestions

4. **The design should explicitly state that Part A does not require code changes.**
   - The existing writer and smoke script already satisfy the acceptance criteria. The sprint task is to *run* the smoke, review output, optionally write notes, and verify through `build_claim_verification_plan`.

5. **Part B (Agent-Reach social inventory) should remain strictly a capability inventory.**
   - The design already says "do not integrate social platforms into the report pipeline yet." Keep it that way.
   - The inventory should produce a read-only markdown doc and should not write knowledge notes or report inputs by default.

6. **Part C (generic social claim note writer) should be deferred.**
   - `community_claim_note_writer.py` already uses a generic-enough internal contract (`source_type`, `source_credit`, `verification_status`, `claim_status`).
   - Generalizing it for future Agent-Reach social records is a follow-up refactor, not required for this sprint.

7. **The runtime validation section should clarify order.**
   - Dry-run all three stocks first.
   - Only if dry-run shows meaningful claims, run `--write` for the most useful stock(s).
   - After writing, run `build_claim_verification_plan` and focused tests; then run **one** fast-test report for the stock with the best claims.

8. **No report-section visibility is correct.**
   - The non-goal "do not add a visible social media report section yet" is consistent with the current renderer architecture. Claim verification summaries already flow into `DeepAnalysisRenderer` via `claim_verification_summary` if configured, but social claims themselves remain invisible as a dedicated section.

### Required task adjustments

- Treat Part A as a **runtime smoke + optional write** task using existing `smoke_cached_community_claims.py`.
- If any code change is needed, it should be limited to:
  - ensuring the smoke script picks up `knowledge/10-Stocks/<stock>/posts/*.md` correctly when no Xueqiu cache exists (already supported via `--posts-dir` and fallback in `load_cached_posts`).
  - possibly extending smoke JSON output to include claim examples for easier review.
- Keep Part B as a read-only inventory; do not wire any social adapter into `source_intake_merge_skill` or `ReportAssemblySkill`.
- Defer Part C until Part A and Part B are complete and a concrete Agent-Reach social record shape exists.

### Missing tests

The existing tests already cover the core invariants. Before writing new code, run and verify:

1. `python3 -m pytest tests/utils/test_community_claim_note_writer.py -q`
2. `python3 -m pytest tests/utils/test_claim_verification.py -q`

If the sprint adds any code changes, add tests for:

- smoke script dry-run default behavior
- smoke script `--write` mode creates a note with correct frontmatter
- smoke script `--write` without `--overwrite` skips existing files
- generated notes remain `social_discussion`, credit 35, `unverified_claim`, `market_opinion`
- no numbered citation markers (`[^n]`, `[n]`) in generated claim notes
- `build_claim_verification_plan` picks up the newly written note and places claims in `low_credit_claims`
- high-credit evidence can verify a matching claim from the newly written note

### Recommended execution order

1. **Run existing smokes dry-run** for all three stocks:
   ```bash
   python3 scripts/smoke_cached_community_claims.py --stock 黑芝麻智能 --code 02533 --json
   python3 scripts/smoke_cached_community_claims.py --stock 中简科技 --code 300777 --json
   python3 scripts/smoke_cached_community_claims.py --stock 圣邦股份 --code 300661 --json
   ```
2. **Review claim counts and example claim texts** from the JSON output.
3. **Run existing focused tests** to confirm invariants still hold.
4. **Write notes only for stock(s) with meaningful claims**:
   ```bash
   python3 scripts/smoke_cached_community_claims.py --stock <stock> --code <code> --write --overwrite --json
   ```
5. **Run claim verification plan** for the written stock(s) and confirm low-credit claims appear and high-credit evidence can verify/support where applicable.
6. **Run one fast-test report** for the stock with the most useful low-credit claims.
7. **Run Agent-Reach social inventory** only after Part A is stable; produce `docs/agent_workflow/2026-06-15-social-source-inventory.md`.

### Blocker

None. The design is safe. The only precondition is running the existing smoke to confirm the existing code produces useful claims for at least one stock before writing notes.
