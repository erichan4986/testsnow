import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

import pytest

# Import CLI module to test main() directly.
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
import wechat_targeted_discovery_preview as cli


@pytest.fixture
def tmp_env_with_key(tmp_path):
    env = tmp_path / ".env"
    env.write_text("WECHAT_EXPORTER_AUTH_KEY=fake-key\n", encoding="utf-8")
    return env


@pytest.fixture
def tmp_stocks_config(tmp_path):
    cfg = [{"name": "圣邦股份", "code": "300661", "industry": "半导体"}]
    path = tmp_path / "stocks.json"
    path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    return path


class FakeClient:
    def __init__(self, articles=None):
        self.articles = articles or []
        self.download_calls = []

    def search_accounts(self, keyword):
        # Return a fake account for every keyword.
        return {
            "list": [
                {"fakeid": f"fakeid-{keyword}", "nickname": f"账号-{keyword}"}
            ]
        }

    def list_articles(self, fakeid, keyword="", page=1):
        # Return all fake articles regardless of fakeid; real code filters by keyword/date.
        return {"articles": self.articles}

    def download_article(self, url, fmt="markdown"):
        self.download_calls.append(url)
        fake = type("Article", (), {"title": "T", "content": "# body"})()
        return fake


def fake_discovery(*args, **kwargs):
    ts = 1767225600  # 2026-01-01 00:00:00 UTC-ish
    return [
        {
            "title": "深度研报标题",
            "url": "https://mp.weixin.qq.com/s/a",
            "digest": "深度解析",
            "publish_time_ts": ts,
            "account": "半导体行业观察",
            "author_name": "",
        },
        {
            "title": "校园招聘启动",
            "url": "https://mp.weixin.qq.com/s/b",
            "digest": "招聘",
            "publish_time_ts": ts,
            "account": "官方号",
            "author_name": "",
        },
        {
            "title": "新品发布",
            "url": "https://mp.weixin.qq.com/s/c",
            "digest": "新品",
            "publish_time_ts": ts,
            "account": "产品号",
            "author_name": "",
        },
    ]


def test_cli_help_includes_key_args(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--stock" in out
    assert "--keyword" in out
    assert "--download-top" in out
    assert "--since-date" in out


def test_cli_runs_with_fake_client_and_writes_outputs(tmp_path, monkeypatch, tmp_env_with_key, tmp_stocks_config):
    out_md = tmp_path / "out.md"
    out_jsonl = tmp_path / "out.jsonl"
    monkeypatch.setattr(cli, "load_auth_key", lambda path=None: "fake-key")
    monkeypatch.setattr(cli, "discover_articles", fake_discovery)
    monkeypatch.setattr(cli, "download_articles", lambda *a, **k: [])

    code = cli.main([
        "--stock", "圣邦股份",
        "--config", str(tmp_stocks_config),
        "--output", str(out_md),
        "--jsonl-output", str(out_jsonl),
        "--since-date", "2025-12-28",
        "--download-top", "0",
        "--base-url", "https://example.com",
        "--auth-key", "fake-key",
    ])
    assert code == 0
    assert out_md.exists()
    assert out_jsonl.exists()
    lines = out_jsonl.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 2
    data = [json.loads(line) for line in lines]
    classifications = {d["classification"] for d in data}
    assert "high_quality_analysis" in classifications
    assert "product_or_event_signal" in classifications
    # drop should not be in JSONL main output by default
    assert "drop" not in classifications
    # All isolation flags false
    for d in data:
        assert d["knowledge_eligible"] is False
        assert d["synthesis_eligible"] is False
        assert d["scoring_eligible"] is False
        assert d["risk_score_eligible"] is False
    md = out_md.read_text(encoding="utf-8")
    assert "Preview-only" in md
    assert "WECHAT_EXPORTER_AUTH_KEY" not in md
    assert "fake-key" not in md


def test_cli_download_top_zero_does_not_call_download(tmp_path, monkeypatch, tmp_env_with_key, tmp_stocks_config):
    out_md = tmp_path / "out.md"
    out_jsonl = tmp_path / "out.jsonl"
    fake_client = FakeClient()
    monkeypatch.setattr(cli, "load_auth_key", lambda path=None: "fake-key")
    monkeypatch.setattr(cli, "WechatExporterClient", lambda **kw: fake_client)
    monkeypatch.setattr(cli, "discover_articles", fake_discovery)

    cli.main([
        "--stock", "圣邦股份",
        "--config", str(tmp_stocks_config),
        "--output", str(out_md),
        "--jsonl-output", str(out_jsonl),
        "--since-date", "2025-12-28",
        "--download-top", "0",
        "--auth-key", "fake-key",
    ])
    assert fake_client.download_calls == []


def test_cli_download_top_positive_downloads_best_candidates(tmp_path, monkeypatch, tmp_env_with_key, tmp_stocks_config):
    out_md = tmp_path / "out.md"
    out_jsonl = tmp_path / "out.jsonl"
    download_dir = tmp_path / "exports"
    fake_client = FakeClient()
    monkeypatch.setattr(cli, "load_auth_key", lambda path=None: "fake-key")
    monkeypatch.setattr(cli, "WechatExporterClient", lambda **kw: fake_client)
    monkeypatch.setattr(cli, "discover_articles", fake_discovery)

    cli.main([
        "--stock", "圣邦股份",
        "--config", str(tmp_stocks_config),
        "--output", str(out_md),
        "--jsonl-output", str(out_jsonl),
        "--download-dir", str(download_dir),
        "--since-date", "2025-12-28",
        "--download-top", "2",
        "--auth-key", "fake-key",
        "--download-delay-seconds", "0",
    ])
    # Should download high_quality_analysis and product_or_event_signal, not the drop.
    assert len(fake_client.download_calls) == 2
    assert download_dir.exists()
    assert len(list(download_dir.glob("*.md"))) == 2


def test_cli_uses_env_auth_when_auth_key_missing(tmp_path, monkeypatch, tmp_stocks_config):
    env = tmp_path / ".env"
    env.write_text("WECHAT_EXPORTER_AUTH_KEY=env-secret\n", encoding="utf-8")
    monkeypatch.setattr(cli, "ENV_PATH", env)
    captured = {}

    def fake_client_constructor(*, auth_key, **kw):
        captured["auth_key"] = auth_key
        return FakeClient()

    monkeypatch.setattr(cli, "WechatExporterClient", fake_client_constructor)
    monkeypatch.setattr(cli, "discover_articles", lambda *a, **k: [])

    cli.main([
        "--stock", "圣邦股份",
        "--config", str(tmp_stocks_config),
        "--since-date", "2025-12-28",
    ])
    assert captured["auth_key"] == "env-secret"


def test_cli_auth_key_never_printed_in_stdout(capsys, tmp_path, monkeypatch, tmp_stocks_config):
    monkeypatch.setattr(cli, "load_auth_key", lambda path=None: "super-secret-key")
    monkeypatch.setattr(cli, "discover_articles", fake_discovery)
    monkeypatch.setattr(cli, "download_articles", lambda *a, **k: [])

    cli.main([
        "--stock", "圣邦股份",
        "--config", str(tmp_stocks_config),
        "--output", str(tmp_path / "out.md"),
        "--jsonl-output", str(tmp_path / "out.jsonl"),
        "--since-date", "2025-12-28",
    ])
    out = capsys.readouterr().out
    assert "super-secret-key" not in out
