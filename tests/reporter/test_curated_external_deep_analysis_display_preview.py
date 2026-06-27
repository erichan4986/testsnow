from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "curated_external_deep_analysis_display_preview.py"


def _long_excerpt(length: int = 520) -> str:
    return "公司收入增长和商业化进展仍需公告验证，外部材料仅作为专业观察。" * (length // 32)


def _card(card_id: str, topic: str = "industry_logic") -> dict:
    return {
        "schema_version": "periodic_report_narrative_evidence_card.v1",
        "card_id": card_id,
        "topic": topic,
        "source_type": "curated_external_analysis_evidence",
        "source_kind": "wechat_high_quality_analysis",
        "title": f"寒武纪外部观察 {card_id}",
        "source_excerpt": _long_excerpt(),
        "source_excerpt_hash": f"seh_{card_id}",
        "source_block_hash": f"sbh_{card_id}",
        "source_ref": f"https://mp.weixin.qq.com/s/{card_id}",
        "source_credit": 55,
        "quality_action": "preview_only",
        "knowledge_eligible": False,
        "synthesis_eligible": True,
        "synthesis_display_only": True,
        "scoring_eligible": False,
        "risk_score_eligible": False,
        "verification_status": "professional_observation",
    }


def _write_cards_json(path: Path, cards: list[dict]) -> Path:
    excerpt_packs = [
        {
            "card_id": card["card_id"],
            "excerpts": [
                {
                    "source_excerpt_hash": card["source_excerpt_hash"],
                    "normalized_substring_verified": True,
                }
            ],
        }
        for card in cards
    ]
    path.write_text(
        json.dumps(
            {
                "schema_version": "curated_external_evidence_cards.v1",
                "wrote_knowledge": False,
                "connected_synthesis": False,
                "cards": cards,
                "excerpt_packs": excerpt_packs,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def test_curated_external_deep_analysis_display_preview_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--cards-json" in result.stdout
    assert "--output" in result.stdout
    assert "--json-output" in result.stdout
    assert "--stock" in result.stdout


def test_curated_external_deep_analysis_display_preview_writes_markdown_and_json(tmp_path: Path) -> None:
    cards_json = _write_cards_json(
        tmp_path / "cards.json",
        [
            _card("c1", "industry_logic"),
            _card("c2", "commercialization"),
            _card("c3", "earnings_context"),
        ],
    )
    output = tmp_path / "deep.md"
    json_output = tmp_path / "summary.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--cards-json",
            str(cards_json),
            "--stock",
            "寒武纪",
            "--output",
            str(output),
            "--json-output",
            str(json_output),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["has_deep_analysis_display"] is True
    assert payload["has_synthesis_display"] is False
    assert payload["wrote_knowledge"] is False
    assert payload["connected_synthesis"] is False
    assert payload["rendered_path"] == str(output)
    assert payload["json_output_path"] == str(json_output)

    markdown = output.read_text(encoding="utf-8")
    assert "## 四、深度分析" in markdown
    assert "微信公众号精选观察" in markdown
    assert "外部材料仅作为专业观察" in markdown

    summary = json.loads(json_output.read_text(encoding="utf-8"))
    assert summary["status"] == "ok"
    assert summary["stats"]["cards_eligible"] == 3
    assert summary["lint"]["ok"] is True
    assert summary["canonical_keys"]["has_synthesis_text"] is True
    assert summary["canonical_keys"]["has_synthesis_display"] is False


def test_curated_external_deep_analysis_display_preview_reports_stock_gate_failure(tmp_path: Path) -> None:
    cards_json = _write_cards_json(tmp_path / "cards.json", [_card("c1", "industry_logic")])
    output = tmp_path / "deep.md"
    json_output = tmp_path / "summary.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--cards-json",
            str(cards_json),
            "--stock",
            "圣邦股份",
            "--output",
            str(output),
            "--json-output",
            str(json_output),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "stock_gate_failed"
    assert payload["has_deep_analysis_display"] is False
    assert output.read_text(encoding="utf-8").strip() == ""

    summary = json.loads(json_output.read_text(encoding="utf-8"))
    assert summary["status"] == "stock_gate_failed"
    assert summary["stats"]["cards_eligible"] == 1
