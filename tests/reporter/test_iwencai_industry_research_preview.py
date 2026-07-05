from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
PREVIEWS_DIR = SCRIPTS_DIR / "previews"
sys.path.insert(0, str(PREVIEWS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))


def test_write_iwencai_preview_writes_markdown_without_knowledge(tmp_path: Path) -> None:
    from iwencai_industry_research_preview import write_iwencai_industry_preview

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "status_code": 0,
                "data": [
                    {
                        "uid": "r1",
                        "title": "半导体行业深度报告：设备材料国产化持续推进",
                        "publish_date": "2026-06-20",
                        "organization": "招商证券",
                        "url": "https://ms.10jqka.com.cn/report/r1",
                        "summary": "产业链深度报告。",
                        "score": 0.1,
                    },
                    {
                        "uid": "r2",
                        "title": "圣邦股份300661一季报点评",
                        "publish_date": "2026-06-19",
                        "organization": "国信证券",
                        "url": "https://ms.10jqka.com.cn/report/r2",
                        "summary": "个股研报。",
                        "score": 0.2,
                    },
                ],
            }

    def fake_post(*args, **kwargs):
        return FakeResponse()

    output_path = tmp_path / "iwencai_preview.md"
    summary = write_iwencai_industry_preview(
        output_path=output_path,
        api_key="secret-key",
        queries=["半导体 行业深度 2026"],
        today=date(2026, 6, 24),
        post=fake_post,
    )

    assert summary["preview_path"] == str(output_path)
    assert summary["selected_count"] == 1
    markdown = output_path.read_text(encoding="utf-8")
    assert "半导体行业深度报告" in markdown
    assert "knowledge_eligible: `false`" in markdown
    assert "stock_specific_or_code_title" in markdown


def test_iwencai_preview_help_runs() -> None:
    script = PREVIEWS_DIR / "iwencai_industry_research_preview.py"
    result = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True, check=False)

    assert result.returncode == 0
    assert "--query" in result.stdout
    assert "--output" in result.stdout
