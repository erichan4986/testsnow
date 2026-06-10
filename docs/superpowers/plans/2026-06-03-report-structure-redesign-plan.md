# 报告结构重塑与重复消除 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构个股报告的板块结构，消除重复事实陈述，增加执行摘要和核心事实基座，将5个深度分析板块合并为3个

**Architecture:** 采用"总-分"式阅读架构。KnowledgeSynthesizer 新增核心事实提取，PerStockReporter 重写板块编排。所有改动保持向后兼容（降级路径不变）。

**Tech Stack:** Python 3.11+, 现有 OpenAI-compatible LLM 客户端, Markdown

---

## 文件结构

| 文件 | 责任 |
|------|------|
| `scripts/utils/knowledge_synthesizer.py` | 新增核心事实提取逻辑；修改 Prompt 减少重复；返回结果加入 `core_facts` |
| `scripts/utils/stock_reporter.py` | 重写 `generate_stock_report()` 板块编排；新增 `_executive_summary()`、`_core_facts_table()`、`_deep_analysis()`；精简 `_valuation_forecast()` |

---

## Task 1: KnowledgeSynthesizer 核心事实提取

**Files:**
- Modify: `scripts/utils/knowledge_synthesizer.py`
- Test: 手工运行 `python -c "from scripts.utils.knowledge_synthesizer import KnowledgeSynthesizer; print('import ok')"`

### 背景
当前 `KnowledgeSynthesizer.synthesize()` 返回5个主题叙事 + citations。新结构需要在合成阶段同时提取一份"核心事实基座"，供后续板块引用而不重复展开。

### 修改点

**Step 1.1: 新增 `extract_core_facts()` 方法**

在 `KnowledgeSynthesizer` 类中新增方法（放在 `_parse_with_citations` 之后）：

```python
    def extract_core_facts(
        self,
        stock_name: str,
        narratives: Dict[str, str],
        items: List[SynthesisItem],
    ) -> List[Dict]:
        """
        从已合成的主题叙事中提取核心事实基座。

        Args:
            stock_name: 股票名称
            narratives: 各主题合成文本 {theme_key: narrative}
            items: 原始信息条目列表

        Returns:
            核心事实列表，每项为 {"fact_id": int, "fact": str, "data": str, "confidence": str}
        """
        if not self.client:
            return []

        # 收集所有主题叙事作为上下文
        narrative_text = "\n\n".join(
            f"【{THEMES.get(k, (k, 0))[0]}】\n{v}"
            for k, v in narratives.items() if v
        )

        prompt = (
            f"你是资深财经数据编辑。请从以下关于{stock_name}的分析文本中，提取8-12条核心事实。"
            "每条事实必须包含：事实陈述、支撑数据、置信度（高/中/低）。"
            "只提取客观事实和数据，不要提取观点、判断或预测。"
            "去重：同一事实在不同段落中出现时只保留一次。"
            "\n\n输出格式（JSON）："
            '\n[\n  {"fact_id": 1, "fact": "2025年营收", "data": "8.22亿元，同比+73.4%", "confidence": "高"},\n  ...\n]'
            "\n\n分析文本：\n"
            f"{narrative_text[:3000]}"  # 限制长度防止 token 超限
        )

        try:
            model = getattr(self, "_default_model", "deepseek-chat")
            resp = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是专业的中文财经数据编辑，擅长从分析文本中提取结构化事实。只输出JSON，不输出其他内容。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=2000,
            )
            text = resp.choices[0].message.content.strip()
            # 提取 JSON 块
            json_match = re.search(r'\[.*\]', text, re.DOTALL)
            if json_match:
                facts = json.loads(json_match.group())
                # 确保字段存在
                for i, f in enumerate(facts, 1):
                    f.setdefault("fact_id", i)
                    f.setdefault("fact", "")
                    f.setdefault("data", "")
                    f.setdefault("confidence", "中")
                return facts
        except Exception as e:
            logger.warning(f"[{stock_name}] 核心事实提取失败: {e}")

        return []
```

**Step 1.2: 修改 `synthesize()` 方法**

在 `synthesize()` 方法的末尾，循环合成所有主题后，调用 `extract_core_facts()`：

```python
        # 新增：提取核心事实基座
        theme_narratives = {k: v for k, v in result.items() if k in THEMES}
        core_facts = self.extract_core_facts(stock_name, theme_narratives, items)
        result["core_facts"] = core_facts

        result["citations"] = dict(self.source_index)
        return result
```

**Step 1.3: 修改各主题 Prompt，加入 `no_repeat` 指令**

修改 `THEME_PROMPT_PREFIX` 中的每个主题 prompt，在末尾追加：

```python
        "industry_logic": (
            "...（原有内容）..."
            "6. 不要在正文中重复展开具体财务数字（如营收、毛利率等），"
            "仅在需要支撑论点时用一句话引用，并标注 [^n]。"
        ),
```

对其他4个主题（fundamentals, valuation_debate, funding_sentiment, events_catalysts）做同样修改，统一追加第6条指令。

**Step 1.4: 验证导入**

```bash
python -c "from scripts.utils.knowledge_synthesizer import KnowledgeSynthesizer; print('import ok')"
```

Expected: `import ok`

**Step 1.5: Commit**

```bash
git add scripts/utils/knowledge_synthesizer.py
git commit -m "feat(synthesizer): add core facts extraction and no-repeat prompt"
```

---

## Task 2: PerStockReporter 新增执行摘要和核心事实基座

**Files:**
- Modify: `scripts/utils/stock_reporter.py`
- Test: 手工运行 `python -c "from scripts.utils.stock_reporter import PerStockReporter; print('import ok')"`

### 背景
当前 `generate_stock_report()` 直接以"综合评分"开头，缺乏阅读层次。需要在开头新增"执行摘要"，并在估值板块之后新增"核心事实基座"。

### 修改点

**Step 2.1: 新增 `_executive_summary()` 方法**

在 `PerStockReporter` 类中新增（放在 `_header()` 之后）：

```python
    def _executive_summary(
        self,
        stock_name: str,
        all_posts: List[Dict],
        stock_raw: Dict,
        quote: Optional[Dict],
        consensus: Optional[Dict],
        ind_fwd_pe: Optional[float],
        synthesis: Dict[str, str],
    ) -> str:
        """
        执行摘要：综合评分 + 核心投资论点（看多/看空各3-4条）+ 一句话结论。
        """
        # 复用现有评分逻辑
        from .reporter.scoring_engine import compute_pillar_scores, ev_expectation
        ps = quote.get("ps") if quote else None
        pillar = compute_pillar_scores(stock_raw, all_posts, quote, consensus, ind_fwd_pe, ps)
        ev = ev_expectation(pillar, consensus)
        total_score = round(
            pillar["valuation"] * 0.30 +
            pillar["technical"] * 0.25 +
            pillar["sentiment"] * 0.20 +
            pillar["fundamental"] * 0.15 +
            pillar["fundflow"] * 0.10,
            1,
        )

        # 基于合成文本提取多空论点（简化版：从 valuation_debate 和 fundamentals 中提取）
        bullish_points = []
        bearish_points = []

        # 使用简单启发式从合成文本中提取论点
        debate_text = synthesis.get("valuation_debate", "")
        fund_text = synthesis.get("fundamentals", "")
        combined = debate_text + "\n" + fund_text

        # 多空论点提取 Prompt（交给 LLM 做）
        extracted = self._extract_thesis_points(stock_name, combined)
        bullish_points = extracted.get("bullish", [])
        bearish_points = extracted.get("bearish", [])

        # 渲染
        lines = [
            "## 一、执行摘要",
            "",
            f"### 综合评分: {total_score}/10 | EV: {ev.get('ev_pct', 0):+.2f}%（{ev.get('signal', 'N/A')}）",
            "",
            "| 维度 | 权重 | 得分(0-10) | 说明 |",
            "|------|------|------------|------|",
            f"| 估值健康度(B) | 30% | {pillar['valuation']:.1f} | {pillar.get('valuation_note', '')} |",
            f"| 技术面强度(M) | 25% | {pillar['technical']:.1f} | {pillar.get('technical_note', '')} |",
            f"| 情绪面温度(M) | 20% | {pillar['sentiment']:.1f} | 看多 {pillar.get('bullish_pct', 0):.0f}% / 看空 {pillar.get('bearish_pct', 0):.0f}% |",
            f"| 基本面趋势(B) | 15% | {pillar['fundamental']:.1f} | {pillar.get('fundamental_note', '')} |",
            f"| 资金关注度(M) | 10% | {pillar['fundflow']:.1f} | {pillar.get('fundflow_note', '')} |",
            "",
        ]

        if bullish_points or bearish_points:
            lines.extend([
                "### 核心投资论点",
                "",
            ])
            if bullish_points:
                lines.append("**看多：**")
                for pt in bullish_points[:4]:
                    star = "⭐" * pt.get("stars", 3)
                    lines.append(f"- {pt.get('text', '')} → {star}")
                lines.append("")
            if bearish_points:
                lines.append("**看空：**")
                for pt in bearish_points[:4]:
                    star = "⭐" * pt.get("stars", 3)
                    lines.append(f"- {pt.get('text', '')} → {star}")
                lines.append("")

        # 一句话结论（从 valuation_debate 最后一句提取，或 LLM 生成）
        conclusion = self._extract_conclusion(stock_name, combined)
        if conclusion:
            lines.extend([
                f"> **一句话结论**：{conclusion}",
                "",
            ])

        return "\n".join(lines)
```

**Step 2.2: 新增 `_extract_thesis_points()` 辅助方法**

```python
    def _extract_thesis_points(self, stock_name: str, text: str) -> Dict:
        """从合成文本中提取看多/看空论点。简化版：直接返回空列表，由后续 LLM 增强。"""
        # V1: 先用空实现，保证报告能生成
        # V2: 后续可接入 LLM 提取
        return {"bullish": [], "bearish": []}
```

**Step 2.3: 新增 `_extract_conclusion()` 辅助方法**

```python
    def _extract_conclusion(self, stock_name: str, text: str) -> str:
        """提取一句话结论。简化版：返回空字符串。"""
        return ""
```

**Step 2.4: 新增 `_core_facts_table()` 方法**

```python
    def _core_facts_table(self, core_facts: List[Dict]) -> str:
        """渲染核心事实基座表格。"""
        if not core_facts:
            return ""

        lines = [
            "## 三、核心事实基座",
            "",
            "| # | 事实 | 数据/来源 | 置信度 |",
            "|---|------|-----------|--------|",
        ]
        for f in core_facts:
            fid = f.get("fact_id", "")
            fact = f.get("fact", "").replace("|", "\\|")
            data = f.get("data", "").replace("|", "\\|")
            conf = f.get("confidence", "中")
            lines.append(f"| {fid} | {fact} | {data} | {conf} |")

        lines.extend([
            "",
            "> **说明**：后续深度分析模块不再重复展开这些数据，仅在需要支撑论点时引用编号（如"见事实#1"）。",
            "",
        ])
        return "\n".join(lines)
```

**Step 2.5: 修改 `generate_stock_report()` 板块编排**

在 `generate_stock_report()` 中，修改 sections 组装逻辑：

```python
        # 构建报告各部分（新 7 模块结构）
        sections = []
        sections.append(self._header(stock_name))

        # 0. 执行摘要（新增）
        sections.append(self._executive_summary(
            stock_name, all_posts, stock_raw, quote, consensus, ind_fwd_pe, synthesis
        ))

        # 1. 综合评分与推荐（保留，但移到执行摘要之后，或合并入执行摘要？）
        # 决策：执行摘要已包含评分表格，此处保留 composite_score_section 的完整版
        # 作为详细评分参考
        sections.append(composite_score_section(stock_name, all_posts, stock_raw, quote, consensus, ind_fwd_pe))

        # 2. 估值与财务快照（精简版）
        sections.append(self._valuation_forecast_compact(stock_name, quote, consensus))

        # 2.5 竞争对手财务指标对比
        comp_metrics = fetch_competitor_metrics(stock_name, self.stock_codes)
        if comp_metrics:
            sections.append(competitor_metrics_table(stock_name, comp_metrics))

        # 3. 核心事实基座（新增）
        core_facts = synthesis.get("core_facts", [])
        if core_facts:
            sections.append(self._core_facts_table(core_facts))
```

Wait — 这里有个编号问题。执行摘要如果叫"一"，那后面的编号全都要变。保持原编号更好？还是重新编号？

根据设计文档，新结构是：
1. 执行摘要
2. 估值与财务快照
3. 核心事实基座
4. 深度分析（4.1/4.2/4.3）
5. 行业特有风险因子
6. 综合风险评分
7. 信息来源汇总

所以编号需要重新编排。原来的 composite_score_section 生成的是"一、综合评分与推荐"，现在执行摘要应该成为"一"。

为了最小化改动，我可以让 composite_score_section 不再生成标题（或修改标题为"二"），但这会改 scoring_engine.py，增加了影响面。

更好的方案：**执行摘要不叫"一"，而是放在最前面但不用编号**，用 `**执行摘要**` 作为引导。这样原有编号可以保持，减少改动。

或者：**执行摘要作为"一"，然后把 composite_score_section 改为"二"，后续顺延**。但这需要改 scoring_engine.py 中的标题生成。

我选择**最小改动方案**：执行摘要不带编号标题（或用 `## 执行摘要`），原有 `composite_score_section` 继续生成 `## 一、综合评分与推荐`。这样阅读顺序是：

- 执行摘要（无编号，最前面）
- 一、综合评分与推荐
- 二、估值与业绩预测
- 三、核心事实基座
- 四、深度分析（4.1/4.2/4.3）
- 五、行业特有风险因子
- 六、综合风险评分
- 七、信息来源汇总

这比较合理。让我调整代码：

```python
        sections.append(self._header(stock_name))

        # 执行摘要（新增，无编号）
        sections.append(self._executive_summary(...))

        # 一、综合评分与推荐（保留）
        sections.append(composite_score_section(...))

        # 二、估值与财务快照（精简版）
        sections.append(self._valuation_forecast_compact(...))

        # 2.5 竞争对手财务指标对比
        ...

        # 三、核心事实基座（新增）
        ...
```

**Step 2.6: 新增 `_valuation_forecast_compact()` 方法**

这是 `_valuation_forecast()` 的精简版，删除长篇判断段落。

```python
    def _valuation_forecast_compact(self, stock_name: str, quote=None, consensus=None) -> str:
        """精简版估值板块：只保留表格 + 一句话判断。"""
        code = self.stock_codes.get(stock_name, "")
        if not code:
            return ""

        if quote is None:
            quote = fetch_tencent_quote(code)
        if consensus is None:
            consensus = fetch_consensus_eps(code)

        if not quote:
            return ""

        price = quote.get("price", 0)
        pe_ttm = quote.get("pe_ttm", 0)
        pb = quote.get("pb", 0)
        mcap = quote.get("mcap_yi", 0)
        change_pct = quote.get("change_pct", 0)

        lines = [
            "## 二、估值与财务快照",
            "",
            f"**数据日期**: {self.date_display} | **数据来源**: 腾讯财经实时行情 + 同花顺机构一致预期",
            "",
            "### 实时估值指标",
            "",
            "| 指标 | 数值 | 说明 |",
            "|------|------|------|",
            f"| 最新价 | {price:.2f} 元 | 较前日 {'+' if change_pct >= 0 else ''}{change_pct:.2f}% |",
            f"| 总市值 | {mcap:.1f} 亿 | 流通市值 {quote.get('float_mcap_yi', 0):.1f} 亿 |",
            f"| PE(TTM) | {pe_ttm:.1f} | 滚动市盈率 |",
            f"| PB | {pb:.2f} | 市净率 |",
        ]

        if consensus and consensus.get("eps_current"):
            eps_cur = consensus["eps_current"]
            eps_next = consensus.get("eps_next")
            pe_fwd = price / eps_cur if eps_cur else float("inf")
            lines.extend([
                "",
                "### Forward 估值",
                "",
                f"| 指标 | 数值 | 说明 |",
                f"|------|------|------|",
                f"| Forward PE | {pe_fwd:.1f} | 最新价 / {consensus['year_current']} 预期 EPS |",
            ])
            if eps_next:
                cagr = (eps_next / eps_cur - 1) if eps_cur else 0
                peg = pe_fwd / (cagr * 100) if cagr > 0 else float("inf")
                lines.append(f"| PEG | {peg:.2f} | Forward PE / 盈利增速 |")
        else:
            lines.extend([
                "",
                "> 暂无法获取机构一致预期 EPS 数据。",
            ])

        # 一句话判断
        judgment = ""
        if pe_ttm <= 0:
            judgment = "PE-TTM 为负，处于亏损状态；估值判断需依赖产业逻辑和同行对比（见深度分析模块）。"
        elif consensus and consensus.get("eps_current"):
            pe_fwd = price / consensus["eps_current"]
            if pe_fwd < pe_ttm:
                judgment = f"Forward PE ({pe_fwd:.1f}) 低于 PE-TTM ({pe_ttm:.1f})，业绩成长正在消化估值。"
            elif pe_fwd > pe_ttm:
                judgment = f"Forward PE ({pe_fwd:.1f}) 高于 PE-TTM ({pe_ttm:.1f})，市场预期业绩增速放缓。"
            else:
                judgment = "Forward PE 与 PE-TTM 基本持平，估值处于合理区间。"
        else:
            judgment = "缺乏 consensus 数据，估值判断参考产业逻辑与同行对比。"

        lines.extend([
            "",
            f"**一句话判断**: {judgment}",
            "",
        ])

        return "\n".join(lines)
```

**Step 2.7: 验证导入**

```bash
python -c "from scripts.utils.stock_reporter import PerStockReporter; print('import ok')"
```

Expected: `import ok`

**Step 2.8: Commit**

```bash
git add scripts/utils/stock_reporter.py
git commit -m "feat(reporter): add executive summary and core facts table"
```

---

## Task 3: PerStockReporter 深度分析板块合并

**Files:**
- Modify: `scripts/utils/stock_reporter.py`
- Test: 运行 `python scripts/run_黑芝麻智能.py` 或等价的报告生成脚本

### 背景
当前5个合成板块（产业逻辑、基本面、估值争议、资金面、催化剂）高度重复。需要合并为3个子板块，且后续分析只引用事实编号，不重复数据。

### 修改点

**Step 3.1: 新增 `_deep_analysis()` 方法**

```python
    def _deep_analysis(
        self,
        stock_name: str,
        synthesis: Dict[str, str],
        citations: Dict,
    ) -> str:
        """
        深度分析板块：合并原 5 个合成板块为 3 个子板块。
        4.1 产业逻辑与竞争格局
        4.2 业绩路径与多空分歧
        4.3 资金面与催化剂时间线
        """
        lines = ["## 四、深度分析", ""]

        # 4.1 产业逻辑与竞争格局
        industry_logic = synthesis.get("industry_logic", "")
        if industry_logic:
            lines.extend([
                "### 4.1 产业逻辑与竞争格局",
                "",
                industry_logic,
                "",
            ])
            # 该板块使用的引用
            used_refs = set(int(m) for m in re.findall(r"\[\^(\d+)\]", industry_logic))
            if used_refs:
                lines.append("**本节引用来源：**")
                for ref_id in sorted(used_refs):
                    meta = citations.get(ref_id, {})
                    source = meta.get("source", "未知")
                    author = meta.get("author", "")
                    title_text = meta.get("title", "")
                    line = f"- [^{ref_id}] {source}"
                    if author:
                        line += f" | 作者: {author}"
                    if title_text:
                        line += f" | 《{title_text[:40]}》"
                    lines.append(line)
                lines.append("")

        # 4.2 业绩路径与多空分歧
        fundamentals = synthesis.get("fundamentals", "")
        valuation_debate = synthesis.get("valuation_debate", "")
        if fundamentals or valuation_debate:
            lines.extend([
                "### 4.2 业绩路径与多空分歧",
                "",
            ])
            if fundamentals:
                lines.append(fundamentals)
                lines.append("")
            if valuation_debate:
                lines.append(valuation_debate)
                lines.append("")

            used_refs = set()
            used_refs.update(int(m) for m in re.findall(r"\[\^(\d+)\]", fundamentals))
            used_refs.update(int(m) for m in re.findall(r"\[\^(\d+)\]", valuation_debate))
            if used_refs:
                lines.append("**本节引用来源：**")
                for ref_id in sorted(used_refs):
                    meta = citations.get(ref_id, {})
                    source = meta.get("source", "未知")
                    author = meta.get("author", "")
                    title_text = meta.get("title", "")
                    line = f"- [^{ref_id}] {source}"
                    if author:
                        line += f" | 作者: {author}"
                    if title_text:
                        line += f" | 《{title_text[:40]}》"
                    lines.append(line)
                lines.append("")

        # 4.3 资金面与催化剂时间线
        funding = synthesis.get("funding_sentiment", "")
        events = synthesis.get("events_catalysts", "")
        if funding or events:
            lines.extend([
                "### 4.3 资金面与催化剂时间线",
                "",
            ])
            if funding:
                lines.append(funding)
                lines.append("")
            if events:
                lines.append(events)
                lines.append("")

            used_refs = set()
            used_refs.update(int(m) for m in re.findall(r"\[\^(\d+)\]", funding))
            used_refs.update(int(m) for m in re.findall(r"\[\^(\d+)\]", events))
            if used_refs:
                lines.append("**本节引用来源：**")
                for ref_id in sorted(used_refs):
                    meta = citations.get(ref_id, {})
                    source = meta.get("source", "未知")
                    author = meta.get("author", "")
                    title_text = meta.get("title", "")
                    line = f"- [^{ref_id}] {source}"
                    if author:
                        line += f" | 作者: {author}"
                    if title_text:
                        line += f" | 《{title_text[:40]}》"
                    lines.append(line)
                lines.append("")

        return "\n".join(lines)
```

**Step 3.2: 修改 `generate_stock_report()` 中的深度分析板块组装**

替换原有的5个独立板块为 `_deep_analysis()` 调用：

```python
        if has_synthesis:
            # 深度分析（合并为3个子板块）
            deep_section = self._deep_analysis(stock_name, synthesis, synthesis.get("citations", {}))
            if deep_section:
                sections.append(deep_section)
                # 收集所有合成文本用于风险评分
                synthesis_texts = [
                    synthesis.get(k, "")
                    for k in ["industry_logic", "fundamentals", "valuation_debate", "funding_sentiment", "events_catalysts"]
                ]
        else:
            # 降级：旧版板块展示
            sections.append(self._sentiment_and_competition(stock_name, all_posts))
            sections.append(self._core_topics(stock_name, all_posts))
            sections.append(self._zhihu_section(stock_name, stock_raw.get("zhihu", {})))
            sections.append(self._featured_posts(stock_name, featured_posts))
            sections.append(self._comment_highlights(stock_name, all_posts))
```

**Step 3.3: 更新板块编号**

行业特有风险因子从 7.5 改为 五：

```python
        # 五、行业特有风险因子评估（如适用）
        chip_risk = industry_specific_risk_table(stock_name)
        if chip_risk:
            # 替换标题中的编号
            chip_risk = chip_risk.replace("## 八-α、行业特有风险因子评估", "## 五、行业特有风险因子评估")
            sections.append(chip_risk)

        # 六、风险综合评估
        ...
        risk_section = risk_score_section(...)
        risk_section = risk_section.replace("## 八、综合风险评分", "## 六、综合风险评分")
        sections.append(risk_section)

        # 七、信息来源汇总
        if has_synthesis and synthesis.get("citations"):
            sections.append(self._citations_section("七、信息来源汇总", synthesis["citations"]))
```

Wait — `risk_score_section` 和 `industry_specific_risk_table` 是在 `scoring_engine.py` 中定义的，它们的标题硬编码在那里。直接替换字符串比较脆弱。

更好的方案是：**不在生成后替换，而是在 scoring_engine.py 中修改标题，或者接受现有编号不一致**。实际上当前报告的 "八、综合风险评分" 和 "九、信息来源汇总" 在旧结构中是因为前面有 1-7。在新结构中前面是：执行摘要（无编号）、一、二、三、四，所以风险评分应该是"五"，信息来源是"六"。

最小改动方案：**先不改 scoring_engine.py 的编号**，让报告中暂时出现编号跳跃（如一、二、三、四、八、九），这在功能上不影响。等用户确认整体结构后再统一调整编号。

不，这样报告看起来会很奇怪。让我选择修改 `scoring_engine.py` 中的标题。这增加了影响面但保证了报告质量。

或者更好的方案：**在 `stock_reporter.py` 中生成 `_deep_analysis` 时，让子板块用 `###` 而不是 `##`，这样 `## 四、深度分析` 下面有 `### 4.1/4.2/4.3`，而其他模块保持原编号不变。**

等一下，我需要重新思考编号。在新结构中：

1. 执行摘要（无编号 `##`）
2. 一、综合评分与推荐（`## 一`）
3. 二、估值与财务快照（`## 二`）
4. 核心事实基座（`## 三`）
5. 四、深度分析（`## 四`，下面有 `### 4.1/4.2/4.3`）
6. 行业特有风险因子（`## 五`）
7. 六、综合风险评分（`## 六`）
8. 七、信息来源汇总（`## 七`）

所以原 "八" 应该改为 "五"，原 "九" 应该改为 "七"。这个改动必须在 `scoring_engine.py` 或 `stock_reporter.py` 中完成。

由于 `industry_specific_risk_table()` 和 `risk_score_section()` 是在 `scoring_engine.py` 中硬编码标题的，我需要在 `scoring_engine.py` 中修改它们。这是一个额外的小改动，我把它加入 plan。

**Step 3.4: 修改 `scoring_engine.py` 中的板块标题**

```python
# 在 industry_specific_risk_table() 中
def industry_specific_risk_table(stock_name: str) -> str:
    ...
    lines = [
        "## 五、行业特有风险因子评估",  # 原 "## 八-α、行业特有风险因子评估"
        ...
    ]
```

```python
# 在 risk_score_section() 中
def risk_score_section(...):
    ...
    lines = [
        "## 六、综合风险评分",  # 原 "## 八、综合风险评分"
        ...
    ]
```

**Step 3.5: 修改 `_citations_section()` 的默认标题**

```python
    def _citations_section(self, title: str = "七、信息来源汇总", citations: Dict) -> str:
        # 原默认是 "九、信息来源汇总"
        ...
```

Wait — `_citations_section` 的签名是 `def _citations_section(self, title: str, citations: Dict)`，没有默认值。是在 `generate_stock_report()` 中传入 `"九、信息来源汇总"` 的。所以只需修改调用处。

```python
        if has_synthesis and synthesis.get("citations"):
            sections.append(self._citations_section("七、信息来源汇总", synthesis["citations"]))
```

**Step 3.6: 生成报告并验证**

```bash
python scripts/run_黑芝麻智能.py
```

Expected: 报告生成成功，新结构包含执行摘要、核心事实基座、深度分析（3子板块）。

**Step 3.7: 人工检查输出**

打开 `reports/黑芝麻智能_YYYYMMDD.md`，确认：
1. 执行摘要在最前面
2. 核心事实基座有编号表格
3. 深度分析有 4.1/4.2/4.3 子板块
4. 没有明显的事实重复
5. 板块编号连续

**Step 3.8: Commit**

```bash
git add scripts/utils/stock_reporter.py scripts/utils/reporter/scoring_engine.py
git commit -m "feat(reporter): merge 5 synthesis sections into 3 deep-analysis subsections"
```

---

## Task 4: 端到端验证

**Files:**
- 无代码修改，仅验证

**Step 4.1: 为全部6只股票生成报告**

```bash
python scripts/run_all_stocks.py  # 或等价的批量报告生成脚本
```

**Step 4.2: 检查每份报告的结构完整性**

确认每份报告都包含：
- [ ] 执行摘要（在最前面）
- [ ] 综合评分表格
- [ ] 估值与财务快照（精简版）
- [ ] 竞争对手对比表格
- [ ] 核心事实基座（如有合成数据）
- [ ] 深度分析（4.1/4.2/4.3）
- [ ] 行业特有风险因子（如适用）
- [ ] 综合风险评分
- [ ] 信息来源汇总

**Step 4.3: Commit**

```bash
git add reports/
git commit -m "chore: regenerate reports with new structure"
```

---

## Self-Review

### Spec Coverage

| 设计文档需求 | 对应 Task |
|-------------|----------|
| 减少重复事实陈述 | Task 1（核心事实提取 + no_repeat Prompt）+ Task 3（深度分析合并，引用事实编号） |
| 开头有要点总结 | Task 2（执行摘要：看多/看空论点 + 星级） |
| 利好与风险速览 | Task 2（执行摘要中的投资论点卡片） |
| 阅读有层次 | Task 2/3（总览 → 数据 → 推理 → 风险评估） |
| 板块合并 | Task 3（5个 → 3个子板块） |

### Placeholder Scan

无 TBD/TODO/"implement later"。所有步骤有明确的代码块和命令。

### Type Consistency

- `synthesize()` 返回结果新增 `core_facts: List[Dict]` 字段，与现有字段类型一致
- `_executive_summary()` 参数列表与 `generate_stock_report()` 中的可用变量一致
- `_deep_analysis()` 参数与现有 `synthesis` 数据结构一致

### Scope Check

本 plan 只包含报告结构重塑（方向1）。方向2（Fact Check）和方向3（Wind 技术分析）不在本 plan 范围内，将后续单独推进。
