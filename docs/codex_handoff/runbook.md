# Runbook — 手动运行指南

> 本项目没有单一统一入口，需根据场景选择对应命令。

---

## 1. 主流程（6只股票全量生成）

**入口**：`scripts/xueqiu_monitor_v2.py`

```bash
cd scripts
python xueqiu_monitor_v2.py
```

- 输出：`reports/*.md`、`reports/*.html`、`reports/*.pdf`
- 不包含雪球社区采集（仅使用本地已采集的 `data/raw/*.json`）
- 港股标的会自动跳过技术/资金/新闻采集

**带雪球社区采集**（需 Chrome 已登录并开启 CDP）：

```bash
cd scripts
python xueqiu_monitor_v2.py --xueqiu
```

> ⚠️ 雪球反爬严格，运行前务必确认 Chrome CDP 已启动（见下方）

---

## 2. 单股快速测试

**股票**：黑芝麻智能、圣邦股份、中简科技、乐鑫科技、澜起科技

```bash
cd scripts
python run_黑芝麻智能.py
# 或
python run_圣邦股份.py
```

- 直接构造 `PerStockReporter` 并生成报告
- 输出到 `reports/<股票名称>_report.md`

---

## 3. 纯技术形态分析（独立流程，不走主 pipeline）

**入口**：`scripts/run_technical_analysis.py`

```bash
cd scripts
python run_technical_analysis.py <股票名称> <代码> <市场(0=深圳/1=上海)>
```

示例：

```bash
python run_technical_analysis.py 测试股 000001 0
```

- 不依赖雪球数据，直接从 API 拉取 K 线
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
python extract_detail_via_cdp.py
```

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
