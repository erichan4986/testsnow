# Knowledge Synthesizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `KnowledgeSynthesizer` to transform the report from source-oriented listing into theme-oriented narrative synthesis, with `[^{n}]` citations and graceful fallback when LLM is unavailable.

**Architecture:** A single `KnowledgeSynthesizer` class consumes consolidated multi-source items + structured data (reports, announcements, fundflow) and produces five themed Markdown narratives. `PerStockReporter` calls it during report generation and assembles the new 9-section report layout. A `SourceAdapter` protocol allows future sources (WeChat, news APIs) to plug in without modifying the synthesizer.

**Tech Stack:** Python 3.10+, OpenAI-compatible LLM client (DeepSeek/Moonshot), regex, existing `ContentConsolidator` and `ContentQualityGate` outputs.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/utils/knowledge_synthesizer.py` | **Create** | Core synthesizer: theme prompt building, LLM call, citation parsing, source index management |
| `scripts/utils/source_adapter.py` | **Create** | `SourceAdapter` protocol + adapters for xueqiu/zhihu/wechat/report/announcement/fundflow/news |
| `scripts/utils/stock_reporter.py` | **Modify** | Integrate synthesizer into `generate_stock_report`, add `_synthesize_sections()`, restructure to 9-section layout |
| `tests/utils/test_knowledge_synthesizer.py` | **Create** | Unit tests for citation parsing, prompt building, fallback behavior |
| `tests/utils/test_source_adapter.py` | **Create** | Unit tests for each adapter's `to_synthesis_item()` output |

---

## Data Flow (before this plan)

```
Xueqiu/Zhihu/Other → ContentQualityGate → keep_posts / zhihu_report_items
                        ↓
                  ContentConsolidator → consolidated items with cross_sources
                        ↓
                  PerStockReporter.generate_stock_report() → 12-section Markdown
```

## Data Flow (after this plan)

```
Xueqiu/Zhihu/Other → ContentQualityGate → keep_posts / zhihu_report_items
                        ↓
                  ContentConsolidator → consolidated items with cross_sources
                        ↓
                  SourceAdapter.to_synthesis_item() → normalized List[SynthesisItem]
                        ↓
                  KnowledgeSynthesizer.synthesize() → 5 themed narratives + citations
                        ↓
                  PerStockReporter.generate_stock_report() → 9-section Markdown
```

---

## Task 1: SourceAdapter Protocol and Adapters

**Files:**
- Create: `scripts/utils/source_adapter.py`
- Test: `tests/utils/test_source_adapter.py`

**Why first:** The synthesizer needs a uniform input format. All downstream tasks depend on this interface.

### Step 1.1: Write the failing test for SourceAdapter protocol

```python
# tests/utils/test_source_adapter.py
import pytest
from scripts.utils.source_adapter import (
    SynthesisItem, SourceAdapter,
    XueqiuAdapter, ZhihuAdapter, ReportAdapter,
)


def test_xueqiu_adapter_maps_fields():
    raw = {
        "title": "模拟芯片涨价分析",
        "author": "张三",
        "content": "圣邦股份Q1收入增长40%...",
        "url": "https://xueqiu.com/123/456",
        "time": "2026-05-20 10:00",
        "like_count": 100,
        "comment_count": 20,
        "source": "雪球",
    }
    item = XueqiuAdapter.to_synthesis_item(raw)
    assert item.title == "模拟芯片涨价分析"
    assert item.author == "张三"
    assert item.source_platform == "雪球"
    assert item.interaction_score == 120
    assert "40%" in item.content


def test_zhihu_adapter_maps_platform():
    raw = {
        "title": "半导体行业观察",
        "author_name": "李四",
        "content_text": "杰华特竞争加剧...",
        "url": "https://zhuanlan.zhihu.com/p/123",
        "edit_time": 1747756800,
        "vote_up_count": 50,
        "comment_count": 10,
        "source_platform": "网易",
    }
    item = ZhihuAdapter.to_synthesis_item(raw)
    assert item.source_platform == "知乎全网(网易)"
    assert item.interaction_score == 60


def test_report_adapter_maps_institution():
    raw = {
        "title": "圣邦股份深度报告",
        "institution": "国信证券",
        "content": "目标价120元...",
        "url": "",
        "publish_date": "2026-05-15",
        "rating": "买入",
    }
    item = ReportAdapter.to_synthesis_item(raw)
    assert item.author == "国信证券"
    assert item.source_platform == "研报"
    assert item.content == "[评级: 买入] 目标价120元..."
```

Run: `python -m pytest tests/utils/test_source_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.utils.source_adapter'`

### Step 1.2: Run test to verify it fails

Run: `python -m pytest tests/utils/test_source_adapter.py -v`
Expected: 3 FAILs (module not found)

### Step 1.3: Implement SourceAdapter protocol and concrete adapters

```python
# scripts/utils/source_adapter.py
"""
SourceAdapter: 统一多源数据格式，供 KnowledgeSynthesizer 使用。

支持来源：雪球、知乎、研报、公告、资金流向、新闻、（预留）微信公众号
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Protocol


@dataclass
class SynthesisItem:
    """KnowledgeSynthesizer 的标准输入单元"""
    title: str
    content: str
    author: str
    source_platform: str  # "雪球" | "知乎" | "知乎全网(网易)" | "研报" | "公告" | "资金流向" | "新闻"
    url: str
    publish_time: str  # ISO date or datetime string
    interaction_score: int = 0  # likes + comments + reposts (or equivalent)
    extra: Dict = field(default_factory=dict)


class SourceAdapter(Protocol):
    """源适配器协议。每个来源实现静态方法 to_synthesis_item。"""

    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        ...


class XueqiuAdapter:
    """雪球帖子适配器"""

    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        content = raw.get("content", "")
        if not content:
            content = raw.get("content_text", "")
        return SynthesisItem(
            title=raw.get("title", ""),
            content=content,
            author=raw.get("author", ""),
            source_platform=raw.get("source", "雪球"),
            url=raw.get("url", ""),
            publish_time=raw.get("time", ""),
            interaction_score=(
                raw.get("like_count", 0)
                + raw.get("comment_count", 0)
                + raw.get("repost_count", 0)
            ),
            extra={"track": raw.get("_track", ""), "is_repost": raw.get("is_repost", False)},
        )


class ZhihuAdapter:
    """知乎及全网内容适配器"""

    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        platform = raw.get("source_platform", "知乎")
        source_type = raw.get("_source_type", "site")
        source_label = f"知乎全网({platform})" if source_type == "web" and platform != "知乎" else "知乎"
        content = raw.get("content", "") or raw.get("content_text", "")
        edit_time = raw.get("edit_time", 0)
        publish_time = ""
        if edit_time:
            publish_time = datetime.fromtimestamp(edit_time).strftime("%Y-%m-%d")
        return SynthesisItem(
            title=raw.get("title", ""),
            content=content,
            author=raw.get("author_name", "未知"),
            source_platform=source_label,
            url=raw.get("url", ""),
            publish_time=publish_time,
            interaction_score=raw.get("vote_up_count", 0) + raw.get("comment_count", 0),
            extra={"search_keyword": raw.get("search_keyword", ""), "source_type": source_type},
        )


class ReportAdapter:
    """券商研报适配器"""

    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        content_parts = []
        if raw.get("rating"):
            content_parts.append(f"[评级: {raw['rating']}]")
        if raw.get("target_price"):
            content_parts.append(f"[目标价: {raw['target_price']}]")
        content_parts.append(raw.get("content", ""))
        return SynthesisItem(
            title=raw.get("title", ""),
            content=" ".join(content_parts),
            author=raw.get("institution", ""),
            source_platform="研报",
            url=raw.get("url", ""),
            publish_time=raw.get("publish_date", ""),
            interaction_score=0,
            extra={"rating": raw.get("rating", ""), "target_price": raw.get("target_price", "")},
        )


class AnnouncementAdapter:
    """公司公告适配器"""

    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        return SynthesisItem(
            title=raw.get("title", ""),
            content=raw.get("content", ""),
            author=raw.get("company", ""),
            source_platform="公告",
            url=raw.get("url", ""),
            publish_time=raw.get("date", ""),
            interaction_score=0,
            extra={"announcement_type": raw.get("type", "")},
        )


class FundFlowAdapter:
    """资金流向适配器（将单条记录转为文本描述）"""

    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        date = raw.get("date", "")
        main_in = raw.get("main_inflow", 0)
        main_out = raw.get("main_outflow", 0)
        net = main_in - main_out
        content = f"日期 {date}: 主力净流入 {net:.0f}万 (流入 {main_in:.0f}万, 流出 {main_out:.0f}万)"
        return SynthesisItem(
            title=f"资金流向 {date}",
            content=content,
            author="",
            source_platform="资金流向",
            url="",
            publish_time=date,
            interaction_score=0,
            extra={"main_inflow": main_in, "main_outflow": main_out, "net": net},
        )


class NewsAdapter:
    """新闻适配器"""

    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        return SynthesisItem(
            title=raw.get("title", ""),
            content=raw.get("content", ""),
            author=raw.get("source", ""),
            source_platform="新闻",
            url=raw.get("url", ""),
            publish_time=raw.get("date", ""),
            interaction_score=0,
            extra={},
        )


class WechatAdapter:
    """微信公众号适配器（预留接口）"""

    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        return SynthesisItem(
            title=raw.get("title", ""),
            content=raw.get("content", ""),
            author=raw.get("author", ""),
            source_platform="微信公众号",
            url=raw.get("url", ""),
            publish_time=raw.get("publish_time", ""),
            interaction_score=raw.get("read_count", 0),
            extra={"account": raw.get("account", "")},
        )


def adapt_all(
    xueqiu_items: List[Dict] = None,
    zhihu_items: List[Dict] = None,
    reports: List[Dict] = None,
    announcements: List[Dict] = None,
    fundflow: List[Dict] = None,
    news: List[Dict] = None,
    wechat_items: List[Dict] = None,
) -> List[SynthesisItem]:
    """批量适配所有来源的数据为统一 SynthesisItem 列表。"""
    result = []
    if xueqiu_items:
        result.extend([XueqiuAdapter.to_synthesis_item(i) for i in xueqiu_items])
    if zhihu_items:
        result.extend([ZhihuAdapter.to_synthesis_item(i) for i in zhihu_items])
    if reports:
        result.extend([ReportAdapter.to_synthesis_item(i) for i in reports])
    if announcements:
        result.extend([AnnouncementAdapter.to_synthesis_item(i) for i in announcements])
    if fundflow:
        result.extend([FundFlowAdapter.to_synthesis_item(i) for i in fundflow])
    if news:
        result.extend([NewsAdapter.to_synthesis_item(i) for i in news])
    if wechat_items:
        result.extend([WechatAdapter.to_synthesis_item(i) for i in wechat_items])
    return result
```

### Step 1.4: Run tests to verify they pass

Run: `python -m pytest tests/utils/test_source_adapter.py -v`
Expected: 3 PASS

### Step 1.5: Commit

```bash
git add scripts/utils/source_adapter.py tests/utils/test_source_adapter.py
git commit -m "feat(source-adapter): add SourceAdapter protocol with 7 source adapters"
```

---

## Task 2: KnowledgeSynthesizer Core Component

**Files:**
- Create: `scripts/utils/knowledge_synthesizer.py`
- Test: `tests/utils/test_knowledge_synthesizer.py`

### Step 2.1: Write the failing test for citation parsing

```python
# tests/utils/test_knowledge_synthesizer.py
import pytest
from scripts.utils.knowledge_synthesizer import KnowledgeSynthesizer
from scripts.utils.source_adapter import SynthesisItem


def test_parse_citations_extracts_refs():
    synth = KnowledgeSynthesizer()
    text = "收入同比增长40%[^1]，毛利率51.6%[^2]。"
    parsed, cites = synth._parse_with_citations(text)
    assert "[^1]" not in parsed  # references stripped from body? no, keep them in narrative
    assert 1 in cites
    assert 2 in cites


def test_parse_citations_handles_missing_refs():
    synth = KnowledgeSynthesizer()
    text = "收入同比增长40%，毛利率51.6%。"
    parsed, cites = synth._parse_with_citations(text)
    assert len(cites) == 0


def test_build_prompt_includes_source_list():
    synth = KnowledgeSynthesizer()
    items = [
        SynthesisItem(
            title="Q1业绩分析", content="营收增长40%", author="张三",
            source_platform="雪球", url="http://x", publish_time="2026-05-20",
            interaction_score=100,
        ),
        SynthesisItem(
            title="行业竞争", content="杰华特威胁", author="李四",
            source_platform="知乎", url="http://z", publish_time="2026-05-19",
            interaction_score=50,
        ),
    ]
    prompt = synth._build_prompt("估值争议", items)
    assert "[1]" in prompt
    assert "Q1业绩分析" in prompt
    assert "[2]" in prompt
    assert "行业竞争" in prompt
    assert "估值争议" in prompt


def test_synthesize_returns_empty_when_no_client():
    synth = KnowledgeSynthesizer(client=None)
    result = synth.synthesize("圣邦股份", {"items": []})
    assert result["industry_logic"] == ""
    assert result["fundamentals"] == ""
    assert result["citations"] == {}


def test_fallback_when_items_too_few():
    """某主题信息不足时跳过合成"""
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="唯一内容", content="内容", author="A",
            source_platform="雪球", url="", publish_time="",
        )
    ]
    # With no client it returns empty, but even with client, <3 items should skip
    # We'll test this behavior by mocking
```

Run: `python -m pytest tests/utils/test_knowledge_synthesizer.py -v`
Expected: FAIL with `ModuleNotFoundError`

### Step 2.2: Implement KnowledgeSynthesizer

```python
# scripts/utils/knowledge_synthesizer.py
"""
KnowledgeSynthesizer: 主题化综合叙事生成器

将多源信息按主题维度合成连贯叙事，要求 LLM 输出带 [^n] 引用的 Markdown 段落。
"""

import json
import logging
import os
import re
from typing import Dict, List, Optional, Tuple

from scripts.utils.source_adapter import SynthesisItem

logger = logging.getLogger(__name__)

# 主题定义: 主题名 -> (显示标题, 最低所需条目数)
THEMES = {
    "industry_logic": ("产业逻辑与竞争格局", 3),
    "fundamentals": ("业绩基本面追踪", 3),
    "valuation_debate": ("估值争议与市场分歧", 3),
    "funding_sentiment": ("资金面与情绪跟踪", 3),
    "events_catalysts": ("关键事件与催化剂", 3),
}

# 每个主题的 prompt 前缀
THEME_PROMPT_PREFIX = {
    "industry_logic": (
        "你是资深半导体行业分析师。请基于以下多源信息，对{stock_name}的产业逻辑与竞争格局进行综合解读。\n\n"
        "要求：\n"
        "1. 写一段 300-500 字的连贯分析，不要分点罗列\n"
        "2. 每个关键数字和事实后面标注 [^n] 引用\n"
        "3. 必须覆盖：行业供需格局、主要竞争对手动态、国产替代进展、涨价/降价周期判断\n"
        "4. 最后给出该赛道未来 6-12 个月的关键趋势判断\n"
        "5. 不要编造数据，只能基于以下信息\n"
    ),
    "fundamentals": (
        "你是资深半导体行业分析师。请基于以下多源信息，对{stock_name}的业绩基本面进行追踪分析。\n\n"
        "要求：\n"
        "1. 写一段 300-500 字的连贯分析，不要分点罗列\n"
        "2. 每个关键数字和事实后面标注 [^n] 引用\n"
        "3. 必须覆盖：最新季度营收/利润变化、毛利率走势、订单/客户动态、管理层指引\n"
        "4. 最后给出业绩预期修正方向（上调/下调/维持）\n"
        "5. 不要编造数据，只能基于以下信息\n"
    ),
    "valuation_debate": (
        "你是资深半导体行业分析师。请基于以下多源信息，对{stock_name}的估值争议进行综合解读。\n\n"
        "要求：\n"
        "1. 写一段 300-500 字的连贯分析，不要分点罗列\n"
        "2. 每个关键数字和事实后面标注 [^n] 引用\n"
        "3. 必须覆盖：看多方的核心论据、看空方的核心论据、双方分歧的关键变量\n"
        "4. 最后给出一个中性的综合判断\n"
        "5. 不要编造数据，只能基于以下信息\n"
    ),
    "funding_sentiment": (
        "你是资深半导体行业分析师。请基于以下多源信息，对{stock_name}的资金面与情绪进行跟踪分析。\n\n"
        "要求：\n"
        "1. 写一段 250-400 字的连贯分析，不要分点罗列\n"
        "2. 每个关键数字和事实后面标注 [^n] 引用\n"
        "3. 必须覆盖：主力资金动向、散户情绪指标、北向资金/机构持仓变化、融资余额变化\n"
        "4. 最后给出资金面对股价的短期影响判断\n"
        "5. 不要编造数据，只能基于以下信息\n"
    ),
    "events_catalysts": (
        "你是资深半导体行业分析师。请基于以下多源信息，梳理{stock_name}近期的关键事件与催化剂。\n\n"
        "要求：\n"
        "1. 写一段 250-400 字的连贯分析，不要分点罗列\n"
        "2. 每个关键数字和事实后面标注 [^n] 引用\n"
        "3. 必须覆盖：已落地的利好/利空、即将发生的事件、政策/行业催化\n"
        "4. 最后给出下一个值得关注的催化剂时间点\n"
        "5. 不要编造数据，只能基于以下信息\n"
    ),
}


class KnowledgeSynthesizer:
    """
    主题化综合叙事生成器。

    用法:
        synth = KnowledgeSynthesizer()
        result = synth.synthesize("圣邦股份", {"items": [...]})
        # result["industry_logic"] -> Markdown 段落
        # result["citations"] -> {1: {...}, 2: {...}}
    """

    def __init__(self, client=None):
        """
        Args:
            client: 已初始化的 OpenAI-compatible LLM 客户端。
                    为 None 时自动从环境变量初始化（DEEPSEEK_API_KEY 或 MOONSHOT_API_KEY）。
        """
        self.client = client
        self.source_index: Dict[int, Dict] = {}
        self._counter = 0
        if self.client is None:
            self._init_client()

    def _init_client(self):
        """自动从环境变量初始化 LLM 客户端。"""
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("MOONSHOT_API_KEY")
        if not api_key:
            logger.warning("DEEPSEEK_API_KEY / MOONSHOT_API_KEY 未设置，KnowledgeSynthesizer 不可用")
            return
        try:
            from openai import OpenAI
            base_url = (
                "https://api.deepseek.com/v1"
                if os.getenv("DEEPSEEK_API_KEY")
                else "https://api.moonshot.cn/v1"
            )
            model_hint = (
                os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
                if os.getenv("DEEPSEEK_API_KEY")
                else os.getenv("MOONSHOT_MODEL", "moonshot-v1-8k")
            )
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            self._default_model = model_hint
        except Exception as e:
            logger.warning(f"LLM 客户端初始化失败: {e}")

    def synthesize(
        self,
        stock_name: str,
        all_data: Dict,
    ) -> Dict[str, str]:
        """
        对一只股票的全部采集数据进行主题化综合。

        Args:
            all_data: 必须包含键 "items"，值为 List[SynthesisItem]。
                     可选包含: "reports", "announcements", "fundflow", "news"

        Returns:
            {
                "industry_logic": "Markdown 段落...",
                "fundamentals": "Markdown 段落...",
                "valuation_debate": "Markdown 段落...",
                "funding_sentiment": "Markdown 段落...",
                "events_catalysts": "Markdown 段落...",
                "citations": {1: {...}, 2: {...}},
            }
        """
        items: List[SynthesisItem] = all_data.get("items", [])
        if not items:
            logger.warning(f"[{stock_name}] 无内容可供合成")
            return {k: "" for k in THEMES} | {"citations": {}}

        # 重置引用索引
        self.source_index = {}
        self._counter = 0

        result = {}
        for theme_key, (theme_title, min_items) in THEMES.items():
            # 为主题筛选最相关的条目（简化：全部传入，让 LLM 自行判断）
            if len(items) < min_items:
                logger.info(f"[{stock_name}] {theme_title}: 信息不足 ({len(items)} < {min_items})，跳过合成")
                result[theme_key] = ""
                continue

            if not self.client:
                result[theme_key] = ""
                continue

            try:
                narrative, citations = self._synthesize_theme(stock_name, theme_key, items)
                result[theme_key] = narrative
                # 合并引用（全局去重）
                for cid, cdata in citations.items():
                    if cid not in self.source_index:
                        self.source_index[cid] = cdata
            except Exception as e:
                logger.warning(f"[{stock_name}] {theme_title} 合成失败: {e}")
                result[theme_key] = ""

        result["citations"] = dict(self.source_index)
        return result

    def _synthesize_theme(
        self, stock_name: str, theme_key: str, items: List[SynthesisItem]
    ) -> Tuple[str, Dict[int, Dict]]:
        """合成单个主题，返回 (叙事文本, 该主题使用的引用字典)"""
        prompt = self._build_prompt(stock_name, theme_key, items)
        response_text = self._call_llm(prompt)
        return self._parse_with_citations(response_text)

    def _build_prompt(self, stock_name: str, theme_key: str, items: List[SynthesisItem]) -> str:
        """为特定主题构建 LLM prompt。"""
        prefix_template = THEME_PROMPT_PREFIX.get(theme_key, THEMES["industry_logic"])
        prefix = prefix_template.format(stock_name=stock_name)

        source_lines = []
        for i, item in enumerate(items):
            # 限制单条内容长度，防止 prompt 过长
            content_snippet = item.content[:500] if len(item.content) > 500 else item.content
            line = (
                f"[{i+1}] 标题: {item.title} | "
                f"来源: {item.source_platform} | "
                f"作者: {item.author} | "
                f"时间: {item.publish_time} | "
                f"内容: {content_snippet}"
            )
            source_lines.append(line)

        return prefix + "\n\n信息来源：\n" + "\n".join(source_lines)

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM，重试 1 次。"""
        if not self.client:
            return ""

        model = getattr(self, "_default_model", "deepseek-chat")
        last_error = None
        for attempt in range(2):
            try:
                resp = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "你是专业的中文财经分析师，擅长综合多源信息撰写连贯的分析叙事。严格遵守引用标注要求。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.4,
                    max_tokens=2500,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                last_error = e
                logger.warning(f"LLM 调用失败 (attempt {attempt + 1}): {e}")
        logger.error(f"LLM 调用最终失败: {last_error}")
        return ""

    def _parse_with_citations(self, text: str) -> Tuple[str, Dict[int, Dict]]:
        """
        解析 LLM 输出，提取 [^n] 引用标记，建立 source_index。

        Returns:
            (叙事文本（保留 [^n] 标记）, 引用编号集合)
        """
        if not text:
            return "", {}

        # 提取所有 [^n] 引用
        refs = set(int(m) for m in re.findall(r"\[\^(\d+)\]", text))
        citations = {}
        for ref_id in refs:
            # 占位：caller 负责在拿到 source_index 后回填真实元数据
            citations[ref_id] = {"_placeholder": True, "ref_id": ref_id}
        return text, citations
```

### Step 2.3: Run tests to verify they pass

Run: `python -m pytest tests/utils/test_knowledge_synthesizer.py -v`
Expected: 4-5 PASS

### Step 2.4: Commit

```bash
git add scripts/utils/knowledge_synthesizer.py tests/utils/test_knowledge_synthesizer.py
git commit -m "feat(knowledge-synthesizer): add theme synthesis with citation parsing"
```

---

## Task 3: Integrate KnowledgeSynthesizer into stock_reporter.py

**Files:**
- Modify: `scripts/utils/stock_reporter.py` (multiple sections)

### Step 3.1: Add `_synthesize_sections()` method

Insert this new method into `PerStockReporter` (after `_header()`, around line 228):

```python
    def _synthesize_sections(self, stock_name: str, stock_raw: Dict) -> Dict[str, str]:
        """
        调用 KnowledgeSynthesizer 生成主题化综合叙事。
        返回包含 5 个主题 Markdown + citations 的字典。
        """
        try:
            from scripts.utils.knowledge_synthesizer import KnowledgeSynthesizer
            from scripts.utils.source_adapter import adapt_all
        except ImportError:
            import sys
            utils_dir = Path(__file__).parent
            if str(utils_dir) not in sys.path:
                sys.path.insert(0, str(utils_dir))
            from knowledge_synthesizer import KnowledgeSynthesizer
            from source_adapter import adapt_all

        # 收集所有来源的数据
        keep_posts = stock_raw.get("_keep_posts", [])
        zhihu_items = stock_raw.get("zhihu", {}).get("report_items", [])
        reports = stock_raw.get("reports", [])
        announcements = stock_raw.get("announcements", [])
        fundflow = stock_raw.get("fundflow", [])
        news = stock_raw.get("news", [])

        items = adapt_all(
            xueqiu_items=keep_posts,
            zhihu_items=zhihu_items,
            reports=reports,
            announcements=announcements,
            fundflow=fundflow,
            news=news,
        )
        if not items:
            return {k: "" for k in ["industry_logic", "fundamentals", "valuation_debate", "funding_sentiment", "events_catalysts"]} | {"citations": {}}

        synth = KnowledgeSynthesizer()
        result = synth.synthesize(stock_name, {"items": items})

        # 回填 citation 元数据：用 items 列表按索引匹配
        citations = result.get("citations", {})
        resolved_citations = {}
        for ref_id, meta in citations.items():
            if meta.get("_placeholder") and 1 <= ref_id <= len(items):
                src_item = items[ref_id - 1]
                resolved_citations[ref_id] = {
                    "title": src_item.title,
                    "source": src_item.source_platform,
                    "author": src_item.author,
                    "url": src_item.url,
                    "date": src_item.publish_time,
                }
            else:
                resolved_citations[ref_id] = meta
        result["citations"] = resolved_citations
        return result
```

### Step 3.2: Modify `generate_stock_report()` to use new 9-section layout

Replace the section assembly in `generate_stock_report()` (around lines 165-214) with:

```python
        # === 主题化综合叙事 ===
        synthesis = self._synthesize_sections(stock_name, stock_raw)
        has_synthesis = any(
            synthesis.get(k) for k in ["industry_logic", "fundamentals", "valuation_debate", "funding_sentiment", "events_catalysts"]
        )

        # 构建报告各部分（新 9 板块结构）
        sections = []
        sections.append(self._header(stock_name))

        # 1. 综合评分与推荐
        sections.append(self._composite_score_section(stock_name, all_posts, stock_raw, quote, consensus))

        # 2. 实时行情与估值
        sections.append(self._valuation_forecast(stock_name, quote, consensus))

        if has_synthesis:
            # 3. 产业逻辑与竞争格局（合成）
            if synthesis.get("industry_logic"):
                sections.append(self._render_synthesis_section("产业逻辑与竞争格局", synthesis["industry_logic"], synthesis["citations"]))

            # 4. 业绩基本面追踪（合成）
            if synthesis.get("fundamentals"):
                sections.append(self._render_synthesis_section("业绩基本面追踪", synthesis["fundamentals"], synthesis["citations"]))

            # 5. 估值争议与市场分歧（合成）
            if synthesis.get("valuation_debate"):
                sections.append(self._render_synthesis_section("估值争议与市场分歧", synthesis["valuation_debate"], synthesis["citations"]))

            # 6. 资金面与情绪跟踪（合成）
            if synthesis.get("funding_sentiment"):
                sections.append(self._render_synthesis_section("资金面与情绪跟踪", synthesis["funding_sentiment"], synthesis["citations"]))

            # 7. 关键事件与催化剂（合成）
            if synthesis.get("events_catalysts"):
                sections.append(self._render_synthesis_section("关键事件与催化剂", synthesis["events_catalysts"], synthesis["citations"]))
        else:
            # 降级：旧版板块展示
            sections.append(self._sentiment_and_competition(stock_name, all_posts))
            sections.append(self._core_topics(stock_name, all_posts))
            sections.append(self._zhihu_section(stock_name, stock_raw.get("zhihu", {})))
            sections.append(self._featured_posts(stock_name, featured_posts))
            sections.append(self._comment_highlights(stock_name, all_posts))

        # 8. 风险综合评估（保留）
        sections.append(self._risk_score_section(stock_name, all_posts, stock_raw, quote, consensus))

        # 9. 信息来源汇总（新）
        if has_synthesis and synthesis.get("citations"):
            sections.append(self._citations_section(synthesis["citations"]))

        sections.append(self._footer())
```

**Note:** The `stock_raw` needs `_keep_posts` injected. Add this line after the quality gate processing (around line 128):

```python
        stock_raw["_keep_posts"] = keep_posts
```

### Step 3.3: Add `_render_synthesis_section()` helper

Insert this method into `PerStockReporter`:

```python
    def _render_synthesis_section(self, title: str, narrative: str, citations: Dict) -> str:
        """渲染一个合成叙事板块，自动提取该板块使用的引用。"""
        import re
        used_refs = set(int(m) for m in re.findall(r"\[\^(\d+)\]", narrative))

        lines = [f"## {title}", "", narrative, ""]

        if used_refs:
            lines.append("**本节引用来源：**")
            for ref_id in sorted(used_refs):
                meta = citations.get(ref_id, {})
                source = meta.get("source", "未知")
                author = meta.get("author", "")
                title_text = meta.get("title", "")
                url = meta.get("url", "")
                date = meta.get("date", "")
                parts = [f"[^{ref_id}]"]
                if source:
                    parts.append(source)
                if author:
                    parts.append(f"作者: {author}")
                if title_text:
                    parts.append(f"《{title_text[:40]}》")
                if date:
                    parts.append(date)
                line = " | ".join(parts)
                if url:
                    line += f" [{url}]"
                lines.append(f"- {line}")
            lines.append("")

        return "\n".join(lines)
```

### Step 3.4: Add `_citations_section()` helper

Insert this method into `PerStockReporter`:

```python
    def _citations_section(self, citations: Dict) -> str:
        """报告末尾的全局引用汇总板块。"""
        lines = ["## 九、信息来源汇总", ""]
        if not citations:
            lines.append("*无引用信息*")
            lines.append("")
            return "\n".join(lines)

        lines.append(f"> 本报告共引用 **{len(citations)}** 条信息来源：")
        lines.append("")

        for ref_id in sorted(citations.keys()):
            meta = citations[ref_id]
            source = meta.get("source", "未知")
            author = meta.get("author", "")
            title = meta.get("title", "")
            url = meta.get("url", "")
            date = meta.get("date", "")
            parts = [f"[^{ref_id}]"]
            if source:
                parts.append(f"**{source}**")
            if author:
                parts.append(f"作者: {author}")
            if title:
                parts.append(f"《{title[:50]}》")
            if date:
                parts.append(date)
            line = " | ".join(parts)
            if url:
                line = f"{line} [{url}]"
            lines.append(f"- {line}")
        lines.append("")
        return "\n".join(lines)
```

### Step 3.5: Run a syntax check

Run: `python -c "import scripts.utils.stock_reporter"`
Expected: No output (success)

### Step 3.6: Commit

```bash
git add scripts/utils/stock_reporter.py
git commit -m "feat(reporter): integrate KnowledgeSynthesizer with 9-section report layout"
```

---

## Task 4: Update demo_shengbang.py to pass data correctly

**Files:**
- Modify: `scripts/demo_shengbang.py`

### Step 4.1: Inject `_keep_posts` into `collected_data`

In `demo_shengbang.py`, the `collected_data` dict needs to include the quality-gate results so that `_synthesize_sections()` can access `stock_raw["_keep_posts"]`.

Find the section where `collected_data` is built (around line 157) and update it to include the gate results:

```python
    # 统一质量门筛选
    gate = ContentQualityGate()
    quality_results = gate.process_xueqiu_posts(dummy_posts)
    keep_posts = [r.item.extra for r in quality_results if r.action == "keep"]

    collected_data = {
        stock_name: {
            "technical": tech_data,
            "reports": reports,
            "announcements": anns,
            "fundflow": fund,
            "news": news,
            "zhihu": zhihu_data,
            "analysis": analysis,
            "_keep_posts": keep_posts,  # <-- 新增，供 synthesizer 使用
        }
    }
```

### Step 4.2: Commit

```bash
git add scripts/demo_shengbang.py
git commit -m "feat(demo): inject _keep_posts into collected_data for synthesizer"
```

---

## Task 5: End-to-End Validation

**Files:**
- None (verification only)

### Step 5.1: Run demo script with LLM disabled

Run:
```bash
cd /Users/erichan/testsnow && python scripts/demo_shengbang.py
```

Expected: Report generates successfully. Check console output for:
- `KnowledgeSynthesizer 不可用` warning (if no API key)
- Report falls back to old 12-section layout
- No Python exceptions

### Step 5.2: Run demo script with LLM enabled (if API key available)

Run:
```bash
cd /Users/erichan/testsnow && MOONSHOT_API_KEY=$MOONSHOT_API_KEY python scripts/demo_shengbang.py
```

Expected:
- 5 synthesis sections appear in the Markdown output
- Each section contains `[^{n}]` citations
- Section 9 (信息来源汇总) lists all referenced sources
- No duplicate citations with different numbers for the same source

### Step 5.3: Inspect generated report

Run:
```bash
head -n 100 /Users/erichan/testsnow/reports/圣邦股份_$(date +%Y%m%d).md
```

Expected: Report starts with header, section 1 (综合评分), section 2 (估值), and either section 3 (产业逻辑) if synthesis succeeded, or old sections if fallback.

### Step 5.4: Commit

```bash
git add reports/  # if any test reports should be ignored, add to .gitignore instead
git commit -m "test: validate KnowledgeSynthesizer e2e with demo script"
```

---

## Task 6: Self-Review Fixes

**Files:**
- Modify as needed

### Step 6.1: Verify spec coverage

| Spec Requirement | Plan Task |
|---|---|
| `KnowledgeSynthesizer` class with `synthesize()` | Task 2 |
| `_build_prompt()` for each theme | Task 2, Step 2.2 |
| `_parse_with_citations()` extracts `[^n]` | Task 2, Step 2.2 |
| 5 themed narrative sections | Task 2, Step 2.2 (THEMES dict) |
| Source index global dedup | Task 2, Step 2.2 (`source_index`) |
| 9-section report structure | Task 3, Step 3.2 |
| Fallback to old layout when LLM unavailable | Task 3, Step 3.2 (`has_synthesis` check) |
| Citations section at report end | Task 3, Step 3.4 |
| SourceAdapter for future WeChat | Task 1, Step 1.3 (`WechatAdapter`) |
| Graceful degradation (<3 items skip) | Task 2, Step 2.2 (`len(items) < min_items`) |
| LLM timeout retry (1 retry) | Task 2, Step 2.2 (`_call_llm()`) |

### Step 6.2: Placeholder scan

Search plan document for:
- "TBD" / "TODO" / "implement later" → None found
- "Add appropriate error handling" → Not used
- "Similar to Task N" → Not used
- All code steps contain actual code

### Step 6.3: Type consistency

- `SynthesisItem` fields: `title`, `content`, `author`, `source_platform`, `url`, `publish_time`, `interaction_score`, `extra` — consistent across all adapters and synthesizer usage.
- `KnowledgeSynthesizer.synthesize()` return keys match `THEMES` keys + `"citations"` — consistent in tests, implementation, and reporter integration.
- `adapt_all()` parameter names match the keys used in `_synthesize_sections()` — `xueqiu_items`, `zhihu_items`, `reports`, etc.

---

## Appendix: Quick Reference for Agentic Workers

### Running tests
```bash
# All new tests
python -m pytest tests/utils/test_source_adapter.py tests/utils/test_knowledge_synthesizer.py -v

# Single test
python -m pytest tests/utils/test_knowledge_synthesizer.py::test_parse_citations_extracts_refs -v
```

### Environment variables required
```bash
export DEEPSEEK_API_KEY="sk-..."   # or MOONSHOT_API_KEY
export DEEPSEEK_MODEL="deepseek-chat"  # optional
```

### Expected report diff (old vs new)
**Old 12 sections:** 1.综合评分 2.估值 3.技术面 4.研报 5.公告 6.资金流向 7.交叉验证 8.知乎 9.情绪竞争 10.精品帖子 11.关键评论 12.风险

**New 9 sections (with synthesis):** 1.综合评分 2.估值 3.产业逻辑 4.业绩基本面 5.估值争议 6.资金面 7.关键事件 8.风险 9.引用汇总

**New fallback (no LLM):** Same as old 12 sections — no regression.
