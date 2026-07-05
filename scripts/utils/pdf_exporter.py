"""
PDF导出模块：将 Markdown 报告转换为美观的 PDF

依赖:
    pip install markdown
    playwright install chromium

用法:
    from utils.pdf_exporter import export_pdf
    export_pdf("reports/xueqiu_report.md", "reports/xueqiu_report.pdf")
"""

import os
import re
import tempfile
from pathlib import Path
from markdown import Markdown


def _get_css_template() -> str:
    """返回报告CSS样式"""
    return """
@page {
    size: A4;
    margin: 2cm 1.8cm 2.5cm 1.8cm;
}

@page :first {
    margin-top: 1.5cm;
}

* {
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.8;
    color: #1a1a2e;
    max-width: 100%;
    margin: 0;
    padding: 0;
    background: #fff;
}

/* 标题 */
h1 {
    font-size: 22pt;
    font-weight: 700;
    color: #16213e;
    text-align: center;
    margin: 0 0 8pt 0;
    padding-bottom: 8pt;
    border-bottom: 2px solid #0f3460;
    letter-spacing: 1px;
}

h2 {
    font-size: 15pt;
    font-weight: 700;
    color: #0f3460;
    margin: 24pt 0 10pt 0;
    padding-bottom: 6pt;
    border-bottom: 1px solid #e0e0e0;
    page-break-after: avoid;
}

h3 {
    font-size: 13pt;
    font-weight: 600;
    color: #1a1a2e;
    margin: 18pt 0 8pt 0;
    page-break-after: avoid;
}

h4 {
    font-size: 11.5pt;
    font-weight: 600;
    color: #333;
    margin: 14pt 0 6pt 0;
}

/* 段落和文本 */
p {
    margin: 8pt 0;
    text-align: justify;
    word-break: break-word;
}

strong {
    font-weight: 600;
    color: #0f3460;
}

em {
    font-style: italic;
    color: #555;
}

/* 元信息 */
.meta-info {
    text-align: center;
    color: #666;
    font-size: 10pt;
    margin-bottom: 20pt;
}

.meta-info p {
    margin: 3pt 0;
    text-align: center;
}

/* 分隔线 */
hr {
    border: none;
    border-top: 1px solid #ddd;
    margin: 16pt 0;
}

/* 表格 */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 12pt 0;
    font-size: 10pt;
    page-break-inside: avoid;
}

th {
    background: #0f3460;
    color: #fff;
    font-weight: 600;
    padding: 8pt 10pt;
    text-align: left;
    border: 1px solid #0f3460;
}

td {
    padding: 7pt 10pt;
    border: 1px solid #e0e0e0;
    vertical-align: top;
}

tr:nth-child(even) {
    background: #f8f9fa;
}

tr:hover {
    background: #eef2f7;
}

/* 列表 */
ul, ol {
    margin: 8pt 0;
    padding-left: 24pt;
}

li {
    margin: 4pt 0;
}

li > ul, li > ol {
    margin: 2pt 0;
}

/* 引用块 */
blockquote {
    margin: 12pt 0;
    padding: 10pt 14pt;
    border-left: 3px solid #0f3460;
    background: #f5f7fa;
    color: #444;
    font-size: 10.5pt;
}

blockquote p {
    margin: 4pt 0;
}

/* 代码 */
code {
    font-family: "SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas, monospace;
    font-size: 9.5pt;
    background: #f4f4f4;
    padding: 1pt 4pt;
    border-radius: 3px;
    color: #c7254e;
}

pre {
    background: #f8f9fa;
    padding: 10pt 12pt;
    border-radius: 4px;
    overflow-x: auto;
    margin: 10pt 0;
    border: 1px solid #e9ecef;
}

pre code {
    background: none;
    padding: 0;
    color: #333;
    font-size: 9pt;
    line-height: 1.5;
}

/* 链接 */
a {
    color: #0f3460;
    text-decoration: none;
}

/* 图片与图表 */
p:has(> img) {
    margin: 12pt 0;
    text-align: center;
    page-break-inside: avoid;
    break-inside: avoid;
}

img {
    display: block;
    max-width: 100%;
    max-height: 210mm;
    width: auto;
    height: auto;
    object-fit: contain;
    margin: 8pt auto;
    page-break-inside: avoid;
    break-inside: avoid;
}

/* Emoji和图标 */
.emoji {
    font-family: "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
}

/* 风险提示标签 */
.risk-high {
    color: #e74c3c;
    font-weight: 600;
}

.risk-medium {
    color: #f39c12;
    font-weight: 600;
}

.risk-low {
    color: #27ae60;
    font-weight: 600;
}

/* 页眉页脚辅助 */
.header-footer {
    display: none;
}

/* 打印优化 */
@media print {
    h2 {
        page-break-after: avoid;
    }
    h3, h4 {
        page-break-after: avoid;
    }
    table {
        page-break-inside: avoid;
    }
    blockquote {
        page-break-inside: avoid;
    }
}

/* 情绪标签 */
.sentiment-badge {
    display: inline-block;
    padding: 2pt 8pt;
    border-radius: 12pt;
    font-size: 10pt;
    font-weight: 600;
    color: #fff;
    vertical-align: middle;
    margin-left: 4pt;
}
.sentiment-bull { background: #27ae60; }
.sentiment-bear { background: #e74c3c; }
.sentiment-neutral { background: #95a5a6; }

/* 信号比例条 */
.signal-bar-container {
    margin: 8pt 0;
    page-break-inside: avoid;
}
.signal-bar-label {
    font-size: 9.5pt;
    color: #555;
    margin-bottom: 3pt;
}
.signal-bar-track {
    width: 100%;
    height: 10pt;
    background: #e9ecef;
    border-radius: 5pt;
    overflow: hidden;
}
.signal-bar-fill {
    height: 100%;
    border-radius: 5pt;
    transition: width 0.3s;
}
.signal-bar-bull { background: #27ae60; }
.signal-bar-bear { background: #e74c3c; }
.signal-bar-neutral { background: #95a5a6; }

/* 互动数据卡片 */
.interaction-cards {
    display: flex;
    gap: 8pt;
    margin: 10pt 0;
    page-break-inside: avoid;
}
.interaction-card {
    flex: 1;
    text-align: center;
    padding: 8pt 4pt;
    background: #f8f9fa;
    border-radius: 4pt;
    border: 1px solid #e9ecef;
}
.interaction-card-icon {
    font-size: 14pt;
    display: block;
    margin-bottom: 2pt;
}
.interaction-card-value {
    font-size: 14pt;
    font-weight: 700;
    color: #0f3460;
    display: block;
}
.interaction-card-label {
    font-size: 8pt;
    color: #888;
    display: block;
}
"""


def _md_to_html(md_content: str, title: str = "报告") -> str:
    """将Markdown转为HTML，并注入CSS样式与可视化增强"""
    md = Markdown(extensions=["tables", "fenced_code", "toc"])
    html_body = md.convert(md_content)

    # 将报告开头的元信息转换为meta-info div
    html_body = _extract_meta_info(html_body)

    # 可视化增强
    html_body = _enhance_sentiment_badge(html_body)
    html_body = _enhance_interaction_cards(html_body)

    css = _get_css_template()

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
{css}
    </style>
</head>
<body>
{html_body}
</body>
</html>"""


def _extract_meta_info(html_body: str) -> str:
    """
    将报告开头的粗体元信息行（如 **报告日期**: 2026-05-20）提取为居中样式
    """
    # 匹配开头的 <p><strong>...: ...</strong>...</p> 模式
    pattern = r'^(\s*<p><strong>[^:<]+:</strong>[^:<]*</p>\s*)+'
    match = re.match(pattern, html_body)
    if match:
        meta_block = match.group(0)
        rest = html_body[match.end():]
        return f'<div class="meta-info">{meta_block}</div>{rest}'
    return html_body


def _enhance_sentiment_badge(html_body: str) -> str:
    """把 情绪定级: 看多/看空/中性 替换为彩色标签。"""
    sentiment_map = {
        "看多": "sentiment-bull",
        "看多（乐观）": "sentiment-bull",
        "看空": "sentiment-bear",
        "看空（悲观）": "sentiment-bear",
        "中性": "sentiment-neutral",
        "中性/观望": "sentiment-neutral",
        "观望": "sentiment-neutral",
    }

    def _replace(m):
        label = m.group(1)
        cls = sentiment_map.get(label, "sentiment-neutral")
        return f'<strong>情绪定级</strong>: <span class="sentiment-badge {cls}">{label}</span>'

    return re.sub(
        r'<strong>情绪定级</strong>:\s*([^<\s]+(?:/[^<\s]+)?)',
        _replace,
        html_body,
    )


def _enhance_interaction_cards(html_body: str) -> str:
    """把 总互动量: 👍 N | 💬 N | 🔄 N 替换为横向数据卡片。"""
    def _replace(m):
        content = m.group(1)
        likes = re.search(r'👍\s*(\d+)', content)
        comments = re.search(r'💬\s*(\d+)', content)
        reposts = re.search(r'🔄\s*(\d+)', content)

        cards = []
        if likes:
            cards.append(
                f'<div class="interaction-card">'
                f'<span class="interaction-card-icon">👍</span>'
                f'<span class="interaction-card-value">{likes.group(1)}</span>'
                f'<span class="interaction-card-label">点赞</span></div>'
            )
        if comments:
            cards.append(
                f'<div class="interaction-card">'
                f'<span class="interaction-card-icon">💬</span>'
                f'<span class="interaction-card-value">{comments.group(1)}</span>'
                f'<span class="interaction-card-label">评论</span></div>'
            )
        if reposts:
            cards.append(
                f'<div class="interaction-card">'
                f'<span class="interaction-card-icon">🔄</span>'
                f'<span class="interaction-card-value">{reposts.group(1)}</span>'
                f'<span class="interaction-card-label">转发</span></div>'
            )

        if cards:
            return f'<div class="interaction-cards">{"".join(cards)}</div>'
        return m.group(0)

    return re.sub(
        r'<li><strong>总互动量</strong>:([^<]+)</li>',
        _replace,
        html_body,
    )


def export_pdf(
    md_path: str,
    pdf_path: str = None,
    title: str = None,
    header_text: str = None,
    footer_text: str = None,
) -> str:
    """
    将Markdown文件导出为PDF

    Args:
        md_path: Markdown文件路径
        pdf_path: 输出PDF路径（默认与md同目录同名）
        title: HTML页面标题
        header_text: 页眉显示文本（默认使用 title）
        footer_text: 页脚左侧文本（默认"雪球舆情监控周报"）

    Returns:
        生成的PDF文件路径
    """
    md_file = Path(md_path)
    if not md_file.exists():
        raise FileNotFoundError(f"Markdown文件不存在: {md_path}")

    if pdf_path is None:
        pdf_path = md_file.with_suffix(".pdf")
    else:
        pdf_path = Path(pdf_path)

    # 读取Markdown内容
    md_content = md_file.read_text(encoding="utf-8")
    if title is None:
        title = md_file.stem

    # 转换为HTML
    html_content = _md_to_html(md_content, title=title)

    # 写入临时HTML文件
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        f.write(html_content)
        temp_html_path = f.name

    # 页眉/页脚个性化
    _header = header_text if header_text else (title or "")
    _footer = footer_text if footer_text else "雪球舆情监控周报"

    try:
        # 使用Playwright渲染PDF
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"file://{temp_html_path}", wait_until="networkidle")

            # 等待字体加载
            page.wait_for_timeout(500)

            page.pdf(
                path=str(pdf_path),
                format="A4",
                margin={
                    "top": "2cm",
                    "bottom": "2.2cm",
                    "left": "1.8cm",
                    "right": "1.8cm",
                },
                print_background=True,
                display_header_footer=True,
                header_template=(
                    "<div style='font-size:8pt; color:#999; width:100%; padding:0 1cm;"
                    "font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;'>"
                    f"<span>{_header}</span>"
                    "</div>"
                ),
                footer_template=(
                    "<div style='font-size:8pt; color:#999; width:100%; padding:0 1cm;"
                    "font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;"
                    "display:flex; justify-content:space-between;'>"
                    f"<span>{_footer}</span>"
                    "<span>第 <span class='pageNumber'></span> 页 / 共 <span class='totalPages'></span> 页</span>"
                    "</div>"
                ),
            )
            browser.close()

        return str(pdf_path)

    finally:
        # 清理临时文件
        try:
            os.unlink(temp_html_path)
        except OSError:
            pass


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python pdf_exporter.py <md文件路径> [pdf输出路径]")
        sys.exit(1)

    md_path = sys.argv[1]
    pdf_path = sys.argv[2] if len(sys.argv) > 2 else None
    result = export_pdf(md_path, pdf_path)
    print(f"PDF已生成: {result}")
