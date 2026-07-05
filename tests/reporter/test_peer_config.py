from scripts.utils.reporter.peer_config import get_peer_codes, get_peer_names


def test_peer_names_prefers_stock_config_and_dedupes_target():
    config = {
        "competitors": ["复旦微电", "紫光国微", "安路科技", "紫光国微"],
        "peer_codes": {"紫光国微": "002049", "安路科技": "688107"},
    }

    assert get_peer_names("复旦微电", config) == ["紫光国微", "安路科技"]


def test_peer_names_falls_back_to_constants_for_existing_stock():
    assert "杰华特" in get_peer_names("圣邦股份", None)


def test_peer_codes_merges_config_and_stock_code_fallbacks():
    config = {
        "competitors": ["紫光国微", "安路科技", "兆易创新"],
        "peer_codes": {"紫光国微": "002049", "安路科技": "688107"},
    }
    stock_codes = {"复旦微电": "688385", "兆易创新": "603986"}

    codes = get_peer_codes("复旦微电", stock_codes, config)

    assert codes == {
        "复旦微电": "688385",
        "紫光国微": "002049",
        "安路科技": "688107",
        "兆易创新": "603986",
    }

