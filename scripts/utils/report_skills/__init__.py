"""Report generation skills package."""

from .data_skills import data_loading_skill, quality_gate_skill, quote_fetching_skill

__all__ = [
    "data_loading_skill",
    "quality_gate_skill",
    "quote_fetching_skill",
]
