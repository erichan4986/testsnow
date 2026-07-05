"""Config-first peer lookup helpers for report generation."""

from __future__ import annotations

from typing import Any, Dict, List

try:
    from .constants import COMPETITOR_CODES, COMPETITOR_MAP
except ImportError:
    from constants import COMPETITOR_CODES, COMPETITOR_MAP


def get_peer_names(stock_name: str, stock_config: Dict[str, Any] | None = None) -> List[str]:
    """Return peer names with stock config taking precedence over constants."""
    configured = []
    if isinstance(stock_config, dict):
        configured = stock_config.get("competitors") or []
    raw_names = configured if configured else COMPETITOR_MAP.get(stock_name, [])
    peers: List[str] = []
    seen = {str(stock_name)}
    for raw_name in raw_names:
        name = str(raw_name or "").strip()
        if not name or name in seen:
            continue
        peers.append(name)
        seen.add(name)
    return peers


def get_peer_codes(
    stock_name: str,
    stock_codes: Dict[str, str] | None = None,
    stock_config: Dict[str, Any] | None = None,
) -> Dict[str, str]:
    """Return target and peer code mapping with config peer_codes as first fallback."""
    stock_codes = stock_codes or {}
    config_codes = {}
    if isinstance(stock_config, dict):
        config_codes = stock_config.get("peer_codes") or {}
    names = [stock_name] + get_peer_names(stock_name, stock_config)
    resolved: Dict[str, str] = {}
    for name in names:
        code = stock_codes.get(name) or config_codes.get(name) or COMPETITOR_CODES.get(name)
        if code:
            resolved[name] = str(code).strip()
    return resolved

