#!/usr/bin/env bash
# wechat-article-exporter 部署助手
#
# 默认使用官方 Docker 镜像，适合本地私有化部署和人工导出公众号文章。
# 源码开发模式需要 Node.js 22+ 和 yarn。

set -euo pipefail

REPO_URL="${WECHAT_EXPORTER_REPO:-https://github.com/wechat-article/wechat-article-exporter.git}"
MIRROR_REPO_URL="${WECHAT_EXPORTER_MIRROR_REPO:-https://gitclone.com/github.com/wechat-article/wechat-article-exporter.git}"
IMAGE="ghcr.io/wechat-article/wechat-article-exporter:latest"
PROJECT_DIR="${WECHAT_EXPORTER_DIR:-$HOME/wechat-article-exporter}"
PORT="${WECHAT_EXPORTER_PORT:-3000}"
MODE="docker"
NO_START=0
RECLONE=0
USE_MIRROR=0

usage() {
    cat <<'EOF'
wechat-article-exporter 部署助手

用法:
  scripts/deploy_wechat_exporter.sh [options]

选项:
  --docker              使用 Docker 镜像部署（默认，推荐）
  --dev                 使用源码开发模式运行，需要 Node.js 22+ 和 yarn
  --project-dir PATH    数据/源码目录，默认 $HOME/wechat-article-exporter
  --port PORT           本地访问端口，默认 3000
  --repo-url URL        源码模式使用的 Git 仓库地址
  --mirror              源码模式优先使用 gitclone 镜像
  --reclone             源码模式下显式删除并重新克隆目录
  --no-start            只准备环境并打印启动命令，不启动服务
  -h, --help            显示帮助

说明:
  - 登录、搜索、同步和导出都在浏览器页面里由用户手动完成。
  - 不要把微信登录凭证、X-Auth-Key、导出原始数据提交到仓库。
  - 导出的 JSON/Markdown 建议放在本地临时目录，后续再由导入脚本清洗。
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --docker)
            MODE="docker"
            shift
            ;;
        --dev)
            MODE="dev"
            shift
            ;;
        --project-dir)
            PROJECT_DIR="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --repo-url)
            REPO_URL="$2"
            shift 2
            ;;
        --mirror)
            USE_MIRROR=1
            shift
            ;;
        --reclone)
            RECLONE=1
            shift
            ;;
        --no-start)
            NO_START=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "未知参数: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

echo "======================================"
echo "wechat-article-exporter 部署助手"
echo "======================================"
echo "模式: $MODE"
echo "目录: $PROJECT_DIR"
echo "端口: $PORT"
echo ""

check_command() {
    local name="$1"
    local hint="$2"
    if ! command -v "$name" >/dev/null 2>&1; then
        echo "错误: 未找到 $name。$hint" >&2
        exit 1
    fi
}

print_usage_notes() {
    cat <<EOF

访问地址: http://localhost:$PORT

使用建议:
  1. 打开浏览器访问上面的本地地址。
  2. 使用微信扫描页面二维码，并选择公众号/服务号登录，不要选择小程序。
  3. 在页面中搜索目标公众号，同步文章列表。
  4. 选择文章后导出 JSON 或 Markdown。
  5. 后续导入 testsnow 时按中信用 professional_observation 处理。

安全边界:
  - 本脚本不自动抓取微信公众号内容。
  - 不保存微信登录凭证或 X-Auth-Key 到仓库。
  - 不把公众号内容写入 knowledge/reports/data/raw，除非后续导入脚本显式处理。
EOF
}

run_docker_mode() {
    check_command "docker" "请先安装 Docker Desktop 或 Docker Engine。"
    mkdir -p "$PROJECT_DIR/.data"

    echo "[1/3] 拉取官方 Docker 镜像..."
    if [[ "$NO_START" -eq 1 ]]; then
        echo "跳过 docker pull（--no-start）。"
    else
        docker pull "$IMAGE"
    fi

    echo "[2/3] 准备数据目录..."
    echo "  $PROJECT_DIR/.data -> /app/.data"

    echo "[3/3] 启动信息..."
    local run_cmd
    run_cmd=(
        docker run -d
        --restart always
        --name wechat-article-exporter
        -e NODE_TLS_REJECT_UNAUTHORIZED=0
        -p "$PORT:3000"
        -v "$PROJECT_DIR/.data:/app/.data"
        "$IMAGE"
    )

    if [[ "$NO_START" -eq 1 ]]; then
        echo "未启动服务。需要启动时运行:"
        printf '  %q' "${run_cmd[@]}"
        echo
        return
    fi

    if docker ps -a --format '{{.Names}}' | grep -qx 'wechat-article-exporter'; then
        echo "容器 wechat-article-exporter 已存在，尝试启动已有容器..."
        docker start wechat-article-exporter >/dev/null
    else
        "${run_cmd[@]}"
    fi
}

run_dev_mode() {
    check_command "git" "请先安装 git。"
    check_command "node" "源码模式需要 Node.js 22+。"
    check_command "yarn" "源码模式按官方文档使用 yarn。"

    local NODE_MAJOR
    NODE_MAJOR="$(node --version | sed 's/^v//' | cut -d'.' -f1)"
    if [[ "$NODE_MAJOR" -lt 22 ]]; then
        echo "错误: 当前 Node.js 版本为 $(node --version)，源码模式需要 Node.js 22+。" >&2
        exit 1
    fi

    local clone_url="$REPO_URL"
    if [[ "$USE_MIRROR" -eq 1 ]]; then
        clone_url="$MIRROR_REPO_URL"
    fi

    if [[ -d "$PROJECT_DIR" && "$RECLONE" -eq 1 ]]; then
        echo "[1/4] --reclone 已指定，删除旧目录: $PROJECT_DIR"
        rm -rf "$PROJECT_DIR"
    fi

    if [[ ! -d "$PROJECT_DIR" ]]; then
        echo "[1/4] 克隆源码: $clone_url"
        git clone --depth=1 "$clone_url" "$PROJECT_DIR"
    else
        echo "[1/4] 使用已有源码目录: $PROJECT_DIR"
    fi

    cd "$PROJECT_DIR"

    echo "[2/4] 安装依赖..."
    yarn install

    echo "[3/4] 启动信息..."
    if [[ "$NO_START" -eq 1 ]]; then
        echo "未启动服务。需要启动时运行:"
        echo "  cd $PROJECT_DIR && yarn dev --port $PORT"
        return
    fi

    echo "[4/4] 启动开发服务器..."
    yarn dev --port "$PORT"
}

case "$MODE" in
    docker)
        run_docker_mode
        ;;
    dev)
        run_dev_mode
        ;;
    *)
        echo "未知模式: $MODE" >&2
        exit 2
        ;;
esac

echo ""
echo "======================================"
echo "准备完成"
echo "======================================"
print_usage_notes
