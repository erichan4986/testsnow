"""HTML Dashboard 板块渲染器。"""

from pathlib import Path
from typing import Any, Dict, List, Optional


class HTMLDashboardRenderer:
    """单页 HTML Dashboard（视觉速览）。"""

    @staticmethod
    def required_keys() -> List[str]:
        return ["stock_name", "date_str"]

    def render(self, ctx: Dict[str, Any]) -> str:
        stock_name = ctx.get("stock_name", "")
        date_str = ctx.get("date_str", "")
        if not stock_name or not date_str:
            return ""

        stock_codes = ctx.get("stock_codes", {})
        code = stock_codes.get(stock_name, "")

        # 基础数据
        try:
            from ..data_fetcher import fetch_tencent_quote
        except ImportError:
            try:
                import sys
                from pathlib import Path as _Path
                utils_dir = _Path(__file__).parent.parent.parent
                if str(utils_dir) not in sys.path:
                    sys.path.insert(0, str(utils_dir))
                from reporter.data_fetcher import fetch_tencent_quote
            except Exception:
                fetch_tencent_quote = lambda c: None

        quote = fetch_tencent_quote(code) if code else None
        price = quote.get("price", 0) if quote else 0
        change_pct = quote.get("change_pct", 0) if quote else 0

        # 五维评分与 EV
        all_posts = ctx.get("posts", [])
        stock_raw = ctx.get("stock_raw", {})

        try:
            from ..data_fetcher import fetch_consensus_eps
        except ImportError:
            try:
                import sys
                from pathlib import Path as _Path
                utils_dir = _Path(__file__).parent.parent.parent
                if str(utils_dir) not in sys.path:
                    sys.path.insert(0, str(utils_dir))
                from reporter.data_fetcher import fetch_consensus_eps
            except Exception:
                fetch_consensus_eps = lambda c: None

        consensus = fetch_consensus_eps(code) if code else None
        pillar = ctx.get("pillar")

        try:
            from ..scoring_engine import ev_expectation
        except ImportError:
            try:
                import sys
                from pathlib import Path as _Path
                utils_dir = _Path(__file__).parent.parent.parent
                if str(utils_dir) not in sys.path:
                    sys.path.insert(0, str(utils_dir))
                from reporter.scoring_engine import ev_expectation
            except Exception:
                ev_expectation = lambda p, c: {"ev_pct": None, "signal": "N/A"}

        if pillar is not None:
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
        else:
            total_score = None
            ev_pct = None
            ev_signal = "N/A"
            ev_pct_str = "N/A"
            ev_color = "text-gray-600"

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
        if total_score is not None:
            if total_score >= 7.5:
                op_rec = "积极关注"
            elif total_score >= 6.0:
                op_rec = "关注"
            elif total_score >= 4.0:
                op_rec = "观望"
            else:
                op_rec = "回避"

        # 图表文件名
        chart_paths = ctx.get("chart_paths", ctx.get("_chart_paths", {}))
        tech_img = Path(chart_paths.get("technical", "")).name if chart_paths.get("technical") else ""
        bb_img = Path(chart_paths.get("bullbear", "")).name if chart_paths.get("bullbear") else ""
        radar_img = Path(chart_paths.get("radar", "")).name if chart_paths.get("radar") else ""
        val_img = Path(chart_paths.get("valuation", "")).name if chart_paths.get("valuation") else ""

        # 多空论点
        synthesis = ctx.get("synthesis_display") or ctx.get("synthesis") or {}
        debate_text = synthesis.get("valuation_debate", "")
        fund_text = synthesis.get("fundamentals", "")
        combined = debate_text + "\n" + fund_text

        try:
            from .executive_summary_renderer import _extract_thesis_points
        except ImportError:
            _extract_thesis_points = lambda t, d: []

        bullish_args = _extract_thesis_points(combined, "bullish")
        bearish_args = _extract_thesis_points(combined, "bearish")

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
            ("风险厌恶型", "回避" if (total_score is not None and total_score < 5) else "轻仓观望", "评分偏低" if (total_score is not None and total_score < 5) else "控制仓位"),
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
        if pillar is not None:
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
        else:
            radar_cards = '<p class="text-gray-500 text-sm">数据不足，暂无法评分</p>'

        date_display = ctx.get("date_display", date_str)

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
                    <p class="text-sm text-gray-500 mt-1">{date_display} · 雪球舆情深度分析</p>
                </div>
                <div class="text-right">
                    <div class="text-3xl font-bold text-gray-900">{price:.2f} <span class="text-sm font-normal text-gray-500">元</span></div>
                    <div class="text-sm font-medium {"text-green-600" if change_pct >= 0 else "text-red-600"}">{"+" if change_pct >= 0 else ""}{change_pct:.2f}%</div>
                </div>
            </div>
            <!-- Metric Cards -->
            <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mt-6">
                {_card("综合评分", f"{total_score}/10" if total_score is not None else "N/A", "blue")}
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
            <p class="text-sm text-gray-600">综合技术评分: <span class="font-bold text-blue-600">{(pillar.get('technical', 0) if pillar else 'N/A')}</span> / 10</p>
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
                <a href="{stock_name}_{date_str}.md" class="inline-flex items-center text-blue-600 hover:text-blue-800 font-medium">
                    查看完整分析报告 →
                </a>
                <p class="text-xs text-gray-400">本报告基于雪球网公开讨论数据由 AI 生成，仅供参考，不构成投资建议。</p>
            </div>
        </div>
    </div>
</body>
</html>"""
        return html
