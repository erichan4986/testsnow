"""知识沉淀 Skill — 将 Pipeline 中间产物写入 Obsidian 知识库。"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

if __name__.startswith("utils."):
    from ..skill_pipeline import BaseSkill, SkillContext
else:
    from skill_pipeline import BaseSkill, SkillContext

logger = logging.getLogger(__name__)


class KnowledgePersistenceSkill(BaseSkill):
    """将报告 Pipeline 的中间产物写入知识库。"""

    name = "knowledge_persistence"
    input_keys = ["stock_name", "date_str"]
    output_keys = []

    def __init__(self, vault_root: str = None, **kwargs):
        super().__init__(**kwargs)
        if vault_root is None:
            vault_root = Path(__file__).parent.parent.parent.parent / "knowledge"
        self.vault_root = Path(vault_root)
        self.stocks_dir = self.vault_root / "10-Stocks"

    def run(self, ctx: SkillContext) -> SkillContext:
        """读取 ctx 中的中间产物，写入知识库。"""
        stock_name = ctx.get("stock_name")
        date_str = ctx.get("date_str")

        if not stock_name or not date_str:
            logger.warning("knowledge_persistence: 缺少 stock_name 或 date_str，跳过")
            return ctx

        stock_dir = self.stocks_dir / stock_name
        stock_dir.mkdir(parents=True, exist_ok=True)

        self._write_deep_analysis(stock_dir, stock_name, date_str, ctx)
        self._write_core_data(stock_dir, stock_name, date_str, ctx)
        self._write_featured_posts(stock_dir, stock_name, date_str, ctx)
        self._update_moc(stock_dir, stock_name, date_str, ctx)

        return ctx

    def _frontmatter(self, stock_name: str, date: str, category: str, tags: List[str] = None) -> str:
        meta = {
            "stock": stock_name,
            "date": f"{date[:4]}-{date[4:6]}-{date[6:]}",
            "category": category,
            "generated_by": "KnowledgePersistenceSkill",
            "tags": tags or [category, stock_name],
        }
        return json.dumps(meta, ensure_ascii=False, indent=2)

    def _write_deep_analysis(self, stock_dir: Path, stock_name: str, date: str, ctx: SkillContext):
        """写入深度分析：多空观点 + 综合叙事 + 跨源摘要。"""
        synthesis = ctx.get("synthesis", {})
        bullish = ctx.get("bullish_args", [])
        bearish = ctx.get("bearish_args", [])
        cross = ctx.get("cross_source_summary", "")
        total_score = ctx.get("total_score")
        pillar = ctx.get("pillar_scores", {})

        lines = [
            "---",
            self._frontmatter(stock_name, date, "深度解读", ["深度解读", stock_name, "AI分析"]),
            "---",
            "",
            f"# {stock_name} - {date} 深度解读",
            "",
            "## 综合评分",
        ]
        if total_score is not None:
            lines.append(f"**总评分**: {total_score}/10")
        lines.append("")
        if pillar:
            lines.append("| 维度 | 得分 |")
            lines.append("|------|------|")
            for dim, score in pillar.items():
                lines.append(f"| {dim} | {score} |")
            lines.append("")

        lines.extend([
            "## 看多论点",
            "",
        ])
        if bullish:
            for arg in bullish:
                lines.append(f"- {arg}")
        else:
            lines.append("_无明确看多观点_")
        lines.append("")

        lines.extend([
            "## 看空论点",
            "",
        ])
        if bearish:
            for arg in bearish:
                lines.append(f"- {arg}")
        else:
            lines.append("_无明确看空观点_")
        lines.append("")

        if cross:
            lines.extend([
                "## 跨源摘要",
                "",
                cross,
                "",
            ])

        if synthesis:
            lines.extend([
                "## AI 综合叙事",
                "",
            ])
            for key, value in synthesis.items():
                lines.append(f"### {key}")
                lines.append(value)
                lines.append("")

        filepath = stock_dir / f"{date}-深度解读.md"
        filepath.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"知识沉淀: {filepath}")

    def _write_core_data(self, stock_dir: Path, stock_name: str, date: str, ctx: SkillContext):
        """写入核心数据快照：报价、估值、图表路径。"""
        quote = ctx.get("quote")
        consensus = ctx.get("consensus")
        ind_fwd_pe = ctx.get("ind_fwd_pe")
        chart_paths = ctx.get("chart_paths", {})
        md_path = ctx.get("md_path")
        html_path = ctx.get("html_path")

        lines = [
            "---",
            self._frontmatter(stock_name, date, "核心数据", ["核心数据", stock_name, "快照"]),
            "---",
            "",
            f"# {stock_name} - {date} 核心数据",
            "",
            "## 实时估值",
        ]

        if quote:
            lines.append("| 指标 | 数值 |")
            lines.append("|------|------|")
            for k, v in quote.items():
                if isinstance(v, (int, float, str)):
                    lines.append(f"| {k} | {v} |")
            lines.append("")
        else:
            lines.append("_无实时报价数据_")
            lines.append("")

        if consensus:
            lines.extend([
                "## 一致预期",
                "",
            ])
            for k, v in consensus.items():
                lines.append(f"- {k}: {v}")
            lines.append("")

        if ind_fwd_pe is not None:
            lines.extend([
                "## 行业估值",
                f"- 行业 Forward PE: {ind_fwd_pe}",
                "",
            ])

        if chart_paths:
            lines.extend([
                "## 图表产出",
                "",
            ])
            for name, path in chart_paths.items():
                if path:
                    lines.append(f"- {name}: `{path}`")
            lines.append("")

        if md_path or html_path:
            lines.extend([
                "## 报告文件",
                "",
            ])
            if md_path:
                lines.append(f"- Markdown: `{md_path}`")
            if html_path:
                lines.append(f"- HTML: `{html_path}`")
            lines.append("")

        filepath = stock_dir / f"{date}-核心数据.md"
        filepath.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"知识沉淀: {filepath}")

    def _write_featured_posts(self, stock_dir: Path, stock_name: str, date: str, ctx: SkillContext):
        """写入精选帖子详情（从报告中移除的 FeaturedPosts / CommentHighlights）。"""
        keep_posts = ctx.get("keep_posts", [])
        all_posts = ctx.get("all_posts", [])

        if not keep_posts:
            return

        lines = [
            "---",
            self._frontmatter(stock_name, date, "精选帖子", ["精选帖子", stock_name, "社区"]),
            "---",
            "",
            f"# {stock_name} - {date} 精选帖子",
            f"\n> 共 {len(keep_posts)} 篇高质量帖子，来源：雪球网",
            "",
        ]

        for idx, post in enumerate(keep_posts, 1):
            title = post.get("title", "无标题")
            author = post.get("author", "匿名")
            url = post.get("url", "")
            content = post.get("content", "")
            likes = post.get("likes", 0)
            comments = post.get("comments", 0)
            reposts = post.get("reposts", 0)

            lines.append(f"## {idx}. {title}")
            lines.append("")
            lines.append(f"- **作者**: {author}")
            if url:
                lines.append(f"- **链接**: {url}")
            lines.append(f"- **互动**: 👍 {likes}  💬 {comments}  ↗️ {reposts}")
            lines.append("")

            if content:
                # 截取前 500 字作为摘要
                excerpt = content[:500] + "..." if len(content) > 500 else content
                lines.append("### 核心摘录")
                lines.append("")
                lines.append(excerpt)
                lines.append("")

        filepath = stock_dir / f"{date}-精选帖子.md"
        filepath.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"知识沉淀: {filepath}")

    def _update_moc(self, stock_dir: Path, stock_name: str, date: str, ctx: SkillContext):
        """更新 MOC (Map of Content) 索引。"""
        import re
        moc_path = stock_dir / "MOC.md"

        existing_links = set()
        if moc_path.exists():
            content = moc_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                match = re.search(r"\[\[(.*?)\]\]", line)
                if match:
                    existing_links.add(match.group(1))

        new_links = {
            f"{date}-深度解读",
            f"{date}-核心数据",
            f"{date}-精选帖子",
        }
        all_links = existing_links | new_links
        sorted_links = sorted(all_links, reverse=True)

        lines = [
            "---",
            json.dumps({
                "stock": stock_name,
                "last_updated": f"{date[:4]}-{date[4:6]}-{date[6:]}",
            }, ensure_ascii=False),
            "---",
            "",
            f"# {stock_name} 知识索引",
            "",
            f"## 本期快照（{date[:4]}-{date[4:6]}-{date[6:]}）",
        ]
        for link in sorted_links:
            if link.startswith(date):
                lines.append(f"- [[{link}]]")

        lines.extend([
            "",
            "## 历史数据",
        ])
        for link in sorted_links:
            if not link.startswith(date):
                lines.append(f"- [[{link}]]")

        lines.append("")
        moc_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"知识沉淀 MOC: {moc_path}")
