import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock


def _load_entry_module():
    script_path = Path(__file__).parent.parent.parent / "scripts" / "run_黑芝麻智能.py"
    spec = importlib.util.spec_from_file_location("run_black_sesame_entry", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_black_sesame_entry_passes_agent_reach_config(monkeypatch, tmp_path):
    module = _load_entry_module()

    monkeypatch.setattr(module, "_load_xueqiu_data", lambda stock_name, date_str: [
        {
            "title": "黑芝麻智能量产进展",
            "content": "黑芝麻智能华山芯片量产",
            "like": 10,
            "comment": 5,
        }
    ])

    zhihu_collector = MagicMock()
    zhihu_collector.collect.return_value = {
        "report_items": [],
        "knowledge_items": [],
        "gate_stats": {},
        "total": 0,
    }
    monkeypatch.setattr(module, "ZhihuCollector", MagicMock(return_value=zhihu_collector))

    reporter_instance = MagicMock()
    reporter_instance.generate_stock_report.return_value = ("", "")
    reporter_cls = MagicMock(return_value=reporter_instance)
    monkeypatch.setattr(module, "PerStockReporter", reporter_cls)

    monkeypatch.setattr(module, "export_pdf", MagicMock())

    module.main()

    kwargs = reporter_cls.call_args.kwargs
    assert kwargs["agent_reach_configs"] == {
        "黑芝麻智能": {
            "enabled": True,
            "web_urls": [
                "https://www.blacksesame.com/zh/list_10/972.html",
                "https://www.blacksesame.com/zh/list_9/977.html",
                "https://www.blacksesame.com/zh/list_9/966.html",
                "https://www.blacksesame.com/zh/list_9/964.html",
                "https://www.blacksesame.com/zh/list_9/961.html",
                "https://www.blacksesame.com/zh/list_10/912.html",
            ],
            "official_domains": ["blacksesame.com"],
        }
    }


def test_fast_test_mode_skips_zhihu_collector(monkeypatch, tmp_path):
    module = _load_entry_module()

    fake_script = tmp_path / "scripts" / "run_黑芝麻智能.py"
    fake_script.parent.mkdir(parents=True)
    monkeypatch.setattr(module, "__file__", str(fake_script))

    monkeypatch.setattr(module, "_load_xueqiu_data", lambda stock_name, date_str: [
        {
            "title": "黑芝麻智能量产进展",
            "content": "黑芝麻智能华山芯片量产",
            "like": 10,
            "comment": 5,
        }
    ])

    zhihu_collector_cls = MagicMock(side_effect=AssertionError("ZhihuCollector should not run"))
    monkeypatch.setattr(module, "ZhihuCollector", zhihu_collector_cls)

    reporter_instance = MagicMock()
    reporter_instance.generate_stock_report.return_value = ("", "")
    reporter_cls = MagicMock(return_value=reporter_instance)
    monkeypatch.setattr(module, "PerStockReporter", reporter_cls)

    monkeypatch.setattr(module, "export_pdf", MagicMock())

    module.main(["--fast-test"])

    zhihu_collector_cls.assert_not_called()
    raw_data = reporter_cls.call_args.kwargs["raw_data"]
    zhihu_data = raw_data["黑芝麻智能"]["zhihu"]
    assert zhihu_data == {
        "report_items": [],
        "knowledge_items": [],
        "gate_stats": {},
        "total": 0,
        "api_calls": 0,
        "fast_test": True,
    }


def test_fast_test_mode_reuses_cached_zhihu_data(monkeypatch, tmp_path):
    module = _load_entry_module()

    fake_script = tmp_path / "scripts" / "run_黑芝麻智能.py"
    fake_script.parent.mkdir(parents=True)
    monkeypatch.setattr(module, "__file__", str(fake_script))

    cached_zhihu = {
        "report_items": [{"title": "缓存知乎深度分析"}],
        "knowledge_items": [],
        "gate_stats": {"keep": 1, "demote": 0, "discard": 0},
        "total": 1,
        "api_calls": 0,
    }
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)
    raw_path = raw_dir / "report_input_20260601_黑芝麻智能.json"
    raw_path.write_text(
        json.dumps({
            "raw_data": {
                "黑芝麻智能": {
                    "zhihu": cached_zhihu,
                }
            }
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "_load_xueqiu_data", lambda stock_name, date_str: [
        {
            "title": "黑芝麻智能量产进展",
            "content": "黑芝麻智能华山芯片量产",
            "like": 10,
            "comment": 5,
        }
    ])

    zhihu_collector_cls = MagicMock(side_effect=AssertionError("ZhihuCollector should not run"))
    monkeypatch.setattr(module, "ZhihuCollector", zhihu_collector_cls)

    reporter_instance = MagicMock()
    reporter_instance.generate_stock_report.return_value = ("", "")
    reporter_cls = MagicMock(return_value=reporter_instance)
    monkeypatch.setattr(module, "PerStockReporter", reporter_cls)

    monkeypatch.setattr(module, "export_pdf", MagicMock())

    module.main(["--fast-test"])

    zhihu_collector_cls.assert_not_called()
    raw_data = reporter_cls.call_args.kwargs["raw_data"]
    assert raw_data["黑芝麻智能"]["zhihu"] == cached_zhihu
