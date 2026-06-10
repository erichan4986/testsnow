# A-Stock Data Sources for Report Quality

> **Scope**: Data sources used by the stock report generation pipeline.
> **Purpose**: Ensure Codex understands which APIs feed into report sections, their reliability tiers, and common failure modes that affect report quality.

---

## Architecture Overview

The report pipeline consumes data from three tiers:

```
Tier 1 — Local / TCP (most reliable, no IP blocking)
├── mootdx        → K-lines (daily/weekly), finance snapshot, F10 text
└── Tencent API   → Real-time PE/PB/market cap/turnover/limit prices

Tier 2 — HTTP APIs (stable, occasional throttling)
├── Eastmoney reportapi   → Broker research list + PDF URLs + 3-year EPS forecasts
├── akshare               → News, announcements, consensus EPS, fund flow
└── cninfo (via akshare)  → Regulatory disclosure filings

Tier 3 — Community / scraped (quality varies, requires validation)
├── Xueqiu list pages     → Post summaries (truncated, may repeat templates)
├── Zhihu / web articles  → Deep analysis (requires quality gate)
└── PDF text extraction   → Broker research full text
```

**Quality rule**: Never let a downstream renderer display data without verifying the upstream collector returned non-empty, correctly-typed fields. The `ContentQualityGate` and `SourceAdapter` layers exist for this reason.

---

## Tier 1: Local / TCP

### mootdx — K-lines & Financial Snapshot

```python
from mootdx.quotes import Quotes

client = Quotes.factory(market='std')

# K-lines: category 4=daily, 5=weekly, 6=monthly
# market: 0=Shenzhen, 1=Shanghai
klines = client.bars(symbol='688017', category=4, offset=150)
# Returns: open, close, high, low, vol, amount, datetime

# Real-time quotes (46 fields)
quotes = client.quotes(symbol=['688017', '300476'])

# Finance snapshot (37 quarterly fields: EPS, ROE, net profit, revenue, etc.)
fin = client.finance(symbol='688017')

# F10 text categories (9 classes: 最新提示, 公司概况, 财务分析, 股东研究, etc.)
text = client.F10(symbol='688017', name='公司概况')
```

**Report-quality notes**:
- mootdx does NOT provide PE/PB/market cap — fetch those from Tencent.
- For Hong Kong stocks (codes starting with 0, e.g. `02533`), mootdx returns empty — skip technical analysis for HK.
- F10 "股东研究" contains historical top-10 shareholder lists that bloat token count. Truncate to the latest period only.

### Tencent Finance API — Valuation Metrics

```python
import urllib.request

def tencent_quote(codes: list[str]) -> dict[str, dict]:
    prefixed = []
    for c in codes:
        if c.startswith(("6", "9")):
            prefixed.append(f"sh{c}")
        elif c.startswith("8"):
            prefixed.append(f"bj{c}")
        else:
            prefixed.append(f"sz{c}")

    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")

    result = {}
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code = key[2:]
        result[code] = {
            "name":         vals[1],
            "price":        float(vals[3]) if vals[3] else 0,
            "last_close":   float(vals[4]) if vals[4] else 0,
            "change_pct":   float(vals[32]) if vals[32] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "pe_ttm":       float(vals[39]) if vals[39] else 0,
            "mcap_yi":      float(vals[44]) if vals[44] else 0,
            "pb":           float(vals[46]) if vals[46] else 0,
            "limit_up":     float(vals[47]) if vals[47] else 0,
            "limit_down":   float(vals[48]) if vals[48] else 0,
            "pe_static":    float(vals[52]) if vals[52] else 0,
        }
    return result
```

**Critical field-index correction** (verified 2026-05-03):

| Index | Field | Common mistake |
|-------|-------|----------------|
| 39 | PE(TTM) | — |
| 43 | Amplitude% | Often mis-documented as PB |
| 44 | Total market cap (亿) | — |
| 45 | Float market cap (亿) | — |
| 46 | PB | Often mis-documented as index 43 |
| 52 | PE(static) | — |

> **Quality impact**: Misreading PB as amplitude (or vice versa) corrupts the valuation section of the report. Always use the verified index map above.

---

## Tier 2: HTTP APIs

### Eastmoney Research API — Broker Reports

```python
import requests
import re
import time

REPORT_API = "https://reportapi.eastmoney.com/report/list"
PDF_TPL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def eastmoney_reports(code: str, max_pages: int = 5) -> list[dict]:
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Referer": "https://data.eastmoney.com/"})
    all_records = []
    for page in range(1, max_pages + 1):
        params = {
            "industryCode": "*", "pageSize": "100", "industry": "*",
            "rating": "*", "ratingChange": "*",
            "beginTime": "2000-01-01", "endTime": "2030-01-01",
            "pageNo": str(page), "fields": "", "qType": "0",
            "orgCode": "", "code": code, "rcode": "",
            "p": str(page), "pageNum": str(page), "pageNumber": str(page),
        }
        r = session.get(REPORT_API, params=params, timeout=30)
        d = r.json()
        rows = d.get("data") or []
        if not rows:
            break
        all_records.extend(rows)
        if page >= (d.get("TotalPage", 1) or 1):
            break
        time.sleep(0.3)
    return all_records
```

**Key fields for report quality**:

| Field | Meaning | Report usage |
|-------|---------|--------------|
| `publishDate` | Report date | Citation dating |
| `orgSName` | Broker name | Source attribution |
| `predictThisYearEps` | Current-year EPS forecast | Consensus validation |
| `predictNextYearEps` | Next-year EPS forecast | Growth-rate calculation |
| `emRatingName` | Rating (Buy/Overweight/Hold) | Sentiment signal |
| `infoCode` | PDF URL component | Deep-link to full report |

> **Quality impact**: If `predictThisYearEps` is missing, the scoring engine cannot compute forward PE. Always check for `None` before feeding into `scoring_engine.py`.

### akshare — Consensus EPS

```python
import akshare as ak

df = ak.stock_profit_forecast_ths(symbol="688017", indicator="预测年报每股收益")
# Columns: 年度, 预测机构数, 最小值, 均值, 最大值, 行业平均数
# "均值" = consensus EPS
# "预测机构数" < 3 → flag as low-coverage in the report
```

> **Quality impact**: Small-cap / ST / newly-listed stocks often return empty DataFrames. The report must handle this gracefully (e.g. "机构覆盖不足，一致预期数据缺失"), not silently drop the valuation section.

### akshare — News & Announcements

```python
import akshare as ak

# Individual stock news (Eastmoney source)
df_news = ak.stock_news_em(symbol="688017")

# CLS (Cai Lian She) flash news — minute-level updates
df_cls = ak.stock_info_global_cls()

# Eastmoney global news
df_global = ak.stock_info_global_em()

# Regulatory announcements (cninfo)
df_announce = ak.stock_zh_a_disclosure_report_cninfo(
    symbol="688017",
    market="沪市"   # "沪市" for 6xxx, "深市" for 0/3xxx, "北交所" for 8xxx
)
```

> **Quality impact**: `stock_news_em` content may contain promotional language. Run through `ContentQualityGate` before including in the synthesis narrative.

---

## Tier 3: Community / Scraped

### Xueqiu List Pages

- **What we get**: Post summaries (truncated, often ending with "...")
- **Quality risk**: Same author may use identical opening templates across multiple posts. The list-page summary looks identical even when full content differs.
- **Mitigation**: Use CDP-based detail-page extraction for featured posts only. Never bulk-scrape detail pages without logged-in Chrome and 3-5s intervals.

### PDF Text Extraction (Broker Research)

- Download URL template: `https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf`
- Must include header `Referer: https://data.eastmoney.com/`
- Use `pdfplumber` or `PyMuPDF` for text extraction
- **Quality risk**: Tables and charts are lost in plain-text extraction. Flag "图表数据需人工核对" in the report when numerical tables are detected.

---

## Data Source Reliability Matrix

| Priority | Source | Use in Report | Reliability | IP Block Risk |
|----------|--------|---------------|-------------|---------------|
| 1 | mootdx (TCP) | K-lines, finance snapshot, F10 | Very high | None |
| 2 | Tencent API | PE, PB, market cap, turnover | High | Low |
| 3 | akshare | News, announcements, consensus EPS | High | Medium (Eastmoney throttle) |
| 4 | Eastmoney reportapi | Broker research list + PDF | High | Low |
| 5 | Xueqiu list pages | Community sentiment | Medium | **High** (anti-bot) |
| 6 | Xueqiu detail pages | Full post content | Medium | **Very high** (account ban risk) |

---

## Common Failure Modes & Report Impact

| Symptom | Likely Cause | Report Impact | Mitigation |
|---------|--------------|---------------|------------|
| `stock_profit_forecast_ths` returns empty | No analyst coverage | Valuation section missing consensus | Flag "覆盖不足" instead of skipping silently |
| Tencent API returns garbled text | Missing `decode("gbk")` | All valuation metrics corrupt | Always decode GBK; validate numeric fields |
| Eastmoney PDF 403 | Missing `Referer` header | Cannot download full research | Add `Referer: https://data.eastmoney.com/` |
| mootdx `finance()` returns NaN | Stock suspended or delisted | Financial snapshot blank | Check `is_hk` flag; skip finance for HK stocks |
| Xueqiu summaries identical | Same author's template opening | Featured-posts section shows duplicates | Extract detail-page full content for top-3 posts |
| F10 text >20k tokens | Historical shareholder lists bloating | LLM context overflow / cost spike | Truncate to latest period only |

---

## Environment Variables

The following keys are required by the pipeline. They are read from the environment at runtime; never hard-code them.

```bash
# Required
export DEEPSEEK_API_KEY="..."
export MOONSHOT_API_KEY="..."

# Optional
export DEEPSEEK_MODEL="deepseek-chat"
export IWENCAI_API_KEY="..."      # Only for NL semantic research search
export IWENCAI_BASE_URL="https://openapi.iwencai.com"
```

---

## When to Consult This Skill

- Adding a new data collector or fetcher module
- Debugging empty/NaN values in report sections
- Evaluating whether a new data source is reliable enough for production reports
- Reviewing PRs that touch `data_fetcher.py`, `data_collector.py`, or any API client

---

> **Note to Codex**: This is a repository-level skill. Global A-stock data skills may also exist at `~/.agents/skills/a-stock-data/`. Prefer this repository copy when working on report-generation code, because it is scoped to the actual sources used by the pipeline.
