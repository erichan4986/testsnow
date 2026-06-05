"""Report assembly skill."""

from pathlib import Path

if __name__.startswith("utils."):
    from ..skill_pipeline import BaseSkill, SkillContext
else:
    from skill_pipeline import BaseSkill, SkillContext


class ReportAssemblySkill(BaseSkill):
    """Markdown + HTML Dashboard 组装。复用 PerStockReporter 的 section 方法保留完整报告结构。"""
    name = "report_assembly"

    def run(self, ctx: SkillContext) -> SkillContext:
        """组装 Markdown + HTML Dashboard。"""
        stock_name = ctx.get("stock_name")
        output_dir = ctx.get("output_dir")
        date_str = ctx.get("date_str")

        md_content = self._assemble_markdown(ctx)
        html_content = self._assemble_html(ctx)

        md_path = Path(output_dir) / f"{stock_name}_{date_str}.md"
        html_path = Path(output_dir) / f"{stock_name}_{date_str}.html"

        md_path.write_text(md_content, encoding="utf-8")
        html_path.write_text(html_content, encoding="utf-8")

        ctx.set("md_path", str(md_path))
        ctx.set("html_path", str(html_path))
        return ctx

    def _reporter(self, ctx: SkillContext):
        """构造一个轻量的 PerStockReporter 实例，用于调用旧 section 方法。"""
        try:
            from ..stock_reporter import PerStockReporter
        except ImportError:
            try:
                from utils.stock_reporter import PerStockReporter
            except ImportError:
                from stock_reporter import PerStockReporter

        stock_name = ctx.get("stock_name")
        date_str = ctx.get("date_str", "")
        all_posts = ctx.get("all_posts", [])
        stock_raw = ctx.get("stock_raw", {})
        stock_codes = ctx.get("stock_codes", {})

        reporter = PerStockReporter(
            stocks_data={stock_name: all_posts},
            stock_codes=stock_codes,
            raw_data={stock_name: stock_raw},
        )
        reporter.date_str = date_str
        reporter.date_display = f"{date_str[:4]}年{date_str[4:6]}月{date_str[6:]}日" if len(date_str) == 8 else date_str
        reporter._chart_paths = {
            "technical": ctx.get("chart_technical"),
            "bullbear": ctx.get("chart_bullbear"),
            "radar": ctx.get("chart_radar"),
            "valuation": ctx.get("chart_valuation"),
        }
        return reporter

    def _assemble_markdown(self, ctx: SkillContext) -> str:
        """组装完整 Markdown 报告。"""
        stock_name = ctx.get("stock_name")
        all_posts = ctx.get("all_posts", [])
        stock_raw = ctx.get("stock_raw", {})
        keep_posts = ctx.get("keep_posts", [])
        quote = ctx.get("quote")
        consensus = ctx.get("consensus")
        ind_fwd_pe = ctx.get("ind_fwd_pe")
        synthesis = ctx.get("synthesis", {})
        stock_codes = ctx.get("stock_codes", {})
        chart_paths = {
            "technical": ctx.get("chart_technical"),
            "bullbear": ctx.get("chart_bullbear"),
            "radar": ctx.get("chart_radar"),
            "valuation": ctx.get("chart_valuation"),
        }

        reporter = self._reporter(ctx)

        # 导入旧辅助函数
        try:
            from ..reporter.scoring_engine import composite_score_section, industry_specific_risk_table, risk_score_section
            from ..reporter.data_fetcher import fetch_competitor_metrics, competitor_metrics_table
        except ImportError:
            try:
                from utils.reporter.scoring_engine import composite_score_section, industry_specific_risk_table, risk_score_section
                from utils.reporter.data_fetcher import fetch_competitor_metrics, competitor_metrics_table
            except ImportError:
                from reporter.scoring_engine import composite_score_section, industry_specific_risk_table, risk_score_section
                from reporter.data_fetcher import fetch_competitor_metrics, competitor_metrics_table

        sections = []
        sections.append(reporter._header(stock_name))
        sections.append(reporter._executive_summary(stock_name, all_posts, stock_raw, quote, consensus, ind_fwd_pe, synthesis))

        # 一、综合评分与推荐
        score_section = composite_score_section(stock_name, all_posts, stock_raw, quote, consensus, ind_fwd_pe)
        radar_chart = chart_paths.get("radar")
        if radar_chart:
            score_section += f"\n\n### 五维评分雷达图\n\n![{stock_name} 五维评分雷达图]({radar_chart})\n"
        sections.append(score_section)

        # 二、估值与财务快照
        sections.append(reporter._valuation_forecast_compact(stock_name, quote, consensus))
        quarterly_fin = reporter._quarterly_financials_table(stock_name)
        if quarterly_fin:
            sections.append(quarterly_fin)

        # 竞争对手财务指标对比
        comp_metrics = fetch_competitor_metrics(stock_name, stock_codes)
        if comp_metrics:
            comp_table = competitor_metrics_table(stock_name, comp_metrics)
            val_chart = chart_paths.get("valuation")
            if val_chart:
                comp_table += f"\n\n### 同业估值对比\n\n![{stock_name} 估值对比]({val_chart})\n"
            sections.append(comp_table)

        # 技术面分析
        tech_section = reporter._technical_analysis_section(stock_name, stock_raw)
        if tech_section:
            sections.append(tech_section)
        tech_chart = chart_paths.get("technical")
        if tech_chart:
            sections.append(f"### 技术面综合分析\n\n![{stock_name} 技术面分析]({tech_chart})\n")

        # 价格目标与触发条件
        price_target_section = reporter._price_target_section(stock_name, stock_raw)
        if price_target_section:
            sections.append(price_target_section)

        # 核心事实基座
        core_facts = synthesis.get("core_facts", [])
        if core_facts:
            sections.append(reporter._core_facts_table(core_facts))

        # 深度分析 / 降级旧版板块
        has_synthesis = any(
            synthesis.get(k) for k in ["industry_logic", "fundamentals", "valuation_debate", "funding_sentiment", "events_catalysts"]
        )
        if has_synthesis:
            sections.append(reporter._deep_analysis(stock_name, synthesis))
        else:
            sections.append(reporter._sentiment_and_competition(stock_name, all_posts))
            sections.append(reporter._core_topics(stock_name, all_posts))
            sections.append(reporter._zhihu_section(stock_name, stock_raw.get("zhihu", {})))
            featured_posts = [p for p in keep_posts if p.get("_track") == "featured"]
            sections.append(reporter._featured_posts(stock_name, featured_posts))
            sections.append(reporter._comment_highlights(stock_name, all_posts))

        # 行业特有风险
        chip_risk = industry_specific_risk_table(stock_name)
        if chip_risk:
            sections.append(chip_risk)

        # 风险综合评估
        watch_points = reporter._risks_and_watch(stock_name, all_posts)
        synthesis_texts = [synthesis.get(k, "") for k in ["industry_logic", "fundamentals", "valuation_debate", "funding_sentiment", "events_catalysts"]]
        sections.append(risk_score_section(stock_name, all_posts, stock_raw, quote, consensus, ind_fwd_pe, watch_points, "\n".join(synthesis_texts)))

        # 信息来源汇总
        if has_synthesis and synthesis.get("citations"):
            sections.append(reporter._citations_section("七、信息来源汇总", synthesis["citations"]))

        sections.append(reporter._footer())

        return "\n\n".join(sections)

    def _assemble_html(self, ctx: SkillContext) -> str:
        """组装 HTML Dashboard。复用旧 _generate_html_dashboard 以保留完整信息。"""
        stock_name = ctx.get("stock_name")
        output_dir = ctx.get("output_dir")
        date_str = ctx.get("date_str")

        reporter = self._reporter(ctx)
        chart_paths = {
            "technical": ctx.get("chart_technical"),
            "bullbear": ctx.get("chart_bullbear"),
            "radar": ctx.get("chart_radar"),
            "valuation": ctx.get("chart_valuation"),
        }

        # 复用旧 HTML 生成方法
        html_content = reporter._generate_html_dashboard(stock_name, chart_paths)

        # 保证 HTML 文件名和 md 文件名一致（测试中期望 {stock_name}_{date_str}.html）
        return html_content
