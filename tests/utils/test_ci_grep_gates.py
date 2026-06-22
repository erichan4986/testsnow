from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_SCRIPT = REPO_ROOT / "tools" / "ci_grep_gates.sh"


def _copy_gate_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "tools").mkdir(parents=True)
    shutil.copy2(GATE_SCRIPT, root / "tools" / "ci_grep_gates.sh")
    return root


def _run_gate(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(GATE_SCRIPT), str(root)],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def test_ci_grep_gates_passes_real_repository() -> None:
    result = _run_gate(REPO_ROOT)

    assert result.returncode == 0, result.stdout


def test_ci_grep_gates_rejects_fulltext_leakage_in_scoring_file(tmp_path: Path) -> None:
    root = _copy_gate_fixture(tmp_path)
    target = root / "scripts" / "utils" / "reporter" / "scoring_engine.py"
    target.parent.mkdir(parents=True)
    target.write_text('value = ctx.get("periodic_report_fulltext_items")\n', encoding="utf-8")

    result = _run_gate(root)

    assert result.returncode != 0
    assert "periodic_report_fulltext" in result.stdout


def test_ci_grep_gates_allows_display_renderer_synthesis_display(tmp_path: Path) -> None:
    root = _copy_gate_fixture(tmp_path)
    target = root / "scripts" / "utils" / "reporter" / "sections" / "deep_analysis_renderer.py"
    target.parent.mkdir(parents=True)
    target.write_text('synthesis = ctx.get("synthesis_display") or ctx.get("synthesis")\n', encoding="utf-8")

    result = _run_gate(root)

    assert result.returncode == 0, result.stdout


def test_ci_grep_gates_rejects_fulltext_leakage_in_filing_fact_writer(tmp_path: Path) -> None:
    root = _copy_gate_fixture(tmp_path)
    target = root / "scripts" / "utils" / "periodic_report_filing_fact_note_writer.py"
    target.parent.mkdir(parents=True)
    target.write_text('value = ctx.get("periodic_report_fulltext_items")\n', encoding="utf-8")

    result = _run_gate(root)

    assert result.returncode != 0
    assert "periodic_report_fulltext" in result.stdout


def test_ci_grep_gates_rejects_fulltext_leakage_in_narrative_evidence_cards(tmp_path: Path) -> None:
    root = _copy_gate_fixture(tmp_path)
    target = root / "scripts" / "utils" / "periodic_report_narrative_evidence_cards.py"
    target.parent.mkdir(parents=True)
    target.write_text('value = ctx.get("periodic_report_fulltext_items")\n', encoding="utf-8")

    result = _run_gate(root)

    assert result.returncode != 0
    assert "periodic_report_fulltext" in result.stdout


def test_ci_grep_gates_rejects_fulltext_leakage_in_narrative_card_writer(tmp_path: Path) -> None:
    root = _copy_gate_fixture(tmp_path)
    target = root / "scripts" / "utils" / "periodic_report_narrative_card_note_writer.py"
    target.parent.mkdir(parents=True)
    target.write_text('value = ctx.get("periodic_report_fulltext_items")\n', encoding="utf-8")

    result = _run_gate(root)

    assert result.returncode != 0
    assert "periodic_report_fulltext" in result.stdout


def test_ci_grep_gates_rejects_narrative_card_leakage_in_scoring_file(tmp_path: Path) -> None:
    root = _copy_gate_fixture(tmp_path)
    target = root / "scripts" / "utils" / "reporter" / "scoring_engine.py"
    target.parent.mkdir(parents=True)
    target.write_text('source_type = "periodic_report_narrative_evidence"\n', encoding="utf-8")

    result = _run_gate(root)

    assert result.returncode != 0
    assert "periodic_report_narrative_evidence" in result.stdout


def test_ci_grep_gates_rejects_requests_get_without_timeout(tmp_path: Path) -> None:
    root = _copy_gate_fixture(tmp_path)
    target = root / "scripts" / "utils" / "bad_fetcher.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "import requests\n\n"
        "def fetch(url):\n"
        "    return requests.get(\n"
        "        url,\n"
        "        headers={'User-Agent': 'test'},\n"
        "    )\n",
        encoding="utf-8",
    )

    result = _run_gate(root)

    assert result.returncode != 0
    assert "requests.get" in result.stdout
    assert "timeout" in result.stdout


def test_ci_grep_gates_rejects_unsafe_yaml_load(tmp_path: Path) -> None:
    root = _copy_gate_fixture(tmp_path)
    target = root / "scripts" / "utils" / "bad_yaml.py"
    target.parent.mkdir(parents=True)
    target.write_text("import yaml\n\nvalue = yaml.load(raw)\n", encoding="utf-8")

    result = _run_gate(root)

    assert result.returncode != 0
    assert "yaml.load" in result.stdout


def test_ci_grep_gates_rejects_obvious_secret_literal(tmp_path: Path) -> None:
    root = _copy_gate_fixture(tmp_path)
    target = root / "scripts" / "utils" / "bad_secret.py"
    target.parent.mkdir(parents=True)
    target.write_text('api_key = "sk-test-secret-1234567890"\n', encoding="utf-8")

    result = _run_gate(root)

    assert result.returncode != 0
    assert "secret" in result.stdout.lower()
