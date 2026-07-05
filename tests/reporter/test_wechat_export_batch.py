import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "utils"))

import wechat_export_batch
from wechat_exporter_client import DownloadedWechatArticle


def test_wechat_export_batch_downloads_url_list_and_writes_preview(tmp_path: Path, monkeypatch, capsys):
    url_list = tmp_path / "urls.txt"
    url_list.write_text("光芯片深度 | https://mp.weixin.qq.com/s/a\n", encoding="utf-8")
    output_dir = tmp_path / "exports"
    preview = tmp_path / "preview.md"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def download_article(self, url, fmt="markdown", timeout=20):
            return DownloadedWechatArticle(
                url=url,
                fmt=fmt,
                content="# 光芯片深度\n\nAI 算力带动 1.6T 光模块。",
                title="光芯片深度",
                metadata={"author": "半导体号", "publish_time": "2026-06-20"},
            )

    monkeypatch.setenv("WECHAT_EXPORTER_AUTH_KEY", "fake-key")
    monkeypatch.setattr(wechat_export_batch, "WechatExporterClient", FakeClient)

    exit_code = wechat_export_batch.main(
        [
            "--url-list",
            str(url_list),
            "--output-dir",
            str(output_dir),
            "--preview-output",
            str(preview),
            "--delay-seconds",
            "0",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["downloaded_count"] == 1
    assert payload["items_count"] == 1
    assert payload["wrote_knowledge"] is False
    assert payload["connected_synthesis"] is False
    saved = sorted(output_dir.glob("*.md"))
    assert len(saved) == 1
    assert "光芯片深度" in saved[0].read_text(encoding="utf-8")
    assert "# WeChat Export Preview" in preview.read_text(encoding="utf-8")


def test_wechat_export_batch_exports_dir_preview_without_auth(tmp_path: Path, capsys):
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir()
    (exports_dir / "local.md").write_text("本地微信导出：模拟芯片。", encoding="utf-8")
    preview = tmp_path / "preview.md"

    exit_code = wechat_export_batch.main(
        [
            "--exports-dir",
            str(exports_dir),
            "--preview-output",
            str(preview),
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["downloaded_count"] == 0
    assert payload["items_count"] == 1
    assert "模拟芯片" in preview.read_text(encoding="utf-8")


def test_wechat_export_batch_default_output_dir_is_outside_repo(tmp_path: Path):
    url_list = tmp_path / "urls.txt"
    url_list.write_text("a | https://mp.weixin.qq.com/s/a\n", encoding="utf-8")

    args = wechat_export_batch._parse_args(["--url-list", str(url_list)])
    output_dir = Path(args.output_dir).resolve()

    assert not output_dir.is_relative_to(REPO_ROOT)
    assert output_dir.is_relative_to(Path("/tmp").resolve())


def test_wechat_export_batch_limits_downloads_and_waits_between_items(tmp_path: Path, monkeypatch, capsys):
    url_list = tmp_path / "urls.txt"
    url_list.write_text(
        "\n".join(
            [
                "a | https://mp.weixin.qq.com/s/a",
                "b | https://mp.weixin.qq.com/s/b",
                "c | https://mp.weixin.qq.com/s/c",
            ]
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "exports"
    preview = tmp_path / "preview.md"
    downloaded = []
    sleeps = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def download_article(self, url, fmt="markdown", timeout=20):
            downloaded.append(url)
            return DownloadedWechatArticle(
                url=url,
                fmt=fmt,
                content=f"# {url}\n\n模拟芯片。",
                title=url.rsplit("/", 1)[-1],
                metadata={},
            )

    monkeypatch.setenv("WECHAT_EXPORTER_AUTH_KEY", "fake-key")
    monkeypatch.setattr(wechat_export_batch, "WechatExporterClient", FakeClient)
    monkeypatch.setattr(wechat_export_batch.time, "sleep", lambda seconds: sleeps.append(seconds))

    exit_code = wechat_export_batch.main(
        [
            "--url-list",
            str(url_list),
            "--output-dir",
            str(output_dir),
            "--preview-output",
            str(preview),
            "--max-downloads",
            "2",
            "--delay-seconds",
            "3",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert downloaded == ["https://mp.weixin.qq.com/s/a", "https://mp.weixin.qq.com/s/b"]
    assert sleeps == [3.0]
    assert payload["downloaded_count"] == 2
