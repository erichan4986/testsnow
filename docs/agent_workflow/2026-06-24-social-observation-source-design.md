# Social Observation Source Design

Date: 2026-06-24

Purpose: record the current Agent-Reach / low-risk social-media smoke status and keep the source boundary explicit before any future implementation.

## Current Smoke Result

Claude Code ran a read-only smoke and wrote `/tmp/social_observation_smoke.md`.

Repository side effects:

- no repository code changes
- no `knowledge/`, `data/raw/`, or `reports/` writes
- no Xueqiu detail-page fetches
- no Chrome/CDP automation
- no LLM calls

Current dirty files were pre-existing work from Source Intake news changes:

- `config/stocks.json`
- `scripts/utils/a_stock_source_intake.py`
- `tests/utils/test_a_stock_source_intake.py`

## Channel Status

| Channel | Status | Notes |
| --- | --- | --- |
| Agent-Reach CLI | Not usable | Binary exists, but `agent-reach doctor` fails with `ModuleNotFoundError: agent_reach.cli`. Do not depend on the wrapper CLI for now. |
| V2EX | Usable but sparse | Public API works. Hot-topic sample had 2 keyword hits out of 10, but quality was mixed and not necessarily investment-specific. |
| Reddit | Not tested | `rdt` is not installed. Per the smoke boundary, no tool installation was attempted. |
| Jina Reader | Usable | Tested URLs returned HTTP 200 and clean Markdown. It can read public pages and some report landing pages. |
| YouTube subtitles | Usable when captions exist | `yt-dlp` can list automatic captions for the tested YouTube video. |
| Bilibili subtitles | Partially usable | `yt-dlp` can parse the page, but the tested video did not expose a usable subtitle list. |

## Boundary

Social observation v1 is not a Knowledge source.

If implemented later, items must be material/display only:

- `source_type`: `social_observation`
- `source_credit`: 45-55 depending on channel
- `verification_status`: `market_discussion` or `secondary_source`
- `knowledge_eligible`: `false`
- `report_eligible`: `true`
- `scoring_eligible`: `false`
- `risk_score_eligible`: `false`

Do not feed social observations into:

- confirmed facts
- fact candidates
- scoring
- risk scoring
- final recommendation logic
- persistent Knowledge notes by default

## Recommended Next Step

Do not implement a broad Agent-Reach wrapper yet.

If this area is reopened, the preferred path is **curated external analysis**, not
open-ended social crawling.  The useful material is likely to come from a small
set of high-quality long-form URLs or exported files, not from broad platform
feeds.

Recommended v1 shape:

1. A preview-only helper tentatively named `curated_external_analysis_pack`.
2. Inputs:
   - user/Claude-curated public article URLs read through Jina Reader;
   - Bilibili / YouTube video URLs with subtitles extracted through `yt-dlp`;
   - local files exported from WeChat article tooling, such as Markdown / HTML /
     text exports;
   - local manually collected industry or company analysis files dropped into a
     per-stock folder.
3. Output:
   - `/tmp/...preview.md` first;
   - optional display-only synthesis items later, after manual review.
4. Metadata:
   - `source_type`: `curated_social_analysis` or `external_analysis`;
   - `source_credit`: 45-65 depending on channel and source quality;
   - `verification_status`: `professional_analysis`, `secondary_source`, or
     `market_discussion`;
   - `knowledge_eligible`: `false` by default;
   - `scoring_eligible`: `false`;
   - `risk_score_eligible`: `false`.

Use this source as synthesis/display material only.  Do not promote it to core
facts or scoring inputs unless an independent high-credit official source later
confirms the claim.

Concrete source guidance:

- Jina Reader: keep for public industry articles, company专题, 36Kr /
  Eastmoney / 同花顺 readable pages, and report landing pages.  This is the
  default low-friction reader.
- Bilibili / YouTube: keep only for explicitly supplied deep-video URLs.  Do not
  run broad video search in v1.
- WeChat articles: evaluate `wechat-article/wechat-article-exporter` as an
  external acquisition tool.  The report system should read exported local
  `md` / `html` / `txt` files rather than logging into WeChat or scraping
  directly.  The exporter appears suitable for stable official-account article
  collection, but credentials / read-count / comment capture must remain outside
  the report pipeline.
- Zhihu: already covered by the existing API path; do not duplicate it here.
- Xueqiu: already covered by the existing Playwright/list-cache path; any detail
  fetch remains subject to the existing logged-in CDP and rate-limit rules.
- Xiaohongshu: potentially valuable for consumer hardware / robotics / channel
  feedback, but not a v1 pipeline source.  Anti-bot controls, `xsec_token`
  coupling, image-heavy posts, OCR needs, and comment quality make it a separate
  smoke-only task.  If tested, use hand-picked note URLs and produce preview-only
  output.
- V2EX / Eastmoney guba / general forums: useful only as weak market discussion
  or claim-risk seed material.  Do not treat them as deep-analysis sources.

Keep Reddit, Bilibili active crawling, Twitter/X, Xiaohongshu, Weibo login
flows, and Xueqiu detail pages out of the main v1 path.

## Stop Conditions

Stop and ask for a new task boundary if any future social observation work requires:

- login cookies
- installed browser automation
- Xueqiu detail-page scraping
- Twitter/X authenticated search
- Xiaohongshu xsec-token handling
- Reddit tool installation
- writing Knowledge notes
- modifying synthesis, scoring, risk, or recommendation logic
