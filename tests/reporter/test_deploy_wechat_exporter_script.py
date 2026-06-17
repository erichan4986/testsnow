"""Static safety checks for the WeChat exporter deploy helper."""

from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "deploy_wechat_exporter.sh"


def _script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_wechat_exporter_uses_current_official_repository():
    text = _script_text()
    assert "wechat-article/wechat-article-exporter" in text
    assert "jooooock/wechat-article-exporter" not in text


def test_wechat_exporter_defaults_to_docker_image():
    text = _script_text()
    assert "MODE=\"docker\"" in text
    assert "ghcr.io/wechat-article/wechat-article-exporter:latest" in text


def test_wechat_exporter_dev_mode_requires_node_22():
    text = _script_text()
    assert "Node.js 22+" in text
    assert "NODE_MAJOR" in text
    assert "-lt 22" in text


def test_wechat_exporter_no_start_and_reclone_are_explicit_flags():
    text = _script_text()
    assert "--no-start" in text
    assert "--reclone" in text
    assert "NO_START=1" in text
    assert "RECLONE=1" in text


def test_wechat_exporter_does_not_prompt_delete_existing_directory_by_default():
    text = _script_text()
    assert "read -p \"  是否删除并重新克隆?" not in text
    assert "rm -rf \"$PROJECT_DIR\"" in text
    assert "RECLONE" in text
