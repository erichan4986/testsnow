import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "curated_external_section_preview.py"


def test_curated_external_section_preview_help_runs():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--candidate-jsonl" in result.stdout
    assert "--output" in result.stdout


def test_curated_external_section_preview_renders_safe_candidate_jsonl(tmp_path):
    candidate_jsonl = tmp_path / "candidates.jsonl"
    output = tmp_path / "section.md"
    items = [
        {
            "source_kind": "wechat_customer_order_or_design_win",
            "source_type": "wechat_customer_order_or_design_win",
            "wechat_signal_category": "customer_order_or_design_win",
            "title": "黑芝麻智能华山A2000拿下首个量产项目定点",
            "content": "客户定点和量产节奏仍需后续验证。",
            "account": "高工智能汽车",
            "publish_time": "2026-02-24",
            "quality_action": "preview_only",
            "knowledge_eligible": False,
            "synthesis_eligible": False,
            "scoring_eligible": False,
            "risk_score_eligible": False,
        },
        {
            "source_kind": "wechat_product_signal",
            "source_type": "wechat_product_signal",
            "wechat_signal_category": "product_or_event_signal",
            "title": "产品方案精选",
            "quality_action": "preview_only",
            "knowledge_eligible": False,
            "synthesis_eligible": False,
            "scoring_eligible": False,
            "risk_score_eligible": False,
        },
        {
            "source_kind": "wechat_product_signal",
            "title": "不安全材料",
            "quality_action": "preview_only",
            "knowledge_eligible": True,
        },
    ]
    candidate_jsonl.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in items) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--candidate-jsonl",
            str(candidate_jsonl),
            "--output",
            str(output),
            "--stock",
            "黑芝麻智能",
            "--max-display-items",
            "1",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["items_count"] == 3
    assert payload["rendered"] is True
    assert payload["wrote_knowledge"] is False
    assert payload["connected_synthesis"] is False

    markdown = output.read_text(encoding="utf-8")
    assert "## 精选外部观察（Preview）" in markdown
    assert "### 微信精选观察" in markdown
    assert "#### 商业化事件" in markdown
    assert "黑芝麻智能华山A2000拿下首个量产项目定点" in markdown
    assert "产品方案精选" in markdown
    assert "不安全材料" not in markdown
