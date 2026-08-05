"""
多源内容统一质量评估机制 (Content Quality Gate)

统一处理来自雪球、知乎、微信公众号等多源内容的质量筛选：
1. 硬指标筛选：长度、数据密度、逻辑密度、情绪密度、重复度
2. LLM 质量评估：对通过硬指标的内容打分（0-100），质量太差的丢弃

输出统一的数据结构，供报告生成器使用。
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Auto-load .env from project root
_project_root = Path(__file__).parent.parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except Exception:
    pass

logger = logging.getLogger(__name__)

# ============ 硬指标配置 ============

# 逻辑连接词
_LOGIC_WORDS = [
    "因为", "所以", "如果", "那么", "因此", "意味着", "结论",
    "前提", "推导", "验证", "由于", "导致", "说明", "反映",
    "对比", "相较于", "数据表明", "统计", "测算", "估算",
    "逻辑", "假设", "推理", "论证", "因果", "关联",
]

# 数据模式（百分比、小数、金额等）
_DATA_PATTERNS = [r"\d+[%％]", r"\d+\.\d+", r"\d+亿", r"\d+万", r"\d+元", r"\d+年"]

# 高质量关键词
_QUALITY_KEYWORDS = [
    "深度", "分析", "研报", "调研", "逻辑", "拆解", "梳理",
    "产业链", "基本面", "估值", "财报", "业绩", "行业",
    "格局", "竞争", "壁垒", "护城河", "商业模式",
]

# 低质量信号词
_LOW_QUALITY_SIGNALS = [
    "涨停", "跌停", "必涨", "必跌", "暴涨", "暴跌", "翻倍", "十倍",
    "绝对", "必然", "一定", "毫无疑问", "铁定", "稳赚",
]


@dataclass
class ContentItem:
    """统一的内容项数据结构（适配多源）"""
    source: str  # "xueqiu" | "zhihu" | "wechat" | "other"
    title: str
    content: str
    author: str
    url: str
    publish_time: str

    # 互动数据（不同来源的指标映射到统一字段）
    likes: int = 0
    comments: int = 0
    reposts: int = 0

    # 元数据
    extra: Dict = field(default_factory=dict)

    @property
    def interaction(self) -> int:
        return self.likes + self.comments + self.reposts

    @property
    def content_length(self) -> int:
        return len(self.content)


@dataclass
class QualityResult:
    """质量评估结果"""
    item: ContentItem
    passed_hard_gate: bool
    hard_gate_reason: str
    quality_score: float  # 0-100，-1 表示未评估
    llm_judgment: str
    action: str  # "keep" | "demote" | "discard"
    reasons: List[str] = field(default_factory=list)


class HardGate:
    """
    硬指标筛选器 — 不调用LLM，纯规则判断。

    通过标准（满足任意一条即可）：
    - 内容长度 >= 200 字 且 含数据 且 含逻辑词
    - 内容长度 >= 100 字 且 互动数 > 15
    - 标题含高质量关键词 且 内容长度 >= 80 字
    """

    MIN_LENGTH_WITH_DATA = 200
    MIN_LENGTH_WITH_INTERACTION = 100
    MIN_INTERACTION = 15
    MIN_LENGTH_SHORT = 80

    def evaluate(self, item: ContentItem) -> tuple:
        """
        Returns: (passed: bool, reason: str)
        """
        text = f"{item.title} {item.content}"
        length = item.content_length
        interaction = item.interaction

        has_data = any(re.search(p, text) for p in _DATA_PATTERNS)
        has_logic = any(w in text for w in _LOGIC_WORDS)
        has_quality_kw = any(kw in item.title for kw in _QUALITY_KEYWORDS)

        # 条件1: 长文 + 有数据 + 有逻辑
        if length >= self.MIN_LENGTH_WITH_DATA and has_data and has_logic:
            return True, f"长文({length}字)+数据+逻辑"

        # 条件2: 中等长度 + 高互动
        if length >= self.MIN_LENGTH_WITH_INTERACTION and interaction >= self.MIN_INTERACTION:
            return True, f"中等长度({length}字)+高互动({interaction})"

        # 条件3: 标题含关键词 + 有实质内容
        if has_quality_kw and length >= self.MIN_LENGTH_SHORT:
            return True, f"高质量标题+实质内容({length}字)"

        # 未通过：给出具体原因
        if length < self.MIN_LENGTH_SHORT:
            return False, f"内容过短({length}字)"
        if not has_data and not has_logic:
            return False, "缺乏数据和逻辑推导"
        if interaction < 3:
            return False, "互动量极低"
        return False, f"未达准入标准(长度{length}, 互动{interaction})"


class LLMQualityAssessor:
    """
    LLM 质量评估器 — 对通过硬指标的内容进行深度质量评分。

    评分维度（0-100）：
    - 论据扎实度（40%）：是否有数据支撑、引用来源
    - 逻辑严谨度（30%）：推导过程是否清晰、无逻辑谬误
    - 信息增量（20%）：是否提供超出常识的新信息
    - 表达清晰度（10%）：结构是否清晰、易于理解

    评分结果：
    - >= 70: keep（进入报告）
    - 50-69: demote（降级为 sentiment/参考）
    - < 50: discard（丢弃）
    """

    KEEP_THRESHOLD = 70
    DEMOTE_THRESHOLD = 50

    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        try:
            from openai import OpenAI
        except ImportError:
            logger.warning("openai 未安装，LLM 质量评估不可用")
            return

        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("MOONSHOT_API_KEY")
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

        if not api_key:
            logger.warning("LLM API_KEY 未设置，质量评估将使用降级规则")
            return

        try:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            self.model = model
        except Exception as e:
            logger.warning(f"LLM 客户端初始化失败: {e}")

    def assess(self, item: ContentItem) -> QualityResult:
        """
        对单条内容进行 LLM 质量评估。

        如果 LLM 不可用，使用规则降级评分。
        """
        if not self.client:
            return self._rule_based_assess(item)

        # 构建评估 prompt
        prompt = self._build_prompt(item)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1000,
            )
            content = response.choices[0].message.content
            return self._parse_response(item, content)
        except Exception as e:
            logger.warning(f"LLM 评估失败: {e}，回退到规则评分")
            return self._rule_based_assess(item)

    def assess_batch(self, items: List[ContentItem]) -> List[QualityResult]:
        """
        批量评估（节省 API 调用）。
        建议批次大小：5-10 条
        """
        if not self.client or len(items) == 0:
            return [self._rule_based_assess(item) for item in items]

        # 构建批量 prompt
        prompt = self._build_batch_prompt(items)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            content = response.choices[0].message.content
            return self._parse_batch_response(items, content)
        except Exception as e:
            logger.warning(f"批量 LLM 评估失败: {e}，回退到规则评分")
            return [self._rule_based_assess(item) for item in items]

    def _system_prompt(self) -> str:
        return """你是一位资深投资内容质量评估专家。你的任务是对投资分析类内容进行质量评分。

评分维度（总分100）：
1. 论据扎实度（0-40分）：是否有具体数据、财务指标、行业数据支撑？是否引用可靠来源？
2. 逻辑严谨度（0-30分）：推导过程是否清晰？前提→论据→推理→结论的链条是否完整？有无逻辑谬误？
3. 信息增量（0-20分）：是否提供超出市场常识的新信息或独特视角？
4. 表达清晰度（0-10分）：结构是否清晰？语言是否准确专业？

评分标准：
- >=70分：keep（高质量，可进入深度报告）
- 50-69分：demote（中等质量，仅作为参考/情绪统计）
- <50分：discard（低质量，直接丢弃）

输出格式（必须严格按JSON格式）：
{
  "score": 75,
  "dimension_scores": {"evidence": 30, "logic": 25, "insight": 15, "clarity": 5},
  "judgment": "该帖子从库存周期、竞争格局、国产替代三个维度系统分析了模拟芯片行业...",
  "action": "keep",
  "reasons": ["论据有具体数据支撑", "逻辑链条完整", "提供了行业涨价的新信息"]
}

注意：
- 口号式、情绪式、无数据支撑的内容应给低分
- 纯预测股价、喊口号的内容应给低分
- 有具体财务数据、行业调研、逻辑推导的内容应给高分"""

    def _build_prompt(self, item: ContentItem) -> str:
        return f"""请对以下内容进行质量评估：

来源: {item.source}
标题: {item.title}
作者: {item.author}
互动: 👍{item.likes} 💬{item.comments} 🔄{item.reposts}

正文:
{item.content[:1500]}

请输出 JSON 格式的评估结果。"""

    def _build_batch_prompt(self, items: List[ContentItem]) -> str:
        parts = []
        for i, item in enumerate(items, 1):
            parts.append(f"""【内容{i}】
来源: {item.source}
标题: {item.title}
作者: {item.author}
互动: 👍{item.likes} 💬{item.comments} 🔄{item.reposts}
正文:
{item.content[:1200]}
---""")

        parts_text = "\n".join(parts)
        return f"""请对以下 {len(items)} 条内容进行批量质量评估。

要求：
1. 对每条内容分别评分
2. 输出严格的 JSON 数组格式
3. 数组中每个元素对应一条内容的评估结果

{parts_text}

输出格式：
[
  {{"score": 75, "dimension_scores": {{...}}, "judgment": "...", "action": "keep", "reasons": ["..."]}},
  ...
]"""

    def _parse_response(self, item: ContentItem, content: str) -> QualityResult:
        """解析单条 LLM 响应"""
        try:
            # 提取 JSON
            json_str = self._extract_json(content)
            result = json.loads(json_str)

            score = float(result.get("score", 0))
            action = result.get("action", "discard")
            judgment = result.get("judgment", "")
            reasons = result.get("reasons", [])

            # 校验 action
            if action not in ("keep", "demote", "discard"):
                action = self._score_to_action(score)

            return QualityResult(
                item=item,
                passed_hard_gate=True,
                hard_gate_reason="已通过硬指标筛选",
                quality_score=score,
                llm_judgment=judgment,
                action=action,
                reasons=reasons,
            )
        except Exception as e:
            logger.warning(f"解析 LLM 响应失败: {e}，回退到规则评分")
            return self._rule_based_assess(item)

    def _parse_batch_response(self, items: List[ContentItem], content: str) -> List[QualityResult]:
        """解析批量 LLM 响应"""
        try:
            json_str = self._extract_json(content)
            results = json.loads(json_str)

            if not isinstance(results, list):
                raise ValueError("响应不是数组")

            quality_results = []
            for i, item in enumerate(items):
                if i < len(results):
                    result = results[i]
                    score = float(result.get("score", 0))
                    action = result.get("action", "discard")
                    if action not in ("keep", "demote", "discard"):
                        action = self._score_to_action(score)

                    quality_results.append(QualityResult(
                        item=item,
                        passed_hard_gate=True,
                        hard_gate_reason="已通过硬指标筛选",
                        quality_score=score,
                        llm_judgment=result.get("judgment", ""),
                        action=action,
                        reasons=result.get("reasons", []),
                    ))
                else:
                    quality_results.append(self._rule_based_assess(item))

            return quality_results
        except Exception as e:
            logger.warning(f"解析批量响应失败: {e}，回退到规则评分")
            return [self._rule_based_assess(item) for item in items]

    def _extract_json(self, content: str) -> str:
        """从 LLM 响应中提取 JSON"""
        # 尝试找 ```json ... ``` 代码块
        match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if match:
            return match.group(1)

        # 尝试直接找 JSON 对象/数组
        match = re.search(r'(\{.*\}|\[.*\])', content, re.DOTALL)
        if match:
            return match.group(1)

        return content

    def _rule_based_assess(self, item: ContentItem) -> QualityResult:
        """
        规则降级评分（LLM 不可用时）。
        基于数据密度、逻辑密度、长度、互动量计算。
        """
        text = f"{item.title} {item.content}"
        length = item.content_length
        interaction = item.interaction

        score = 0.0
        reasons = []

        # 1. 数据密度（0-30分）
        data_count = sum(1 for p in _DATA_PATTERNS if re.search(p, text))
        data_score = min(data_count * 5, 30)
        score += data_score
        if data_count > 0:
            reasons.append(f"含{data_count}类数据指标")

        # 2. 逻辑密度（0-25分）
        logic_count = sum(1 for w in _LOGIC_WORDS if w in text)
        logic_score = min(logic_count * 3, 25)
        score += logic_score
        if logic_count > 0:
            reasons.append(f"含{logic_count}个逻辑连接词")

        # 3. 长度（0-20分）
        length_score = min(length / 20, 20)
        score += length_score
        reasons.append(f"内容长度{length}字")

        # 4. 互动（0-15分）
        if interaction > 50:
            score += 15
            reasons.append(f"高互动({interaction})")
        elif interaction > 20:
            score += 10
            reasons.append(f"中等互动({interaction})")
        elif interaction > 5:
            score += 5
            reasons.append(f"基础互动({interaction})")

        # 5. 关键词（0-10分）
        kw_count = sum(1 for kw in _QUALITY_KEYWORDS if kw in text)
        kw_score = min(kw_count * 2, 10)
        score += kw_score

        action = self._score_to_action(score)

        return QualityResult(
            item=item,
            passed_hard_gate=True,
            hard_gate_reason="已通过硬指标筛选",
            quality_score=round(score, 1),
            llm_judgment=f"[规则评分] 数据密度{data_score:.0f} + 逻辑密度{logic_score:.0f} + 长度{length_score:.0f} + 互动{min(interaction/5,15):.0f} + 关键词{kw_score:.0f}",
            action=action,
            reasons=reasons,
        )

    def _score_to_action(self, score: float) -> str:
        if score >= self.KEEP_THRESHOLD:
            return "keep"
        elif score >= self.DEMOTE_THRESHOLD:
            return "demote"
        return "discard"


class ContentQualityGate:
    """
    内容质量总控门。

    使用流程:
        gate = ContentQualityGate()
        results = gate.process(items)  # items: List[ContentItem]

        keep_items = [r for r in results if r.action == "keep"]
        demote_items = [r for r in results if r.action == "demote"]
        discarded = [r for r in results if r.action == "discard"]
    """

    def __init__(self):
        self.hard_gate = HardGate()
        self.llm_assessor = LLMQualityAssessor()

    def process(self, items: List[ContentItem], use_llm: bool = True) -> List[QualityResult]:
        """
        对内容列表执行完整质量评估流程。

        Args:
            items: 内容项列表
            use_llm: 是否使用 LLM 进行二次评估（默认 True）

        Returns:
            QualityResult 列表
        """
        logger.info(f"内容质量门: 收到 {len(items)} 条内容")

        # 步骤1: 硬指标筛选
        hard_results = []
        for item in items:
            passed, reason = self.hard_gate.evaluate(item)
            if passed:
                hard_results.append(item)
            else:
                logger.debug(f"[{item.source}] 硬指标未通过: {reason} | {item.title[:30]}")

        logger.info(f"硬指标筛选: {len(hard_results)}/{len(items)} 条通过")

        # 步骤2: LLM 质量评估（批量）
        if use_llm and self.llm_assessor.client and hard_results:
            llm_results = []
            batch_size = 5
            for i in range(0, len(hard_results), batch_size):
                batch = hard_results[i:i+batch_size]
                batch_results = self.llm_assessor.assess_batch(batch)
                llm_results.extend(batch_results)
                logger.info(f"LLM 评估进度: {min(i+batch_size, len(hard_results))}/{len(hard_results)}")
        else:
            llm_results = [
                self.llm_assessor._rule_based_assess(item)
                for item in hard_results
            ]

        # 统计
        keep = sum(1 for r in llm_results if r.action == "keep")
        demote = sum(1 for r in llm_results if r.action == "demote")
        discard = sum(1 for r in llm_results if r.action == "discard")
        logger.info(f"质量评估完成: keep={keep}, demote={demote}, discard={discard}")

        return llm_results

    def process_xueqiu_posts(self, posts: List[Dict], use_llm: bool = True) -> List[QualityResult]:
        """
        处理雪球帖子（兼容现有数据结构）。
        """
        items = []
        for post in posts:
            item = ContentItem(
                source="xueqiu",
                title=post.get("title", ""),
                content=post.get("content", ""),
                author=post.get("author", ""),
                url=post.get("url", ""),
                publish_time=post.get("time", ""),
                likes=post.get("like_count", 0),
                comments=post.get("comment_count", 0),
                reposts=post.get("repost_count", 0),
                extra=post,
            )
            items.append(item)
        return self.process(items, use_llm=use_llm)

    def process_zhihu_items(self, zhihu_items: List[Dict]) -> List[QualityResult]:
        """
        处理知乎回答（兼容现有数据结构）。
        """
        items = []
        for it in zhihu_items:
            item = ContentItem(
                source="zhihu",
                title=it.get("title", ""),
                content=it.get("content_text", ""),
                author=it.get("author_name", ""),
                url=it.get("url", ""),
                publish_time=it.get("edit_time", ""),
                likes=it.get("vote_up_count", 0),
                comments=it.get("comment_count", 0),
                reposts=0,
                extra=it,
            )
            items.append(item)
        return self.process(items)


# ============ 便捷函数 ============

def filter_xueqiu_posts(posts: List[Dict], min_quality_score: float = 50) -> Dict[str, List[Dict]]:
    """
    对雪球帖子执行统一质量筛选。

    Returns:
        {"featured": [...], "sentiment": [...], "discarded": [...]}
    """
    gate = ContentQualityGate()
    results = gate.process_xueqiu_posts(posts)

    featured = []
    sentiment = []
    discarded = []

    for result in results:
        post = result.item.extra
        if result.action == "keep":
            post["_quality_score"] = result.quality_score
            post["_quality_reasons"] = result.reasons
            featured.append(post)
        elif result.action == "demote":
            post["_quality_score"] = result.quality_score
            sentiment.append(post)
        else:
            discarded.append(post)

    # 按质量分排序
    featured.sort(key=lambda x: x.get("_quality_score", 0), reverse=True)
    sentiment.sort(key=lambda x: x.get("_quality_score", 0), reverse=True)

    return {
        "featured": featured,
        "sentiment": sentiment,
        "discarded": discarded,
    }


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    test_posts = [
        {
            "title": "圣邦股份深度分析：模拟芯片周期反转+国产替代双击",
            "content": "因为模拟芯片行业库存周期已经见底，所以Q2开始涨价。根据德州仪器的财报数据，Q1库存周转天数从120天下降到90天。如果国产替代加速，那么圣邦作为龙头最受益。结论：当前估值合理，建议持有。",
            "author": "分析师A",
            "url": "https://xueqiu.com/test/1",
            "time": "2026-05-20",
            "like_count": 45,
            "comment_count": 20,
        },
        {
            "title": "冲啊！圣邦必涨！",
            "content": "绝对涨停！铁定翻倍！毫无疑问！",
            "author": "散户B",
            "url": "https://xueqiu.com/test/2",
            "time": "2026-05-20",
            "like_count": 5,
            "comment_count": 2,
        },
        {
            "title": "从财务报表看圣邦的竞争力",
            "content": "圣邦股份2025年营收45.6亿元，同比增长32%。毛利率58.5%，净利率22.3%。对比思瑞浦营收38.2亿、毛利率55.2%，圣邦在盈利能力和规模上都有优势。研发投入占比18.5%，高于行业平均15%。",
            "author": "价值投资者C",
            "url": "https://xueqiu.com/test/3",
            "time": "2026-05-20",
            "like_count": 120,
            "comment_count": 35,
        },
    ]

    result = filter_xueqiu_posts(test_posts)
    print(f"\n=== 筛选结果 ===")
    print(f"featured: {len(result['featured'])} 条")
    for p in result["featured"]:
        print(f"  [{p['author']}] {p['title'][:30]}... (质量分: {p.get('_quality_score', 0)})")
    print(f"sentiment: {len(result['sentiment'])} 条")
    print(f"discarded: {len(result['discarded'])} 条")
