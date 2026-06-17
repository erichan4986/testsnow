import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "smoke_cached_community_claims.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("smoke_cached_community_claims", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_cached_community_claims_dry_run_does_not_write(monkeypatch, tmp_path):
    module = _load_module()
    monkeypatch.setattr(module, "load_cached_posts", lambda *args, **kwargs: [{"content": "社区称C1236进入比亚迪供应链。"}])
    calls = []

    def fake_write(**kwargs):
        calls.append(kwargs)
        return {"status": "dry_run", "claim_count": 1, "path": str(tmp_path / "note.md")}

    monkeypatch.setattr(module, "write_cached_community_claim_note", fake_write)
    summary = module.run_smoke("黑芝麻智能", base_dir=str(tmp_path), write=False, date_str="20260614")
    assert summary["status"] == "dry_run"
    assert calls[0]["dry_run"] is True


def test_smoke_cached_community_claims_write_mode_passes_dry_run_false(monkeypatch, tmp_path):
    module = _load_module()
    monkeypatch.setattr(module, "load_cached_posts", lambda *args, **kwargs: [{"content": "社区称C1236进入比亚迪供应链。"}])

    def fake_write(**kwargs):
        assert kwargs["dry_run"] is False
        return {"status": "written", "claim_count": 1, "path": str(tmp_path / "note.md")}

    monkeypatch.setattr(module, "write_cached_community_claim_note", fake_write)
    summary = module.run_smoke("黑芝麻智能", base_dir=str(tmp_path), write=True, date_str="20260614")
    assert summary["status"] == "written"


def test_smoke_cached_community_claims_json_output(monkeypatch, capsys, tmp_path):
    module = _load_module()

    def fake_run_smoke(**kwargs):
        return {"stock_name": kwargs["stock_name"], "status": "dry_run", "claim_count": 2}

    monkeypatch.setattr(module, "run_smoke", fake_run_smoke)
    module.main(["--stock", "黑芝麻智能", "--json", "--base-dir", str(tmp_path)])
    data = json.loads(capsys.readouterr().out)
    assert data["stock_name"] == "黑芝麻智能"
    assert data["claim_count"] == 2


def test_load_cached_posts_uses_latest_matching_file(tmp_path):
    module = _load_module()
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    older = raw_dir / "xueqiu_data_20260601_黑芝麻智能.json"
    newer = raw_dir / "xueqiu_data_20260602_黑芝麻智能.json"
    older.write_text(json.dumps({"posts": [{"content": "old"}]}, ensure_ascii=False), encoding="utf-8")
    newer.write_text(json.dumps({"posts": [{"content": "new"}]}, ensure_ascii=False), encoding="utf-8")
    posts, path = module.load_cached_posts("黑芝麻智能", raw_dir=raw_dir)
    assert posts == [{"content": "new"}]
    assert path == newer


def test_load_markdown_posts_from_posts_dir(tmp_path):
    module = _load_module()
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()
    post = posts_dir / "123.md"
    post.write_text(
        """---
source_url: https://xueqiu.com/1/123
title: 中简科技26Q1
interactions:
  likes: 3
  comments: 2
  reposts: 1
---

# 中简科技26Q1

报告期内收入下降约50%-60%，研发费用同比增长约175%-185%。
""",
        encoding="utf-8",
    )
    posts, path = module.load_markdown_posts(posts_dir)
    assert path == posts_dir
    assert len(posts) == 1
    assert posts[0]["title"] == "中简科技26Q1"
    assert posts[0]["url"] == "https://xueqiu.com/1/123"
    assert posts[0]["like_count"] == 3
    assert "收入下降约50%-60%" in posts[0]["content"]


def test_run_smoke_prefers_posts_dir_when_provided(monkeypatch, tmp_path):
    module = _load_module()
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()
    monkeypatch.setattr(module, "load_markdown_posts", lambda path: ([{"content": "帖子称收入下降约50%-60%。"}], Path(path)))
    monkeypatch.setattr(module, "load_cached_posts", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("raw loader should not run")))

    def fake_write(**kwargs):
        assert kwargs["posts"] == [{"content": "帖子称收入下降约50%-60%。"}]
        return {"status": "dry_run", "claim_count": 1, "path": str(tmp_path / "note.md")}

    monkeypatch.setattr(module, "write_cached_community_claim_note", fake_write)
    summary = module.run_smoke("中简科技", base_dir=str(tmp_path), posts_dir=str(posts_dir), write=False)
    assert summary["post_count"] == 1
    assert summary["raw_path"] == str(posts_dir)


def test_run_smoke_falls_back_to_knowledge_posts_when_raw_empty(monkeypatch, tmp_path):
    module = _load_module()
    posts_dir = tmp_path / "knowledge" / "10-Stocks" / "中简科技" / "posts"
    posts_dir.mkdir(parents=True)
    monkeypatch.setattr(module, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(module, "load_cached_posts", lambda *args, **kwargs: ([], Path("")))
    monkeypatch.setattr(module, "load_markdown_posts", lambda path: ([{"content": "帖子称收入下降约50%-60%。"}], Path(path)))

    def fake_write(**kwargs):
        assert kwargs["posts"] == [{"content": "帖子称收入下降约50%-60%。"}]
        return {"status": "dry_run", "claim_count": 1, "path": str(tmp_path / "note.md")}

    monkeypatch.setattr(module, "write_cached_community_claim_note", fake_write)
    summary = module.run_smoke("中简科技", base_dir=str(tmp_path / "knowledge"), write=False)

    assert summary["status"] == "dry_run"
    assert summary["post_count"] == 1
    assert summary["raw_path"] == str(posts_dir)
