"""Tests for the peer comparison material builder."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.peer_comparison_material import (
    build_peer_comparison_material,
    filter_peer_rows_for_prompt,
)


def _make_competitor_metrics():
    """Return a realistic competitor_metrics dict for 复旦微电 and its config peers."""
    return {
        "复旦微电": {
            "gross_margin": 60.0,
            "pe_ttm": 50.0,
            "forward_pe": 45.0,
            "mcap": 300.0,
            "ps": 8.0,
        },
        "紫光国微": {
            "gross_margin": 65.0,
            "pe_ttm": 40.0,
            "forward_pe": 38.0,
            "mcap": 500.0,
            "ps": 10.0,
        },
        "兆易创新": {
            "gross_margin": 42.0,
            "pe_ttm": 55.0,
            "forward_pe": 50.0,
            "mcap": 700.0,
            "ps": 12.0,
        },
    }


def _make_stock_config():
    return {
        "competitors": ["紫光国微", "安路科技", "兆易创新", "普冉股份", "聚辰股份"],
        "peer_codes": {
            "紫光国微": "002049",
            "安路科技": "688107",
            "兆易创新": "603986",
            "普冉股份": "688766",
            "聚辰股份": "688123",
        },
    }


class TestBuildPeerComparisonMaterial:
    """Tests for build_peer_comparison_material()."""

    def test_builds_high_confidence_metric_rows_from_competitor_metrics(self):
        """Rows built from competitor_metrics get confidence >= 0.80."""
        metrics = _make_competitor_metrics()
        config = _make_stock_config()

        material = build_peer_comparison_material(
            stock_name="复旦微电",
            competitor_metrics=metrics,
            stock_config=config,
        )

        assert material["schema"] == "peer_comparison_material.v1"
        assert material["target"] == "复旦微电"
        assert len(material["rows"]) > 0
        assert material["warnings"] == []

        for row in material["rows"]:
            assert isinstance(row["confidence"], (int, float))
            assert row["usage"] in ("claim_eligible", "context_only", "audit_only")
            assert row["target"] == "复旦微电"
            assert row["peer"] in ("紫光国微", "兆易创新")
            assert row["source_refs"] == ["指标:competitor_metrics"]

            # High confidence from same-metric, same source family
            if row["confidence"] >= 0.80:
                assert row["usage"] == "claim_eligible"
                assert "comparison" in row
                assert "target_value" in row
                assert "peer_value" in row

    def test_drops_rows_when_target_or_peer_value_missing(self):
        """Missing values produce no metric row (no invention)."""
        metrics = {
            "复旦微电": {"gross_margin": 60.0, "mcap": 300.0},
            "紫光国微": {"gross_margin": 65.0},  # missing mcap
        }

        material = build_peer_comparison_material(
            stock_name="复旦微电",
            competitor_metrics=metrics,
            stock_config={"competitors": ["紫光国微"]},
        )

        # gross_margin row should exist
        gross_margin_rows = [r for r in material["rows"] if r["metric"] == "gross_margin"]
        assert len(gross_margin_rows) == 1

        # mcap row should NOT exist because 紫光国微 has no mcap
        mcap_rows = [r for r in material["rows"] if r["metric"] == "mcap"]
        assert len(mcap_rows) == 0

    def test_assigns_usage_tiers_correctly(self):
        """Confidence formula produces correct usage tiers."""
        metrics = {
            "复旦微电": {"gross_margin": 60.0},
            "紫光国微": {"gross_margin": 65.0},
        }

        # Metric rows from confident metrics should be claim_eligible
        material = build_peer_comparison_material(
            stock_name="复旦微电",
            competitor_metrics=metrics,
            stock_config={"competitors": ["紫光国微"]},
        )

        assert len(material["rows"]) == 1
        row = material["rows"][0]
        assert row["confidence"] == 0.85  # same metric, same period, same source family
        assert row["usage"] == "claim_eligible"

        # Context-only: if periods differ, confidence drops
        # For Phase 3b we don't have period info in competitor_metrics,
        # so baseline stays at 0.85. The adjustments test lower tiers
        # through direct confidence assignment (formula coverage).

    def test_drops_social_source_refs(self):
        """Source refs with social-only prefixes are not generated."""
        metrics = _make_competitor_metrics()
        config = _make_stock_config()

        material = build_peer_comparison_material(
            stock_name="复旦微电",
            competitor_metrics=metrics,
            stock_config=config,
        )

        for row in material["rows"]:
            for ref in row["source_refs"]:
                assert not ref.startswith("雪球:")
                assert not ref.startswith("知乎:")
                assert not ref.startswith("微信:")
                assert not ref.startswith("精选外部:")
                assert not ref.startswith("社区:")

    def test_compact_row_count_limits(self):
        """No more than 2 peers per metric and max 8 total metric rows."""
        # Create many peers with many metrics
        metrics = {
            "复旦微电": {"gross_margin": 60.0, "pe_ttm": 50.0, "forward_pe": 45.0, "mcap": 300.0, "ps": 8.0},
            "紫光国微": {"gross_margin": 65.0, "pe_ttm": 40.0, "forward_pe": 38.0, "mcap": 500.0, "ps": 10.0},
            "安路科技": {"gross_margin": 55.0, "pe_ttm": 60.0, "forward_pe": 55.0, "mcap": 100.0, "ps": 15.0},
            "兆易创新": {"gross_margin": 42.0, "pe_ttm": 55.0, "forward_pe": 50.0, "mcap": 700.0, "ps": 12.0},
            "普冉股份": {"gross_margin": 48.0, "pe_ttm": 70.0, "forward_pe": 65.0, "mcap": 80.0, "ps": 20.0},
            "聚辰股份": {"gross_margin": 45.0, "pe_ttm": 75.0, "forward_pe": 68.0, "mcap": 60.0, "ps": 22.0},
        }
        config = _make_stock_config()

        material = build_peer_comparison_material(
            stock_name="复旦微电",
            competitor_metrics=metrics,
            stock_config=config,
        )

        assert len(material["rows"]) <= 8

        # Check per-metric peer limit (max 2 per metric)
        metrics_seen = {}
        for row in material["rows"]:
            m = row["metric"]
            metrics_seen.setdefault(m, 0)
            metrics_seen[m] += 1
        for m, count in metrics_seen.items():
            assert count <= 2, f"Metric {m} has {count} peers, max is 2"

    def test_returns_empty_rows_when_no_data(self):
        """No data produces valid schema with empty rows."""
        material = build_peer_comparison_material(
            stock_name="复旦微电",
            competitor_metrics=None,
        )

        assert material["schema"] == "peer_comparison_material.v1"
        assert material["target"] == "复旦微电"
        assert material["rows"] == []
        assert material["peers"] == []

    def test_peers_list_in_config_order(self):
        """material['peers'] preserves config competitor order."""
        metrics = {
            "复旦微电": {"gross_margin": 60.0},
            "紫光国微": {"gross_margin": 65.0},
            "兆易创新": {"gross_margin": 42.0},
        }
        config = _make_stock_config()

        material = build_peer_comparison_material(
            stock_name="复旦微电",
            competitor_metrics=metrics,
            stock_config=config,
        )

        # peers should be in config order, only those with data
        assert material["peers"] == ["紫光国微", "兆易创新"]


class TestFilterPeerRowsForPrompt:
    """Tests for filter_peer_rows_for_prompt()."""

    def test_removes_low_confidence_rows(self):
        """Rows with confidence < 0.50 are removed entirely."""
        material = {
            "schema": "peer_comparison_material.v1",
            "target": "复旦微电",
            "peers": ["紫光国微"],
            "rows": [
                {
                    "dimension": "盈利能力",
                    "target": "复旦微电",
                    "peer": "紫光国微",
                    "metric": "gross_margin",
                    "target_value": 60.0,
                    "peer_value": 65.0,
                    "comparison": "毛利率低于紫光国微",
                    "source_refs": ["指标:competitor_metrics"],
                    "confidence": 0.85,
                    "usage": "claim_eligible",
                },
                {
                    "dimension": "盈利能力",
                    "target": "复旦微电",
                    "peer": "紫光国微",
                    "metric": "gross_margin",
                    "target_value": 60.0,
                    "peer_value": 65.0,
                    "comparison": "可能毛利率低于同行",
                    "source_refs": ["行业资讯:某报告"],
                    "confidence": 0.40,
                    "usage": "audit_only",
                },
            ],
            "warnings": [],
        }

        filtered = filter_peer_rows_for_prompt(material)

        assert len(filtered["rows"]) == 1
        assert filtered["rows"][0]["confidence"] == 0.85

    def test_strips_comparison_from_context_only_rows(self):
        """Rows with 0.50 <= confidence < 0.70 lose comparison, values."""
        material = {
            "schema": "peer_comparison_material.v1",
            "target": "复旦微电",
            "peers": ["紫光国微"],
            "rows": [
                {
                    "dimension": "盈利能力",
                    "target": "复旦微电",
                    "peer": "紫光国微",
                    "metric": "gross_margin",
                    "target_value": 60.0,
                    "peer_value": 65.0,
                    "comparison": "毛利率可能低于紫光国微",
                    "source_refs": ["行业资讯:某报告"],
                    "confidence": 0.60,
                    "usage": "context_only",
                },
            ],
            "warnings": [],
        }

        filtered = filter_peer_rows_for_prompt(material)

        assert len(filtered["rows"]) == 1
        row = filtered["rows"][0]
        assert "comparison" not in row or not row.get("comparison")
        assert "target_value" not in row or row.get("target_value") is None
        assert "peer_value" not in row or row.get("peer_value") is None
        assert row["dimension"] == "盈利能力"
        assert row["source_refs"] == ["行业资讯:某报告"]
        assert row["confidence"] == 0.60
        assert row["usage"] == "context_only"

    def test_high_confidence_rows_unchanged(self):
        """Rows with confidence >= 0.70 keep all fields."""
        material = {
            "schema": "peer_comparison_material.v1",
            "target": "复旦微电",
            "peers": ["紫光国微"],
            "rows": [
                {
                    "dimension": "盈利能力",
                    "target": "复旦微电",
                    "peer": "紫光国微",
                    "metric": "gross_margin",
                    "target_value": 60.0,
                    "peer_value": 65.0,
                    "comparison": "毛利率低于紫光国微",
                    "source_refs": ["指标:competitor_metrics"],
                    "confidence": 0.85,
                    "usage": "claim_eligible",
                },
            ],
            "warnings": [],
        }

        filtered = filter_peer_rows_for_prompt(material)

        assert filtered["rows"] == material["rows"]

    def test_preserves_empty_rows(self):
        """Empty rows list stays empty."""
        material = {
            "schema": "peer_comparison_material.v1",
            "target": "复旦微电",
            "peers": [],
            "rows": [],
            "warnings": [],
        }

        filtered = filter_peer_rows_for_prompt(material)
        assert filtered["rows"] == []
        assert filtered["peers"] == []
