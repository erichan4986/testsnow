"""估值与财务快照板块渲染器。"""

from typing import Any, Dict, List, Optional


_FINANCIAL_TREND_KEYS = ("revenue", "net_profit", "operating_cash_flow")
_NO_QUOTE_NOTE = "> 实时行情暂不可用，以下仅展示结构化年度财务趋势。"


def _safe_cells(values: Any, count: int) -> bool:
    return (isinstance(values, list) and len(values) == count
            and all(isinstance(value, str) and value and "|" not in value
                    and "\n" not in value for value in values))


class ValuationRenderer:
    """估值与财务快照 — 实时估值指标 + Forward 估值 + 最新财务快照 + 同业对比。"""

    @staticmethod
    def required_keys() -> List[str]:
        return ["stock_name"]

    def render(self, ctx: Dict[str, Any]) -> str:
        stock_name = ctx.get("stock_name", "")
        if not stock_name:
            return ""

        stock_codes = ctx.get("stock_codes", {})
        code = stock_codes.get(stock_name, "")
        if not code:
            return ""

        quote = ctx.get("quote")
        consensus = ctx.get("consensus")

        # Lazy fetch if not in ctx
        if quote is None:
            try:
                from ..data_fetcher import fetch_tencent_quote
                quote = fetch_tencent_quote(code)
            except ImportError:
                try:
                    import sys
                    from pathlib import Path
                    utils_dir = Path(__file__).parent.parent.parent
                    if str(utils_dir) not in sys.path:
                        sys.path.insert(0, str(utils_dir))
                    from reporter.data_fetcher import fetch_tencent_quote
                    quote = fetch_tencent_quote(code)
                except Exception:
                    quote = None

        if consensus is None:
            try:
                from ..data_fetcher import fetch_consensus_eps
                consensus = fetch_consensus_eps(code)
            except ImportError:
                try:
                    import sys
                    from pathlib import Path
                    utils_dir = Path(__file__).parent.parent.parent
                    if str(utils_dir) not in sys.path:
                        sys.path.insert(0, str(utils_dir))
                    from reporter.data_fetcher import fetch_consensus_eps
                    consensus = fetch_consensus_eps(code)
                except Exception:
                    consensus = None

        if not quote:
            trend_md = self._financial_trend_table(ctx.get("financial_trend_view"), code)
            return "\n\n".join(("## 二、估值与财务快照", _NO_QUOTE_NOTE, trend_md)) if trend_md else ""

        price = quote.get("price", 0)
        pe_ttm = quote.get("pe_ttm", 0)
        pb = quote.get("pb", 0)
        mcap = quote.get("mcap_yi", 0)
        change_pct = quote.get("change_pct", 0)
        float_mcap_display = self._format_float_mcap(quote)

        lines = [
            "## 二、估值与财务快照",
            "",
            "**数据日期**: 实时 | **数据来源**: 腾讯财经实时行情 + 同花顺机构一致预期",
            "",
            "### 实时估值指标",
            "",
            "| 指标 | 数值 | 说明 |",
            "|------|------|------|",
            f"| 最新价 | {price:.2f} 元 | 较前日 {'+' if change_pct >= 0 else ''}{change_pct:.2f}% |",
            f"| 总市值 | {mcap:.1f} 亿 | 流通市值 {float_mcap_display} |",
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

        # 最新财务快照
        fin_md = self._quarterly_financials_table(code)
        if fin_md:
            lines.append(fin_md)
        trend_md = self._financial_trend_table(ctx.get("financial_trend_view"), code)
        if trend_md:
            lines.append(trend_md)

        # 同业对比
        try:
            from ..data_fetcher import fetch_competitor_metrics, competitor_metrics_table
        except ImportError:
            try:
                import sys
                from pathlib import Path
                utils_dir = Path(__file__).parent.parent.parent
                if str(utils_dir) not in sys.path:
                    sys.path.insert(0, str(utils_dir))
                from reporter.data_fetcher import fetch_competitor_metrics, competitor_metrics_table
            except Exception:
                fetch_competitor_metrics = None
                competitor_metrics_table = None

        if fetch_competitor_metrics and competitor_metrics_table:
            stock_codes = ctx.get("stock_codes", {})
            stock_config = ctx.get("stock_config", {})
            comp_metrics = ctx.get("competitor_metrics") or fetch_competitor_metrics(
                stock_name,
                stock_codes,
                stock_config=stock_config,
            )
            if comp_metrics:
                lines.append(
                    competitor_metrics_table(
                        stock_name,
                        comp_metrics,
                        stock_config=stock_config,
                    )
                )
                lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _financial_trend_table(view: Any, stock_code: str) -> str:
        if not isinstance(view, dict) or (
            view.get("schema_version") != "financial_trend_view.v1"
            or view.get("status") != "ready"
            or view.get("display_eligible") is not True
            or view.get("scoring_eligible") is not False
            or str(view.get("stock_code") or "") != str(stock_code)
        ):
            return ""
        years, rows, ratio = (
            view.get("years"), view.get("rows"), view.get("cash_conversion"),
        )
        if (
            not isinstance(years, list) or len(years) != 3
            or not all(isinstance(year, int) for year in years)
            or years != list(range(years[0], years[0] + 3))
            or not isinstance(rows, list) or len(rows) != 3
            or not isinstance(ratio, dict)
        ):
            return ""
        display_rows = []
        for row, metric_key in zip(rows, _FINANCIAL_TREND_KEYS):
            values = row.get("values") if isinstance(row, dict) else None
            if (
                not isinstance(row, dict)
                or row.get("metric_key") != metric_key or row.get("unit") != "亿元"
                or not _safe_cells([row.get("label")], 1)
                or not _safe_cells(values, 3)
                or not _safe_cells([row.get("latest_growth_rate")], 1)
            ):
                return ""
            display_rows.append([f"{row['label']}（{row['unit']}）", *values, row["latest_growth_rate"]])
        if (
            ratio.get("metric_key") != "operating_cash_flow_to_net_profit"
            or ratio.get("label") != "现金转换率"
            or ratio.get("unit") != "%"
            or ratio.get("latest_growth_rate") != "—"
            or not _safe_cells(ratio.get("values"), 3)
        ):
            return ""
        summary, source = view.get("summary"), view.get("source_label")
        if not _safe_cells([summary, source], 2):
            return ""
        display_rows.append(["现金转换率", *ratio["values"], "—"])
        return "\n".join([
            "### 近三年财务趋势", "",
            "| 指标 | " + " | ".join(map(str, years)) + " | 最新同比 |",
            "|------|------|------|------|----------|",
            *("| " + " | ".join(row) + " |" for row in display_rows),
            "", f"> **趋势观察**: {summary}", ">", f"> 数据来源：{source}", "",
        ])

    @staticmethod
    def _format_float_mcap(quote: dict) -> str:
        quality = quote.get("market_cap_quality")
        if quality == "market_cap_inconsistent":
            return "N/A（口径冲突）"
        value = quote.get("float_mcap_yi")
        if value is None:
            return "N/A"
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "N/A"
        if numeric <= 0:
            return "N/A"
        return f"{numeric:.1f} 亿"

    def _quarterly_financials_table(self, code: str) -> str:
        """最新财务数据快照（含同比）。"""
        try:
            from ..data_fetcher import fetch_latest_quarterly_financials
        except ImportError:
            try:
                import sys
                from pathlib import Path
                utils_dir = Path(__file__).parent.parent.parent
                if str(utils_dir) not in sys.path:
                    sys.path.insert(0, str(utils_dir))
                from reporter.data_fetcher import fetch_latest_quarterly_financials
            except Exception:
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
