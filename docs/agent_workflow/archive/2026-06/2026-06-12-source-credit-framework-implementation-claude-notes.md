# Source Credit Framework Phase 1 — Implementation Notes

**日期**: 2026-06-12  
**任务**: 实现 Source Credit Framework Phase 1，仅新增 source-credit 评分模块并在 AgentReachAdapter 中注入 metadata，不扩大范围。

## 1. 改动文件

| 文件 | 变更摘要 |
|------|----------|
| `scripts/utils/source_credit.py` | **新增**。定义 `SourceCreditResult` frozen dataclass 与纯函数 `score_source_credit()`；实现 URL 归一化、检测优先级、9 级来源信用分层。 |
| `scripts/utils/source_adapter.py` | **修改**。`AgentReachAdapter.to_synthesis_item()` 调用 `score_source_credit()` 并将结果追加到 `extra` 字典，保留原有 `"raw"` 字段；未改 `SynthesisItem` 构造签名。 |
| `tests/utils/test_source_credit.py` | **新增**。TDD 测试：来源分层、URL 归一化、检测优先级冲突、metadata reason、结果不可变性、adapter 集成。 |
| `tests/utils/test_source_adapter.py` | **修改**。新增/扩展现有 Agent-Reach 适配测试，断言 `extra` 同时包含 `"raw"` 与全部 source-credit 字段。 |
| `docs/agent_workflow/2026-06-12-source-credit-framework-implementation-claude-notes.md` | **新增**（本文档）。 |

## 2. Source Type / Credit Policy

按设计文档优先级实现：

```text
exchange_announcement > company_ir > company_official > broker_research
> mainstream_media > industry_media > social_discussion > unknown_web > missing_source
```

| Source Type | Credit | Verification | Knowledge | Report | 检测依据 |
|---|---|---:|---|---|---|
| `exchange_announcement` | 98 | `primary_source` | ✅ | ✅ | `hkexnews.hk`, `sse.com.cn`, `szse.cn`, `cninfo.com.cn` |
| `company_ir` | 88 | `primary_source` | ✅ | ✅ | URL 路径 `/ir/`, `/investor/`, `/announcement/` 或 `raw.source_type == "ir"` |
| `company_official` | 85 | `primary_source` | ✅ | ✅ | `blacksesame.com`, `blacksesame.com.cn` |
| `broker_research` | 72 | `professional_analysis` | ✅ | ✅ | `source_platform="研报"`, `raw.source_type="research"`, 或 `raw.institution` |
| `mainstream_media` | 65 | `secondary_source` | ✅ | ✅ | `eastmoney.com`, `sina.com.cn`, `stcn.com`, `yicai.com`, `caixin.com` |
| `industry_media` | 55 | `secondary_source` | ✅ | ❌ | `36kr.com`, `jiemian.com`, `leiphone.com` |
| `social_discussion` | 35 | `market_opinion` | ✅ | ❌ | 知乎/雪球/Twitter/X/Reddit/Bilibili/微博/小红书（中英文别名） |
| `unknown_web` | 30 | `unverified` | ✅ | ❌ | 有 URL 但无已知分类 |
| `missing_source` | 10 | `unverified` | ❌ | ❌ | 无 URL、无平台、无来源元数据 |

关键冲突规则：
- **URL 优先于 platform**：`source_platform="知乎"` + `blacksesame.com` URL → `company_official`
- **raw `source_type="ir"` 优先于普通 URL**：即使域名普通 → `company_ir`
- **`is_official=True` 不升级未知域名**：`unknown_web` 保持不变
- **空 URL + social platform** → `social_discussion`
- **`user_provided_url=True` 只在官方域名添加 reason**，不改变未知域名评分

## 3. URL 归一化

`score_source_credit()` 内部对 URL 做：
- 接受有/无 scheme
- host 转小写
- 去掉 `www.` 前缀
- 忽略 query/fragment
- 包含空格或不是合法域名的字符串返回空 domain

## 4. 测试结果

运行命令：

```bash
python3 -m pytest tests/utils/test_source_credit.py tests/utils/test_source_adapter.py tests/reporter/test_agent_reach_quality_skill.py -q
```

结果：**79 passed**。

新增/覆盖的关键测试：
- Black Sesame 官网 URL → `company_official`, credit ≥ 80
- HKEX / SSE / SZSE / CNINFO → `exchange_announcement`, credit ≥ 95
- `/ir/` 路径与 `raw.source_type="ir"` → `company_ir`
- 知乎/雪球/Twitter/X/Reddit/Bilibili/微博/小红书 → `social_discussion`
- 研报/research/institution → `broker_research`
- 东方财富/新浪财经/证券时报/第一财经/财新 → `mainstream_media`
- 36kr/界面/雷锋网 → `industry_media`
- 未知 URL → `unknown_web`
- 无来源 → `missing_source`
- 用户显式提供官网 URL 添加 reason，但不提升未知域名
- Adapter 集成：`extra` 同时含 `raw` 与 source-credit 字段

## 5. 是否偏离设计

- **无偏离**。完全按设计文档与 review notes 实现。
- 额外注意点：`_is_social()` 未读取 `raw["platform"]`，因为 Agent-Reach 的 `raw["platform"]` 是 connector 平台（如 `web` / `twitter`），不是内容平台。读取它会把无 URL 的 Agent-Reach 记录误标为 social。当前实现仅使用 `source_platform`、URL domain 和 `raw.source_type`。

## 6. git status 摘要（本次相关）

```text
 M scripts/utils/source_adapter.py
 M tests/utils/test_source_adapter.py
?? scripts/utils/source_credit.py
?? tests/utils/test_source_credit.py
?? docs/agent_workflow/2026-06-12-source-credit-framework-implementation-claude-notes.md
```

其他 `M`/`??` 文件均来自之前的工作，非本次 Source Credit Framework Phase 1 产生。

## 7. 是否触碰禁止文件

**未触碰**任何禁止文件：
- ❌ `scripts/utils/report_skills/agent_reach_quality_skill.py`
- ❌ `scripts/utils/report_skills/agent_reach_skill.py`
- ❌ `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- ❌ `scripts/utils/knowledge_synthesizer.py`
- ❌ `scripts/utils/reporter/scoring_engine.py`
- ❌ technical analyzer / technical modules
- ❌ report templates
- ❌ `scripts/run_黑芝麻智能.py`
- ❌ `scripts/xueqiu_monitor_v2.py`
- ❌ `config/stocks.json`
- ❌ `knowledge/` 目录
- ❌ `reports/` 目录

## 8. 对下游行为的影响

- `AgentReachAdapter` 只向 `extra` 追加新的 metadata 字段，不删除、不修改原有 `raw` 字段。
- `SynthesisItem` 构造签名未变，所有现有适配器行为不变。
- `agent_reach_quality_skill.py` 仍只读 `item.extra["raw"]`，未感知新字段，行为不变。
- `AgentReachEvidenceRenderer` 未读取 `extra`，行为不变。
- 未进入 LLM synthesis、评分、技术分析、报告结论。
- Source-credit 当前是 **inert metadata**，仅供后续 evidence note / claim verification 阶段消费。

## 9. 限制与后续扩展点

- 公司官方域名目前仅硬编码 `blacksesame.com` / `blacksesame.com.cn`；Phase 2 可改为从 stock config 注入。
- `mainstream_media` / `industry_media` 域名列表为初始集合，后续可扩展。
- `author` 字段当前保留但未参与评分，未来可叠加作者可信度权重。
- `source_domain` 已显式输出，便于后续按域名聚类、交叉验证。
