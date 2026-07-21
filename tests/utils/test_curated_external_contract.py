from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

import curated_external_argument_cards as external_contract
from curated_external_argument_cards import (
    EXTERNAL_DISPLAY_TOPIC_ORDER,
    external_family_title,
    external_scope_bucket,
    external_unit_key,
    external_units_by_key,
)


def test_external_contract_owns_titles_order_and_scope_normalization():
    assert external_family_title("technology_product") == "技术与产品"
    assert external_family_title("unknown") == "外部变量"
    assert EXTERNAL_DISPLAY_TOPIC_ORDER[:3] == ("需求与客户", "商业化进展", "技术与产品")
    assert external_scope_bucket("peer_or_industry") == "peer_or_industry"
    assert external_scope_bucket("target_with_peer_context") == "target"


def test_external_contract_builds_one_canonical_unit_index():
    cards = [{
        "argument_key": " technology ",
        "evidence_units": [{"unit_id": " unit:1 ", "text": "原文。"}],
    }]

    index = external_units_by_key(cards)

    assert external_unit_key(" technology ", " unit:1 ") == ("technology", "unit:1")
    assert external_contract.clean_external_text("  technology\n product  ") == "technology product"
    assert index[("technology", "unit:1")]["text"] == "原文。"
