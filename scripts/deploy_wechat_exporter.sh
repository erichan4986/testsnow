#!/bin/bash
# wechat-article-exporter 一键部署脚本
# 运行环境：macOS/Linux + Node.js 18+ + npm/yarn

set -e

PROJECT_DIR="${1:-$HOME/wechat-article-exporter}"
PORT="${2:-3006}"

echo "======================================"
echo "wechat-article-exporter 部署脚本"
echo "======================================"
echo ""

# 检查依赖
echo "[1/5] 检查环境..."
if ! command -v node &> /dev/null; then
    echo "错误: Node.js 未安装，请先安装 Node.js 18+"
    echo "  macOS: brew install node"
    echo "  Ubuntu: sudo apt install nodejs npm"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "错误: Node.js 版本过低 (当前: $(node --version)), 需要 18+"
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo "错误: git 未安装"
    exit 1
fi

echo "  Node.js: $(node --version)"
echo "  npm: $(npm --version)"
echo ""

# 克隆仓库
echo "[2/5] 克隆仓库..."
if [ -d "$PROJECT_DIR" ]; then
    echo "  目录已存在: $PROJECT_DIR"
    read -p "  是否删除并重新克隆? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$PROJECT_DIR"
    else
        echo "  使用现有目录"
    fi
fi

if [ ! -d "$PROJECT_DIR" ]; then
    git clone --depth=1 https://github.com/jooooock/wechat-article-exporter.git "$PROJECT_DIR"
fi

cd "$PROJECT_DIR"
echo ""

# 安装依赖
echo "[3/5] 安装依赖..."
if command -v yarn &> /dev/null; then
    yarn install
else
    npm install
fi
echo ""

# 配置代理（可选）
echo "[4/5] 代理配置..."
if [ ! -f "config/proxy.txt" ] && [ -f "config/proxy.txt.example" ]; then
    cp config/proxy.txt.example config/proxy.txt
    echo "  已创建代理配置文件 config/proxy.txt（当前为空，如需代理请编辑）"
else
    echo "  代理配置已存在或无需配置"
fi
echo ""

# 启动服务
echo "[5/5] 启动服务..."
echo ""
echo "======================================"
echo "部署完成!"
echo "======================================"
echo ""
echo "访问地址: http://localhost:$PORT"
echo ""
echo "使用方法:"
echo "  1. 打开浏览器访问 http://localhost:$PORT"
echo "  2. 使用微信扫描页面上的二维码"
echo "  3. 选择你的公众号进行登录（注意：必须使用公众号登录）"
echo "  4. 搜索你想导出的目标公众号"
echo "  5. 选择文章批量导出为 JSON 格式"
echo ""
echo "导出文件建议放置到: data/wechat/ 目录"
echo ""
echo "启动命令:"
echo "  cd $PROJECT_DIR && npm run dev"
echo ""

read -p "是否现在启动服务? (Y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo "正在启动..."
    npm run dev -- --port "$PORT"
fi
