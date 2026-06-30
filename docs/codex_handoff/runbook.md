# Runbook — 手动运行指南

> 本项目没有单一统一入口，需根据场景选择对应命令。报告试跑和质量验证默认走单股深度报告入口，不走批量 monitor。

---

## 1. 单股深度报告试跑（首选）

**默认股票**：黑芝麻智能  
**入口**：`scripts/run_黑芝麻智能.py`

```bash
cd scripts
python run_黑芝麻智能.py --fast-test
```

- 这是报告 runtime validation 的默认入口。
- `--fast-test` 会跳过知乎采集和 ZhihuCurator/LLM 精编，优先复用本地 `data/raw/report_input_*_黑芝麻智能.json` 中的知乎数据；没有缓存时使用空知乎数据。
- 用于验证深度报告 pipeline、Agent-Reach、Markdown/HTML/PDF 输出和报告质量。
- 不要为了普通报告试跑运行 `xueqiu_monitor_v2.py`。
- 其他单股入口同理：`run_圣邦股份.py`、`run_中简科技.py` 等。
- 只有需要正式刷新知乎/LLM 基本面材料时，才运行不带 `--fast-test` 的完整入口。

### 黑芝麻智能默认证据链

黑芝麻智能当前默认启用：

- Agent-Reach 官方种子源：读取 `config/stocks.json` 中的 `blacksesame.com` 官方 URL，作为高信用外部证据。
- 官方 evidence notes：写入/读取 `knowledge/10-Stocks/黑芝麻智能/evidence/` 下的高信用事实候选。
- 社媒观点补充：当前通过 curated/social viewpoint digest 与 narrative 进入 4.4 Preview；旧的“雪球缓存社区 claims”smoke 路线已退役。
- Claim verification risk bridge：高信用证据验证低信用 claim；未验证 claim 只进入“结构化风险观察（不计分）”，不影响风险评分。

轻量检查入口：

```bash
python scripts/smoke_agent_reach_claim_bridge.py --stock 黑芝麻智能 --json
```

该 smoke 脚本用于调试 Agent-Reach 风险桥，不替代最终报告验收。正式验收仍使用 `cd scripts && python run_黑芝麻智能.py --fast-test`。

---

## 2. 批量轻量报告 / legacy monitor

**入口**：`scripts/xueqiu_monitor_v2.py`

```bash
cd scripts
python xueqiu_monitor_v2.py
```

- 输出：`reports/*.md`、`reports/*.html`、`reports/*.pdf`
- 不包含雪球社区采集（仅使用本地已采集的 `data/raw/*.json`）
- 港股标的会自动跳过技术/资金/新闻采集
- 只在验证批量调度、批量采集或 legacy monitor 自身时使用。
- 后续架构方向：该文件降级为批量轻量报告/采集调度器；深度报告核心能力应沉淀到单股 pipeline。

**带雪球社区采集**（需 Chrome 已登录并开启 CDP）：

```bash
cd scripts
python xueqiu_monitor_v2.py --xueqiu
```

> ⚠️ 雪球反爬严格，运行前务必确认 Chrome CDP 已启动（见下方）

---

## 3. 纯技术形态分析（独立流程，不走主 pipeline）

**入口**：当前为股票专用脚本，仓库内没有统一的 `run_technical_analysis.py` 通用 CLI。

```bash
cd scripts
python run_澜起科技技术分析_真实数据.py
```

示例：

```bash
python run_中简科技技术分析_真实数据.py
```

- 不走主报告 pipeline
- 输出 Markdown 技术报告到 `reports/`

---

## 4. 单股真实数据技术分析

部分股票有独立的技术分析专用脚本：

```bash
cd scripts
python run_中简科技技术分析_真实数据.py
python run_乐鑫科技技术分析_真实数据.py
python run_澜起科技技术分析_真实数据.py
```

---

## 5. 测试

```bash
# 全部测试
pytest

# 特定模块
pytest tests/reporter/test_pipeline_integration.py -v
pytest tests/reporter/test_technical_*.py -v
```

---

## 6. Smoke Test（快速验证链路）

```bash
cd scripts
bash smoke_test.sh
```

- 约 1–2 秒完成
- 验证技术形态分析端到端输出，不依赖外部网络
- 输出样例报告：`reports/smoke_test_report.md`

---

## 7. 启动 Chrome CDP（雪球采集前置条件）

如需批量提取雪球详情页，先启动已登录的 Chrome：

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/chrome_dev"
```

然后运行提取脚本：

```bash
cd scripts
python extract_detail.py --stock 黑芝麻智能 --date YYYYMMDD --cdp-port 9222
python extract_detail.py --all --date YYYYMMDD --cdp-port 9222
```

> `extract_detail_via_cdp.py` 已弃用，保留仅作为兼容性 shim。请使用 `extract_detail.py`。

---

## 8. 目录约定

| 目录 | 用途 |
|------|------|
| `reports/` | Markdown / HTML / PDF 输出 |
| `data/raw/` | 原始采集数据（JSON） |
| `data/processed/` | 处理后数据 |
| `knowledge/10-Stocks/` | Obsidian 知识库输出 |

---

## 9. 环境变量

```bash
export DEEPSEEK_API_KEY="..."
export MOONSHOT_API_KEY="..."
# export DEEPSEEK_MODEL="..."   # 可选
```

---

*本文档供 Codex 及开发者手动运行参考。*
