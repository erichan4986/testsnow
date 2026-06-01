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
            if len(items) < min_items:
                logger.info(f"[{stock_name}] {theme_title}: 信息不足 ({len(items)} < {min_items})，跳过合成")
                result[theme_key] = ""
                continue

            if not self.client:
                result[theme_key] = ""
                continue

            try:
                # 收集已生成的前置板块叙事，避免跨板块重复展开
                previous_narratives = {
                    k: v for k, v in result.items()
                    if v and k in THEMES
                }
                narrative, citations = self._synthesize_theme(
                    stock_name, theme_key, items, previous_narratives
                )
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
        self,
        stock_name: str,
        theme_key: str,
        items: List[SynthesisItem],
        previous_narratives: Dict[str, str] = None,
    ) -> Tuple[str, Dict[int, Dict]]:
        """合成单个主题，返回 (叙事文本, 该主题使用的引用字典)"""
        prompt = self._build_prompt(stock_name, theme_key, items, previous_narratives)
        response_text = self._call_llm(prompt)
        return self._parse_with_citations(response_text)

    def _build_prompt(
        self,
        stock_name: str,
        theme_key: str,
        items: List[SynthesisItem],
        previous_narratives: Dict[str, str] = None,
    ) -> str:
        """为特定主题构建 LLM prompt。"""
        prefix_template = THEME_PROMPT_PREFIX.get(theme_key, THEMES["industry_logic"][0])
        try:
            prefix = prefix_template.format(stock_name=stock_name)
        except KeyError:
            prefix = prefix_template

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

        prompt = prefix + "\n\n信息来源：\n" + "\n".join(source_lines)

        # 追加前置板块上下文，避免跨板块重复展开
        if previous_narratives:
            prompt += "\n\n---\n\n注意：以下内容是本报告已生成的其他板块分析。"
            prompt += "请确保本板块不重复展开已在其他板块中详细讨论过的事实（如季度收入、毛利率、具体订单数字等）。"
            prompt += "仅在需要支撑本板块论点时，用一句话简要引用，并继续标注 [^n] 引用。\n\n"
            for prev_key, prev_text in previous_narratives.items():
                prev_title = THEMES.get(prev_key, (prev_key, 0))[0]
                # 截取前 300 字作为上下文，控制 prompt 长度
                truncated = prev_text[:300] + "..." if len(prev_text) > 300 else prev_text
                prompt += f"【{prev_title}】\n{truncated}\n\n"

        return prompt

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
        解析 LLM 输出，提取 [^n] 引用标记。

        Returns:
            (叙事文本（保留 [^n] 标记）, 引用编号集合)
        """
        if not text:
            return "", {}

        # 提取所有 [^n] 引用
        refs = set(int(m) for m in re.findall(r"\[\^(\d+)\]", text))
        citations = {}
        for ref_id in refs:
            # 占位：caller 负责回填真实元数据
            citations[ref_id] = {"_placeholder": True, "ref_id": ref_id}
        return text, citations
