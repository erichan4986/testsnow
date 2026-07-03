import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from fundflow_material import build_fundflow_material_pack, format_fundflow_material_pack


def test_build_fundflow_material_pack_summarizes_baidu_rows():
    pack = build_fundflow_material_pack([
        {
            "date": "2026-07-02",
            "main_in": "1200",
            "super_net_in": "500",
            "large_net_in": "300",
            "small_net_in": "-900",
            "change_pct": "2.5",
            "source": "baidu_pae",
        },
        {
            "date": "2026-07-01",
            "main_in": "-200",
            "super_net_in": "-100",
            "large_net_in": "50",
            "small_net_in": "300",
            "change_pct": "-0.5",
            "source": "baidu_pae",
        },
    ])

    assert pack["schema"] == "fundflow_material_pack.v1"
    assert pack["summary"]["days"] == 2
    assert pack["summary"]["main_net_total"] == 1000.0
    assert pack["summary"]["super_large_net_total"] == 750.0
    assert pack["summary"]["price_change_total_pct"] == 2.0
    assert pack["summary"]["signal"] == "inflow_with_price_up"
    assert pack["rows"][0]["main_net"] == 1200.0
    assert pack["rows"][0]["super_large_net"] == 800.0


def test_format_fundflow_material_pack_is_compact_and_non_investment_signal():
    pack = build_fundflow_material_pack([
        {"date": "2026-07-02", "main_in": "1200", "change_pct": "2.5"},
        {"date": "2026-07-01", "main_in": "-200", "change_pct": "-0.5"},
    ])

    text = format_fundflow_material_pack(pack)

    assert "资金流向确定性汇总（仅供4.3使用，非新增引用）" in text
    assert "近2日主力净流入合计 1000万" in text
    assert "资金与价格同向" in text
    assert "不要自行求和" in text
    assert "signal=买入信号" not in text
