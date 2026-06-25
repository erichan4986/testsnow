import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "wechat_candidate_selector_preview.py"


def test_wechat_candidate_selector_preview_cli_writes_markdown(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.txt"
    candidates.write_text(
        "\n".join(
            [
                "2026-05-23 | 半导体行业观察 | AI的火烧到了模拟芯片 | https://mp.weixin.qq.com/s/a | AI数据中心拉动电源和高速信号链。",
                "2026-06-22 | 圣邦微电子 | 上海展会邀请函 | https://mp.weixin.qq.com/s/b | 邀您共赴展会。",
                "2026-06-09 | 电子工程专辑 | 圣邦微电子推出车规级电子保险丝控制器SGM42148Q | https://mp.weixin.qq.com/s/c | 车规级电源保护产品。",
            ]
        ),
        encoding="utf-8",
    )
    config = tmp_path / "stocks.json"
    config.write_text(
        json.dumps(
            [
                {
                    "name": "圣邦股份",
                    "code": "300661",
                    "source_intake": {
                        "a_stock": {
                            "iwencai_industry_research": {
                                "queries": ["模拟芯片 行业研究报告", "车规芯片 产业链 深度报告"]
                            }
                        }
                    },
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "preview.md"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--candidate-file",
            str(candidates),
            "--stock",
            "圣邦股份",
            "--config",
            str(config),
            "--theme-term",
            "AI 电源",
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["counts"] == {"keep": 1, "drop": 1, "product_signal": 1}
    assert payload["wrote_knowledge"] is False
    assert payload["connected_synthesis"] is False
    markdown = output.read_text(encoding="utf-8")
    assert "# WeChat Candidate Selector Preview" in markdown
    assert "AI的火烧到了模拟芯片" in markdown
    assert "上海展会邀请函" in markdown
    assert "product_signal" in markdown


def test_wechat_candidate_selector_preview_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--candidate-file" in result.stdout
    assert "--theme-term" in result.stdout
