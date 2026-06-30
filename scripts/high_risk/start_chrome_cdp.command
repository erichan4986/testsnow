#!/bin/bash
# 启动 Chrome 并开启远程调试端口（CDP 模式）
# macOS 双击运行

cd "$(dirname "$0")/../.."
CHROME_APP="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
USER_DATA_DIR="$HOME/Library/Application Support/Google/Chrome"
CDP_PORT=9222

echo "=========================================="
echo "  启动 Chrome CDP 模式"
echo "=========================================="
echo ""

# 检查 Chrome 是否已运行
if pgrep -x "Google Chrome" > /dev/null; then
    echo "⚠️  Chrome 正在运行，需要先关闭所有 Chrome 窗口"
    echo ""
    read -p "按回车键自动关闭 Chrome，或按 Ctrl+C 取消..."
    killall "Google Chrome" 2>/dev/null
    sleep 2
fi

# 复制 profile 到临时目录（CDP 需要非默认数据目录）
TMP_PROFILE=$(mktemp -d /tmp/chrome_cdp_profile.XXXXXX)
echo "📁 复制 Chrome profile 到临时目录: $TMP_PROFILE"
echo ""

cp -r "$USER_DATA_DIR"/* "$TMP_PROFILE/" 2>/dev/null || true

# 移除锁文件
rm -f "$TMP_PROFILE/SingletonLock" "$TMP_PROFILE/SingletonSocket" "$TMP_PROFILE/SingletonCookie" 2>/dev/null

echo "正在启动 Chrome（CDP端口: $CDP_PORT）..."
echo ""
echo "启动后请："
echo "  1. 在 Chrome 中访问 https://xueqiu.com"
echo "  2. 登录雪球账号（如果未自动登录）"
echo "  3. 登录完成后，在终端运行: python3 scripts/high_risk/batch_fetch_quality_posts.py"
echo ""
echo "=========================================="
echo ""
read -p "按回车键启动 Chrome..."

# 启动 Chrome
"$CHROME_APP" \
    --remote-debugging-port=$CDP_PORT \
    --remote-debugging-address=0.0.0.0 \
    --user-data-dir="$TMP_PROFILE" \
    --no-first-run \
    --no-default-browser-check \
    "about:blank"
