"""Load persisted broker research digest notes as display-only synthesis items."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

if __name__.startswith("utils."):
    from .source_adapter import SynthesisItem
else:
    from source_adapter import SynthesisItem


BROKER_RESEARCH_SOURCE_TYPE = "broker_research"


def load_broker_research_digest_synthesis_items(
    *,
    stock_name: str,
    base_dir: str | Path,
    max_items: int = 5,
) -> List[SynthesisItem]:
    """Read broker-research digest Knowledge notes and convert them to display items.

    The reader is intentionally read-only.  Only notes that pass all guardrail
    checks are returned; the caller must still opt in via synthesis context
    flags before they are shown.
    """
    notes_dir = (
        Path(base_dir)
        / "10-Stocks"
        / _safe_dir_segment(stock_name)
        / "broker_research_digest"
    )
    if not notes_dir.exists():
        return []

    candidates: List[SynthesisItem] = []
    for path in sorted(notes_dir.glob("*.md")):
        item = _read_note_as_item(path)
        if item is None:
            continue
        candidates.append(item)

    selected: List[SynthesisItem] = []
    seen_clusters: set[str] = set()
    # First pass: keep at most one item per viewpoint_cluster.
    for item in candidates:
        cluster = str((item.extra or {}).get("viewpoint_cluster", "")).strip()
        if not cluster or cluster in seen_clusters:
            continue
        seen_clusters.add(cluster)
        selected.append(item)
        if len(selected) >= max_items:
            break

    # Second pass: fill remaining budget with additional non-duplicate clusters.
    if len(selected) < max_items:
        for item in candidates:
            if item in selected:
                continue
            cluster = str((item.extra or {}).get("viewpoint_cluster", "")).strip()
            if cluster in seen_clusters:
                continue
            seen_clusters.add(cluster)
            selected.append(item)
            if len(selected) >= max_items:
                break

    return selected


def _read_note_as_item(path: Path) -> Optional[SynthesisItem]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    frontmatter = _parse_frontmatter(text)
    if not _passes_guardrails(frontmatter):
        return None

    excerpt = _extract_broker_research_excerpt(text)
    if not excerpt:
        return None

    title = str(frontmatter.get("report_title") or frontmatter.get("title") or "券商研报").strip()
    institution = str(frontmatter.get("institution") or "券商").strip()
    card_type = str(frontmatter.get("card_type") or "").strip()
    viewpoint_cluster = str(frontmatter.get("viewpoint_cluster") or "").strip()
    report_length_class = str(frontmatter.get("report_length_class") or "").strip()
    publish_time = str(frontmatter.get("publish_time") or "").strip()

    return SynthesisItem(
        title=f"{institution} | {title}".strip(" |") if institution else title,
        content=excerpt,
        author=institution,
        source_platform="券商研报",
        url="",
        publish_time=publish_time,
        interaction_score=0,
        extra={
            "source_type": BROKER_RESEARCH_SOURCE_TYPE,
            "source_credit": 72,
            "verification_status": "professional_observation",
            "claim_status": "professional_analysis",
            "knowledge_eligible": False,
            "report_eligible": False,
            "synthesis_eligible": False,
            "synthesis_display_only": True,
            "confirmed_fact": False,
            "scoring_eligible": False,
            "risk_score_eligible": False,
            "institution": institution,
            "card_type": card_type,
            "viewpoint_cluster": viewpoint_cluster,
            "report_length_class": report_length_class,
        },
    )


def _passes_guardrails(frontmatter: Dict[str, Any]) -> bool:
    required_keys = (
        "source_type",
        "claim_status",
        "source_credit",
        "confirmed_fact",
        "scoring_eligible",
        "risk_score_eligible",
        "display_only",
    )
    if any(key not in frontmatter for key in required_keys):
        return False
    if str(frontmatter.get("source_type")) != BROKER_RESEARCH_SOURCE_TYPE:
        return False
    if str(frontmatter.get("claim_status")) != "professional_analysis":
        return False
    if int(frontmatter.get("source_credit") or 0) != 72:
        return False
    if _is_truthy(frontmatter.get("confirmed_fact")):
        return False
    if _is_truthy(frontmatter.get("scoring_eligible")):
        return False
    if _is_truthy(frontmatter.get("risk_score_eligible")):
        return False
    if _is_truthy(frontmatter.get("display_only")):
        return False
    return True


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)


def _extract_broker_research_excerpt(text: str) -> str:
    match = re.search(
        r"(?ms)^## Broker Research Excerpt\s*\n+(?P<body>.*?)(?:\n## |\Z)",
        text,
    )
    if not match:
        return ""

    lines = []
    for line in match.group("body").splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            lines.append(stripped.lstrip(">").strip())
        elif lines and stripped:
            break
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def _parse_frontmatter(text: str) -> Dict[str, Any]:
    match = re.match(r"\A---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not match:
        return {}

    data: Dict[str, Any] = {}
    for raw_line in match.group(1).splitlines():
        if not raw_line or raw_line.startswith(" ") or ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key or value == "":
            continue
        data[key] = _clean_scalar(value)
    return data


def _clean_scalar(value: str) -> Any:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if (
        (value.startswith('"') and value.endswith('"'))
        or (value.startswith("'") and value.endswith("'"))
    ):
        value = value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value
    return value


def _safe_dir_segment(value: str) -> str:
    cleaned = re.sub(r"[\\/:\*\?\"<>\|\r\n\t]+", "_", str(value or "")).strip(" ._")
    return cleaned or "unknown"
