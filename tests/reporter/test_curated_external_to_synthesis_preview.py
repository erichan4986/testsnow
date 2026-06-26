import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "curated_external_to_synthesis_preview.py"


def _write_candidate_jsonl(path: Path, items: list[dict]) -> Path:
    path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in items)
        + ("\n" if items else ""),
        encoding="utf-8",
    )
    return path


def _safe_candidate(
    title: str,
    source_kind: str = "wechat_high_quality_analysis",
    content_preview: str = "摘要",
    account: str = "测试号",
    publish_time: str = "2026-06-01",
    url: str = "https://mp.weixin.qq.com/s/test",
):
    return {
        "title": title,
        "source_kind": source_kind,
        "source_type": source_kind,
        "content_preview": content_preview,
        "account": account,
        "publish_time": publish_time,
        "url": url,
        "quality_action": "preview_only",
        "knowledge_eligible": False,
        "synthesis_eligible": False,
        "scoring_eligible": False,
        "risk_score_eligible": False,
        "discovery_score": 70,
    }


def test_curated_external_to_synthesis_preview_cli_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--candidate-jsonl" in result.stdout
    assert "--output" in result.stdout
    assert "--jsonl-output" in result.stdout
    assert "--stock" in result.stdout
    assert "--max-items" in result.stdout


def test_curated_external_to_synthesis_preview_cli_writes_markdown_and_jsonl(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    _write_candidate_jsonl(
        candidates,
        [
            _safe_candidate("深度分析", source_kind="wechat_high_quality_analysis"),
            _safe_candidate("新品发布", source_kind="wechat_product_signal"),
        ],
    )
    output = tmp_path / "preview.md"
    jsonl_output = tmp_path / "items.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--candidate-jsonl",
            str(candidates),
            "--stock",
            "测试股",
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
    assert payload["counts"]["industry_logic"] == 1
    assert payload["counts"]["product_roadmap"] == 1

    assert output.exists()
    md = output.read_text(encoding="utf-8")
    assert "display-only" in md
    assert "不接 canonical synthesis" in md or "不接 canonical" in md
    assert jsonl_output.exists()

    rows = [json.loads(line) for line in jsonl_output.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    for row in rows:
        assert row["source_type"] == "curated_external_analysis"
        assert row["verification_status"] == "professional_observation"
        assert row["knowledge_eligible"] is False
        assert row["synthesis_eligible"] is True
        assert row["synthesis_display_only"] is True
        assert row["scoring_eligible"] is False
        assert row["risk_score_eligible"] is False


def test_curated_external_to_synthesis_preview_cli_respects_max_items(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    _write_candidate_jsonl(
        candidates,
        [_safe_candidate(f"分析 {i}", source_kind="wechat_high_quality_analysis") for i in range(5)],
    )
    output = tmp_path / "preview.md"
    jsonl_output = tmp_path / "items.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--candidate-jsonl",
            str(candidates),
            "--max-items",
            "2",
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
    assert payload["items_count"] == 2
    rows = [json.loads(line) for line in jsonl_output.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2


def test_curated_external_to_synthesis_preview_cli_drops_unsafe_items(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    _write_candidate_jsonl(
        candidates,
        [
            _safe_candidate("safe"),
            _safe_candidate("knowledge unsafe", content_preview="x"),
            _safe_candidate("scoring unsafe", content_preview="x"),
            _safe_candidate("risk unsafe", content_preview="x"),
        ],
    )
    # Patch unsafe fields after writing via raw manipulation is awkward; rewrite with explicit flags.
    raw_items = [json.loads(line) for line in candidates.read_text(encoding="utf-8").splitlines()]
    raw_items[1]["knowledge_eligible"] = True
    raw_items[2]["scoring_eligible"] = True
    raw_items[3]["risk_score_eligible"] = True
    _write_candidate_jsonl(candidates, raw_items)

    output = tmp_path / "preview.md"
    jsonl_output = tmp_path / "items.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--candidate-jsonl",
            str(candidates),
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
    assert len(rows) == 1
    assert rows[0]["title"] == "safe"
