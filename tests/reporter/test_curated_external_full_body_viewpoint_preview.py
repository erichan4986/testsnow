from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import curated_external_full_body_viewpoint_preview as _preview_module
from curated_external_full_body_viewpoint_preview import main


def _make_source_jsonl(tmp_path: Path) -> Path:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))
    from curated_external_full_body_viewpoint_claims import normalized_hash

    source_ref = "https://mp.weixin.qq.com/s/cli-example"
    content = "外部产业分析认为公司核心机制正从光模块速率转向硅光平台集成，这一变量仍需客户验证。"
    item = {
        "title": "CLI 测试外部文章",
        "account": "测试账号",
        "publish_time": "2026-04-01",
        "source_kind": "wechat_high_quality_analysis",
        "source_ref": source_ref,
        "content": content,
        "quality_action": "preview_only",
        "knowledge_eligible": False,
        "scoring_eligible": False,
        "risk_score_eligible": False,
        "synthesis_eligible": True,
        "synthesis_display_only": True,
    }

    path = tmp_path / "sources.jsonl"
    path.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
    return path


def _make_baseline(tmp_path: Path) -> Path:
    path = tmp_path / "baseline.txt"
    path.write_text("baseline text without overlapping facts", encoding="utf-8")
    return path


class TestCLIPreview:
    def test_cli_default_outputs_under_tmp(self, tmp_path: Path, capsys):
        source_path = _make_source_jsonl(tmp_path)
        baseline_path = _make_baseline(tmp_path)
        stock = f"cli_tmp_{uuid.uuid4().hex[:8]}"

        try:
            rc = main(
                [
                    "--source-jsonl",
                    str(source_path),
                    "--baseline-synthesis-file",
                    str(baseline_path),
                    "--stock",
                    stock,
                    "--extractor",
                    "heuristic",
                    "--min-display-claims",
                    "1",
                ]
            )
            captured = capsys.readouterr()
            payload = json.loads(captured.out)
            assert rc == 0
            assert payload["status"] == "ok"
            assert payload["wrote_repo_path"] is False
            assert payload["json_output_path"].startswith("/tmp/") or payload[
                "json_output_path"
            ].startswith("/private/tmp/")
            assert payload["markdown_output_path"].startswith("/tmp/") or payload[
                "markdown_output_path"
            ].startswith("/private/tmp/")
            assert Path(payload["json_output_path"]).exists()
            assert Path(payload["markdown_output_path"]).exists()
        finally:
            json_path = Path(f"/tmp/{stock}_full_body_viewpoint_claims.json")
            md_path = Path(f"/tmp/{stock}_full_body_viewpoint_digest_preview.md")
            if json_path.exists():
                json_path.unlink()
            if md_path.exists():
                md_path.unlink()

    def test_cli_rejects_rendered_markdown_baseline(self, tmp_path: Path, capsys):
        source_path = _make_source_jsonl(tmp_path)
        baseline_path = tmp_path / "baseline.md"
        baseline_path.write_text(
            "# Report\n\n## 四、深度分析\n\n### 4.1 ...\n",
            encoding="utf-8",
        )
        rc = main(
            [
                "--source-jsonl",
                str(source_path),
                "--baseline-synthesis-file",
                str(baseline_path),
                "--stock",
                "baseline_reject",
                "--extractor",
                "heuristic",
            ]
        )
        captured = capsys.readouterr()
        assert rc == 1
        assert "rendered report" in captured.err

    def test_cli_refuses_repo_output_path(self, tmp_path: Path, capsys):
        source_path = _make_source_jsonl(tmp_path)
        baseline_path = _make_baseline(tmp_path)
        rc = main(
            [
                "--source-jsonl",
                str(source_path),
                "--baseline-synthesis-file",
                str(baseline_path),
                "--stock",
                "repo_path_test",
                "--output",
                "reports/repo_path_test_preview.md",
                "--extractor",
                "heuristic",
                "--min-display-claims",
                "1",
            ]
        )
        captured = capsys.readouterr()
        assert rc == 1
        assert "must not resolve under the repository" in captured.err

    def test_cli_llm_missing_key_errors(self, tmp_path: Path, capsys, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
        source_path = _make_source_jsonl(tmp_path)
        baseline_path = _make_baseline(tmp_path)

        rc = _preview_module.main(
            [
                "--source-jsonl",
                str(source_path),
                "--baseline-synthesis-file",
                str(baseline_path),
                "--stock",
                "llm_missing_key",
                "--extractor",
                "llm",
            ]
        )
        captured = capsys.readouterr()
        assert rc == 1
        assert "API key" in captured.err

    def test_cli_llm_fake_factory_success(self, tmp_path: Path, capsys, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key-for-testing")
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))
        from curated_external_full_body_viewpoint_claims import normalized_hash

        source_path = _make_source_jsonl(tmp_path)
        baseline_path = _make_baseline(tmp_path)
        stock = f"cli_llm_{uuid.uuid4().hex[:8]}"
        json_path = Path(f"/tmp/{stock}_full_body_viewpoint_claims.json")
        md_path = Path(f"/tmp/{stock}_full_body_viewpoint_digest_preview.md")

        content = "外部产业分析认为公司核心机制正从光模块速率转向硅光平台集成，这一变量仍需客户验证。"
        source_ref = "https://mp.weixin.qq.com/s/cli-example"

        def _fake_extractor(sources, baseline_text, fingerprint):
            return [
                {
                    "schema_version": "curated_external_viewpoint_claim.v1",
                    "claim_type": "novel_mechanism",
                    "topic": "commercialization",
                    "claim": "外部产业分析认为公司核心机制正从光模块速率转向硅光平台集成。",
                    "source_quote": content,
                    "source_quote_hash": normalized_hash(content),
                    "why_incremental": "baseline未讨论。",
                    "baseline_overlap": "none",
                    "source_ref": source_ref,
                    "evidence_refs": [source_ref],
                    "quality_action": "preview_only",
                    "knowledge_eligible": False,
                    "synthesis_display_only": True,
                    "scoring_eligible": False,
                    "risk_score_eligible": False,
                }
            ]

        def _fake_factory(**kwargs):
            return _fake_extractor

        monkeypatch.setattr(_preview_module, "llm_extractor_factory", _fake_factory)

        try:
            rc = _preview_module.main(
                [
                    "--source-jsonl",
                    str(source_path),
                    "--baseline-synthesis-file",
                    str(baseline_path),
                    "--stock",
                    stock,
                    "--extractor",
                    "llm",
                    "--llm-model",
                    "test-model",
                    "--llm-base-url",
                    "http://localhost",
                    "--min-display-claims",
                    "1",
                ]
            )
            captured = capsys.readouterr()
            assert rc == 0
            payload = json.loads(captured.out)
            assert payload["status"] == "ok"
            assert payload["claims_count"] == 1
            assert md_path.exists()
            markdown = md_path.read_text(encoding="utf-8")
            assert "[^1]" in markdown
        finally:
            if json_path.exists():
                json_path.unlink()
            if md_path.exists():
                md_path.unlink()

    def test_cli_llm_multipass_fake_factory_success(self, tmp_path: Path, capsys, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key-for-testing")
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))
        from curated_external_full_body_viewpoint_claims import normalized_hash

        source_path = _make_source_jsonl(tmp_path)
        baseline_path = _make_baseline(tmp_path)
        stock = f"cli_multipass_{uuid.uuid4().hex[:8]}"
        json_path = Path(f"/tmp/{stock}_full_body_viewpoint_claims.json")
        md_path = Path(f"/tmp/{stock}_full_body_viewpoint_digest_preview.md")

        content = "外部产业分析认为公司核心机制正从光模块速率转向硅光平台集成，这一变量仍需客户验证。"
        source_ref = "https://mp.weixin.qq.com/s/cli-example"

        def _fake_extractor(sources, baseline_text, fingerprint):
            return [
                {
                    "schema_version": "curated_external_viewpoint_claim.v1",
                    "claim_type": "novel_mechanism",
                    "topic": "technology_path",
                    "claim": "外部产业分析认为公司核心机制正从光模块速率转向硅光平台集成。",
                    "source_quote": content,
                    "source_quote_hash": normalized_hash(content),
                    "why_incremental": "baseline未讨论。",
                    "baseline_overlap": "none",
                    "source_ref": source_ref,
                    "evidence_refs": [source_ref],
                    "quality_action": "preview_only",
                    "knowledge_eligible": False,
                    "synthesis_display_only": True,
                    "scoring_eligible": False,
                    "risk_score_eligible": False,
                }
            ]

        def _fake_factory(**kwargs):
            return _fake_extractor

        monkeypatch.setattr(_preview_module, "multipass_llm_extractor_factory", _fake_factory)

        try:
            rc = _preview_module.main(
                [
                    "--source-jsonl",
                    str(source_path),
                    "--baseline-synthesis-file",
                    str(baseline_path),
                    "--stock",
                    stock,
                    "--extractor",
                    "llm-multipass",
                    "--llm-model",
                    "test-model",
                    "--llm-base-url",
                    "http://localhost",
                    "--min-display-claims",
                    "1",
                ]
            )
            captured = capsys.readouterr()
            assert rc == 0
            payload = json.loads(captured.out)
            assert payload["status"] == "ok"
            assert payload["claims_count"] == 1
            assert md_path.exists()
            markdown = md_path.read_text(encoding="utf-8")
            assert "[^1]" in markdown
        finally:
            if json_path.exists():
                json_path.unlink()
            if md_path.exists():
                md_path.unlink()

    def test_cli_min_display_claims_default_report_safe(self, tmp_path: Path, capsys):
        source_path = _make_source_jsonl(tmp_path)
        baseline_path = _make_baseline(tmp_path)
        stock = f"cli_min_{uuid.uuid4().hex[:8]}"
        json_path = Path(f"/tmp/{stock}_full_body_viewpoint_claims.json")
        md_path = Path(f"/tmp/{stock}_full_body_viewpoint_digest_preview.md")

        try:
            rc = main(
                [
                    "--source-jsonl",
                    str(source_path),
                    "--baseline-synthesis-file",
                    str(baseline_path),
                    "--stock",
                    stock,
                    "--extractor",
                    "heuristic",
                ]
            )
            captured = capsys.readouterr()
            payload = json.loads(captured.out)
            assert rc == 1
            assert payload["status"] == "no_incremental_claims"
            assert payload["claims_count"] == 1
            assert payload["stats"]["display_claims"] == 1
            assert payload["stats"]["drop_reasons"] == ["valid claims 1 < min 2"]
            assert payload["min_display_claims"] == 2
            assert md_path.exists()
            assert md_path.read_text(encoding="utf-8") == ""
        finally:
            if json_path.exists():
                json_path.unlink()
            if md_path.exists():
                md_path.unlink()

    def test_cli_help_includes_max_api_retries(self, capsys):
        with pytest.raises(SystemExit):
            main(["--help"])
        captured = capsys.readouterr()
        assert "--max-api-retries" in captured.out

    def test_cli_help_includes_theme_profile_args(self, capsys):
        with pytest.raises(SystemExit):
            main(["--help"])
        captured = capsys.readouterr()
        assert "--theme-profile" in captured.out
        assert "--min-theme-coverage" in captured.out

    def test_cli_theme_coverage_failure(self, tmp_path: Path, capsys, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key-for-testing")
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))
        from curated_external_full_body_viewpoint_claims import normalized_hash

        source_path = _make_source_jsonl(tmp_path)
        baseline_path = _make_baseline(tmp_path)
        stock = f"cli_theme_{uuid.uuid4().hex[:8]}"

        def _fake_extractor(sources, baseline_text, fingerprint):
            return [
                {
                    "schema_version": "curated_external_viewpoint_claim.v1",
                    "claim_type": "context_extension",
                    "topic": "general",
                    "claim": "外部文章提示一般性观察。",
                    "source_quote": sources[0]["content"],
                    "source_quote_hash": normalized_hash(sources[0]["content"]),
                    "why_incremental": "baseline未涉及。",
                    "baseline_overlap": "none",
                    "source_id": sources[0]["source_id"],
                    "evidence_refs": [sources[0]["source_id"]],
                    "quality_action": "preview_only",
                    "knowledge_eligible": False,
                    "synthesis_display_only": True,
                    "scoring_eligible": False,
                    "risk_score_eligible": False,
                }
            ]

        def _fake_factory(**kwargs):
            return _fake_extractor

        monkeypatch.setattr(_preview_module, "llm_extractor_factory", _fake_factory)

        try:
            rc = _preview_module.main(
                [
                    "--source-jsonl",
                    str(source_path),
                    "--baseline-synthesis-file",
                    str(baseline_path),
                    "--stock",
                    stock,
                    "--extractor",
                    "llm",
                    "--llm-model",
                    "test-model",
                    "--llm-base-url",
                    "http://localhost",
                    "--min-display-claims",
                    "1",
                    "--theme-profile",
                    "zhongji_ai_optics",
                    "--min-theme-coverage",
                    "0.9",
                ]
            )
            captured = capsys.readouterr()
            assert rc == 1
            payload = json.loads(captured.out)
            assert payload["status"] == "theme_coverage_failed"
            assert payload["stats"]["theme_coverage_ratio"] < 0.9
            assert len(payload["stats"]["missing_themes"]) > 0
        finally:
            json_path = Path(f"/tmp/{stock}_full_body_viewpoint_claims.json")
            md_path = Path(f"/tmp/{stock}_full_body_viewpoint_digest_preview.md")
            if json_path.exists():
                json_path.unlink()
            if md_path.exists():
                md_path.unlink()
