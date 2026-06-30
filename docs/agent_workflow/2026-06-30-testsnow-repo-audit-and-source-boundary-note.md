# testsnow repo audit and source-boundary note

## 1. Report source-boundary conclusion

Status after curated external 4.4 launch:

- 4.4 is effectively closed for the current release: validated narrative JSON is read at report runtime, rendered as a flat `### 4.4 精选外部观察（Preview）` section, citation labels are preserved, and display-only isolation gates pass.
- The next quality problem is not 4.4. It is the canonical 4.1-4.3 synthesis layer.
- 4.1-4.3 should move toward a formal-first source boundary:
  - default sources: announcements, annual/interim/quarterly reports, broker research, industry research, authoritative news, and structured market/financial data;
  - social / forum / WeChat / Zhihu material should normally stay in 4.4;
  - a small amount of social material may enter 4.1-4.3 only when cross-verified by formal sources and rendered with explicit attribution;
  - strong claims, precise market-share numbers, policy mandates, customer-lock-in claims, and supply-share estimates need source-tier-aware wording.
- 中际旭创 is the right first sample for this next phase because its 4.1-4.3 currently shows the exact failure mode: high information density but mixed source credibility, repeated themes, and over-assertive language.

## 2. Repo audit snapshot

Commands were read-only. No files were deleted.

High-level size snapshot:

| Path | Size | Notes |
| --- | ---: | --- |
| `data/raw` | 92M | Largest runtime/data surface; includes tracked old raw fixtures, PDFs, screenshots, and ignored generated data. |
| `reports` | 59M | Many report PDFs and historical chart outputs. Most current outputs are ignored, but older generated outputs are tracked. |
| `.git` | 80M | Repository history is already heavy; removing tracked generated assets helps future churn but does not shrink existing clone history without history rewrite. |
| `.worktrees` | 6.3M | Ignored by `.gitignore`; local-only cleanup candidate if not needed. |
| `tests` | 4.9M | 139 Python test files. Broad but not large by disk size; complexity is the issue, not bytes. |
| `scripts` | 4.3M | 47 top-level scripts and 108 utility modules. Many preview/smoke routes reflect historical experiments. |
| `docs/agent_workflow` | 2.5M | 240 tracked workflow notes/design/task files; useful audit trail, but very noisy. |
| `.cache` | 1.8M | 159 tracked cache files despite `.gitignore` ignoring `.cache/`. Strong cleanup candidate. |
| `knowledge` | 1.5M | Tracked Obsidian-style output. Keep only if intentionally part of the product surface. |

Tracked generated / local-state candidates already visible:

- `.cache/**`: 159 tracked files even though `.gitignore` ignores `.cache/`.
- `reports/**`: 17 tracked generated report/chart files, mostly historical Saintbon/Black Sesame outputs.
- `data/raw/**`: 63 tracked raw files, including dated sample data, debug screenshots, and one Excel file.
- `docs/agent_workflow/**`: 240 tracked historical workflow files.
- Root-level local artifacts: two `.docx` files and one root-level `黑芝麻智能_20260526.md`.

## 3. Test-suite shape

Current test surface:

- Total Python test files: 139.
- `tests/reporter`: broad report, renderer, skill, entrypoint, technical, preview, and smoke tests.
- `tests/utils`: helper-level tests for source intake, curated external, periodic report, WeChat, claim verification, credit, and note writers.

Existing marker policy already points in the right direction:

- Normal loop: `python3 -m pytest tests/reporter -m "report_core and not slow and not legacy" -q`
- 4.4 loop: focused curated external / narrative / renderer tests.
- Full suite is intentionally broad and should not be the default inner loop.

Audit interpretation:

- Do not delete tests just because they are numerous.
- First classify tests into active product contracts, preview-tool contracts, smoke/import guards, and legacy route tests.
- Only delete a test after its production code path is either removed or explicitly declared outside the supported product surface.

Likely review buckets:

| Bucket | Examples | Initial action |
| --- | --- | --- |
| Active report core | `test_synthesis_skills.py`, `test_deep_analysis_renderer.py`, scoring/risk/technical renderer tests | Keep. |
| Current 4.4 / source boundary work | curated external, social viewpoint, display lint, source credit tests | Keep for now. |
| Preview/smoke scripts | `*_preview.py`, `smoke_*.py` and matching tests | Review one by one; many may move to `legacy` marker before deletion. |
| Historical Agent-Reach / claim-verification phases | old phase docs and smoke tests | Candidate for archival or legacy marker. |
| Periodic report experimental routes | narrative cards, fulltext preview, structured facts | Keep only if still on roadmap; otherwise mark legacy first. |
| Tracked generated assets | `.cache`, old `reports`, debug screenshots | Strong cleanup candidates after verifying they are not fixtures. |

## 4. Recommended cleanup order

Use small, reviewable commits. Do not combine code cleanup with source-boundary refactor.

1. **Workspace hygiene commit**
   - Keep current 4.4 code/data changes together.
   - Do not include unrelated `AGENTS.md` or generated radar/chart files unless explicitly intended.

2. **Generated/local artifact cleanup**
   - Remove tracked `.cache/**`.
   - Remove tracked old `reports/**` generated outputs if not used by tests.
   - Remove root-level accidental artifacts (`*.docx`, root report markdown) if not product docs.
   - Consider moving required binary/report fixtures under `tests/fixtures/`.

3. **Data fixture cleanup**
   - Review tracked `data/raw/**`.
   - Keep only minimal deterministic fixtures required by tests or fast report runs.
   - Move true fixtures to `tests/fixtures/` or document why they stay in `data/raw`.

4. **Workflow-doc archival**
   - Keep current design/review docs for active work.
   - Move older multi-file phase logs to an archive directory or remove them from the active tree.
   - Preserve only final design/decision docs where useful.

5. **Test taxonomy pass**
   - Add or correct `legacy` / `slow` markers for historical preview/smoke routes.
   - Confirm the fast report-core command covers the product path.
   - Only then delete tests whose underlying route is no longer supported.

6. **Formal-first synthesis design**
   - Start as a separate task after cleanup.
   - Target 中际旭创 first.
   - Add source-tier-aware synthesis constraints and lints before changing report output broadly.

## 5. Stop conditions

- Do not delete source files, tests, or raw fixtures until a read-only dependency check shows no active imports or test references.
- Do not remove any Xueqiu/CDP related guard tests unless the corresponding risky route is removed or formally deprecated.
- Do not mix cleanup with scoring, technical, risk, or KnowledgeSynthesizer prompt changes.
- If a file is generated but currently tracked and used as a fixture, relocate or document it instead of deleting it silently.

## 6. PR1 cleanup action taken

2026-06-30 cleanup pass:

- Removed tracked cache/report/debug generated artifacts from the git index with `git rm --cached`, leaving local files in place.
- Affected tracked paths:
  - `.cache/**`
  - `data/raw/debug/**`
  - `reports/**`
- Added `.gitignore` coverage for:
  - `/data/raw/debug/`
  - `/reports/e2e_test/`
- Deleted one untracked root-level stale report artifact: `黑芝麻智能_20260526.md`.

Post-action checks:

- `git ls-files .cache data/raw/debug reports | wc -l` returned `0`.
- `tools/ci_grep_gates.sh` passed.
- Focused smoke test command passed: `python3 -m pytest tests/test_pytest_marker_contract.py tests/reporter/test_deep_analysis_renderer.py tests/reporter/test_run_stock_report_entry.py -q` (`47 passed`).

## 7. PR2 data/raw fixture split action taken

2026-06-30 data fixture pass:

- Removed tracked historical raw collection / technical experiment artifacts from the git index with `git rm --cached`, leaving local files in place:
  - `data/raw/20260526/**`
  - `data/raw/20260527/**`
  - `data/raw/lanqi_688008_*.csv`
  - `data/raw/lesin_688018_daily_20260608.csv`
- Kept the tracked raw files that have clear live code or test dependencies:
  - `data/raw/黑芝麻智能数据.xlsx` — used by `tests/reporter/test_wind_kline_loader.py` and `scripts/utils/wind_kline_loader.py`.
  - `data/raw/periodic_reports/黑芝麻智能_2025_annual_jina.txt` — annual report fulltext cache; retained until periodic/formal-first source path is reviewed.
  - `data/raw/zhongjian_300777_daily_20260608.csv` — read by `scripts/run_中简科技技术分析_真实数据.py`.
- Added `.gitignore` coverage for:
  - `/data/raw/*.csv`
  - `/data/raw/*.xlsx`
  - `/data/raw/2025*/`

Post-action state:

- `git ls-files data/raw | sort` now shows only the three retained fixture/source files above.

## 8. PR2 test taxonomy action taken

2026-06-30 test taxonomy pass:

- Added `external_material` coverage for the new social viewpoint preview path:
  - `test_social_*`
- Marked the live collector smoke file as `slow`:
  - `tests/test_data_collector.py`
  - Rationale: it exercises real collector paths such as K-line, reports, announcements, fund flow, and news; it should not run in the default development loop.
- Marked older community-claim smoke/audit scripts as `legacy` while keeping them runnable:
  - `test_cached_community_claim_smoke_script.py`
  - `test_claim_intake_audit_flow_script.py`
  - `test_claim_verification_audit_script.py`
  - `test_fresh_social_claim_smoke_script.py`
- Updated `tests/README.md` with the current recommended commands and marker notes.

Post-action checks:

- Marker contract and affected smoke/preview tests passed:
  - `python3 -m pytest tests/test_pytest_marker_contract.py tests/reporter/test_social_viewpoint_digest_preview.py tests/reporter/test_cached_community_claim_smoke_script.py tests/reporter/test_claim_intake_audit_flow_script.py tests/reporter/test_claim_verification_audit_script.py tests/reporter/test_fresh_social_claim_smoke_script.py -q`
  - Result: `31 passed`.
- Fast report-core command passed:
  - `python3 -m pytest tests/reporter -m "report_core and not slow and not legacy" -q`
  - Result: `200 passed, 674 deselected`.
- Broad non-slow collect-only passed:
  - `python3 -m pytest --collect-only tests -m "not slow and not legacy" -q`
  - Result: `1890/1975 tests collected (85 deselected)`.

## 9. PR3 legacy community-claim route removal

2026-06-30 legacy route deletion pass:

- Removed the retired community-claim smoke/audit script layer:
  - `scripts/smoke_cached_community_claims.py`
  - `scripts/smoke_claim_intake_audit_flow.py`
  - `scripts/smoke_claim_verification_audit.py`
  - `scripts/smoke_fresh_social_claims.py`
- Removed their direct reporter tests:
  - `tests/reporter/test_cached_community_claim_smoke_script.py`
  - `tests/reporter/test_claim_intake_audit_flow_script.py`
  - `tests/reporter/test_claim_verification_audit_script.py`
  - `tests/reporter/test_fresh_social_claim_smoke_script.py`
- Removed the helper modules used only by the retired smoke scripts:
  - `scripts/utils/community_claim_note_writer.py`
  - `scripts/utils/fresh_social_claim_intake.py`
- Removed their direct utility tests:
  - `tests/utils/test_community_claim_note_writer.py`
  - `tests/utils/test_fresh_social_claim_intake.py`
- Updated `docs/codex_handoff/runbook.md` so it no longer advertises the retired cached-community smoke route.

Rationale:

- Current 4.4 social/community content now flows through source packets, viewpoint digest, and narrative rendering.
- The deleted scripts were historical June 2026 audit/smoke routes and were not part of the current report pipeline.
- `claim_verification.py` and risk-bridge tests remain in place because they still support active risk observation behavior.
