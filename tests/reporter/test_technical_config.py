import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

from technical_config import load_technical_config


def test_load_config_returns_dict():
    cfg = load_technical_config()
    assert isinstance(cfg, dict)
    assert "technical" in cfg
    assert cfg["technical"]["boll"]["open_ratio"] == 1.2


def test_missing_file_uses_defaults():
    cfg = load_technical_config("/nonexistent/path.yaml")
    assert isinstance(cfg, dict)
    assert cfg["technical"]["boll"]["open_ratio"] == 1.2


def test_config_overrides_defaults():
    cfg = load_technical_config()
    assert cfg["technical"]["bias"]["lookback"] == 120
