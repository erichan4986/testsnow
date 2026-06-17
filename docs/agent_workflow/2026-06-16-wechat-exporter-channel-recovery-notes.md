# WeChat Exporter Channel Recovery Notes

Date: 2026-06-16

## Goal

Recover the WeChat official-account article channel as a user-authorized, medium-credit source path.

## Source Review

Reviewed:

- GitHub: `wechat-article/wechat-article-exporter`
- Docs: `https://docs.mptext.top`
- API docs: `https://docs.mptext.top/advanced/api`
- Private deploy docs: `https://docs.mptext.top/advanced/private-deploy`

Key facts:

- Current public site is `https://down.mptext.top`.
- The project supports public website usage, Docker private deployment, Cloudflare deployment, and REST API.
- Docker image: `ghcr.io/wechat-article/wechat-article-exporter:latest`.
- Local dev mode requires Node.js 22+ and yarn.
- REST API requires `X-Auth-Key`, generated after login and valid with the login session.
- API endpoints include account search, article list, article download, account-by-url, and auth-key validation.

## Script Changes

Updated `scripts/deploy_wechat_exporter.sh`:

- Correct repo URL: `https://github.com/wechat-article/wechat-article-exporter.git`.
- Default mode is Docker, using official `ghcr.io` image.
- Source dev mode is explicit via `--dev`.
- Dev mode requires Node.js 22+ and yarn.
- Existing directories are reused by default.
- Destructive reclone requires explicit `--reclone`.
- `--no-start` prepares/prints commands without starting Docker or dev server.
- Usage notes explicitly say login/search/sync/export are user-driven browser actions.

## Safety Boundary

- Do not automate WeChat login.
- Do not store `X-Auth-Key`, cookies, credentials, or exported raw private data in the repo.
- Do not write WeChat output directly into `knowledge/`, `reports/`, or `data/raw/` without a dedicated import/cleaning step.
- Treat imported WeChat articles as medium-credit `professional_observation` unless later verified by high-credit sources.
- WeChat content must not support core facts or scoring by itself.

## Recommended Next Step

Add a separate importer:

- Input: JSON/Markdown exported manually from wechat-article-exporter.
- Output: normalized `wechat_items` or evidence notes.
- Metadata: `source_platform="微信公众号"`, medium credit, `professional_observation`.
- Tests should cover malformed JSON, missing URL/title/content, duplicate URLs, and no credential leakage.

## Verification

```bash
python3 -m pytest tests/reporter/test_deploy_wechat_exporter_script.py -q
bash -n scripts/deploy_wechat_exporter.sh
bash scripts/deploy_wechat_exporter.sh --help
```
