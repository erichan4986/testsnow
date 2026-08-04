# Chapter 4 Sentence-Level Owner Delta: Codex Self-Review Round 1

## Verdict

`needs_revision`，修订后进入 Round 2。

## Findings

### R1 — Empty narrative would resurrect raw fallback

原设计说全部 parts 被隐藏后省略 narrative，但 renderer 将“没有 narrative”解释为需要回退到 verified rows，导致重复事实重新出现。

**修复：**完整 coverage 已验证但 parts 为空时保留内部 empty sentinel；renderer 在输出标题前跳过该 topic，只有真正缺少 narrative 时才 fallback。

### R2 — Equivalence rule was not executable enough

“高度相似”“更丰富”缺少确定阈值，实施者可能引入宽泛 fuzzy deletion。

**修复：**锁定保护条件、containment 方向、`0.92` similarity 和 `1.10` external-length ceiling；新增 anchor、metric、time 或 event 一律保留。

### R3 — Formal-thin offset proof was underspecified

仅检查引用有效不足以证明 hidden ref 没有压缩后续编号。

**修复：**测试必须隐藏一个较早 external ref，并断言后续可见 ref 仍使用 full-snapshot 原编号。

### R4 — 4.4 material ownership was ambiguous

如果直接裁剪 `external_material_rows`，4.4 的条件推演材料会被显示层反向改变。

**修复：**原 rows 继续供 4.4 和既有消费者使用；仅 4.3 narrative projection 过滤 owner-equivalent parts。

## Scope Check

仍限定两个 runtime 文件和两个测试文件；不需要修改 producer、pack、quality gate 或 topic taxonomy。
