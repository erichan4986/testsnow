import json
import logging
import os
from typing import Dict, List, Any
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


class KimiAnalyzer:
    """
    Kimi (Moonshot) API 分析器
    使用 OpenAI 兼容接口调用 Kimi 进行情感分析、话题提取和报告生成
    """

    def __init__(self, api_key: str = None, model: str = None, base_url: str = None):
        self.api_key = api_key or os.getenv("MOONSHOT_API_KEY")
        self.model = model or os.getenv("MOONSHOT_MODEL", "moonshot-v1-128k")
        self.base_url = base_url or os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")

        if not self.api_key:
            logger.warning("MOONSHOT_API_KEY 未设置，LLM 分析将不可用")
            self.client = None
        elif OpenAI is None:
            logger.warning("openai 包未安装，LLM 分析将不可用")
            self.client = None
        else:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )

    def analyze_all_stocks(self, stocks_data: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """
        对所有股票数据进行 LLM 分析

        Args:
            stocks_data: {股票名称: 帖子列表}

        Returns:
            结构化分析结果
        """
        if not self.client:
            logger.error("Kimi API 客户端未初始化，跳过分析")
            return self._fallback_analysis(stocks_data)

        # 构建输入数据摘要（控制 token 长度）
        prompt_data = self._build_analysis_prompt(stocks_data)

        try:
            logger.info("正在调用 Kimi API 生成分析报告...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt_data},
                ],
                temperature=0.3,
                max_tokens=8000,
            )

            content = response.choices[0].message.content
            # 尝试从 markdown json 代码块中提取 JSON
            result = self._extract_json(content)
            logger.info("Kimi 分析报告生成成功")
            return result

        except Exception as e:
            logger.error(f"Kimi API 调用失败: {e}")
            return self._fallback_analysis(stocks_data)

    def generate_report_markdown(self, analysis_result: Dict[str, Any], stocks_data: Dict[str, List[Dict]]) -> str:
        """
        生成最终 Markdown 报告

        如果 analysis_result 包含完整的 report_markdown，直接使用；
        否则基于结构化数据组装报告。
        """
        if analysis_result.get("report_markdown"):
            return analysis_result["report_markdown"]

        return self._assemble_report(analysis_result, stocks_data)

    @staticmethod
    def _system_prompt() -> str:
        return """你是一位专业的股票舆情分析师，擅长从社区讨论中提取投资信号。

## 任务
基于提供的股票社区帖子数据，生成一份结构化的舆情分析报告。

## 分析维度
1. **市场情绪总览**：统计每只股票看多/看空/中性的比例
2. **热门话题提取**：识别讨论焦点（如半导体、AI、医药、新能源、机器人等）
3. **精品内容拆解**：选出质量最高的2-3条帖子，深度分析其观点和逻辑
4. **评论亮点**：摘录有价值的评论观点（雪球评论往往包含更直接的情绪和判断）
5. **风险提示**：识别潜在风险信号

## 输出格式
必须返回有效的 JSON，格式如下：
```json
{
  "market_overview": {
    "summary": "整体市场情绪概述（100字以内）",
    "stocks": [
      {
        "name": "股票名称",
        "sentiment": "看多/看空/中性",
        "sentiment_score": 0-100,
        "key_points": ["核心看点1", "核心看点2"]
      }
    ]
  },
  "hot_topics": [
    {"topic": "话题名称", "mentions": 提及次数, "related_stocks": ["相关股票"]}
  ],
  "featured_posts": [
    {
      "stock": "股票名称",
      "title": "帖子标题",
      "url": "链接",
      "sentiment": "看多/看空/中性",
      "summary": "深度摘要（200字以内）",
      "key_arguments": ["论点1", "论点2"]
    }
  ],
  "comment_highlights": [
    {"stock": "股票名称", "author": "评论作者", "content": "评论内容", "significance": "为什么这条评论有价值"}
  ],
  "risk_alerts": ["风险信号1", "风险信号2"],
  "report_markdown": "完整的 Markdown 格式报告（可选，如果提供则直接用于最终输出）"
}
```

## 注意事项
- 情感判断基于帖子内容语义，不要仅看标题
- 精品帖子标准：观点鲜明、逻辑清晰、有数据或事实支撑、互动量高（评论/点赞多）
- 热门话题要具体，避免过于宽泛的分类
- 输出必须是纯 JSON，不要包含 markdown 代码块标记之外的内容
"""

    @staticmethod
    def _build_analysis_prompt(stocks_data: Dict[str, List[Dict]]) -> str:
        """构建分析 prompt，控制长度"""
        # 检测数据来源
        data_source = "东方财富股吧"
        for posts in stocks_data.values():
            if posts and any(p.get("source") == "xueqiu" for p in posts):
                data_source = "雪球网"
                break

        lines = [
            f"# 股票社区舆情数据（来源：{data_source}）",
            f"\n分析日期: {datetime.now().strftime('%Y-%m-%d')}\n"
        ]

        for stock_name, posts in stocks_data.items():
            lines.append(f"\n## {stock_name}")
            lines.append(f"共 {len(posts)} 条帖子:\n")

            for i, post in enumerate(posts[:15], 1):  # 每只股票最多取15条
                title = post.get("title", "")
                author = post.get("author", "")
                read_count = post.get("read_count", 0)
                comment_count = post.get("comment_count", 0)
                like_count = post.get("like_count", 0)
                time_str = post.get("time", "")
                content = post.get("content", "")[:300]  # 正文截断到300字
                is_repost = post.get("is_repost", False)

                repost_tag = " [转发]" if is_repost else ""
                lines.append(f"{i}. [{title}]{repost_tag}")
                lines.append(f"   作者: {author} | 评论: {comment_count} | 点赞: {like_count} | 时间: {time_str}")
                if content:
                    lines.append(f"   内容摘要: {content}")

                # 如果有评论，取前3条高赞评论
                comments = post.get("comments", [])
                if comments:
                    top_comments = sorted(comments, key=lambda x: x.get("like_count", 0), reverse=True)[:3]
                    lines.append("   热门评论:")
                    for c in top_comments:
                        c_author = c.get("author", "")
                        c_content = c.get("content", "")[:100]
                        c_likes = c.get("like_count", 0)
                        lines.append(f"     - {c_author} (赞{c_likes}): {c_content}")

                lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        """从 LLM 输出中提取 JSON"""
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 代码块提取
        import re
        patterns = [
            r'```json\s*(.*?)\s*```',
            r'```\s*(.*?)\s*```',
        ]
        for pat in patterns:
            match = re.search(pat, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue

        # 尝试找第一个 { 和最后一个 }
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                pass

        logger.warning("无法从 LLM 输出中提取 JSON，返回原始文本")
        return {"raw_text": text, "report_markdown": text}

    @staticmethod
    def _fallback_analysis(stocks_data: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """LLM 不可用时的降级分析"""
        # 检测数据来源
        data_source = "东方财富股吧"
        for posts in stocks_data.values():
            if posts and any(p.get("source") == "xueqiu" for p in posts):
                data_source = "雪球网"
                break

        stocks = []
        for name, posts in stocks_data.items():
            # 简单规则：基于关键词判断情绪
            bullish_keywords = ["涨", "利好", "突破", "买入", "看好", "反弹", "业绩", "增长"]
            bearish_keywords = ["跌", "利空", "卖出", "看空", "下跌", "暴雷", "减持", "亏损"]

            bullish = sum(1 for p in posts for k in bullish_keywords if k in p.get("title", ""))
            bearish = sum(1 for p in posts for k in bearish_keywords if k in p.get("title", ""))

            if bullish > bearish:
                sentiment = "看多"
                score = min(50 + (bullish - bearish) * 5, 90)
            elif bearish > bullish:
                sentiment = "看空"
                score = max(50 - (bearish - bullish) * 5, 10)
            else:
                sentiment = "中性"
                score = 50

            # 取评论量+点赞量最高的作为精品帖
            featured = sorted(
                posts,
                key=lambda x: x.get("comment_count", 0) + x.get("like_count", 0),
                reverse=True
            )[:2]

            stocks.append({
                "name": name,
                "sentiment": sentiment,
                "sentiment_score": score,
                "key_points": [
                    f"热门帖子评论: {p.get('comment_count', 0)} 点赞: {p.get('like_count', 0)}"
                    for p in featured
                ],
            })

        return {
            "market_overview": {
                "summary": f"基于关键词规则的自动分析（LLM 未启用 | 数据来源: {data_source}）",
                "stocks": stocks,
            },
            "hot_topics": [],
            "featured_posts": [],
            "comment_highlights": [],
            "risk_alerts": ["LLM 分析未启用，情绪判断仅基于简单关键词匹配，仅供参考"],
            "report_markdown": "",
        }

    @staticmethod
    def _assemble_report(analysis: Dict[str, Any], stocks_data: Dict[str, List[Dict]]) -> str:
        """手动组装 Markdown 报告（当 LLM 未返回 report_markdown 时）"""
        from datetime import datetime
        now = datetime.now().strftime("%Y年%m月%d日")

        # 检测数据来源
        data_source = "东方财富股吧"
        for posts in stocks_data.values():
            if posts and any(p.get("source") == "xueqiu" for p in posts):
                data_source = "雪球网"
                break

        lines = [
            f"# 股票舆情监控周报 ({now})",
            "",
            "## 市场情绪总览",
            "",
        ]

        overview = analysis.get("market_overview", {})
        lines.append(overview.get("summary", "暂无概述"))
        lines.append("")

        # 情绪统计表
        lines.append("| 股票 | 情绪 | 评分 | 核心看点 |")
        lines.append("|------|------|------|----------|")
        for s in overview.get("stocks", []):
            points = "; ".join(s.get("key_points", [])[:2])
            lines.append(f"| {s['name']} | {s['sentiment']} | {s['sentiment_score']} | {points} |")
        lines.append("")

        # 热门话题
        topics = analysis.get("hot_topics", [])
        if topics:
            lines.append("## 热门话题")
            lines.append("")
            for t in topics:
                stocks = ", ".join(t.get("related_stocks", []))
                lines.append(f"- **{t['topic']}** (提及 {t.get('mentions', 0)} 次) — 相关: {stocks}")
            lines.append("")

        # 精品帖子
        featured = analysis.get("featured_posts", [])
        if featured:
            lines.append("## 精品帖子深度分析")
            lines.append("")
            for fp in featured:
                lines.append(f"### [{fp['stock']}] {fp['title']}")
                lines.append(f"- 链接: {fp.get('url', 'N/A')}")
                lines.append(f"- 情绪: {fp.get('sentiment', '未知')}")
                lines.append(f"- 摘要: {fp.get('summary', '')}")
                args = fp.get("key_arguments", [])
                if args:
                    lines.append("- 核心论点:")
                    for arg in args:
                        lines.append(f"  - {arg}")
                lines.append("")

        # 评论亮点
        comment_highlights = analysis.get("comment_highlights", [])
        if comment_highlights:
            lines.append("## 评论亮点")
            lines.append("")
            for ch in comment_highlights:
                lines.append(f"### [{ch.get('stock', '')}] {ch.get('author', '')}")
                lines.append(f"- {ch.get('content', '')}")
                lines.append(f"- *价值: {ch.get('significance', '')}*")
                lines.append("")

        # 各股票详情
        lines.append("## 各股票详情")
        lines.append("")
        for stock_name, posts in stocks_data.items():
            lines.append(f"### {stock_name}")
            lines.append("")
            if not posts:
                lines.append("*暂无数据*")
                lines.append("")
                continue

            # 根据数据来源调整表头
            if data_source == "雪球网":
                lines.append("| 排名 | 内容摘要 | 作者 | 评论 | 点赞 | 时间 |")
                lines.append("|------|----------|------|------|------|------|")
                for i, p in enumerate(posts[:10], 1):
                    title = p.get("title", "")[:40] + "..." if len(p.get("title", "")) > 40 else p.get("title", "")
                    url = p.get("url", "")
                    title_md = f"[{title}]({url})" if url else title
                    lines.append(
                        f"| {i} | {title_md} | {p.get('author', '')} | "
                        f"{p.get('comment_count', 0)} | {p.get('like_count', 0)} | {p.get('time', '')} |"
                    )
            else:
                lines.append("| 排名 | 标题 | 作者 | 阅读 | 评论 | 时间 |")
                lines.append("|------|------|------|------|------|------|")
                for i, p in enumerate(posts[:10], 1):
                    title = p.get("title", "")[:30] + "..." if len(p.get("title", "")) > 30 else p.get("title", "")
                    url = p.get("url", "")
                    title_md = f"[{title}]({url})" if url else title
                    lines.append(
                        f"| {i} | {title_md} | {p.get('author', '')} | "
                        f"{p.get('read_count', 0)} | {p.get('comment_count', 0)} | {p.get('time', '')} |"
                    )
            lines.append("")

        # 风险提示
        risks = analysis.get("risk_alerts", [])
        if risks:
            lines.append("## 风险提示")
            lines.append("")
            for r in risks:
                lines.append(f"- {r}")
            lines.append("")

        lines.append("---")
        lines.append(f"*报告生成时间: {now} | 数据来源: {data_source}*")

        return "\n".join(lines)
