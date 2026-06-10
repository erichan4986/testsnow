# AlphaGBM 26 Skills 深度拆解与借鉴分析

> 分析日期: 2026-06-01
> 数据来源: /tmp/alphagbm-skills (git clone 获取)
> 分析者: Claude Code

---

## 一、AlphaGBM 整体架构概览

AlphaGBM 是一个面向美股/港股/A股的 AI 驱动期权与股票研究平台，提供 26 个独立 Skill，覆盖五大领域：

| 领域 | Skills 数量 | 代表 Skill |
|------|------------|-----------|
| **核心股票分析** | 6 | stock-analysis, compare, company-profile, investment-thesis, theme-research, take-profit |
| **期权策略与定价** | 10 | options-score, options-strategy, greeks, iv-rank, vol-surface, vol-smile, earnings-crush, duan-analysis, hedge-advisor, pnl-simulator |
| **市场情绪与宏观** | 4 | market-sentiment, vix-status, fear-score, macro-view |
| **研究知识库** | 4 | company-profile, investment-thesis, theme-research, health-check |
| **交易工具** | 4 | alert, watchlist, unusual-activity, polymarket |
| **回测与验证** | 2 | bps-backtest, take-profit |

**核心理念**: G = B + M (Gain = Basics + Momentum)，五维度评分模型。

---

## 二、核心股票分析类 Skill（6个）

### 2.1 alphagbm-stock-analysis — 股票综合分析

**功能概述**: 五维度综合评分 + EV Expectation Model + AI 研报生成

**实现机制**:

1. **五维度评分 (0-10)**:
   - **Basics (B)**: PE/PEG, growth rate, profit margin, ROE, FCF
   - **Momentum (M)**: VIX, technical indicators, fund flow, macro
   - 权重: Fundamental valuation + Market sentiment

2. **Risk Score (0-10, 加法模型)**:
   | Factor | Trigger | Points |
   |--------|---------|--------|
   | Valuation | PE > 60 | +2.0 |
   | Growth | Growth < -10% | +2.0 |
   | Liquidity | Volume below threshold | +2.0 |
   | Market | VIX > 30 | +1.5 |
   | Technical | Price < MA200 | +1.0 |
   - Risk 0-2 → Max position 20%
   - Risk 8-10 → Don't buy

3. **EV Expectation Model**:
   ```
   EV = (upside_prob × upside_range) + (downside_prob × downside_range)
   Weighted = 50% × 1-week + 30% × 1-month + 20% × 3-month
   ```
   | EV | Recommendation |
   |----|---------------|
   | > +8% | STRONG_BUY |
   | +3% ~ +8% | BUY |
   | -3% ~ +3% | HOLD |
   | < -8% | STRONG_AVOID |

4. **Target Price — 5 methods, industry-weighted**:
   - PE valuation · PEG valuation · Growth discount · DCF · Technical analysis
   - Risk adjustment: high risk → -15%, medium risk → -8%

5. **ATR Stop-Loss**:
   ```
   stop = price - ATR(14) × multiplier(1.5-4.0)
   ```
   Multiplier adjusts for Beta and VIX. Hard floor: -15%.

**API 设计**:
- `GET /api/stock/quick-quote/<TICKER>` — 即时快照，无配额消耗
- `POST /api/stock/analyze-sync` — 同步分析（阻塞 10-30s）
- `POST /api/stock/analyze-async` — 异步分析（返回 task_id）
- `GET /api/stock/summary/<TICKER>` — 精简分析，首次免费

**数据缓存策略**:
- Quick quote: 实时
- Full analysis: 首次计算后缓存，后续请求秒回

**可借鉴点**:
1. ✅ **五维度加权评分** — 已借鉴到 stock_reporter.py，G = B + M 框架
2. ✅ **EV Expectation Model** — 已借鉴，短期(技术面+资金)+中期(情绪+基本面)+长期(估值)
3. 🎯 **Risk Score 加法模型** — 可作为 Phase 3 增强，我们的 `_risk_score_section` 目前较简单
4. 🎯 **Target Price 多方法加权** — 目前我们只用了一致预期 EPS，可扩展为 PE/PEG/DCF/技术面加权
5. 🎯 **ATR Stop-Loss** — 可作为止损建议板块加入报告
6. 🎯 **compact=true 参数** — 给 LLM 友好的精简输出 (~500 tokens)

---

### 2.2 alphagbm-compare — 多股对比

**功能概述**: 2-5 只股票的五维度横向对比，每个维度标出 winner

**实现机制**:
- 并排比较: GBM Five Pillars / Options Metrics / Technicals / Valuations
- Category Winner: 每个维度用绿色 badge 高亮最佳标的
- Overall Recommendation: 加权综合排名 + 关键差异化因素
- Trade idea: 如果必须选一个，选哪个及原因

**API**: `GET /api/analytics/compare?symbols=AAPL,MSFT,GOOGL&dimensions=all`

**可借鉴点**:
1. 🎯 **持仓组合对比报告** — 我们的 6 只股票可以生成横向对比页，目前只有单股报告
2. 🎯 **维度 Winner 标注** — 对比表中用视觉标记突出每维度最佳
3. 🎯 **Trade Idea 生成** — 对比后给出"如果只能选一个"的推荐

---

### 2.3 alphagbm-company-profile — 公司档案与知识库

**功能概述**: 用户个人研究知识库，每只股票一个档案，自动刷新

**核心功能**:
- 8 年 PE/PB Band 历史数据
- Financial red flags (规则引擎检测)
- Event radar (近期事件追踪)
- AI-generated profile summary (~500 chars markdown)
- 分层限制: Free=1, Plus=10, Pro=50

**Red Flags 规则示例**:
```json
{"rule_id": "revenue_decline_2q", "severity": "high", "message": "连续两季度营收下滑"}
```

**API**:
- `POST /api/research/profiles` — 创建/更新档案
- `GET /api/research/profiles/<TICKER>` — 读取档案
- `POST /api/research/profiles/<TICKER>/refresh` — 刷新数据
- `GET /api/research/profiles/<TICKER>/band` — 8 年 PE/PB Band（无需登录）

**可借鉴点**:
1. 🎯 **PE/PB Band 历史图** — 可用于报告中的估值历史位置判断（当前 PE 在过去 8 年的百分位）
2. 🎯 **Financial Red Flags 规则引擎** — 可用财报数据自动检测风险信号
3. 🎯 **Event Radar** — 公司公告+新闻的时间线聚合
4. 🎯 **档案分层管理** — 我们的 ObsidianWriter 已有类似概念，但缺少自动刷新机制

---

### 2.4 alphagbm-investment-thesis — 投资论据管理

**功能概述**: 记录"为什么买入"和"何时卖出"，结构化监控

**核心功能**:
- `buy_thesis`: 自由文本买入理由 (2-4 句)
- `sell_conditions`: 结构化触发器数组
  - `price_drop_pct` — 回撤百分比
  - `pe_above` / `pb_above` — 估值上限
  - `growth_below` — 增速下限
  - `thesis_breach` — 定性论据破坏
- 自动监控: 条件触发时状态从 `active` → `triggered`
- AI critique: 系统对论据质量的评分和反馈

**Status 生命周期**:
```
active ──(sell condition fires)──▶ triggered
   │                                   │
   └────────(user closes)──▶ closed ◀──┘
```

**可借鉴点**:
1. 🎯 **买入理由+卖出条件结构化** — 我们目前的报告只有分析，没有投资决策框架
2. 🎯 **论据漂移检测 (Thesis Drift)** — 当基本面变化导致原始论据不再成立时自动提醒
3. 🎯 **AI Critique** — 用 LLM 评判买入论据的逻辑严谨性

---

### 2.5 alphagbm-theme-research — 主题研究

**功能概述**: 将多只股票按主题分组（如 AI 基建、港股高息），主题级 AI 总结 + 新闻监控

**核心功能**:
- Theme: name + description + tickers[] + news_keywords[]
- theme_summary: AI 生成的主题叙事 (markdown)
- 聚合数据: 平均涨跌幅、领涨/领跌股、匹配新闻
- 主题级新闻监控: keywords 匹配的新闻自动聚合

**可借鉴点**:
1. 🎯 **按主题分组持仓** — 我们的 6 只股票可以按主题分组（半导体、生物医药、新能源等）
2. 🎯 **主题级新闻监控** — 用关键词聚合跨公司的新闻，生成主题动态
3. 🎯 **主题级 AI 总结** — 不仅单股分析，还有组合层面的产业逻辑总结

---

### 2.6 alphagbm-take-profit — 止盈策略实验室

**功能概述**: 量化回答"能否长期持有还是必须主动止盈"

**核心指标: Rollercoaster Rate**:
- 定义: 入场后浮盈达到 +50% 然后回撤 >50% 峰值的概率
- 指数 ETF/蓝筹股: 0%（可长期持有）
- 高成长股 (NVDA/TSLA): ~85%（必须止盈）
- 杠杆 ETF (TQQQ): ~97%（结构性不可持有）

**15 种止盈策略回测**:
- A 家族: 全仓卖出 (+50% / +100% / +200% 触发)
- B 家族: 分级卖出 (B_50/100/200, B_30/60/100 等)
- C_10x: 信念持有
- D: 止损策略（回测显示在所有标的上均输给持有）
- E: 永不卖出
- F: +50% 激活后峰值回撤触发
- G: HV 感知策略（根据入场日波动率选择 A_+100% 或 A_+200%）

**输出**: 每种策略的 CAGR / Rollercoaster Rate / Max Drawdown

**可借鉴点**:
1. 🎯 **持仓止盈策略建议** — 根据股票类型（蓝筹/成长/杠杆）推荐不同的止盈方案
2. 🎯 **Rollercoaster Rate 概念** — 高波动股的"纸上富贵"概率量化
3. 🎯 **分级止盈策略** — 比如 黑芝麻智能(高波动)适合 B_30/60/100，长春高新适合持有
4. 🎯 **策略回测数据库** — 首次计算 ~30s，后续全球缓存 30 天

---

## 三、期权策略与定价类 Skill（10个）

> **注意**: 我们的系统目前没有期权功能，但以下设计思路仍然可以借鉴。

### 3.1 alphagbm-options-score — 期权合约评分

**功能概述**: 对期权链中每个合约用多因子模型评分 (0-100)

**四大策略的评分权重**:

| Sell Put | Weight | Buy Call | Weight |
|----------|--------|----------|--------|
| premium_yield | 20% | bullish_momentum | 25% |
| support_strength | 20% | breakout_potential | 20% |
| safety_margin | 15% | value_efficiency | 20% |
| trend_alignment | 15% | volatility_timing | 15% |
| probability_profit | 15% | liquidity | 10% |
| liquidity | 10% | time_optimization | 10% |
| time_decay | 5% | | |

**评分等级**:
- 80-100: Exceptional
- 60-79: Strong
- 40-59: Average
- 0-39: Poor

**风险收益风格标签**:
- steady_income: 65-80% 胜率, 1-5%/月
- balanced: 40-55% 胜率, 50-200%
- high_risk_high_reward: 20-40% 胜率, 2-10x

**可借鉴点**:
1. 🎯 **多因子评分模型设计** — 7-8 个因子加权，每个因子有明确的计算逻辑
2. 🎯 **风格标签系统** — 将量化结果映射为投资者易懂的风格描述
3. 🎯 **Reverse Score** — 给定合约参数反向计算评分（验证当前持仓质量）

---

### 3.2 alphagbm-options-strategy — 多腿策略推荐

**功能概述**: 根据市场观点推荐最优多腿期权策略

**策略模板 (15+)**:
- 看涨: Bull Call Spread, Bull Put Spread, Long Call, Covered Call, Synthetic Long
- 看跌: Bear Put Spread, Bear Call Spread, Long Put, Synthetic Short
- 中性: Iron Condor, Iron Butterfly, Short Straddle, Short Strangle, Calendar Spread
- 波动: Long Straddle, Long Strangle, Butterfly Spread, Reverse Iron Condor
- 收益: Covered Call, Cash-Secured Put, Collar, Jade Lizard

**策略选择逻辑**:
1. 匹配用户市场观点 → 候选策略
2. IV 环境过滤 (高 IV 偏卖方，低 IV 偏买方)
3. 风险/收益 + 盈利概率 + 资金效率评分
4. 返回 Top 3 推荐，含完整 P&L profile

**可借鉴点**:
1. 🎯 **策略模板化** — 预设多种策略模板，根据市场条件自动匹配
2. 🎯 **IV 环境驱动的策略过滤** — 高/低波动环境决定买卖方向
3. 🎯 **Top 3 推荐而非单一答案** — 给用户选择空间

---

### 3.3 alphagbm-greeks — 希腊字母分析

**功能概述**: 一阶 + 二阶 Greeks 计算 + 情景热力图

**覆盖指标**:
| Greek | Order | 含义 |
|-------|-------|------|
| Delta | 1st | 价格敏感度 |
| Gamma | 1st | Delta 敏感度（加速度）|
| Theta | 1st | 时间衰减 |
| Vega | 1st | IV 敏感度 |
| Rho | 1st | 利率敏感度 |
| Charm | 2nd | Delta 衰减 (delta-theta cross) |
| Vanna | 2nd | Delta-vol cross |
| Volga | 2nd | Vega 凸性 |

**热力图**: Price axis × IV axis 的 Delta/PnL grid

**可借鉴点**:
1. 🎯 **情景分析矩阵** — 我们的报告可以增加"如果股价 ±10% / 情绪变化，会怎样"的情景分析
2. 🎯 **二阶效应** — 不仅考虑直接影响，还考虑交叉影响

---

### 3.4 alphagbm-iv-rank — 隐含波动率排名

**功能概述**: IV Rank + IV Percentile + VRP 分析

**核心指标**:
| Metric | Formula |
|--------|---------|
| IV Rank | (Current IV - 52w Low) / (52w High - 52w Low) × 100 |
| IV Percentile | 过去 252 天中 IV 低于今天的比例 |
| HV/IV Ratio | Historical Vol / Implied Vol |

**IV 区域信号**:
| IV Rank | Zone | 建议 |
|---------|------|------|
| 80-100 | Very High | 卖出权利金 |
| 60-80 | High | 偏卖方，选择性操作 |
| 40-60 | Moderate | 方向中性，用观点决定 |
| 20-40 | Low | 偏买方 |
| 0-20 | Very Low | 买入权利金 |

**VRP (Volatility Risk Premium)**:
```
VRP = Implied Vol - Historical Vol
```
| VRP Level | Seller | Buyer |
|-----------|--------|-------|
| >=15% | Very favorable | Unfavorable |
| 5-15% | Favorable | Slightly unfavorable |
| +/-5% | Neutral | Neutral |
| -15% to -5% | Unfavorable | Favorable |
| <-15% | Very unfavorable | Very favorable |

**可借鉴点**:
1. 🎯 **历史分位体系** — 不仅看绝对值，还看历史位置（我们的 PE 评分已部分实现）
2. 🎯 **VRP 概念** — 市场预期 vs 实际实现的差距，可用于判断"情绪溢价"
3. 🎯 **区域信号映射** — 将连续数值映射为离散交易信号

---

### 3.5 alphagbm-vol-surface / vol-smile — 波动率曲面/微笑

**功能概述**: 3D IV 曲面分析（行权价 × 到期日）/ 2D 微笑分析（单到期日）

**关键输出**:
- Surface Grid: 每个 (strike, expiry) 坐标的 IV
- ATM Term Structure: 近月 vs 远月 IV
- Skew by Expiry: Put-Call IV 差值
- Surface Anomalies: 偏离拟合曲面的合约（潜在定价错误）
- Shape Classification: contango / backwardation / flat / inverted / event-driven

**微笑形状含义**:
| Shape | 市场含义 | 交易思路 |
|-------|---------|---------|
| Normal | OTM put IV > OTM call | 标准对冲需求 |
| Flat | IV 大致相等 | 低恐惧，中性策略 |
| Reverse | OTM call IV > OTM put | 上行投机或逼空 |
| Winged | 两边 OTM 都高 | 预期大波动，方向不明 |
| Smirk | 一边明显更陡 | 集中于一侧的方向恐惧 |

**可借鉴点**:
1. 🎯 **异常检测** — 识别偏离正常模式的定价错误
2. 🎯 **形状分类** — 将复杂数据简化为几种典型模式
3. 🎯 **跨期限分析** — 短期 vs 长期情绪的差异

---

### 3.6 alphagbm-earnings-crush — 财报季 IV 分析

**功能概述**: 财报前 IV crush 历史 + 隐含波动预测 + Iron Condor 报价

**核心功能**:
- 过去 8 季度: pre-earnings IV / post-earnings IV / crush% / actual move / straddle PnL
- 隐含波动 ±X%: 期权市场定价的财报波动
- IV Rank 策略标签: >70→short IV / <30→directional / 30-70→wait
- Iron Condor 报价: 4 腿 spread，含 credit/max profit/max loss/breakevens

**可借鉴点**:
1. 🎯 **事件驱动分析模板** — 财报、公告等事件前后的波动分析
2. 🎯 **历史模式识别** — 过去 N 次同类事件的表现统计
3. 🎯 **策略标签化** — 根据数据自动打策略标签

---

### 3.7 alphagbm-duan-analysis — 段永平风格分析

**功能概述**: 针对段永平投资框架的三面板分析

**三面板**:
1. **Sell Put**: 心理价位卖 Put，计算年化收益和行权成本价
2. **Covered Call**: 持有正股卖 Call，计算增强收益
3. **Panic Buy Context**: VIX ≥ 35 为极端恐惧买入信号

**设计理念**: 卖方为主、收租逻辑、 never a buyer of options

**可借鉴点**:
1. 🎯 **知名投资者框架封装** — 将特定投资哲学转化为结构化分析
2. 🎯 **三面板设计** — 一个框架下多个独立但相关的分析维度
3. 🎯 **中文原生表达** — 用中文投资者熟悉的语言体系

---

### 3.8 alphagbm-hedge-advisor — 对冲顾问

**功能概述**: 根据持仓状态自动分类并推荐对冲策略

**四种持仓场景**:
| Scenario | Trigger | 推荐对冲 |
|----------|---------|---------|
| Falling Knife | 回撤 ≥15% 且 PnL ≤ +5% | Long Put 5% OTM, 75 DTE, 100% cover, ~5% budget |
| Bottom Fishing | PnL ±8% 且 purpose = just_bought | Long Put 5% OTM, 90 DTE, 50-75% cover, ~3% budget |
| Gain Protection | PnL ≥ 15% | Collar 95/110 + Tier-down |
| Normal Hold | 默认 | 仓位规则，无紧急对冲 |

**可借鉴点**:
1. 🎯 **持仓状态自动分类** — 根据盈亏和回撤自动判断持仓处境
2. 🎯 **场景化建议** — 不同场景给出不同的操作方案
3. 🎯 **Position Rules** — 单票 ≤20%, 板块 ≤30-35%, 现金储备 10-15%

---

### 3.9 alphagbm-pnl-simulator — P&L 模拟器

**功能概述**: 任意期权的到期 P&L 图 + 时间序列 + 情景分析

**模拟能力**:
- P&L at Expiry: 经典 payoff diagram
- P&L Over Time: 从当前到到期日的价值演变
- What-If: Price / IV / Time 三维情景
- Probability Distribution: Monte Carlo 模拟
- Breakeven Analysis: 盈亏平衡点

**可借鉴点**:
1. 🎯 **情景分析矩阵** — 股价/基本面/情绪变化下的不同结果
2. 🎯 **蒙特卡洛模拟** — 用概率分布替代点估计

---

### 3.10 alphagbm-bps-backtest — Bull Put Spread 回测

**功能概述**: 8 年历史数据的 BPS 策略 walk-forward 回测

**双轨回测**:
- With Signal: 仅 FearScore ≥ 60 时入场
- No Signal (Control): 每周一无条件入场

**参数化**:
| Param | Default | Range |
|-------|---------|-------|
| dte_target | 14 | 7-45 |
| short_delta | 0.25 | 0.15-0.35 |
| spread_width | 5.0 | 2-10 |
| take_profit_pct | 0.50 | 0.20-0.80 |
| fear_threshold | 60 | 40-80 |

**回测结果**:
- QQQ FearScore ≥ 60: 年化 +10.8%, 胜率 100%, 最大回撤 0%
- 无信号对照: 年化 +3.5%, 胜率 82%
- **信号版本 α 是对照组的 3 倍**

**可借鉴点**:
1. 🎯 **信号有效性验证** — 用历史回测证明评分的预测能力
2. 🎯 **双轨对比设计** — 信号版 vs 对照版，量化信号的价值
3. 🎯 **参数化回测** — 用户可以调整参数看不同策略表现
4. 🎯 **Walk-forward** — 避免过拟合的滚动回测方法

---

## 四、市场情绪与宏观类 Skill（4个）

### 4.1 alphagbm-market-sentiment — 市场情绪仪表盘

**功能概述**: 市场级情绪指标聚合 + 当前环境分类

**指标**:
| Indicator | 描述 |
|-----------|------|
| VIX Level + Percentile | 当前 VIX 及过去一年分位 |
| Put/Call Ratio | 股权+指数 P/C 比 |
| Fear & Greed Index | 综合情绪指数 (0-100) |
| Market Breadth | 涨跌比 + 新高新低 |
| Sector Rotation Stage | 经济周期阶段映射 |
| Regime Classification | risk-on / risk-off / neutral |

**可借鉴点**:
1. 🎯 **市场大环境板块** — 报告开头可以增加市场整体情绪判断
2. 🎯 **板块轮动分析** — 当前处于经济周期的哪个阶段，哪些板块受益

---

### 4.2 alphagbm-vix-status — VIX 状态

**功能概述**: VIX 五层温度计 + 期权卖方策略提示

**五层体系**:
| Tier | VIX | Color | 卖方操作 |
|------|-----|-------|---------|
| Calm | < 15 | 🔵 | 权利金薄，买保护 |
| Normal | 15-20 | 🟢 | 日常 Sell Put / BPS |
| Seller Sweet Spot | 20-25 | 🟡 | BPS 权利金肥厚，积极开仓 |
| Caution | 25-35 | 🟠 | 减半仓位，VIX 爆炸风险 |
| Extreme Fear | ≥ 35 | 🔴 | 只买股票抄底 |

**额外输出**:
- mean_1y, percentile_1y
- distribution_1y_pct: 过去一年在各 tier 的时间占比

**可借鉴点**:
1. 🎯 **离散化分级** — 将连续数值映射为有限的操作指导
2. 🎯 **历史分布** — 不仅看当前值，还看在历史中的位置
3. 🎯 **双语输出** — 中英文策略提示同时返回

---

### 4.3 alphagbm-fear-score — 恐慌指数

**功能概述**: 单只股票的六维恐慌评分 (0-100)，≥60 触发 BPS 入场信号

**六维加权**:
| Indicator | Weight | Source |
|-----------|--------|--------|
| VIX level | 20% | 全局恐惧底 |
| IV Rank | 25% | 单票期权溢价 |
| RSI-14 | 15% | 超卖强度 |
| Volume anomaly | 15% | 量 vs 5 日均 |
| Put/Call ratio | 15% | 看跌持仓偏斜 |
| Consecutive down | 10% | 连跌天数 |

**回测证据**: 146 笔 BPS 交易中，FearScore ≥ 60 入场的年化 ROC ~10.8%，无条件入场的 ~3.5%，**3 倍 α**。

**缺失数据处理**: 缺失输入回退到 neutral values，标注 fallback flag，endpoint 永不 500。

**可借鉴点**:
1. ✅ **多维度恐慌评分** — 已部分借鉴到我们的 Risk Score
2. 🎯 **明确的信号阈值** — ≥60 = 入场信号，规则清晰
3. 🎯 **回测验证** — 每个评分体系都有历史回测支撑
4. 🎯 **缺失数据优雅降级** — fallback 机制保证系统鲁棒性

---

### 4.4 alphagbm-macro-view — 宏观指标追踪

**功能概述**: 用户自选宏观指标追踪 + 对持仓的影响分析

**指标库**:
| Key | 含义 | 影响 |
|-----|------|------|
| VIX | 波动率指数 | 风险情绪、期权定价 |
| US10Y | 美债 10 年 | 贴现率、股债轮动 |
| US2Y | 美债 2 年 | 加息预期 |
| DXY | 美元指数 | 新兴市场/商品/跨国公司 |
| GOLD | 黄金 | 对冲、实际利率反向 |
| OIL | 原油 | 通胀/能源 |
| BTC | 比特币 | 风险偏好 |
| HKD | 港币流动性 | 港股流动性信号 |

**impact_analysis**: AI 生成，引用用户具体持仓（"Your NVDA & TSLA positions are high-beta; consider..."）

**可借鉴点**:
1. 🎯 **宏观指标对持仓的影响分析** — 将宏观变化映射到具体持仓的风险/机会
2. 🎯 **自选指标面板** — 用户可自定义关注的宏观变量
3. 🎯 **变化方向标注** — ↑ red (VIX/yields up), ↓ green

---

## 五、研究知识库类 Skill（4个）

### 5.1 alphagbm-health-check — 知识库健康检查

**功能概述**: 周期性审计用户研究空间，0-100 健康评分

**检测维度**:
- **stale_profiles**: 超过 N 天未更新的档案
- **thesis_drift**: AI 检测原始论据是否不再成立
- **orphan_pages**: 无 thesis 的 profile / 无 profile 的 theme

**评分带**:
| Score | Band | 含义 |
|-------|------|------|
| 90-100 | Excellent | 无紧急事项 |
| 75-89 | Good | 轻微过期 |
| 60-74 | Fair | 多个档案需刷新，部分漂移 |
| 40-59 | Poor | 显著漂移/孤儿页 |
| 0-39 | Critical | 知识库大部分过期 |

**Recommendation 类型**:
- refresh → 刷新数据
- review_thesis → 审核论据
- archive → 归档
- create_thesis → 补充论据

**可借鉴点**:
1. 🎯 **数据新鲜度监控** — 自动检测采集数据是否过期
2. 🎯 **论据漂移检测** — 当基本面变化时提醒重新审视结论
3. 🎯 **健康评分体系** — 量化知识库的整体状态
4. 🎯 **分层权限** — 基础版自动周报，Pro 版可即时触发

---

## 六、交易工具类 Skill（4个）

### 6.1 alphagbm-alert — 智能警报

**警报类型**:
| Type | 描述 |
|------|------|
| IV Rank Threshold | IV Rank  crossing threshold |
| Price Level | 突破支撑/阻力/自定义价位 |
| Unusual Activity | 异常期权流 |
| Earnings Approaching | N 天前提醒 |
| VRP Signal Change | 波动率风险溢价翻转 |
| One-Time vs Recurring | 一次性/循环警报 |

**可借鉴点**:
1. 🎯 **条件触发系统** — 当某个指标 crossing 阈值时自动通知
2. 🎯 **循环 vs 一次性** — 不同场景的不同警报模式

---

### 6.2 alphagbm-watchlist — 自选股监控

**功能**:
- 自定义 watchlist + 默认 "Hot Options" 列表
- 价格异动标记 (gap up/down, breakout, breakdown)
- IV Rank 穿越标记 (上穿 80 / 下穿 20)
- 异常活动标记
- 财报临近提醒 (7 天内)
- 优先级排序

**可借鉴点**:
1. 🎯 **多维度异动检测** — 价格/波动/活动/事件四维监控
2. 🎯 **优先级排序** — 多条通知按重要性排序

---

### 6.3 alphagbm-unusual-activity — 异常活动检测

**检测信号**:
| Signal | 描述 |
|--------|------|
| Volume/OI Ratio | 今日量远超持仓量 = 新开仓 |
| Block Trade | 单笔大额 (100+ 合约) |
| Sweep Order | 跨交易所急单 = 紧迫性 |
| Premium Flow | Call vs Put 净权利金流向 |
| Sentiment Classification | bullish sweep / bearish block / hedging / earnings |
| Historical Accuracy | 过去类似信号的方向预测准确率 |

**可借鉴点**:
1. 🎯 **异常检测模式** — 量/价/持仓的交叉异常识别
2. 🎯 **历史准确率追踪** — 每个信号类型都有命中统计

---

### 6.4 alphagbm-polymarket — 预测市场集成

**功能**: 将 Polymarket 预测市场概率与期权隐含概率对比，发现定价错误

**核心概念**:
- Event Probability (预测市场)
- Options-Implied Probability (期权市场)
- Probability Spread = 两者差距
- Arbitrage Signal: spread > threshold

**可借鉴点**:
1. 🎯 **多源数据交叉验证** — 不同市场的同一事件定价对比
2. 🎯 **定价错误发现** — 当两个信息源给出显著不同的概率时，可能存在机会

---

## 七、整体架构设计借鉴

### 7.1 API 设计模式

AlphaGBM 的 API 设计非常规范，值得我们借鉴：

1. **双模式接口**: `sync` + `async`
   - 同步: 阻塞，适合快速查询 (< 5s)
   - 异步: 返回 task_id，适合重计算 (> 10s)

2. **配额分层**:
   - Free: 基础配额，足够体验
   - Plus: 10x 配额
   - Pro: 50x 配额 + 高级功能

3. **缓存策略**:
   - 实时数据: 无缓存
   - 计算结果: 5min in-process + 30day DB cache
   - 历史数据: 永久缓存

4. **降级处理**:
   - 缺失数据回退到 neutral values
   - fallback flag 标注
   - endpoint 永不 500

5. **compact 模式**:
   - `?compact=true` 返回 LLM 友好的精简输出 (~500 tokens)
   - 默认返回完整人类可读输出

### 7.2 Skill 触发机制

每个 Skill 有明确的触发关键词：
```yaml
description: |
  Triggers: "analyze AAPL", "what do you think about NVDA", 
  "should I buy TSLA", "stock analysis for META"
```

**借鉴**: 我们的报告系统可以设计类似的触发词，让用户通过自然语言获取分析。

### 7.3 相关 Skill 网络

每个 Skill 底部都有 Related Skills 表格：
```
| Skill | Relevance |
|-------|-----------|
| alphagbm-stock-analysis | 单股深度分析 |
| alphagbm-options-score | 期权评分 |
```

**借鉴**: 我们的模块之间也可以建立显式的关联关系，形成分析 pipeline。

### 7.4 Mock Data 体系

每个 Skill 都有 mock-data，支持 5 个 demo ticker (AAPL, NVDA, SPY, TSLA, META)：
```
mock-data/
  AAPL.json — 完整股票+期权快照
  fear-score/
    example-calm.json
    example-signal-triggered.json
```

**借鉴**: 我们的系统也可以准备 mock 数据，用于无 API key 的演示和测试。

---

## 八、对我们系统的具体借鉴建议（按优先级）

### P0: 立即可以实现的

1. **Risk Score 加法模型完善**
   - 当前 `_risk_score_section` 较简单，可借鉴 AlphaGBM 的 5 维度加法模型
   - 加入: PE > 60 (+2), Growth < -10% (+2), Volume low (+2), VIX > 30 (+1.5), Price < MA200 (+1)
   - 映射到仓位建议: Risk 0-2 → 20%仓位, 8-10 → 不买

2. **Target Price 多方法加权**
   - 当前只用一致预期 EPS，可加入 PE/PEG/DCF/技术面
   - 行业加权平均，高风险调整 -15%

3. **ATR Stop-Loss 板块**
   - `stop = price - ATR(14) × multiplier`
   - Multiplier 根据 Beta 和 VIX 动态调整

4. **compact 输出模式**
   - 为 LLM 消费设计精简版输出 (~500 tokens)
   - 保留完整版供人类阅读

### P1: 中短期可以实现的

5. **PE/PB Band 历史百分位**
   - 8 年 PE 历史，当前百分位
   - "PE 64.7, 位于过去 8 年 85th percentile → 偏贵"

6. **Financial Red Flags 规则引擎**
   - 用财报数据自动检测: 连续两季营收下滑、毛利率恶化、现金流转负等
   - 规则可配置，severity 分级

7. **Thesis 管理框架**
   - 买入理由 + 结构化卖出条件
   - 自动监控条件是否触发
   - 论据漂移检测

8. **持仓组合对比页**
   - 6 只股票的五维度横向对比
   - 每维度 Winner 标注
   - 组合层面主题总结

9. **数据新鲜度监控**
   - 每份数据标注采集时间
   - 过期数据自动提醒刷新
   - 知识库健康评分

10. **情景分析矩阵**
    - 如果股价 +10% / -10%，报告结论如何变化
    - 如果 EPS 预期上调/下调，估值如何变化

### P2: 长期方向

11. **策略回测框架**
    - 回测我们的评分体系在历史数据中的预测能力
    - 双轨对比: 信号版 vs 对照版
    - Walk-forward 避免过拟合

12. **分级止盈策略建议**
    - 根据股票波动率类型推荐不同止盈方案
    - 高波动股 (黑芝麻): 分级止盈
    - 低波动股 (长春高新): 长期持有

13. **宏观指标影响分析**
    - 美债利率、汇率、大宗商品对持仓的影响
    - AI 生成 impact_analysis，引用具体持仓

14. **异常检测系统**
    - 个股价格/成交量/情绪的异常偏离检测
    - 跨市场信息交叉验证

15. **主题研究框架**
    - 按产业主题分组持仓
    - 主题级新闻聚合和 AI 总结
    - 主题动态追踪

---

## 九、数据模型参考

### AlphaGBM 单票完整数据结构 (mock-data/AAPL.json)

```json
{
  "ticker": "AAPL",
  "stock": {
    "price", "change_pct", "volume", "avg_volume_20d",
    "market_cap_b", "pe_ratio", "forward_pe", "peg_ratio",
    "dividend_yield", "beta", "52w_high", "52w_low",
    "rsi_14", "macd_signal", "sma_50", "sma_200",
    "sector", "industry"
  },
  "options": {
    "iv_30d", "iv_60d", "iv_90d", "hv_20d", "hv_60d",
    "vrp", "iv_rank", "iv_percentile", "put_call_ratio",
    "skew_25d", "next_earnings", "days_to_earnings",
    "term_structure": [{"expiry", "dte", "atm_iv"}],
    "vol_surface": [{"expiry", "strikes": [{"strike", "moneyness", "call_iv", "put_iv"}]}],
    "chain_sample": [{"expiry", "type", "strike", "bid", "ask", "last", "volume", "oi", "iv", "delta", "gamma", "theta", "vega", "score", "score_breakdown"}],
    "strategies": [{"name", "legs", "max_profit", "max_loss", "breakeven", "pop", "risk_reward_ratio", "recommendation_score"}]
  },
  "earnings_history": [{"date", "iv_before", "iv_after", "crush_pct", "move_pct", "implied_move"}],
  "unusual_activity": [{"date", "type", "strike", "expiry", "volume", "oi", "vol_oi_ratio", "premium", "sentiment"}],
  "gbm_analysis": {
    "overall_score", "signal", "pillars": {"fundamental", "technical", "sentiment", "flow", "valuation"},
    "risk_level", "risk_factors", "target_price", "recommendation"
  },
  "market_sentiment": {"vix", "vix_percentile", "fear_greed_index", "fear_greed_label", "spy_put_call", "sector_rotation", "market_breadth"}
}
```

### 与我们系统的数据映射

| AlphaGBM 字段 | 我们已有 | 缺失 |
|--------------|---------|------|
| stock.price | ✅ 腾讯行情 | |
| stock.pe_ratio | ✅ 腾讯行情 | |
| stock.forward_pe | ✅ 一致预期 EPS 计算 | |
| stock.peg_ratio | ✅ 已计算 | |
| stock.beta | ❌ | 需从 akshare 获取 |
| stock.rsi_14 | ✅ TechnicalCollector | |
| stock.macd_signal | ✅ TechnicalCollector | |
| stock.sma_50/200 | ✅ TechnicalCollector | |
| options.iv_rank | ❌ | A股无期权数据 |
| options.put_call_ratio | ❌ | A股无期权数据 |
| earnings_history | ❌ | 可从 akshare 获取 |
| unusual_activity | ❌ | A股无期权流 |
| gbm_analysis.pillars | ✅ 五维度评分 | |
| gbm_analysis.risk_level | ⚠️ 简单版 | 可完善 |
| gbm_analysis.target_price | ✅ 一致预期 | 可扩展多方法 |
| market_sentiment.vix | ❌ | 美股指标 |

---

## 十、总结

AlphaGBM 的核心设计哲学:

1. **量化一切**: 每个判断都有数字支撑，每个数字都有历史回测
2. **结构化输出**: 复杂的分析被封装为有限的离散信号 (BUY/HOLD/AVOID, 5-tier VIX)
3. **场景化建议**: 不同的持仓状态/市场环境给出不同的操作建议
4. **知识库闭环**: Profile → Thesis → Health Check → Refresh，形成持续跟踪体系
5. **降级鲁棒**: 缺失数据不报错，fallback 到 neutral 并标注
6. **缓存分层**: 计算密集型结果全局缓存，实时数据即时获取
7. **双语原生**: 中英文输出同时维护，不是简单翻译

我们系统可以优先借鉴的方向:
- **立即**: Risk Score 完善、Target Price 多方法、ATR Stop-Loss
- **短期**: PE Band 历史、Red Flags 规则、Thesis 框架、组合对比
- **中期**: 回测验证、分级止盈、宏观影响、情景分析
- **长期**: 主题研究、异常检测、预测市场交叉验证
