"""Content consolidator — cross-source deduplication and summary."""

from typing import Any, Dict, List


class ContentConsolidator:
    """Deduplicate and summarize content from multiple sources."""

    def consolidate(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate items and return consolidated list."""
        seen = set()
        result = []
        for item in items:
            key = item.get("title", "") + "|" + item.get("content", "")[:100]
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    def generate_cross_source_summary(self, consolidated: List[Dict[str, Any]]) -> str:
        """Generate a summary string from consolidated items."""
        if not consolidated:
            return ""
        return f"Consolidated {len(consolidated)} unique items."
