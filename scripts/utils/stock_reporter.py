"""
个股深度报告生成器

基于雪球采集数据，为每只股票生成独立的深度舆情分析报告，
包含竞争格局对比、精品帖子深度解读（>=150字+判断）、关键评论摘录等。
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# 从 reporter 子模块导入常量与函数
from .reporter.constants import COMPETITOR_MAP, COMPETITOR_CODES, INDUSTRY_MAP
from .reporter.data_fetcher import (
    fetch_tencent_quote,
    fetch_consensus_eps,
    fetch_competitor_metrics,
    competitor_metrics_table,
    industry_fwd_pe,
    fetch_latest_quarterly_financials,
)
from .reporter.scoring_engine import (
    classify_sentiment,
    composite_score_section,
    compute_pillar_scores,
    ev_expectation,
    industry_specific_risk_table,
    risk_score_section,
    sentiment_ratio,
    valuation_industry_judgment,
)
from .reporter.chart_generator import (
    generate_bull_bear_chart,
    generate_radar_chart,
    generate_technical_panel,
    generate_valuation_comparison,
)


class PerStockReporter:
    """个股深度报告生成器"""

    def __init__(self, stocks_data: Dict[str, List[Dict]] = None, data_path: str = None, stock_codes: Dict[str, str] = None, raw_data: Dict[str, Any] = None):
        """
        Args:
            stocks_data: 直接传入股票数据字典
            data_path: 或从JSON文件路径加载
            stock_codes: 股票名称到6位代码的映射，如 {"乐鑫科技": "688018"}
            raw_data: 原始采集数据（研报、公告、资金流向等）
        """
        if stocks_data:
            self.stocks_data = stocks_data
        elif data_path:
            with open(data_path, "r", encoding="utf-8") as f:
                self.stocks_data = json.load(f)
        else:
            self.stocks_data = {}

        self.stock_codes = stock_codes or {}
        self.raw_data = raw_data or {}
        self.date_str = datetime.now().strftime("%Y%m%d")
        self.date_display = datetime.now().strftime("%Y年%m月%d日")

        # Lazy-initialized judgment generator
        self._judgment_generator = None

    def generate_all_reports(self, output_dir: str = None) -> List[str]:
        """
        生成所有股票的深度报告

        Returns:
            生成的Markdown文件路径列表
        """
        if output_dir is None:
            output_dir = Path(__file__).parent.parent.parent / "reports"
        else:
            output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        report_paths = []
        for stock_name in self.stocks_data:
            md_path, html_path = self.generate_stock_report(stock_name, str(output_dir))
            if md_path:
                report_paths.append(md_path)
            if html_path:
                report_paths.append(html_path)
            logger.info(f"[{stock_name}] 深度报告已生成: {md_path} | Dashboard: {html_path}")

        # 同时生成一份汇总简报
        summary_path = self._generate_summary_report(str(output_dir))
        report_paths.append(summary_path)
        logger.info(f"汇总简报已生成: {summary_path}")

        return report_paths

    def generate_stock_report(self, stock_name: str, output_dir: str) -> tuple:
        """
        生成单只股票的深度报告（Pipeline 内部实现，接口不变）。
        """
        all_posts = self.stocks_data.get(stock_name, [])
        if not all_posts:
            logger.warning(f"[{stock_name}] 无数据，跳过")
            return "", ""

        try:
            from .report_skills import build_stock_report_pipeline
            pipeline = build_stock_report_pipeline()
            ctx = pipeline.run({
                "stock_name": stock_name,
                "date_str": self.date_str,
                "output_dir": output_dir,
                "stocks_data": self.stocks_data,
                "raw_data": self.raw_data,
                "stock_codes": self.stock_codes,
            })
            md_path = ctx.output.get("md_path", "")
            html_path = ctx.output.get("html_path", "")
            if md_path:
                logger.info(f"[{stock_name}] 报告已生成: {md_path}")
            if html_path:
                logger.info(f"[{stock_name}] Dashboard 已生成: {html_path}")
            return md_path, html_path
        except Exception as e:
            logger.error(f"[{stock_name}] Pipeline 执行失败: {e}")
            return "", ""

    def generate_stock_report_legacy(self, stock_name: str, output_dir: str) -> tuple:
        """
        生成单只股票的深度报告（旧实现，保留供参考）

        Args:
            stock_name: 股票名称
            output_dir: 输出目录

        Returns:
            (Markdown文件路径, HTML Dashboard文件路径)
        """
        all_posts = self.stocks_data.get(stock_name, [])
        if not all_posts:
            logger.warning(f"[{stock_name}] 无数据，跳过")
            return "", ""

        # 统一质量门筛选（硬指标 + LLM 评估）
        try:
            from .content_quality_gate import ContentQualityGate
        except ImportError:
            import sys
            utils_dir = Path(__file__).parent
            if str(utils_dir) not in sys.path:
                sys.path.insert(0, str(utils_dir))
            from content_quality_gate import ContentQualityGate

        gate = ContentQualityGate()
        quality_results = gate.process_xueqiu_posts(all_posts)

        # 只保留高质量内容进入报告
        keep_posts = [r.item.extra for r in quality_results if r.action == "keep"]
        demote_posts = [r.item.extra for r in quality_results if r.action == "demote"]
        discard_posts = [r.item.extra for r in quality_results if r.action == "discard"]

        stock_raw = self.raw_data.get(stock_name, {})
        stock_raw["_keep_posts"] = keep_posts

        # 在 keep 的帖子中，再按原双轨分流区分 featured/sentiment
        featured_posts = [p for p in keep_posts if p.get("_track") == "featured"]
        sentiment_posts = [p for p in keep_posts if p.get("_track") != "featured"]

        logger.info(
            f"[{stock_name}] 质量门筛选: 原始={len(all_posts)}, "
            f"保留={len(keep_posts)}, 降级={len(demote_posts)}, 丢弃={len(discard_posts)} | "
            f"报告用: featured={len(featured_posts)}, sentiment={len(sentiment_posts)}"
        )

        # 准备数据
        analysis_result = stock_raw.get("analysis", {})
        code = self.stock_codes.get(stock_name, "")
        quote = fetch_tencent_quote(code) if code else None
        consensus = fetch_consensus_eps(code) if code else None
        ind_fwd_pe = industry_fwd_pe(stock_name)

        # 亏损股：计算 PS（市销率）用于替代 PE 做估值评分
        if quote and quote.get("pe_ttm", 0) <= 0 and code:
            from .reporter.data_fetcher import fetch_ps
            ps = fetch_ps(code, quote)
            if ps:
                quote["ps"] = ps

        # === 图表生成（在报告各板块中嵌入） ===
        chart_dir = Path(output_dir) / "charts"
        chart_dir.mkdir(parents=True, exist_ok=True)
        self._chart_paths: Dict[str, str] = {}

        # 先初始化 synthesis，供图表生成和后续流程使用
        synthesis = self._synthesize_sections(stock_name, stock_raw)

        try:
            # 1. 技术面综合图
            daily_data = stock_raw.get("technical", {}).get("daily_data", {})
            indicators = stock_raw.get("technical", {}).get("indicators", {})
            patterns = indicators.get("_patterns", [])
            if daily_data and indicators:
                tech_path = chart_dir / f"{stock_name}_technical_{self.date_str}.png"
                generate_technical_panel(
                    stock_name=stock_name,
                    daily_data=daily_data,
                    patterns=patterns,
                    indicators=indicators,
                    output_path=str(tech_path),
                )
                self._chart_paths["technical"] = str(tech_path)

            # 2. 多空论点对比图
            debate_text = synthesis.get("valuation_debate", "")
            fund_text = synthesis.get("fundamentals", "")
            combined = debate_text + "\n" + fund_text
            bullish_args = self._extract_thesis_points(combined, "bullish")
            bearish_args = self._extract_thesis_points(combined, "bearish")
            if bullish_args or bearish_args:
                bb_path = chart_dir / f"{stock_name}_bullbear_{self.date_str}.png"
                generate_bull_bear_chart(
                    stock_name=stock_name,
                    bullish_args=bullish_args,
                    bearish_args=bearish_args,
                    output_path=str(bb_path),
                )
                self._chart_paths["bullbear"] = str(bb_path)

            # 3. 五维评分雷达图
            pillar = compute_pillar_scores(stock_raw, all_posts, quote, consensus, ind_fwd_pe, quote.get("ps") if quote else None)
            total_score = round(
                pillar["valuation"] * 0.30 +
                pillar["technical"] * 0.25 +
                pillar["sentiment"] * 0.20 +
                pillar["fundamental"] * 0.15 +
                pillar["fundflow"] * 0.10,
                1,
            )
            radar_path = chart_dir / f"{stock_name}_radar_{self.date_str}.png"
            generate_radar_chart(
                stock_name=stock_name,
                pillar_scores=pillar,
                total_score=total_score,
                output_path=str(radar_path),
            )
            self._chart_paths["radar"] = str(radar_path)

            # 4. 估值对比图
            comp_metrics = fetch_competitor_metrics(stock_name, self.stock_codes)
            if comp_metrics:
                val_path = chart_dir / f"{stock_name}_valuation_{self.date_str}.png"
                generate_valuation_comparison(
                    stock_name=stock_name,
                    competitor_metrics=comp_metrics,
                    output_path=str(val_path),
                )
                self._chart_paths["valuation"] = str(val_path)
        except Exception as e:
            logger.warning(f"[{stock_name}] 图表生成失败: {e}")

        # === 跨来源内容去重与归纳 ===
        # 收集所有来源的高质量内容（雪球 keep + 知乎 report_items）
        zhihu_report_items = stock_raw.get("zhihu", {}).get("report_items", [])
        all_sources_items = keep_posts + zhihu_report_items

        cross_source_section = ""
        if all_sources_items:
            try:
                from .content_consolidator import ContentConsolidator
                consolidator = ContentConsolidator()
                consolidated = consolidator.consolidate(all_sources_items)
                cross_source_section = consolidator.generate_cross_source_summary(consolidated) or ""
                # 将 cross_sources 信息回注到 featured_posts 和 zhihu_report_items
                # 用于在各板块内标注交叉来源
                self._annotate_cross_sources(consolidated, keep_posts, zhihu_report_items)
            except Exception as e:
                logger.warning(f"跨来源内容归纳失败: {e}")

        # === 主题化综合叙事 ===
        # synthesis 已在图表生成阶段初始化
        has_synthesis = any(
            synthesis.get(k) for k in ["industry_logic", "fundamentals", "valuation_debate", "funding_sentiment", "events_catalysts"]
        )

        # 构建报告各部分（新 7 模块结构）
        sections = []
        sections.append(self._header(stock_name))

        # 执行摘要（新增，无编号）
        sections.append(self._executive_summary(stock_name, all_posts, stock_raw, quote, consensus, ind_fwd_pe, synthesis))

        # 一、综合评分与推荐
        score_section = composite_score_section(stock_name, all_posts, stock_raw, quote, consensus, ind_fwd_pe)
        radar_chart = getattr(self, "_chart_paths", {}).get("radar")
        if radar_chart:
            score_section += f"\n\n### 五维评分雷达图\n\n![{stock_name} 五维评分雷达图]({radar_chart})\n"
        sections.append(score_section)

        # 二、估值与财务快照（精简版）
        sections.append(self._valuation_forecast_compact(stock_name, quote, consensus))

        # 最新财务快照（含同比）
        quarterly_fin = self._quarterly_financials_table(stock_name)
        if quarterly_fin:
            sections.append(quarterly_fin)

        # 竞争对手财务指标对比（无编号）
        comp_metrics = fetch_competitor_metrics(stock_name, self.stock_codes)
        if comp_metrics:
            comp_table = competitor_metrics_table(stock_name, comp_metrics)
            val_chart = getattr(self, "_chart_paths", {}).get("valuation")
            if val_chart:
                comp_table += f"\n\n### 估值对比图\n\n![{stock_name} 估值对比]({val_chart})\n"
            sections.append(comp_table)

        # 技术面分析（新增）
        tech_section = self._technical_analysis_section(stock_name, stock_raw)
        if tech_section:
            sections.append(tech_section)

        # 价格目标与触发条件（新增）
        price_target_section = self._price_target_section(stock_name, stock_raw)
        if price_target_section:
            sections.append(price_target_section)

        # 三、核心事实基座（新增）
        core_facts = synthesis.get("core_facts", [])
        if core_facts:
            sections.append(self._core_facts_table(core_facts))

        # 收集合成文本用于风险评分增强
        synthesis_texts = []

        if has_synthesis:
            # 四、深度分析（合并5个合成板块为3个子板块）
            deep_section = self._deep_analysis(stock_name, synthesis)
            if deep_section:
                sections.append(deep_section)
                for k in ["industry_logic", "fundamentals", "valuation_debate", "funding_sentiment", "events_catalysts"]:
                    if synthesis.get(k):
                        synthesis_texts.append(synthesis[k])
        else:
            # 降级：旧版板块展示
            sections.append(self._sentiment_and_competition(stock_name, all_posts))
            sections.append(self._core_topics(stock_name, all_posts))
            sections.append(self._zhihu_section(stock_name, stock_raw.get("zhihu", {})))
            sections.append(self._featured_posts(stock_name, featured_posts))
            sections.append(self._comment_highlights(stock_name, all_posts))

        # 7.5 行业特有风险因子评估（如适用）
        chip_risk = industry_specific_risk_table(stock_name)
        if chip_risk:
            sections.append(chip_risk)

        # 8. 风险综合评估（保留）
        watch_points = self._risks_and_watch(stock_name, all_posts)
        combined_synthesis = "\n".join(synthesis_texts)
        sections.append(risk_score_section(stock_name, all_posts, stock_raw, quote, consensus, ind_fwd_pe, watch_points, combined_synthesis))

        # 9. 信息来源汇总（新）
        if has_synthesis and synthesis.get("citations"):
            sections.append(self._citations_section("七、信息来源汇总", synthesis["citations"]))

        sections.append(self._footer())

        markdown = "\n\n".join(sections)

        # 保存 Markdown
        md_filename = f"{stock_name}_{self.date_str}.md"
        md_path = Path(output_dir) / md_filename
        md_path.write_text(markdown, encoding="utf-8")

        # 生成 HTML Dashboard
        html_filename = f"{stock_name}_Dashboard_{self.date_str}.html"
        html_path = Path(output_dir) / html_filename
        html_content = self._generate_html_dashboard(stock_name, self._chart_paths)
        html_path.write_text(html_content, encoding="utf-8")

        return str(md_path), str(html_path)

    def _header(self, stock_name: str) -> str:
        """报告头部"""
        industry = INDUSTRY_MAP.get(stock_name, "")
        competitors = ", ".join(COMPETITOR_MAP.get(stock_name, []))
        return f"""# {stock_name} 舆情深度报告

**报告日期**: {self.date_display}
**所属赛道**: {industry}
**可比公司**: {competitors}
**数据来源**: 雪球网热门讨论

---"""

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
        """执行摘要：综合评分 + 核心投资论点 + 一句话结论。"""
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
        sentiment = sentiment_ratio(all_posts)

        ev_pct = ev.get('ev_pct')
        ev_signal = ev.get('signal') or 'N/A'
        ev_pct_str = f"{ev_pct:+.2f}" if ev_pct is not None else "N/A"
        lines = [
            "## 执行摘要",
            "",
            f"### 综合评分: {total_score}/10 | EV: {ev_pct_str}%（{ev_signal}）",
            "",
            "| 维度 | 权重 | 得分(0-10) | 说明 |",
            "|------|------|------------|------|",
            f"| 估值健康度(B) | 30% | {pillar['valuation']:.1f} | {pillar.get('valuation_note', '')} |",
            f"| 技术面强度(M) | 25% | {pillar['technical']:.1f} | {pillar.get('technical_note', '')} |",
            f"| 情绪面温度(M) | 20% | {pillar['sentiment']:.1f} | 看多 {sentiment['bullish']:.0f}% / 看空 {sentiment['bearish']:.0f}% |",
            f"| 基本面趋势(B) | 15% | {pillar['fundamental']:.1f} | {pillar.get('fundamental_note', '')} |",
            f"| 资金关注度(M) | 10% | {pillar['fundflow']:.1f} | {pillar.get('fundflow_note', '')} |",
            "",
            "### 核心投资论点",
            "",
        ]

        # 从合成文本中提取多空信号（简化启发式）
        debate_text = synthesis.get("valuation_debate", "")
        fund_text = synthesis.get("fundamentals", "")
        combined = debate_text + "\n" + fund_text

        bullish_points = self._extract_thesis_points(combined, "bullish")
        bearish_points = self._extract_thesis_points(combined, "bearish")

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

        # 一句话结论
        conclusion = self._extract_conclusion(stock_name, combined)
        if conclusion:
            lines.append(f"> **一句话结论**：{conclusion}")
            lines.append("")

        # --- 多空论点对比图 ---
        bullbear_chart = getattr(self, "_chart_paths", {}).get("bullbear")
        if bullbear_chart:
            lines.append("### 多空论点对比")
            lines.append("")
            lines.append(f"![{stock_name} 多空论点对比]({bullbear_chart})")
            lines.append("")

        return "\n".join(lines)

    def _extract_thesis_points(self, text: str, direction: str) -> List[Dict]:
        """从合成文本中提取看多/看空论点。优先使用 LLM，失败时回退到启发式。"""
        points = []
        if not text:
            return points

        # 尝试 LLM 提取
        try:
            llm_result = self._llm_extract_thesis(text)
            if direction == "bullish":
                return llm_result.get("bullish", [])
            else:
                return llm_result.get("bearish", [])
        except Exception as e:
            logger.warning(f"LLM 论点提取失败，回退到启发式: {e}")

        # 回退：启发式提取
        if direction == "bullish":
            keywords = ["增长", "放量", "突破", "拐点", "优势", "机遇", "看好", "上调", "超预期", "确定性"]
            for sentence in text.split("。"):
                if any(k in sentence for k in keywords) and len(sentence) > 20:
                    points.append({"text": sentence.strip() + "。", "stars": 3})
                if len(points) >= 4:
                    break
        else:
            keywords = ["亏损", "下滑", "压力", "风险", "落后", "减持", "解禁", "看空", "下调", "陷阱"]
            for sentence in text.split("。"):
                if any(k in sentence for k in keywords) and len(sentence) > 20:
                    points.append({"text": sentence.strip() + "。", "stars": 3})
                if len(points) >= 4:
                    break

        return points

    def _extract_conclusion(self, stock_name: str, text: str) -> str:
        """提取一句话结论。优先使用 LLM，失败时返回空字符串。"""
        if not text:
            return ""
        try:
            llm_result = self._llm_extract_thesis(text)
            return llm_result.get("conclusion", "")
        except Exception:
            return ""

    def _llm_extract_thesis(self, text: str) -> Dict:
        """调用 LLM 从合成文本中提取多空论点和结论。"""
        import os
        from openai import OpenAI

        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("MOONSHOT_API_KEY")
        if not api_key:
            raise RuntimeError("LLM API key not configured")

        base_url = (
            "https://api.deepseek.com/v1"
            if os.getenv("DEEPSEEK_API_KEY")
            else "https://api.moonshot.cn/v1"
        )
        model = (
            os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            if os.getenv("DEEPSEEK_API_KEY")
            else os.getenv("MOONSHOT_MODEL", "moonshot-v1-8k")
        )

        client = OpenAI(api_key=api_key, base_url=base_url)

        prompt = (
            "你是资深投资分析师。请基于以下分析文本，提取核心投资论点。\n\n"
            "要求：\n"
            "1. 看多论点：最多3条，每条不超过60字，只保留最核心的判断和数据支撑\n"
            "2. 看空论点：最多3条，每条不超过60字，只保留最核心的判断和数据支撑\n"
            "3. 给每条论点一个风险/机会等级（1-5星，整数）\n"
            "4. 一句话结论（不超过40字，概括多空博弈的核心）\n\n"
            "输出严格 JSON 格式，不要有任何其他内容：\n"
            '{\n'
            '  "bullish": [{"text": "...", "stars": 4}, ...],\n'
            '  "bearish": [{"text": "...", "stars": 3}, ...],\n'
            '  "conclusion": "..."\n'
            '}\n\n'
            "分析文本：\n"
            f"{text[:3000]}"
        )

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是专业的中文投资分析师，擅长提炼多空核心论点。只输出JSON，不输出任何解释或markdown。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=800,
        )

        response_text = resp.choices[0].message.content.strip()
        # 去除可能的 markdown code block
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        result = json.loads(response_text)
        # 校验结构
        for key in ["bullish", "bearish"]:
            if key in result and isinstance(result[key], list):
                for pt in result[key]:
                    if not isinstance(pt, dict):
                        continue
                    pt.setdefault("text", "")
                    pt.setdefault("stars", 3)
                    # 确保 stars 是 1-5 的整数
                    pt["stars"] = max(1, min(5, int(pt.get("stars", 3))))
        result.setdefault("conclusion", "")
        return result

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
            "> **说明**：后续深度分析模块不再重复展开这些数据，仅在需要支撑论点时引用编号（如“见事实#1”）。",
            "",
        ])
        return "\n".join(lines)

    def _valuation_forecast_compact(self, stock_name: str, quote=None, consensus=None) -> str:
        """精简版估值板块：表格 + 一句话判断。"""
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
                "| 指标 | 数值 | 说明 |",
                "|------|------|------|",
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

    def _quarterly_financials_table(self, stock_name: str) -> str:
        """最新财务数据快照（含同比）。"""
        code = self.stock_codes.get(stock_name, "")
        if not code:
            return ""

        fin = fetch_latest_quarterly_financials(code)
        if not fin:
            return ""

        date_type = fin.get("date_type", "")
        report_date = fin.get("report_date", "")[:10] if fin.get("report_date") else ""

        def _fmt(val, unit="", decimals=1):
            if val is None:
                return "N/A"
            if unit == "亿":
                return f"{val/100000000:.{decimals}f}亿"
            if unit == "%":
                return f"{val:.{decimals}f}%"
            return f"{val:.{decimals}f}"

        def _yoy(val):
            if val is None:
                return "N/A"
            sign = "+" if val >= 0 else ""
            return f"{sign}{val:.1f}%"

        revenue = fin.get("revenue")
        net_profit = fin.get("net_profit")
        gross_margin = fin.get("gross_margin")
        net_margin = fin.get("net_margin")
        roe = fin.get("roe")
        basic_eps = fin.get("basic_eps")

        lines = [
            "### 最新财务快照",
            "",
            f"> 报告期: {report_date} ({date_type}) | 数据来源: 东方财富",
            "",
            "| 指标 | 最新值 | 同比变化 |",
            "|------|--------|----------|",
        ]

        if revenue is not None:
            lines.append(f"| 营业总收入 | {_fmt(revenue, '亿', 2)} | {_yoy(fin.get('revenue_yoy'))} |")
        if net_profit is not None:
            lines.append(f"| 归母净利润 | {_fmt(net_profit, '亿', 2)} | {_yoy(fin.get('net_profit_yoy'))} |")
        if gross_margin is not None:
            lines.append(f"| 毛利率 | {_fmt(gross_margin, '%', 1)} | {_yoy(fin.get('gross_margin_yoy'))} |")
        if net_margin is not None:
            lines.append(f"| 净利率 | {_fmt(net_margin, '%', 1)} | {_yoy(fin.get('net_margin_yoy'))} |")
        if roe is not None:
            lines.append(f"| ROE(平均) | {_fmt(roe, '%', 1)} | {_yoy(fin.get('roe_yoy'))} |")
        if basic_eps is not None:
            lines.append(f"| 基本 EPS | {_fmt(basic_eps)} | {_yoy(fin.get('eps_yoy'))} |")

        lines.append("")

        # 一句话总结
        summary_parts = []
        if fin.get("revenue_yoy") is not None:
            direction = "增长" if fin["revenue_yoy"] >= 0 else "下滑"
            summary_parts.append(f"营收同比{direction}{abs(fin['revenue_yoy']):.1f}%")
        if fin.get("net_profit_yoy") is not None:
            direction = "增长" if fin["net_profit_yoy"] >= 0 else "下滑"
            summary_parts.append(f"净利润同比{direction}{abs(fin['net_profit_yoy']):.1f}%")
        if summary_parts:
            lines.append(f"> **财务趋势**: {'，'.join(summary_parts)}。")
            lines.append("")

        return "\n".join(lines)

    def _deep_analysis(
        self,
        stock_name: str,
        synthesis: Dict[str, str],
    ) -> str:
        """
        深度分析板块：合并原5个合成板块为3个子板块。
        4.1 产业逻辑与竞争格局
        4.2 业绩路径与多空分歧
        4.3 资金面与催化剂时间线
        """
        citations = synthesis.get("citations", {})
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

    def _synthesize_sections(self, stock_name: str, stock_raw: Dict) -> Dict[str, str]:
        """
        调用 KnowledgeSynthesizer 生成主题化综合叙事。
        返回包含 5 个主题 Markdown + citations 的字典。
        """
        try:
            from scripts.utils.knowledge_synthesizer import KnowledgeSynthesizer
            from scripts.utils.source_adapter import adapt_all
        except ImportError:
            import sys
            utils_dir = Path(__file__).parent
            if str(utils_dir) not in sys.path:
                sys.path.insert(0, str(utils_dir))
            from knowledge_synthesizer import KnowledgeSynthesizer
            from source_adapter import adapt_all

        # 收集所有来源的数据
        keep_posts = stock_raw.get("_keep_posts", [])
        zhihu_items = stock_raw.get("zhihu", {}).get("report_items", [])
        reports = stock_raw.get("reports", [])
        announcements = stock_raw.get("announcements", [])
        fundflow = stock_raw.get("fundflow", [])
        news = stock_raw.get("news", [])

        items = adapt_all(
            xueqiu_items=keep_posts,
            zhihu_items=zhihu_items,
            reports=reports,
            announcements=announcements,
            fundflow=fundflow,
            news=news,
        )
        if not items:
            return {k: "" for k in ["industry_logic", "fundamentals", "valuation_debate", "funding_sentiment", "events_catalysts"]} | {"citations": {}}

        synth = KnowledgeSynthesizer()
        result = synth.synthesize(stock_name, {"items": items})

        # 回填 citation 元数据：用 items 列表按索引匹配
        citations = result.get("citations", {})
        resolved_citations = {}
        for ref_id, meta in citations.items():
            if meta.get("_placeholder") and 1 <= ref_id <= len(items):
                src_item = items[ref_id - 1]
                resolved_citations[ref_id] = {
                    "title": src_item.title,
                    "source": src_item.source_platform,
                    "author": src_item.author,
                    "url": src_item.url,
                    "date": src_item.publish_time,
                }
            else:
                resolved_citations[ref_id] = meta
        result["citations"] = resolved_citations
        return result

    def _sentiment_and_competition(self, stock_name: str, posts: List[Dict]) -> str:
        """
        市场情绪与竞争格局
        根据股票名称做差异化深度分析
        """
        total = len(posts)
        total_likes = sum(p.get("like_count", 0) for p in posts)
        total_comments = sum(p.get("comment_count", 0) for p in posts)
        total_reposts = sum(p.get("repost_count", 0) for p in posts)
        avg_interaction = (total_likes + total_comments + total_reposts) / total if total else 0

        # 提取看多/看空/中性信号
        bullish_signals, bearish_signals, neutral_signals = classify_sentiment(posts)

        section = f"""## 八、市场情绪与竞争格局

### 1.1 社区情绪画像

本报告基于雪球网{stock_name}讨论区最新 **{total}** 条热门帖子分析：

- **总互动量**: 👍 {total_likes} | 💬 {total_comments} | 🔄 {total_reposts}
- **平均互动**: {avg_interaction:.1f} 次/帖
- **看多信号**: {len(bullish_signals)} 条
- **看空信号**: {len(bearish_signals)} 条
- **中性/观望**: {len(neutral_signals)} 条

**情绪定级**: {"看多" if len(bullish_signals) > len(bearish_signals) else "看空" if len(bearish_signals) > len(bullish_signals) else "中性"}

### 1.2 竞争格局对比

{self._competitor_analysis(stock_name, posts)}
"""
        return section

    def _competitor_analysis(self, stock_name: str, posts: List[Dict]) -> str:
        """根据股票生成竞争格局分析"""
        analyses = {
            "黑芝麻智能": """
黑芝麻智能当前在雪球社区的热度处于**中等偏上**水平。与同业对比：

- **vs 地平线**: 地平线作为港股上市的智驾芯片第一股，社区讨论热度更高，但黑芝麻智能在"性价比"和"比亚迪供应链"切入点上获得了更多看多关注。地平线更多被讨论的是高端市场，而黑芝麻被视为"英伟达平替"，走的是差异化路线。
- **vs 英伟达/高通**: 国际巨头的讨论多集中在美股板块，A股/港股投资者更关注国产替代逻辑。黑芝麻的华山A2000芯片对标Orin，但社区对其量产进度和软件生态仍有疑虑。
- **竞争态势判断**: 黑芝麻智能处于"认知度快速提升但信任度尚未完全建立"的阶段。看多者认为其性价比+本土服务是核心竞争力；看空者担忧其市值过低（约120亿港币），面临港股通退通和外资做空的双重压力。""",

            "长春高新": """
长春高新在雪球社区的情绪处于**极度低迷**状态。与同业对比：

- **vs 特宝生物**: 特宝生物的长效生长激素已进医保，社区讨论中多次出现"特宝进医保、金赛不进"的对比，长春高新在医保准入节奏上明显落后，这是最大的看空理由。
- **vs 诺和诺德**: 国际巨头在减肥药和生长激素领域的技术领先被频繁提及，投资者认为长春高新的"创新药"叙事在面对真正国际化竞争时缺乏说服力。
- **竞争态势判断**: 长春高新正经历"戴维斯双杀"后的深度价值陷阱期。社区情绪极度悲观，大量融资盘爆仓。少数看多者认为当前估值已反映所有利空，但看空者认为集采+竞争格局恶化远未结束。""",

            "三花智控": """
三花智控当前是雪球社区**最热门的机器人概念股之一**。与同业对比：

- **vs 拓普集团**: 拓普被更多讨论为"特斯拉一体化压铸+机器人"双主线标的，而三花的核心标签是"热管理+执行器"。社区有投资者正将仓位从拓普转向三花，理由是三花的数据中心冷却业务提供了第二增长曲线。
- **vs 银轮股份**: 银轮在热管理领域有竞争关系，但三花在特斯拉T链中的地位更稳固，且机器人执行器（旋转/线性关节）是银轮没有的增量业务。
- **竞争态势判断**: 三花智控处于"产业周期+资金情绪"双击的最强窗口。社区共识认为5-6月是订单落地的关键期，7-8月量产前股价仍有催化空间。风险在于短期涨幅过大，一旦订单不及预期可能面临剧烈回调。""",

            "中简科技": """
中简科技在雪球社区的讨论呈现**"少数深度投资者高度活跃、大众关注度偏低"**的特征。与同业对比：

- **vs 光威复材**: 光威是碳纤维板块的老大哥，市值和产品线都更全面。但中简在**高端军工T800级及以上产品**上有技术壁垒，社区讨论认为中简在"航天级"应用上有差异化优势。
- **vs 恒神股份**: 恒神被提及较多的是"陕煤系"背景和民品拓展，与中简的"纯军工高端"定位不同。
- **竞争态势判断**: 中简科技正处于最艰难的时期。Q1业绩暴雷（客户需求阶段性减少）导致大量散户离场，股东人数下降10%。但深度跟踪者认为，军工订单的季节性波动不应改变长期逻辑——歼-35量产、商业航天（全碳纤维箭体）、空客供应链（科泰思创合作）三大催化正在蓄力。当前更像是"筹码从散户向机构集中"的阶段。""",

            "圣邦股份": """
圣邦股份在雪球社区正处于**"趋势确立、情绪升温"**的阶段。与同业对比：

- **vs 思瑞浦**: 思瑞浦在社区中被视为"扩品类更快"的少壮派，圣邦则是"平台更稳"的老掌门。近期两者同步大涨，说明模拟芯片板块整体得到资金认可。
- **vs 杰华特**: 杰华特在MOS/DrMOS领域的技术领先被一些业内人士提及，有观点认为杰华特的产品已通过更多认证，圣邦在高端MOS上仍需追赶。这是圣邦最大的竞争风险点。
- **竞争态势判断**: 圣邦的核心逻辑是"模拟芯片是物理AI的前端刚需"。社区已形成共识：无论AI应用落地在哪个终端，信号链+电源管理芯片都是必不可少的。从库存周期看，模拟芯片行业已完成去库存，进入涨价周期。但短期内涨幅过大（90→100+），需要警惕获利回吐。""",

            "乐鑫科技": """
乐鑫科技在雪球社区的讨论呈现**"长线投资者坚定持有、短线交易者抱怨走势"**的分化格局。与同业对比：

- **vs 翱捷科技**: 翱捷聚焦蜂窝基带，乐鑫聚焦Wi-Fi/BLE，两者定位不同。但社区有讨论认为AIoT芯片的终局可能是"连接+计算"一体化，翱捷和高通的布局可能挤压乐鑫的长期空间。
- **vs 博通集成/全志科技**: 这些公司在低功耗连接领域与乐鑫有直接竞争，但乐鑫的开发者生态（数百万开发者、详尽的文档和海量的开源代码）是其最深的护城河。Anthropic在开发者活动中推荐ESP32就是最佳背书。
- **竞争态势判断**: 乐鑫的核心矛盾是"低端芯片"的市场标签与其在端侧AI中的战略价值之间的预期差。社区长线投资者认为500亿市值只是起点（当前约200亿+），但短线交易者对量化资金控盘、走势不流畅抱怨颇多。S31新品的导入进度是近期最大看点。""",
        }
        return analyses.get(stock_name, "")

    def _core_topics(self, stock_name: str, posts: List[Dict]) -> str:
        """
        核心话题与产业逻辑
        根据股票做差异化话题提取
        """
        topic_analyses = {
            "黑芝麻智能": """## 九、核心话题与产业逻辑

### 话题1：AEB强制安装倒计时——10万级市场的增量空间

2026年是AEB（自动紧急制动）强制安装的元年。根据国内法规，新上市乘用车必须标配AEB，这将极大拉动智驾芯片的渗透率。黑芝麻智能的华山系列芯片主打"高性价比舱驾一体"，恰好切入了10-20万元价格带的增量市场。社区讨论认为，这一市场此前被英伟达Orin（成本过高）和地平线（竞争激烈）占据，黑芝麻的差异化在于"用1/3的价格实现80%的性能"。

**催化剂**: 法规强制安装节点临近，比亚迪等主机厂开始大规模招标。

### 话题2：港股通做空围猎与退通风险

这是社区最具争议性的话题。有投资者指出，黑芝麻智能市值仅约120亿港币，而港股通退通的红线约为65亿（市值后4%）。如果股价跌到10港币附近（当前约15港币），将面临退通风险。退通后大陆投资者只能卖不能买，而外资可以继续做空还券，形成"稳赚不赔"的套利结构。看空者认为这是港股小市值科技股的结构性BUG；看多者则认为这是"被错杀"的机会，伯恩斯坦给予16港币目标价就是底线确认。

**催化剂**: 港股通持股比例变化、公司回购进展。

### 话题3：具身智能/机器人第二曲线

黑芝麻智能在社区中被提及的第三大业务板块是"具身智能"。公司在年报中透露该业务已实现"从无到有的突破"，但具体产品和客户信息较少。看多者将其视为继智驾之后的第二增长曲线；看空者认为这纯属概念炒作，距离商业化还很遥远。

**催化剂**: 与机器人本体厂商的合作公告。""",

            "长春高新": """## 九、核心话题与产业逻辑

### 话题1：生长激素集采后的竞争格局恶化

长春高新最核心的利空是金赛药业生长激素面临集采压力和竞品挤压。特宝生物的长效生长激素已率先进入医保，社区讨论中"特宝进医保、金赛不进"被反复提及。更严峻的是，诺和诺德等跨国药企在生长激素领域的研发管线不断推进，一旦进口产品降价进入中国市场，长春高新的价格体系将面临更大冲击。

**催化剂**: 新一轮医保谈判目录、各省集采扩面进度。

### 话题2：金赛增成人适应症三期临床终止的信任危机

2026年5月，长春高新公告终止金赛增成人适应症三期临床（CTR20232469），这在社区引发轩然大波。投资者质疑：为什么2023年启动的试验拖到2026年才砍？累计投入1.2亿元是否打水漂？管理层在投资者关系活动中对BD（商务拓展）的描述也备受质疑——"每年都会增加"被批评为"空话"。

**催化剂**: 管理层在股东会和业绩说明会上的进一步解释。

### 话题3：从"百倍牛股"到"价值陷阱"——估值体系的崩塌

社区有大量帖子复盘长春高新从550元跌到86元的过程。核心教训是：高估值成长股在政策逆风期可能面临"业绩下滑+估值压缩"的戴维斯双杀。曾经支撑百倍PE的"永续增长"叙事，在集采面前不堪一击。当前市盈率已降至历史低位，但投资者担心"低估值陷阱"——业绩可能继续恶化。

**催化剂**: 金赛药业季度环比增速能否回到5%以上。""",

            "三花智控": """## 九、核心话题与产业逻辑

### 话题1：特斯拉Optimus Gen-3量产——T链核心供应商地位

2026年7-8月特斯拉人形机器人正式量产，这是三花智控当前最热的催化因素。社区共识认为，三花在热管理（电子膨胀阀、换热器）和执行器（旋转关节、线性推杆）两个环节都是特斯拉的核心供应商。瑞银5月研报指出，未来1-2个月（5-6月）将是供应链利好的集中爆发期，多个核心项目的正式定点、首批量产订单会陆续落地。

**催化剂**: 特斯拉供应商大会、小批量订单落地公告。

### 话题2：物理AI/数据中心冷却——第二增长曲线

"物理AI"是近期A股最火的概念之一，三花智控被市场视为"数据中心液冷"的核心标的。社区讨论指出，随着AI算力需求爆发，数据中心PUE（能源使用效率）要求越来越严格，液冷替代风冷是大趋势。三花在新能源汽车热管理中积累的液冷技术可以直接迁移到数据中心场景。投资者正在将拓普的仓位转向三花，正是看中了这一增量业务。

**催化剂**: 与互联网大厂/算力中心的液冷订单、英伟达GB200液冷方案进展。

### 话题3：特斯拉汽车业务之外的"去单一客户依赖"

虽然特斯拉机器人是三花当前的最大热点，但社区深度投资者更关注三花在家用空调、数据中心冷却、储能热管理等多个领域的布局。欧洲家庭空调渗透率仅20%（中国城镇接近100%），印度仅8-10%，这些市场的增长空间为传统汽车热管理业务提供了安全边际。

**催化剂**: 海外市场拓展进度、非特斯拉客户占比变化。""",

            "中简科技": """## 九、核心话题与产业逻辑

### 话题1：Q1业绩暴雷后的真相——订单节奏还是需求萎缩？

2026年Q1中简科技业绩大幅下滑，公司解释是"客户对部分产品的需求量阶段性减少"。社区对此存在分歧：看空者认为这是需求萎缩的信号，碳纤维在军工领域的应用可能不及预期；看多者则认为军工订单具有强季节性，Q1 traditionally是淡季，且公司年报中已透露出"部分产品送样、试用"的积极信号。

**催化剂**: Q2订单恢复情况、新定型产品批产公告。

### 话题2：航空发动机碳纤维应用——从"不可能"到"已送样"

中简科技在投资者关系活动中透露，公司正在推动碳纤维产品在航空发动机领域的应用，"部分产品已经送样、试用"。社区认为这是最大的预期差——如果碳纤维能进入航空发动机（此前被认为是技术和产业链上的不可能），将打开十倍级市场空间。技术逻辑是：碳纤维复合材料可以大幅减轻发动机重量、提高推重比。

**催化剂**: 航空发动机型号定型进展、军品鉴定报告。

### 话题3：商业航天+空客供应链——从军工单一大客户到多元化

中简科技近期与科泰思创（空客波音复材供应商）达成战略合作，被社区解读为"进军空客供应链"的信号。同时，2026年中国航天大会上"全碳纤维箭体+全流量发动机"的发布，也让商业航天成为碳纤维的新应用场景。社区深度跟踪者认为，中简正在从"单一大客户依赖"向"军工+民机+商业航天"多元化转型。

**催化剂**: 与科泰思创合作的具体订单、朱雀/微光等火箭型号采用中简材料公告。""",

            "圣邦股份": """## 九、核心话题与产业逻辑

### 话题1：物理AI前端刚需——模拟芯片的价值重估

"物理AI"概念近期火爆，其核心逻辑是将AI能力从云端延伸到物理世界（机器人、智能设备、汽车等）。而物理AI的前端——传感器信号采集、电源管理、电机驱动——都离不开模拟芯片。社区有投资者系统梳理了圣邦的产品线，指出其在信号链和电源管理两大领域均有完整布局，是"物理AI必须用到"的核心标的。

**催化剂**: 物理AI概念持续发酵、AI终端产品（AI玩具、AI机器人）出货量。

### 话题2：库存周期反转+涨价预期

模拟芯片行业自2023年以来经历了漫长的去库存周期。社区有跟踪者从去年下半年开始布局圣邦，前两次因库存未反转小亏出局，今年1月底最后一次买入至今获利丰厚。当前行业共识是模拟芯片库存已恢复正常，部分产品开始涨价。圣邦Q1业绩的超预期增长验证了周期反转逻辑。

**催化剂**: 行业涨价函、Q2业绩指引。

### 话题3：国产替代加速——从消费电子走向工业/汽车

圣邦股份的传统优势在消费电子领域，但社区讨论显示，其产品正在快速向工业控制和汽车电子渗透。模拟芯片的国产替代率目前仍不足20%，在贸易摩擦背景下，华为、小米等终端厂商加速导入国产模拟芯片。圣邦的"货架式"产品策略（SKU数量远超国内同行）使其在客户导入时具有便利性优势。

**催化剂**: 进入华为/小米供应链公告、车规级产品认证进展。""",

            "乐鑫科技": """## 九、核心话题与产业逻辑

### 话题1：端侧AI核心硬件——Anthropic官方背书的战略价值

Anthropic在最新开发者活动中将基于乐鑫ESP32-S3的M5Stack Cardputer作为官方推荐硬件，这是乐鑫近期最大的品牌事件。社区讨论的核心逻辑是：AI模型要落地到物理世界，必须依赖低功耗、高性价比的边缘计算芯片。乐鑫ESP32系列在全球拥有数百万开发者，对于AI模型来说，乐鑫详尽的文档和海量的开源代码库是其"学习最充分、执行最精准"的硬件语言。

**催化剂**: 更多AI公司采用ESP32作为边缘硬件、与OpenAI/Anthropic的合作深化。

### 话题2：20亿颗年出货目标与S31新品导入

乐鑫管理层提出2026年芯片出货量达到20亿颗的目标（此前年出货约10亿颗级别）。社区对此存在分歧：看多者认为AIoT设备爆发将带来出货量指数级增长；看空者质疑20亿颗目标过于激进，且S31新品的导入期通常需要1-2年，今年难以贡献显著增量。公司大幅增加原材料备货，被部分投资者解读为"赌S31量产"。

**催化剂**: S31新品发布、季度出货量数据、大客户导入公告。

### 话题3：从"Wi-Fi芯片商"到"端侧AI平台商"的定位升级

乐鑫面临的最大市场预期差，是投资者仍将其视为"做体脂秤/插座Wi-Fi模块的低端芯片商"。社区长线投资者反复解释：乐鑫的真正价值不在于单颗芯片的ASP，而在于其"芯片+软件+生态"的平台能力。随着ESP-IDF机器学习框架的成熟，乐鑫正在从"连接芯片商"升级为"端侧AI平台商"。

**催化剂**: 端侧AI应用爆款产品出现、与智能家居/机器人品牌厂商的深度合作。""",
        }
        return topic_analyses.get(stock_name, "")

    def _featured_posts(self, stock_name: str, posts: List[Dict]) -> str:
        """
        精品帖子深度解读（>=150字原文 + 我的判断）
        选取互动量最高的2-3条非转发帖子，同一作者相似内容去重
        """
        if not posts:
            return "## 十、精品帖子深度解读\n\n*本期无高质量分析帖*\n"

        # 过滤掉转发帖和公告帖
        original_posts = [
            p for p in posts
            if not p.get("is_repost") and p.get("author") != stock_name
            and not ("公告" in p.get("title", "") and p.get("author", "").startswith(stock_name))
        ]
        if not original_posts:
            original_posts = posts

        # 按互动量排序
        sorted_posts = sorted(
            original_posts,
            key=lambda x: x.get("like_count", 0) + x.get("comment_count", 0) + x.get("repost_count", 0),
            reverse=True
        )

        # 去重：同一作者且内容相似度过高的帖子只保留互动量最高的一篇
        featured = []
        for post in sorted_posts:
            if len(featured) >= 3:
                break
            author = post.get("author", "")
            content = post.get("content", "")
            # 检查是否与已选帖子（同作者）内容高度相似
            is_duplicate = False
            for fp in featured:
                if fp.get("author") == author:
                    # 计算相似度：取较长内容的70%作为阈值
                    fp_content = fp.get("content", "")
                    min_len = min(len(content), len(fp_content))
                    if min_len > 0:
                        # 简单判断：前 min_len 个字符中相同比例
                        same_chars = sum(1 for a, b in zip(content[:min_len], fp_content[:min_len]) if a == b)
                        if same_chars / min_len > 0.7:
                            is_duplicate = True
                            break
            if not is_duplicate:
                featured.append(post)

        # 如果去重后不足3篇，补充其他帖子
        if len(featured) < 3:
            featured_urls = {p.get("url") for p in featured}
            for post in sorted_posts:
                if post.get("url") not in featured_urls:
                    featured.append(post)
                if len(featured) >= 3:
                    break

        sections = ["## 十、精品帖子深度解读\n"]

        # 每只股票预定义的深度分析（按URL匹配，确保与帖子一一对应）
        featured_analyses = self._get_featured_analyses(stock_name)

        for i, post in enumerate(featured, 1):
            title = post.get("title", "")
            author = post.get("author", "")
            url = post.get("url", "")
            likes = post.get("like_count", 0)
            comments = post.get("comment_count", 0)
            reposts = post.get("repost_count", 0)
            content = post.get("content", "")
            time_str = post.get("time", "")

            # 优先从 Vault 读取完整正文
            vault_data = self._read_full_content_from_vault(stock_name, url)
            if vault_data:
                full_content = vault_data["body"]
                media_info = vault_data.get("media", {})
                excerpt = self._extract_excerpt(full_content, min_length=200, max_length=600)
            else:
                full_content = content
                media_info = {}
                excerpt = self._extract_excerpt(content, min_length=150, max_length=400)
                # 如果内容明显是截断的列表页摘要，标注提示
                if len(content) < 200:
                    excerpt = f"【列表页摘要，详情见原文链接】{excerpt}"

            # 获取我的判断：优先使用 LLM 自动生成，其次回退到硬编码
            judgment = self._get_llm_judgment(stock_name, post, full_content or content)
            if not judgment:
                judgment = featured_analyses.get(url, "")
            if not judgment:
                judgment = featured_analyses.get(i, "")
            if not judgment:
                judgment = self._generic_judgment(stock_name, post)

            # 负面过滤：LLM 判断论据质量极低的帖子不进入报告
            low_quality_signals = [
                "论据扎实程度极低",
                "论据基础为零",
                "不具备分析价值",
                "逻辑链条断裂",
                "内容不完整",
            ]
            if any(sig in judgment for sig in low_quality_signals):
                logger.info(
                    f"[{stock_name}] 帖子因论据质量极低被过滤: {title[:30]}..."
                )
                continue

            # 图表与数据说明
            media_desc = self._format_media_description(media_info)
            media_section = f"\n\n**图表与数据说明**:\n\n{media_desc}" if media_desc else ""

            # 确保引用块内段落连续：将 \n\n 替换为 \n>\n> 以保持 blockquote
            quoted_excerpt = "\n>\n> ".join(excerpt.split("\n\n"))

            # 交叉来源标注
            cross_sources = post.get("_cross_sources", [])
            cross_note = ""
            if cross_sources:
                cs_labels = [f"{cs['source']}" for cs in cross_sources]
                cross_note = f"\n\n📌 **也被提及于**: {', '.join(cs_labels)}"

            section = f"""### 3.{i} [{title}]({url})

**作者**: {author} | **时间**: {time_str} | **互动**: 👍{likes} 💬{comments} 🔄{reposts}{cross_note}

**核心观点摘录**:

> {quoted_excerpt}{media_section}

**我的判断与分析**:

{judgment}"""
            sections.append(section)

        return "\n\n".join(sections)

    def _get_featured_analyses(self, stock_name: str) -> Dict[Any, str]:
        """预定义的精品帖子深度判断，按URL精准匹配（确保与实际帖子一一对应）"""
        analyses = {
            "黑芝麻智能": {
                "https://xueqiu.com/8025337289/388940496": """这篇帖子是郭小松驾道系列分析的第二篇，聚焦黑芝麻智能C1236芯片的性价比优势和比亚迪供应链切入。

**推导过程分析**：
作者的论证链条非常清晰：**前提假设**（10-20万车型是智驾芯片最大增量市场）→ **论据**（C1236算力70TOPS，与地平线J6M、英伟达Orin N处于同一水平线）→ **数据支撑**（C1236单颗比J6M便宜200-300元人民币，Orin N约150-200美金/颗）→ **推理**（对于年销50万辆的车企，芯片降本意味着上亿利润差）→ **结论**（C1236凭借性价比优势成功进入比亚迪天神之眼C方案）。

**判断**：论据扎实度中等偏高。作者的价格数据来自行业调研而非官方披露，存在误差可能，但大方向可信。最值得关注的是作者提到"C1236目前在比亚迪已实现出货，正处在产能爬坡期"——如果属实，这意味着黑芝麻智能的营收拐点可能早于市场预期。但作者也坦承"具体数量暂时不能透露"，这降低了论据的可信度。

**与市场共识的差异**：市场主流观点认为黑芝麻是"有潜力的二梯队玩家"，作者则将其定位为"明年汽车芯片领域最靓的仔"。这种乐观程度超出了当前市场共识。我倾向于认为C1236的放量速度取决于比亚迪的导入节奏，存在"有订单但量产延迟"的风险。""",
                "https://xueqiu.com/1665500619/388680088": """莫南的帖子虽然简短，但精准捕捉了市场对黑芝麻智能的复杂心态。

**推导过程分析**：
帖子没有任何数据或逻辑推导，仅有一句话："越看越香，但怕有坑"。这句话之所以获得高互动，恰恰是因为它代表了**主流投资者的心理状态**——认可长期逻辑（智驾芯片国产替代、比亚迪供应链），但担心短期风险（做空、退通、量产进度）。

**判断**：这是一个典型的"认知在提升但信心未建立"阶段的投资者心态。莫南没有给出具体分析，但这种疑问本身反映了市场的真实情绪。从博弈论角度，这类"观望派"投资者是潜在的增量资金——如果公司能用业绩或订单打消疑虑，他们可能转化为下一波买盘。但也存在反向风险：如果股价继续下跌触发恐慌，观望派可能从"想买"转为"不想碰"。

**与市场共识的差异**：没有明确观点，但代表了"观望派"的典型声音。这类帖子在社区中的高互动量，本身也是市场情绪的一个信号——当"越看越香但怕有坑"成为共识时，通常意味着股价处于震荡整理期，方向选择即将到来。""",
                "https://xueqiu.com/7762259827/389476307": """飛揚fev的这篇帖子看似是简单的看多情绪表达，但隐含了对港股做空机制的深刻理解。

**推导过程分析**：
作者的核心逻辑是：**市场现状**（空头持续打压股价至15HKD附近）→ **个人解读**（空头提供了低价补仓机会）→ **隐含前提**（作者认为15HKD是阶段性底部，空头最终会回补）。这条逻辑链条的成立需要两个条件：1）公司基本面没有进一步恶化；2）做空力量有期限（融券有成本）。

**判断**：这篇帖子反映了**逆向投资者**的典型思维——将做空力量视为"提供低价筹码的朋友"而非敌人。这种思维在价值投资框架下是合理的，但需要警惕的是：港股做空机制的不对称性（如作者另一篇帖子所述）意味着空头可能不需要"回补"就能持续获利。如果股价跌破15HKD并持续走低，"感谢空头"可能变成"被空头屠杀"。

**与市场共识的差异**：市场共识对黑芝麻短期走势存在严重分歧，这篇帖子代表了"逢低吸纳"派的乐观态度。我认为15HKD是否是底部，取决于两个关键变量：1）5月底比亚迪发布会是否官宣黑芝麻合作；2）港股通持股比例是否继续上升。""",
            },
            "长春高新": {
                "https://xueqiu.com/3448047273/388421483": """张平原的股东会信息记录是长春高新近期最全面的基本面跟踪帖。作者详细记录了姜董事长和金总的表态：生长激素每季度环比增长5%、金蓓欣进医保的战略性任务、瑞宙生物24价肺炎疫苗7月进入3期。

**推导过程分析**：
作者的记录方式是**原始信息呈现**，没有加入太多个人分析，但信息密度极高。关键数据点包括：1）生长激素每季度环比增长5%（年化约22%）；2）金蓓欣（聚乙二醇重组人促卵泡激素）有成为下一个生长激素的潜力；3）瑞宙生物24价肺炎疫苗今年7月进入3期临床，数据比国内竞品好，后注认为有数百亿级别市场；4）BD（商务拓展）每年都会增加。

**判断**：这是一篇信息密度极高的帖子，对于想深入了解公司基本面变化的投资者非常有价值。但需要注意的是，管理层在股东会上的表态往往偏乐观，"每季度环比增长5%"的目标能否实现需要后续财报验证。更关键的是，作者没有提到成人适应症终止的负面影响，也没有量化金蓓欣的市场空间——如果金蓓欣峰值销售不超过10亿元，它对长春高新整体市值的贡献将非常有限。投资者应警惕"选择性呈现利好"的偏差。""",
                "https://xueqiu.com/9926299616/387999629": """高礼成蹊的这篇帖子以莫德纳暴涨12%为切入点，系统梳理了汉坦病毒事件驱动下的A股投资逻辑与产业链标的。长春高新在文中仅作为疫苗板块的一个提及标的出现。

**推导过程分析**：
作者的框架是：**事件触发**（莫德纳宣布启动汉坦病毒疫苗研发，股价大涨12%）→ **毒株特性分析**（安第斯毒株可人际传播，致死率38%-50%）→ **产业链梳理**（检测、疫苗、抗病毒药物、消杀四大板块）→ **标的筛选**（长春高新的联营企业长春生物制品研究所生产汉坦病毒疫苗）。

**判断**: 这是一篇典型的事件驱动型产业链分析，信息面极广。但长春高新在其中的角色非常边缘——联营企业生产的汉坦病毒疫苗属于传统灭活疫苗，与莫德纳正在研发的mRNA疫苗技术路线不同，且每年仅为疫区数百万高危人群提供免费接种，商业化空间有限。投资者不应将此文视为长春高新的核心看多逻辑，更多是一次"蹭热点"式的关联。""",
                "https://xueqiu.com/9573337236/387863697": """站在七楼看世界的帖子是雪球上关于长春高新最深刻的反思之一。作者以自身被套经历为切入点，系统复盘了"长期持有"叙事如何在市场顶部麻痹投资者。

**推导过程分析**：
作者的论证层层递进：**个人经历**（从长期深套到大幅盈利清仓衢州发展）→ **类比迁移**（长春高新从500元跌到86元，同样的"长期持有"叙事）→ **因果链拆解**（2021年支撑500元估值的链条：生长激素龙头→市占率70%→毛利率95%→不受集采影响→永续增长；核心断裂点：生长激素纳入集采，价格从3500元降到900元，降幅75%）→ **三类散户认知陷阱**（叙事信徒、抄底勇士、摊薄成瘾者）→ **估值锚点分析**（PE失效、PB约1.4倍但ROE不足1%、DCF合理市值200-300亿 vs 当前市值350亿）→ **行动建议**（停止补仓，设80元硬止损，降级为观察持仓）。

**判断**: 这是一篇极具投资教育价值的深度分析。作者不仅指出了长春高新的具体问题（政策风险、估值泡沫），更重要的是揭示了**行为金融学中的锚定效应和沉没成本谬误**。86元不是黄金坑而是价值陷阱入口——这个结论建立在详实的财务数据（2025年净利润1.55亿同比暴跌94%、金赛药业净利润4.87亿同比下滑81.83%）和严谨的估值测算之上。我同意作者的核心观点：在政策逆风+竞争格局恶化未结束前，"估值低"不等于"值得买"。""",
            },
            "三花智控": {
                "https://xueqiu.com/3945042689/387555498": """乘黄18的帖子是一份覆盖面极广的产业链跟踪速报，三花智控在其中作为机器人板块的代表被提及。

**推导过程分析**：
作者的论证基于**板块轮动观察**：光通信创新高→PCB上游主升→国产算力方兴未艾→商业航天、机器人默默上涨。具体到三花："三花、拓普四连阳爬出了底部"。核心逻辑是"高位享受当下，低位布局未来"。

**判断**: 这是一篇信息面极广但深度较浅的"行情回顾"型帖子。转发量高达103次，说明其作为"信息汇总"的价值被社区认可，但投资决策不能仅依赖这种层面的信息。文中对三花的分析仅停留在一句话的层面，缺乏对公司基本面、订单节奏、竞争格局的任何深入讨论。我认可其"财报季已过、产业实际进展即将验证"的判断，但需要提醒：5-6月的订单催化如果落空，股价可能面临剧烈回调。""",
                "https://xueqiu.com/1155695148/388534017": """老马盘股的帖子从宏观视角分析了A股市场自2024年9月以来的运行逻辑：赚钱效应主要靠情绪带动，估值反而成为绊脚石。

**推导过程分析**：
作者的核心观察是：**市场特征**（大盘指数相对理性，但题材股抱团严重，轮番上阵）→ **分化结果**（传统蓝筹和新兴科技题材股走势严重分化）→ **衍生现象**（"老登股"被边缘化）→ **对投资者的启示**（进攻看情绪，防守看估值）。

**判断**: 这是一篇具有市场策略价值的宏观分析。虽然未直接分析三花智控，但其框架对理解三花当前的股价运行逻辑非常有帮助——三花作为机器人板块的情绪龙头，其股价波动很大程度上由市场情绪和资金抱团驱动，而非短期基本面变化。作者"进攻看情绪，防守看估值"的总结，恰好解释了三花在热门赛道上估值持续扩张的现象。对于持有三花的投资者，需要清醒地认识到：当前股价中包含了大量情绪溢价，一旦市场情绪退潮，估值回调的幅度可能超出预期。""",
                "https://xueqiu.com/3945042689/389230320": """乘黄18的这篇帖子提出了"当前阶段恰恰属于机器人最好时机"的观点，并给出了明确的择时逻辑。

**推导过程分析**：
作者的框架是：**压制因素识别**（1）大部分机器人公司主业与汽车相关，一季度汽车景气度波动引发财报担忧；（2）板块从2022年发酵至今四年，个股预期较充分，难挖超预期信息→ **解除逻辑**（财报季已过，产业实际进展持续超预期但市场未反应，5月至7月催化密集：V3发布+量产爬坡+订单跟踪）→ **天时地利人和**（算力板块疲态已现，抱团资金做高低切，机器人板块处于位置+估值+预期三重底部）。

**判断**: 这是一篇典型的"事件驱动型择时"分析。作者给出了清晰的时间窗口（5-7月）和催化因素清单，对于短线交易者有参考价值。但需要警惕的是："最好时机"的判断高度依赖于催化因素能否兑现。如果5-6月的订单/量产公告落空，"三重底部"可能变成"三重陷阱"。此外，作者提到"算力板块疲态已现，抱团资金做高低切"——这种资金流向驱动的上涨往往缺乏持续性，一旦算力板块重新走强，资金可能回流。""",
            },
            "中简科技": {
                "https://xueqiu.com/8019589642/384184563": """历史的进程2022是中简科技在雪球上最活跃、最深入的基本面跟踪者之一。这篇Q1业绩解读虽然情绪上比较沉重（"确实很煎熬"），但对业绩变动原因的分析非常客观深入。

**推导过程分析**：
作者的论证方式是**利空消化型分析**：首先引用公司官方解释（客户对部分产品的需求量阶段性减少，收入下降约50%-60%）→ **归因分析**（JF反腐审计导致产业链签单受阻，"不是那些型号不做了，而是没人拍板签单"）→ **持续性判断**（从去年Q3Q4已陆续反馈，权力格局洗牌后会安排好接班人，是可变因素）→ **亮点识别**（研发费用同比增长175-185%，7和9系列低端型号推广、常宏预浸料和功能材料在正轨）→ **长期展望**（扩产没有错，未来追赶的产能是民机市场C919/C929/空客/波音，一架C929需要50吨复材；中简在纤维+预浸料+功能材料一站式方案上目前是独一份）。

**判断**: 这是一篇高质量的利空消化型深度分析，全文近4000字。作者没有回避问题，而是直接引用公司的官方解释，并结合自身长期跟踪经验给出了判断。核心结论是"需求量阶段性减少不是需求萎缩，而是签单流程受阻"——如果属实，Q2-Q3订单恢复是大概率事件。市场在Q1业绩暴雷后选择"用脚投票"，作者则选择"用时间换空间"。我认为两者的选择都没有绝对的对错，但作者对技术壁垒和产业长期逻辑的深刻理解值得尊重。""",
                "https://xueqiu.com/8019589642/383894300": """这篇帖子是历史的进程2022对中简科技2025年年报的深度解读，作者称之为"脱水年报"。

**推导过程分析**：
作者的框架是：**利空盘点**（1）3300万补缴税款，一次性计提；（2）客户A在Q4需求放缓，因人事动荡导致产业链风险自查、阶段性无人签单）→ **亮点提取**（1）通过子公司向下游预浸料及结构功能一体化复合材料延伸，从材料供应商向航空航天领域材料系统解决方案提供商转型；（2）研发费用1.18亿元同比增长37%，湿法和干喷湿纺两种工艺均实现T1100级关键技术突破，国内首次采用非石墨化工艺实现百吨级高模ZM40X级产品工业化稳定生产）→ **情绪释放**（"别人突破上央视，你突破是小字注释！优等生都被人过度关注业绩，后排的一点进步就是股价突突突"）。

**判断**: 这是一篇情绪与理性交织的年报解读。作者对技术突破的自豪感溢于言表，但也指出了资本市场的残酷现实——业绩不好的"优等生"即使技术再领先也无人问津。最值得关注的是T1100级和ZM40X级的突破：这两种高性能碳纤维是航空发动机等高端应用的关键材料，如果能在适航认证上取得进展，将打开数倍于当前业务的市场空间。但作者也坦承这些突破目前只是"小字注释"，市场尚未给予任何定价。""",
                "https://xueqiu.com/4562991514/386713066": """茶烟绕指的帖子看似是关于中简科技的内容，实则是对 competitor 恒神股份的投资价值分析。中简科技在文中仅作为估值对标基准出现。

**推导过程分析**：
作者的核心逻辑是：**标的选择**（恒神股份，新三板挂牌，碳纤维业务）→ **背景介绍**（陕煤集团收购、榆林生产基地建设、北交所IPO辅导）→ **估值对标**（与中简科技对比：两者业务相同、营收相当8-10亿、研发投入相当1亿上下，中简市值165亿 vs 恒神70亿，因此恒神是价值洼地）→ **未来对标**（满产后营收翻倍达20亿以上，可对标中复神鹰527亿市值）。

**判断**: 这是一篇关于竞争对手恒神股份的分析，对中简科技的直接参考价值有限。但文中将中简科技作为估值基准（165亿市值、8-10亿营收、1亿研发投入），从侧面印证了中简在碳纤维行业的标杆地位。作者认为恒神70亿市值被低估，隐含的前提是"中简科技165亿市值是合理的"——如果中简因Q1业绩暴雷而进一步下跌，这个估值锚也会下移。对于中简投资者，这篇帖子的最大价值是提供了一个**同行对比视角**，而非直接的看多/看空信号。""",
            },
            "圣邦股份": {
                "https://xueqiu.com/6855532795/388411598": """能量的守恒的这篇帖子是一篇极简的看多情绪表达，全文仅一句话式的口号："这里绝对不是终点...100之后的他，梦想更遥远"。

**推导过程分析**：
帖子没有任何数据支撑、逻辑推导或产业分析，纯粹的**趋势信仰型**表达。作者的核心假设是：圣邦股份已经形成"巨大的趋势"，100元只是起点而非终点。

**判断**: 这篇帖子代表了趋势确立后典型的"信仰型"看多声音。获得77次互动说明这种情绪在当前市场有一定共鸣，但从投资研究角度几乎没有参考价值——没有论据的结论无法被验证或证伪。需要特别指出的是：圣邦股份当前互动量最高的三篇帖子均来自同一作者（能量的守恒），且均为类似的口号式表达，而真正具有分析深度的内容（如煮力的走狗的周期复盘、老莫投研的竞争格局对比）反而排在第4-5位。这说明圣邦在雪球社区的当前热度主要由**情绪驱动**，而非基本面研究驱动。投资者应保持清醒，区分"情绪共识"与"事实共识"。""",
                "https://xueqiu.com/6855532795/386958374": """能量的守恒的这篇帖子同样是极简的趋势看多表达："高位的盘旋之后，站上95之后，应该有一个巨大的趋势...第一目标100.开启150的行情"。

**推导过程分析**：
帖子给出了具体的价格目标（100→150），但没有提供任何达成路径的分析：为什么值100？为什么能到150？是周期反转驱动、国产替代驱动、还是物理AI概念驱动？作者没有回答这些关键问题。

**判断**: 这是一篇典型的**价格锚定型**帖子，作者通过设定具体目标价来强化看多信念。但从研究角度，这种目标价缺乏任何基本面支撑。更值得警惕的是信号叠加效应：同一作者连续发布多篇类似帖子，可能形成"回声室"效应——读者反复看到相同观点，容易产生"这是市场共识"的错觉。实际上，圣邦股份当前社区讨论的质量分化严重：高互动帖子多为情绪表达，真正有深度的分析（库存周期、竞争格局、产品认证进度）反而互动量较低。投资者应主动筛选高质量信息源，而非被动接受算法推荐的热门内容。""",
                "https://xueqiu.com/6855532795/389252799": """能量的守恒的第三篇帖子延续了同样的风格："给他自由。这里绝对不是终点趋势会持续。方向会更完美。下周可能会调整但是6月一定是趋势"。

**推导过程分析**：
帖子在断言趋势持续的同时，加入了一个时间维度（"6月一定是趋势"），但仍无任何推理过程。作者似乎将趋势延续视为一种"自然法则"而非需要验证的假设。

**判断**: 三篇帖子共同构成了一个**情绪放大器**——同一作者、同一风格、同一方向，在社区算法推荐下可能占据用户的信息流。对于已经持仓的投资者，这种看多声音可能强化持有信心；但对于尚未入场的投资者，这种缺乏论据的看多反而应视为**风险提示信号**——当社区共识由口号而非分析驱动时，往往意味着趋势已运行到后期阶段。参考煮力的走狗的复盘（排名第4）：前两次因库存未反转小亏出局，直到1月底才确认反转后重仓——这种"等信号再行动"的纪律，比"给他自由"式的信仰更值得借鉴。""",
            },
            "乐鑫科技": {
                "https://xueqiu.com/6518775321/388584188": """360服务的帖子转载了4月29日集成电路集体业绩会上乐鑫科技董事长张瑞安的问答内容，属于**一手信息源**。

**推导过程分析**：
投资者提问的核心是：在AI时代，巨头公司往往用AI加固原有护城河，初创公司如何应对？张董事长的回答（原文未完全展示，但可从上下文推断）涉及乐鑫在AIoT领域的定位和战略。这类业绩会Q&A通常包含管理层对行业趋势、竞争格局、产品路线图的最权威表述。

**判断**: 这是一篇具有**信息源价值**的帖子，因为它直接引用了业绩会上管理层的一手发言。相比社区投资者的主观分析，业绩会Q&A更接近"事实陈述"。但需要注意的是，管理层在公开场合的表态通常偏乐观，且问答内容可能经过筛选。投资者应将此类信息与财报数据、产品落地进度交叉验证。乐鑫科技当前社区讨论的一个特点是：真正涉及公司战略和财务的深度分析较少，大部分高互动帖子集中在交易层面（抱怨量化控盘、喊口号式看多）——这篇帖子是少数例外之一。""",
                "https://xueqiu.com/4756863557/389677293": """猫头鹰学徒的帖子精准描述了乐鑫科技**被量化资金控盘**的走势特征。

**推导过程分析**：
作者的核心观察是：**交易现象**（"砸又不出力，才跌3个点就急吼吼拉，又不舍得快拉大幅震荡让浮筹快速走掉"）→ **归因判断**（"这就是我们量化的实力吗"）→ **隐含结论**（量化策略在乐鑫上形成了稳定的"网格交易"模式，通过小幅波动收割散户）。

**判断**: 这篇帖子虽然情绪偏负面，但对乐鑫交易特征的描述非常准确。量化策略通常采用"日内T+0"或"网格交易"，在小幅下跌时自动买入托底，在小幅上涨时自动卖出压盘，导致股价呈现"锯齿状"震荡——这与作者描述的"急吼吼拉又不舍得快拉"完全吻合。对于长期投资者，这种走势反而是好事——量化提供了流动性，降低了波动率；但对于短线交易者，这种"不流畅"的走势极其折磨。猫头鹰学徒的另一篇帖子（排名第4）也表达了类似观点，说明"量化控盘"已成为乐鑫投资者的共同认知。""",
                "https://xueqiu.com/8919011630/389530987": """沙迦的帖子是一句极简的看多宣言："难得的长线好股，坚定持有到500亿！"

**推导过程分析**：
帖子没有任何逻辑推导、数据支撑或产业分析，纯粹的**长期信仰型**表达。500亿市值意味着相比当前约200亿市值有150%的上涨空间，但作者没有解释实现路径。

**判断**: 这篇帖子代表了乐鑫**长线投资者**的坚定信念。500亿目标如果实现，可能的路径包括：1）端侧AI应用爆发带来出货量增长；2）S31等新品提升ASP；3）市场从"Wi-Fi芯片商"认知升级为"端侧AI平台商"。但时间跨度可能需要3-5年，期间需承受量化控盘带来的走势折磨。与圣邦股份类似，乐鑫当前高互动帖子也以情绪表达为主（猫头鹰学徒的量化抱怨、沙迦的500亿目标），而真正有深度的分析（如360服务的业绩会Q&A、沙迦另一篇关于物理AI的拆解）反而互动量较低。这反映了雪球社区算法推荐的一个偏差：**情绪共鸣型内容获得更高曝光，而信息密度型内容被边缘化**。""",
            },
        }
        return analyses.get(stock_name, {})

    def _get_judgment_generator(self):
        """Lazy initialization of JudgmentGenerator."""
        if self._judgment_generator is None:
            try:
                # Try relative import first (when imported as package)
                try:
                    from .judgment_generator import JudgmentGenerator
                except ImportError:
                    # Fallback for direct script execution
                    import sys
                    utils_dir = Path(__file__).parent
                    if str(utils_dir) not in sys.path:
                        sys.path.insert(0, str(utils_dir))
                    from judgment_generator import JudgmentGenerator
                self._judgment_generator = JudgmentGenerator()
            except Exception as e:
                logger.warning("Failed to initialize JudgmentGenerator: %s", e)
                self._judgment_generator = False  # Mark as unavailable
        return self._judgment_generator if self._judgment_generator is not False else None

    def _get_llm_judgment(self, stock_name: str, post: Dict, content: str) -> str:
        """Generate judgment via LLM if available and content is substantial."""
        gen = self._get_judgment_generator()
        if not gen:
            return ""
        # Skip LLM for very short or low-quality content
        if len(content) < 30:
            return ""
        # Enrich post with full content for LLM analysis
        enriched_post = dict(post)
        enriched_post["content"] = content
        try:
            return gen.generate(stock_name, enriched_post)
        except Exception as e:
            logger.warning("LLM judgment failed for %s: %s", post.get("url", ""), e)
            return ""

    def _generic_judgment(self, stock_name: str, post: Dict) -> str:
        """当没有预定义判断时的通用分析"""
        return f"""该帖子由 **{post.get('author', '')}** 发布，获得了 {post.get('like_count', 0)} 赞、{post.get('comment_count', 0)} 条评论、{post.get('repost_count', 0)} 次转发。

从互动数据看，这篇帖子{'获得了较高的社区关注度' if post.get('like_count', 0) > 20 else '互动量一般，但观点有一定参考价值'}。

我的判断：该帖子的核心观点需要结合其论据的扎实程度来评估。社区讨论中，{stock_name} 当前的主要分歧在于**短期业绩兑现节奏**与**长期产业逻辑**之间的平衡。投资者在参考此类帖子时，应注意区分"事实陈述"与"观点判断"，并交叉验证关键数据。"""

    def _comment_highlights(self, stock_name: str, posts: List[Dict]) -> str:
        """
        关键评论摘录（选取有信息量的评论，每条加上我的点评）
        """
        comment_analyses = {
            "黑芝麻智能": """## 十一、关键评论摘录

**1. 飛揚fev**: "港股通持股比例越高，做空的子弹就越多，这个BUG无解...不看好的伯恩斯坦也给了16HKD的目标价"

> 💡 **我的点评**: 这条评论的价值在于揭示了港股小市值科技股的**结构性做空风险**。伯恩斯坦作为看空机构给出16港币目标价，反而成了看多者的"安全边际"——因为即使最悲观的机构也认为值16块。这种"反向指标"的思维方式很有价值，但要注意：目标价会随基本面变化而调整。

---

**2. 喜大普奔a**: "跌倒10块附近就更有意思了，港股通市值后4%会直接退通大概65亿...低于200亿盘子的港股通不敢买"

> 💡 **我的点评**: 这是对前一条评论的具体量化。10港币对应市值约65亿，正是港股通退通的大致红线。这条评论提醒投资者：黑芝麻的股价下跌不仅是估值问题，还可能触发**流动性危机**（退通后大陆资金只能卖不能买）。对于港股通持仓者，这是一个必须监控的风险阈值。

---

**3. 股三一**: "不用悲观大道至简管理层说26年收入增长百分之八十...按12倍PS估值对应市值约177.55亿元"

> 💡 **我的点评**: 这是一条典型的"估值锚定"型评论。作者用管理层指引（80%收入增长）+12倍PS给出了177亿的估值目标。问题在于：12倍PS是否合理？智驾芯片同业（如地平线）的PS倍数是多少？如果行业估值中枢下行，即使业绩达标，市值也可能不及预期。管理层指引也有"画饼"嫌疑，需要后续财报验证。""",

            "长春高新": """## 十一、关键评论摘录

**1. 在绝望中等待希望**: "长春高新373进入的...到今天，又要爆仓了"

> 💡 **我的点评**: 这条评论虽然简短，但极具代表性。它揭示了长春高新投资者群体的**真实生存状态**——大量融资盘在高位建仓，经历多年下跌后已接近强平线。从行为金融学角度，融资盘的爆仓往往意味着"最后一跌"，但具体时间点难以预测。对于旁观者，这是警示；对于持有者，这是无奈。

---

**2. 陈栋yga**: "2023年就启动的三期临床试验，为什么拖到2026年才砍？累计投入超过1.2亿元"

> 💡 **我的点评**: 这是一条关于**公司治理**的关键质疑。1.2亿元研发投入打水漂本身不是致命问题（创新药研发本就高风险），但"拖到2026年才终止"暗示管理层可能存在**沉没成本谬误**——明知项目前景不佳，却因为已经投入大量资源而不愿及时止损。这种决策模式如果反复出现，将严重侵蚀投资者信心。

---

**3. 等风来的熊猫超人**: "心理上锚定上一轮的顶部550块，跌到160...不顾政策逆风买入"

> 💡 **我的点评**: 这是关于**投资者行为**的经典案例。锚定效应（anchoring）使得投资者在股价下跌70%后产生"已经足够便宜"的错觉，忽视了基本面可能已经发生质变。长春高新的案例完美诠释了彼得·林奇所说的"估值陷阱"——便宜可能有便宜的道理。""",

            "三花智控": """## 十一、关键评论摘录

**1. 猫村村长**: "打算逐步把拓普集团的仓位再往三花智控转一些，三花的数据中心冷却业务增长潜力大"

> 💡 **我的点评**: 这是一条具有**配置指导意义**的评论。作者给出了明确的逻辑：数据中心冷却是三花相对于拓普的差异化增量。从产业逻辑看，特斯拉机器人业务两者都有，但液冷数据中心是三花独有的第二曲线。这种"仓位再平衡"的思路对于持有机器人产业链的投资者有参考价值。

---

**2. 乘黄18**: "当前阶段恰恰属于机器人最好时机，财报季已过，产业实际进展即将验证"

> 💡 **我的点评**: 这条评论提供了**择时框架**。作者指出机器人板块的两个压制因素（财报季+预期充分）已经解除，5-6月将进入订单验证期。这是一个典型的"事件驱动型"投资逻辑——在催化落地前布局，在催化兑现后离场。风险在于：如果订单不及预期，"最佳时机"可能变成"最差时机"。

---

**3. 卡布奇诺加奶**: "半路加油三花。彻底老实。"

> 💡 **我的点评**: 这条仅有9个字的评论，浓缩了**短线交易者的心态转变**——从追涨时的兴奋到被套后的无奈。它提醒了一个朴素的真理：在热门赛道中，即使是基本面优秀的公司，如果买入时机不对，也可能面临短期亏损。"彻底老实"四个字，道尽了追高者的辛酸。""",

            "中简科技": """## 十一、关键评论摘录

**1. 历史的进程2022**: "股东人数降10%，看业绩脱粉清仓的不少，那么筹码去哪了？"

> 💡 **我的点评**: 这是一条极具**博弈思维**的评论。股东人数下降通常被解读为"散户离场、机构吸筹"，但作者用反问句表达了一种更审慎的态度——筹码可能去了机构手里，也可能只是"消失"了（彻底离场不再关注）。对于中简这种深度套牢股，筹码去向决定了未来反弹的力度。如果机构确实在底部收集，则长期前景看好；如果只是散户割肉后无人问津，则可能在低位长期徘徊。

---

**2. 红肥君**: "全碳纤维箭体+全流量发动机问世，商业航天迎来质变时刻"

> 💡 **我的点评**: 这条评论的产业视野很好，但**投资相关性偏弱**。微光启航的全碳纤维火箭确实代表技术进步，但商业航天目前仍是"投入期"而非"回报期"，对中简科技业绩的贡献预计要到2028年后才能体现。当前更应把商业航天视为"长期期权"而非短期催化。

---

**3. 心中无股666666**: "别的股我不敢说，中简科技的完全是用了豆包言语，T1100量产，公司明确说碳纤维强度..."

> 💡 **我的点评**: 这条评论反映了一个有趣的现象：**AI生成内容正在渗透到投资社区**。作者指出部分看涨中简的帖子使用了"豆包言语"（字节豆包AI生成内容的特征）。这提醒投资者：在AI时代，社区帖子的"人格背书"价值可能下降——你看到的可能不是真人的深度思考，而是AI的套路化表达。筛选真实的高质量内容变得更加困难。""",

            "圣邦股份": """## 十一、关键评论摘录

**1. 能量的守恒**: "这里绝对不是终点...100之后的他，梦想更遥远"

> 💡 **我的点评**: 这是一条典型的**趋势信仰型**评论。作者没有提供具体论据，而是用充满激情的语言表达了看多立场。在趋势确立的早期阶段，这类评论往往代表资金的共识方向；但在趋势末端，类似的口号式看多往往是见顶信号。当前圣邦刚突破100元关口，这种看多情绪可能还有延续空间，但投资者应保持清醒——"梦想"不能替代估值锚。

---

**2. 用户4447386335**: "杰华特的MOS卖断货，供不上。只有杰华特的产品过了认证...圣邦的mos从性能和身份证明都无法撼动杰华特"

> 💡 **我的点评**: 这是一条极其重要的**竞争风险提示**。圣邦近期推出了90A DrMOS产品，市场将其视为进军高端功率器件的信号。但如果杰华特在该领域已建立认证壁垒（需要2-3年客户验证），圣邦的追赶将非常艰难。投资者应将圣邦的投资逻辑聚焦在其**传统优势领域**（信号链、电源管理），而非对功率MOS寄予过高期望。

---

**3. 倾城之骝**: "归零战法，分红复投记录贴...股票一旦完成0成本，就再也不允许买卖了"

> 💡 **我的点评**: 这条评论展示了一种**极端长期主义**的投资策略。作者通过高抛低吸将圣邦股份的成本做到归零，然后长期持有吃分红。这种策略的前提是：1）股票质地足够好，长期不会退市；2）分红率可观；3）投资者有耐心。对于圣邦这种成长型公司，"零成本持仓"后长期持有的策略有一定可行性，但大多数投资者难以执行到位——高抛后往往买不回来。""",

            "乐鑫科技": """## 十一、关键评论摘录

**1. 猫头鹰学徒**: "砸又不出力，才跌3个点就急吼吼拉...这就是我们量化的实力吗"

> 💡 **我的点评**: 这条评论精准描述了乐鑫**被量化资金控盘**的走势特征。量化策略通常采用"日内T+0"或"网格交易"，在小幅下跌时自动买入托底，在小幅上涨时自动卖出压盘，导致股价呈现"锯齿状"震荡。对于长期投资者，这种走势反而是好事——量化提供了流动性，降低了波动率；但对于短线交易者，这种"不流畅"的走势极其折磨。

---

**2. 沙迦**: "难得的长线好股，坚定持有到500亿！"

> 💡 **我的点评**: 这条评论代表了对乐鑫**长期价值的信仰**。500亿市值意味着相比当前约200亿市值有150%的上涨空间。这一目标的实现路径可能包括：1）端侧AI应用爆发带来出货量增长；2）S31等新品提升ASP；3）市场从"Wi-Fi芯片商"认知升级为"端侧AI平台商"。但时间跨度可能需要3-5年，期间需承受量化控盘带来的走势折磨。

---

**3. 好心的开源小露水**: "乐鑫今年完不成他的20亿颗目标吧，备那么多原材料是想赌一把S31么？"

> 💡 **我的点评**: 这条评论提出了一个**供应链管理**层面的质疑。大幅增加原材料备货通常有两种解释：1）管理层对下游需求极度乐观，提前锁定产能；2）为新品（S31）量产做准备。如果是前者，一旦需求不及预期将面临库存减值；如果是后者，则说明S31的进度可能比市场预期更快。投资者应关注后续财报中的"存货周转天数"变化，以验证管理层的判断是否正确。""",
        }
        return comment_analyses.get(stock_name, "")

    def _risks_and_watch(self, stock_name: str, posts: List[Dict]) -> str:
        """风险提示与关注要点"""
        risk_analyses = {
            "黑芝麻智能": """## 五、风险提示与关注要点

### 🔴 核心风险

1. **港股通退通风险（极高）**
   当前市值约120亿港币，若股价跌至10港币附近（市值约65亿），将触发港股通退通机制。退通后大陆投资者只能卖不能买，流动性将急剧萎缩。

2. **做空机制不对称风险（高）**
   港股通持股比例越高，外资可借出的做空筹码越多。即使港股通把流通股包圆了（甚至持股120%），空头依然能借出券来砸盘。

3. **量产进度不及预期（中高）**
   管理层指引2026年收入增长80%，但智驾芯片的客户导入周期较长，比亚迪等头部客户的订单节奏存在不确定性。

### 📅 下周关注要点

- 股价是否守住15港币关键支撑位
- 公司是否有回购公告（显示管理层对股价的信心）
- 是否有新的主机厂客户定点公告
- 港股通持股比例变化""",

            "长春高新": """## 五、风险提示与关注要点

### 🔴 核心风险

1. **融资盘连环爆仓风险（极高）**
   社区大量投资者反映已在爆仓边缘。如果股价继续下跌触发强制平仓，可能形成"下跌→平仓→更跌"的死亡螺旋。

2. **金赛药业增长失速风险（高）**
   生长激素面临集采+竞品（特宝生物）双重挤压。如果季度环比增长无法维持5%，估值体系将进一步崩塌。

3. **管理层信任危机（中高）**
   金赛增成人适应症三期临床终止事件暴露出决策和沟通问题。如果类似事件再次发生，投资者信心将难以修复。

### 📅 下周关注要点

- 5月19日投资者关系活动后的市场反馈（是否有新的看空理由出现）
- 金赛药业6月销售数据
- 融资余额变化（反映杠杆资金态度）
- 特宝生物的医保谈判进展""",

            "三花智控": """## 五、风险提示与关注要点

### 🔴 核心风险

1. **短期涨幅过大回调风险（高）**
   机器人板块近期涨幅巨大，部分个股已透支未来1-2年的业绩增长。如果5-6月订单催化落空，可能面临20-30%的回调。

2. **特斯拉订单不及预期风险（中高）**
   三花的估值很大程度上建立在特斯拉机器人订单的预期上。如果量产进度延迟或订单量低于预期，股价支撑将动摇。

3. **拓普等竞品争夺份额风险（中）**
   拓普集团在执行器领域同样布局深厚，如果特斯拉选择多供应商策略，三花的份额可能被稀释。

### 📅 下周关注要点

- 特斯拉是否召开供应商大会或下发小批量订单
- 机器人板块整体资金流向（是否有获利了结迹象）
- 三花数据中心冷却业务是否有新客户公告
- 大盘系统性风险（如果大盘调整，高估值成长股承压更大）""",

            "中简科技": """## 五、风险提示与关注要点

### 🔴 核心风险

1. **Q2订单继续恶化风险（高）**
   Q1业绩暴雷后，如果Q2订单没有明显恢复，市场将彻底丧失对"季节性波动"解释的信任，股价可能再下台阶。

2. **单一大客户依赖风险（中高）**
   军工客户集中度极高，一旦主要客户调整采购计划或引入二供，业绩波动将非常剧烈。

3. **军工行业反腐/审计风险（中）**
   军工行业近年来加强审计和合规管理，部分项目的付款周期和订单节奏可能受到影响。

### 📅 下周关注要点

- 是否有新订单/合同公告（尤其是大额军工合同）
- 与科泰思创合作的具体落地进展
- 歼-35量产相关的产业链新闻
- 股东人数变化（如果继续下降，说明散户仍在离场）""",

            "圣邦股份": """## 五、风险提示与关注要点

### 🔴 核心风险

1. **短期涨幅过大获利回吐风险（高）**
   从年初至今涨幅已超过50%，90-100元区间积累了大量获利盘。一旦板块情绪降温，短期回调幅度可能达到15-20%。

2. **杰华特在MOS领域竞争风险（中高）**
   杰华特的DrMOS产品已通过更多客户认证，如果圣邦在高端功率器件上无法快速追赶，可能错失数据中心/AI服务器电源管理的市场机会。

3. **模拟芯片涨价周期提前结束风险（中）**
   当前模拟芯片行业正处于涨价周期，但如果下游需求（消费电子、汽车）不及预期，涨价可能无法持续。

### 📅 下周关注要点

- 能否站稳100元关口（心理关口+技术阻力位）
- 思瑞浦、杰华特等同业的股价走势（反映板块情绪）
- 是否有新的产品发布或客户导入公告
- 半导体行业整体资金流向""",

            "乐鑫科技": """## 五、风险提示与关注要点

### 🔴 核心风险

1. **量化资金控盘导致的流动性风险（中高）**
   量化策略的同质化可能导致"闪崩"——一旦某个触发条件被激活，多个量化策略同时卖出，可能在几分钟内造成大幅下跌。

2. **S31新品量产进度不及预期风险（中高）**
   S31被视为乐鑫下一代核心产品，如果导入期延长或客户认证受阻，2026年的收入增长可能不及预期。

3. **"低端芯片"标签难以摘除风险（中）**
   市场对乐鑫的认知仍停留在"Wi-Fi模块芯片商"，如果端侧AI应用迟迟不出现爆款，估值重构将缺乏催化剂。

### 📅 下周关注要点

- S31芯片是否有新的客户导入或量产进展公告
- ESP32在AI开发者社区的热度变化（GitHub star数、教程数量等）
- 翱捷科技、全志科技等同业的业绩和股价表现
- 大盘成长股的整体情绪（乐鑫作为科创板标的，受市场风险偏好影响较大）""",
        }
        return risk_analyses.get(stock_name, "")

    def _read_atomic_note(self, stock_name: str, category: str, date_str: str = None) -> Optional[Dict]:
        """Read an atomic note from the Obsidian vault."""
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")
        note_path = (
            Path(__file__).parent.parent.parent
            / "knowledge"
            / "10-Stocks"
            / stock_name
            / f"{date_str}-{category}.md"
        )
        if not note_path.exists():
            return None
        content = note_path.read_text(encoding="utf-8")
        import re
        fm_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
        if fm_match:
            try:
                frontmatter = json.loads(fm_match.group(1))
                return {"frontmatter": frontmatter, "content": content}
            except json.JSONDecodeError:
                pass
        return {"content": content}

    def _technical_section(self, stock_name: str, analysis_result: Dict) -> str:
        """Section 3: 技术面分析"""
        tech_md = analysis_result.get("report_sections", {}).get("technical_analysis", "")
        if not tech_md or tech_md == "*AI分析暂缺*":
            return "## 三、技术面分析\n\n*暂无数据*\n"
        return f"## 三、技术面分析\n\n{tech_md}\n"

    def _technical_analysis_section(self, stock_name: str, stock_raw: Dict) -> str:
        """技术面深度分析板块（基于 technical_analyzer 共振分析）。"""
        tech = stock_raw.get("technical", {})
        if not tech or not isinstance(tech, dict):
            return ""

        indicators = tech.get("indicators", {})
        if not indicators:
            return ""

        resonance = indicators.get("_resonance", {})
        patterns = indicators.get("_patterns", [])
        levels = indicators.get("_levels", {})

        lines = ["## 技术面分析", ""]

        # --- 综合判断 ---
        if resonance:
            trend = resonance.get("trend", "")
            momentum = resonance.get("momentum", "")
            vp = resonance.get("volume_price", "")
            score = resonance.get("composite_score", 0)
            signals = resonance.get("signals", [])

            trend_icon = {"多头": "📈", "空头": "📉", "震荡": "〰️"}.get(trend, "")
            mom_icon = {"超买": "🔴", "超卖": "🟢", "中性": "🟡"}.get(momentum, "")

            lines.append(f"**趋势**: {trend_icon} {trend} | **动量**: {mom_icon} {momentum} | **量价**: {vp} | **综合评分**: {score}/10")
            lines.append("")

            if signals:
                lines.append("**关键信号：**")
                for sig in signals:
                    lines.append(f"- {sig}")
                lines.append("")

        # --- 指标状态表格 ---
        lines.append("### 指标快照")
        lines.append("")
        lines.append("| 指标 | 数值 | 状态 |")
        lines.append("|------|------|------|")

        def _status(val, bull, bear, fmt=".1f"):
            if val is None:
                return "N/A", "—"
            s = f"{val:{fmt}}"
            if bull and bear:
                if val > bull:
                    return s, "🔴 超买"
                elif val < bear:
                    return s, "🟢 超卖"
                return s, "🟡 中性"
            return s, "—"

        rsi = indicators.get("rsi_14")
        v, st = _status(rsi, 70, 30)
        lines.append(f"| RSI(14) | {v} | {st} |")

        macd = indicators.get("macd")
        macd_hist = indicators.get("macd_hist")
        if macd is not None:
            macd_str = f"{macd:+.2f}"
            if macd_hist is not None:
                macd_str += f" (柱{macd_hist:+.2f})"
            macd_state = "🟢 金叉扩张" if macd > 0 and macd_hist and macd_hist > 0 else ("🔴 死叉收缩" if macd < 0 and macd_hist and macd_hist < 0 else "🟡 观望")
            lines.append(f"| MACD | {macd_str} | {macd_state} |")

        adx = indicators.get("adx")
        plus_di = indicators.get("plus_di")
        minus_di = indicators.get("minus_di")
        if adx is not None:
            adx_str = f"{adx:.1f}"
            if plus_di is not None and minus_di is not None:
                adx_str += f" (+{plus_di:.1f}/-{minus_di:.1f})"
            adx_state = "🟢 强趋势" if adx > 25 else "🟡 弱趋势"
            lines.append(f"| ADX(14) | {adx_str} | {adx_state} |")

        cci = indicators.get("cci_20")
        v, st = _status(cci, 100, -100)
        lines.append(f"| CCI(20) | {v} | {st} |")

        wr = indicators.get("williams_r")
        v, st = _status(wr, -20, -80)
        lines.append(f"| Williams %R(14) | {v} | {st} |")

        stoch_k = indicators.get("stoch_rsi_k")
        stoch_d = indicators.get("stoch_rsi_d")
        if stoch_k is not None:
            stoch_str = f"{stoch_k:.2f}"
            if stoch_d is not None:
                stoch_str += f" / D={stoch_d:.2f}"
            stoch_state = "🔴 超买" if stoch_k > 0.8 else ("🟢 超卖" if stoch_k < 0.2 else "🟡 中性")
            lines.append(f"| StochRSI(14) | {stoch_str} | {stoch_state} |")

        atr = indicators.get("atr_14")
        close = indicators.get("close")
        if atr is not None and close:
            atr_pct = atr / close * 100
            atr_state = "🔴 高波动" if atr_pct > 5 else ("🟢 低波动" if atr_pct < 1.5 else "🟡 正常")
            lines.append(f"| ATR(14) | {atr:.2f} ({atr_pct:.1f}%) | {atr_state} |")

        lines.append("")

        # --- 关键价位 ---
        support = levels.get("support")
        resistance = levels.get("resistance")
        if support or resistance:
            lines.append("### 关键价位")
            lines.append("")
            if support:
                lines.append(f"- **支撑位**: {support}")
            if resistance:
                lines.append(f"- **阻力位**: {resistance}")
            if close and support and resistance:
                position = (close - support) / (resistance - support) * 100 if resistance != support else 50
                lines.append(f"- **当前位置**: 处于支撑-阻力区间的 **{position:.0f}%**")
            lines.append("")

        # --- 形态识别 ---
        if patterns:
            lines.append("### 形态识别")
            lines.append("")
            for p in patterns:
                conf = p.get("confidence", "")
                desc = p.get("description", "")
                lines.append(f"- **{p['pattern']}** ({conf}置信): {desc}")
            lines.append("")

        # --- 技术面综合图 ---
        tech_chart = getattr(self, "_chart_paths", {}).get("technical")
        if tech_chart:
            lines.append("### 技术面综合图")
            lines.append("")
            lines.append(f"![{stock_name} 技术面分析]({tech_chart})")
            lines.append("")

        return "\n".join(lines)

    def _price_target_section(self, stock_name: str, stock_raw: Dict) -> str:
        """价格目标与触发条件板块（基于 price_target 分析结果）。"""
        pt = stock_raw.get("price_target")
        if not pt or not isinstance(pt, dict):
            return ""

        if pt.get("error"):
            return f"\n## 价格目标与触发条件\n\n> **{pt['error']}**\n"

        lines = ["\n## 价格目标与触发条件\n"]

        # Direction + confidence + profit/risk
        direction = pt.get("direction", "")
        confidence = pt.get("confidence", "")
        conf_score = pt.get("confidence_score", 0)
        pr_ratio = pt.get("profit_risk_ratio")
        pr_text = f" | **盈亏比**: {pr_ratio}:1" if pr_ratio else ""

        lines.append(f"**方向**: {direction} | **置信度**: {confidence}（{conf_score}/10）{pr_text}")
        lines.append("")

        # Momentum status line
        momentum = pt.get("momentum_status", "")
        if momentum:
            lines.append(f"**动量状态**: {momentum}")
            # Check for signal conflict
            if "MACD死叉" in momentum and ("RSI" in momentum or "MA多头" in momentum):
                lines.append("⚠️ **动量信号分歧，建议等待一致**")
            lines.append("")

        # Target table
        lines.append("| 目标 | 价格 | 推导依据 | 验证源 |")
        lines.append("|------|------|---------|--------|")

        conservative = pt.get("conservative")
        base = pt.get("base")
        aggressive = pt.get("aggressive")
        aggressive_raw = pt.get("aggressive_raw")
        method = pt.get("method", "")

        if conservative:
            lines.append(f"| 保守 | {conservative} | {method} | 综合 |")
        if base:
            lines.append(f"| 基准 | {base} | {method} | A+B交叉验证 |")
        if aggressive:
            if pt.get("is_far_target"):
                lines.append(f"| 激进 | {aggressive_raw}（久远，暂不可达） | 周K斐波那契1.618扩展 | 周线大结构 |")
            else:
                lines.append(f"| 激进 | {aggressive} | 周K斐波那契1.618扩展 | 周线大结构 |")

        lines.append("")

        # Trigger conditions
        trigger = pt.get("trigger_conditions", {})
        if trigger:
            parts = []
            if trigger.get("price"):
                parts.append(trigger["price"])
            if trigger.get("trend"):
                parts.append(trigger["trend"])
            if trigger.get("volume"):
                parts.append(trigger["volume"])
            if trigger.get("momentum"):
                parts.append(trigger["momentum"])
            if parts:
                lines.append(f"**触发**: {' + '.join(parts)}")

        # Stop loss
        stop = pt.get("stop_loss", "")
        if stop:
            lines.append(f"**止损**: {stop}")

        # Failure conditions
        failures = pt.get("failure_conditions", [])
        if failures:
            lines.append(f"**失效**: {' / '.join(failures)}")

        # Time estimate
        time_est = pt.get("time_estimate", {})
        if time_est:
            parts = []
            if time_est.get("conservative"):
                parts.append(f"保守{time_est['conservative']}")
            if time_est.get("base"):
                parts.append(f"基准{time_est['base']}")
            if time_est.get("aggressive"):
                parts.append(f"激进{time_est['aggressive']}")
            if parts:
                lines.append(f"**时间预期**: {' / '.join(parts)}")

        lines.append("")
        return "\n".join(lines)

    def _reports_section(self, stock_name: str, analysis_result: Dict, raw_reports: list) -> str:
        """Section 4: 最新研报摘要"""
        lines = ["## 四、最新研报摘要（近4个月）", ""]
        if raw_reports:
            lines.append("| 日期 | 机构 | 评级 | 目标价 | 核心观点 |")
            lines.append("|------|------|------|--------|----------|")
            for r in raw_reports[:10]:
                lines.append(
                    f"| {r.get('date', '')} | {r.get('institution', '')} | "
                    f"{r.get('rating', '')} | {r.get('target_price', '')} | {r.get('summary', '')[:30]}... |"
                )
            lines.append("")

        report_md = analysis_result.get("report_sections", {}).get("report_summary", "")
        if report_md and report_md != "*AI分析暂缺*":
            lines.append(report_md)
        else:
            lines.append("*暂无研报分析*")
        lines.append("")
        return "\n".join(lines)

    def _announcements_section(self, stock_name: str, analysis_result: Dict, raw_anns: list) -> str:
        """Section 5: 近期公告要点"""
        lines = ["## 五、近期公告要点（近3个月）", ""]
        if raw_anns:
            lines.append("| 日期 | 类型 | 标题 | 要点 |")
            lines.append("|------|------|------|------|")
            for a in raw_anns[:10]:
                lines.append(
                    f"| {a.get('date', '')} | {a.get('type', '')} | {a.get('title', '')[:20]}... | "
                    f"{a.get('content', '')[:30]}... |"
                )
            lines.append("")

        ann_md = analysis_result.get("report_sections", {}).get("announcement_signals", "")
        if ann_md and ann_md != "*AI分析暂缺*":
            lines.append(ann_md)
        else:
            lines.append("*暂无公告分析*")
        lines.append("")
        return "\n".join(lines)

    def _fundflow_section(self, stock_name: str, analysis_result: Dict, raw_fundflow: list) -> str:
        """Section 6: 资金流向追踪"""
        lines = ["## 六、资金流向追踪（近1周）", ""]
        if raw_fundflow:
            lines.append("| 日期 | 主力净流入 | 散户净流入 | 大单占比 | 信号 |")
            lines.append("|------|-----------|-----------|----------|------|")
            for f in raw_fundflow[:7]:
                signal = "主力吸筹" if f.get("main_inflow", 0) > 0 else "主力流出"
                lines.append(
                    f"| {f.get('date', '')} | {f.get('main_inflow', 0):.0f}万 | "
                    f"{f.get('retail_inflow', 0):.0f}万 | {f.get('large_order_pct', 0):.0f}% | {signal} |"
                )
            lines.append("")

        fund_md = analysis_result.get("report_sections", {}).get("fundflow_interpretation", "")
        if fund_md and fund_md != "*AI分析暂缺*":
            lines.append(fund_md)
        else:
            lines.append("*暂无资金流向分析*")
        lines.append("")
        return "\n".join(lines)

    def _annotate_cross_sources(self, consolidated: List[Dict], keep_posts: List[Dict], zhihu_items: List[Dict]) -> None:
        """
        将 cross_sources 信息回注到原始内容中，用于在各板块内标注交叉来源。
        """
        # 建立 title -> cross_sources 映射
        cross_map = {}
        for item in consolidated:
            title = item.get("title", "")
            if title and item.get("cross_sources"):
                cross_map[title] = item.get("cross_sources", [])

        # 回注到雪球 keep_posts
        for post in keep_posts:
            title = post.get("title", "")
            if title in cross_map:
                post["_cross_sources"] = cross_map[title]

        # 回注到知乎 items
        for item in zhihu_items:
            title = item.get("title", "")
            if title in cross_map:
                item["_cross_sources"] = cross_map[title]

    def _zhihu_section(self, stock_name: str, zhihu_data: Dict) -> str:
        """Section 7: 知乎及全网内容精选（统一质量评估后）"""
        lines = ["## 七、知乎及全网内容精选", ""]

        report_items = zhihu_data.get("report_items", []) if isinstance(zhihu_data, dict) else []
        if not report_items:
            lines.append("*暂无相关内容*")
            lines.append("")
            return "\n".join(lines)

        total = zhihu_data.get("total", 0)
        gate_stats = zhihu_data.get("gate_stats", {})
        lines.append(
            f"> 本次采集 {total} 条内容（知乎站内 + 全网），经质量门筛选出 **{len(report_items)}** 条高质量内容纳入报告。\n"
        )

        # 优先展示高质量内容，最多展示 12 条
        display_items = report_items[:12]
        for i, item in enumerate(display_items, 1):
            title = item.get("title", "")
            author = item.get("author_name", "未知")
            badge = item.get("author_badge", "")
            url = item.get("url", "")
            vote_up = item.get("vote_up_count", 0)
            comments = item.get("comment_count", 0)
            search_kw = item.get("search_keyword", "")
            edit_time = item.get("edit_time", 0)
            source_platform = item.get("source_platform", "知乎")
            source_type = item.get("_source_type", "site")
            date_str = ""
            if edit_time:
                from datetime import datetime
                date_str = datetime.fromtimestamp(edit_time).strftime("%Y-%m-%d")

            # 兼容新旧两种评估结果格式
            qg = item.get("_quality_gate", {})
            cur = item.get("_curator", {})
            quality_score = qg.get("quality_score") or cur.get("quality_score", 0)
            reasons = qg.get("reasons", [])
            summary = cur.get("summary", "")
            logic_chain = cur.get("logic_chain", {})
            judgment = cur.get("judgment", "")

            # 来源标签
            source_label = "[全网]" if source_type == "web" else "[站内]"

            # 元数据行
            meta_parts = [f"**{author}**"]
            if badge:
                meta_parts.append(f"({badge})")
            meta_parts.append(f"来源: {source_platform}")
            if date_str:
                meta_parts.append(f"编辑时间 {date_str}")
            meta_parts.append(f"👍 {vote_up}")
            if quality_score:
                meta_parts.append(f"质量分 {quality_score}/100")

            # 交叉来源标注
            cross_sources = item.get("_cross_sources", [])
            if cross_sources:
                cs_labels = [f"{cs['source']}" for cs in cross_sources]
                meta_parts.append(f"📌 也被: {', '.join(cs_labels)} 提及")

            lines.append(f"### {i}. {source_label}[{title}]({url})")
            lines.append(" | ".join(meta_parts))
            if search_kw:
                lines.append(f"> 搜索关键词: {search_kw}")
            if reasons:
                lines.append(f"> 质量亮点: {', '.join(reasons[:2])}")
            lines.append("")

            # 摘要（旧格式兼容）
            if summary:
                lines.append("**摘要**：")
                lines.append(f"{summary}")
                lines.append("")

            # 逻辑链（旧格式兼容）
            if logic_chain and any(logic_chain.values()):
                lines.append("**逻辑链**：")
                premise = logic_chain.get("premise", "")
                evidence = logic_chain.get("evidence", "")
                reasoning = logic_chain.get("reasoning", "")
                conclusion = logic_chain.get("conclusion", "")
                if premise:
                    lines.append(f"- **前提**：{premise}")
                if evidence:
                    lines.append(f"- **论据**：{evidence}")
                if reasoning:
                    lines.append(f"- **推理**：{reasoning}")
                if conclusion:
                    lines.append(f"- **结论**：{conclusion}")
                lines.append("")

            # AI 判断（旧格式兼容）
            if judgment and "[降级模式]" not in judgment:
                lines.append("**判断**：")
                lines.append(f"{judgment}")
                lines.append("")
            elif not summary and not judgment:
                # 降级：显示原始内容截断
                text = item.get("content_text", "")[:300]
                lines.append(f"> {text}...")
                lines.append("")

        if len(report_items) > len(display_items):
            lines.append(f"*... 还有 {len(report_items) - len(display_items)} 条高质量内容未展示*")
            lines.append("")

        return "\n".join(lines)

    def _valuation_forecast(self, stock_name: str, quote=None, consensus=None) -> str:
        """
        估值与预测板块：整合实时行情 + 券商一致预期，计算 forward PE / PEG
        """
        code = self.stock_codes.get(stock_name, "")
        if not code:
            return ""

        # 拉取实时估值（如果未传入）
        if quote is None:
            quote = fetch_tencent_quote(code)
        # 拉取一致预期（如果未传入）
        if consensus is None:
            consensus = fetch_consensus_eps(code)

        if not quote:
            return ""

        price = quote.get("price", 0)
        pe_ttm = quote.get("pe_ttm", 0)
        pb = quote.get("pb", 0)
        mcap = quote.get("mcap_yi", 0)
        change_pct = quote.get("change_pct", 0)

        # 构建估值板块
        lines = [
            "## 二、估值与业绩预测",
            "",
            f"**数据日期**: {self.date_display} | **数据来源**: 腾讯财经实时行情 + 同花顺机构一致预期",
            "",
            "### 实时估值指标",
            "",
            f"| 指标 | 数值 | 说明 |",
            f"|------|------|------|",
            f"| 最新价 | {price:.2f} 元 | 较前日 {'+' if change_pct >= 0 else ''}{change_pct:.2f}% |",
            f"| 总市值 | {mcap:.1f} 亿 | 流通市值 {quote.get('float_mcap_yi', 0):.1f} 亿 |",
            f"| PE(TTM) | {pe_ttm:.1f} | 滚动市盈率 |",
            f"| PB | {pb:.2f} | 市净率 |",
        ]

        # 一致预期与 forward 估值
        if consensus and consensus.get("eps_current"):
            eps_cur = consensus["eps_current"]
            eps_next = consensus.get("eps_next")
            analyst_count = consensus.get("analyst_count", 0)
            pe_fwd = price / eps_cur if eps_cur else float("inf")

            lines.extend([
                "",
                "### 券商一致预期与 Forward 估值",
                "",
                f"> 覆盖机构数: **{analyst_count}** 家",
                "",
                f"| 指标 | 数值 | 推导逻辑 |",
                f"|------|------|----------|",
                f"| 预期 EPS ({consensus['year_current']}) | {eps_cur:.2f} 元 | 机构一致预期均值 |",
            ])

            if eps_next:
                cagr = (eps_next / eps_cur - 1) if eps_cur else 0
                peg = pe_fwd / (cagr * 100) if cagr > 0 else float("inf")
                lines.append(f"| 预期 EPS ({consensus['year_next']}) | {eps_next:.2f} 元 | 同比增速 {(cagr * 100):.1f}% |")
                lines.append(f"| Forward PE | {pe_fwd:.1f} | 最新价 / {consensus['year_current']} 预期 EPS |")
                lines.append(f"| PEG | {peg:.2f} | Forward PE / 盈利增速 ({(cagr * 100):.1f}%) |")
            else:
                lines.append(f"| Forward PE | {pe_fwd:.1f} | 最新价 / {consensus['year_current']} 预期 EPS |")
                lines.append(f"| PEG | — | 次年预期 EPS 暂不可用 |")

            # 判断与结论
            lines.extend([
                "",
                "### 估值判断",
                "",
            ])

            judgments = []
            if pe_ttm <= 0:
                judgments.append(f"- **业绩拐点**: PE-TTM 为负（{pe_ttm:.1f}），说明过去四个季度整体亏损；Forward PE ({pe_fwd:.1f}) 为正，反映机构预期明年实现盈利。这是典型的**业绩拐点型估值**，股价走势将取决于实际盈利修复能否兑现 consensus 预期。")
            elif pe_fwd < pe_ttm:
                digest_pct = (1 - pe_fwd / pe_ttm) * 100
                judgments.append(f"- **估值消化**: Forward PE ({pe_fwd:.1f}) 低于 PE-TTM ({pe_ttm:.1f})，说明业绩成长正在消化估值，预期消化幅度约 **{digest_pct:.1f}%**")
            elif pe_fwd > pe_ttm:
                judgments.append(f"- **估值压力**: Forward PE ({pe_fwd:.1f}) 高于 PE-TTM ({pe_ttm:.1f})，说明市场预期业绩增速放缓或存在估值下修压力")
            else:
                judgments.append(f"- **估值中性**: Forward PE 与 PE-TTM 基本持平，估值处于合理区间")

            if eps_next and cagr > 0:
                if peg < 0.8:
                    judgments.append(f"- **PEG 吸引力**: PEG = {peg:.2f} < 0.8，按彼得·林奇标准，当前估值相对盈利增速具有明显安全边际")
                elif peg < 1.2:
                    judgments.append(f"- **PEG 合理**: PEG = {peg:.2f} 处于 0.8–1.2 区间，估值与增速基本匹配")
                else:
                    judgments.append(f"- **PEG 偏高**: PEG = {peg:.2f} > 1.2，当前估值已较充分反映增长预期，需警惕业绩不及预期的回调风险")

            # 结合产业逻辑的额外判断
            industry_judgment = valuation_industry_judgment(stock_name, pe_ttm, pe_fwd, peg if eps_next and cagr > 0 else None, mcap)
            judgments.append(industry_judgment)

            lines.extend(judgments)
        else:
            lines.extend([
                "",
                "### 券商一致预期",
                "",
                "> 暂无法获取机构一致预期 EPS 数据（可能为非 A 股标的或覆盖机构不足）。",
                "",
                "**判断**: 缺乏 consensus 数据时，估值判断需更多依赖产业逻辑和同行对比。建议参考报告中「市场情绪与竞争格局」与「核心话题」部分的定性分析。",
            ])

        return "\n".join(lines)

    # ============ Phase 2: 量化评分体系 ============

    def _footer(self) -> str:
        """报告尾部"""
        return f"""---

*本报告基于雪球网公开讨论数据由 Claude AI 深度分析生成，仅供参考，不构成投资建议。*
*报告生成时间: {self.date_display}*
"""

    # ============ 辅助方法 ============

    def _read_full_content_from_vault(self, stock_name: str, url: str) -> Optional[Dict]:
        """
        从 Obsidian Vault 读取帖子的完整正文和多媒体信息。

        Returns:
            {"body": str, "media": {"images": [...], "tables": [...]}} or None
        """
        import json

        post_id = url.rstrip("/").split("/")[-1]
        vault_path = (
            Path(__file__).parent.parent.parent
            / "knowledge"
            / "10-Stocks"
            / stock_name
            / "posts"
            / f"{post_id}.md"
        )
        if not vault_path.exists():
            return None

        raw = vault_path.read_text(encoding="utf-8")
        match = re.search(r"^---\n.*?\n---\n\n# [^\n]+\n\n(.+)", raw, re.DOTALL)
        if not match:
            return None

        body = match.group(1).strip()
        # Strip embedded media comment from body (it is parsed separately below)
        body = re.sub(r"\n?<!-- media: .*? -->\s*$", "", body, flags=re.DOTALL).strip()
        # Reject footer-only or extremely short/scraped garbage content
        footer_markers = ["tousu@xueqiu.com", "京ICP备", "我给雪球提建议", "防诈骗举报专区", "证券业协会会员单位"]
        if any(m in body for m in footer_markers):
            return None
        if len(body) < 80:
            return None

        # Extract embedded media JSON comment
        media: Dict = {"images": [], "tables": []}
        media_match = re.search(r"<!-- media: (.*?) -->", raw, re.DOTALL)
        if media_match:
            try:
                parsed = json.loads(media_match.group(1))
                if isinstance(parsed, dict):
                    media = parsed
            except Exception:
                pass

        return {"body": body, "media": media}

    def _format_media_description(self, media: Dict) -> str:
        """将 Vault 中记录的图表/表格信息格式化为 Markdown 描述文本。"""
        lines = []
        images = media.get("images", [])
        tables = media.get("tables", [])

        for idx, img in enumerate(images, 1):
            alt = img.get("alt", "").strip()
            caption = img.get("caption", "").strip()
            desc = caption or alt
            if desc:
                lines.append(f"- 图{idx}: {desc}")
            else:
                lines.append(f"- 图{idx}: [图片，详情见原文链接]")

        for idx, table in enumerate(tables, 1):
            rows = table.get("rows", 0)
            cols = table.get("columns", 0)
            md = table.get("markdown", "").strip()
            lines.append(f"- 表{idx}（{rows}行×{cols}列）:")
            if md:
                # Indent markdown table for blockquote compatibility
                indented = "\n".join("  " + line for line in md.split("\n"))
                lines.append(indented)
            else:
                lines.append("  [表格内容已提取，见原文链接]")

        return "\n".join(lines) if lines else ""

    def _detect_slogan_content(self, content: str) -> tuple:
        """
        检测内容是否为口号式/纯情绪表达。

        Returns:
            (is_slogan: bool, reason: str)
        """
        content = content.strip()
        total_len = len(content)
        if total_len == 0:
            return True, "内容为空"

        # 指标2: 数据密度与逻辑密度（先计算，供指标1使用）
        has_numbers = any(c.isdigit() for c in content)
        logic_words = [
            "因为", "所以", "如果", "那么", "因此", "意味着", "结论",
            "前提", "推导", "验证", "由于", "导致", "说明", "反映",
            "对比", "相较于", "数据表明", "统计", "测算", "估算",
        ]
        has_logic = any(w in content for w in logic_words)

        # 指标1: 极短内容（Vault 已过滤 <80，这里进一步收紧）
        # 但如果短内容包含数据或逻辑，仍视为有效分析
        if total_len < 120 and not has_numbers and not has_logic:
            return True, "内容过短且缺乏数据与逻辑推导"

        # 指标3: 情绪密度（感叹号/问号占比）
        excl_count = content.count("！") + content.count("!")
        ques_count = content.count("？") + content.count("?")
        emotion_ratio = (excl_count + ques_count) / total_len if total_len else 0

        # 指标4: 股票标签密度
        tag_count = content.count("$")

        if not has_numbers and not has_logic:
            if emotion_ratio > 0.03:
                return True, "以情绪感叹为主，缺乏数据与逻辑推导"
            if tag_count >= 2 and total_len < 250:
                return True, "主要为股票标签和简单断言，无实质分析"

        # 指标5: 重复标点模式
        if re.search(r'[!！]{3,}|[?？]{3,}|[。]{5,}', content):
            return True, "包含大量重复标点，情绪表达特征明显"

        # 指标6: 极端断言词密度
        extreme_words = ["绝对", "必然", "一定", "毫无疑问", "铁定", "暴涨", "暴跌", "翻倍", "十倍"]
        extreme_count = sum(content.count(w) for w in extreme_words)
        if extreme_count >= 3 and not has_numbers:
            return True, "充斥极端断言词汇但缺乏数据支撑"

        return False, ""

    def _extract_argument_chain(self, content: str, min_length: int = 200, max_length: int = 600) -> str:
        """
        从帖子正文中提取推导链（前提假设 → 论据/数据 → 推理过程 → 结论）。

        策略：
        1. 先检测口号式/情绪内容，如是则返回质量提示
        2. 如果正文长度在范围内，直接返回
        3. 如果过长，优先保留包含逻辑连接词和数字的段落
        4. 按原文顺序重组选中的段落
        """
        content = content.strip()

        # 质量检测：口号式/情绪表达
        is_slogan, reason = self._detect_slogan_content(content)
        if is_slogan:
            preview = content[:120]
            if len(content) > 120:
                preview += "..."
            return f"[该帖子{reason}，不具备深度分析参考价值。]\n\n原文摘录：{preview}"

        # Detect broken-line content (scraped pages where each punctuation is on its own line)
        raw_lines = [l.strip() for l in content.split("\n") if l.strip()]
        avg_len = sum(len(l) for l in raw_lines) / len(raw_lines) if raw_lines else 0
        if avg_len < 15:
            # Reconstruct text flow and split by sentence endings
            reconstructed = "".join(raw_lines)
            sentences = re.split(r'(?<=[。！？；])', reconstructed)
            paragraphs = [s.strip() for s in sentences if len(s.strip()) >= 10]
            if paragraphs:
                content = "\n\n".join(paragraphs)

        if len(content) <= max_length:
            return content

        # If still too long after reconstruction, use paragraph scoring
        paragraphs = [p for p in content.split("\n\n") if p.strip()]

        logic_keywords = ["因为", "所以", "如果", "那么", "因此", "意味着", "结论是",
                          "前提", "论据", "推导", "逻辑", "假设", "验证"]
        data_patterns = [r"\d+[%％]", r"\d+\.\d+", r"\d+亿", r"\d+万", r"\d+元"]

        scored_paragraphs = []
        for p in paragraphs:
            score = 0
            for kw in logic_keywords:
                if kw in p:
                    score += 2
            for pattern in data_patterns:
                if re.search(pattern, p):
                    score += 3
            if 30 <= len(p) <= 200:
                score += 1
            scored_paragraphs.append((score, p))

        scored_paragraphs.sort(key=lambda x: x[0], reverse=True)

        selected = []
        total_len = 0
        for score, p in scored_paragraphs:
            if total_len + len(p) > max_length and total_len >= min_length:
                break
            selected.append(p)
            total_len += len(p) + 1

        selected_set = set(selected)
        ordered = [p for p in paragraphs if p in selected_set]

        result = "\n".join(ordered)

        if len(result) < min_length:
            truncated = content[:max_length]
            last_period = max(truncated.rfind("。"), truncated.rfind("！"), truncated.rfind("？"))
            if last_period > min_length:
                return truncated[:last_period + 1]
            return truncated + "..."

        return result

    def _extract_excerpt(self, content: str, min_length: int = 150, max_length: int = 400) -> str:
        """Backward-compatible alias for _extract_argument_chain."""
        return self._extract_argument_chain(content, min_length, max_length)

    def _render_synthesis_section(self, title: str, narrative: str, citations: Dict) -> str:
        """渲染一个合成叙事板块，自动提取该板块使用的引用。"""
        import re
        used_refs = set(int(m) for m in re.findall(r"\[\^(\d+)\]", narrative))

        lines = [f"## {title}", "", narrative, ""]

        if used_refs:
            lines.append("**本节引用来源：**")
            for ref_id in sorted(used_refs):
                meta = citations.get(ref_id, {})
                source = meta.get("source", "未知")
                author = meta.get("author", "")
                title_text = meta.get("title", "")
                url = meta.get("url", "")
                date = meta.get("date", "")
                parts = [f"[^{ref_id}]"]
                if source:
                    parts.append(source)
                if author:
                    parts.append(f"作者: {author}")
                if title_text:
                    parts.append(f"《{title_text[:40]}》")
                if date:
                    parts.append(date)
                line = " | ".join(parts)
                if url:
                    line += f" [{url}]"
                lines.append(f"- {line}")
            lines.append("")

        return "\n".join(lines)

    def _citations_section(self, title: str, citations: Dict) -> str:
        """报告末尾的全局引用汇总板块。"""
        lines = [f"## {title}", ""]
        if not citations:
            lines.append("*无引用信息*")
            lines.append("")
            return "\n".join(lines)

        lines.append(f"> 本报告共引用 **{len(citations)}** 条信息来源：")
        lines.append("")

        for ref_id in sorted(citations.keys()):
            meta = citations[ref_id]
            source = meta.get("source", "未知")
            author = meta.get("author", "")
            title = meta.get("title", "")
            url = meta.get("url", "")
            date = meta.get("date", "")
            parts = [f"[^{ref_id}]"]
            if source:
                parts.append(f"**{source}**")
            if author:
                parts.append(f"作者: {author}")
            if title:
                parts.append(f"《{title[:50]}》")
            if date:
                parts.append(date)
            line = " | ".join(parts)
            if url:
                line = f"{line} [{url}]"
            lines.append(f"- {line}")
        lines.append("")
        return "\n".join(lines)

    def _generate_html_dashboard(self, stock_name: str, chart_paths: Dict[str, str]) -> str:
        """生成单页 HTML Dashboard（视觉速览）。"""
        # 基础数据准备
        code = self.stock_codes.get(stock_name, "")
        quote = fetch_tencent_quote(code) if code else None
        price = quote.get("price", 0) if quote else 0
        change_pct = quote.get("change_pct", 0) if quote else 0

        # 五维评分与 EV
        all_posts = self.stocks_data.get(stock_name, [])
        stock_raw = self.raw_data.get(stock_name, {})
        ps = quote.get("ps") if quote else None
        consensus = fetch_consensus_eps(code) if code else None
        ind_fwd_pe = industry_fwd_pe(stock_name)
        pillar = compute_pillar_scores(stock_raw, all_posts, quote, consensus, ind_fwd_pe, ps)
        total_score = round(
            pillar["valuation"] * 0.30 +
            pillar["technical"] * 0.25 +
            pillar["sentiment"] * 0.20 +
            pillar["fundamental"] * 0.15 +
            pillar["fundflow"] * 0.10,
            1,
        )
        ev = ev_expectation(pillar, consensus)
        ev_pct = ev.get("ev_pct")
        ev_signal = ev.get("signal") or "N/A"
        ev_pct_str = f"{ev_pct:+.2f}%" if ev_pct is not None else "N/A"
        ev_color = "text-green-600" if ev_pct and ev_pct > 0 else "text-red-600" if ev_pct and ev_pct < 0 else "text-gray-600"

        # 价格目标 / 盈亏比
        pt = stock_raw.get("price_target")
        pr_ratio = pt.get("profit_risk_ratio") if pt else None
        pr_text = f"{pr_ratio}:1" if pr_ratio else "N/A"

        # AI 推荐
        ai_rec = "关注/不操作"
        if ev_pct is not None:
            ai_rec = "关注" if ev_pct > 5 else "持有" if ev_pct > -5 else "观望"

        # 操作建议
        op_rec = "关注/不操作"
        if total_score >= 7.5:
            op_rec = "积极关注"
        elif total_score >= 6.0:
            op_rec = "关注"
        elif total_score >= 4.0:
            op_rec = "观望"
        else:
            op_rec = "回避"

        # 图表文件名（HTML 与 PNG 同目录）
        tech_img = Path(chart_paths.get("technical", "")).name if chart_paths.get("technical") else ""
        bb_img = Path(chart_paths.get("bullbear", "")).name if chart_paths.get("bullbear") else ""
        radar_img = Path(chart_paths.get("radar", "")).name if chart_paths.get("radar") else ""
        val_img = Path(chart_paths.get("valuation", "")).name if chart_paths.get("valuation") else ""

        # 多空论点
        synthesis = self._synthesize_sections(stock_name, stock_raw)
        debate_text = synthesis.get("valuation_debate", "")
        fund_text = synthesis.get("fundamentals", "")
        combined = debate_text + "\n" + fund_text
        bullish_args = self._extract_thesis_points(combined, "bullish")
        bearish_args = self._extract_thesis_points(combined, "bearish")

        def _card(title: str, value: str, color: str = "blue") -> str:
            color_map = {
                "blue": "bg-blue-50 text-blue-700 border-blue-200",
                "green": "bg-green-50 text-green-700 border-green-200",
                "red": "bg-red-50 text-red-700 border-red-200",
                "yellow": "bg-yellow-50 text-yellow-700 border-yellow-200",
            }
            cls = color_map.get(color, color_map["blue"])
            return f"""<div class="{cls} border rounded-xl p-4 flex flex-col">
                <span class="text-xs font-semibold uppercase tracking-wider opacity-70">{title}</span>
                <span class="text-2xl font-bold mt-1">{value}</span>
            </div>"""

        def _arg_card(direction: str, args: List[Dict]) -> str:
            if not args:
                return ""
            color = "green" if direction == "bullish" else "red"
            label = "看多论点" if direction == "bullish" else "看空论点"
            items = "\n".join(
                f'<li class="mb-2"><span class="font-bold">{"⭐" * a.get("stars", 3)}</span> {a.get("text", "")}</li>'
                for a in args[:3]
            )
            return f"""<div class="bg-{color}-50 border border-{color}-200 rounded-xl p-4">
                <h4 class="text-{color}-700 font-bold mb-2">{label}</h4>
                <ul class="text-sm text-gray-700">{items}</ul>
            </div>"""

        # 投资者类型建议表
        advice_rows = ""
        advice_data = [
            ("短线交易者", "观望", "等待方向明确"),
            ("中线投资者", op_rec, "基于综合评分"),
            ("长线持有者", ai_rec, "基于EV预期"),
            ("风险厌恶型", "回避" if total_score < 5 else "轻仓观望", "评分偏低" if total_score < 5 else "控制仓位"),
        ]
        for investor, advice, note in advice_data:
            row_color = "text-green-700" if "积极" in advice or "关注" in advice else "text-yellow-700" if "观望" in advice else "text-red-700"
            advice_rows += f"""<tr class="border-b border-gray-100">
                <td class="py-3 px-4 font-medium">{investor}</td>
                <td class="py-3 px-4 font-bold {row_color}">{advice}</td>
                <td class="py-3 px-4 text-gray-500 text-sm">{note}</td>
            </tr>"""

        # 五维评分卡片
        radar_cards = ""
        radar_labels = [
            ("估值健康度", "valuation", "30%"),
            ("技术面强度", "technical", "25%"),
            ("情绪面温度", "sentiment", "20%"),
            ("基本面趋势", "fundamental", "15%"),
            ("资金关注度", "fundflow", "10%"),
        ]
        for label, key, weight in radar_labels:
            score = pillar.get(key, 0)
            bar_width = int(score * 10)
            bar_color = "bg-green-500" if score >= 7 else "bg-yellow-500" if score >= 5 else "bg-red-500"
            radar_cards += f"""<div class="mb-3">
                <div class="flex justify-between text-sm mb-1">
                    <span class="font-medium">{label} ({weight})</span>
                    <span class="font-bold">{score:.1f}</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-2.5">
                    <div class="{bar_color} h-2.5 rounded-full" style="width: {bar_width}%"></div>
                </div>
            </div>"""

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{stock_name} 舆情 Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 text-gray-800">
    <div class="max-w-4xl mx-auto px-4 py-6">
        <!-- Header -->
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-6">
            <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                    <h1 class="text-2xl font-bold text-gray-900">{stock_name}</h1>
                    <p class="text-sm text-gray-500 mt-1">{self.date_display} · 雪球舆情深度分析</p>
                </div>
                <div class="text-right">
                    <div class="text-3xl font-bold text-gray-900">{price:.2f} <span class="text-sm font-normal text-gray-500">元</span></div>
                    <div class="text-sm font-medium {"text-green-600" if change_pct >= 0 else "text-red-600"}">{"+" if change_pct >= 0 else ""}{change_pct:.2f}%</div>
                </div>
            </div>
            <!-- Metric Cards -->
            <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mt-6">
                {_card("综合评分", f"{total_score}/10", "blue")}
                {_card("AI推荐", ai_rec, "green" if "积极" in ai_rec or "关注" in ai_rec else "yellow")}
                {_card("EV", ev_pct_str, "green" if ev_pct and ev_pct > 0 else "red" if ev_pct and ev_pct < 0 else "yellow")}
                {_card("盈亏比", pr_text, "blue")}
                {_card("操作建议", op_rec, "green" if "积极" in op_rec or "关注" in op_rec else "yellow" if "观望" in op_rec else "red")}
            </div>
        </div>

        <!-- 技术面分析 -->
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-6">
            <h2 class="text-lg font-bold text-gray-900 mb-4">技术面分析</h2>
            {"<img src='charts/" + tech_img + "' alt='技术面分析' class='w-full rounded-xl mb-4'/>" if tech_img else "<p class='text-gray-400 text-sm'>暂无技术面图表</p>"}
            <p class="text-sm text-gray-600">综合技术评分: <span class="font-bold text-blue-600">{pillar.get('technical', 0):.1f}</span> / 10</p>
        </div>

        <!-- 多空观点拆解 -->
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-6">
            <h2 class="text-lg font-bold text-gray-900 mb-4">多空观点拆解</h2>
            {"<img src='charts/" + bb_img + "' alt='多空论点对比' class='w-full rounded-xl mb-4'/>" if bb_img else "<p class='text-gray-400 text-sm'>暂无多空对比图表</p>"}
            <div class="grid md:grid-cols-2 gap-4 mt-4">
                {_arg_card("bullish", bullish_args)}
                {_arg_card("bearish", bearish_args)}
            </div>
        </div>

        <!-- 五维评分雷达 -->
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-6">
            <h2 class="text-lg font-bold text-gray-900 mb-4">五维评分雷达</h2>
            <div class="flex flex-col md:flex-row gap-6">
                <div class="md:w-1/2">
                    {"<img src='charts/" + radar_img + "' alt='五维评分雷达图' class='w-full rounded-xl'/>" if radar_img else "<p class='text-gray-400 text-sm'>暂无雷达图</p>"}
                </div>
                <div class="md:w-1/2">
                    {radar_cards}
                </div>
            </div>
        </div>

        <!-- 同业估值对比 -->
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-6">
            <h2 class="text-lg font-bold text-gray-900 mb-4">同业估值对比</h2>
            {"<img src='charts/" + val_img + "' alt='同业估值对比' class='w-full rounded-xl'/>" if val_img else "<p class='text-gray-400 text-sm'>暂无估值对比图表</p>"}
        </div>

        <!-- 操作建议 -->
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-6">
            <h2 class="text-lg font-bold text-gray-900 mb-4">操作建议</h2>
            <div class="overflow-x-auto">
                <table class="w-full text-left">
                    <thead>
                        <tr class="border-b border-gray-200 text-sm text-gray-500">
                            <th class="py-2 px-4 font-medium">投资者类型</th>
                            <th class="py-2 px-4 font-medium">建议</th>
                            <th class="py-2 px-4 font-medium">备注</th>
                        </tr>
                    </thead>
                    <tbody class="text-sm">
                        {advice_rows}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Footer -->
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
            <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <a href="{stock_name}_{self.date_str}.md" class="inline-flex items-center text-blue-600 hover:text-blue-800 font-medium">
                    查看完整分析报告 →
                </a>
                <p class="text-xs text-gray-400">本报告基于雪球网公开讨论数据由 AI 生成，仅供参考，不构成投资建议。</p>
            </div>
        </div>
    </div>
</body>
</html>"""
        return html

    def _generate_summary_report(self, output_dir: str) -> str:
        """生成汇总简报"""
        lines = [
            f"# 雪球舆情监控汇总简报 ({self.date_display})",
            "",
            "## 市场情绪速览",
            "",
            "| 股票 | 情绪 | 热度 | 核心看点 |",
            "|------|------|------|----------|",
        ]

        for stock_name, posts in self.stocks_data.items():
            total = len(posts)
            likes = sum(p.get("like_count", 0) for p in posts)
            comments = sum(p.get("comment_count", 0) for p in posts)
            bullish, bearish, neutral = classify_sentiment(posts)
            sentiment = "看多" if len(bullish) > len(bearish) else "看空" if len(bearish) > len(bullish) else "中性"
            heat = "🔥" if likes + comments > 100 else "🌡️" if likes + comments > 50 else "❄️"

            key_point = {
                "黑芝麻智能": "智驾量产+做空风险并存",
                "长春高新": "套牢严重+融资盘风险",
                "三花智控": "特斯拉机器人核心供应商",
                "中简科技": "Q1暴雷+长期军工逻辑",
                "圣邦股份": "模拟芯片周期反转",
                "乐鑫科技": "端侧AI+量化控盘",
            }.get(stock_name, "")

            lines.append(f"| {stock_name} | {sentiment} | {heat} | {key_point} |")

        lines.extend([
            "",
            "## 本周最热赛道",
            "",
            "1. **特斯拉人形机器人/物理AI** — 三花智控、圣邦股份受益",
            "2. **智能驾驶/AEB强制标准** — 黑芝麻智能催化",
            "3. **碳纤维/商业航天** — 中简科技长期期权",
            "",
            "## 风险提示",
            "",
            "- 🔴 **黑芝麻智能**: 港股通退通风险（市值接近65亿红线）",
            "- 🔴 **长春高新**: 融资盘爆仓风险",
            "- 🟡 **三花智控**: 短期涨幅过大回调风险",
            "- 🟡 **圣邦股份**: 杰华特竞争威胁",
            "",
            f"*详细个股报告请查看同目录下 `{self.date_str}` 日期的个股文件。*",
            "",
            f"*报告生成时间: {self.date_display}*",
        ])

        markdown = "\n".join(lines)
        filepath = Path(output_dir) / f"xueqiu_summary_{self.date_str}.md"
        filepath.write_text(markdown, encoding="utf-8")
        return str(filepath)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python stock_reporter.py <数据JSON路径> [输出目录]")
        sys.exit(1)

    data_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    reporter = PerStockReporter(data_path=data_path)
    paths = reporter.generate_all_reports(output_dir)
    print(f"共生成 {len(paths)} 份报告:")
    for p in paths:
        print(f"  - {p}")
