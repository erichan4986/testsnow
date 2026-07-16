"""Load persisted annual narrative materials as display-only synthesis items."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List

if __name__.startswith("utils."):
    from .source_adapter import SynthesisItem
    from .annual_report_material_pack import (
        build_annual_report_material_pack,
        selected_cards_to_synthesis_items,
    )
else:
    from source_adapter import SynthesisItem
    from annual_report_material_pack import (
        build_annual_report_material_pack,
        selected_cards_to_synthesis_items,
    )


def load_periodic_narrative_card_synthesis_items(
    *,
    stock_name: str,
    base_dir: str | Path,
    stock_code: str = "",
    max_cards: int = 12,
    use_pack: bool = True,
    **_legacy_options: Any,
) -> List[SynthesisItem]:
    """Load the validated material pack; legacy flags cannot bypass it."""
    del use_pack, _legacy_options
    pack = build_annual_report_material_pack(
        stock_name=stock_name,
        stock_code=stock_code,
        base_dir=base_dir,
    )
    return selected_cards_to_synthesis_items(
        pack["selected_narrative_cards"]
    )[: max(0, int(max_cards))]
