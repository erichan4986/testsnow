# 华大九天 2025 年报全文 LLM Preview

## 目标

用当前 annual/semiannual standalone experimental path 对华大九天（301269）2025 年报做真实 LLM preview，验证新增 required metrics、required financial risk metrics、product/project/customer evidence backfill 对 EDA 公司是否适配。

## 输入与产物

- 年报缓存：`data/raw/periodic_reports/华大九天_2025_annual_jina.txt`
- Markdown 预览：`/tmp/huadajiutian_2025_annual_fulltext_summary.md`
- JSON 预览：`/tmp/huadajiutian_2025_annual_fulltext_summary.json`
- 证据审计：`/tmp/huadajiutian_2025_annual_fulltext_summary_audit.md`

## 关键结果

- 分产品必备指标已覆盖：
  - `EDA 软件销售`：收入 `107451.24万元`，收入同比 `-1.63%`，毛利率 `100.00%`
  - `技术服务`：收入 `20128.29万元`，收入同比 `74.93%`，毛利率 `44.64%`
- 分地区必备指标覆盖境内/境外。
- 客户集中度覆盖前五合计 `30.58%`、第一大 `18.68%`。
- 供应商集中度覆盖前五合计 `44.48%`、第一大 `17.30%`。
- 库存指标为空，符合 EDA 软件公司特征。
- product/project backfill 命中 EDA 语义：`数字`、`EDA`、`3DIC`、`PDK`、`ISO 26262`、`IEC 61508`，未出现射频/手机模组词错配。

## 质量观察

- 六段摘要能覆盖公司画像、主营业务、客户与订单、研发技术、管理层市场判断、财务风险。
- 风险清单包括收入确认、客户集中、资产减值、政府补助依赖、境外收入/贸易摩擦、现金流质量、关联方治理、供应商集中。
- `supplier_concentration` 语义更偏关联方采购与供应链独立性，而不是单纯高集中度；可以接受。
- 公司画像补充仍有通用句“渠道备货节奏”，对直销型 EDA 公司不够贴切，后续可优化为“客户项目节奏/授权续费节奏”。

## 本轮发现并修复

- `EDA 软件销售` 行因成本为 `0.00` 且缺少完整毛利率变化列，之前被分产品解析漏掉；已补充 compact 行解析增量测试和修复。
- 重复渲染旧 JSON 时，profile backfill 可能重复追加；已增加 section judgment 去重与幂等测试。
- `cash_flow_quality` / `profit_quality` 若 summary+mechanism 完全相同，已增加跨类型去重。

## 污染检查

- 未发现 `L-PAMiD`、`RedCap`、`AEC-Q104`、`UHB`、`Wi-Fi` 等非 EDA 公司词错配。
- 未发现 `[^...]` 非法引用。
- 未发现 `confirmed_fact` / `fact_candidate` 泄漏。
- 仅有说明性文本包含“核心事实”，用于声明不进入核心事实、评分或风险评分。

## 结论

华大九天样例验证通过。当前实验路径对 EDA 公司已能提取核心经营指标与产品/技术语义，且没有明显行业错配。进入 Source Intake 集成设计前，建议保留“仅 professional_analysis / source_credit=75 / 不进核心事实、不进评分、不进风险评分”的边界。
