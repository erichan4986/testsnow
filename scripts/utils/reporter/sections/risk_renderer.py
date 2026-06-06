"""风险评分板块渲染器。"""

from typing import Any, Dict, List, Optional


class RiskRenderer:
    """综合风险评分板块 — 风险因子 + 关注要点 + 行业特有风险。"""

    @staticmethod
    def required_keys() -> List[str]:
        return ["stock_name", "all_posts"]

    def render(self, ctx: Dict[str, Any]) -> str:
        stock_name = ctx.get("stock_name", "")
        all_posts = ctx.get("all_posts", [])
        if not stock_name or not isinstance(all_posts, list):
            return ""

        stock_raw = ctx.get("stock_raw", {})
        quote = ctx.get("quote")
        consensus = ctx.get("consensus")
        ind_fwd_pe = ctx.get("industry_fwd_pe")
        synthesis_text = ctx.get("synthesis_text", "")

        # 行业特有风险表
        try:
            from ..scoring_engine import industry_specific_risk_table
        except ImportError:
            try:
                import sys
                from pathlib import Path
                utils_dir = Path(__file__).parent.parent.parent
                if str(utils_dir) not in sys.path:
                    sys.path.insert(0, str(utils_dir))
                from reporter.scoring_engine import industry_specific_risk_table
            except Exception:
                industry_specific_risk_table = lambda s: ""

        specific_risk = industry_specific_risk_table(stock_name)

        # 综合风险评分
        try:
            from ..scoring_engine import risk_score_section
        except ImportError:
            try:
                import sys
                from pathlib import Path
                utils_dir = Path(__file__).parent.parent.parent
                if str(utils_dir) not in sys.path:
                    sys.path.insert(0, str(utils_dir))
                from reporter.scoring_engine import risk_score_section
            except Exception:
                risk_score_section = None

        watch_points_md = ""
        if risk_score_section:
            watch_points_md = risk_score_section(
                stock_name=stock_name,
                posts=all_posts,
                stock_raw=stock_raw,
                quote=quote,
                consensus=consensus,
                industry_fwd_pe=ind_fwd_pe,
                watch_points_md="",
                synthesis_text=synthesis_text,
            )

        # 预定义的风险提示与关注要点
        risk_analyses = self._risks_and_watch(stock_name, all_posts)

        parts = []
        if specific_risk:
            parts.append(specific_risk)
        if watch_points_md:
            parts.append(watch_points_md)
        if risk_analyses:
            parts.append(risk_analyses)

        return "\n\n".join(parts)

    def _risks_and_watch(self, stock_name: str, posts: List[Dict]) -> str:
        """风险提示与关注要点（预定义内容）。"""
        risk_analyses = {
            "黑芝麻智能": """## 风险提示与关注要点

### 🔴 核心风险

1. **港股通退通风险（极高）**
   当前市值约120亿港币，若股价跌至10港币附近（市值约65亿），将触发港股通退通机制。退通后大陆投资者只能卖不能买，流动性将急剧萎缩。

2. **做空机制不对称风险（高）**
   港股通持股比例越高，外资可借出的做空筹码越多。即使港股通把流通股包圆了（甚至持股120%），空头依然能借出券来砸盘。

3. **量产进度不及预期（中高）**
   管理层指引2026年收入增长80%，但智驾芯片的客户导入周期较长，比亚迪等头部客户的订单节奏存在不确定性。

### 📅 下周关注要点

- 股价是否守住15港币关键支撑位
- 公司是否有回购公告（显示管理层对股价的信心）
- 是否有新的主机厂客户定点公告
- 港股通持股比例变化""",

            "长春高新": """## 风险提示与关注要点

### 🔴 核心风险

1. **融资盘连环爆仓风险（极高）**
   社区大量投资者反映已在爆仓边缘。如果股价继续下跌触发强制平仓，可能形成"下跌→平仓→更跌"的死亡螺旋。

2. **金赛药业增长失速风险（高）**
   生长激素面临集采+竞品（特宝生物）双重挤压。如果季度环比增长无法维持5%，估值体系将进一步崩塌。

3. **管理层信任危机（中高）**
   金赛增成人适应症三期临床终止事件暴露出决策和沟通问题。如果类似事件再次发生，投资者信心将难以修复。

### 📅 下周关注要点

- 5月19日投资者关系活动后的市场反馈（是否有新的看空理由出现）
- 金赛药业6月销售数据
- 融资余额变化（反映杠杆资金态度）
- 特宝生物的医保谈判进展""",

            "三花智控": """## 风险提示与关注要点

### 🔴 核心风险

1. **短期涨幅过大回调风险（高）**
   机器人板块近期涨幅巨大，部分个股已透支未来1-2年的业绩增长。如果5-6月订单催化落空，可能面临20-30%的回调。

2. **特斯拉订单不及预期风险（中高）**
   三花的估值很大程度上建立在特斯拉机器人订单的预期上。如果量产进度延迟或订单量低于预期，股价支撑将动摇。

3. **拓普等竞品争夺份额风险（中）**
   拓普集团在执行器领域同样布局深厚，如果特斯拉选择多供应商策略，三花的份额可能被稀释。

### 📅 下周关注要点

- 特斯拉是否召开供应商大会或下发小批量订单
- 机器人板块整体资金流向（是否有获利了结迹象）
- 三花数据中心冷却业务是否有新客户公告
- 大盘系统性风险（如果大盘调整，高估值成长股承压更大）""",

            "中简科技": """## 风险提示与关注要点

### 🔴 核心风险

1. **Q2订单继续恶化风险（高）**
   Q1业绩暴雷后，如果Q2订单没有明显恢复，市场将彻底丧失对"季节性波动"解释的信任，股价可能再下台阶。

2. **单一大客户依赖风险（中高）**
   军工客户集中度极高，一旦主要客户调整采购计划或引入二供，业绩波动将非常剧烈。

3. **军工行业反腐/审计风险（中）**
   军工行业近年来加强审计和合规管理，部分项目的付款周期和订单节奏可能受到影响。

### 📅 下周关注要点

- 是否有新订单/合同公告（尤其是大额军工合同）
- 与科泰思创合作的具体落地进展
- 歼-35量产相关的产业链新闻
- 股东人数变化（如果继续下降，说明散户仍在离场）""",

            "圣邦股份": """## 风险提示与关注要点

### 🔴 核心风险

1. **短期涨幅过大获利回吐风险（高）**
   从年初至今涨幅已超过50%，90-100元区间积累了大量获利盘。一旦板块情绪降温，短期回调幅度可能达到15-20%。

2. **杰华特在MOS领域竞争风险（中高）**
   杰华特的DrMOS产品已通过更多客户认证，如果圣邦在高端功率器件上无法快速追赶，可能错失数据中心/AI服务器电源管理的市场机会。

3. **模拟芯片涨价周期提前结束风险（中）**
   当前模拟芯片行业正处于涨价周期，但如果下游需求（消费电子、汽车）不及预期，涨价可能无法持续。

### 📅 下周关注要点

- 能否站稳100元关口（心理关口+技术阻力位）
- 思瑞浦、杰华特等同业的股价走势（反映板块情绪）
- 是否有新的产品发布或客户导入公告
- 半导体行业整体资金流向""",

            "乐鑫科技": """## 风险提示与关注要点

### 🔴 核心风险

1. **量化资金控盘导致的流动性风险（中高）**
   量化策略的同质化可能导致"闪崩"——一旦某个触发条件被激活，多个量化策略同时卖出，可能在几分钟内造成大幅下跌。

2. **S31新品量产进度不及预期风险（中高）**
   S31被视为乐鑫下一代核心产品，如果导入期延长或客户认证受阻，2026年的收入增长可能不及预期。

3. **"低端芯片"标签难以摘除风险（中）**
   市场对乐鑫的认知仍停留在"Wi-Fi模块芯片商"，如果端侧AI应用迟迟不出现爆款，估值重构将缺乏催化剂。

### 📅 下周关注要点

- S31芯片是否有新的客户导入或量产进展公告
- ESP32在AI开发者社区的热度变化（GitHub star数、教程数量等）
- 翱捷科技、全志科技等同业的业绩和股价表现
- 大盘成长股的整体情绪（乐鑫作为科创板标的，受市场风险偏好影响较大）""",
        }
        return risk_analyses.get(stock_name, "")
