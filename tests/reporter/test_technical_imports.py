import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pytest


# ---------------------------------------------------------------------------
# Part A: direct imports of new modules (created in Phase 2 Tasks 1-4)
# ---------------------------------------------------------------------------

NEW_MODULES = [
    "technical_indicators",
    "technical_structure",
    "technical_state_machine",
    "technical_patterns",
    "technical_resonance",
    "technical_analyzer",
]


@pytest.mark.parametrize("module_name", NEW_MODULES)
def test_new_module_can_be_imported(module_name):
    """Each new module must be importable directly."""
    try:
        __import__(module_name)
    except ImportError as exc:
        if module_name == "technical_analyzer":
            pytest.fail(f"technical_analyzer must always be importable: {exc}")
        pytest.skip(f"{module_name} not yet created: {exc}")


# ---------------------------------------------------------------------------
# Part B: legacy symbols from technical_analyzer
# ---------------------------------------------------------------------------

LEGACY_CALLABLES = [
    "_sma",
    "_ema",
    "_atr",
    "_macd",
    "_rsi",
    "_bollinger",
    "compute_bias",
    "compute_boll_state",
    "compute_weekly_trend",
    "classify_trend_state",
    "compute_trend_health",
    "detect_boll_overextension",
    "analyze",
    "advanced_medium_term_resonance",
]


def test_technical_analyzer_imports():
    """technical_analyzer must always be importable."""
    import technical_analyzer as ta
    assert ta is not None


@pytest.mark.parametrize("symbol_name", LEGACY_CALLABLES)
def test_legacy_symbol_callable(symbol_name):
    """Legacy symbols exported by technical_analyzer must be callable."""
    import technical_analyzer as ta

    assert hasattr(ta, symbol_name), f"technical_analyzer missing {symbol_name}"
    symbol = getattr(ta, symbol_name)
    assert callable(symbol), f"{symbol_name} is not callable"
