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
    from .deep_analysis_topic_ownership import (
        format_previous_topic_ledger,
        format_topic_ownership_contract,
    )
    from .source_adapter import SynthesisItem
    from .synthesis_credit import (
        credit_usage_rules_text,
        format_synthesis_source_line,
        format_claim_verification_appendix,
        sanitize_citation_markers,
    )
except ImportError:
    from deep_analysis_topic_ownership import (
        format_previous_topic_ledger,
        format_topic_ownership_contract,
    )
    from source_adapter import SynthesisItem
    from synthesis_credit import (
        credit_usage_rules_text,
        format_synthesis_source_line,
        format_claim_verification_appendix,
        sanitize_citation_markers,
    )

logger = logging.getLogger(__name__)

# 主题定义: 主题名 -> (显示标题, 最低所需条目数)
THEMES = {
    "industry_logic": ("产业逻辑与竞争格局", 3),
    "fundamentals": ("业绩基本面追踪", 3),
    "valuation_debate": ("估值争议与市场分歧", 3),
    "funding_sentiment": ("资金面与情绪跟踪", 3),
    "events_catalysts": ("关键事件与催化剂", 3),
}

MAX_SYNTHESIS_PARAGRAPH_CHARS = 260

COMMON_PROSE_CONTRACT = (
    "通用行文结构约束：\n"
    "- 不要写成一整段长文；每段不超过260个中文字符，尽量每句不超过110字。\n"
    "- 优先使用 Markdown 表格承载变量、证据、推导和验证点；表格单元格里的关键事实也必须带 [^n] 引用。\n"
    "- 引用格式必须写成 [^1]、[^2]，不要写成 [1]、[2]。\n"
    "- 避免模板化连接词，如“综合来看”“展望未来”“与此同时”“结构性繁荣”；直接写变量、证据和推导。\n"
    "- 直接输出正文，不要写“好的，作为资深分析师”“以下是分析”等角色扮演套话。\n"
    "- 避免强确认词和强垄断表述；除非来源为公告/官方确认，否则使用“外部材料显示/研报认为/仍需跟踪”等审慎措辞。\n"
    "- 每个关键数字和事实后面标注 [^n] 引用；不要编造数据，只能基于以下信息。\n"
)

# 每个主题的 prompt 前缀
THEME_PROMPT_PREFIX = {
    "industry_logic": (
        "你是资深半导体行业分析师。请基于以下多源信息，对{stock_name}的产业逻辑与竞争格局进行综合解读。\n\n"
        "要求：\n"
        "1. 只写产业需求、技术路线、供应链位置、竞争格局与直接竞争对手。\n"
        "2. 如有3个以上比较维度，优先使用 Markdown 表格：| 维度 | 公司位置 | 对手/行业状态 | 判断 | 来源 |。\n"
        "3. 不要重复展开4.2应写的季度营收、利润、毛利率、订单兑现；不要写4.3应写的资金面、融资盘、催化剂时间线。\n"
        "4. 对未来趋势只写产业层面的1-2个验证变量，不写交易结论。\n"
        f"{COMMON_PROSE_CONTRACT}"
    ),
    "fundamentals": (
        "你是资深半导体行业分析师。请基于以下多源信息，对{stock_name}的业绩基本面进行追踪分析。\n\n"
        "要求：\n"
        "1. 只写营收/利润/毛利率/费用率/订单客户/管理层指引如何影响业绩路径。\n"
        "2. 优先使用 Markdown 表格：| 变量 | 当前证据 | 对业绩路径的含义 | 需跟踪 | 来源 |。\n"
        "3. 不要重复展开4.1的行业背景、技术路线和竞争格局；不要写4.3的资金面、融资余额、催化剂时间线。\n"
        "4. 结论只能写业绩预期修正方向（上调/下调/维持）及条件，不写投资建议。\n"
        f"{COMMON_PROSE_CONTRACT}"
    ),
    "valuation_debate": (
        "你是资深半导体行业分析师。请基于以下多源信息，对{stock_name}的估值争议进行综合解读。\n\n"
        "要求：\n"
        "1. 只写估值多空分歧、关键验证变量和情景分歧，不写交易建议。\n"
        "2. 优先使用 Markdown 表格：| 多方观点 | 依据 | 反方约束 | 关键验证点 | 来源 |。\n"
        "3. 不要重复展开4.1的产业技术背景；不要重复4.2的财务数字，只在支撑估值分歧时一句话引用。\n"
        "4. 最后给出中性判断：当前估值依赖哪些变量兑现。\n"
        f"{COMMON_PROSE_CONTRACT}"
    ),
    "funding_sentiment": (
        "你是资深半导体行业分析师。请基于以下多源信息，对{stock_name}的资金面与情绪进行跟踪分析。\n\n"
        "要求：\n"
        "1. 只写主力资金、机构/北向、融资余额、市场情绪或持仓结构变化。\n"
        "2. 如有3个以上资金变量，优先使用 Markdown 表格：| 资金变量 | 当前证据 | 对短期交易结构的含义 | 需跟踪 | 来源 |。\n"
        "3. 不要重复展开4.1的技术路线和产业背景；不要重复4.2的业绩路径，除非一句话解释资金反应的原因。\n"
        "4. 最后只写资金面对短期波动的影响判断，不写买卖建议。\n"
        f"{COMMON_PROSE_CONTRACT}"
    ),
    "events_catalysts": (
        "你是资深半导体行业分析师。请基于以下多源信息，梳理{stock_name}近期的关键事件与催化剂。\n\n"
        "要求：\n"
        "1. 只写已发生事件、后续时间点、政策/行业催化和验证指标。\n"
        "2. 优先使用 Markdown 表格：| 时间点 | 催化剂/事件 | 当前状态 | 验证指标 | 来源 |。\n"
        "3. 不要重复展开4.1的产业技术背景；不要重复4.2的完整业绩路径；不要把社媒传闻写成已确认事件。\n"
        "4. 最后给出下一个值得关注的催化剂时间点及其验证指标。\n"
        f"{COMMON_PROSE_CONTRACT}"
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
        peer_comparison_material = all_data.get("peer_comparison_material")
        if not items:
            logger.warning(f"[{stock_name}] 无内容可供合成")
            return {k: "" for k in THEMES} | {"citations": {}}

        # 重置引用索引
        self.source_index = {}
        self._counter = 0

        result = {}
        for theme_key, (theme_title, min_items) in THEMES.items():
            theme_items = self._filter_items_for_theme(theme_key, items)
            if len(theme_items) < min_items:
                logger.info(f"[{stock_name}] {theme_title}: 信息不足 ({len(theme_items)} < {min_items})，跳过合成")
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
                    stock_name, theme_key, theme_items,
                    previous_narratives, claim_verification_context,
                    peer_comparison_material,
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
        peer_comparison_material: Dict[str, Any] = None,
    ) -> Tuple[str, Dict[int, Dict]]:
        """合成单个主题，返回 (叙事文本, 该主题使用的引用字典)"""
        prompt = self._build_prompt(
            stock_name, theme_key, items,
            previous_narratives, claim_verification_context,
            peer_comparison_material,
        )
        response_text = self._call_llm(prompt)
        return self._parse_with_citations(response_text)

    def _build_prompt(
        self,
        stock_name: str,
        theme_key: str,
        items: List[SynthesisItem],
        previous_narratives: Dict[str, str] = None,
        claim_verification_context: Dict[str, Any] = None,
        peer_comparison_material: Dict[str, Any] = None,
    ) -> str:
        """为特定主题构建 LLM prompt。"""
        prefix_template = THEME_PROMPT_PREFIX.get(theme_key, THEMES["industry_logic"][0])
        try:
            prefix = prefix_template.format(stock_name=stock_name)
        except KeyError:
            prefix = prefix_template

        source_lines = []
        theme_items = self._filter_items_for_theme(theme_key, items)
        for i, item in enumerate(theme_items):
            source_lines.append(format_synthesis_source_line(i + 1, item))

        rules = credit_usage_rules_text()
        ownership_contract = format_topic_ownership_contract(theme_key)
        prompt_parts = [prefix]
        if ownership_contract:
            prompt_parts.append(ownership_contract)
        prompt_parts.extend([rules, "信息来源：\n" + "\n".join(source_lines)])
        prompt = "\n\n".join(prompt_parts)

        # Append peer comparison appendix for 4.1/4.2 themes only.
        if peer_comparison_material and theme_key in {"industry_logic", "fundamentals", "valuation_debate"}:
            peer_appendix = self._format_peer_appendix(peer_comparison_material, theme_key)
            if peer_appendix:
                prompt += "\n\n---\n\n" + peer_appendix

        # Append optional claim verification context after numbered sources.
        if claim_verification_context:
            appendix = self._format_claim_verification_context(claim_verification_context)
            if appendix:
                prompt += "\n\n---\n\n" + appendix

        # 追加前置板块上下文，避免跨板块重复展开
        if previous_narratives:
            theme_titles = {key: value[0] for key, value in THEMES.items()}
            ledger = format_previous_topic_ledger(previous_narratives, theme_titles)
            if ledger:
                prompt += "\n\n---\n\n" + ledger + "\n"

        return prompt

    @staticmethod
    def _format_peer_appendix(peer_comparison_material: Dict[str, Any], theme_key: str) -> str:
        """Build compact non-citable peer comparison appendix for 4.1/4.2 theme prompts."""
        try:
            from .peer_comparison_material import filter_peer_rows_for_prompt
        except ImportError:
            from peer_comparison_material import filter_peer_rows_for_prompt

        filtered = filter_peer_rows_for_prompt(peer_comparison_material)
        rows = filtered.get("rows", [])
        if not rows:
            return ""

        # Per-theme row caps
        max_rows = {"industry_logic": 4, "fundamentals": 3, "valuation_debate": 3}
        limit = max_rows.get(theme_key, 0)

        # For valuation_debate, prefer 估值水平 rows first
        if theme_key == "valuation_debate":
            valuation_rows = [r for r in rows if r.get("dimension") == "估值水平"]
            other_rows = [r for r in rows if r.get("dimension") != "估值水平"]
            theme_rows = valuation_rows[:limit]
            if len(theme_rows) < limit:
                theme_rows.extend(other_rows[:limit - len(theme_rows)])
        else:
            theme_rows = rows[:limit]

        if not theme_rows:
            return ""

        lines = [
            "同行对比材料（正式/指标来源，非新增引用）",
            "",
            "使用规则：",
            "- 只能基于 claim_eligible 行写\"高于/低于/接近/优于/弱于\"等相对判断。",
            "- context_only 行只能写成\"后续可跟踪的对比线索\"，不能写成已确认优劣。",
            "- 不得把同行材料写入 4.3 资金面/催化剂。",
            "- 不得引用雪球/知乎/微信/精选外部来支撑 4.1/4.2 同行结论。",
            "- 同行材料不是新的引用来源，不得生成新的 [^n] 引用编号。",
            "",
        ]

        for row in theme_rows:
            usage = row.get("usage", "audit_only")
            dim = row.get("dimension", "")
            target = row.get("target", "")
            peer = row.get("peer", "")
            metric = row.get("metric", "")
            conf = row.get("confidence", 0)
            refs = "; ".join(row.get("source_refs", []))

            if usage == "claim_eligible" and row.get("comparison"):
                comparison = row.get("comparison", "")
                target_val = row.get("target_value", "")
                peer_val = row.get("peer_value", "")
                lines.append(
                    f"- {dim} | {target} vs {peer} | {metric}: {target_val} vs {peer_val}"
                    f" | {comparison} | confidence={conf} | 来源: {refs}"
                )
            else:
                lines.append(
                    f"- {dim} | peer={peer} | metric={metric} | context_only"
                    f" | confidence={conf} | 来源: {refs}"
                )

        return "\n".join(lines)

    @staticmethod
    def _filter_items_for_theme(theme_key: str, items: List[SynthesisItem]) -> List[SynthesisItem]:
        """Apply deterministic section eligibility before LLM prompt construction."""
        if theme_key not in {"funding_sentiment", "events_catalysts"}:
            return items

        filtered: List[SynthesisItem] = []
        for item in items:
            extra = item.extra or {}
            allowed_sections = extra.get("allowed_sections")
            is_industry_news = (
                item.source_platform == "行业资讯"
                or extra.get("source_type") == "mainstream_media"
                or extra.get("source_domain") == "eastmoney.com"
            )
            if isinstance(allowed_sections, list):
                if "4.3" in {str(section) for section in allowed_sections}:
                    filtered.append(item)
                continue
            if is_industry_news:
                continue
            filtered.append(item)
        return filtered

    def _format_claim_verification_context(self, context: Dict[str, Any]) -> str:
        """Render a guarded, non-citable claim verification appendix for prompts."""
        return format_claim_verification_appendix(context)

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

        # Strip non-numeric markers such as [^supported] / [^needs_review]
        # before extracting numbered citations.
        text = sanitize_citation_markers(text)
        text = self._normalize_plain_numeric_citations(text)
        text = self._sanitize_theme_narrative(text)

        # 提取所有 [^n] 引用
        refs = set(int(m) for m in re.findall(r"\[\^(\d+)\]", text))
        citations = {}
        for ref_id in refs:
            # 占位：caller 负责回填真实元数据
            citations[ref_id] = {"_placeholder": True, "ref_id": ref_id}
        return text, citations

    @staticmethod
    def _normalize_plain_numeric_citations(text: str) -> str:
        """Convert LLM-emitted [n] source refs into the renderer's [^n] form."""
        if not isinstance(text, str):
            return text
        return re.sub(r"(?<!\^)\[(\d+)\]", r"[^\1]", text)

    def _sanitize_theme_narrative(self, text: str) -> str:
        """Deterministically normalize LLM theme output without changing facts.

        The sanitizer is intentionally conservative: it preserves Markdown
        tables/lists/headings verbatim, and only splits overlong prose
        paragraphs at sentence boundaries so citation markers stay attached to
        their original sentence.
        """
        text = self._strip_llm_role_preface(str(text or "").strip())
        blocks = re.split(r"\n\s*\n", text)
        sanitized_blocks = []
        for block in blocks:
            cleaned = block.strip()
            if not cleaned:
                continue
            if self._is_structured_markdown_block(cleaned):
                sanitized_blocks.append(cleaned)
                continue
            sanitized_blocks.extend(self._split_overlong_prose_block(cleaned))
        return "\n\n".join(sanitized_blocks).strip()

    @staticmethod
    def _strip_llm_role_preface(text: str) -> str:
        """Remove common assistant role prefaces without touching analysis text."""
        if not text:
            return ""
        patterns = [
            r"^\s*(?:好的，)?作为[^。！？\n]{0,80}(?:分析师|研究员)[^。！？\n]{0,160}[。！？]\s*",
            r"^\s*(?:以下是|下面是)[^。！？\n]{0,120}(?:分析|解读)[^。！？\n]{0,80}[。！？]\s*",
        ]
        cleaned = text
        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned, count=1)
        return cleaned.strip()

    @staticmethod
    def _is_structured_markdown_block(block: str) -> bool:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            return False
        return all(
            line.startswith("|")
            or line.startswith("- ")
            or line.startswith("* ")
            or re.match(r"^\d+[.)、]\s+", line)
            or line.startswith("#")
            for line in lines
        )

    def _split_overlong_prose_block(self, block: str) -> List[str]:
        compact = re.sub(r"\s+", "", block)
        if len(compact) <= MAX_SYNTHESIS_PARAGRAPH_CHARS:
            return [block]

        sentences = [piece.strip() for piece in re.split(r"(?<=[。！？；])", block) if piece.strip()]
        if len(sentences) <= 1:
            return [block]

        paragraphs = []
        current = ""
        for sentence in sentences:
            candidate = f"{current}{sentence}" if current else sentence
            if current and len(re.sub(r"\s+", "", candidate)) > MAX_SYNTHESIS_PARAGRAPH_CHARS:
                paragraphs.append(current)
                current = sentence
            else:
                current = candidate
        if current:
            paragraphs.append(current)
        return paragraphs or [block]

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
            f"【{THEMES.get(k, (k, 0))[0]}】\n{sanitize_citation_markers(v)}"
            for k, v in narratives.items() if v
        )

        prompt = (
            f"你是资深财经数据编辑。请从以下关于{stock_name}的分析文本中，提取8-12条核心事实。"
            "每条事实必须包含：事实陈述、支撑数据、置信度（高/中/低）、以及 source_refs。"
            "source_refs 必须从分析文本中的 [^n] 引用标记里提取；如果某条事实没有对应引用标记，请输出空数组 []。"
            "不要编造不存在的 source ID，不要输出分析文本中没有的引用编号。"
            "只提取客观事实和数据，不要提取观点、判断或预测。"
            "不要提取券商/媒体观点本身、社区讨论观点本身、supported/unverified discussion、多源低信用社区共振线索或 analyst inference。"
            "不要提取任何含有“可能、预计、推测、若...则...”等推断性措辞的句子。"
            "只有当事实由公告/官方/交易所/巨潮/高信用 confirmed 来源支持时，才可进入核心事实；"
            "由研报、新闻、雪球、知乎、微信公众号、AgentReach、资金流向等中低信用来源支撑的内容不得成为核心事实。"
            "去重：同一事实在不同段落中出现时只保留一次。"
            "不要在 fact 和 data 字段里包含 [1] 或 [^1] 等引用标记。"
            "\n\n输出格式（JSON）："
            '\n[\n  {"fact_id": 1, "fact": "2025年营收", "data": "8.22亿元，同比+73.4%", "confidence": "高", "source_refs": [2]},\n  ...\n]'
            "\n\n分析文本：\n"
            f"{narrative_text[:3000]}"
        )

        try:
            response_text = self._call_llm(prompt)
            if not response_text:
                return []

            # 提取 JSON 块（处理 markdown code block）
            text = sanitize_citation_markers(response_text)
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
                    fact_text = str(f.get("fact", ""))
                    data_text = str(f.get("data", ""))
                    # Strip inline citation markers like [1] or [^1] from displayed fields
                    fact_text = re.sub(r"\[\^?\d+\]", "", fact_text).strip()
                    data_text = re.sub(r"\[\^?\d+\]", "", data_text).strip()
                    # Also strip non-numeric markers such as [^supported].
                    fact_text = sanitize_citation_markers(fact_text).strip()
                    data_text = sanitize_citation_markers(data_text).strip()

                    raw_refs = f.get("source_refs", [])
                    if not isinstance(raw_refs, list):
                        raw_refs = []

                    seen = set()
                    clean_refs = []
                    for ref in raw_refs:
                        if isinstance(ref, bool):
                            continue
                        if isinstance(ref, int):
                            ref_int = ref
                        elif isinstance(ref, str) and re.fullmatch(r"\d+", ref.strip()):
                            ref_int = int(ref.strip())
                        else:
                            continue
                        if ref_int <= 0:
                            continue
                        if ref_int in seen:
                            continue
                        seen.add(ref_int)
                        clean_refs.append(ref_int)
                        if len(clean_refs) >= 3:
                            break

                    normalized.append({
                        "fact_id": f.get("fact_id", i),
                        "fact": fact_text,
                        "data": data_text,
                        "confidence": str(f.get("confidence", "中")),
                        "source_refs": clean_refs,
                    })
            return normalized
        except json.JSONDecodeError as e:
            logger.warning(f"[{stock_name}] 核心事实 JSON 解析失败: {e}")
            return []
        except Exception as e:
            logger.warning(f"[{stock_name}] 核心事实提取解析失败: {e}")
            return []
