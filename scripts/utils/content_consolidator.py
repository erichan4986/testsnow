"""
跨来源内容去重与归纳 (Content Consolidator) — 主题聚类版

对来自雪球、知乎、全网搜索等多源内容进行：
1. LLM 提取主题标签（取代全文相似度）
2. 按主题聚类
3. 每类保留最佳内容，标注交叉来源
4. 生成主题级交叉验证摘要
"""

import json
import logging
import os
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ContentConsolidator:
    """
    跨来源内容去重与归纳器 — 主题聚类版。

    使用 LLM 提取主题标签，将表达同一主题的多源内容聚为一类，
    保留质量分最高的条目，标注交叉来源。
    """

    # 主题关键词库（用于无 LLM 时的 fallback 主题提取）
    TOPIC_KEYWORDS = {
        "业绩/财报": ["营收", "净利润", "业绩", "季报", "年报", "EPS", "毛利率", "增长", "盈利", "利润"],
        "估值/价格": ["估值", "目标价", "市值", "股价", "低估", "高估", "pe", "pb", "市盈率", "市净率"],
        "国产替代": ["国产替代", "自主可控", "进口替代", "卡脖子"],
        "涨价/周期": ["涨价", "供需", "库存", "产能", "提价", "景气度", "周期反转"],
        "技术/产品": ["新品发布", "技术突破", "产品研发", "专利授权", "芯片设计", "流片", "量产"],
        "竞争格局": ["竞争", "市场份额", "行业龙头", "护城河", "壁垒", "行业格局"],
        "资金流向": ["主力资金", "净流入", "北向资金", "机构持仓", "增持", "减持", "融资买入"],
        "政策/宏观": ["政策补贴", "关税", "利率", "美联储", "央行", "宏观经济", "货币政策"],
        "订单/客户": ["订单", "供应链", "大客户", "合作签约", "客户导入", "比亚迪", "华为"],
        "市场情绪": ["情绪", "恐慌", "乐观", "看跌", "看涨", "抄底", "出货", "洗盘", "散户"],
    }

    SIMILARITY_THRESHOLD = 0.55

    def __init__(self, similarity_threshold: float = None, use_llm_topics: bool = True):
        self.similarity_threshold = similarity_threshold or self.SIMILARITY_THRESHOLD
        self.use_llm_topics = use_llm_topics
        self._client = None
        self._init_llm()

    def _init_llm(self):
        """初始化 LLM 客户端（用于主题提取）"""
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("MOONSHOT_API_KEY")
        if not api_key:
            return
        try:
            from openai import OpenAI
            base_url = (
                "https://api.deepseek.com/v1"
                if os.getenv("DEEPSEEK_API_KEY")
                else "https://api.moonshot.cn/v1"
            )
            self._client = OpenAI(api_key=api_key, base_url=base_url)
        except Exception as e:
            logger.warning(f"LLM 客户端初始化失败: {e}")

    @staticmethod
    def _normalize_text(text: str) -> str:
        if not text:
            return ""
        return re.sub(r"[^一-龥a-zA-Z0-9]", "", text).lower()

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        a_norm = ContentConsolidator._normalize_text(a)
        b_norm = ContentConsolidator._normalize_text(b)
        if not a_norm or not b_norm:
            return 0.0
        return SequenceMatcher(None, a_norm, b_norm).ratio()

    def _extract_topics_llm(self, items: List[Dict]) -> Dict[int, List[str]]:
        """用 LLM 批量提取主题标签。"""
        if not self._client or len(items) == 0:
            return {}

        # 构建 prompt
        lines = []
        for i, item in enumerate(items):
            title = item.get("title", "")[:50]
            body = (item.get("content", "") or item.get("content_text", ""))[:150]
            lines.append(f"[{i}] {title} | {body}")

        prompt = (
            "对以下每篇文章提取 1-3 个核心主题标签（从业绩/财报、估值/价格、国产替代、"
            "涨价/周期、技术/产品、竞争格局、资金流向、政策/宏观、订单/客户、市场情绪中选择）。\n\n"
            + "\n".join(lines)
            + '\n\n请严格按以下 JSON 格式返回，不要额外说明:\n'
            + '[{"index": 0, "topics": ["国产替代", "涨价/周期"]}, ...]'
        )

        try:
            # 根据 base_url 判断使用哪个模型
            if "moonshot" in str(self._client.base_url):
                model = os.getenv("MOONSHOT_MODEL", "moonshot-v1-8k")
            else:
                model = "deepseek-chat"
            resp = self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一个财经内容主题分类专家。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            raw = resp.choices[0].message.content.strip()
            # 提取 JSON
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            results = json.loads(raw)
            mapping = {}
            for r in results:
                idx = r.get("index")
                topics = r.get("topics", [])
                if isinstance(idx, int) and 0 <= idx < len(items):
                    mapping[idx] = topics
            return mapping
        except Exception as e:
            logger.warning(f"LLM 主题提取失败: {e}")
            return {}

    def _extract_topics_fallback(self, item: Dict) -> List[str]:
        """无 LLM 时的关键词匹配主题提取。"""
        text = item.get("title", "") + " " + (item.get("content", "") or item.get("content_text", ""))
        text_lower = text.lower()
        topics = []
        for topic, kws in self.TOPIC_KEYWORDS.items():
            for kw in kws:
                if kw in text_lower:
                    topics.append(topic)
                    break
        return topics if topics else ["其他"]

    def _extract_all_topics(self, items: List[Dict]) -> List[List[str]]:
        """为所有 item 提取主题标签。"""
        if self.use_llm_topics and self._client:
            llm_results = self._extract_topics_llm(items)
            all_topics = []
            for i in range(len(items)):
                if i in llm_results and llm_results[i]:
                    all_topics.append(llm_results[i])
                else:
                    all_topics.append(self._extract_topics_fallback(items[i]))
            return all_topics
        else:
            return [self._extract_topics_fallback(it) for it in items]

    def _compute_comparison_text(self, item: Dict) -> str:
        title = item.get("title", "")
        body = item.get("content", "") or item.get("content_text", "")
        return f"{title} {body[:300]}"

    def _get_quality_score(self, item: Dict) -> float:
        qg = item.get("_quality_gate", {})
        if qg and qg.get("quality_score", -1) >= 0:
            return qg["quality_score"]
        likes = item.get("like_count", 0) or item.get("vote_up_count", 0)
        comments = item.get("comment_count", 0)
        reposts = item.get("repost_count", 0)
        return likes + comments * 2 + reposts

    def _get_source_label(self, item: Dict) -> str:
        if item.get("source") == "知乎":
            platform = item.get("source_platform", "知乎")
            if platform != "知乎":
                return f"知乎全网({platform})"
            return "知乎"
        return item.get("source", "雪球")

    def consolidate(self, items: List[Dict]) -> List[Dict]:
        """
        对多源内容进行去重与归纳。

        策略：
        1. 按主题标签粗聚类（同一主题的内容视为关联）
        2. 同一主题内按来源去重（同一来源只保留质量最高的一条）
        3. 保留质量分最高的条目，标注其他来源的关联内容
        """
        if not items:
            return []

        n = len(items)
        all_topics = self._extract_all_topics(items)

        # Step 1: 按主题标签粗聚类
        topic_groups: Dict[str, List[int]] = {}
        for idx, topics in enumerate(all_topics):
            for t in topics:
                topic_groups.setdefault(t, []).append(idx)

        # Step 2: 对每个主题，按来源去重 + 细聚类（同来源高相似度去重）
        # 限制聚类最大大小，防止超大簇
        MAX_CLUSTER_SIZE = 15
        visited = [False] * n
        clusters = []

        for topic, indices in topic_groups.items():
            unvisited = [i for i in indices if not visited[i]]
            for seed in unvisited:
                if visited[seed]:
                    continue

                cluster = [seed]
                visited[seed] = True
                seed_source = self._get_source_label(items[seed])
                seed_text = self._compute_comparison_text(items[seed])

                for other in unvisited:
                    if visited[other] or other == seed:
                        continue
                    if len(cluster) >= MAX_CLUSTER_SIZE:
                        break
                    other_source = self._get_source_label(items[other])

                    # 不同来源：直接归入同一聚类（主题关联）
                    if other_source != seed_source:
                        cluster.append(other)
                        visited[other] = True
                        continue

                    # 同来源：用文本相似度判断是否重复
                    other_text = self._compute_comparison_text(items[other])
                    sim = self._similarity(seed_text, other_text)
                    if sim >= self.similarity_threshold:
                        cluster.append(other)
                        visited[other] = True

                clusters.append(cluster)

        # 处理剩余未聚类的
        for i in range(n):
            if not visited[i]:
                clusters.append([i])

        # Step 3: 每个聚类保留最佳，标注交叉来源
        result = []
        for cluster in clusters:
            sorted_cluster = sorted(
                cluster,
                key=lambda idx: self._get_quality_score(items[idx]),
                reverse=True,
            )
            best_idx = sorted_cluster[0]
            best_item = dict(items[best_idx])

            cross_sources = []
            for idx in sorted_cluster[1:]:
                other = items[idx]
                cross_sources.append({
                    "source": self._get_source_label(other),
                    "title": other.get("title", "")[:60],
                    "author": other.get("author", "") or other.get("author_name", ""),
                    "url": other.get("url", ""),
                    "quality_score": self._get_quality_score(other),
                })

            best_item["cluster_size"] = len(cluster)
            best_item["cross_sources"] = cross_sources
            best_item["_topics"] = all_topics[best_idx]
            result.append(best_item)

        # 按质量分排序
        result.sort(key=lambda x: self._get_quality_score(x), reverse=True)

        multi_source = sum(1 for r in result if r.get("cluster_size", 1) > 1)
        logger.info(
            f"内容归纳完成: 原始 {n} 条 → 去重后 {len(result)} 条, "
            f"聚类数={len(clusters)}, 多源聚类={multi_source}"
        )
        return result

    def generate_cross_source_summary(self, items: List[Dict]) -> Optional[str]:
        """生成跨来源信息交叉验证摘要。"""
        multi_source = [it for it in items if it.get("cluster_size", 1) > 1]
        if not multi_source:
            return None

        lines = ["### 多源交叉验证", ""]
        lines.append(f"> 以下 {len(multi_source)} 条信息被多个来源共同提及，可信度较高：")
        lines.append("")

        for it in multi_source[:10]:
            title = it.get("title", "")
            topics = it.get("_topics", [])
            sources = [self._get_source_label(it)] + [
                cs["source"] for cs in it.get("cross_sources", [])
            ]
            source_str = " + ".join(sorted(set(sources)))
            topic_str = f"[{', '.join(topics[:2])}]" if topics else ""
            lines.append(f"- {topic_str} **{title[:50]}** — 来源: {source_str}")

        lines.append("")
        return "\n".join(lines)
