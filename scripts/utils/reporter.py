import os
import logging
from datetime import datetime
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class ReportManager:
    """报告文件管理器"""

    DEFAULT_REPORT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "reports"))

    def __init__(self, report_dir: str = None):
        self.report_dir = report_dir or self.DEFAULT_REPORT_DIR
        os.makedirs(self.report_dir, exist_ok=True)

    def save_report(self, markdown_content: str, filename: str = None) -> str:
        """
        保存 Markdown 报告到文件

        Args:
            markdown_content: 报告 Markdown 内容
            filename: 自定义文件名，默认 xueqiu_report_YYYYMMDD.md

        Returns:
            保存的文件路径
        """
        if not filename:
            date_str = datetime.now().strftime("%Y%m%d")
            filename = f"xueqiu_report_{date_str}.md"

        filepath = os.path.join(self.report_dir, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            logger.info(f"报告已保存: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"保存报告失败: {e}")
            raise

    def save_raw_data(self, data: Dict[str, List[Dict]], filename: str = None) -> str:
        """
        保存原始采集数据为 JSON

        Args:
            data: 原始股票数据
            filename: 自定义文件名

        Returns:
            保存的文件路径
        """
        import json

        if not filename:
            date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"raw_data_{date_str}.json"

        # 默认保存到项目 data/raw/ 目录
        raw_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")
        raw_dir = os.path.abspath(raw_dir)
        os.makedirs(raw_dir, exist_ok=True)

        filepath = os.path.join(raw_dir, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"原始数据已保存: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"保存原始数据失败: {e}")
            raise

    def list_reports(self) -> List[str]:
        """列出所有已生成的报告"""
        try:
            files = sorted(
                [f for f in os.listdir(self.report_dir) if f.endswith(".md")],
                reverse=True
            )
            return files
        except Exception:
            return []

    def get_latest_report_path(self) -> str:
        """获取最新报告路径"""
        reports = self.list_reports()
        if reports:
            return os.path.join(self.report_dir, reports[0])
        return ""
