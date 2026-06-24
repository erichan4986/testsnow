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

If this area is reopened, start with a narrow preview-only helper:

1. Jina Reader public-page preview.
2. V2EX keyword observation preview.
3. Optional YouTube subtitle preview when the user supplies a URL.

Keep Reddit, Bilibili active crawling, Twitter/X, Xiaohongshu, Weibo login flows, and Xueqiu detail pages out of v1.

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
