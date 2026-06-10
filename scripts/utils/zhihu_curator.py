"""
知乎内容精编器 (ZhihuCurator)

三层漏斗过滤：
  L1: 统一 cutoff 粗筛（365天）
  L2: DeepSeek 批量质量评估（5条/批次）
  L3: 时效性判断（按 valid_until 过滤）

输出：report_items（进入报告）+ knowledge_items（知识沉淀）
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Auto-load .env from project root
_project_root = Path(__file__).parent.parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except Exception:
    pass

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

_CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "zhihu_curator"

# 内容类型 → 默认有效期（天）
CONTENT_TYPE_TTL = {
    "短期股价预测": 14,
    "事件点评": 30,
    "财报分析": 90,
    "产业深度分析": 180,
    "竞争格局分析": 180,
    "宏观政策解读": 60,
    "投资策略分享": 60,
    "其他": 30,
}


class ZhihuCurator:
    """
    知乎内容精编器。

    用法:
        curator = ZhihuCurator()
        result = curator.curate(items, current_date="2026-05-27")
        # result["report_items"]      → 进入报告的高质量内容
        # result["knowledge_items"]   → 未采纳内容（含未采纳原因）
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = None,
        base_url: str = None,
        cache_dir: Path = None,
        temperature: float = 0.3,
        l1_cutoff_days: int = 365,
        l2_quality_threshold: int = 60,
        batch_size: int = 5,
    ):
        self.temperature = temperature
        self.l1_cutoff_days = l1_cutoff_days
        self.l2_quality_threshold = l2_quality_threshold
        self.batch_size = batch_size
        self.cache_dir = cache_dir or _CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Resolve LLM backend: explicit args > DEEPSEEK > MOONSHOT
        if api_key:
            self.api_key = api_key
            self.model = model
            self.base_url = base_url
        elif os.getenv("DEEPSEEK_API_KEY"):
            self.api_key = os.getenv("DEEPSEEK_API_KEY")
            self.model = model or "deepseek-chat"
            self.base_url = base_url or "https://api.deepseek.com/v1"
        elif os.getenv("MOONSHOT_API_KEY"):
            self.api_key = os.getenv("MOONSHOT_API_KEY")
            self.model = model or os.getenv("MOONSHOT_MODEL", "moonshot-v1-128k")
            self.base_url = base_url or os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")
        else:
            self.api_key = None
            self.model = None
            self.base_url = None

        if not self.api_key:
            logger.warning("LLM API_KEY 未设置，ZhihuCurator 将使用降级规则")
            self.client = None
        elif OpenAI is None:
            logger.warning("openai 包未安装，ZhihuCurator 将使用降级规则")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def curate(
        self,
        items: List[Dict],
        current_date: str = None,
    ) -> Dict:
        """
        对知乎内容执行三层漏斗过滤。

        Args:
            items: ZhihuCollector 返回的原始条目列表
            current_date: 当前日期，格式 "YYYY-MM-DD"，默认今天

        Returns:
            {
                "report_items": [...],    # 进入报告的高质量内容
                "knowledge_items": [...], # 未采纳内容（含 reason_if_excluded）
                "stats": {
                    "total": N,
                    "l1_passed": N,
                    "l2_evaluated": N,
                    "l3_included": N,
                    "api_calls": N,
                }
            }
        """
        if current_date is None:
            current_date = datetime.now().strftime("%Y-%m-%d")
        current_dt = datetime.strptime(current_date, "%Y-%m-%d")
        cutoff_dt = current_dt - timedelta(days=self.l1_cutoff_days)

        stats = {"total": len(items), "l1_passed": 0, "l2_evaluated": 0, "l3_included": 0, "api_calls": 0}

        # === L1: 统一 cutoff 粗筛 ===
        l1_items = []
        for item in items:
            edit_time = item.get("edit_time", 0)
            if edit_time:
                item_dt = datetime.fromtimestamp(edit_time)
                if item_dt < cutoff_dt:
                    continue
            l1_items.append(item)
        stats["l1_passed"] = len(l1_items)
        logger.info(f"[ZhihuCurator] L1 粗筛: {len(items)} → {len(l1_items)} 条")

        # === L2+L3: 批量质量评估 + 时效判断 ===
        evaluated = []

        if self.client and l1_items:
            # 按批次处理
            for i in range(0, len(l1_items), self.batch_size):
                batch = l1_items[i : i + self.batch_size]
                batch_results = self._evaluate_batch(batch, current_date)
                stats["api_calls"] += 1
                for item, result in zip(batch, batch_results):
                    item["_curator"] = result
                    evaluated.append(item)
        else:
            # LLM 不可用：使用降级规则
            for item in l1_items:
                item["_curator"] = self._fallback_evaluation(item, current_date)
                evaluated.append(item)

        stats["l2_evaluated"] = len(evaluated)

        # === 分类：report vs knowledge ===
        report_items = []
        knowledge_items = []

        for item in evaluated:
            cur = item.get("_curator", {})
            include = cur.get("include_in_report", False)
            quality_score = cur.get("quality_score", 0)
            valid_until = cur.get("valid_until", current_date)

            # 检查是否过期
            try:
                valid_dt = datetime.strptime(valid_until, "%Y-%m-%d")
                expired = valid_dt < current_dt
            except Exception:
                expired = False

            if include and not expired and quality_score >= self.l2_quality_threshold:
                report_items.append(item)
                stats["l3_included"] += 1
            else:
                # 补充未采纳原因
                reasons = []
                if not include:
                    reason = cur.get("reason_if_excluded", "")
                    if reason:
                        reasons.append(reason)
                    else:
                        reasons.append("AI判定不纳入报告")
                if expired:
                    reasons.append(f"内容已过期（有效期至 {valid_until}）")
                # 仅当 LLM 未给出具体原因时才追加质量分不足
                has_quality_reason = any("质量" in r or "评分" in r or "分" in r for r in reasons)
                if quality_score < self.l2_quality_threshold and not has_quality_reason:
                    reasons.append(f"质量分不足（{quality_score}/100 < {self.l2_quality_threshold}）")
                cur["_exclusion_reason"] = "; ".join(reasons) if reasons else "未通过质量筛选"
                knowledge_items.append(item)

        logger.info(
            f"[ZhihuCurator] 最终分类: report={len(report_items)}, "
            f"knowledge={len(knowledge_items)}, API调用={stats['api_calls']}"
        )

        return {
            "report_items": report_items,
            "knowledge_items": knowledge_items,
            "stats": stats,
        }

    def _evaluate_batch(self, batch: List[Dict], current_date: str) -> List[Dict]:
        """
        调用 LLM 批量评估一批知乎内容。

        Returns:
            与 batch 等长的评估结果列表
        """
        cache_key = self._batch_cache_key(batch)
        cached = self._load_cache(cache_key)
        if cached:
            logger.debug("ZhihuCurator batch cache hit")
            try:
                return cached
            except Exception:
                pass

        # 构建 prompt
        batch_text = []
        for idx, item in enumerate(batch, 1):
            title = item.get("title", "")
            content = item.get("content_text", "")[:1000]
            author = item.get("author_name", "")
            badge = item.get("author_badge", "")
            vote_up = item.get("vote_up_count", 0)
            edit_time = item.get("edit_time", 0)
            date_str = datetime.fromtimestamp(edit_time).strftime("%Y-%m-%d") if edit_time else "未知"

            batch_text.append(
                f"### 文章 {idx}\n"
                f"标题: {title}\n"
                f"作者: {author} ({badge or '无认证'})\n"
                f"发布时间: {date_str}\n"
                f"点赞数: {vote_up}\n"
                f"正文:\n{content}\n"
            )

        prompt = f"""# 任务

你是一位专业的投资内容策展编辑。请对以下 {len(batch)} 篇知乎文章进行批量质量评估。
当前日期: {current_date}

## 评估标准

对每篇文章从以下维度评分（满分100）：
- **论据充分度** (40%): 是否有数据、案例、引用支撑
- **逻辑清晰度** (30%): 推理链条是否完整、有无跳跃
- **观点独特性** (15%): 是否提供非共识视角
- **时效相关性** (15%): 对当前投资决策的价值

## 内容类型与有效期规则

判断每篇文章的内容类型，并给出有效期：
- 短期股价预测 → 有效期14天
- 事件点评 → 有效期30天
- 财报分析 → 有效期90天
- 产业深度分析 → 有效期180天
- 竞争格局分析 → 有效期180天
- 宏观政策解读 → 有效期60天
- 投资策略分享 → 有效期60天
- 其他 → 有效期30天

## 输出格式

必须输出 **纯 JSON 数组**，不要 Markdown 代码块，不要其他文字。数组长度必须严格等于 {len(batch)}。

每篇文章的 JSON 结构：
{{
  "quality_score": 78,
  "content_type": "产业深度分析",
  "valid_until": "2026-08-24",
  "summary": "≥175字的摘要，提炼核心论点...",
  "logic_chain": {{
    "premise": "前提假设/背景...",
    "evidence": "论据/数据...",
    "reasoning": "推理过程...",
    "conclusion": "结论..."
  }},
  "judgment": "AI对该观点的独立判断（认可/质疑/补充），150-250字...",
  "include_in_report": true,
  "reason_if_excluded": ""
}}

注意：
- summary 必须 ≥175 字
- judgment 保持客观，可认可、可质疑、可补充
- 如果质量分 < 60，include_in_report 设为 false，并在 reason_if_excluded 中说明原因
- 如果内容已过期（valid_until < {current_date}），include_in_report 设为 false

## 待评估文章

{chr(10).join(batch_text)}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位专业的投资内容策展编辑，擅长评估财经类文章的质量和价值。你只输出纯JSON，不输出任何其他文字。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()

            # 解析 JSON
            # LLM 可能返回 {"results": [...]} 或直接返回数组
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                results = parsed
            elif isinstance(parsed, dict):
                # 尝试各种可能的键
                for key in ["results", "items", "evaluations", "data"]:
                    if key in parsed and isinstance(parsed[key], list):
                        results = parsed[key]
                        break
                else:
                    # 如果都没有，取 dict 中的第一个 list 值
                    results = next((v for v in parsed.values() if isinstance(v, list)), [])
            else:
                results = []

            # 确保长度匹配
            if len(results) != len(batch):
                logger.warning(
                    f"[ZhihuCurator] LLM 返回结果数量不匹配: 期望 {len(batch)}, 实际 {len(results)}"
                )
                # 填充缺失项
                while len(results) < len(batch):
                    results.append(self._empty_evaluation(current_date))
                results = results[: len(batch)]

            self._save_cache(cache_key, results)
            return results

        except Exception as e:
            logger.error(f"[ZhihuCurator] LLM 批量评估失败: {e}")
            # 全部使用降级评估
            return [self._fallback_evaluation(item, current_date) for item in batch]

    def _fallback_evaluation(self, item: Dict, current_date: str) -> Dict:
        """LLM 不可用时的降级评估规则。"""
        text = item.get("title", "") + " " + item.get("content_text", "")
        vote_up = item.get("vote_up_count", 0)
        comment_count = item.get("comment_count", 0)

        # 简单规则评分
        score = 50
        has_numbers = any(c.isdigit() for c in text)
        has_logic = any(w in text for w in ["因为", "所以", "如果", "因此", "意味着", "结论"])
        has_data = any(w in text for w in ["%", "亿", "万", "元", "倍", "PE", "PB"])

        if has_numbers:
            score += 10
        if has_logic:
            score += 10
        if has_data:
            score += 10
        if vote_up > 50:
            score += 10
        if comment_count > 20:
            score += 5

        # 判断内容类型（简单关键词匹配）
        content_type = "其他"
        if any(w in text for w in ["股价", "涨跌", "目标价", "涨停", "跌停"]):
            content_type = "短期股价预测"
        elif any(w in text for w in ["财报", "年报", "季报", "业绩", "营收", "净利润"]):
            content_type = "财报分析"
        elif any(w in text for w in ["产业", "行业", "产业链", "格局", "趋势"]):
            content_type = "产业深度分析"
        elif any(w in text for w in ["竞争", "对手", "vs", "对比", "相较于"]):
            content_type = "竞争格局分析"
        elif any(w in text for w in ["政策", "宏观", "GDP", "CPI", "利率", "央行"]):
            content_type = "宏观政策解读"
        elif any(w in text for w in ["策略", "投资", "配置", "仓位", "建议"]):
            content_type = "投资策略分享"
        elif any(w in text for w in ["事件", "公告", "新闻", "突发"]):
            content_type = "事件点评"

        ttl_days = CONTENT_TYPE_TTL.get(content_type, 30)
        valid_until = (
            datetime.strptime(current_date, "%Y-%m-%d") + timedelta(days=ttl_days)
        ).strftime("%Y-%m-%d")

        include = score >= self.l2_quality_threshold

        # 生成简单摘要
        summary = text[:200] + "..." if len(text) > 200 else text

        return {
            "quality_score": score,
            "content_type": content_type,
            "valid_until": valid_until,
            "summary": summary,
            "logic_chain": {
                "premise": "[降级模式] 无法提取详细逻辑链",
                "evidence": "[降级模式] 无法提取详细论据",
                "reasoning": "[降级模式] 无法提取详细推理",
                "conclusion": "[降级模式] 无法提取详细结论",
            },
            "judgment": "[降级模式] LLM API 不可用，无法生成深度判断。建议人工评估内容质量。",
            "include_in_report": include,
            "reason_if_excluded": "" if include else "质量分不足或 LLM API 不可用",
        }

    def _empty_evaluation(self, current_date: str) -> Dict:
        """返回空评估结构。"""
        return {
            "quality_score": 0,
            "content_type": "其他",
            "valid_until": current_date,
            "summary": "评估失败",
            "logic_chain": {
                "premise": "",
                "evidence": "",
                "reasoning": "",
                "conclusion": "",
            },
            "judgment": "LLM 评估失败",
            "include_in_report": False,
            "reason_if_excluded": "评估失败",
        }

    def _batch_cache_key(self, batch: List[Dict]) -> str:
        """基于批次内容生成缓存键。"""
        parts = []
        for item in batch:
            cid = item.get("content_id", "")
            title = item.get("title", "")[:50]
            parts.append(f"{cid}:{title}")
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _load_cache(self, key: str) -> Optional[List[Dict]]:
        """从缓存加载评估结果。"""
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def _save_cache(self, key: str, results: List[Dict]) -> None:
        """保存评估结果到缓存。"""
        cache_file = self.cache_dir / f"{key}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save curator cache: {e}")
