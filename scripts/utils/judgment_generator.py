"""
精品帖子判断生成器

使用 LLM (Kimi/DeepSeek) 为每篇雪球帖子自动生成深度判断，
替代硬编码的 _get_featured_analyses()。

输出格式：
- 推导过程分析
- 论据扎实度判断
- 与市场共识的差异

支持文件缓存，避免重复调用 LLM。
"""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional

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

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "judgments"


class JudgmentGenerator:
    """
    为雪球帖子生成 AI 深度判断。

    用法:
        generator = JudgmentGenerator()
        judgment = generator.generate(
            stock_name="圣邦股份",
            post={
                "title": "...",
                "author": "...",
                "url": "...",
                "content": "帖子正文（完整或摘要）",
                "like_count": 77,
                "comment_count": 5,
                "repost_count": 0,
            }
        )
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = None,
        base_url: str = None,
        cache_dir: Path = None,
        temperature: float = 0.4,
    ):
        self.temperature = temperature
        self.cache_dir = cache_dir or _CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Resolve backend: explicit args > DEEPSEEK > MOONSHOT
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
            logger.warning("LLM API_KEY 未设置，JudgmentGenerator 将使用降级判断")
            self.client = None
        elif OpenAI is None:
            logger.warning("openai 包未安装，JudgmentGenerator 将使用降级判断")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def generate(self, stock_name: str, post: Dict) -> str:
        """
        为单篇帖子生成深度判断。

        Args:
            stock_name: 股票名称
            post: 帖子字典，至少包含 title, author, url, content

        Returns:
            Markdown 格式的判断文本
        """
        cache_key = self._cache_key(stock_name, post)
        cached = self._load_cache(cache_key)
        if cached:
            logger.debug("Judgment cache hit for %s", post.get("url", ""))
            return cached

        if not self.client:
            return self._generic_judgment(stock_name, post)

        try:
            judgment = self._call_llm(stock_name, post)
            self._save_cache(cache_key, judgment)
            return judgment
        except Exception as e:
            logger.error("LLM judgment generation failed for %s: %s", post.get("url", ""), e)
            return self._generic_judgment(stock_name, post)

    def _call_llm(self, stock_name: str, post: Dict) -> str:
        """调用 LLM 生成判断。"""
        title = post.get("title", "")
        author = post.get("author", "")
        content = post.get("content", "") or ""
        likes = post.get("like_count", 0)
        comments = post.get("comment_count", 0)
        reposts = post.get("repost_count", 0)

        # Truncate very long content to control token usage
        max_content_len = 3000
        if len(content) > max_content_len:
            content = content[:max_content_len] + "\n...[内容已截断]"

        prompt = f"""# 分析任务

你是一位专业的股票社区内容分析师。请基于以下雪球网帖子，生成一份深度判断。

## 帖子信息

- **股票**: {stock_name}
- **标题**: {title}
- **作者**: {author}
- **互动数据**: 👍{likes} | 💬{comments} | 🔄{reposts}

## 帖子正文

{content}

## 分析要求

请从以下三个维度进行分析，每个维度 150-300 字：

### 1. 推导过程分析
拆解作者的论证链条：前提假设 → 论据/数据 → 推理过程 → 结论。如果帖子缺乏逻辑推导（如纯情绪表达、口号式看多/看空），请明确指出。

### 2. 判断
评估论据的扎实程度：数据是否可验证？逻辑是否有漏洞？推理是否严谨？给出具体的理由，不要泛泛而谈。

### 3. 与市场共识的差异
这篇帖子的观点与当前市场主流认知相比，是更乐观、更悲观、还是更悲观但有新论据？它提出了哪些市场尚未充分定价的因素？

## 输出格式

直接输出 Markdown 文本，不需要 JSON，不需要代码块。使用以下结构：

**推导过程分析**：
[分析内容]

**判断**：
[评估内容]

**与市场共识的差异**：
[对比分析]

## 注意事项
- 保持客观中立，不要附和作者观点
- 如果帖子内容过短或缺乏实质分析，请直接说明"内容过短，无法提取有效推导链"
- 如果帖子包含未经证实的数据，请标注"数据待验证"
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位专业的股票社区内容分析师，擅长拆解投资论证的逻辑链条。"},
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            max_tokens=2000,
        )

        return response.choices[0].message.content.strip()

    @staticmethod
    def _generic_judgment(stock_name: str, post: Dict) -> str:
        """LLM 不可用时的降级判断。"""
        author = post.get("author", "")
        likes = post.get("like_count", 0)
        comments = post.get("comment_count", 0)
        reposts = post.get("repost_count", 0)
        content = post.get("content", "")

        # Detect content type
        content_len = len(content)
        has_numbers = any(c.isdigit() for c in content)
        has_logic_words = any(w in content for w in ["因为", "所以", "如果", "因此", "意味着"])

        if content_len < 50:
            quality = "内容过短，仅为情绪表达或口号式断言"
        elif not has_numbers and not has_logic_words:
            quality = "缺乏数据支撑和逻辑推导，主要为观点陈述"
        elif has_numbers and has_logic_words:
            quality = "包含一定数据支撑和逻辑推导，具有一定分析价值"
        else:
            quality = "观点有一定参考价值，但论据扎实度一般"

        return f"""**推导过程分析**：
该帖子由 **{author}** 发布，获得了 {likes} 赞、{comments} 条评论、{reposts} 次转发。内容长度 {content_len} 字。{quality}。

**判断**：
从互动数据看，这篇帖子{'获得了较高的社区关注度' if likes > 20 else '互动量一般，但观点有一定参考价值'}。
社区讨论中，{stock_name} 当前的主要分歧在于**短期业绩兑现节奏**与**长期产业逻辑**之间的平衡。投资者在参考此类帖子时，应注意区分"事实陈述"与"观点判断"，并交叉验证关键数据。

**与市场共识的差异**：
无法从当前内容中判断与市场共识的具体差异。建议结合更多来源的信息进行交叉验证。"""

    def _cache_key(self, stock_name: str, post: Dict) -> str:
        """生成缓存键。基于股票名、URL 和内容摘要。"""
        url = post.get("url", "")
        content = post.get("content", "")[:500]
        raw = f"{stock_name}|{url}|{content}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _load_cache(self, key: str) -> Optional[str]:
        """从缓存加载判断。"""
        cache_file = self.cache_dir / f"{key}.md"
        if cache_file.exists():
            try:
                return cache_file.read_text(encoding="utf-8")
            except Exception:
                pass
        return None

    def _save_cache(self, key: str, judgment: str) -> None:
        """保存判断到缓存。"""
        cache_file = self.cache_dir / f"{key}.md"
        try:
            cache_file.write_text(judgment, encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to save judgment cache: %s", e)


if __name__ == "__main__":
    # Quick test
    gen = JudgmentGenerator()
    test_post = {
        "title": "这里绝对不是终点他是一个巨大的趋势出来了",
        "author": "能量的守恒",
        "url": "https://xueqiu.com/6855532795/388411598",
        "content": "$圣邦股份(SZ300661)$ .这里绝对不是终点他是一个巨大的趋势出来了未来可能会有盘旋和等待但是终点是遥远的那，一个非常大的遥远的地方！！！100之后的他，梦想更遥远",
        "like_count": 77,
        "comment_count": 5,
        "repost_count": 0,
    }
    print(gen.generate("圣邦股份", test_post))
