"""Reporter 模块 — 个股深度报告生成器。

Phase C+ 拆分：
  - data_fetcher.py  → 外部 API 调用
  - scoring_engine.py → 评分与 EV 模型
  - constants.py      → 共享常量
  - stock_reporter.py → 协调器 + 板块渲染（保留在 utils/ 下）

外部使用方式不变：
    from scripts.utils.reporter import PerStockReporter
"""

# 导出常量供外部使用
from .constants import COMPETITOR_MAP, COMPETITOR_CODES, INDUSTRY_MAP

# 导出数据获取函数
from .data_fetcher import (
    fetch_tencent_quote,
    fetch_consensus_eps,
    fetch_financial_abstract,
    fetch_competitor_metrics,
    competitor_metrics_table,
    industry_fwd_pe,
)

# 导出评分引擎
from .scoring_engine import (
    classify_sentiment,
    sentiment_ratio,
    compute_pillar_scores,
    ev_expectation,
    composite_score_section,
    risk_score_section,
)

# 协调器（从原文件延迟导入，避免循环依赖）
# 外部仍通过 from scripts.utils.stock_reporter import PerStockReporter 使用

# 报告管理器
from .report_manager import ReportManager
