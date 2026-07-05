from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "previews"))

from formal_first_source_policy_preview import main


def _write_report_input(tmp_path: Path, stock_raw: dict, posts: list | None = None) -> Path:
    payload = {
        "stocks_data": {"测试股": posts or []},
        "raw_data": {"测试股": stock_raw},
    }
    path = tmp_path / "report_input.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_formal_first_preview_reports_enough_formal_sources(tmp_path: Path, capsys):
    output = f"/tmp/formal_first_{uuid.uuid4().hex[:8]}.json"
    stock_raw = {
        "reports": [{"title": "券商研报", "content": "正式研报内容", "institution": "测试证券"}],
        "announcements": [{"title": "公司公告", "content": "公告内容", "date": "2026-06-01"}],
        "fundflow": [],
        "news": [{"title": "主流新闻", "content": "新闻内容", "source": "财联社"}],
        "zhihu": {
            "report_items": [
                {
                    "title": "知乎观点",
                    "content": "知乎内容",
                    "author_name": "知乎作者",
                    "url": "https://zhihu.com/question/1",
                }
            ]
        },
    }
    posts = [{"title": "雪球帖", "content": "雪球内容", "source": "雪球"}]

    rc = main(
        [
            "--report-input-json",
            str(_write_report_input(tmp_path, stock_raw, posts)),
            "--stock",
            "测试股",
            "--output",
            output,
            "--min-formal-items",
            "2",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["status"] == "ok"
    assert payload["formal_items_count"] == 3
    assert payload["legacy_items_count"] == 5
    assert payload["excluded_social_counts"] == {"xueqiu": 1, "zhihu": 1}
    assert "雪球" not in payload["formal_source_platform_counts"]
    assert "知乎" not in payload["formal_source_platform_counts"]
    assert payload["wrote_repo_path"] is False
    assert Path(payload["output_path"]).exists()


def test_formal_first_preview_marks_social_only_input_insufficient(tmp_path: Path, capsys):
    output = f"/tmp/formal_first_{uuid.uuid4().hex[:8]}.json"
    stock_raw = {
        "reports": [],
        "announcements": [],
        "fundflow": [],
        "news": [],
        "zhihu": {
            "report_items": [
                {
                    "title": "知乎观点",
                    "content": "知乎内容",
                    "author_name": "知乎作者",
                    "url": "https://zhihu.com/question/1",
                }
            ]
        },
    }
    posts = [{"title": "雪球帖", "content": "雪球内容", "source": "雪球"}]

    rc = main(
        [
            "--report-input-json",
            str(_write_report_input(tmp_path, stock_raw, posts)),
            "--stock",
            "测试股",
            "--output",
            output,
            "--min-formal-items",
            "1",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["status"] == "formal_sources_insufficient"
    assert payload["formal_items_count"] == 0
    assert payload["legacy_items_count"] == 2
    assert payload["excluded_social_counts"] == {"xueqiu": 1, "zhihu": 1}
    assert Path(payload["output_path"]).exists()


def test_formal_first_preview_rejects_repo_output_path(tmp_path: Path, capsys):
    rc = main(
        [
            "--report-input-json",
            str(_write_report_input(tmp_path, {"zhihu": {"report_items": []}})),
            "--stock",
            "测试股",
            "--output",
            "formal_first_preview.json",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert "under /tmp" in captured.err


def test_formal_first_preview_script_can_run_directly_with_help():
    script = Path(__file__).resolve().parents[2] / "scripts" / "previews" / "formal_first_source_policy_preview.py"

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--report-input-json" in result.stdout
