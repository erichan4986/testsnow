# 知乎内容精编采纳 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立知乎内容的智能编辑采纳流水线：三层漏斗过滤 + 批次 DeepSeek 分析 + 深度摘要渲染 + 知识沉淀。

**Architecture:** 新增 ZhihuCurator 组件负责批量 AI 质量评估和摘要生成；ZhihuCollector 集成 curator 做过滤分层；StockReporter 升级渲染格式；ObsidianWriter 支持知乎沉淀笔记。

**Tech Stack:** Python, DeepSeek API (OpenAI-compatible), JSON structured output

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/utils/zhihu_curator.py` | Create | 知乎内容精编器： cutoff 过滤、DeepSeek 批量评估、摘要生成、时效判断 |
| `scripts/utils/data_collector.py` | Modify | ZhihuCollector 集成 curator，替换原有简单分类逻辑 |
| `scripts/utils/stock_reporter.py` | Modify | `_zhihu_section()` 升级渲染格式（摘要+逻辑链+判断） |
| `scripts/utils/obsidian_writer.py` | Modify | `write_atomic_note()` 支持传入 analysis 渲染知乎沉淀内容 |
| `scripts/demo_shengbang.py` | Modify | 集成新流程，传入 curator 后的数据 |

---

### Task 1: 创建 ZhihuCurator 核心组件

**Files:**
- Create: `scripts/utils/zhihu_curator.py`

- [ ] **Step 1: 创建文件骨架**

```python
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


class ZhihuCurator:
    """
    知乎内容精编器：批量 AI 质量评估 + 深度摘要生成
    - L1: 统一 cutoff 粗筛（默认90天）
    - L2: DeepSeek 批量质量评估（5条/批次）
    - L3: 按 valid_until 过滤
    """

    def __init__(self, api_key: str = None, model: str = None, base_url: str = None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY") or os.getenv("MOONSHOT_API_KEY")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

        if not self.api_key or OpenAI is None:
            logger.warning("DeepSeek API 未配置，ZhihuCurator 将不可用")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def curate(self, items: List[Dict], stock_name: str = "") -> Dict[str, List[Dict]]:
        """
        对知乎内容进行精编筛选
        Returns: {"report_items": [...], "knowledge_items": [...]}
        """
        # TODO
        pass
```

- [ ] **Step 2: 实现 L1 cutoff 过滤**

```python
    def _cutoff_filter(self, items: List[Dict], days: int = 90) -> List[Dict]:
        """L1: 统一 cutoff 粗筛"""
        cutoff_ts = time.time() - days * 86400
        filtered = []
        for item in items:
            edit_time = item.get("edit_time", 0)
            if edit_time >= cutoff_ts:
                filtered.append(item)
            else:
                item["_exclude_reason"] = f"编辑时间过早 ({self._ts_to_str(edit_time)})"
        logger.info(f"L1 cutoff 过滤: {len(items)} → {len(filtered)} (cutoff={days}天)")
        return filtered

    @staticmethod
    def _ts_to_str(ts: int) -> str:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
```

- [ ] **Step 3: 实现 DeepSeek 批量评估 prompt**

```python
    def _build_batch_prompt(self, items: List[Dict], stock_name: str) -> str:
        """构建批次评估 prompt"""
        lines = [
            f"你是一位专业的半导体行业投资分析师。请对以下知乎文章进行质量评估和深度分析。",
            f"当前分析的股票是：{stock_name}",
            f"当前日期：{datetime.now().strftime('%Y-%m-%d')}",
            "",
            "对每篇文章，请输出以下结构化信息：",
            "- quality_score: 质量评分(0-100)，维度：论据充分度40%、逻辑清晰度30%、观点独特性15%、时效相关性15%",
            "- content_type: 内容类型，枚举：[短期股价预测, 事件点评, 财报分析, 产业深度分析, 竞争格局分析, 宏观政策解读, 投资策略分享, 其他]",
            "- valid_until: 有效期截止日期(YYYY-MM-DD格式)，根据内容类型判断",
            "- summary: ≥175字的摘要，提炼核心论点，不含主观评价",
            "- logic_chain: 推理链条，包含premise(前提)、evidence(论据)、reasoning(推理)、conclusion(结论)",
            "- judgment: 你对该观点的独立判断（认可/质疑/补充），若质疑需说明理由",
            "- include_in_report: 是否值得纳入投资报告(true/false)",
            "- reason_if_excluded: 若不纳入，说明原因",
            "",
            "注意：",
            "1. 评分<60分的内容不纳入报告",
            "2. 纯情绪发泄、无论据支撑的内容评分应低于40",
            "3. 摘要必须≥175字",
            "4. 有效期判断：短期预测14天、事件点评30天、财报分析90天、产业/竞争180天、宏观/策略60天、其他30天",
            "",
            "请严格返回 JSON 数组格式，每篇文章对应一个对象：",
            "[{\"quality_score\": 78, \"content_type\": \"产业深度分析\", ...}, ...]",
            "",
            "--- 文章列表 ---",
            "",
        ]
        for i, item in enumerate(items, 1):
            lines.append(f"【文章{i}】")
            lines.append(f"标题: {item.get('title', '')}")
            lines.append(f"作者: {item.get('author_name', '')}")
            lines.append(f"编辑时间: {self._ts_to_str(item.get('edit_time', 0))}")
            lines.append(f"点赞: {item.get('vote_up_count', 0)} | 评论: {item.get('comment_count', 0)}")
            text = item.get('content_text', '')[:1000]
            lines.append(f"正文:\n{text}")
            lines.append("")
        return "\n".join(lines)
```

- [ ] **Step 4: 实现批次评估调用**

```python
    def _batch_evaluate(self, items: List[Dict], stock_name: str) -> List[Dict]:
        """L2: DeepSeek 批量质量评估"""
        if not self.client or not items:
            return []

        prompt = self._build_batch_prompt(items, stock_name)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位专业的半导体行业投资分析师，擅长评估投资相关内容的质量。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=8000,
            )
            content = response.choices[0].message.content
            evaluations = self._extract_json_array(content)
            if len(evaluations) != len(items):
                logger.warning(f"DeepSeek 返回评估数量不匹配: {len(evaluations)} vs {len(items)}")
            return evaluations
        except Exception as e:
            logger.error(f"DeepSeek 批量评估失败: {e}")
            return []

    @staticmethod
    def _extract_json_array(text: str) -> List[Dict]:
        """从 LLM 输出中提取 JSON 数组"""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        import re
        # 尝试提取 ```json ... ``` 或 [...]
        for pat in [r'```json\s*(\[.*?\])\s*```', r'```\s*(\[.*?\])\s*```', r'(\[\s*\{.*?\}\s*\])']:
            match = re.search(pat, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
        logger.warning("无法从 LLM 输出中提取 JSON 数组")
        return []
```

- [ ] **Step 5: 实现 curate 主流程**

```python
    def curate(self, items: List[Dict], stock_name: str = "") -> Dict[str, List[Dict]]:
        """
        对知乎内容进行精编筛选
        Returns: {"report_items": [...], "knowledge_items": [...]}
        """
        # L1: cutoff 粗筛
        l1_items = self._cutoff_filter(items, days=90)

        # L2: 批次 DeepSeek 评估
        batch_size = 5
        all_evaluations = []
        for i in range(0, len(l1_items), batch_size):
            batch = l1_items[i:i + batch_size]
            evaluations = self._batch_evaluate(batch, stock_name)
            all_evaluations.extend(evaluations)

        # 合并评估结果到原始数据
        for item, eval_ in zip(l1_items, all_evaluations):
            item["_evaluation"] = eval_

        # L3: 按 valid_until 过滤 + 质量分过滤
        today = datetime.now().strftime("%Y-%m-%d")
        report_items = []
        knowledge_items = []

        for item in l1_items:
            eval_ = item.get("_evaluation", {})
            quality_score = eval_.get("quality_score", 0)
            valid_until = eval_.get("valid_until", "")
            include = eval_.get("include_in_report", False)

            # 质量分过滤
            if quality_score < 60:
                item["_exclude_reason"] = f"质量分过低 ({quality_score})"
                knowledge_items.append(item)
                continue

            # 有效期过滤
            if valid_until and valid_until < today:
                item["_exclude_reason"] = f"已过有效期 (至 {valid_until})"
                knowledge_items.append(item)
                continue

            # AI 判断
            if not include:
                item["_exclude_reason"] = eval_.get("reason_if_excluded", "AI判断不纳入")
                knowledge_items.append(item)
                continue

            report_items.append(item)

        logger.info(
            f"知乎精编完成: L1={len(l1_items)}, "
            f"报告={len(report_items)}, 沉淀={len(knowledge_items)}"
        )
        return {
            "report_items": report_items,
            "knowledge_items": knowledge_items,
        }
```

- [ ] **Step 6: Commit**

```bash
git add scripts/utils/zhihu_curator.py
git commit -m "feat(zhihu): add ZhihuCurator with batch AI evaluation and dynamic expiry"
```

---

### Task 2: 集成 ZhihuCurator 到 ZhihuCollector

**Files:**
- Modify: `scripts/utils/data_collector.py`

- [ ] **Step 1: 导入 ZhihuCurator**

在 `data_collector.py` 顶部（ZhihuCollector 之前）添加：

```python
try:
    from zhihu_curator import ZhihuCurator
except ImportError:
    ZhihuCurator = None
```

- [ ] **Step 2: 修改 ZhihuCollector.collect() 使用 curator**

```python
    def collect(self, stock_name: str = None, keywords: list = None,
                author_names: list = None, limit: int = 5) -> Dict:
        """
        一键采集知乎内容，经 ZhihuCurator 精编后分类
        """
        start_count = self._request_count

        # 默认关键词
        default_keywords = [stock_name] if stock_name else []
        search_keywords = list(set((keywords or []) + default_keywords))

        # 默认关注博主
        default_authors = ["Deep Van", "奥特之父", "MR.Dang", "羊村里最快的羊"]
        search_authors = author_names or default_authors

        # 搜索
        kw_items = self.search_keywords(search_keywords, limit_per_kw=limit)
        author_items = self.search_authors(search_authors, limit_per_author=min(limit, 3))
        all_items = kw_items + author_items

        # 精编筛选（如果 curator 可用）
        if ZhihuCurator is not None:
            curator = ZhihuCurator()
            if curator.client:
                curated = curator.curate(all_items, stock_name=stock_name or "")
                report_items = curated.get("report_items", [])
                knowledge_items = curated.get("knowledge_items", [])
                logger.info(
                    f"知乎采集+精编完成: 共 {len(all_items)} 条, "
                    f"报告 {len(report_items)} 条, 沉淀 {len(knowledge_items)} 条, "
                    f"消耗API {self._request_count - start_count} 次"
                )
                return {
                    "report_items": report_items,
                    "knowledge_items": knowledge_items,
                    "total": len(all_items),
                    "api_calls": self._request_count - start_count,
                }

        # Fallback: 使用原有简单关键词分类
        report_items = []
        knowledge_items = []
        for item in all_items:
            text = item.get("title", "") + " " + item.get("content_text", "")
            if self._is_stock_macro_related(text):
                item["relevance"] = "股市/宏观经济"
                report_items.append(item)
            else:
                item["relevance"] = "知识沉淀"
                knowledge_items.append(item)

        return {
            "report_items": report_items,
            "knowledge_items": knowledge_items,
            "total": len(all_items),
            "api_calls": self._request_count - start_count,
        }
```

- [ ] **Step 3: Commit**

```bash
git add scripts/utils/data_collector.py
git commit -m "feat(zhihu): integrate ZhihuCurator into ZhihuCollector"
```

---

### Task 3: 升级 stock_reporter.py 的 _zhihu_section

**Files:**
- Modify: `scripts/utils/stock_reporter.py`

- [ ] **Step 1: 重写 _zhihu_section 渲染逻辑**

替换现有的 `_zhihu_section` 方法（约第 971-1000 行）：

```python
    def _zhihu_section(self, stock_name: str, zhihu_data: Dict) -> str:
        """Section 7: 知乎内容精选（经 AI 精编）"""
        lines = ["## 七、知乎内容精选", ""]

        report_items = zhihu_data.get("report_items", []) if isinstance(zhihu_data, dict) else []
        total = zhihu_data.get("total", 0) if isinstance(zhihu_data, dict) else 0
        if not report_items:
            lines.append("*暂无知乎相关内容*")
            lines.append("")
            return "\n".join(lines)

        lines.append(f"> 本次从知乎采集 {total} 条内容，经 AI 评估筛选出 {len(report_items)} 条高质量内容纳入报告。\n")

        for i, item in enumerate(report_items[:5], 1):
            title = item.get("title", "")
            author = item.get("author_name", "未知")
            badge = item.get("author_badge", "")
            url = item.get("url", "")
            vote_up = item.get("vote_up_count", 0)
            comments = item.get("comment_count", 0)
            edit_time_ts = item.get("edit_time", 0)
            edit_time = datetime.fromtimestamp(edit_time_ts).strftime("%Y-%m-%d") if edit_time_ts else "未知"

            eval_ = item.get("_evaluation", {})
            quality_score = eval_.get("quality_score", 0)
            valid_until = eval_.get("valid_until", "")
            summary = eval_.get("summary", "")
            logic_chain = eval_.get("logic_chain", {})
            judgment = eval_.get("judgment", "")

            # 标题行
            lines.append(f"### {i}. [{title}]({url})")

            # 元信息行
            author_info = f"**{author}**"
            if badge:
                author_info += f" ({badge})"
            meta_parts = [author_info, f"编辑时间 {edit_time}", f"👍 {vote_up}", f"💬 {comments}"]
            if quality_score:
                meta_parts.append(f"质量分 {quality_score}/100")
            if valid_until:
                meta_parts.append(f"有效期至 {valid_until}")
            lines.append(" | ".join(meta_parts))
            lines.append("")

            # 摘要
            if summary:
                lines.append("**摘要**：")
                lines.append(summary)
                lines.append("")

            # 逻辑链
            if logic_chain and any(logic_chain.values()):
                lines.append("**逻辑链**：")
                premise = logic_chain.get("premise", "")
                evidence = logic_chain.get("evidence", "")
                reasoning = logic_chain.get("reasoning", "")
                conclusion = logic_chain.get("conclusion", "")
                if premise:
                    lines.append(f"- **前提**：{premise}")
                if evidence:
                    lines.append(f"- **论据**：{evidence}")
                if reasoning:
                    lines.append(f"- **推理**：{reasoning}")
                if conclusion:
                    lines.append(f"- **结论**：{conclusion}")
                lines.append("")

            # 判断
            if judgment:
                lines.append(f"**判断**：{judgment}")
                lines.append("")

        return "\n".join(lines)
```

- [ ] **Step 2: Commit**

```bash
git add scripts/utils/stock_reporter.py
git commit -m "feat(reports): upgrade _zhihu_section with AI summary, logic chain and judgment"
```

---

### Task 4: 升级 ObsidianWriter 支持知乎沉淀

**Files:**
- Modify: `scripts/utils/obsidian_writer.py`

- [ ] **Step 1: 增强 write_atomic_note 对知乎数据的渲染**

当前 `write_atomic_note` 已经可以传入 `analysis` 参数渲染分析内容。对于知乎沉淀笔记，我们需要在 `data` 中传入 `zhihu_items` 并让渲染逻辑能展示 `_exclude_reason`。

修改 `write_atomic_note` 中的原始数据渲染部分（约第 66-78 行）：

```python
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"- **{key}**:")
                for k, v in value.items():
                    lines.append(f"  - {k}: {v}")
            elif isinstance(value, list):
                lines.append(f"- **{key}**: {len(value)} 条")
                for item in value[:10]:
                    if isinstance(item, dict):
                        title = item.get("title", "")
                        reason = item.get("_exclude_reason", "")
                        author = item.get("author_name", "")
                        line = f"  - {title}"
                        if author:
                            line += f" (作者: {author})"
                        if reason:
                            line += f" — 未采纳原因: {reason}"
                        lines.append(line)
            else:
                lines.append(f"- **{key}**: {value}")
```

- [ ] **Step 2: Commit**

```bash
git add scripts/utils/obsidian_writer.py
git commit -m "feat(obsidian): enhance list rendering with exclude_reason for zhihu knowledge items"
```

---

### Task 5: 更新 demo_shengbang.py

**Files:**
- Modify: `scripts/demo_shengbang.py`

- [ ] **Step 1: 确保 demo 已经使用新的 ZhihuCollector.collect()**

当前 demo 已经正确调用了 `zhihu.collect()`，且 ZhihuCollector 内部已集成 curator，无需额外修改。

但需确认：若 DeepSeek API 未设置，collector 会 fallback 到原有简单分类，这是预期行为。

- [ ] **Step 2: Commit（如有改动）**

```bash
git add scripts/demo_shengbang.py 2>/dev/null || true
git diff --cached --quiet || git commit -m "feat(demo): zhihu curation integration verified"
```

---

### Task 6: End-to-End 测试

**Files:**
- Test via: `python scripts/demo_shengbang.py`

- [ ] **Step 1: 运行 demo 脚本**

```bash
python scripts/demo_shengbang.py
```

- [ ] **Step 2: 验证报告中的知乎板块**

```bash
grep -A 30 "七、知乎内容精选" /Users/erichan/testsnow/reports/圣邦股份_20260524.md
```

期望看到：
- 质量分、有效期、编辑时间
- ≥175字摘要
- 逻辑链（前提/论据/推理/结论）
- AI 独立判断

- [ ] **Step 3: 验证知识沉淀笔记**

```bash
ls /Users/erichan/testsnow/knowledge/10-Stocks/圣邦股份/*知乎沉淀*
cat /Users/erichan/testsnow/knowledge/10-Stocks/圣邦股份/20260524-知乎沉淀.md
```

期望看到：未采纳内容的标题、作者、未采纳原因。

- [ ] **Step 4: Commit 测试通过**

```bash
git add reports/ knowledge/10-Stocks/圣邦股份/
git commit -m "test: e2e zhihu curation pipeline verified"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] 动态时效判断 → Task 1 Step 5 valid_until 过滤
- [x] 质量优先采纳 → Task 1 Step 5 quality_score < 60 过滤
- [x] 深度摘要 ≥175字 → Task 1 Step 3 prompt 明确要求
- [x] 逻辑链条 → Task 1 Step 3 prompt + Task 3 Step 1 渲染
- [x] AI 独立判断 → Task 1 Step 3 prompt + Task 3 Step 1 渲染
- [x] 知识沉淀 → Task 1 Step 5 knowledge_items + Task 4
- [x] 成本控制 5条/批次 → Task 1 Step 5 batch_size=5

**2. Placeholder scan:**
- [x] 无 TBD/TODO
- [x] 所有代码完整可直接复制
- [x] 所有命令有预期输出

**3. Type consistency:**
- [x] `curate()` 返回 `Dict[str, List[Dict]]`
- [x] `_evaluation` 挂在 item dict 上
- [x] `stock_reporter.py` 读取 `item.get("_evaluation", {})`

---

*Plan created: 2026-05-24*
