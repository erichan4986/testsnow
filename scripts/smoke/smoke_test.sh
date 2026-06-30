#!/usr/bin/env bash
# Smoke test: 验证技术形态分析模块能端到端运行并输出含关键词的报告
# 不依赖外部网络，使用模拟数据，约 1-2 秒完成

set -e

cd "$(dirname "$0")/../.."
REPO_ROOT="$(pwd)"

echo "=== Smoke Test: Stock Report Generation ==="
echo "Repository: $REPO_ROOT"
echo ""

# Step 1: 运行已有的快速兼容性测试（验证 technical_analyzer 核心链路）
echo "[1/3] Running pytest technical e2e test (should take <1s)..."
python3 -m pytest tests/reporter/test_backward_compatibility.py -v --tb=short
echo ""

# Step 2: 生成一份实际的技术分析报告并检查关键词
echo "[2/3] Generating sample technical report and checking keywords..."

python3 << 'PYEOF'
import sys
from pathlib import Path

sys.path.insert(0, str(Path("scripts/utils/reporter").resolve()))
sys.path.insert(0, str(Path("scripts/utils/reporter/sections").resolve()))

import pandas as pd
import numpy as np
from technical_analyzer import analyze
from technical_renderer import TechnicalRenderer

np.random.seed(42)
close = [100.0]
for _ in range(149):
    close.append(close[-1] * (1 + 0.005 + np.random.normal(0, 0.005)))

df = pd.DataFrame({
    "close": close,
    "open": [c * 0.99 for c in close],
    "high": [c * 1.01 for c in close],
    "low": [c * 0.98 for c in close],
    "volume": [1000] * 150,
})

result = analyze(df)
res = result["resonance"]

ctx = {
    "stock_name": "测试股",
    "stock_raw": {"technical": {"indicators": {"_resonance": res}}},
    "chart_paths": {},
}
renderer = TechnicalRenderer()
output = renderer.render(ctx)

keywords = ["趋势", "日线", "周线", "评分", "可信度", "风险"]
found = [k for k in keywords if k in output]
missing = [k for k in keywords if k not in output]

print(f"  报告长度: {len(output)} 字符")
print(f"  找到关键词 ({len(found)}/{len(keywords)}): {found}")
if missing:
    print(f"  缺少关键词: {missing}")

report_dir = Path("reports")
report_dir.mkdir(exist_ok=True)
report_path = report_dir / "smoke_test_report.md"
report_path.write_text(output, encoding="utf-8")
print(f"  样例报告已保存: {report_path}")

if len(found) < 4:
    print("ERROR: 找到的关键词不足 4 个，smoke test 失败")
    sys.exit(1)

print("SUCCESS: 样例报告包含足够的关键词")
PYEOF

echo ""

# Step 3: 验证报告文件存在
echo "[3/3] Verifying report file exists..."
if [ -f "reports/smoke_test_report.md" ]; then
    echo "  报告文件已生成: reports/smoke_test_report.md"
    echo "  文件大小: $(wc -c < reports/smoke_test_report.md) 字节"
else
    echo "ERROR: 报告文件未生成"
    exit 1
fi

echo ""
echo "=== Smoke Test PASSED ==="
