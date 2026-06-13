"""
KnowledgeSynthesizer: 主题化综合叙事生成器

将多源信息按主题维度合成连贯叙事，要求 LLM 输出带 [^n] 引用的 Markdown 段落。
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    from .source_adapter import SynthesisItem
except ImportError:
    from source_adapter import SynthesisItem

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
        "1. 写一段 400-600 字的连贯分析，不要分点罗列\n"
        "2. 每个关键数字和事实后面标注 [^n] 引用\n"
        "3. 必须覆盖：\n"
        "   - 行业供需格局与涨价/降价周期判断\n"
        "   - 主要竞争对手动态：横向对比{stock_name}与竞争对手（思瑞浦、杰华特、纳芯微、艾为电子）在产品料号数、车规级布局、研发费用、毛利率、核心客户等维度的差异\n"
        "   - 国产替代进展与市场份额变化\n"
        "4. 最后给出该赛道未来 6-12 个月的关键趋势判断\n"
        "5. 不要编造数据，只能基于以下信息\n"
        "6. 不要在正文中重复展开具体财务数字（如营收、毛利率等），仅在需要支撑论点时用一句话引用，并标注 [^n]。\n"
    ),
    "fundamentals": (
        "你是资深半导体行业分析师。请基于以下多源信息，对{stock_name}的业绩基本面进行追踪分析。\n\n"
        "要求：\n"
        "1. 写一段 300-500 字的连贯分析，不要分点罗列\n"
        "2. 每个关键数字和事实后面标注 [^n] 引用\n"
        "3. 必须覆盖：最新季度营收/利润变化、毛利率走势、订单/客户动态、管理层指引\n"
        "4. 最后给出业绩预期修正方向（上调/下调/维持）\n"
        "5. 不要编造数据，只能基于以下信息\n"
        "6. 不要在正文中重复展开具体财务数字（如营收、毛利率等），仅在需要支撑论点时用一句话引用，并标注 [^n]。\n"
    ),
    "valuation_debate": (
        "你是资深半导体行业分析师。请基于以下多源信息，对{stock_name}的估值争议进行综合解读。\n\n"
        "要求：\n"
        "1. 写一段 300-500 字的连贯分析，不要分点罗列\n"
        "2. 每个关键数字和事实后面标注 [^n] 引用\n"
        "3. 必须覆盖：看多方的核心论据、看空方的核心论据、双方分歧的关键变量\n"
        "4. 最后给出一个中性的综合判断\n"
        "5. 不要编造数据，只能基于以下信息\n"
        "6. 不要在正文中重复展开具体财务数字（如营收、毛利率等），仅在需要支撑论点时用一句话引用，并标注 [^n]。\n"
    ),
    "funding_sentiment": (
        "你是资深半导体行业分析师。请基于以下多源信息，对{stock_name}的资金面与情绪进行跟踪分析。\n\n"
        "要求：\n"
        "1. 写一段 250-400 字的连贯分析，不要分点罗列\n"
        "2. 每个关键数字和事实后面标注 [^n] 引用\n"
        "3. 必须覆盖：主力资金动向、散户情绪指标、北向资金/机构持仓变化、融资余额变化\n"
        "4. 最后给出资金面对股价的短期影响判断\n"
        "5. 不要编造数据，只能基于以下信息\n"
        "6. 不要在正文中重复展开具体财务数字（如营收、毛利率等），仅在需要支撑论点时用一句话引用，并标注 [^n]。\n"
    ),
    "events_catalysts": (
        "你是资深半导体行业分析师。请基于以下多源信息，梳理{stock_name}近期的关键事件与催化剂。\n\n"
        "要求：\n"
        "1. 写一段 250-400 字的连贯分析，不要分点罗列\n"
        "2. 每个关键数字和事实后面标注 [^n] 引用\n"
        "3. 必须覆盖：已落地的利好/利空、即将发生的事件、政策/行业催化\n"
        "4. 最后给出下一个值得关注的催化剂时间点\n"
        "5. 不要编造数据，只能基于以下信息\n"
        "6. 不要在正文中重复展开具体财务数字（如营收、毛利率等），仅在需要支撑论点时用一句话引用，并标注 [^n]。\n"
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
                    如果环境变量不存在则保持 None，便于测试隔离。
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
        claim_verification_context = all_data.get("claim_verification_context")
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
                    stock_name, theme_key, items, previous_narratives, claim_verification_context
                )
                result[theme_key] = narrative
                # 合并引用（全局去重）
                for cid, cdata in citations.items():
                    if cid not in self.source_index:
                        self.source_index[cid] = cdata
            except Exception as e:
                logger.warning(f"[{stock_name}] {theme_title} 合成失败: {e}")
                result[theme_key] = ""

        # 提取核心事实基座
        if self.client and any(result.get(k) for k in THEMES):
            try:
                narratives = {k: result[k] for k in THEMES if result.get(k)}
                result["core_facts"] = self.extract_core_facts(stock_name, narratives)
            except Exception as e:
                logger.warning(f"[{stock_name}] 核心事实提取失败: {e}")
                result["core_facts"] = []
        else:
            result["core_facts"] = []

        result["citations"] = dict(self.source_index)
        return result

    def _synthesize_theme(
        self,
        stock_name: str,
        theme_key: str,
        items: List[SynthesisItem],
        previous_narratives: Dict[str, str] = None,
        claim_verification_context: Dict[str, Any] = None,
    ) -> Tuple[str, Dict[int, Dict]]:
        """合成单个主题，返回 (叙事文本, 该主题使用的引用字典)"""
        prompt = self._build_prompt(stock_name, theme_key, items, previous_narratives, claim_verification_context)
        response_text = self._call_llm(prompt)
        return self._parse_with_citations(response_text)

    def _build_prompt(
        self,
        stock_name: str,
        theme_key: str,
        items: List[SynthesisItem],
        previous_narratives: Dict[str, str] = None,
        claim_verification_context: Dict[str, Any] = None,
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

        # Append optional claim verification context after numbered sources.
        if claim_verification_context:
            appendix = self._format_claim_verification_context(claim_verification_context)
            if appendix:
                prompt += "\n\n---\n\n" + appendix

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

    def _format_claim_verification_context(self, context: Dict[str, Any]) -> str:
        """Render a guarded, non-citable claim verification appendix for prompts."""
        if not context or not context.get("enabled"):
            return ""

        counts = context.get("counts", {})
        lines = [
            "Claim Verification Context（以下不是新的引用来源）",
            "",
            "重要约束：",
            "- 以下内容不是新的引用来源，不能用 [^n] 引用，也不能单独作为事实写入正文。",
            "- 它只用于判断社区观点的可信度，帮助你决定如何强调或弱化某些信息。",
            "",
            f"统计：高信用声明 {counts.get('high_credit_claims', 0)} 条，低信用声明 {counts.get('low_credit_claims', 0)} 条，"
            f"已验证 {counts.get('verified', 0)} 条，中等支持 {counts.get('supported', 0)} 条，"
            f"未验证 {counts.get('unverified', 0)} 条，需复核 {counts.get('needs_review', 0)} 条。",
            "",
            "可信度使用规则：",
            "- verified：只有当同一事实也出现在上方编号信息来源中时，才可作为重点线索使用，并必须引用上方编号来源。",
            "- supported：可描述为“有中等信用来源支持的线索”，但不得写成已确认事实。",
            "- unverified：只能作为“待验证市场观点/社区讨论”，不得进入核心事实基座。",
            "- needs_review：仅提示存在相关信息，但当前证据不足，不得写入正文。",
            "",
        ]

        def _render_bucket(label: str, rows: List[Dict[str, Any]]) -> List[str]:
            if not rows:
                return []
            out = [f"{label}："]
            for row in rows:
                text = row.get("claim_text", "")
                action = row.get("action", "")
                confidence = row.get("confidence")
                reason = row.get("reason", "")
                titles = row.get("verified_by_titles", [])
                parts = [f"- [{action}] {text}"]
                if confidence is not None:
                    parts.append(f"（置信度 {confidence}）")
                if titles:
                    parts.append(f"[依据标题: {' / '.join(titles)}]")
                if reason:
                    parts.append(f"[原因: {reason}]")
                out.append(" ".join(parts))
            return out

        lines.extend(_render_bucket("已验证声明", context.get("verified_claims", [])))
        if context.get("supported_claims"):
            lines.append("")
        lines.extend(_render_bucket("中等支持声明", context.get("supported_claims", [])))
        if context.get("needs_review_claims"):
            lines.append("")
        lines.extend(_render_bucket("需复核声明", context.get("needs_review_claims", [])))
        if context.get("unverified_claims"):
            lines.append("")
        lines.extend(_render_bucket("未验证声明", context.get("unverified_claims", [])))

        return "\n".join(lines)

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

    def extract_core_facts(
        self,
        stock_name: str,
        narratives: Dict[str, str],
    ) -> List[Dict]:
        """
        从已合成的主题叙事中提取核心事实基座。

        Args:
            stock_name: 股票名称
            narratives: theme_key -> 叙事文本

        Returns:
            [{"fact_id": int, "fact": str, "data": str, "confidence": str}, ...]
        """
        if not self.client:
            return []

        narrative_text = "\n\n".join(
            f"【{THEMES.get(k, (k, 0))[0]}】\n{v}"
            for k, v in narratives.items() if v
        )

        prompt = (
            f"你是资深财经数据编辑。请从以下关于{stock_name}的分析文本中，提取8-12条核心事实。"
            "每条事实必须包含：事实陈述、支撑数据、置信度（高/中/低）。"
            "只提取客观事实和数据，不要提取观点、判断或预测。"
            "去重：同一事实在不同段落中出现时只保留一次。"
            "\n\n输出格式（JSON）："
            '\n[\n  {"fact_id": 1, "fact": "2025年营收", "data": "8.22亿元，同比+73.4%", "confidence": "高"},\n  ...\n]'
            "\n\n分析文本：\n"
            f"{narrative_text[:3000]}"
        )

        try:
            response_text = self._call_llm(prompt)
            if not response_text:
                return []

            # 提取 JSON 块（处理 markdown code block）
            text = response_text
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            facts = json.loads(text)
            if not isinstance(facts, list):
                return []

            normalized = []
            for i, f in enumerate(facts, 1):
                if isinstance(f, dict) and f.get("fact"):
                    normalized.append({
                        "fact_id": f.get("fact_id", i),
                        "fact": str(f.get("fact", "")),
                        "data": str(f.get("data", "")),
                        "confidence": str(f.get("confidence", "中")),
                    })
            return normalized
        except json.JSONDecodeError as e:
            logger.warning(f"[{stock_name}] 核心事实 JSON 解析失败: {e}")
            return []
        except Exception as e:
            logger.warning(f"[{stock_name}] 核心事实提取解析失败: {e}")
            return []
