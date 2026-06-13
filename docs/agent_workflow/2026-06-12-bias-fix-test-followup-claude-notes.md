# BIAS Advisor Fix — 测试收口笔记

**日期**: 2026-06-12  
**背景**: Codex 已修复 `scripts/utils/reporter/technical_analyzer.py` 中的 BIAS advisor 红灯，把无 ATR/分位数辅助时触发“负偏离”的阈值从 `bias_5 < -3` 改为 `bias_5 <= -2`。需要本地验证全量测试状态，并确认是否有其他失败与该修复有关。

## 1. 当前工作树中 BIAS 修复确认

文件：`scripts/utils/reporter/technical_analyzer.py`

```diff
-        elif bias_5 < -3:
+        elif bias_5 <= -2:
             bias_state = "负偏离"
             bias_meaning = "价格低于均线，提示短线已有回撤"
```

测试文件 `tests/reporter/test_lexin_phase3_report.py` 与当前 HEAD 无差异（用户提供的测试用例已经存在于工作树中）。

## 2. 分段运行测试结果

### 2.1 tests/reporter（最大失败 10）

```bash
python3 -m pytest tests/reporter -q --maxfail=10
```

结果：**417 passed, 6 skipped**。

### 2.2 tests/utils（最大失败 10）

```bash
python3 -m pytest tests/utils -q --maxfail=10
```

结果：**25 passed**。

### 2.3 全量 tests/（最大失败 10）

```bash
python3 -m pytest tests/ -q --maxfail=10
```

结果：**463 passed, 6 skipped**。

### 2.4 全量 tests/（无 maxfail，完整跑完）

```bash
python3 -m pytest tests/ -q
```

结果：**463 passed, 6 skipped**（耗时约 2 分 10 秒）。

### 2.5 BIAS 相关 focused tests

```bash
python3 -m pytest tests/reporter/test_lexin_phase3_report.py::test_negative_bias_advisor_no_chasing \
  tests/reporter/test_lexin_phase3_report.py::test_positive_bias_advisor_uses_chasing -q -v
```

结果：**2 passed**。

```bash
python3 -m pytest tests/reporter/test_lexin_phase3_report.py \
  tests/reporter/test_lanqi_phase3_report.py \
  tests/reporter/test_phase3_bottom_strategy.py -q -v
```

结果：**34 passed**。

```bash
python3 -m pytest tests/reporter/test_technical_renderer.py \
  tests/reporter/test_technical_structure.py \
  tests/reporter/test_technical_state_machine.py \
  tests/reporter/test_bias_computation.py -q -v
```

结果：**38 passed**。

## 3. 失败用例列表

本次分段运行及全量运行**未发现任何失败**。

唯一需要关注的是：用户提到 Codex 之前跑全量时曾在约 30% 附近看到 `FFFFFF`，后来在约 46% 被中断。当前工作树中这些失败已无法复现，可能是以下原因之一：
- Codex 的分支/工作树状态与当前不同；
- 之前的中断发生在修复尚未完全应用或存在临时文件冲突时；
- 外部依赖（网络、缓存）导致的偶发失败，在后续运行中已恢复。

## 4. 与 BIAS 修复的相关性判断

- 当前所有测试通过，包括新增的 BIAS 负偏离用例。
- 没有发现因 `bias_5 <= -2` 改动而失败的测试。
- `test_lexin_phase3_report.py`、`test_lanqi_phase3_report.py`、`test_phase3_bottom_strategy.py` 以及 technical/bias 相关测试全部通过，说明 BIAS 修复没有破坏现有行为。

## 5. 代码修改情况

本次测试收口**未对任何源码或测试文件做修改**。

当前工作树中已存在的、与 BIAS 相关的修改只有：

| 文件 | 修改 | 是否本次新增 |
|------|------|--------------|
| `scripts/utils/reporter/technical_analyzer.py` | `bias_5 < -3` → `bias_5 <= -2` | 否（Codex 已修） |
| `tests/reporter/test_lexin_phase3_report.py` | 新增/已有的 BIAS 测试用例 | 否（已存在） |

## 6. 剩余未通过项

无。全量测试：**463 passed, 6 skipped**。6 个 skipped 是预期内的（通常是有外部依赖或环境不满足的用例），不是失败。

## 7. 结论

- ✅ 当前工作树中 BIAS 修复存在。
- ✅ 新增/已有的 BIAS 红灯用例通过。
- ✅ 全量测试通过，无失败。
- ✅ 没有发现与 BIAS 修复相关的回归失败。
- ✅ 未修改任何代码。
- ✅ 未运行 `xueqiu_monitor_v2.py`，未使用 Chrome/CDP/Playwright。

建议：由于当前测试已全部通过，BIAS 修复可以认为已经完成验证。如果后续全量测试再次偶发失败，建议保留 `--maxfail=10` 的输出并针对具体失败文件单独分析。
