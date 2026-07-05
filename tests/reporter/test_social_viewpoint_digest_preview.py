from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "previews"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import social_viewpoint_digest_preview as preview_module
from social_viewpoint_digest_preview import main


def _write_report_input(tmp_path: Path) -> Path:
    payload = {
        "stocks_data": {
            "测试股": [
                {
                    "title": "雪球产业长文",
                    "content": "外部社媒长文认为公司商业化窗口仍取决于客户车型放量。" + "订单节奏需要持续验证。" * 20,
                    "url": "https://xueqiu.com/1/social",
                    "author": "雪球作者",
                    "source": "xueqiu",
                }
            ]
        },
        "raw_data": {"测试股": {"zhihu": {"report_items": []}}},
    }
    path = tmp_path / "report_input.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_baseline(tmp_path: Path, text: str = "canonical synthesis text") -> Path:
    path = tmp_path / "baseline.txt"
    path.write_text(text, encoding="utf-8")
    return path


def _fake_extractor(source_packets, baseline_text, fingerprint):
    from curated_external_full_body_viewpoint_claims import normalized_hash

    source = source_packets[0]
    quote = source["content"][:80]
    return [
        {
            "schema_version": "curated_external_viewpoint_claim.v1",
            "claim_id": "social-claim-1",
            "stock_name": "测试股",
            "claim_type": "watch_variable",
            "topic": "competition_commercialization",
            "claim": "外部社媒长文认为公司商业化窗口仍取决于客户车型放量。",
            "source_quote": quote,
            "source_quote_hash": normalized_hash(quote),
            "why_incremental": "baseline 未覆盖该商业化节奏分歧。",
            "baseline_overlap": "none",
            "source_id": source["source_id"],
            "source_ref": source["source_ref"],
            "source_title": source["title"],
            "source_account": source["account"],
            "evidence_refs": [source["source_id"]],
            "evidence_hashes": [
                {
                    "source_id": source["source_id"],
                    "source_block_hash": source["source_content_hash"],
                    "source_quote_hash": normalized_hash(quote),
                }
            ],
            "verification_status": "professional_observation",
            "source_credit": 45,
            "claim_source_credit": 45,
            "quality_action": "preview_only",
            "knowledge_eligible": False,
            "synthesis_display_only": True,
            "scoring_eligible": False,
            "risk_score_eligible": False,
        }
    ]


def test_social_viewpoint_digest_cli_writes_only_tmp_outputs(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(preview_module, "_build_extractor", lambda args: _fake_extractor)
    stock = f"social_cli_{uuid.uuid4().hex[:8]}"

    rc = main(
        [
            "--report-input-json",
            str(_write_report_input(tmp_path)),
            "--baseline-synthesis-file",
            str(_write_baseline(tmp_path)),
            "--stock",
            "测试股",
            "--output",
            f"/tmp/{stock}_social_viewpoint_digest.md",
            "--json-output",
            f"/tmp/{stock}_social_viewpoint_digest.json",
            "--min-display-claims",
            "1",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["status"] == "ok"
    assert payload["wrote_repo_path"] is False
    assert payload["source_packets_count"] == 1
    assert payload["json_output_path"].startswith("/tmp/") or payload["json_output_path"].startswith("/private/tmp/")
    assert payload["markdown_output_path"].startswith("/tmp/") or payload["markdown_output_path"].startswith("/private/tmp/")
    assert Path(payload["json_output_path"]).exists()
    assert Path(payload["markdown_output_path"]).exists()


def test_social_viewpoint_digest_cli_rejects_rendered_markdown_baseline(tmp_path: Path, capsys):
    rc = main(
        [
            "--report-input-json",
            str(_write_report_input(tmp_path)),
            "--baseline-synthesis-file",
            str(_write_baseline(tmp_path, "## 四、深度分析\n### 4.4 外部观点")),
            "--stock",
            "测试股",
            "--extractor",
            "heuristic",
            "--min-display-claims",
            "1",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "rendered report" in captured.err
