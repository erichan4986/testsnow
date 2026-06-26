from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "curated_external_evidence_cards_preview.py"


def _write_jsonl(path: Path, items: list[dict]) -> Path:
    path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in items)
        + ("\n" if items else ""),
        encoding="utf-8",
    )
    return path


def _item(title: str = "黑芝麻智能华山A2000拿下首个量产项目定点") -> dict:
    return {
        "title": title,
        "content": "黑芝麻智能华山A2000拿下首个量产项目定点，预计2026年量产，但车型名称和收入节奏仍待验证。",
        "source_type": "curated_external_analysis",
        "source_kind": "wechat_customer_order_or_design_win",
        "verification_status": "professional_observation",
        "quality_action": "preview_only",
        "knowledge_eligible": False,
        "synthesis_eligible": True,
        "synthesis_display_only": True,
        "scoring_eligible": False,
        "risk_score_eligible": False,
        "topic": "commercialization",
        "url": "https://mp.weixin.qq.com/s/design-win",
        "source_ref": "https://mp.weixin.qq.com/s/design-win",
        "account": "高工智能汽车",
        "publish_time": "2026-02-24",
    }


def test_curated_external_evidence_cards_preview_help_runs():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--synthesis-items-jsonl" in result.stdout
    assert "--cards-json" in result.stdout
    assert "--output" in result.stdout


def test_curated_external_evidence_cards_preview_writes_markdown_and_json(tmp_path: Path):
    input_path = _write_jsonl(tmp_path / "items.jsonl", [_item()])
    output = tmp_path / "preview.md"
    cards_json = tmp_path / "cards.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--synthesis-items-jsonl",
            str(input_path),
            "--stock",
            "黑芝麻智能",
            "--output",
            str(output),
            "--cards-json",
            str(cards_json),
            "--max-excerpt-chars",
            "200",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["cards_count"] == 1
    assert payload["excerpt_packs_count"] == 1
    assert payload["wrote_knowledge"] is False
    assert payload["connected_synthesis"] is False

    markdown = output.read_text(encoding="utf-8")
    assert "Curated External Evidence Cards Preview" in markdown
    assert "display-only" in markdown
    assert "黑芝麻智能华山A2000" in markdown
    assert "normalized_substring_verified: `true`" in markdown

    data = json.loads(cards_json.read_text(encoding="utf-8"))
    card = data["cards"][0]
    assert card["schema_version"] == "periodic_report_narrative_evidence_card.v1"
    assert card["knowledge_eligible"] is False
    assert card["synthesis_display_only"] is True
    assert card["scoring_eligible"] is False
    assert card["risk_score_eligible"] is False
