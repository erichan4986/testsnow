import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "curated_external_candidate_discovery_preview.py"


def test_curated_external_candidate_discovery_preview_cli_writes_markdown_and_jsonl(tmp_path: Path) -> None:
    url_list = tmp_path / "urls.txt"
    url_list.write_text("产业长文 | https://36kr.com/p/123\n", encoding="utf-8")
    selector_file = tmp_path / "wechat.jsonl"
    selector_file.write_text(
        json.dumps(
            {
                "action": "product_signal",
                "candidate": {
                    "title": "圣邦微电子推出SGM25890",
                    "url": "https://mp.weixin.qq.com/s/power",
                    "digest": "90A Smart Power Stage。",
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "preview.md"
    jsonl_output = tmp_path / "candidates.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--url-list",
            str(url_list),
            "--wechat-selector-file",
            str(selector_file),
            "--output",
            str(output),
            "--jsonl-output",
            str(jsonl_output),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["preview_path"] == str(output)
    assert payload["jsonl_path"] == str(jsonl_output)
    assert payload["counts"] == {"url_candidate": 1, "wechat_product_signal": 1}
    assert output.exists()
    assert jsonl_output.exists()
    assert "Curated External Candidate Discovery Preview" in output.read_text(encoding="utf-8")
    assert "wechat_product_signal" in jsonl_output.read_text(encoding="utf-8")


def test_curated_external_candidate_discovery_preview_cli_filters_since_date(tmp_path: Path) -> None:
    selector_file = tmp_path / "wechat.jsonl"
    selector_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "action": "product_signal",
                        "candidate": {
                            "title": "近期新品",
                            "url": "https://mp.weixin.qq.com/s/recent",
                            "publish_time": "2026-06-01 09:00:00",
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "action": "keep",
                        "candidate": {
                            "title": "过旧分析",
                            "url": "https://mp.weixin.qq.com/s/old",
                            "publish_time": "2022-01-01 09:00:00",
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "preview.md"
    jsonl_output = tmp_path / "candidates.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--wechat-selector-file",
            str(selector_file),
            "--since-date",
            "2025-12-27",
            "--output",
            str(output),
            "--jsonl-output",
            str(jsonl_output),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in jsonl_output.read_text(encoding="utf-8").splitlines()]
    assert [row["title"] for row in rows] == ["近期新品"]
    assert "过旧分析" not in output.read_text(encoding="utf-8")


def test_curated_external_candidate_discovery_preview_cli_filters_theme_keywords(tmp_path: Path) -> None:
    curated = tmp_path / "curated.json"
    curated.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "source_kind": "jina_url",
                        "title": "光模块长文",
                        "url": "https://example.com/optical",
                        "content": "光模块和 CPO 产业链。",
                        "quality_action": "preview_only",
                    },
                    {
                        "source_kind": "jina_url",
                        "title": "模拟芯片长文",
                        "url": "https://example.com/analog",
                        "content": "圣邦股份、模拟芯片、信号链、电源管理与车规产品线。",
                        "quality_action": "preview_only",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "preview.md"
    jsonl_output = tmp_path / "candidates.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--curated-preview-file",
            str(curated),
            "--theme-keywords",
            "圣邦,模拟芯片,信号链,电源管理,车规",
            "--min-theme-score",
            "1",
            "--output",
            str(output),
            "--jsonl-output",
            str(jsonl_output),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in jsonl_output.read_text(encoding="utf-8").splitlines()]
    assert [row["title"] for row in rows] == ["模拟芯片长文"]
    assert rows[0]["theme_score"] > 0
    assert "光模块长文" not in output.read_text(encoding="utf-8")


def test_curated_external_candidate_discovery_preview_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--url-list" in result.stdout
    assert "--materials-dir" in result.stdout
    assert "--wechat-selector-file" in result.stdout
    assert "--curated-preview-file" in result.stdout
    assert "--since-date" in result.stdout
    assert "--theme-keywords" in result.stdout
    assert "--min-theme-score" in result.stdout
