import json
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ObsidianWriter:
    """
    将采集的数据写入 Obsidian 格式的原子笔记
    """

    def __init__(self, vault_root: str = None):
        if vault_root is None:
            vault_root = Path(__file__).parent.parent.parent / "knowledge"
        self.vault_root = Path(vault_root)
        self.stocks_dir = self.vault_root / "10-Stocks"
        self.meta_dir = self.vault_root / "99-Meta"

    def write_atomic_note(
        self,
        stock_name: str,
        code: str,
        date: str,
        category: str,
        data: Dict,
        data_source: str,
        analysis: str = "",
        confidence: str = "确认事实",
        valid_days: int = 7,
    ) -> Path:
        """
        写入一篇原子笔记
        """
        stock_dir = self.stocks_dir / stock_name
        stock_dir.mkdir(parents=True, exist_ok=True)

        valid_until = (datetime.strptime(date, "%Y%m%d") + timedelta(days=valid_days)).strftime("%Y-%m-%d")

        filename = f"{date}-{category}.md"
        filepath = stock_dir / filename

        frontmatter = {
            "stock": stock_name,
            "code": code,
            "date": datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d"),
            "category": category,
            "data_source": data_source,
            "valid_until": valid_until,
            "confidence": confidence,
            "tags": [category, stock_name],
        }

        lines = [
            "---",
            json.dumps(frontmatter, ensure_ascii=False, indent=2),
            "---",
            "",
            f"# {stock_name} - {date} {category}",
            "",
            "## 原始数据",
        ]

        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"- **{key}**:")
                for k, v in value.items():
                    lines.append(f"  - {k}: {v}")
            elif isinstance(value, list):
                lines.append(f"- **{key}**: {len(value)} 条")
                for item in value[:5]:
                    if isinstance(item, dict):
                        title = item.get("title", "")
                        lines.append(f"  - {title}")
            else:
                lines.append(f"- **{key}**: {value}")

        if analysis:
            lines.extend(["", "## 分析", analysis])

        lines.extend(["", "## 相关链接", f"- [[{date}-深度分析]]"])

        filepath.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"原子笔记已写入: {filepath}")
        return filepath

    def update_moc(self, stock_name: str, code: str, date: str, note_links: list):
        """
        更新或创建该股票的 MOC (Map of Content)
        """
        stock_dir = self.stocks_dir / stock_name
        stock_dir.mkdir(parents=True, exist_ok=True)
        moc_path = stock_dir / "MOC.md"

        existing_links = set()
        if moc_path.exists():
            content = moc_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.strip().startswith("- [["):
                    link = line.strip()[3:].split("]]")[0]
                    existing_links.add(link)

        all_links = existing_links | set(note_links)
        sorted_links = sorted(all_links, reverse=True)

        moc_content = [
            "---",
            json.dumps({"stock": stock_name, "code": code, "last_updated": datetime.now().strftime("%Y-%m-%d")}, ensure_ascii=False),
            "---",
            "",
            f"# {stock_name} 知识索引",
            "",
            f"## 本期数据快照（{datetime.strptime(date, '%Y%m%d').strftime('%Y-%m-%d')}）",
        ]
        for link in sorted_links:
            if link.startswith(date):
                moc_content.append(f"- [[{link}]]")

        moc_content.extend(["", "## 历史数据"])
        for link in sorted_links:
            if not link.startswith(date):
                moc_content.append(f"- [[{link}]]")

        moc_content.extend([
            "",
            "## 跨概念链接",
            "- [[模拟芯片赛道]]",
            "- [[半导体行业跟踪]]",
            "",
        ])

        moc_path.write_text("\n".join(moc_content), encoding="utf-8")
        logger.info(f"MOC 已更新: {moc_path}")

    def update_weekly_index(self, code: str, date: str, note_path: str, report_path: str):
        """
        更新 weekly_index.json，用于周期性报告聚合
        """
        index_path = self.meta_dir / "weekly_index.json"
        index_data = {}
        if index_path.exists():
            try:
                index_data = json.loads(index_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        if code not in index_data:
            index_data[code] = []

        exists = any(entry["date"] == date for entry in index_data[code])
        if not exists:
            index_data[code].append({
                "date": date,
                "note_path": note_path,
                "report_path": report_path,
            })
            index_data[code].sort(key=lambda x: x["date"])

        index_path.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")
