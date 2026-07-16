from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "previews"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import curated_external_viewpoint_narrative_preview as _preview_module
from curated_external_viewpoint_narrative_preview import main


def _make_digest(tmp_path: Path, *, stock_name: str = "测试股") -> Path:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))
    from curated_external_full_body_viewpoint_claims import normalized_hash

    text = "外部文章提示800G交付计划下调传言仍需跟踪。"
    digest = {
        "schema_version": "curated_external_viewpoint_digest.v1",
        "status": "ok",
        "stock_name": stock_name,
        "claims": [
            {
                "schema_version": "curated_external_viewpoint_claim.v1",
                "claim_id": "c1",
                "claim_type": "watch_variable",
                "topic": "supply_delivery_capacity",
                "claim": text,
                "source_quote": text,
                "source_quote_hash": normalized_hash(text),
                "why_incremental": "baseline未覆盖。",
                "baseline_overlap": "none",
                "source_id": "source:c1",
                "source_title": "测试微信文章",
                "source_account": "测试账号",
                "source_ref": "https://mp.weixin.qq.com/s/test",
                "verification_status": "professional_observation",
                "source_credit": 55,
                "quality_action": "preview_only",
                "knowledge_eligible": False,
                "synthesis_display_only": True,
                "scoring_eligible": False,
                "risk_score_eligible": False,
            }
        ],
    }
    path = tmp_path / "digest.json"
    path.write_text(json.dumps(digest, ensure_ascii=False), encoding="utf-8")
    return path


def _make_baseline(tmp_path: Path) -> Path:
    path = tmp_path / "baseline.txt"
    path.write_text("baseline synthesis text", encoding="utf-8")
    return path


def test_cli_heuristic_writes_preview_under_tmp(tmp_path: Path, capsys):
    suffix = uuid.uuid4().hex[:8].translate(str.maketrans("0123456789", "abcdefghij"))
    stock = f"narrative_{suffix}"
    digest_path = _make_digest(tmp_path, stock_name=stock)
    baseline_path = _make_baseline(tmp_path)

    try:
        rc = main(
            [
                "--digest-json",
                str(digest_path),
                "--baseline-synthesis-file",
                str(baseline_path),
                "--stock",
                stock,
                "--composer",
                "heuristic",
            ]
        )
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert rc == 0, captured.err or captured.out
        assert payload["status"] == "ok"
        assert payload["wrote_repo_path"] is False
        assert Path(payload["json_output_path"]).exists()
        assert Path(payload["markdown_output_path"]).exists()
        assert str(payload["json_output_path"]).startswith(("/tmp/", "/private/tmp/"))
    finally:
        for path in (
            Path(f"/tmp/{stock}_viewpoint_narrative.json"),
            Path(f"/tmp/{stock}_viewpoint_narrative_preview.md"),
        ):
            if path.exists():
                path.unlink()


def test_cli_rejects_repo_output_path(tmp_path: Path, capsys):
    rc = main(
        [
            "--digest-json",
            str(_make_digest(tmp_path)),
            "--baseline-synthesis-file",
            str(_make_baseline(tmp_path)),
            "--stock",
            "测试股",
            "--composer",
            "heuristic",
            "--output",
            "reports/narrative.md",
        ]
    )
    assert rc == 1
    assert "must not resolve under the repository" in capsys.readouterr().err


def test_cli_llm_missing_key_errors(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    rc = main(
        [
            "--digest-json",
            str(_make_digest(tmp_path)),
            "--baseline-synthesis-file",
            str(_make_baseline(tmp_path)),
            "--stock",
            "测试股",
            "--composer",
            "llm",
        ]
    )
    assert rc == 1
    assert "API key" in capsys.readouterr().err


def test_cli_fake_llm_factory_success(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy")
    stock = f"narrative_llm_{uuid.uuid4().hex[:8]}"

    def _fake_factory(**kwargs):
        def _composer(_claims, _baseline, _stock):
            return {
                "paragraphs": [
                    {
                        "heading": "交付变量",
                        "text": "外部材料把800G交付传言作为待验证变量，提示交付弹性仍需观察。",
                        "claim_refs": ["c1"],
                    }
                ]
            }

        return _composer

    monkeypatch.setattr(_preview_module, "llm_narrative_composer_factory", _fake_factory)

    try:
        rc = main(
            [
                "--digest-json",
                str(_make_digest(tmp_path, stock_name=stock)),
                "--baseline-synthesis-file",
                str(_make_baseline(tmp_path)),
                "--stock",
                stock,
                "--composer",
                "llm",
                "--llm-model",
                "test-model",
                "--llm-base-url",
                "http://localhost",
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        markdown = Path(payload["markdown_output_path"]).read_text(encoding="utf-8")
        assert "交付变量" in markdown
        assert "[^1]" in markdown
    finally:
        for path in (
            Path(f"/tmp/{stock}_viewpoint_narrative.json"),
            Path(f"/tmp/{stock}_viewpoint_narrative_preview.md"),
        ):
            if path.exists():
                path.unlink()
