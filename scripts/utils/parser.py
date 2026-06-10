import re
import logging
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class EastmoneyParser:
    """东方财富股吧 HTML 解析器"""

    BASE_URL = "https://guba.eastmoney.com"

    def parse_post_list(self, html: str, gid: str) -> List[Dict]:
        """
        解析帖子列表页

        东方财富列表页每行大致结构：
        <tr class="listitem">
            <td class="l1"><a>...</a></td>  <!-- 标题 -->
            <td class="l2">作者</td>
            <td class="l3">时间</td>
            <td class="l4">阅读量</td>
            <td class="l5">评论数</td>
        </tr>
        """
        posts = []

        # 尝试多种模式匹配，兼容结构微调
        # 模式1：完整的 listitem tr
        pattern = re.compile(
            r'<tr[^>]*class="[^"]*listitem[^"]*"[^>]*>.*?<\/tr>',
            re.S | re.I
        )
        rows = pattern.findall(html)

        if not rows:
            # 模式2：更宽松的行匹配
            pattern2 = re.compile(
                r'<tr[^>]*>.*?<td[^>]*class="l1".*?</tr>',
                re.S | re.I
            )
            rows = pattern2.findall(html)

        for row in rows:
            post = self._parse_row(row, gid)
            if post and post.get("title"):
                posts.append(post)

        return posts

    def _parse_row(self, row_html: str, gid: str) -> Optional[Dict]:
        """解析单行 HTML"""
        try:
            # 提取阅读量
            read_count = 0
            read_match = re.search(
                r'<div[^>]*class="read"[^>]*>(.*?)</div>',
                row_html,
                re.S | re.I
            )
            if read_match:
                read_count = self._parse_number(self._clean_html(read_match.group(1)))

            # 提取评论数
            comment_count = 0
            comment_match = re.search(
                r'<div[^>]*class="reply"[^>]*>(.*?)</div>',
                row_html,
                re.S | re.I
            )
            if comment_match:
                comment_count = self._parse_number(self._clean_html(comment_match.group(1)))

            # 提取标题和链接
            title_match = re.search(
                r'<div[^>]*class="title"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?</div>',
                row_html,
                re.S | re.I
            )
            if not title_match:
                return None

            link = title_match.group(1).strip()
            title = self._clean_html(title_match.group(2))

            # 补全链接
            if link.startswith("//"):
                link = "https:" + link
            elif link.startswith("/"):
                link = self.BASE_URL + link
            elif not link.startswith("http"):
                link = f"{self.BASE_URL}/{link}"

            # 提取作者
            author = ""
            author_match = re.search(
                r'<div[^>]*class="author"[^>]*>.*?<a[^>]*>(.*?)</a>.*?</div>',
                row_html,
                re.S | re.I
            )
            if author_match:
                author = self._clean_html(author_match.group(1))

            # 提取时间
            time_str = ""
            time_match = re.search(
                r'<div[^>]*class="update"[^>]*>(.*?)</div>',
                row_html,
                re.S | re.I
            )
            if time_match:
                time_str = self._clean_html(time_match.group(1))

            return {
                "title": title,
                "url": link,
                "author": author,
                "time": time_str,
                "read_count": read_count,
                "comment_count": comment_count,
                "source": "eastmoney",
                "gid": gid,
            }

        except Exception as e:
            logger.debug(f"解析行失败: {e}")
            return None

    def parse_post_detail(self, html: str) -> Dict:
        """
        解析帖子详情页，提取正文和评论

        Returns:
            {"content": str, "comments": List[Dict]}
        """
        result = {"content": "", "comments": []}

        # 提取正文（多种可能的选择器）
        content_patterns = [
            r'<div[^>]*id="post_content"[^>]*>(.*?)</div>\s*</div>\s*<div',
            r'<div[^>]*class="[^"]*stockcodec[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*article-body[^"]*"[^>]*>(.*?)</div>',
        ]

        for pat in content_patterns:
            match = re.search(pat, html, re.S | re.I)
            if match:
                result["content"] = self._clean_html(match.group(1))
                break

        # 提取评论（简化版）
        comment_pattern = re.compile(
            r'<div[^>]*class="[^"]*reply-item[^"]*"[^>]*>.*?<\/div>\s*<\/div>',
            re.S | re.I
        )
        comment_blocks = comment_pattern.findall(html)

        for block in comment_blocks[:10]:  # 最多取前10条评论
            comment = self._parse_comment_block(block)
            if comment:
                result["comments"].append(comment)

        return result

    def _parse_comment_block(self, html: str) -> Optional[Dict]:
        """解析单条评论"""
        try:
            # 评论内容
            content_match = re.search(
                r'<div[^>]*class="[^"]*reply-text[^"]*"[^>]*>(.*?)</div>',
                html,
                re.S | re.I
            )
            if not content_match:
                content_match = re.search(
                    r'<div[^>]*class="[^"]*text[^"]*"[^>]*>(.*?)</div>',
                    html,
                    re.S | re.I
                )

            content = self._clean_html(content_match.group(1)) if content_match else ""

            # 评论作者
            author_match = re.search(
                r'<a[^>]*class="[^"]*user-name[^"]*"[^>]*>(.*?)</a>',
                html,
                re.S | re.I
            )
            author = self._clean_html(author_match.group(1)) if author_match else ""

            # 点赞数
            like_match = re.search(
                r'<span[^>]*class="[^"]*like-count[^"]*"[^>]*>(.*?)</span>',
                html,
                re.S | re.I
            )
            like_count = 0
            if like_match:
                like_count = self._parse_number(self._clean_html(like_match.group(1)))

            if content:
                return {
                    "author": author,
                    "content": content,
                    "like_count": like_count,
                }
            return None

        except Exception:
            return None

    @staticmethod
    def _clean_html(raw: str) -> str:
        """去除 HTML 标签和多余空白"""
        if not raw:
            return ""
        # 去标签
        text = re.sub(r'<[^>]+>', '', raw)
        # 去 HTML 实体
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&amp;', '&').replace('&quot;', '"')
        # 去多余空白
        text = ' '.join(text.split())
        return text.strip()

    @staticmethod
    def _parse_number(text: str) -> int:
        """解析数字（支持万、千等）"""
        if not text:
            return 0
        text = text.strip().replace(',', '')
        try:
            if '万' in text:
                return int(float(text.replace('万', '')) * 10000)
            return int(float(text))
        except (ValueError, TypeError):
            return 0


class XueqiuParser:
    """雪球网 HTML/JSON 解析器（增强方案备用）"""

    def parse_post_list(self, html: str) -> List[Dict]:
        """解析雪球帖子列表（简化版）"""
        posts = []
        # 雪球结构变化较频繁，此处保留接口
        return posts

    def parse_post_detail(self, html: str) -> Dict:
        """解析雪球帖子详情"""
        return {"content": "", "comments": []}
