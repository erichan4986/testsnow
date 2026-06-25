import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

import pytest

from wechat_exporter_client import WechatExporterClient, WechatExporterError


class FakeResponse:
    def __init__(self, body: str, status: int = 200, content_type: str = "text/plain"):
        self.body = body.encode("utf-8")
        self.status = status
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


def test_download_article_sends_auth_header_and_parses_json_envelope():
    captured = {}

    def opener(request, timeout=20):
        captured["url"] = request.full_url
        captured["auth"] = request.headers.get("X-auth-key") or request.headers.get("X-Auth-Key")
        return FakeResponse(
            json.dumps(
                {
                    "code": 0,
                    "data": {
                        "title": "模拟芯片深度",
                        "content": "# 正文\n\n圣邦股份 模拟芯片。",
                        "author": "半导体号",
                        "url": "https://mp.weixin.qq.com/s/abc",
                    },
                },
                ensure_ascii=False,
            ),
            content_type="application/json",
        )

    client = WechatExporterClient(
        base_url="https://down.mptext.top/",
        auth_key="secret-key",
        opener=opener,
    )

    article = client.download_article("https://mp.weixin.qq.com/s/abc", fmt="markdown")

    assert captured["auth"] == "secret-key"
    assert captured["url"].startswith("https://down.mptext.top/api/public/v1/download?")
    assert "format=markdown" in captured["url"]
    assert article.title == "模拟芯片深度"
    assert article.content == "# 正文\n\n圣邦股份 模拟芯片。"
    assert article.metadata["author"] == "半导体号"


def test_download_article_raises_sanitized_error_without_auth_key():
    def opener(request, timeout=20):
        raise OSError("network failed with secret-key")

    client = WechatExporterClient(
        base_url="https://down.mptext.top",
        auth_key="secret-key",
        opener=opener,
    )

    with pytest.raises(WechatExporterError) as exc:
        client.download_article("https://mp.weixin.qq.com/s/abc")

    assert "secret-key" not in str(exc.value)
    assert "network failed" in str(exc.value)


def test_client_requires_auth_key_for_download():
    client = WechatExporterClient(base_url="https://down.mptext.top", auth_key="")

    with pytest.raises(WechatExporterError) as exc:
        client.download_article("https://mp.weixin.qq.com/s/abc")

    assert "WECHAT_EXPORTER_AUTH_KEY" in str(exc.value)
