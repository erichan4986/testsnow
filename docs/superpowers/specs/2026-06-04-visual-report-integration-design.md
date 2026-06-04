# 可视化报告与 Markdown 报告集成设计

> **Goal**: 让 stock_reporter.py 每次生成报告时，同时输出一份带图表嵌入的完整 Markdown 报告和一份精简的 HTML Dashboard 看板。

**Architecture**: 图表生成 → Markdown 报告（文字+图表嵌入）→ HTML Dashboard（精简+图表）。四个图表文件（技术分析面板、多空对比、五维雷达、同业估值）作为共享资产被两个输出格式引用。

**Tech Stack**: Python, Plotly/Kaleido (PNG 导出), markdown (标准语法), HTML+Tailwind (Dashboard)。

---

## 一、现状与问题

当前 `stock_reporter.py` 的 `generate_stock_report()` 只生成 Markdown 报告，文字内容详尽但缺乏图表配合。之前已有一份独立的 HTML 可视化报告，但和主报告是割裂的两份文件。

**目标**：
- Markdown 报告在技术面、多空观点、估值等关键位置嵌入图表，让文字有图可配
- HTML 报告精简为 Dashboard，聚焦核心判断和图表，详细文字留在 md
- 一次运行，两份输出，共享同一批图表资产

---

## 二、图表资产清单

每次生成报告时，先生成以下 4 张 PNG 图表（固定命名规则）：

| 图表 | 文件名模板 | 用途 |
|------|-----------|------|
| 技术分析面板 | `{stock_name}_技术分析面板_{date_str}.png` | K线+成交量+MACD+RSI，含形态标注 |
| 多空观点对比 | `{stock_name}_多空观点对比_{date_str}.png` | 横向条形图对比看空/看多论据 |
| 五维评分雷达 | `{stock_name}_五维评分雷达_{date_str}.png` | 雷达图+及格线 |
| 同业估值对比 | `{stock_name}_同业估值对比_{date_str}.png` | Forward PE + PS 双轴对比 |

**输出目录**: `reports/`

---

## 三、Markdown 报告改动

在现有 `_technical_analysis_section()` 和 `_valuation_forecast_compact()` 中插入图片引用。

### 3.1 技术面分析板块（已有）

在 `_technical_analysis_section()` 返回的 markdown 末尾追加图片：

```markdown
### 技术分析图表

![技术分析面板]({stock_name}_技术分析面板_{date_str}.png)

> 图表说明：上图包含K线走势（含MA5/MA20/MA60）、成交量、MACD、RSI四个子图。
> 关键标注：双底形态颈线 {neckline}，底1 {bottom1}，底2 {bottom2}。
```

### 3.2 新增：多空观点板块

在 `_executive_summary()` 之后、`_valuation_forecast_compact()` 之前，新增 `_bull_bear_section()`：

```markdown
## 多空观点拆解

![多空观点对比]({stock_name}_多空观点对比_{date_str}.png)

> 图表说明：绿色为看多论据，红色为看空论据，长度代表强度（1-5星）。

### 看多力量
...

### 看空力量
...

### 多空博弈结论
...
```

### 3.3 综合评分板块（已有）

在 `composite_score_section()` 返回的 markdown 中，五维评分表格下方追加：

```markdown
### 五维评分雷达图

![五维评分雷达]({stock_name}_五维评分雷达_{date_str}.png)
```

### 3.4 估值板块（已有）

在 `_valuation_forecast_compact()` 或 `competitor_metrics_table()` 下方追加：

```markdown
### 同业估值对比

![同业估值对比]({stock_name}_同业估值对比_{date_str}.png)

> 图表说明：柱状图为 Forward PE，折线为 PS（市销率）。
```

---

## 四、HTML Dashboard 设计

### 4.1 定位

一页纸 Dashboard，让读者 30 秒内掌握核心判断。不包含详细论述文字。

### 4.2 板块结构

```
┌─────────────────────────────────────────┐
│  圣邦股份 (300661)  ·  模拟芯片/半导体   │
│  报告日期: 2026-06-04  ·  最新价: 113.25 │
├─────────────────────────────────────────┤
│ [评分6.8] [AI推荐] [EV+9.9%] [盈亏比]   │
│ [操作建议: 关注/不操作]                  │
├─────────────────────────────────────────┤
│ 一、技术面分析                           │
│ [技术分析面板大图]                       │
│ 形态识别文字 + 指标清单 + 关键判断高亮    │
├─────────────────────────────────────────┤
│ 二、多空观点拆解                         │
│ [多空对比图]                             │
│ 看多/看空核心论据卡片 + 博弈结论          │
├─────────────────────────────────────────┤
│ 三、五维评分雷达                         │
│ [雷达图] + 右侧分项得分卡片              │
├─────────────────────────────────────────┤
│ 四、同业估值对比                         │
│ [估值对比图] + 速览卡片 + 文字解读        │
├─────────────────────────────────────────┤
│ 五、操作建议                             │
│ 投资者类型分表（短线/波段/长期）          │
├─────────────────────────────────────────┤
│ [查看完整分析报告 → {stock_name}_{date}.md]│
└─────────────────────────────────────────┘
```

### 4.3 样式

- 使用 Tailwind CSS CDN
- 卡片式布局，圆角阴影
- 颜色编码：看多绿色、看空红色、中性灰色、关键判断黄色高亮
- 响应式：移动端单列，桌面端双列

---

## 五、生成流程

在 `generate_stock_report()` 中调整顺序：

```python
def generate_stock_report(self, stock_name, output_dir):
    # 1. 准备数据（不变）
    # 2. 生成 4 张图表 PNG → reports/
    charts = self._generate_charts(stock_name, stock_raw, output_dir)
    
    # 3. 构建 Markdown 报告（文字 + 图片嵌入）
    sections = []
    # ... 各板块生成，图片路径通过 charts 字典传入
    md_path = self._write_markdown(sections, output_dir)
    
    # 4. 生成 HTML Dashboard（精简版）
    html_path = self._write_html_dashboard(stock_name, charts, output_dir)
    
    return md_path, html_path
```

### 5.1 `_generate_charts()` 职责

调用已有的图表生成函数（或提取为独立模块）：
- `generate_technical_panel()` → PNG
- `generate_bull_bear_chart()` → PNG
- `generate_radar_chart()` → PNG
- `generate_valuation_comparison()` → PNG

返回 `{chart_name: file_path}` 字典供后续引用。

### 5.2 `_write_html_dashboard()` 职责

基于 Jinja2 模板（或字符串拼接）生成 HTML，填入：
- 股票名称、价格、日期等头部信息
- 4 张 PNG 的相对路径 `<img src="...">`
- 多空论据、操作建议等结构化数据
- 底部链接到同目录的 md 文件

---

## 六、关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 图表引擎 | Plotly + Kaleido | 已验证可工作，CJK 支持好 |
| HTML 样式 | Tailwind CDN | 无需构建步骤，快速渲染 |
| 模板引擎 | Python string/f-string | 结构简单，无需引入 Jinja2 依赖 |
| 图片引用方式 | 相对路径 | md 和 html 与图片在同一目录，保证可移植 |
| HTML 与 md 的关系 | 并行独立 | 不互相依赖，任一文件可单独查看 |

---

## 七、验证标准

- [ ] 运行 `generate_stock_report()` 后，`reports/` 目录同时出现 `.md` 和 `.html`
- [ ] Markdown 中至少 4 处图片嵌入，图片可正常显示
- [ ] HTML Dashboard 在浏览器中打开，布局正常，图表显示完整
- [ ] HTML 底部链接可点击跳转到同目录 md 文件
- [ ] 移动端浏览器打开，布局自适应

---

*设计日期: 2026-06-04*
